"""Proces: contactgegevens opnieuw nalezen in Lighthouse.

Voor reservaties met aankomst binnenkort die nog geen e-mailadres hebben: het adres kan later
nog in Lighthouse komen. Voor aankomsten van de komende dagen (code-mail) ook kamer, betaling en
status, want kamers worden vaak pas later toegewezen. Draait minder vaak dan het zoeken naar nieuwe reservaties (de robot
beslist wanneer, instelling [robot] contact_refresh_hours in het hotelbestand).
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone

from hotel_checkin.core import workflow
from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse
from hotel_checkin.processes import grant_access, guest_profiles
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


def arrivals_due(hotel_id: str) -> list:
    """Reservaties die binnenkort de code-mail krijgen en nog geen pincode hebben: kamer, betaling
    en status opnieuw lezen (kamers worden vaak pas later toegewezen)."""
    today = date.today()
    days = max([s.days for s in workflow.steps(hotel_id) if s.step == "access_code"] or [0]) + 1
    todo = [r for r in guests.list_reservations(hotel_id)
            if (not r.access_pin and r.status != ReservationStatus.CANCELLED
                and today <= r.arrival <= today + timedelta(days=days))
            # met pincode (nog niet vertrokken): volgen of kamer, data of status veranderen
            or (r.salto_group_id and r.departure >= today)]
    return sorted(todo, key=lambda r: r.arrival)


def _apply_detail(r, d) -> None:
    """Kamer, betaling, status en Lighthouse-status van de detailpagina; contact alleen aanvullen."""
    r.rooms = d.rooms or r.rooms
    r.arrival, r.departure = d.arrival, d.departure
    r.paid = d.paid if d.paid is not None else r.paid
    r.status = d.status
    r.pms_status = d.pms_status or r.pms_status
    if not r.checkin_completed_at:
        r.guest.email = r.guest.email or d.guest.email
        r.guest.phone = r.guest.phone or d.guest.phone


def run(hotel_id: str) -> int:
    """Lees de contactgegevens van die reservaties opnieuw. Geeft het aantal gevonden e-mailadressen terug."""
    started = datetime.now(timezone.utc)
    todo = due(hotel_id)
    arrivals = [r for r in arrivals_due(hotel_id) if r.reservation_id not in {x.reservation_id for x in todo}]
    details_read = 0
    access_changes: list[str] = []
    stats = _ContactStats()
    skipped: list[str] = []
    timings: dict[str, float] = {}  # gemeten duur per onderdeel (seconden), voor de monitor
    try:
        if todo or arrivals:
            t0 = time.monotonic()
            with lighthouse.connect(hotel_id) as lh:
                timings["login"] = round(time.monotonic() - t0, 1)
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
                    if contact.email or contact.phone:
                        guest_profiles.link(reservation)
                # Aankomsten van de komende dagen: kamer en betaling voor de code-mail
                for reservation in arrivals:
                    if time.monotonic() > deadline:
                        break
                    try:
                        detail = lighthouse.get_reservation(hotel_id, reservation.reservation_id, lh)
                    except Exception as exc:  # noqa: BLE001 - volgende keer opnieuw
                        skipped.append(f"{reservation.booking_number or 'reservatie'}: {type(exc).__name__}")
                        continue
                    _apply_detail(reservation, detail)
                    guests.save_reservation(reservation)
                    details_read += 1
                    if reservation.salto_group_id:
                        try:
                            changes = grant_access.follow_changes(hotel_id, reservation)
                        except Exception as exc:  # noqa: BLE001 - volgende keer opnieuw
                            skipped.append(f"{reservation.booking_number or 'reservatie'}: Salto {exc}")
                            continue
                        if changes:
                            access_changes.append(f"{reservation.booking_number}: {'; '.join(changes)}")
    except Exception as exc:
        guests.log_robot_run(hotel_id, TASK, started, False, len(todo), 0, f"{type(exc).__name__}: {exc}", timings=timings)
        raise
    parts = [stats.note()] if stats.read else []
    if details_read:
        parts.append(f"{details_read} aankomsten en verblijven nagekeken (kamer, data, betaling)")
    if access_changes:
        parts.append("Salto aangepast: " + ", ".join(access_changes))
    if skipped:
        parts.append(f"{len(skipped)} niet gelezen: " + "; ".join(skipped[:5]))
    guests.log_robot_run(hotel_id, TASK, started, True, len(todo) + len(arrivals), stats.with_email, ". ".join(parts) or None,
                         skipped=len(skipped), timings=timings | stats.timings())
    return stats.with_email
