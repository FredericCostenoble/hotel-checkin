"""Datum en tijd in de tijdzone van het hotel.

Azure draait in UTC: date.today() is daar tot 1 of 2 uur 's nachts nog "gisteren" in Brussel. De
dagen van de workflow (herinnering, code-mail, opruimen) horen bij de kalender van het hotel.
Tijdzone: [hotel] tijdzone in config/hotels/<hotel_id>.toml, standaard Europe/Brussels.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Europe/Brussels"


def tz(hotel_id: str) -> ZoneInfo:
    from hotel_checkin.core.hotels import load_hotel

    return ZoneInfo(load_hotel(hotel_id).get("hotel", {}).get("tijdzone") or DEFAULT_TZ)


def today(hotel_id: str) -> date:
    return datetime.now(tz(hotel_id)).date()
