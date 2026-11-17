"""Proces: naar welk nummer een oproep op het Twilio-nummer doorgeschakeld wordt.

Overdag naar de telefoon van het hotel ([hotel] telefoon), 's avonds en 's nachts naar het noodnummer
([nood] nummer), volgens [doorschakelen] avond_van en avond_tot (lokale tijd van het hotel, bv. 18:30 tot 08:00).
Leeg of ongeldig uur, of geen noodnummer: altijd de telefoon van het hotel.

Twilio roept /api/twilio/voice?h=<hotel_id> op (function_app.py). Als dat niet lukt, gebruikt Twilio de vaste
TwiML Bin van het nummer ("Primary handler fails"), die naar de telefoon van het hotel doorschakelt.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from hotel_checkin.core.hotels import load_hotel


def _time(raw) -> tuple[int, int] | None:
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(raw or ""))
    if not m or int(m[1]) > 23 or int(m[2]) > 59:
        return None
    return int(m[1]), int(m[2])


def is_evening(hotel_id: str, now: datetime | None = None) -> bool:
    """Valt dit moment in het avond- en nachtvenster van het hotel?"""
    from hotel_checkin.core import clock

    cfg = load_hotel(hotel_id).get("doorschakelen", {})
    start, end = _time(cfg.get("avond_van")), _time(cfg.get("avond_tot"))
    if start is None or end is None or start == end:
        return False
    local = (now or datetime.now(UTC)).astimezone(clock.tz(hotel_id))
    t = (local.hour, local.minute)
    return (start <= t or t < end) if start > end else start <= t < end


def number(hotel_id: str, now: datetime | None = None) -> str:
    """Het nummer om naar door te schakelen."""
    hotel = load_hotel(hotel_id)
    day = str(hotel["hotel"]["telefoon"])
    evening = str(hotel.get("nood", {}).get("nummer") or "")
    return evening if evening and is_evening(hotel_id, now) else day
