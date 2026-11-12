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
import re
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import ClassVar
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
T_CONFIG = "HotelConfig"  # instellingen die in de monitor gewijzigd werden (bv. de workflow)
T_STATE = "RobotState"  # kleine toestand per hotel, bv. tot waar de mailbox gelezen is
T_FORMS = "CheckinForms"  # elke indiening van het check-in-formulier, nooit overschreven (vangnet)
T_LISTS = "DailyLists"  # ontbijtlijst en kuislijst per dag (alleen de laatste 15 per soort)
T_EVIDENCE = "PmsEvidence"  # zelftest Lighthouse: de pagina's die niet meer klopten (bewijs om te herstellen)

_client_factory = None  # alleen voor tests: functie die een tabelnaam krijgt en een tabel teruggeeft


def _now() -> datetime:
    return datetime.now(UTC)


@lru_cache
def _service():
    from azure.data.tables import TableServiceClient

    conn = os.environ.get("STORAGE_CONNECTION_STRING")
    if conn:
        return TableServiceClient.from_connection_string(conn)
    from hotel_checkin.core.clients import azure_credential
    from hotel_checkin.core.config import get_setting

    return TableServiceClient(endpoint=get_setting("STORAGE_TABLE_ENDPOINT"), credential=azure_credential())


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
        "relay_email": (r.guest.relay_email or "").lower(),
        "backup_phone": r.guest.backup_phone or "",
        "channels": json.dumps(r.guest.channels) if r.guest.channels is not None else "",
        "phone_consent": json.dumps(r.guest.phone_consent) if r.guest.phone_consent is not None else "",
        "arrival": r.arrival.isoformat(),
        "departure": r.departure.isoformat(),
        "rooms": json.dumps(r.rooms),
        "room_names": json.dumps(r.room_names) if r.room_names else "",
        "room_type": r.room_type or "",
        "rate_plan": r.rate_plan or "",
        "non_refundable": "" if r.non_refundable is None else str(r.non_refundable),
        "remarks": (r.remarks or "")[:4000],
        "internal_memo": (r.internal_memo or "")[:4000],
        "transactions": json.dumps(r.transactions),
        "payout_registered_at": r.payout_registered_at.isoformat() if r.payout_registered_at else "",
        "breakfast_labeled_at": r.breakfast_labeled_at.isoformat() if r.breakfast_labeled_at else "",
        "pms_labels": json.dumps(r.pms_labels) if r.pms_labels else "",
        "pay_requested_at": r.pay_requested_at.isoformat() if r.pay_requested_at else "",
        "pay_link": r.pay_link or "",
        "room_statuses": json.dumps(r.room_statuses),
        "pms_codes_line": r.pms_codes_line or "",
        "status": r.status.value,
        "source": r.source or "",
        "paid": "" if r.paid is None else str(r.paid),
        "open_amount": "" if r.open_amount is None else str(r.open_amount),
        "folio": json.dumps(r.folio),
        "folio_total": "" if r.folio_total is None else str(r.folio_total),
        "token": r.token or "",
        "checkin_completed_at": r.checkin_completed_at.isoformat() if r.checkin_completed_at else "",
        "booking_number": r.booking_number or "",
        "pms_status": r.pms_status or "",
        "guest_count": "" if r.guest_count is None else str(r.guest_count),
        "booked_at": r.booked_at.isoformat() if r.booked_at else "",
        "contact_checked_at": r.contact_checked_at.isoformat() if r.contact_checked_at else "",
        "guest_id": r.guest_id or "",
        "access_codes": json.dumps(r.access_codes),
        "room_moves": json.dumps(r.room_moves),
        "access_valid_from": r.access_valid_from.isoformat() if r.access_valid_from else "",
        "access_valid_until": r.access_valid_until.isoformat() if r.access_valid_until else "",
        # vroegere velden (één code voor alle kamers): leeg, zodat _codes_from ze niet meer gebruikt
        "access_pin": "", "salto_user_id": "", "salto_group_id": "", "salto_schedule_id": "", "access_rooms": "",
        "stay_counted_at": r.stay_counted_at.isoformat() if r.stay_counted_at else "",
        "cancel_counted_at": r.cancel_counted_at.isoformat() if r.cancel_counted_at else "",
        "stairs_help": "" if r.stairs_help is None else ("1" if r.stairs_help else "0"),
        "stairs_memo_at": r.stairs_memo_at.isoformat() if r.stairs_memo_at else "",
        "stairs_label_at": r.stairs_label_at.isoformat() if r.stairs_label_at else "",
        "updated_at": _now().isoformat(),
    }


