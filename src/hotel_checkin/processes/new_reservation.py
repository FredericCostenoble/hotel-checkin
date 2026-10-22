"""Proces: nieuwe reservatie binnengekomen in Lighthouse.

Voorbeeld van hoe een proces de bouwblokken combineert. Een proces bevat geen
technische details van Lighthouse, Salto of Twilio; die zitten in de bouwblokken.
"""

from __future__ import annotations

from datetime import datetime

from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse


def run(since: datetime) -> int:
    """Haal nieuwe reservaties op en sla de gasten op. Geeft het aantal verwerkte reservaties terug.

    Volgende stappen (bevestigingsmail, check-in uitnodiging, code op D-1) komen in
    aparte processen, zodat elk proces op zijn eigen moment kan lopen.
    """
    reservations = lighthouse.get_new_reservations(since)
    for reservation in reservations:
        guests.save_reservation(reservation)
    return len(reservations)
