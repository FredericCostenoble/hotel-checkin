"""Bouwblok: kleine index-tabellen voor de lijsten in de monitor (Reservaties en Gasten).

Per reservatie en per gastprofiel één korte rij met alleen wat de lijst nodig heeft om te zoeken, te filteren
en te sorteren (naam, datums, kanaal, zoektekst). De monitor leest de index in plaats van alle volledige
reservaties en profielen, en bouwt de volledige gegevens alleen voor de 50 rijen die hij toont.

De index wordt mee bijgewerkt bij elk bewaren en verwijderen (repository.save_reservation,
repository.delete_reservation, profiles.save_profile, profiles.delete_profile). Is de index er nog niet of is
hij van een oudere versie, dan bouwt rebuild() hem opnieuw op uit de volledige tabellen (één keer).

Alleen opslag: wat er gefilterd en gesorteerd wordt, beslist de monitor (admin/service.py).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from hotel_checkin.guests.repository import _key, _q, _table

T_RES_INDEX = "ReservationIndex"
T_GUEST_INDEX = "GuestIndex"
VERSION = "1"  # hoger zetten als de velden van de index veranderen: dan bouwt rebuild() alles opnieuw
_STATE_KEY = "list_index_version"


def _search(*parts) -> str:
    return " ".join(str(p) for p in parts if p).lower()


def reservation_row(r) -> dict:
    g = r.guest
    return {
        "PartitionKey": _key(r.hotel_id), "RowKey": _key(r.reservation_id), "id": r.reservation_id,
        "arrival": r.arrival.isoformat(), "departure": r.departure.isoformat(),
        "guest": f"{g.first_name} {g.last_name}".strip(), "booking_number": r.booking_number or "",
        "status": r.status.value, "source": r.source or "", "pms_status": r.pms_status or "",
        "rooms": json.dumps(r.rooms), "room_type": r.room_type or "", "guest_id": r.guest_id or "",
        "email": g.email or "", "phone": g.phone or "",
        "search": _search(g.first_name, g.last_name, r.booking_number, g.email, g.phone, g.backup_email, g.backup_phone),
        "indexed_at": datetime.now(UTC).isoformat(),
    }


def guest_row(p) -> dict:
    channels = sorted(p.channels.items(), key=lambda kv: -kv[1])
    return {
        "PartitionKey": _key(p.hotel_id), "RowKey": p.guest_id, "id": p.guest_id,
        "name": f"{p.first_name} {p.last_name}".strip(), "country": p.country or "",
        "stays": p.stays, "reservations": len(p.reservation_ids),
        "last_stay": p.last_stay.isoformat() if p.last_stay else "",
        "first_stay": p.first_stay.isoformat() if p.first_stay else "",
        "preferred_channel": channels[0][0] if channels else "",
        "email": p.email or "", "phone": p.phone or "",
        "search": _search(p.first_name, p.last_name, p.email, p.phone, p.backup_email, p.backup_phone,
                          *p.known_emails, *p.known_phones),
        "indexed_at": datetime.now(UTC).isoformat(),
    }


def _row(e: dict) -> dict:
    out = {k: v for k, v in dict(e).items() if k not in ("PartitionKey", "RowKey", "search", "indexed_at")}
    out["search"] = e.get("search", "")
    if "rooms" in out and isinstance(out["rooms"], str):
        out["rooms"] = json.loads(out["rooms"] or "[]")
    return out


def put_reservation(r) -> None:
    try:
        _table(T_RES_INDEX).upsert_entity(reservation_row(r))
    except Exception:  # noqa: BLE001 - de index mag het bewaren nooit doen mislukken; rebuild herstelt hem
        pass


def drop_reservation(hotel_id: str, reservation_id: str) -> None:
    try:
        _table(T_RES_INDEX).delete_entity(_key(hotel_id), _key(reservation_id))
    except Exception:  # noqa: BLE001 - stond er niet in
        pass


def put_guest(p) -> None:
    try:
        _table(T_GUEST_INDEX).upsert_entity(guest_row(p))
    except Exception:  # noqa: BLE001 - zie put_reservation
        pass


def drop_guest(hotel_id: str, guest_id: str) -> None:
    try:
        _table(T_GUEST_INDEX).delete_entity(_key(hotel_id), guest_id)
    except Exception:  # noqa: BLE001
        pass


def reservations(hotel_id: str) -> list[dict]:
    ensure(hotel_id)
    return [_row(e) for e in _table(T_RES_INDEX).query_entities(f"PartitionKey eq '{_q(_key(hotel_id))}'")]


def guests(hotel_id: str) -> list[dict]:
    ensure(hotel_id)
    return [_row(e) for e in _table(T_GUEST_INDEX).query_entities(f"PartitionKey eq '{_q(_key(hotel_id))}'")]


def ensure(hotel_id: str) -> None:
    """Index opbouwen als hij er nog niet is of van een oudere versie is."""
    from hotel_checkin.guests import repository

    if repository.get_state(hotel_id, _STATE_KEY) != VERSION:
        rebuild(hotel_id)


def rebuild(hotel_id: str) -> dict:
    """Index volledig opnieuw opbouwen uit de tabellen Reservations en Guests (ook rijen die er niet meer horen weg)."""
    from hotel_checkin.guests import profiles, repository

    counts = {}
    for table, items, row, key in (
        (T_RES_INDEX, repository.list_reservations(hotel_id), reservation_row, lambda x: _key(x.reservation_id)),
        (T_GUEST_INDEX, profiles.list_profiles(hotel_id), guest_row, lambda x: x.guest_id),
    ):
        t = _table(table)
        keep = set()
        for x in items:
            t.upsert_entity(row(x))
            keep.add(key(x))
        for e in list(t.query_entities(f"PartitionKey eq '{_q(_key(hotel_id))}'")):
            if e["RowKey"] not in keep:
                t.delete_entity(e["PartitionKey"], e["RowKey"])
        counts[table] = len(keep)
    repository.set_state(hotel_id, _STATE_KEY, VERSION)
    return counts
