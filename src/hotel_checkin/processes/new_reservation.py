"""Proces: nieuwe reservatie binnengekomen in Lighthouse.

Voorbeeld van hoe een proces de bouwblokken combineert. Een proces bevat geen
technische details van Lighthouse, Salto of Twilio; die zitten in de bouwblokken.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from hotel_checkin.core import workflow
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse
from hotel_checkin.processes import guest_profiles


def run(hotel_id: str, since: datetime) -> int:
    """Haal nieuwe reservaties van een hotel op en bewaar ze. Geeft het aantal nieuwe reservaties terug.

    Van nieuwe reservaties worden meteen de contactgegevens gelezen als de workflow van het hotel
    ze nodig heeft. Land en taal komen uit de lijst. Bestaande reservaties zonder e-mailadres:
    zie refresh_contacts.py.
    Wat de gast zelf invulde in het check-in-formulier en het token blijven behouden.
    Elke run wordt gelogd (monitor). De stappen zelf (confirmation, reminder, access_code)
    komen in aparte processen.
    """
    started = datetime.now(timezone.utc)
    found = new = 0
    stats = _ContactStats()
    skipped: list[str] = []
    timings: dict[str, float] = {}  # gemeten duur per onderdeel (seconden), voor de monitor
    try:
        t0 = time.monotonic()
        with lighthouse.connect(hotel_id) as lh:
            timings["login"] = round(time.monotonic() - t0, 1)
            t0 = time.monotonic()
            listed = lighthouse.get_new_reservations(hotel_id, since, lh, skipped)
            timings["list"] = round(time.monotonic() - t0, 1)
            pool = guest_profiles.profiles.list_profiles(hotel_id)  # één keer laden per run
            details_after_booking = workflow.needs_details_after_booking(hotel_id)
            for reservation in listed:
                found += 1
                existing = guests.get_reservation(hotel_id, reservation.reservation_id)
                if existing is None:
                    new += 1
                contact = None
                # Alleen van nieuwe reservaties meteen de contactgegevens (als de workflow een stap na
                # de boeking heeft). Bestaande zonder e-mail: proces refresh_contacts, minder vaak.
                needs_detail = existing is None and details_after_booking
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
                if contact is not None or existing is None:
                    guest_profiles.link(reservation, pool)
    except Exception as exc:
        guests.log_robot_run(hotel_id, TASK, started, False, found, new, f"{type(exc).__name__}: {exc}",
                             since=since, skipped=len(skipped), timings=timings | stats.timings())
        raise
    parts = [stats.note()] if stats.read else []
    if skipped:
        parts.append(f"{len(skipped)} overgeslagen: " + "; ".join(skipped[:5]))
    note = ". ".join(parts) or None
    guests.log_robot_run(hotel_id, TASK, started, True, found, new, note, since=since, skipped=len(skipped), timings=timings | stats.timings())
    return new


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
        parts = []
        if self.with_email:
            parts.append(f"{self.with_email} contactgegevens gevonden")
        if self.read - self.with_email:
            parts.append(f"{self.read - self.with_email} nog zonder e-mail in Lighthouse")
        return ", ".join(parts)

    def timings(self) -> dict[str, float]:
        """Gemiddelde duur per reservatie (seconden), alleen als er gelezen werd."""
        return {"contact": round(self.seconds / self.read, 1), "contacts": self.read} if self.read else {}


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
