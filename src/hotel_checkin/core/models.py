"""Gedeelde types die tussen de bouwblokken doorgegeven worden."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class ReservationStatus(str, Enum):
    READY_FOR_CHECKIN = "ready_for_checkin"  # KLAAR OM IN TE CHECKEN
    CHECKED_IN = "checked_in"  # INGECHECKT
    CHECKED_OUT = "checked_out"  # UITGECHECKT
    CANCELLED = "cancelled"


def normalize_language(code: str | None) -> str:
    """Taal voor berichten en formulier: nl, fr of de als die meegegeven is, anders altijd en.

    Varianten zoals "nl-BE", "FR" of "de_DE" worden herkend.
    """
    base = (code or "").strip().lower().replace("_", "-").split("-")[0]
    return base if base in ("nl", "fr", "de") else "en"


class Channel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    SALTO = "salto"  # pincode maken (logboek van de code-mail)
    FORM = "form"  # de gast vulde het check-in-formulier in (logboek)
    PMS = "lighthouse"  # iets in Lighthouse geschreven (logboek), bv. de overschrijving van Booking.com


@dataclass
class Guest:
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None  # E.164, bv. +32470123456
    language: str = "nl"  # nl, fr, en, de
    country: str | None = None  # land van de gast (woonland, uit de reservatiegegevens), ISO-code: BE, FR, DE
    backup_email: str | None = None
    backup_phone: str | None = None  # E.164
    relay_email: str | None = None  # doorstuuradres van Booking.com, Expedia, ... (bewaard als de gast een eigen adres gaf)
    channels: list[str] | None = None  # gekozen in het check-in-formulier: email (altijd), sms, whatsapp; None = nog niet gekozen


@dataclass
class Reservation:
    hotel_id: str  # welk hotel (bestand config/hotels/<hotel_id>.toml), bv. "lucca"
    reservation_id: str  # Lighthouse-id (uuid uit /Customer/Reservations/Detail/{uuid})
    guest: Guest
    arrival: date
    departure: date
    rooms: list[str] = field(default_factory=list)
    room_names: dict[str, str] = field(default_factory=dict)  # kamer -> omschrijving in Lighthouse, bv. "SUPERIOR DOUBLE ROOM"
    status: ReservationStatus = ReservationStatus.READY_FOR_CHECKIN
    source: str | None = None  # Booking.com, Expedia, Booking Engine, ...
    paid: bool | None = None  # None = nog niet gecontroleerd
    open_amount: float | None = None  # openstaand saldo in Lighthouse (folio), None = niet gekend
    folio: list[dict] = field(default_factory=list)  # lijnen van de folio: {"label", "qty", "amount"}
    folio_total: float | None = None  # totaal van de folio
    room_type: str | None = None
    rate_plan: str | None = None  # tarief in Lighthouse, bv. "NRF BREAKFAST EXCL" of "STANDARD RATE"
    non_refundable: bool | None = None  # niet annuleerbaar (NRF); None = niet gekend
    remarks: str | None = None  # blok Opmerkingen op de detailpagina (bv. betaalinfo van het boekingskanaal)
    internal_memo: str | None = None  # interne memo van het hotel in Lighthouse (bij het label SPECIAAL VERZOEK)
    transactions: list[str] = field(default_factory=list)  # regels onder Transacties (detailpagina), bv. "Overschrijving ... € 362,00"
    pay_requested_at: datetime | None = None  # betaalverzoek in Lighthouse gemaakt (processes/pay_requests.py)
    breakfast_labeled_at: datetime | None = None  # label ONTBIJT op het planbord gezet (processes/breakfast_labels.py)
    pms_labels: list[str] = field(default_factory=list)  # labels op het planbord in Lighthouse (namen), bv. ["ONTBIJT"]
    payout_registered_at: datetime | None = None  # overschrijving van Booking.com in Lighthouse geregistreerd (processes/booking_payout.py)
    room_statuses: list[str] = field(default_factory=list)  # status per kamer in Lighthouse: none, readyforcheckin, checkin, checkout
    pms_codes_line: str | None = None  # regel "Deur Pin code: ..." zoals de robot ze in Lighthouse zette (processes/pms_sync.py)
    pay_link: str | None = None  # betaallink van Lighthouse (mail "Betaal uw openstaande saldo" in checkin@)
    token: str | None = None  # geheime sleutel in de link naar het check-in-formulier
    checkin_completed_at: datetime | None = None  # wanneer de gast het formulier invulde
    stairs_help: bool | None = None  # formulier: een van de gasten kan moeilijk trappen lopen (lagere verdieping indien vrij)
    stairs_memo_at: datetime | None = None  # wanneer de robot dat in de interne memo in Lighthouse zette (processes/stairs_memo.py)
    stairs_label_at: datetime | None = None  # wanneer de robot NIET VERPLAATSEN zette (kamer op een lage verdieping)
    booking_number: str | None = None  # reservatienummer in Lighthouse, bv. CPB-4276-002731
    pms_status: str | None = None  # status zoals Lighthouse ze toont: Nieuw, Bevestigd, Geannuleerd
    guest_count: int | None = None
    booked_at: datetime | None = None  # "Gemaakt op" in Lighthouse
    contact_checked_at: datetime | None = None  # wanneer de contactgegevens in Lighthouse gelezen werden
    guest_id: str | None = None  # gastprofiel (tabel Guests), zie processes/guest_profiles.py
    # Pincodes van Salto, één per kamer (processes/grant_access.py): {"room", "pin", "user_id", "group_id",
    # "schedule_id"}. De ids bij Salto zijn nodig om op te ruimen na vertrek of bij annulering.
    access_codes: list[dict] = field(default_factory=list)
    access_valid_from: datetime | None = None  # zelfde periode voor alle kamers
    access_valid_until: datetime | None = None
    room_moves: list[dict] = field(default_factory=list)  # kamerwissels met zelfde code: {"from", "to", "at"} (bericht aan de gast)
    stay_counted_at: datetime | None = None  # wanneer het verblijf meegeteld werd in het gastprofiel
    cancel_counted_at: datetime | None = None  # wanneer de annulering meegeteld werd in het gastprofiel
    created_at: datetime | None = None  # wanneer de robot de reservatie voor het eerst bewaarde (alleen lezen)
    updated_at: datetime | None = None  # laatste keer dat er iets aan de gegevens veranderde (alleen lezen)


def _first_pin(self) -> str | None:
    return self.access_codes[0]["pin"] if self.access_codes else None


def _code_rooms(self) -> list[str]:
    return [c["room"] for c in self.access_codes]


# Gemakshalve: de pincode als er maar één kamer is (eerste code), en de kamers met een code
Reservation.access_pin = property(_first_pin)
Reservation.access_rooms = property(_code_rooms)


@dataclass
class GuestProfile:
    """Een gast over al zijn reservaties heen (blijft bestaan als de reservaties opgeruimd zijn)."""

    hotel_id: str
    guest_id: str
    first_name: str = ""
    last_name: str = ""
    email: str | None = None
    email_own: bool = False  # eigen adres (niet een doorstuuradres van Booking.com, Expedia, ...), bruikbaar voor marketing
    phone: str | None = None
    language: str = "en"
    country: str | None = None
    first_stay: date | None = None  # aankomst van het eerste meegetelde verblijf
    last_stay: date | None = None  # vertrek van het laatste meegetelde verblijf
    stays: int = 0  # aantal verblijven = aantal aparte periodes (overlappende reservaties = één verblijf)
    nights: int = 0  # nachten over die periodes (twee kamers dezelfde nacht = één nacht)
    stay_periods: list[list[str]] = field(default_factory=list)  # [[aankomst, vertrek], ...] ISO-datums
    cancellations: int = 0  # aantal geannuleerde reservaties
    last_cancelled: date | None = None  # dag waarop de laatste annulering gezien werd
    persons: int = 0  # som over de verblijven met gekend aantal personen
    persons_stays: int = 0  # aantal verblijven met gekend aantal personen
    rooms: dict[str, int] = field(default_factory=dict)  # kamer -> aantal verblijven
    room_types: dict[str, int] = field(default_factory=dict)
    channels: dict[str, int] = field(default_factory=dict)  # Booking.com, Expedia, direct, ... -> aantal verblijven
    reservation_ids: list[str] = field(default_factory=list)  # gekoppelde reservaties (ook toekomstige)
    from_checkin_form: bool = False  # contactgegevens bevestigd door de gast zelf
    message_channels: list[str] = field(default_factory=list)  # gekozen kanalen voor berichten (check-in-formulier)
    muted_channels: list[str] = field(default_factory=list)  # door het hotel uitgezet: email, whatsapp, sms
    known_emails: list[str] = field(default_factory=list)  # alle eigen adressen ooit gezien (om te herkennen)
    known_phones: list[str] = field(default_factory=list)  # alle nummers ooit gezien (om te herkennen)
    backup_email: str | None = None  # extra adres uit het check-in-formulier
    backup_phone: str | None = None  # extra gsm-nummer uit het check-in-formulier (E.164)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class AccessCode:
    reservation_id: str
    room: str
    code: str
    valid_from: datetime
    valid_until: datetime
    salto_key_id: str | None = None  # referentie bij Salto, nodig om te annuleren


@dataclass
class SendResult:
    channel: Channel
    to: str
    ok: bool
    provider_id: str | None = None  # id bij Graph/Twilio, voor opvolging
    error: str | None = None
    delivered_to: str | None = None  # waar het echt naartoe ging (buiten PRD het testadres)