def _codes_from(e: dict) -> list[dict]:
    """Pincodes per kamer. Vroeger (tot 02/11/2026) één code voor alle kamers in aparte velden:
    die wordt één regel met alle kamers, zodat ze nog opgeruimd en gevolgd kan worden."""
    if e.get("access_codes"):
        return json.loads(e["access_codes"])
    if e.get("access_pin") or e.get("salto_user_id") or e.get("salto_group_id"):
        rooms = json.loads(e["access_rooms"]) if e.get("access_rooms") else []
        return [{"room": ", ".join(rooms), "pin": e.get("access_pin") or "", "user_id": e.get("salto_user_id") or None,
                 "group_id": e.get("salto_group_id") or None, "schedule_id": e.get("salto_schedule_id") or None}]
    return []


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
            relay_email=e.get("relay_email") or None,
            backup_phone=e.get("backup_phone") or None,
            channels=json.loads(e["channels"]) if e.get("channels") else None,
            phone_consent=json.loads(e["phone_consent"]) if e.get("phone_consent") else None,
        ),
        arrival=date.fromisoformat(e["arrival"]),
        departure=date.fromisoformat(e["departure"]),
        rooms=json.loads(e["rooms"]),
        room_names=json.loads(e["room_names"]) if e.get("room_names") else {},
        status=ReservationStatus(e["status"]),
        source=e["source"] or None,
        paid=None if e["paid"] == "" else e["paid"] == "True",
        room_type=e["room_type"] or None,
        rate_plan=e.get("rate_plan") or None,
        non_refundable=None if e.get("non_refundable") in (None, "") else e["non_refundable"] == "True",
        remarks=e.get("remarks") or None,
        internal_memo=e.get("internal_memo") or None,
        transactions=json.loads(e["transactions"]) if e.get("transactions") else [],
        payout_registered_at=datetime.fromisoformat(e["payout_registered_at"]) if e.get("payout_registered_at") else None,
        breakfast_labeled_at=datetime.fromisoformat(e["breakfast_labeled_at"]) if e.get("breakfast_labeled_at") else None,
        pms_labels=json.loads(e["pms_labels"]) if e.get("pms_labels") else [],
        pay_requested_at=datetime.fromisoformat(e["pay_requested_at"]) if e.get("pay_requested_at") else None,
        pay_link=e.get("pay_link") or None,
        room_statuses=json.loads(e["room_statuses"]) if e.get("room_statuses") else [],
        pms_codes_line=e.get("pms_codes_line") or None,
        token=e["token"] or None,
        checkin_completed_at=(
            datetime.fromisoformat(e["checkin_completed_at"]) if e["checkin_completed_at"] else None
        ),
        booking_number=e.get("booking_number") or None,
        pms_status=e.get("pms_status") or None,
        guest_count=int(e["guest_count"]) if e.get("guest_count") else None,
        booked_at=datetime.fromisoformat(e["booked_at"]) if e.get("booked_at") else None,
        contact_checked_at=datetime.fromisoformat(e["contact_checked_at"]) if e.get("contact_checked_at") else None,
        guest_id=e.get("guest_id") or None,
        access_codes=_codes_from(e),
        room_moves=json.loads(e["room_moves"]) if e.get("room_moves") else [],
        access_valid_from=datetime.fromisoformat(e["access_valid_from"]) if e.get("access_valid_from") else None,
        access_valid_until=datetime.fromisoformat(e["access_valid_until"]) if e.get("access_valid_until") else None,
        open_amount=float(e["open_amount"]) if e.get("open_amount") not in (None, "") else None,
        folio=json.loads(e["folio"]) if e.get("folio") else [],
        folio_total=float(e["folio_total"]) if e.get("folio_total") not in (None, "") else None,
        stay_counted_at=datetime.fromisoformat(e["stay_counted_at"]) if e.get("stay_counted_at") else None,
        cancel_counted_at=datetime.fromisoformat(e["cancel_counted_at"]) if e.get("cancel_counted_at") else None,
        stairs_help=None if e.get("stairs_help") in (None, "") else e["stairs_help"] == "1",
        stairs_memo_at=datetime.fromisoformat(e["stairs_memo_at"]) if e.get("stairs_memo_at") else None,
        stairs_label_at=datetime.fromisoformat(e["stairs_label_at"]) if e.get("stairs_label_at") else None,
        created_at=datetime.fromisoformat(e["created_at"]) if e.get("created_at") else None,
        updated_at=datetime.fromisoformat(e["updated_at"]) if e.get("updated_at") else None,
    )


# Velden die niet meetellen voor "bijgewerkt": tijdstempels en technische velden van de tabel
_NOT_DATA = {"created_at", "updated_at", "contact_checked_at", "stay_counted_at", "cancel_counted_at", "stairs_memo_at", "stairs_label_at", "Timestamp", "etag", "odata.etag", "odata.metadata"}

