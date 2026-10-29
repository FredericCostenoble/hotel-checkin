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


@dataclass
class Reservation:
    hotel_id: str  # welk hotel (bestand config/hotels/<hotel_id>.toml), bv. "lucca"
    reservation_id: str  # Lighthouse-id (uuid uit /Customer/Reservations/Detail/{uuid})
    guest: Guest
    arrival: date
    departure: date
    rooms: list[str] = field(default_factory=list)
    status: ReservationStatus = ReservationStatus.READY_FOR_CHECKIN
    source: str | None = None  # Booking.com, Expedia, Booking Engine, ...
    paid: bool | None = None  # None = nog niet gecontroleerd
    room_type: str | None = None
    token: str | None = None  # geheime sleutel in de link naar het check-in-formulier
    checkin_completed_at: datetime | None = None  # wanneer de gast het formulier invulde
    booking_number: str | None = None  # reservatienummer in Lighthouse, bv. CPB-4276-002731
    pms_status: str | None = None  # status zoals Lighthouse ze toont: Nieuw, Bevestigd, Geannuleerd
    guest_count: int | None = None
    booked_at: datetime | None = None  # "Gemaakt op" in Lighthouse


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
