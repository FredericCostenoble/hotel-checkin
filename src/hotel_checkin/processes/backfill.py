"""Proces: eenmalig de oudere boekingen voor toekomstige verblijven binnenhalen.

Het systeem kende alleen reservaties die het zelf binnenhaalde sinds de start (de robot leest nieuwe boekingen).
Wie vroeger boekte voor een verblijf dat nog moet komen (bv. geboekt in januari voor december), stond er niet in,
dus overschrijvingen en ontbijtlabels sloegen die over. Deze taak bladert eenmalig door de hele reservatielijst
van Lighthouse (nieuwste boeking eerst) en bewaart elke reservatie met een vertrek vandaag of later.
- Geen berichten voor deze reservaties: ze zijn geboekt voor [messaging] start (send_messages.before_start).
- Geen contactgegevens lezen (kan later, Reservaties bijwerken); alleen wat in de lijst staat.
- Hoogstens MAX_SECONDS per run; de volgende run gaat verder waar deze stopte (state backfill_page).
- Klaar als een pagina leeg is of alleen boekingen ouder dan MAX_YEARS jaar heeft (state backfill_done).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

from hotel_checkin.core import clock
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse

TASK = "oude_boekingen"
PAGE_KEY = "backfill_page"
DONE_KEY = "backfill_done"
MAX_SECONDS = 5 * 60
MAX_YEARS = 2


def done(hotel_id: str) -> bool:
    return bool(guests.get_state(hotel_id, DONE_KEY))


def run(hotel_id: str, lh) -> None:
    from hotel_checkin.core import progress

    started = datetime.now(UTC)
    today = clock.today(hotel_id)
    first = max(0, int(guests.get_state(hotel_id, PAGE_KEY) or 0) - 1)  # één pagina overlap: lijst schuift op
    cutoff = datetime.now(UTC) - timedelta(days=365 * MAX_YEARS)
    stop = time.monotonic() + MAX_SECONDS
    number, rows_seen, stored, finished, skipped = first, 0, [], False, []
    progress.step(hotel_id, TASK, f"oudere boekingen binnenhalen vanaf pagina {first + 1}", force=True)
    while time.monotonic() < stop:
        rows = lighthouse.list_page(hotel_id, number, lh, skipped)
        if not rows:
            finished = True
            break
        rows_seen += len(rows)
        for r in rows:
            if r.departure < today or guests.get_reservation(hotel_id, r.reservation_id) is not None:
                continue
            guests.save_reservation(r)
            stored.append(r)
        oldest = min((r.booked_at for r in rows if r.booked_at), default=None)
        number += 1
        progress.step(hotel_id, TASK, f"pagina {number}: {rows_seen} reservaties gelezen, {len(stored)} toekomstige "
                                      "nieuw bewaard")
        if oldest is not None and (oldest if oldest.tzinfo else oldest.replace(tzinfo=UTC)) < cutoff:
            finished = True
            break
    guests.set_state(hotel_id, PAGE_KEY, str(number))
    if finished:
        guests.set_state(hotel_id, DONE_KEY, datetime.now(UTC).isoformat())
    examples = ", ".join(f"{r.booking_number or r.reservation_id[:8]} ({r.arrival:%d/%m/%Y})" for r in stored[:6])
    note = (f"eenmalig: oudere boekingen voor toekomstige verblijven binnenhalen. Pagina {first + 1} tot {number} "
            f"gelezen ({rows_seen} reservaties), {len(stored)} toekomstige nieuw bewaard"
            + (f", bv. {examples}" if examples else "")
            + ". Geen berichten voor deze reservaties (geboekt voor de start). "
            + ("Klaar." if finished else "Nog niet klaar: de volgende run gaat verder (tijd op)."))
    if skipped:
        note += f" {len(skipped)} rij(en) niet leesbaar: " + "; ".join(skipped[:3])
    logging.info("%s: %s", hotel_id, note)
    guests.log_robot_run(hotel_id, TASK, started, True, rows_seen, len(stored), note, skipped=len(skipped))