# Wie welke velden van een reservatie schrijft. Een proces dat maar een deel bezit, geeft dat deel mee
# aan save_reservation(fields=...): de andere velden blijven zoals ze nu in de tabel staan. Zo wist de
# robot (lijst uit Lighthouse) nooit de pincode van Salto of de koppeling met het gastprofiel.
LIST_FIELDS = ("first_name", "last_name", "arrival", "departure", "rooms", "room_names", "room_type", "status", "source", "paid",
               "booking_number", "pms_status", "guest_count", "booked_at", "rate_plan", "non_refundable")
CONTACT_FIELDS = ("email", "phone", "language", "country", "backup_email", "backup_phone", "relay_email",
                  "contact_checked_at")
DETAIL_FIELDS = ("rooms", "room_names", "arrival", "departure", "paid", "open_amount", "folio", "folio_total", "status",
                 "pms_status", "email", "phone", "rate_plan", "non_refundable", "remarks", "transactions",
                 "room_statuses", "internal_memo")
PAYOUT_FIELDS = ("payout_registered_at",)
BREAKFAST_FIELDS = ("breakfast_labeled_at",)
PMS_LABEL_FIELDS = ("pms_labels",)
PAY_REQUEST_FIELDS = ("pay_requested_at",)
PAY_LINK_FIELDS = ("pay_link",)
PMS_SYNC_FIELDS = ("pms_codes_line", "room_statuses")
FORM_FIELDS = ("email", "phone", "language", "backup_email", "backup_phone", "relay_email", "channels", "phone_consent",
               "checkin_completed_at", "stairs_help")
STAIRS_MEMO_FIELDS = ("stairs_memo_at", "stairs_label_at", "internal_memo")
SALTO_FIELDS = ("access_codes", "room_moves", "access_valid_from", "access_valid_until", "access_pin", "salto_user_id",
                "salto_group_id", "salto_schedule_id", "access_rooms")
PROFILE_FIELDS = ("guest_id", "stay_counted_at", "cancel_counted_at")
_KEYS = {"PartitionKey", "RowKey", "hotel_id", "reservation_id", "created_at", "updated_at"}
T_TOKENS = "TokenIndex"  # token van de formulierlink -> hotel en reservatie (geen tabelscan per aanvraag)
_MAX_TRIES = 5


def _etag(entity) -> str | None:
    meta = getattr(entity, "metadata", None) or {}
    return meta.get("etag")


def save_reservation(reservation: Reservation, fields: tuple[str, ...] | list[str] | None = None) -> Reservation:
    """Bewaar of werk bij. Een nieuwe reservatie krijgt een token; een bestaand token blijft behouden.

    fields: alleen deze velden (namen zoals in de tabel, zie LIST_FIELDS, SALTO_FIELDS, ...) schrijven;
    de rest blijft zoals het nu bewaard is. None = alles (nieuwe reservatie, of het proces bezit alles).
    Optimistische concurrentie (ETag): veranderde de rij tussen lezen en schrijven, dan opnieuw lezen en
    samenvoegen.
    """
    table = _table(T_RESERVATIONS)
    pk, rk = _key(reservation.hotel_id), _key(reservation.reservation_id)
    from azure.core import MatchConditions
    from azure.core.exceptions import ResourceExistsError, ResourceModifiedError
    from azure.data.tables import UpdateMode

    for attempt in range(_MAX_TRIES):
        try:
            stored = table.get_entity(pk, rk)
        except Exception:  # noqa: BLE001 - bestaat nog niet
            stored = None
        old = dict(stored) if stored is not None else None
        new_token = False
        if old and old.get("token"):
            reservation.token = old["token"]  # een bestaand token verandert nooit
        elif not reservation.token:
            reservation.token, new_token = secrets.token_urlsafe(24), True
        else:
            new_token = True
        _keep_form(reservation, old)
        entity = _to_entity(reservation)
        if old is not None and fields is not None:
            own = set(fields)
            for k in entity:
                if k not in own and k not in _KEYS and k in old:
                    entity[k] = old[k]
        entity["created_at"] = old["created_at"] if old and old.get("created_at") else entity["updated_at"]
        # updated_at alleen verzetten als er echt iets veranderde (de robot bewaart ook ongewijzigde rijen)
        if old and old.get("updated_at") and all(
            str(old.get(k, "")) == str(v) for k, v in entity.items() if k not in _NOT_DATA
        ):
            entity["updated_at"] = old["updated_at"]
        try:
            if stored is None:
                table.create_entity(entity)
            else:
                table.update_entity(entity, mode=UpdateMode.REPLACE, etag=_etag(stored),
                                    match_condition=MatchConditions.IfNotModified)
            break
        except (ResourceExistsError, ResourceModifiedError):
            if attempt == _MAX_TRIES - 1:
                raise
    if new_token:
        _index_token(reservation.hotel_id, reservation.reservation_id, entity["token"])
    reservation.created_at = datetime.fromisoformat(entity["created_at"])
    reservation.updated_at = datetime.fromisoformat(entity["updated_at"])
    return reservation


