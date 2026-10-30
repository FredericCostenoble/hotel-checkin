"""Workflow per hotel: welke stappen (berichten, codes) wanneer en onder welke voorwaarden.

Staat in config/hotels/<hotel_id>.toml als [[workflow]]-blokken, bv.:

    [[workflow]]
    step = "reminder"                 # berichttype (messaging/texts) of actie
    when = "days_before_arrival"      # after_booking | days_before_arrival | at_start
    days = 7
    only_if = ["form_not_completed", "not_cancelled"]
    channels = ["email"]
    replaced_by = ["access_code"]     # niet meer nodig als die stap al aan de beurt is
    skip_if_booked_late = true        # niet als de reservatie pas op of na deze dag binnenkwam

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
    # Stap overslaan als een van deze stappen al aan de beurt is (bv. late boeking: meteen de
    # code-mail, geen bevestiging meer)
    replaced_by: list[str] = field(default_factory=list)
    # days_before_arrival: overslaan als de reservatie pas op of na de dag van deze stap
    # binnenkwam (dan kreeg de gast net de bevestiging)
    skip_if_booked_late: bool = False

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
            replaced_by=list(raw.get("replaced_by", [])), skip_if_booked_late=bool(raw.get("skip_if_booked_late", False)),
        )
        if s.when not in WHEN:
            raise ValueError(f"{hotel_id}: workflow stap {i}: onbekende 'when' {s.when!r} (kies uit {WHEN})")
        unknown = [c for c in s.only_if if c not in CONDITIONS] + [c for c in s.channels if c not in CHANNELS]
        if unknown:
            raise ValueError(f"{hotel_id}: workflow stap {i} ({s.step}): onbekend {unknown}")
        out.append(s)
    names = {s.step for s in out}
    for s in out:
        if [x for x in s.replaced_by if x not in names]:
            raise ValueError(f"{hotel_id}: workflow {s.step}: replaced_by verwijst naar onbekende stap {s.replaced_by}")
    return out


def is_due(step: Step, r: Reservation, today: date) -> bool:
    """Moet deze stap nu gebeuren (los van de voorwaarden in only_if)?"""
    if step.when == "after_booking":
        return True
    if step.when == "days_before_arrival":
        return step.due_date(r) <= today < r.arrival
    return False  # at_start: niet gebruikt


def is_replaced(step: Step, r: Reservation, today: date, all_steps: list[Step]) -> bool:
    """Overslaan omdat een latere stap al aan de beurt is, of omdat de boeking te laat kwam."""
    by_name = {s.step: s for s in all_steps}
    if any(is_due(by_name[x], r, today) for x in step.replaced_by):
        return True
    if step.skip_if_booked_late and step.when == "days_before_arrival" and r.created_at:
        return r.created_at.date() >= step.due_date(r)
    return False


def detail_window_days(hotel_id: str) -> int:
    """Vanaf hoeveel dagen voor aankomst de details van een reservatie nodig zijn: de vroegste
    stap voor aankomst, plus een dag marge."""
    days = [s.days for s in steps(hotel_id) if s.when == "days_before_arrival"]
    return max(days) + 1 if days else DEFAULT_DETAIL_DAYS


def needs_details_after_booking(hotel_id: str) -> bool:
    """Is er een stap meteen na de boeking (dan zijn de contactgegevens meteen nodig)?"""
    return any(s.when == "after_booking" for s in steps(hotel_id))
