"""Proces: toegang geven via Salto voor een reservatie, en weer intrekken.

Combineert de bouwblokken van access/salto.py zoals Salto het aanraadt, per kamer van de boeking:
  gebruiker, access group (deur van die kamer plus de gemeenschappelijke deuren, periode van
  check-in tot check-out), gebruiker in de group, pincode. Meer kamers = meer codes: elke kamer
  (bv. een ander gezin van dezelfde groep) heeft haar eigen code.
De pincode en de ids bij Salto worden bij de reservatie bewaard (opnieuw versturen, opruimen).
Lukt een stap niet, dan wordt wat al aangemaakt was weer verwijderd.

Check-in en check-out: [receptie] van en [checkout] tot in het hotelbestand.
"""

from __future__ import annotations

import logging
from datetime import datetime, time

from hotel_checkin.access import salto
from hotel_checkin.core import clock
from hotel_checkin.core.hotels import load_hotel
from hotel_checkin.core.models import Reservation
from hotel_checkin.guests import repository as guests


def _at(day, hhmm: str, tz) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.combine(day, time(h, m), tzinfo=tz)


def period(hotel_id: str, r: Reservation) -> tuple[datetime, datetime]:
    cfg, tz = load_hotel(hotel_id), clock.tz(hotel_id)
    return (_at(r.arrival, cfg.get("receptie", {}).get("van", "14:00"), tz),
            _at(r.departure, cfg.get("checkout", {}).get("tot", "11:00"), tz))


def _name(r: Reservation, room: str) -> str:
    return f"{r.booking_number or r.reservation_id[:8]} {room} {r.arrival:%d/%m}"


def _grant_room(hotel_id: str, r: Reservation, room: str, valid_from: datetime, valid_until: datetime) -> dict:
    """Gebruiker, access group (voordeur en deze kamer), schema en pincode voor één kamer.
    Lukt een stap niet, dan wordt wat al aangemaakt was weer verwijderd."""
    lock_ids = salto.lock_ids_for(hotel_id, [room])
    user_id = group_id = None
    try:
        user_id = salto.create_user(hotel_id, r.guest.first_name, r.guest.last_name, alias=_name(r, room))
        group_id = salto.create_access_group(hotel_id, _name(r, room))
        salto.add_locks(hotel_id, group_id, lock_ids)
        schedule_id = salto.add_time_schedule(hotel_id, group_id, valid_from, valid_until)
        salto.add_user_to_group(hotel_id, group_id, user_id)
        pin = salto.create_pin(hotel_id, user_id, expiry=valid_until)
    except Exception:
        _cleanup(hotel_id, user_id, group_id)
        raise
    return {"room": room, "pin": pin, "user_id": user_id, "group_id": group_id, "schedule_id": schedule_id}


def grant(hotel_id: str, r: Reservation) -> list[dict]:
    """Eén pincode per kamer (gebruiker en access group per kamer: voordeur en die kamer). Kamers die al
    een code hebben, blijven zoals ze zijn. Geeft de codes terug. Fout als er geen kamer is of Salto faalt;
    codes die al gemaakt waren, blijven bewaard (de volgende poging maakt alleen de rest)."""
    if not r.rooms:
        raise salto.SaltoError("nog geen kamer toegewezen")
    have = set(r.access_rooms)
    todo = [room for room in r.rooms if room not in have]
    if not todo:
        return r.access_codes
    valid_from, valid_until = period(hotel_id, r)
    try:
        for room in todo:
            r.access_codes.append(_grant_room(hotel_id, r, room, valid_from, valid_until))
    finally:
        if len(r.access_codes) > len(have):
            r.access_valid_from, r.access_valid_until = valid_from, valid_until
            guests.save_reservation(r, fields=guests.SALTO_FIELDS)
    return r.access_codes


def follow_changes(hotel_id: str, r: Reservation) -> list[str]:
    """De pincodes volgen de gast: andere kamer = andere deur in dezelfde access group (zelfde gebruiker,
    zelfde pincode); kamer erbij = nieuwe code; kamer weg = die code weg; andere data = schema aangepast;
    geannuleerd = alle toegang weg. Geeft een korte beschrijving van wat veranderde (leeg = niets)."""
    from hotel_checkin.core.models import ReservationStatus

    if not r.access_codes:
        return []
    if r.status == ReservationStatus.CANCELLED:
        revoke(hotel_id, r)
        return ["geannuleerd: toegang ingetrokken"]
    changes: list[str] = []
    wanted = list(r.rooms)
    if wanted:
        removed = [c for c in r.access_codes if c["room"] not in wanted]
        added = [room for room in wanted if room not in r.access_rooms]
        # Andere kamer: de deur wisselen in dezelfde access group, de gast houdt zijn code
        for c, room in zip(removed, added):
            old = set(salto.lock_ids_for(hotel_id, [x.strip() for x in c["room"].split(",") if x.strip()], common=False))
            new = set(salto.lock_ids_for(hotel_id, [room], common=False))
            salto.change_locks(hotel_id, c["group_id"], sorted(new - old), sorted(old - new))
            changes.append(f"kamer {c['room']} naar {room}")
            c["room"] = room
        for c in removed[len(added):]:  # kamer weg
            _cleanup(hotel_id, c.get("user_id"), c.get("group_id"))
            r.access_codes.remove(c)
            changes.append(f"kamer {c['room']}: code ingetrokken")
    valid_from, valid_until = period(hotel_id, r)
    if (valid_from, valid_until) != (r.access_valid_from, r.access_valid_until):
        for c in r.access_codes:
            if c.get("schedule_id"):
                salto.update_time_schedule(hotel_id, c["group_id"], c["schedule_id"], valid_from, valid_until)
            else:
                c["schedule_id"] = salto.add_time_schedule(hotel_id, c["group_id"], valid_from, valid_until)
        changes.append(f"periode {valid_from:%d/%m %H:%M} tot {valid_until:%d/%m %H:%M}")
        r.access_valid_from, r.access_valid_until = valid_from, valid_until
    if changes:
        guests.save_reservation(r, fields=guests.SALTO_FIELDS)
    if wanted and [room for room in wanted if room not in r.access_rooms]:  # kamer erbij: nieuwe code
        before = set(r.access_rooms)
        grant(hotel_id, r)
        changes += [f"kamer {c['room']}: nieuwe code" for c in r.access_codes if c["room"] not in before]
    return changes


def revoke(hotel_id: str, r: Reservation) -> bool:
    """Alle gebruikers en access groups bij Salto verwijderen (na vertrek of bij annulering)."""
    if not r.access_codes:
        return False
    for c in r.access_codes:
        _cleanup(hotel_id, c.get("user_id"), c.get("group_id"))
    r.access_codes = []
    guests.save_reservation(r, fields=guests.SALTO_FIELDS)
    return True


def _cleanup(hotel_id: str, user_id: str | None, group_id: str | None) -> None:
    for kind, fn, ident in (("access group", salto.delete_access_group, group_id), ("gebruiker", salto.delete_user, user_id)):
        if ident:
            try:
                fn(hotel_id, ident)
            except Exception:
                logging.exception("%s: Salto %s %s niet verwijderd", hotel_id, kind, ident)