def _index_token(hotel_id: str, reservation_id: str, token: str) -> None:
    if token:
        _table(T_TOKENS).upsert_entity({"PartitionKey": _key(token), "RowKey": "", "hotel_id": hotel_id,
                                        "reservation_id": reservation_id})


def save_form_submission(hotel_id: str, reservation_id: str, values: dict) -> str:
    """Elke indiening van het formulier apart bewaren, vóór de reservatie bijgewerkt wordt.
    Zo gaat wat de gast invulde nooit verloren, ook niet als het bijwerken mislukt."""
    row = new_message_id()
    _table(T_FORMS).upsert_entity({"PartitionKey": _msg_pk(hotel_id, reservation_id), "RowKey": row,
                                   "hotel_id": hotel_id, "reservation_id": reservation_id,
                                   "submitted_at": _now().isoformat(), "values": json.dumps(values)})
    return row


def _prefix_filter(hotel_id: str) -> str:
    """Alle partities van één hotel in een tabel met PartitionKey <hotel>|<reservatie> (bereik, geen scan)."""
    start = f"{_key(hotel_id)}|"
    return f"PartitionKey ge '{_q(start)}' and PartitionKey lt '{_q(start[:-1] + chr(ord('|') + 1))}'"


def form_submissions(hotel_id: str, reservation_id: str) -> list[dict]:
    """Alle indieningen van het formulier voor deze reservatie, oudste eerst."""
    pk = _msg_pk(hotel_id, reservation_id)
    rows = list(_table(T_FORMS).query_entities(f"PartitionKey eq '{_q(pk)}'"))
    rows.sort(key=lambda e: e["RowKey"])
    return [{"submitted_at": e["submitted_at"], **json.loads(e["values"])} for e in rows]


def all_form_submissions(hotel_id: str) -> list[dict]:
    """Laatste indiening per reservatie van dit hotel (om na te kijken of alles verwerkt is)."""
    latest: dict[str, dict] = {}
    for e in _table(T_FORMS).query_entities(_prefix_filter(hotel_id)):
        if e["reservation_id"] not in latest or e["RowKey"] > latest[e["reservation_id"]]["_row"]:
            latest[e["reservation_id"]] = {"_row": e["RowKey"], "reservation_id": e["reservation_id"],
                                           "submitted_at": e["submitted_at"], **json.loads(e["values"])}
    return list(latest.values())


_FORM_FIELDS = ("email", "phone", "backup_email", "backup_phone", "relay_email", "language", "phone_consent")


def _keep_form(reservation: Reservation, old: dict | None) -> None:
    """Wat de gast in het check-in-formulier invulde, gaat altijd voor. Een proces dat de reservatie
    las vóór de gast het formulier indiende (bv. de robot, die minuten bezig is) mag het niet
    overschrijven met oudere gegevens."""
    if not old or not old.get("checkin_completed_at"):
        return
    stored = datetime.fromisoformat(old["checkin_completed_at"])
    if reservation.checkin_completed_at and reservation.checkin_completed_at >= stored:
        return  # dit is de nieuwste formulierversie (bv. net ingediend)
    fresh = _from_entity(old)
    reservation.checkin_completed_at = fresh.checkin_completed_at
    for field in _FORM_FIELDS:
        setattr(reservation.guest, field, getattr(fresh.guest, field))
    reservation.stairs_help = fresh.stairs_help


def delete_form_submissions(hotel_id: str, reservation_id: str) -> int:
    """Indieningen van het formulier voor deze reservatie verwijderen (bewaartermijn)."""
    table = _table(T_FORMS)
    rows = list(table.query_entities(f"PartitionKey eq '{_q(_msg_pk(hotel_id, reservation_id))}'"))
    for e in rows:
        table.delete_entity(e["PartitionKey"], e["RowKey"])
    return len(rows)


def delete_reservation(hotel_id: str, reservation_id: str) -> None:
    """Reservatie, haar berichtenlog, de formulierindieningen en het token verwijderen (opruimen na het verblijf)."""
    r = get_reservation(hotel_id, reservation_id)
    for m in messages_for(hotel_id, reservation_id):
        _table(T_MESSAGES).delete_entity(m["PartitionKey"], m["RowKey"])
    delete_form_submissions(hotel_id, reservation_id)
    if r is not None and r.token:
        _table(T_TOKENS).delete_entity(_key(r.token), "")
    _table(T_RESERVATIONS).delete_entity(_key(hotel_id), _key(reservation_id))


def get_reservation(hotel_id: str, reservation_id: str) -> Reservation | None:
    try:
        return _from_entity(_table(T_RESERVATIONS).get_entity(_key(hotel_id), _key(reservation_id)))
    except Exception:  # noqa: BLE001 - niet gevonden
        return None


