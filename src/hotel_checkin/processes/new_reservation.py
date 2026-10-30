"""Proces: nieuwe reservatie binnengekomen in Lighthouse.

Voorbeeld van hoe een proces de bouwblokken combineert. Een proces bevat geen
technische details van Lighthouse, Salto of Twilio; die zitten in de bouwblokken.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone

from hotel_checkin.core import workflow
from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse


def run(hotel_id: str, since: datetime) -> int:
    """Haal nieuwe reservaties van een hotel op en bewaar ze. Geeft het aantal nieuwe reservaties terug.

    Van nieuwe reservaties (en van reservaties zonder e-mailadres) worden de contactgegevens gelezen
    als de workflow van het hotel ze nodig heeft. Land en taal komen uit de lijst.
    Wat de gast zelf invulde in het check-in-formulier en het token blijven behouden.
    Elke run wordt gelogd (monitor). De stappen zelf (confirmation, reminder, access_code)
    komen in aparte processen.
    """
    started = datetime.now(timezone.utc)
    found = new = 0
    stats = _ContactStats()
    skipped: list[str] = []
    seen: set[str] = set()
    try:
        with lighthouse.connect(hotel_id) as lh:
            for reservation in lighthouse.get_new_reservations(hotel_id, since, lh, skipped):
                found += 1
                existing = guests.get_reservation(hotel_id, reservation.reservation_id)
                if existing is None:
                    new += 1
                contact = None
                needs_detail = existing is None or (not existing.guest.email and not existing.checkin_completed_at
                                                     and not existing.contact_checked_at)
                if needs_detail and existing is None and not workflow.needs_details_after_booking(hotel_id):
                    needs_detail = False  # geen stap na de boeking: details pas als de aankomst nadert
                if needs_detail:
                    try:
                        t0 = time.monotonic()
                        contact = lighthouse.get_contact(hotel_id, reservation.reservation_id, lh)
                        stats.add(contact, time.monotonic() - t0)
                    except Exception as exc:  # noqa: BLE001 - volgende run probeert opnieuw
                        skipped.append(f"{reservation.booking_number or 'reservatie'}: contact niet gelezen ({type(exc).__name__})")
                if existing is not None:
                    _keep_known(reservation, existing)
                if contact is not None:
                    _apply_contact(reservation, contact)
                guests.save_reservation(reservation)
                seen.add(reservation.reservation_id)
            # Reservaties die binnenkort aankomen en nog geen e-mailadres hebben, alsnog aanvullen
            deadline = time.monotonic() + DETAIL_BACKFILL_SECONDS
            for reservation in _missing_details(hotel_id, seen):
                if time.monotonic() > deadline:
                    break  # de volgende run gaat verder
                try:
                    t0 = time.monotonic()
                    contact = lighthouse.get_contact(hotel_id, reservation.reservation_id, lh)
                    stats.add(contact, time.monotonic() - t0)
                except Exception as exc:  # noqa: BLE001 - volgende run probeert opnieuw
                    skipped.append(f"{reservation.booking_number or 'reservatie'}: contact niet gelezen ({type(exc).__name__})")
                    continue
                _apply_contact(reservation, contact)
                guests.save_reservation(reservation)
    except Exception as exc:
        guests.log_robot_run(hotel_id, TASK, started, False, found, new, f"{type(exc).__name__}: {exc}",
                             since=since, skipped=len(skipped))
        raise
    parts = [stats.note()] if stats.read else []
    if skipped:
        parts.append(f"{len(skipped)} overgeslagen: " + "; ".join(skipped[:5]))
    note = ". ".join(parts) or None
    guests.log_robot_run(hotel_id, TASK, started, True, found, new, note, since=since, skipped=len(skipped))
    return new


# Aanvullen zolang er tijd is: een run mag in Azure max. 15 minuten duren (en in PRD start elk
# kwartier een nieuwe). Wat niet past, doet de volgende run. Rechtstreeks minder dan een seconde
# per reservatie, via de detailpagina een paar seconden.
DETAIL_BACKFILL_SECONDS = 10 * 60


# Details alleen lezen als de workflow ze nodig heeft (core/workflow.py): nieuwe boekingen meteen
# als er een stap na de boeking is, de rest pas vanaf de vroegste stap voor aankomst.


def _missing_details(hotel_id: str, seen: set[str]) -> list:
    """Niet geannuleerde reservaties met aankomst binnenkort, zonder e-mailadres, nog niet door de
    gast aangevuld en nog niet eerder in Lighthouse nagekeken. Eerst wie het eerst aankomt."""
    today = date.today()
    horizon = today + timedelta(days=workflow.detail_window_days(hotel_id))
    todo = [r for r in guests.list_reservations(hotel_id)
            if r.reservation_id not in seen and not r.guest.email and not r.checkin_completed_at
            and not r.contact_checked_at
            and r.status != ReservationStatus.CANCELLED and r.departure >= today and r.arrival <= horizon]
    return sorted(todo, key=lambda r: r.arrival)


class _ContactStats:
    """Telt hoeveel contactgegevens gelezen werden, met en zonder e-mail, en hoe lang het duurde."""

    def __init__(self) -> None:
        self.read = self.with_email = 0
        self.seconds = 0.0

    def add(self, contact, seconds: float) -> None:
        self.read += 1
        self.with_email += 1 if contact.email else 0
        self.seconds += seconds

    def note(self) -> str:
        text = f"{self.read} contactgegevens gelezen ({self.seconds / self.read:.0f} s per reservatie)"
        if self.read - self.with_email:
            text += f", {self.read - self.with_email} zonder e-mail in Lighthouse"
        return text


def _apply_contact(reservation, contact) -> None:
    """Contactgegevens uit Lighthouse; naam en verblijf komen uit de lijst. Status, betaling en
    kamers leest de stap die ze nodig heeft (bv. access_code) zelf, vlak ervoor."""
    reservation.contact_checked_at = datetime.now(timezone.utc)
    if reservation.checkin_completed_at:
        return  # wat de gast zelf invulde, gaat voor
    reservation.guest.email = contact.email or reservation.guest.email
    reservation.guest.phone = contact.phone or reservation.guest.phone
    if contact.country:
        reservation.guest.country, reservation.guest.language = contact.country, contact.language


TASK = "nieuwe_reservaties"


def _keep_known(reservation, existing) -> None:
    reservation.token = existing.token
    reservation.checkin_completed_at = existing.checkin_completed_at
    reservation.contact_checked_at = existing.contact_checked_at
    reservation.paid = existing.paid if reservation.paid is None else reservation.paid
    if existing.checkin_completed_at:
        reservation.guest = existing.guest
        return
    # De lijst bevat geen contactgegevens: eerder opgehaalde waarden niet wissen
    for field in ("email", "phone", "language", "country"):
        if not getattr(reservation.guest, field) or field == "language":
            setattr(reservation.guest, field, getattr(existing.guest, field))
