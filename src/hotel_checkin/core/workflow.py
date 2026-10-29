"""Workflow per hotel: welke stappen (berichten, codes) wanneer en onder welke voorwaarden.

Staat in config/hotels/<hotel_id>.toml als [[workflow]]-blokken, bv.:

    [[workflow]]
    step = "reminder"                 # berichttype (messaging/texts) of actie
    when = "days_before_arrival"      # after_booking | days_before_arrival | at_start
    days = 7
    only_if = ["form_not_completed", "not_cancelled"]
    channels = ["email"]

De bouwblokken (Lighthouse, mail, SMS, Salto) kennen deze workflow niet; alleen de processen
lezen hem en beslissen daarmee wat wanneer gebeurt, en welke gegevens ze daarvoor nodig hebben.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from hotel_checkin.core.hotels import load_hotel
from hotel_checkin.core.models import Reservation, ReservationStatus

WHEN = ("after_booking", "days_before_arrival", "at_start")
CHANNELS = ("email", "sms", "whatsapp")

CONDITIONS = {
    "not_cancelled": lambda r: r.status != ReservationStatus.CANCELLED,
    "form_completed": lambda r: r.checkin_completed_at is not None,
    "form_not_completed": lambda r: r.checkin_completed_at is None,
    "paid": lambda r: r.paid is True,
    "checked_in": lambda r: r.status == ReservationStatus.CHECKED_IN,
    "has_email": lambda r: bool(r.guest.email),
    "has_phone": lambda r: bool(r.guest.phone),
}

DEFAULT_DETAIL_DAYS = 8


@dataclass
class Step:
    step: str
    when: str
    days: int = 0
    only_if: list[str] = field(default_factory=list)
    channels: list[str] = field(default_factory=lambda: ["email"])

    def conditions_met(self, r: Reservation) -> bool:
        return all(CONDITIONS[c](r) for c in self.only_if)

    def due_date(self, r: Reservation) -> date | None:
        """Dag waarop de stap moet gebeuren (alleen bij days_before_arrival)."""
        return r.arrival - timedelta(days=self.days) if self.when == "days_before_arrival" else None


def steps(hotel_id: str) -> list[Step]:
    """De workflow van een hotel, gecontroleerd. Fout bij een onbekende waarde."""
    out = []
    for i, raw in enumerate(load_hotel(hotel_id).get("workflow", []), 1):
        s = Step(
            step=raw["step"], when=raw["when"], days=int(raw.get("days", 0)),
            only_if=list(raw.get("only_if", [])), channels=list(raw.get("channels", ["email"])),
        )
        if s.when not in WHEN:
            raise ValueError(f"{hotel_id}: workflow stap {i}: onbekende 'when' {s.when!r} (kies uit {WHEN})")
        unknown = [c for c in s.only_if if c not in CONDITIONS] + [c for c in s.channels if c not in CHANNELS]
        if unknown:
            raise ValueError(f"{hotel_id}: workflow stap {i} ({s.step}): onbekend {unknown}")
        out.append(s)
    return out


def detail_window_days(hotel_id: str) -> int:
    """Vanaf hoeveel dagen voor aankomst de details van een reservatie nodig zijn: de vroegste
    stap voor aankomst, plus een dag marge."""
    days = [s.days for s in steps(hotel_id) if s.when == "days_before_arrival"]
    return max(days) + 1 if days else DEFAULT_DETAIL_DAYS


def needs_details_after_booking(hotel_id: str) -> bool:
    """Is er een stap meteen na de boeking (dan zijn de contactgegevens meteen nodig)?"""
    return any(s.when == "after_booking" for s in steps(hotel_id))