TOKEN_INDEX_READY = "token_index_ready"  # RobotState (hotel "_all"): alle bestaande tokens staan in de index


def get_by_token(token: str) -> Reservation | None:
    """Gebruikt door het check-in-formulier: de link bevat alleen het token (uniek over alle hotels).
    Via de tabel TokenIndex (één puntlezing). Zolang de index nog niet volledig is (net na de uitrol),
    valt het terug op zoeken in Reservations en vult het de index aan."""
    if not token:
        return None
    try:
        e = _table(T_TOKENS).get_entity(_key(token), "")
        r = get_reservation(e["hotel_id"], e["reservation_id"])
        return r if r is not None and r.token == token else None
    except Exception:  # noqa: BLE001 - niet in de index
        pass
    if get_state("_all", TOKEN_INDEX_READY):
        return None
    rows = list(_table(T_RESERVATIONS).query_entities(f"token eq '{_q(token)}'"))
    if not rows:
        return None
    r = _from_entity(rows[0])
    _index_token(r.hotel_id, r.reservation_id, token)
    return r


def build_token_index() -> int:
    """Eenmalig (onderhoud): alle bestaande tokens in de index zetten. Geeft het aantal terug."""
    if get_state("_all", TOKEN_INDEX_READY):
        return 0
    n = 0
    for e in _table(T_RESERVATIONS).query_entities("token ne ''"):
        if e.get("token"):
            _index_token(e["hotel_id"], e["reservation_id"], e["token"])
            n += 1
    set_state("_all", TOKEN_INDEX_READY, "1")
    return n


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
    channels: list[str] | None = None,
    stairs_help: bool | None = None,
) -> Reservation | None:
    """Gegevens van het check-in-formulier bewaren. Lege reservecontacten wissen een vorige waarde."""
    r = get_reservation(hotel_id, reservation_id)
    if r is None:
        return None
    if email:
        from hotel_checkin.core.addresses import is_own_email

        # Doorstuuradres van het boekingsplatform bewaren als reserve, het eigen adres gaat voor
        if r.guest.email and not is_own_email(r.guest.email) and r.guest.email.lower() != email.lower():
            r.guest.relay_email = r.guest.email
        r.guest.email = email
    if phone:
        r.guest.phone = phone
    if language:
        r.guest.language = language
    r.guest.backup_email = backup_email or None
    r.guest.backup_phone = backup_phone or None
    # Toestemming voor WhatsApp en sms: de nummers die de gast nu zelf invulde (een leeg veld = geen toestemming)
    r.guest.phone_consent = [p for p in (phone, backup_phone) if p]
    if channels is not None:
        r.guest.channels = channels
    if stairs_help is not None:  # alleen als de vraag op het formulier stond
        r.stairs_help = stairs_help
    r.checkin_completed_at = _now()
    return save_reservation(r, fields=FORM_FIELDS)


# ---------------------------------------------------------------- berichten


def new_message_id() -> str:
    """Sleutel van een bericht in het logboek (ook vooraf nodig voor de statusmelding van Twilio)."""
    return f"{_now().strftime('%Y%m%dT%H%M%S%f')}-{uuid.uuid4().hex[:8]}"


def log_message(hotel_id: str, reservation_id: str, message_type: str, result: SendResult,
                message_id: str | None = None, note: str = "", room: str = "") -> str:
    """Noteer een verstuurd (of mislukt) bericht. Geeft de sleutel terug.
    status: sent of failed; later bijgewerkt door Twilio (delivered, undelivered, ...)."""
    sent_at = _now()
    row = message_id or new_message_id()
    _table(T_MESSAGES).upsert_entity(
        {
            "PartitionKey": _msg_pk(hotel_id, reservation_id),
            "RowKey": row,
            "hotel_id": hotel_id,
            "reservation_id": reservation_id,
            "message_type": message_type,
            "channel": result.channel.value,
            "recipient": result.to,
            "delivered_to": result.delivered_to or "",
            "ok": result.ok,
            "provider_id": result.provider_id or "",
            "error": (result.error or "")[:1000],
            "sent_at": sent_at.isoformat(),
            "status": "sent" if result.ok else "failed",
            "note": note,
            "room": room,  # code per kamer: één sms of WhatsApp per kamer
        }
    )
    return row


def update_message_status(hotel_id: str, reservation_id: str, message_id: str, status: str,
                          error: str = "") -> dict | None:
    """Status van Twilio (delivered, read, undelivered, failed). Mislukt = ok wordt False."""
    table = _table(T_MESSAGES)
    try:
        e = dict(table.get_entity(_msg_pk(hotel_id, reservation_id), message_id))
    except Exception:  # noqa: BLE001 - onbekend bericht
        return None
    e["status"] = status
    if status in ("undelivered", "failed"):
        e["ok"] = False
        e["error"] = (error or e.get("error") or status)[:1000]
    e["status_at"] = _now().isoformat()
    table.upsert_entity(e)
    return e


