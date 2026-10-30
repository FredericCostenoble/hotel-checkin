"""Proces: toegang geven via Salto voor een reservatie, en weer intrekken.

Combineert de bouwblokken van access/salto.py zoals Salto het aanraadt, per boeking:
  gebruiker, access group (deuren van de kamers plus de gemeenschappelijke deuren, periode van
  check-in tot check-out), gebruiker in de group, pincode.
De pincode en de ids bij Salto worden bij de reservatie bewaard (opnieuw versturen, opruimen).
Lukt een stap niet, dan wordt wat al aangemaakt was weer verwijderd.

Check-in en check-out: [receptie] van en [checkout] tot in het hotelbestand.
"""

from __future__ import annotations

import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from hotel_checkin.access import salto
from hotel_checkin.core.hotels import load_hotel
from hotel_checkin.core.models import Reservation
from hotel_checkin.guests import repository as guests

TZ = ZoneInfo("Europe/Brussels")


def _at(day, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.combine(day, time(h, m), tzinfo=TZ)


def period(hotel_id: str, r: Reservation) -> tuple[datetime, datetime]:
    cfg = load_hotel(hotel_id)
    return (_at(r.arrival, cfg.get("receptie", {}).get("van", "14:00")),
            _at(r.departure, cfg.get("checkout", {}).get("tot", "11:00")))


def grant(hotel_id: str, r: Reservation) -> str:
    """Geeft de pincode terug (bestaande als ze er al is). Fout als er geen kamer is of Salto faalt."""
    if r.access_pin and r.salto_user_id:
        return r.access_pin
    if not r.rooms:
        raise salto.SaltoError("nog geen kamer toegewezen")
    lock_ids = salto.lock_ids_for(hotel_id, r.rooms)
    valid_from, valid_until = period(hotel_id, r)
    name = f"{r.booking_number or r.reservation_id[:8]} {r.arrival:%d/%m}"
    user_id = group_id = None
    try:
        user_id = salto.create_user(hotel_id, r.guest.first_name, r.guest.last_name, alias=name)
        group_id = salto.create_access_group(hotel_id, name)
        salto.add_locks(hotel_id, group_id, lock_ids)
        salto.add_time_schedule(hotel_id, group_id, valid_from, valid_until)
        salto.add_user_to_group(hotel_id, group_id, user_id)
        pin = salto.create_pin(hotel_id, user_id, expiry=valid_until)
    except Exception:
        _cleanup(hotel_id, user_id, group_id)
        raise
    r.access_pin, r.salto_user_id, r.salto_group_id = pin, user_id, group_id
    r.access_valid_from, r.access_valid_until = valid_from, valid_until
    guests.save_reservation(r)
    return pin


def revoke(hotel_id: str, r: Reservation) -> bool:
    """Gebruiker en access group bij Salto verwijderen (na vertrek of bij annulering)."""
    if not (r.salto_user_id or r.salto_group_id):
        return False
    _cleanup(hotel_id, r.salto_user_id, r.salto_group_id)
    r.salto_user_id = r.salto_group_id = None
    r.access_pin = None
    guests.save_reservation(r)
    return True


def _cleanup(hotel_id: str, user_id: str | None, group_id: str | None) -> None:
    for kind, fn, ident in (("access group", salto.delete_access_group, group_id), ("gebruiker", salto.delete_user, user_id)):
        if ident:
            try:
                fn(hotel_id, ident)
            except Exception:  # noqa: BLE001 - verder opruimen; staat in het logboek
                logging.exception("%s: Salto %s %s niet verwijderd", hotel_id, kind, ident)
