"""Bouwblok: gastprofielen bewaren (tabel Guests) en paren die geen dezelfde gast zijn (tabel GuestPairs).

Alleen opslag. Wie bij wie hoort en wanneer een verblijf meetelt, beslist het proces
processes/guest_profiles.py.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime

from hotel_checkin.core.models import GuestProfile
from hotel_checkin.guests.repository import _key, _now, _q, _table

T_GUESTS = "Guests"
T_PAIRS = "GuestPairs"

_JSON = ("rooms", "room_types", "channels", "reservation_ids", "stay_periods", "message_channels", "muted_channels",
         "known_emails", "known_phones")
_DATES = ("first_stay", "last_stay", "last_cancelled")
_TIMES = ("created_at", "updated_at")


def _to_entity(g: GuestProfile) -> dict:
    e = {"PartitionKey": _key(g.hotel_id), "RowKey": g.guest_id}
    for k, v in vars(g).items():
        if k in _JSON:
            e[k] = json.dumps(v)
        elif k in _DATES or k in _TIMES:
            e[k] = v.isoformat() if v else ""
        elif isinstance(v, bool):
            e[k] = "true" if v else ""
        else:
            e[k] = "" if v is None else v
    return e


def _from_entity(e: dict) -> GuestProfile:
    g = GuestProfile(hotel_id=e["hotel_id"], guest_id=e["guest_id"])
    for k in vars(g):
        if k in ("hotel_id", "guest_id") or k not in e:
            continue
        v = e[k]
        if k in _JSON:
            setattr(g, k, json.loads(v or ("[]" if k in ("reservation_ids", "stay_periods", "message_channels", "muted_channels", "known_emails", "known_phones") else "{}")))
        elif k in _DATES:
            setattr(g, k, date.fromisoformat(v) if v else None)
        elif k in _TIMES:
            setattr(g, k, datetime.fromisoformat(v) if v else None)
        elif isinstance(getattr(g, k), bool):
            setattr(g, k, v in (True, "true", "True"))
        elif isinstance(getattr(g, k), int):
            setattr(g, k, int(v or 0))
        else:
            setattr(g, k, v or (None if k in ("email", "phone", "country", "backup_email", "backup_phone") else ""))
    return g


def new_profile(hotel_id: str) -> GuestProfile:
    return GuestProfile(hotel_id=hotel_id, guest_id=uuid.uuid4().hex)


def save_profile(g: GuestProfile) -> GuestProfile:
    now = _now()
    g.created_at = g.created_at or now
    g.updated_at = now
    _table(T_GUESTS).upsert_entity(_to_entity(g))
    return g


def get_profile(hotel_id: str, guest_id: str) -> GuestProfile | None:
    try:
        return _from_entity(_table(T_GUESTS).get_entity(_key(hotel_id), guest_id))
    except Exception:  # noqa: BLE001 - niet gevonden
        return None


def list_profiles(hotel_id: str) -> list[GuestProfile]:
    rows = _table(T_GUESTS).query_entities(f"PartitionKey eq '{_q(_key(hotel_id))}'")
    return [_from_entity(e) for e in rows]


def delete_profile(hotel_id: str, guest_id: str) -> None:
    _table(T_GUESTS).delete_entity(_key(hotel_id), guest_id)


def _pair_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def mark_different(hotel_id: str, a: str, b: str) -> None:
    """Onthoud dat twee profielen niet dezelfde gast zijn (keuze in de monitor)."""
    _table(T_PAIRS).upsert_entity({"PartitionKey": _key(hotel_id), "RowKey": _pair_key(a, b),
                                   "decision": "different", "at": _now().isoformat()})


def different_pairs(hotel_id: str) -> set[str]:
    rows = _table(T_PAIRS).query_entities(f"PartitionKey eq '{_q(_key(hotel_id))}'")
    return {e["RowKey"] for e in rows if e.get("decision") == "different"}


def is_marked_different(pairs: set[str], a: str, b: str) -> bool:
    return _pair_key(a, b) in pairs