def messages_for_hotel(hotel_id: str) -> dict[str, list[dict]]:
    """Alle berichten van een hotel in één query, per reservatie (oudste eerst). Voor de monitor."""
    out: dict[str, list[dict]] = {}
    for e in _table(T_MESSAGES).query_entities(_prefix_filter(hotel_id)):
        out.setdefault(e["reservation_id"], []).append(e)
    for rows in out.values():
        rows.sort(key=lambda e: e["RowKey"])
    return out


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


def _run_fields() -> dict:
    from hotel_checkin.core import run_context

    return run_context.fields()


def log_robot_run(
    hotel_id: str, task: str, started: datetime, ok: bool,
    found: int = 0, new: int = 0, error: str | None = None,
    since: datetime | None = None, skipped: int = 0, timings: dict | None = None,
) -> None:
    """Noteer een run van de robot (bv. task="nieuwe_reservaties").

    since: vanaf welke boekdatum gelezen werd; skipped: aantal overgeslagen rijen. Een run met
    overgeslagen rijen of een fout wordt bij de volgende run opnieuw gelezen vanaf dezelfde `since`.
    """
    finished = _now()
    _table(T_ROBOT).upsert_entity({
        "PartitionKey": _key(hotel_id),
        # Omgekeerde tijd als sleutel: nieuwste run eerst
        "RowKey": f"{_run_key(started)}-{uuid.uuid4().hex[:6]}",
        "hotel_id": hotel_id,
        "task": task,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "ok": ok,
        "found": found,
        "new": new,
        "error": (error or "")[:2000],
        "since": since.isoformat() if since else "",
        "skipped": skipped,
        # gemeten duur per onderdeel in seconden, bv. {"login": 25, "list": 6, "contact": 9}
        "timings": json.dumps(timings or {}),
        # robot: wanneer de container begon en welke run van Azure (core/run_context.py)
        **_run_fields(),
    })


def get_config_doc(hotel_id: str, name: str) -> dict | None:
    """Een in de monitor gewijzigd configuratiedocument (JSON) met wie en wanneer, of None."""
    try:
        e = _table(T_CONFIG).get_entity(_key(hotel_id), _key(name))
    except Exception:  # noqa: BLE001 - niet gewijzigd: standaard uit het hotelbestand
        return None
    return {"value": json.loads(e["value"]), "updated_by": e.get("updated_by", ""), "updated_at": e.get("updated_at", "")}


def set_config_doc(hotel_id: str, name: str, value: dict, user: str) -> None:
    _table(T_CONFIG).upsert_entity({"PartitionKey": _key(hotel_id), "RowKey": _key(name), "value": json.dumps(value),
                                    "updated_by": user or "", "updated_at": _now().isoformat()})


def delete_config_doc(hotel_id: str, name: str) -> None:
    try:
        _table(T_CONFIG).delete_entity(_key(hotel_id), _key(name))
    except Exception:  # noqa: BLE001 - stond er niet
        pass


def get_state(hotel_id: str, key: str) -> str | None:
    try:
        return _table(T_STATE).get_entity(_key(hotel_id), _key(key)).get("value") or None
    except Exception:  # noqa: BLE001 - nog niet gezet
        return None


def set_state(hotel_id: str, key: str, value: str) -> None:
    _table(T_STATE).upsert_entity({"PartitionKey": _key(hotel_id), "RowKey": _key(key), "value": value,
                                   "updated_at": _now().isoformat()})


def delete_state(hotel_id: str, key: str) -> None:
    try:
        _table(T_STATE).delete_entity(_key(hotel_id), _key(key))
    except Exception:  # noqa: BLE001 - stond er niet
        pass


def delete_robot_run(hotel_id: str, run_id: str) -> bool:
    """Verwijder één run uit het logboek (monitor, vuilbakje). run_id = RowKey."""
    if not re.fullmatch(r"\d{10}-[0-9a-f]{6}", run_id or ""):
        return False
    _table(T_ROBOT).delete_entity(_key(hotel_id), run_id)
    return True


def _runs_filter(hotel_id: str, task: str | None = None) -> str:
    flt = f"PartitionKey eq '{_q(_key(hotel_id))}'"
    return flt + (f" and task eq '{_q(task)}'" if task else "")


def _run_key(moment: datetime) -> str:
    return f"{9999999999 - int(moment.timestamp()):010d}"


def delete_robot_runs(hotel_id: str, task: str | None = None) -> int:
    """Verwijder alle runs van een hotel uit het logboek, of alleen die van één taak. Geeft het aantal terug."""
    table = _table(T_ROBOT)
    rows = list(table.query_entities(_runs_filter(hotel_id, task)))
    for e in rows:
        table.delete_entity(e["PartitionKey"], e["RowKey"])
    return len(rows)


