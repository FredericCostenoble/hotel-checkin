"""Proces: naar welk nummer een oproep op het Twilio-nummer doorgeschakeld wordt.

Volgens [doorschakelen] (lokale tijd van het hotel, instelbaar in de monitor):
1. van avond_van tot avond_tot (bv. 18:30 tot 08:00): [nood] nummer;
2. van receptie_van tot receptie_tot (bv. 10:00 tot 18:30): receptie_nummer (vaste lijn van de receptie);
3. anders: [hotel] telefoon (gsm van het hotel).
Een leeg of ongeldig uur of een leeg nummer: die periode valt weg.

Twilio roept /api/twilio/voice?h=<hotel_id> op (function_app.py). Als dat niet lukt, gebruikt Twilio de vaste
TwiML Bin van het nummer ("Primary handler fails"), die naar de gsm van het hotel doorschakelt.
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


def _within(cfg: dict, prefix: str, t: tuple[int, int]) -> bool:
    start, end = _time(cfg.get(f"{prefix}_van")), _time(cfg.get(f"{prefix}_tot"))
    if start is None or end is None or start == end:
        return False
    return (start <= t or t < end) if start > end else start <= t < end


def period(hotel_id: str, now: datetime | None = None) -> str:
    """"avond", "receptie" of "dag" op dit moment (alleen perioden met een nummer)."""
    from hotel_checkin.core import clock

    hotel = load_hotel(hotel_id)
    cfg = hotel.get("doorschakelen", {})
    local = (now or datetime.now(UTC)).astimezone(clock.tz(hotel_id))
    t = (local.hour, local.minute)
    if hotel.get("nood", {}).get("nummer") and _within(cfg, "avond", t):
        return "avond"
    if cfg.get("receptie_nummer") and _within(cfg, "receptie", t):
        return "receptie"
    return "dag"


def number(hotel_id: str, now: datetime | None = None) -> str:
    """Het nummer om naar door te schakelen."""
    hotel = load_hotel(hotel_id)
    which = period(hotel_id, now)
    if which == "avond":
        return str(hotel["nood"]["nummer"])
    if which == "receptie":
        return str(hotel["doorschakelen"]["receptie_nummer"])
    return str(hotel["hotel"]["telefoon"])
