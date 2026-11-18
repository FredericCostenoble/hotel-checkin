"""Proces: deuren openen vanuit de gast-app (Salto, op afstand openen).

De gast schuift in de gast-app over de knop van een deur; de app vraagt de server die deur te openen. Hier
beslist de server of dat mag. Het Salto-blok opent alleen (access/salto.py, open_lock).

Regels:
- hoofdschakelaar [schakelaars] ontgrendelen aan, Salto ingesteld, en buiten PRD alleen voor testgasten;
- de gast vulde zijn gegevens in, de kamer is betaald en er is een pincode bij Salto;
- alleen de eigen kamers en de gemeenschappelijke deuren ([salto] common_lock_ids), nooit een deur die de pagina
  zelf kiest: de pagina stuurt alleen "front" of "room:<kamer>";
- alleen binnen de periode van de code: kamer van check-in tot [checkout] kamer_tot, voordeur tot voordeur_tot;
- hoogstens MAX_OPENS keer per OPEN_WINDOW per reservatie;
- elke poging die naar Salto gaat, staat in het berichtenlog van de reservatie (zichtbaar in de monitor).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from hotel_checkin.core import safety, workflow
from hotel_checkin.core.models import Channel, Reservation, ReservationStatus, SendResult
from hotel_checkin.guests import repository as guests

FRONT = "front"
MESSAGE_TYPE = "app_unlock"
MAX_OPENS = 10
OPEN_WINDOW = timedelta(minutes=10)


def _switch_on(hotel_id: str) -> bool:
    from hotel_checkin.processes import send_messages

    return send_messages.switch(hotel_id, "ontgrendelen")


def _salto_ready(hotel_id: str) -> bool:
    from hotel_checkin.access import salto

    return salto.configured(hotel_id)


def own_entrance(hotel_id: str, room: str) -> bool:
    """Kamer met een eigen ingang ([kamers.<nummer>] toegang_*): de gast gaat niet via de voordeur."""
    from hotel_checkin.core.hotels import load_hotel

    own = load_hotel(hotel_id).get("kamers", {}).get(str(room))
    return isinstance(own, dict) and any(str(v).strip() for k, v in own.items() if k.startswith("toegang_"))


def has_front_door(hotel_id: str, r: Reservation) -> bool:
    """Toont de app een tegel Voordeur? Ja als minstens één kamer via de voordeur bereikbaar is."""
    return any(not own_entrance(hotel_id, room) for room in r.access_rooms or r.rooms)


def doors(hotel_id: str, r: Reservation) -> list[str]:
    """Deuren die deze gast mag openen: "front" (als een kamer via de voordeur gaat) en "room:<kamer>"."""
    out = [FRONT] if has_front_door(hotel_id, r) else []
    return out + [f"room:{room}" for room in r.access_rooms]


def window(hotel_id: str, r: Reservation, door: str) -> tuple[datetime, datetime]:
    """Van wanneer tot wanneer een deur open mag: die van de pincode bij Salto."""
    from hotel_checkin.processes import grant_access

    start, room_end = grant_access.period(hotel_id, r)
    start = r.access_valid_from or start
    if door == FRONT:
        return start, grant_access.front_until(hotel_id, r)
    return start, r.access_valid_until or room_end


def allowed(hotel_id: str, r: Reservation) -> bool:
    """Mag deze gast deuren openen met de app (los van het tijdstip)?"""
    if r.status == ReservationStatus.CANCELLED or not r.access_codes:
        return False
    if r.checkin_completed_at is None or not workflow.room_paid(r):
        return False
    if not (_switch_on(hotel_id) and _salto_ready(hotel_id)):
        return False
    return safety.is_production() or safety.is_test_guest(hotel_id, r.guest.first_name, r.guest.last_name)


def _recent_opens(hotel_id: str, r: Reservation, now: datetime) -> int:
    since = now - OPEN_WINDOW
    n = 0
    for m in guests.messages_for(hotel_id, r.reservation_id):
        if m.get("message_type") != MESSAGE_TYPE:
            continue
        try:
            if datetime.fromisoformat(m["sent_at"]) >= since:
                n += 1
        except (KeyError, ValueError):
            continue
    return n


def _lock_ids(hotel_id: str, door: str) -> list[str]:
    from hotel_checkin.access import salto

    if door == FRONT:
        return salto.common_lock_ids(hotel_id)
    return salto.lock_ids_for(hotel_id, [door.split(":", 1)[1]], common=False)


def open_door(hotel_id: str, r: Reservation, door: str, now: datetime) -> tuple[bool, str]:
    """Open een deur voor deze gast. Geeft (ok, reden) terug; reden: opened, not_allowed, unknown_door,
    too_early, too_late, too_many, failed."""
    if not allowed(hotel_id, r):
        return False, "not_allowed"
    if door not in doors(hotel_id, r):
        return False, "unknown_door"
    start, end = window(hotel_id, r, door)
    if now < start:
        return False, "too_early"
    if now > end:
        return False, "too_late"
    if _recent_opens(hotel_id, r, now) >= MAX_OPENS:
        return False, "too_many"
    from hotel_checkin.access import salto

    what = "voordeur" if door == FRONT else f"kamer {door.split(':', 1)[1]}"
    try:
        ids = _lock_ids(hotel_id, door)
        if not ids:
            raise salto.SaltoError(f"geen Salto-deur ingesteld voor {what}")
        for lock_id in ids:
            salto.open_lock(hotel_id, lock_id)
    except Exception as exc:  # noqa: BLE001 - de gast krijgt "gebruik je code", de fout staat in het log
        error = str(exc) if isinstance(exc, salto.SaltoError) else f"{type(exc).__name__}: {exc}"
        logging.warning("%s %s: deur niet geopend: %s", hotel_id, r.reservation_id, error)
        guests.log_message(hotel_id, r.reservation_id, MESSAGE_TYPE,
                           SendResult(Channel.APP, what, False, error=error[:500]),
                           note=f"{what} openen via de gast-app mislukt")
        return False, "failed"
    guests.log_message(hotel_id, r.reservation_id, MESSAGE_TYPE, SendResult(Channel.APP, what, True),
                       note=f"{what} geopend via de gast-app")
    return True, "opened"