def prune_robot_runs(hotel_id: str, keep_days: int = 30) -> int:
    """Verwijder robotruns ouder dan keep_days. Geeft het aantal verwijderde runs terug."""
    # RowKey = omgekeerde starttijd: oudere runs hebben een grotere sleutel (bereik, geen scan)
    cutoff = _run_key(_now() - timedelta(days=keep_days))
    table = _table(T_ROBOT)
    old = list(table.query_entities(f"{_runs_filter(hotel_id)} and RowKey gt '{cutoff}'"))
    for e in old:
        table.delete_entity(e["PartitionKey"], e["RowKey"])
    return len(old)


def robot_runs(hotel_id: str, limit: int = 50, task: str | None = None) -> list[dict]:
    """Nieuwste runs eerst (de tabel geeft ze al in die volgorde: RowKey = omgekeerde tijd).
    Alleen de eerste `limit` worden gelezen; task filtert op de server."""
    from itertools import islice

    rows = _table(T_ROBOT).query_entities(_runs_filter(hotel_id, task), results_per_page=min(limit, 1000))
    return list(islice(rows, limit))


# ---------------------------------------------------------------- dagelijkse lijsten (ontbijt, kuis)
# Tabel DailyLists: PartitionKey = <hotel_id>|<soort> (breakfast, cleaning), RowKey = dag (ISO), veld data (JSON).
# Alleen kamers, aantallen en opmerkingen, geen gastnamen. Alleen de laatste lijsten blijven (processes/daily_lists.py).


def _list_pk(hotel_id: str, kind: str) -> str:
    return f"{_key(hotel_id)}|{_key(kind)}"


def save_daily_list(hotel_id: str, kind: str, day: str, data: dict) -> None:
    _table(T_LISTS).upsert_entity({"PartitionKey": _list_pk(hotel_id, kind), "RowKey": day, "hotel_id": hotel_id,
                                   "kind": kind, "data": json.dumps(data), "updated_at": _now().isoformat()})


def get_daily_list(hotel_id: str, kind: str, day: str) -> dict | None:
    try:
        return json.loads(_table(T_LISTS).get_entity(_list_pk(hotel_id, kind), day)["data"])
    except Exception:  # noqa: BLE001 - nog niet gemaakt
        return None


def daily_lists(hotel_id: str, kind: str) -> list[dict]:
    """Alle bewaarde lijsten van die soort, nieuwste dag eerst."""
    rows = _table(T_LISTS).query_entities(f"PartitionKey eq '{_q(_list_pk(hotel_id, kind))}'")
    out = [json.loads(e["data"]) for e in rows]
    return sorted(out, key=lambda d: d.get("day", ""), reverse=True)


def delete_daily_list(hotel_id: str, kind: str, day: str) -> None:
    try:
        _table(T_LISTS).delete_entity(_list_pk(hotel_id, kind), day)
    except Exception:  # noqa: BLE001 - stond er niet
        pass


# ---------------------------------------------------------------- marketing


def add_opt_out(hotel_id: str, email: str, source: str) -> None:
    """Zet een e-mailadres op de blokkeerlijst. source: bv. 'checkin_form', 'unsubscribe_link', 'mail'."""
    addr = email.strip().lower()
    _table(T_OPTOUT).upsert_entity(
        {"PartitionKey": _key(hotel_id), "RowKey": _key(addr), "hotel_id": hotel_id, "email": addr, "source": source,
         "created_at": _now().isoformat()}
    )


def opted_out_emails(hotel_id: str) -> list[str]:
    rows = _table(T_OPTOUT).query_entities(f"PartitionKey eq '{_q(_key(hotel_id))}'")
    return [e.get("email", "") for e in rows]


def is_opted_out(hotel_id: str, email: str) -> bool:
    try:
        _table(T_OPTOUT).get_entity(_key(hotel_id), _key(email.strip().lower()))
        return True
    except Exception:  # noqa: BLE001 - niet gevonden
        return False


# ---------------------------------------------------------------- opslag in het geheugen
# Voor de lokale testserver en tests: zelfde gedrag als Azure Table Storage, zonder Azure.


class _MemoryEntity(dict):
    """Rij met metadata (ETag), zoals TableEntity van de Azure SDK."""

    def __init__(self, *args, metadata: dict | None = None, **kw):
        super().__init__(*args, **kw)
        self.metadata = metadata or {}


