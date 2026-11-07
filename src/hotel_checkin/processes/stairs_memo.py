"""Proces: de gast vinkte op het check-in-formulier aan dat een van de gasten moeilijk trappen loopt (geen lift).
Het hotel probeert dan een kamer op een lagere verdieping te geven, als er bij aankomst nog een vrij is.

De robot zet dat in Lighthouse, zodat wie de kamers toewijst het ziet:
- een regel achteraan de interne memo ([checkin] trappen_memo); wat er al staat, blijft staan (alleen aanvullen);
- het label [checkin] trappen_label op het planbord, als het ingevuld is (eerst aanmaken in Lighthouse).
Alleen in PRD, of op een reservatie van een testgast (core/safety.py, may_write_pms). Eén keer per reservatie
(stairs_memo_at). Ook op de schoonmaaklijst (processes/daily_lists.py) en als tag in de monitor.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime

from hotel_checkin.core import clock, safety
from hotel_checkin.core.hotels import load_hotel
from hotel_checkin.core.models import Reservation, ReservationStatus
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse

TASK = "trappen"
MAX_SECONDS = 3 * 60
DEFAULT_MEMO = "Moeilijk ter been (check-in-formulier): lagere verdieping indien vrij"


def settings(hotel_id: str) -> dict:
    c = load_hotel(hotel_id).get("checkin", {})
    return {"memo": str(c.get("trappen_memo") or DEFAULT_MEMO).strip(), "label": str(c.get("trappen_label") or "").strip()}


def candidate(r: Reservation, today: date) -> bool:
    return (bool(r.stairs_help) and r.stairs_memo_at is None and r.status != ReservationStatus.CANCELLED
            and r.departure >= today and safety.may_write_pms(r.hotel_id, r.guest.first_name, r.guest.last_name))


def due(hotel_id: str, today: date | None = None) -> list[Reservation]:
    from hotel_checkin.processes.send_messages import switch

    if not switch(hotel_id, "reservaties"):
        return []
    today = today or clock.today(hotel_id)
    return sorted((r for r in guests.list_reservations(hotel_id) if candidate(r, today)), key=lambda r: r.arrival)


def _label(hotel_id: str, r: Reservation, name: str, lh) -> str:
    """Het label op elke kamer van de reservatie (bestaande labels blijven). Geeft een korte notitie."""
    board = lighthouse.reservation_labels(hotel_id, r.reservation_id, r.arrival, r.departure, lh)
    label_id = board["names"].get(name)
    if not label_id:
        return f"label {name} bestaat niet in Lighthouse"
    for room in board["rooms"]:
        if label_id not in room["labels"]:
            lighthouse.add_label(hotel_id, r.reservation_id, room["accommodation_id"], room["labels"], label_id, lh)
    return f"label {name}"


def run(hotel_id: str, lh, today: date | None = None) -> dict:
    result: dict = {"todo": 0, "done": [], "errors": [], "left": 0}
    todo = due(hotel_id, today)
    result["todo"] = len(todo)
    if not todo:
        return result
    cfg = settings(hotel_id)
    from hotel_checkin.core import progress, run_context

    progress.step(hotel_id, TASK, f"{len(todo)} reservatie(s): moeilijk ter been in de interne memo zetten", force=True)
    stop = run_context.stop_at(MAX_SECONDS)
    for n, r in enumerate(todo, 1):
        if time.monotonic() > stop:
            result["left"] = len(todo) - n + 1
            break
        name = r.booking_number or r.reservation_id[:8]
        try:
            what = lighthouse.append_internal_memo(hotel_id, r.reservation_id, cfg["memo"], lh)
            notes = ["memo aangevuld" if what == "added" else "stond al in de memo"]
            if cfg["label"]:
                notes.append(_label(hotel_id, r, cfg["label"], lh))
        except Exception as exc:  # noqa: BLE001 - volgende run opnieuw
            result["errors"].append(f"{name}: {type(exc).__name__}: {str(exc)[:120]}")
            continue
        r.stairs_memo_at = datetime.now(UTC)
        r.internal_memo = ((r.internal_memo or "").rstrip() + "\n" + cfg["memo"]).strip() if what == "added" else r.internal_memo
        guests.save_reservation(r, fields=guests.STAIRS_MEMO_FIELDS)
        result["done"].append(f"{name} ({', '.join(notes)})")
    return result


def log_run(hotel_id: str, started: datetime, result: dict) -> None:
    if not result["todo"]:
        return
    parts = [f"{len(result['done'])} in Lighthouse gezet: " + "; ".join(result["done"]) if result["done"] else "niets gezet"]
    if result["errors"]:
        parts.append(f"{len(result['errors'])} fout: " + "; ".join(result["errors"][:5]))
    if result["left"]:
        parts.append(f"nog {result['left']} in een volgende run (tijd op)")
    guests.log_robot_run(hotel_id, TASK, started, not result["errors"], result["todo"], len(result["done"]),
                         ". ".join(parts), skipped=len(result["errors"]))
