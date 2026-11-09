"""Proces: zelftest van Lighthouse. Staat alles wat de robot nodig heeft nog op de pagina's (reservatielijst,
detailpagina, planbord)? Lighthouse kan zijn schermen op elk moment veranderen; dan moet dat meteen opvallen,
voor er gasten of lijsten getroffen worden.

- Eén keer per dag, in een run die toch al draait (geen extra run), en meteen als de robot in één run
  meerdere reservaties niet kon lezen (FORCE_AFTER).
- Klopt iets niet: de pagina wordt als bewijs bewaard (guests.save_evidence), de robot schrijft niets meer in
  Lighthouse (blocked, via core/safety.py may_write_pms) en de bewaking stuurt meteen een waarschuwing
  (processes/oversight.py). Lezen gaat gewoon door.
- Is de zelftest daarna weer in orde (bv. na een herstelling), dan mag de robot vanzelf weer schrijven.
Alleen lezen in Lighthouse; de technische details staan in het Lighthouse-blok (pms/lighthouse.py, self_test).
"""

from __future__ import annotations

import json
import time
from datetime import UTC, date, datetime

from hotel_checkin.core import clock
from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse

TASK = "zelftest"
STATE = "pms_health"  # RobotState: {"checked_at", "day", "ok", "failures": [{"part", "why", "evidence"}]}
FORCE_AFTER = 3  # zoveel reservaties niet gelezen in één run: meteen de zelftest
_cache: dict[str, tuple[float, dict]] = {}


def state(hotel_id: str) -> dict:
    try:
        return json.loads(guests.get_state(hotel_id, STATE) or "{}")
    except ValueError:
        return {}


def blocked(hotel_id: str) -> bool:
    """Mag de robot niet schrijven in Lighthouse, omdat de laatste zelftest een probleem vond? (kort onthouden)"""
    now = time.monotonic()
    hit = _cache.get(hotel_id)
    if hit is None or now - hit[0] > 60:
        hit = (now, state(hotel_id))
        _cache[hotel_id] = hit
    return hit[1].get("ok") is False


def due(hotel_id: str, today: date | None = None) -> bool:
    """Eén keer per dag, en meteen als ze gevraagd werd (bv. een nieuwe versie met een herstelling op TST)."""
    from hotel_checkin.processes import repair

    today = today or clock.today(hotel_id)
    return state(hotel_id).get("day") != today.isoformat() or bool(guests.get_state(hotel_id, repair.SELFTEST_REQUEST))


def _sample(hotel_id: str, today: date) -> str | None:
    """Een reservatie met een kamer die binnenkort aankomt of nu verblijft, om de detailpagina na te kijken."""
    rs = [r for r in guests.list_reservations(hotel_id)
          if r.rooms and r.status != ReservationStatus.CANCELLED and r.departure >= today]
    rs.sort(key=lambda r: abs((r.arrival - today).days))
    return rs[0].reservation_id if rs else None


def run(hotel_id: str, lh, reason: str = "dagelijks") -> dict:
    started = datetime.now(UTC)
    today = clock.today(hotel_id)
    results = lighthouse.self_test(hotel_id, lh, _sample(hotel_id, today), today)
    failures = []
    for x in results:
        if x["ok"]:
            continue
        key = guests.save_evidence(hotel_id, x["part"], {"part": x["part"], "why": x["why"], "reason": reason},
                                   x["html"] or "")
        failures.append({"part": x["part"], "why": x["why"], "evidence": key})
    before = state(hotel_id)
    st = {"checked_at": started.isoformat(), "day": today.isoformat(), "ok": not failures, "failures": failures,
          "since": (before.get("since") if before.get("ok") is False else started.isoformat()) if failures else ""}
    from hotel_checkin.processes import oversight, repair

    if failures and before.get("ok") is not False:  # nieuw probleem: de herstelrobot vragen (één keer)
        st["repair"] = (repair.request(hotel_id, failures) if oversight.settings(hotel_id)["monitoring"]
                        else "herstelrobot niet gevraagd (monitoring staat uit)")
    elif failures:
        st["repair"] = before.get("repair", "")
    guests.set_state(hotel_id, STATE, json.dumps(st))
    guests.delete_state(hotel_id, repair.SELFTEST_REQUEST)
    _cache.pop(hotel_id, None)
    if failures:
        note = ("Lighthouse is mogelijk veranderd, de robot schrijft niets meer in Lighthouse tot dit opgelost is: "
                + "; ".join(f"{f['part']}: {f['why']}" for f in failures) + f". {st.get('repair', '')}")
    else:
        note = ("alles gevonden (reservatielijst, detailpagina, planbord)"
                + (": de robot mag weer schrijven in Lighthouse" if before.get("ok") is False else ""))
    guests.log_robot_run(hotel_id, TASK, started, not failures, len(results), len(results) - len(failures),
                         f"{reason}: {note}")
    return st