class MemoryTable:
    def __init__(self):
        self.rows: dict[tuple[str, str], dict] = {}
        self.etags: dict[tuple[str, str], str] = {}

    def _stamp(self, key) -> None:
        self.etags[key] = uuid.uuid4().hex

    def upsert_entity(self, entity, **_):
        key = (entity["PartitionKey"], entity["RowKey"])
        self.rows[key] = dict(entity)
        self._stamp(key)

    def create_entity(self, entity, **_):
        from azure.core.exceptions import ResourceExistsError

        if (entity["PartitionKey"], entity["RowKey"]) in self.rows:
            raise ResourceExistsError("EntityAlreadyExists")
        self.upsert_entity(entity)

    def update_entity(self, entity, mode=None, etag=None, match_condition=None, **_):
        from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError

        key = (entity["PartitionKey"], entity["RowKey"])
        if key not in self.rows:
            raise ResourceNotFoundError("ResourceNotFound")
        if etag is not None and self.etags.get(key) != etag:
            raise ResourceModifiedError("UpdateConditionNotSatisfied")
        if str(mode).lower().endswith("merge"):
            self.rows[key].update(entity)
            self._stamp(key)
        else:
            self.upsert_entity(entity)

    def delete_entity(self, pk, rk, **_):
        self.rows.pop((pk, rk), None)
        self.etags.pop((pk, rk), None)

    def get_entity(self, pk, rk, **_):
        from azure.core.exceptions import ResourceNotFoundError

        if (pk, rk) not in self.rows:
            raise ResourceNotFoundError("ResourceNotFound")
        return _MemoryEntity(self.rows[(pk, rk)], metadata={"etag": self.etags.get((pk, rk))})

    _OPS: ClassVar[dict] = {"eq": lambda a, b: a == b, "ne": lambda a, b: a != b, "gt": lambda a, b: a > b,
            "ge": lambda a, b: a >= b, "lt": lambda a, b: a < b, "le": lambda a, b: a <= b}

    def query_entities(self, flt, **_):
        """Ondersteunt filters van de vorm: veld op 'waarde' [and veld op 'waarde' ...] (op: eq ne gt ge lt le).
        Resultaat gesorteerd op PartitionKey en RowKey, zoals Azure Table Storage."""
        conds = [
            (f, op, v.replace("''", "'"))
            for f, op, v in re.findall(r"(\w+) (eq|ne|gt|ge|lt|le) '((?:[^']|'')*)'", flt)
        ]
        hits = [dict(e) for k, e in sorted(self.rows.items())
                if all(self._OPS[op](str(e.get(f, "")), v) for f, op, v in conds)]
        return iter(hits)


_CHUNK = 30_000  # tekens per eigenschap (Table Storage: max. 32 K tekens per tekst)


def save_evidence(hotel_id: str, name: str, meta: dict, content: str, keep: int = 20) -> str:
    """Bewijs van de zelftest bewaren: een pagina van Lighthouse (gecomprimeerd) met wat er niet klopte.
    Alleen de laatste `keep` blijven. Geeft de sleutel terug."""
    import base64
    import gzip

    key = f"{_now():%Y%m%d%H%M%S}-{name}"
    packed = base64.b64encode(gzip.compress(content.encode("utf-8"))).decode("ascii")[: _CHUNK * 30]
    entity = {"PartitionKey": _key(hotel_id), "RowKey": _key(key), "meta": json.dumps(meta), "parts": 0,
              "created_at": _now().isoformat()}
    for i in range(0, len(packed), _CHUNK):
        entity[f"p{i // _CHUNK}"] = packed[i:i + _CHUNK]
        entity["parts"] = i // _CHUNK + 1
    _table(T_EVIDENCE).upsert_entity(entity)
    old = sorted(evidence_list(hotel_id), key=lambda e: e["key"], reverse=True)[keep:]
    for e in old:
        try:
            _table(T_EVIDENCE).delete_entity(_key(hotel_id), _key(e["key"]))
        except Exception:  # noqa: BLE001
            pass
    return key


def evidence_list(hotel_id: str) -> list[dict]:
    rows = _table(T_EVIDENCE).query_entities(f"PartitionKey eq '{_q(_key(hotel_id))}'")
    return sorted(({"key": e["RowKey"], "created_at": e.get("created_at", ""), **json.loads(e.get("meta") or "{}")}
                   for e in rows), key=lambda e: e["key"], reverse=True)


def get_evidence(hotel_id: str, key: str) -> str | None:
    import base64
    import gzip

    try:
        e = _table(T_EVIDENCE).get_entity(_key(hotel_id), _key(key))
    except Exception:  # noqa: BLE001
        return None
    packed = "".join(e.get(f"p{i}", "") for i in range(int(e.get("parts") or 0)))
    return gzip.decompress(base64.b64decode(packed)).decode("utf-8") if packed else ""


def use_memory_store() -> None:
    """Schakel over naar opslag in het geheugen (gegevens verdwijnen bij het afsluiten)."""
    global _client_factory
    tables: dict[str, MemoryTable] = {}
    _client_factory = lambda name: tables.setdefault(name, MemoryTable())
