"""Proces: nieuwe reservatie binnengekomen in Lighthouse.

Voorbeeld van hoe een proces de bouwblokken combineert. Een proces bevat geen
technische details van Lighthouse, Salto of Twilio; die zitten in de bouwblokken.
"""

from __future__ import annotations

from datetime import datetime

from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse


def run(hotel_id: str, since: datetime) -> int:
    """Haal nieuwe reservaties van een hotel op en bewaar ze. Geeft het aantal nieuwe reservaties terug.

    Wat de gast zelf invulde in het check-in-formulier (contactgegevens, taal) en het token
    blijven behouden; Lighthouse overschrijft dat niet.
    Volgende stappen (bevestigingsmail, herinnering, code) komen in aparte processen.
    """
    new = 0
    for reservation in lighthouse.get_new_reservations(hotel_id, since):
        existing = guests.get_reservation(hotel_id, reservation.reservation_id)
        if existing is None:
            new += 1
        else:
            reservation.token = existing.token
            reservation.checkin_completed_at = existing.checkin_completed_at
            reservation.paid = existing.paid if reservation.paid is None else reservation.paid
            if existing.checkin_completed_at:
                reservation.guest = existing.guest
            else:
                # De lijst bevat geen contactgegevens: eerder opgehaalde waarden niet wissen
                for field in ("email", "phone", "language", "country"):
                    if not getattr(reservation.guest, field) or field == "language":
                        setattr(reservation.guest, field, getattr(existing.guest, field))
        guests.save_reservation(reservation)
    return new
