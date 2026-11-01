"""Vraag om reservaties meteen opnieuw na te lezen (gewijzigd of geannuleerd).

De meldingsmail van Cubilis bevat het Cubilis-nummer (niet het Lighthouse-nummer) en de aankomstdag.
De mailtrigger (Function App) noteert die dagen; de robot leest bij de volgende run de reservaties
met die aankomst- of vertrekdag opnieuw (refresh_contacts.py) en wist daarna de dagen die klaar zijn.
Opgeslagen in RobotState, per hotel. Geen browser, geen Lighthouse: ook bruikbaar in de Function App.
"""

from __future__ import annotations

import json
from datetime import date

from hotel_checkin.guests import repository as guests

STATE_KEY = "refresh_dates"


def requested(hotel_id: str) -> set[str]:
    """ISO-dagen waarvoor een nalezing gevraagd is."""
    try:
        return set(json.loads(guests.get_state(hotel_id, STATE_KEY) or "[]"))
    except ValueError:
        return set()


def request(hotel_id: str, days: list[date]) -> None:
    days_iso = {d.isoformat() for d in days if d}
    if not days_iso:
        return
    current = requested(hotel_id)
    if not days_iso <= current:
        guests.set_state(hotel_id, STATE_KEY, json.dumps(sorted(current | days_iso)))


def done(hotel_id: str, days: set[str]) -> None:
    """Dagen die nagelezen zijn, wissen (wat intussen bijkwam, blijft staan)."""
    if not days:
        return
    current = requested(hotel_id)
    if current & days:
        guests.set_state(hotel_id, STATE_KEY, json.dumps(sorted(current - days)))
