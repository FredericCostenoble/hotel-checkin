"""Bouwblok 5: reservaties, verstuurde berichten en marketing-bezwaren opslaan (Azure Table Storage).

Drie tabellen:
- Reservations: een rij per reservatie (gast, data, kamer, token voor het check-in-formulier).
- Messages: een rij per verstuurd bericht (type, kanaal, ontvanger, tijdstip, resultaat).
  Daarmee vermijden we dubbele berichten.
- MarketingOptOut: blokkeerlijst per e-mailadres, los van de reservaties. Wie hier staat,
  krijgt geen commerciele mails meer. Verblijfsmails blijven wel vertrekken.

Verbinding:
- Productie: instelling STORAGE_TABLE_ENDPOINT (bv. https://<account>.table.core.windows.net),
  aanmelden met DefaultAzureCredential (in de codespace de app registration hotel-checkin,
  in Azure de managed identity). Geen opslagsleutels.
- Alternatief (bv. lokale emulator Azurite): STORAGE_CONNECTION_STRING.

Bewaartermijnen (zie privacyverklaring): opschonen gebeurt later in een apart proces.
"""

from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import date, datetime, timezone
from functools import lru_cache
from urllib.parse import quote

from hotel_checkin.core.models import Guest, Reservation, ReservationStatus, SendResult

T_RESERVATIONS = "Reservations"
T_MESSAGES = "Messages"
T_OPTOUT = "MarketingOptOut"
_PK_RESERVATION = "reservation"
_PK_OPTOUT = "optout"

_client_factory = None  # alleen voor tests: functie die een tabelnaam krijgt en een tabel teruggeeft


def _now() -> datetime:
    return datetime.now(timezone.utc)


@lru_cache
def _service():
    from azure.data.tables import TableServiceClient

    conn = os.environ.get("STORAGE_CONNECTION_STRING")
    if conn:
        return TableServiceClient.from_connection_string(conn)
    from azure.identity import DefaultAzureCredential

    from hotel_checkin.core.config import get_setting

    return TableServiceClient(
        endpoint=get_setting("STORAGE_TABLE_ENDPOINT"), credential=DefaultAzureCredential()
    )


_ready: set[str] = set()


def _table(name: str):
    if _client_factory is not None:
        return _client_factory(name)
    if name not in _ready:
        _service().create_table_if_not_exists(name)
        _ready.add(name)
    return _service().get_table_client(name)


def _key(value: str) -> str:
    """RowKey mag geen / \\ # ? bevatten; daarom coderen."""
    return quote(value, safe="@.+-_")


def _q(value: str) -> str:
    return value.replace("'", "''")


# ---------------------------------------------------------------- reservaties


def _to_entity(r: Reservation) -> dict:
    return {
        "PartitionKey": _PK_RESERVATION,
        "RowKey": _key(r.reservation_id),
        "reservation_id": r.reservation_id,
        "first_name": r.guest.first_name,
        "last_name": r.guest.last_name,
        "email": (r.guest.email or "").lower(),
        "phone": r.guest.phone or "",
        "language": r.guest.language,
        "country": (r.guest.country or "").upper(),
        "backup_email": (r.guest.backup_email or "").lower(),
        "backup_phone": r.guest.backup_phone or "",
        "arrival": r.arrival.isoformat(),
        "departure": r.departure.isoformat(),
        "rooms": json.dumps(r.rooms),
        "room_type": r.room_type or "",
        "status": r.status.value,
        "source": r.source or "",
        "paid": "" if r.paid is None else str(r.paid),
        "token": r.token or "",
        "checkin_completed_at": r.checkin_completed_at.isoformat() if r.checkin_completed_at else "",
        "updated_at": _now().isoformat(),
    }


def _from_entity(e: dict) -> Reservation:
    return Reservation(
        reservation_id=e["reservation_id"],
        guest=Guest(
            first_name=e["first_name"],
            last_name=e["last_name"],
            email=e["email"] or None,
            phone=e["phone"] or None,
            language=e["language"],
            country=e.get("country") or None,
            backup_email=e.get("backup_email") or None,
            backup_phone=e.get("backup_phone") or None,
        ),
        arrival=date.fromisoformat(e["arrival"]),
        departure=date.fromisoformat(e["departure"]),
        rooms=json.loads(e["rooms"]),
        status=ReservationStatus(e["status"]),
        source=e["source"] or None,
        paid=None if e["paid"] == "" else e["paid"] == "True",
        room_type=e["room_type"] or None,
        token=e["token"] or None,
        checkin_completed_at=(
            datetime.fromisoformat(e["checkin_completed_at"]) if e["checkin_completed_at"] else None
        ),
    )


