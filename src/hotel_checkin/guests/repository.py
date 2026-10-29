"""Bouwblok 5: reservaties, verstuurde berichten en marketing-bezwaren opslaan (Azure Table Storage).

Multi-hotel: alle gegevens zitten per hotel in een eigen partitie (PartitionKey begint met de hotel_id).

Drie tabellen:
- Reservations: PartitionKey = hotel_id, RowKey = reservatie-id (gast, data, kamer, token).
- Messages: PartitionKey = <hotel_id>|<reservatie-id>, een rij per verstuurd bericht
  (type, kanaal, ontvanger, tijdstip, resultaat). Daarmee vermijden we dubbele berichten.
- MarketingOptOut: PartitionKey = hotel_id, RowKey = e-mailadres. Blokkeerlijst per hotel
  (elk hotel is zelf verwerkingsverantwoordelijke). Verblijfsmails blijven wel vertrekken.

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

from hotel_checkin.core.models import (
    Guest,
    Reservation,
    ReservationStatus,
    SendResult,
    normalize_language,
)

T_RESERVATIONS = "Reservations"
T_MESSAGES = "Messages"
T_OPTOUT = "MarketingOptOut"
T_ROBOT = "RobotRuns"

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


def _msg_pk(hotel_id: str, reservation_id: str) -> str:
    return f"{_key(hotel_id)}|{_key(reservation_id)}"


# ---------------------------------------------------------------- reservaties


def _to_entity(r: Reservation) -> dict:
    return {
        "PartitionKey": _key(r.hotel_id),
        "RowKey": _key(r.reservation_id),
        "hotel_id": r.hotel_id,
        "reservation_id": r.reservation_id,
        "first_name": r.guest.first_name,
        "last_name": r.guest.last_name,
        "email": (r.guest.email or "").lower(),
        "phone": r.guest.phone or "",
        "language": normalize_language(r.guest.language),
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
        "booking_number": r.booking_number or "",
        "pms_status": r.pms_status or "",
        "guest_count": "" if r.guest_count is None else str(r.guest_count),
        "booked_at": r.booked_at.isoformat() if r.booked_at else "",
        "updated_at": _now().isoformat(),
    }


def _from_entity(e: dict) -> Reservation:
    return Reservation(
        hotel_id=e["hotel_id"],
        reservation_id=e["reservation_id"],
        guest=Guest(
            first_name=e["first_name"],
            last_name=e["last_name"],
            email=e["email"] or None,
            phone=e["phone"] or None,
            language=normalize_language(e["language"]),
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
        booking_number=e.get("booking_number") or None,
        pms_status=e.get("pms_status") or None,
        guest_count=int(e["guest_count"]) if e.get("guest_count") else None,
        booked_at=datetime.fromisoformat(e["booked_at"]) if e.get("booked_at") else None,
    )


def save_reservation(reservation: Reservation) -> Reservation:
    """Bewaar of werk bij. Een nieuwe reservatie krijgt een token; een bestaand token blijft behouden."""
    if not reservation.token:
        existing = get_reservation(reservation.hotel_id, reservation.reservation_id)
        reservation.token = existing.token if existing and existing.token else secrets.token_urlsafe(24)
    entity = _to_entity(reservation)
    table = _table(T_RESERVATIONS)
    try:
        created = table.get_entity(entity["PartitionKey"], entity["RowKey"])["created_at"]
    except Exception:  # noqa: BLE001 - bestaat nog niet
        created = _now().isoformat()
    entity["created_at"] = created
    table.upsert_entity(entity)
    return reservation


def get_reservation(hotel_id: str, reservation_id: str) -> Reservation | None:
    try:
        return _from_entity(_table(T_RESERVATIONS).get_entity(_key(hotel_id), _key(reservation_id)))
    except Exception:  # noqa: BLE001 - niet gevonden
        return None


def get_by_token(token: str) -> Reservation | None:
    """Gebruikt door het check-in-formulier: de link bevat alleen het token (uniek over alle hotels)."""
    rows = list(_table(T_RESERVATIONS).query_entities(f"token eq '{_q(token)}'"))
    return _from_entity(rows[0]) if rows else None


def find_by_phone(hotel_id: str, phone: str) -> list[Reservation]:
    """Reservaties van dit hotel met dit gsm-nummer (gebruikt door de telefooncentrale)."""
    flt = f"PartitionKey eq '{_q(_key(hotel_id))}' and phone eq '{_q(phone)}'"
    return [_from_entity(e) for e in _table(T_RESERVATIONS).query_entities(flt)]


def mark_checkin_completed(
    hotel_id: str,
    reservation_id: str,
    email: str | None,
    phone: str | None,
    language: str | None,
    backup_email: str | None = None,
    backup_phone: str | None = None,
) -> Reservation | None:
    """Gegevens van het check-in-formulier bewaren. Lege reservecontacten wissen een vorige waarde."""
    r = get_reservation(hotel_id, reservation_id)
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


def log_message(hotel_id: str, reservation_id: str, message_type: str, result: SendResult) -> None:
    """Noteer een verstuurd (of mislukt) bericht."""
    sent_at = _now()
    _table(T_MESSAGES).upsert_entity(
        {
            "PartitionKey": _msg_pk(hotel_id, reservation_id),
            "RowKey": f"{sent_at.strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:8]}",
            "hotel_id": hotel_id,
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


def messages_for(hotel_id: str, reservation_id: str) -> list[dict]:
    rows = _table(T_MESSAGES).query_entities(f"PartitionKey eq '{_q(_msg_pk(hotel_id, reservation_id))}'")
    return sorted(rows, key=lambda e: e["RowKey"])


def was_sent(hotel_id: str, reservation_id: str, message_type: str, channel: str | None = None) -> bool:
    """Is dit bericht al met succes verstuurd (eventueel via een bepaald kanaal)?"""
    return any(
        m["message_type"] == message_type and m["ok"] and (channel is None or m["channel"] == channel)
        for m in messages_for(hotel_id, reservation_id)
    )


def list_reservations(hotel_id: str) -> list[Reservation]:
    """Alle reservaties van een hotel, gesorteerd op aankomst (voor de opvolgpagina)."""
    rows = _table(T_RESERVATIONS).query_entities(f"PartitionKey eq '{_q(_key(hotel_id))}'")
    return sorted((_from_entity(e) for e in rows), key=lambda r: (r.arrival, r.reservation_id))


# ---------------------------------------------------------------- robot


def log_robot_run(
    hotel_id: str, task: str, started: datetime, ok: bool,
    found: int = 0, new: int = 0, error: str | None = None,
) -> None:
    """Noteer een run van de robot (bv. task="nieuwe_reservaties")."""
    finished = _now()
    _table(T_ROBOT).upsert_entity({
        "PartitionKey": _key(hotel_id),
        # Omgekeerde tijd als sleutel: nieuwste run eerst
        "RowKey": f"{9999999999 - int(started.timestamp()):010d}-{uuid.uuid4().hex[:6]}",
        "hotel_id": hotel_id,
        "task": task,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "ok": ok,
        "found": found,
        "new": new,
        "error": (error or "")[:2000],
    })


def robot_runs(hotel_id: str, limit: int = 50) -> list[dict]:
    rows = _table(T_ROBOT).query_entities(f"PartitionKey eq '{_q(_key(hotel_id))}'")
    return sorted(rows, key=lambda e: e["RowKey"])[:limit]


# ---------------------------------------------------------------- marketing


def add_opt_out(hotel_id: str, email: str, source: str) -> None:
    """Zet een e-mailadres op de blokkeerlijst. source: bv. 'checkin_form', 'unsubscribe_link', 'mail'."""
    addr = email.strip().lower()
    _table(T_OPTOUT).upsert_entity(
        {"PartitionKey": _key(hotel_id), "RowKey": _key(addr), "hotel_id": hotel_id, "email": addr, "source": source,
         "created_at": _now().isoformat()}
    )


def is_opted_out(hotel_id: str, email: str) -> bool:
    try:
        _table(T_OPTOUT).get_entity(_key(hotel_id), _key(email.strip().lower()))
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
        """Ondersteunt filters van de vorm: veld eq 'waarde' [and veld eq 'waarde' ...]."""
        import re

        conds = [
            (f, v.replace("''", "'"))
            for f, v in re.findall(r"(\w+) eq '((?:[^']|'')*)'", flt)
        ]
        return [dict(e) for e in self.rows.values() if all(str(e.get(f)) == v for f, v in conds)]


def use_memory_store() -> None:
    """Schakel over naar opslag in het geheugen (gegevens verdwijnen bij het afsluiten)."""
    global _client_factory
    tables: dict[str, MemoryTable] = {}
    _client_factory = lambda name: tables.setdefault(name, MemoryTable())  # noqa: E731
