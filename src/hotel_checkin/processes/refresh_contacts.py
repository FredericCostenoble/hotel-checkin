"""Proces: contactgegevens opnieuw nalezen in Lighthouse.

Voor reservaties met aankomst binnenkort die nog geen e-mailadres hebben: het adres kan later
nog in Lighthouse komen. Draait minder vaak dan het zoeken naar nieuwe reservaties (de robot
beslist wanneer, instelling [robot] contact_refresh_hours in het hotelbestand).
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone

from hotel_checkin.core import workflow
from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse
from hotel_checkin.processes.new_reservation import _apply_contact, _ContactStats

TASK = "contactgegevens_nalezen"

# Zolang er tijd is: een run mag in Azure max. 15 minuten duren. Wat niet past, doet de volgende run.
MAX_SECONDS = 10 * 60


def due(hotel_id: str) -> list:
    """Niet geannuleerde reservaties met aankomst binnen het venster van de workflow, zonder
    e-mailadres en nog niet door de gast aangevuld. Eerst wie het eerst aankomt."""
    today = date.today()
    horizon = today + timedelta(days=workflow.detail_window_days(hotel_id))
    todo = [r for r in guests.list_reservations(hotel_id)
            if not r.guest.email and not r.checkin_completed_at
            and r.status != ReservationStatus.CANCELLED and r.departure >= today and r.arrival <= horizon]
    return sorted(todo, key=lambda r: r.arrival)


def run(hotel_id: str) -> int:
    """Lees de contactgegevens van die reservaties opnieuw. Geeft het aantal gevonden e-mailadressen terug."""
    started = datetime.now(timezone.utc)
    todo = due(hotel_id)
    stats = _ContactStats()
    skipped: list[str] = []
    try:
        if todo:
            with lighthouse.connect(hotel_id) as lh:
                deadline = time.monotonic() + MAX_SECONDS
                for reservation in todo:
                    if time.monotonic() > deadline:
                        break
                    try:
                        t0 = time.monotonic()
                        contact = lighthouse.get_contact(hotel_id, reservation.reservation_id, lh)
                        stats.add(contact, time.monotonic() - t0)
                    except Exception as exc:  # noqa: BLE001 - volgende keer opnieuw
                        skipped.append(f"{reservation.booking_number or 'reservatie'}: {type(exc).__name__}")
                        continue
                    _apply_contact(reservation, contact)
                    guests.save_reservation(reservation)
    except Exception as exc:
        guests.log_robot_run(hotel_id, TASK, started, False, len(todo), 0, f"{type(exc).__name__}: {exc}")
        raise
    parts = [stats.note()] if stats.read else []
    if skipped:
        parts.append(f"{len(skipped)} niet gelezen: " + "; ".join(skipped[:5]))
    guests.log_robot_run(hotel_id, TASK, started, True, len(todo), stats.with_email, ". ".join(parts) or None,
                         skipped=len(skipped))
    return stats.with_email