def save_reservation(reservation: Reservation) -> Reservation:
    """Bewaar of werk bij. Een nieuwe reservatie krijgt een token; een bestaand token blijft behouden."""
    if not reservation.token:
        existing = get_reservation(reservation.reservation_id)
        reservation.token = existing.token if existing and existing.token else secrets.token_urlsafe(24)
    entity = _to_entity(reservation)
    table = _table(T_RESERVATIONS)
    try:
        created = table.get_entity(_PK_RESERVATION, entity["RowKey"])["created_at"]
    except Exception:  # noqa: BLE001 - bestaat nog niet
        created = _now().isoformat()
    entity["created_at"] = created
    table.upsert_entity(entity)
    return reservation


def get_reservation(reservation_id: str) -> Reservation | None:
    try:
        return _from_entity(_table(T_RESERVATIONS).get_entity(_PK_RESERVATION, _key(reservation_id)))
    except Exception:  # noqa: BLE001 - niet gevonden
        return None


def get_by_token(token: str) -> Reservation | None:
    """Gebruikt door het check-in-formulier: de link bevat alleen het token."""
    rows = list(_table(T_RESERVATIONS).query_entities(f"token eq '{_q(token)}'"))
    return _from_entity(rows[0]) if rows else None


def find_by_phone(phone: str) -> list[Reservation]:
    """Reservaties met dit gsm-nummer (gebruikt door de telefooncentrale)."""
    return [_from_entity(e) for e in _table(T_RESERVATIONS).query_entities(f"phone eq '{_q(phone)}'")]


def mark_checkin_completed(
    reservation_id: str,
    email: str | None,
    phone: str | None,
    language: str | None,
    backup_email: str | None = None,
    backup_phone: str | None = None,
) -> Reservation | None:
    """Gegevens van het check-in-formulier bewaren. Lege reservecontacten wissen een vorige waarde."""
    r = get_reservation(reservation_id)
    if r is None:
        return None
    if email:
        r.guest.email = email
    if phone:
        r.guest.phone = phone
    if language:
        r.guest.language = language
    r.guest.backup_email = backup_email or None
    r.guest.backup_phone = backup_phone or None
    r.checkin_completed_at = _now()
    return save_reservation(r)


# ---------------------------------------------------------------- berichten


def log_message(reservation_id: str, message_type: str, result: SendResult) -> None:
    """Noteer een verstuurd (of mislukt) bericht."""
    sent_at = _now()
    _table(T_MESSAGES).upsert_entity(
        {
            "PartitionKey": _key(reservation_id),
            "RowKey": f"{sent_at.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:8]}",
            "reservation_id": reservation_id,
            "message_type": message_type,
            "channel": result.channel.value,
            "recipient": result.to,
            "ok": result.ok,
            "provider_id": result.provider_id or "",
            "error": (result.error or "")[:1000],
            "sent_at": sent_at.isoformat(),
        }
    )


def messages_for(reservation_id: str) -> list[dict]:
    rows = _table(T_MESSAGES).query_entities(f"PartitionKey eq '{_q(_key(reservation_id))}'")
    return sorted(rows, key=lambda e: e["RowKey"])


def was_sent(reservation_id: str, message_type: str, channel: str | None = None) -> bool:
    """Is dit bericht al met succes verstuurd (eventueel via een bepaald kanaal)?"""
    return any(
        m["message_type"] == message_type and m["ok"] and (channel is None or m["channel"] == channel)
        for m in messages_for(reservation_id)
    )


# ---------------------------------------------------------------- marketing


def add_opt_out(email: str, source: str) -> None:
    """Zet een e-mailadres op de blokkeerlijst. source: bv. 'checkin_form', 'unsubscribe_link', 'mail'."""
    addr = email.strip().lower()
    _table(T_OPTOUT).upsert_entity(
        {"PartitionKey": _PK_OPTOUT, "RowKey": _key(addr), "email": addr, "source": source,
         "created_at": _now().isoformat()}
    )


def is_opted_out(email: str) -> bool:
    try:
        _table(T_OPTOUT).get_entity(_PK_OPTOUT, _key(email.strip().lower()))
        return True
    except Exception:  # noqa: BLE001 - niet gevonden
        return False


# ---------------------------------------------------------------- opslag in het geheugen
# Voor de lokale testserver en tests: zelfde gedrag als Azure Table Storage, zonder Azure.


class MemoryTable:
    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}

    def upsert_entity(self, entity):
        self.rows[(entity["PartitionKey"], entity["RowKey"])] = dict(entity)

    def get_entity(self, pk, rk):
        if (pk, rk) not in self.rows:
            raise KeyError("ResourceNotFound")
        return dict(self.rows[(pk, rk)])

    def query_entities(self, flt):
        import re

        field, value = re.fullmatch(r"(\w+) eq '(.*)'", flt).groups()
        value = value.replace("''", "'")
        return [dict(e) for e in self.rows.values() if str(e.get(field)) == value]


def use_memory_store() -> None:
    """Schakel over naar opslag in het geheugen (gegevens verdwijnen bij het afsluiten)."""
    global _client_factory
    tables: dict[str, MemoryTable] = {}
    _client_factory = lambda name: tables.setdefault(name, MemoryTable())  # noqa: E731
