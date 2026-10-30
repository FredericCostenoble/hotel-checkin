"""Workflow per hotel: welke stappen (berichten, codes) wanneer en onder welke voorwaarden,
apart per flow (boekingskanaal en betaalstatus).

Flows (vaste namen, volgorde van herkennen):
    booking         reservaties via Booking.com
    expedia         reservaties via Expedia
    website_paid    andere kanalen (website, telefoon, ...), al betaald
    website_unpaid  andere kanalen, nog niet (volledig) betaald

Standaard staat de workflow in config/hotels/<hotel_id>.toml ([workflow_parameters] en
[flows.<naam>] met [[flows.<naam>.steps]]). In de monitor (tabblad Workflow) kan hij gewijzigd
worden; die versie staat in de tabel HotelConfig en gaat dan voor, met wie en wanneer.

Een stap:
    step = "reminder"                 # berichttype (messaging/texts) of actie
    when = "days_before_arrival"      # after_booking | days_before_arrival
    days = 7
    only_if = ["form_not_completed", "not_cancelled"]
    channels = ["email"]
    skip_if_booked_late = true        # niet als de reservatie pas op of na deze dag binnenkwam
    pay = "none"                      # betaalknop: none | open_amount | city_tax
    enabled = true
    content = { reservation = true, checkin_form = true, code = false, practical_info = false }
                                      # wat in de mail staat (bouwstenen, zie messaging/templates.py)

De bouwblokken (Lighthouse, mail, SMS, Salto) kennen deze workflow niet; alleen de processen
lezen hem en beslissen daarmee wat wanneer gebeurt, en welke gegevens ze daarvoor nodig hebben.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from hotel_checkin.core.hotels import load_hotel
from hotel_checkin.core.models import Reservation, ReservationStatus

FLOWS = ("booking", "expedia", "website_paid", "website_unpaid")
WHEN = ("after_booking", "days_before_arrival", "days_after_departure")
AFTER_DEPARTURE_WINDOW = 14  # dagen: een bericht na vertrek dat zo lang niet weg kon, vervalt
CHANNELS = ("email", "sms", "whatsapp")
PAY = ("none", "open_amount", "city_tax")
STEP_TYPES = ("confirmation", "reminder", "access_code", "thank_you", "payment_request")
CITY_TAX_UNITS = ("person_night", "person_stay")
CONFIG_DOC = "workflow"
CONTENT = ("reservation", "checkin_form", "code", "practical_info")
# Standaardinhoud per berichttype (als een stap niets opgeeft)
DEFAULT_CONTENT = {
    "confirmation": {"reservation": True, "checkin_form": True, "code": False, "practical_info": False},
    "reminder": {"reservation": True, "checkin_form": True, "code": False, "practical_info": False},
    "access_code": {"reservation": False, "checkin_form": False, "code": True, "practical_info": True},
    "thank_you": {"reservation": False, "checkin_form": False, "code": False, "practical_info": False},
    "payment_request": {"reservation": True, "checkin_form": False, "code": False, "practical_info": False},
}

CONDITIONS = {
    "not_cancelled": lambda r: r.status != ReservationStatus.CANCELLED,
    "form_completed": lambda r: r.checkin_completed_at is not None,
    "form_not_completed": lambda r: r.checkin_completed_at is None,
    "paid": lambda r: r.paid is True,
    "not_paid": lambda r: r.paid is False,  # alleen als Lighthouse "openstaand" toont (onbekend telt niet)
    "checked_in": lambda r: r.status == ReservationStatus.CHECKED_IN,
    "has_email": lambda r: bool(r.guest.email),
    "has_phone": lambda r: bool(r.guest.phone),
}

DEFAULT_DETAIL_DAYS = 8
DEFAULT_PARAMETERS = {"city_tax_amount": 5.0, "city_tax_unit": "person_night", "currency": "EUR"}


@dataclass
class Step:
    step: str
    when: str
    days: int = 0
    only_if: list[str] = field(default_factory=list)
    channels: list[str] = field(default_factory=lambda: ["email"])
    replaced_by: list[str] = field(default_factory=list)  # niet meer gebruikt (vaste regel in is_replaced)
    # days_before_arrival: overslaan als de reservatie pas op of na de dag van deze stap
    # binnenkwam (dan kreeg de gast net de bevestiging)
    skip_if_booked_late: bool = False
    pay: str = "none"
    enabled: bool = True
    content: dict[str, bool] = field(default_factory=dict)  # leeg = standaard voor dit berichttype

    def mail_content(self) -> dict[str, bool]:
        """Wat in de mail staat: standaard voor het berichttype, aangevuld met de keuzes van de stap."""
        return {**DEFAULT_CONTENT.get(self.step, {}), **self.content}

    def conditions_met(self, r: Reservation) -> bool:
        return all(CONDITIONS[c](r) for c in self.only_if)

    def due_date(self, r: Reservation) -> date | None:
        """Dag waarop de stap moet gebeuren (niet bij after_booking)."""
        if self.when == "days_before_arrival":
            return r.arrival - timedelta(days=self.days)
        if self.when == "days_after_departure":
            return r.departure + timedelta(days=self.days)
        return None


# ---------------------------------------------------------------- configuratie lezen en bewaren


def file_config(hotel_id: str) -> dict:
    """De standaardworkflow uit het hotelbestand."""
    raw = load_hotel(hotel_id)
    return {"parameters": {**DEFAULT_PARAMETERS, **raw.get("workflow_parameters", {})},
            "flows": copy.deepcopy(raw.get("flows", {}))}


def config(hotel_id: str) -> dict:
    """De geldende workflow (gecontroleerd), met meta: source (file of monitor), updated_by, updated_at."""
    from hotel_checkin.guests import repository

    doc = repository.get_config_doc(hotel_id, CONFIG_DOC)
    if doc is None:
        cfg = validate(hotel_id, file_config(hotel_id))
        return {**cfg, "meta": {"source": "file", "updated_by": "", "updated_at": ""}}
    cfg = validate(hotel_id, _with_new_steps(doc["value"], file_config(hotel_id)))
    return {**cfg, "meta": {"source": "monitor", "updated_by": doc["updated_by"], "updated_at": doc["updated_at"]}}


def _with_new_steps(saved: dict, default: dict) -> dict:
    """Stappen die later aan de standaard zijn toegevoegd (bv. na vertrek) ook tonen in een eerder
    bewaarde workflow. Een stap uitzetten gebeurt met enabled, dus ontbrekend betekent nieuw."""
    out = copy.deepcopy(saved)
    for name, flow in default.get("flows", {}).items():
        mine = out.setdefault("flows", {}).setdefault(name, copy.deepcopy(flow))
        known = {s.get("step") for s in mine.get("steps", [])}
        mine.setdefault("steps", []).extend(copy.deepcopy(s) for s in flow.get("steps", [])
                                            if s.get("step") not in known)
    return out


def save_config(hotel_id: str, cfg: dict, user: str) -> dict:
    """Controleer en bewaar een gewijzigde workflow (monitor). Fout met uitleg als iets niet klopt."""
    from hotel_checkin.guests import repository

    clean = validate(hotel_id, cfg)
    repository.set_config_doc(hotel_id, CONFIG_DOC, clean, user)
    return config(hotel_id)


def reset_config(hotel_id: str) -> dict:
    """Terug naar de standaard uit het hotelbestand."""
    from hotel_checkin.guests import repository

    repository.delete_config_doc(hotel_id, CONFIG_DOC)
    return config(hotel_id)


def validate(hotel_id: str, cfg: dict) -> dict:
    """Geeft een nette kopie terug, of ValueError met alle problemen."""
    problems: list[str] = []
    params = {**DEFAULT_PARAMETERS, **(cfg.get("parameters") or {})}
    try:
        params["city_tax_amount"] = round(float(params["city_tax_amount"]), 2)
        if params["city_tax_amount"] < 0:
            problems.append("toeristenbelasting kan niet negatief zijn")
    except (TypeError, ValueError):
        problems.append("toeristenbelasting moet een bedrag zijn")
    if params["city_tax_unit"] not in CITY_TAX_UNITS:
        problems.append(f"onbekende eenheid toeristenbelasting {params['city_tax_unit']!r}")
    flows_in = cfg.get("flows") or {}
    flows = {}
    for name in FLOWS:
        raw = flows_in.get(name)
        if raw is None:
            problems.append(f"flow {name} ontbreekt")
            continue
        steps_raw = raw.get("steps") or []
        clean_steps = []
        for i, s in enumerate(steps_raw, 1):
            where = f"{name}, stap {i} ({s.get('step', '?')})"
            try:
                step = Step(
                    step=str(s["step"]), when=str(s["when"]), days=int(s.get("days", 0) or 0),
                    only_if=list(s.get("only_if", [])), channels=list(s.get("channels", ["email"])),
                    replaced_by=list(s.get("replaced_by", [])),
                    skip_if_booked_late=bool(s.get("skip_if_booked_late", False)),
                    pay=str(s.get("pay", "none")), enabled=bool(s.get("enabled", True)),
                    content={**DEFAULT_CONTENT.get(str(s.get("step")), {}),
                             **{k: bool(v) for k, v in (s.get("content") or {}).items()}},
                )
            except (KeyError, TypeError, ValueError) as exc:
                problems.append(f"{where}: {exc}")
                continue
            if step.step not in STEP_TYPES:
                problems.append(f"{where}: onbekende stap (kies uit {', '.join(STEP_TYPES)})")
            if step.when not in WHEN:
                problems.append(f"{where}: onbekende 'when' {step.when!r} (kies uit {', '.join(WHEN)})")
            if step.when != "after_booking" and not 0 <= step.days <= 365:
                problems.append(f"{where}: aantal dagen moet tussen 0 en 365 liggen")
            unknown = [c for c in step.only_if if c not in CONDITIONS] + [c for c in step.channels if c not in CHANNELS]
            if unknown:
                problems.append(f"{where}: onbekend {unknown}")
            if [k for k in step.content if k not in CONTENT]:
                problems.append(f"{where}: onbekende inhoud {[k for k in step.content if k not in CONTENT]}")
            if step.pay not in PAY:
                problems.append(f"{where}: onbekende betaalknop {step.pay!r}")
            clean_steps.append(step)
        names = [s.step for s in clean_steps]
        if len(names) != len(set(names)):
            problems.append(f"{name}: elke stap mag maar één keer voorkomen")
        for step in clean_steps:
            bad = [x for x in step.replaced_by if x not in names or x == step.step]
            if bad:
                problems.append(f"{name}, {step.step}: replaced_by verwijst naar {bad}")
        paid = raw.get("paid")
        flows[name] = {"sources": [str(x) for x in raw.get("sources", [])],
                       "paid": None if paid is None else bool(paid),
                       "steps": [asdict(s) for s in clean_steps]}
    if problems:
        raise ValueError(f"{hotel_id}: " + "; ".join(problems))
    return {"parameters": params, "flows": flows}


# ---------------------------------------------------------------- gebruik door de processen


def _steps_from(cfg: dict, flow: str | None) -> list[Step]:
    names = [flow] if flow else list(FLOWS)
    out = []
    for name in names:
        out += [Step(**s) for s in cfg["flows"][name]["steps"]]
    return out


def steps(hotel_id: str, flow: str | None = None, enabled_only: bool = True) -> list[Step]:
    """De stappen van één flow, of van alle flows samen (flow=None)."""
    found = _steps_from(config(hotel_id), flow)
    return [s for s in found if s.enabled] if enabled_only else found


def flow_for(hotel_id: str, r: Reservation, cfg: dict | None = None) -> str:
    """Welke flow geldt voor deze reservatie: eerst op kanaal, dan op betaalstatus."""
    cfg = cfg or config(hotel_id)
    source = (r.source or "").lower()
    for name in FLOWS:
        sources = [x.lower() for x in cfg["flows"][name]["sources"]]
        if sources and any(x in source for x in sources):
            return name
    return "website_paid" if r.paid is True else "website_unpaid"


def city_tax(hotel_id: str, r: Reservation, cfg: dict | None = None) -> float:
    """Toeristenbelasting voor deze reservatie volgens de parameters."""
    p = (cfg or config(hotel_id))["parameters"]
    persons = r.guest_count or 1
    nights = max((r.departure - r.arrival).days, 1)
    return round(p["city_tax_amount"] * persons * (nights if p["city_tax_unit"] == "person_night" else 1), 2)


def is_due(step: Step, r: Reservation, today: date) -> bool:
    """Moet deze stap nu gebeuren (los van de voorwaarden in only_if)?"""
    if step.when == "after_booking":
        return today < r.departure  # niet meer als de gast al vertrokken is (laat ingelezen)
    if step.when == "days_before_arrival":
        return step.due_date(r) <= today < r.arrival
    if step.when == "days_after_departure":
        return step.due_date(r) <= today < step.due_date(r) + timedelta(days=AFTER_DEPARTURE_WINDOW)
    return False


def _booked_late(step: Step, r: Reservation) -> bool:
    return bool(step.skip_if_booked_late and step.when == "days_before_arrival" and r.created_at
                and r.created_at.date() >= step.due_date(r))


def is_replaced(step: Step, r: Reservation, today: date, all_steps: list[Step]) -> bool:
    """Vaste regel: een bericht gaat niet weg als een later bericht (dichter bij de aankomst) nu al
    aan de beurt is en ook echt verstuurd wordt, bv. bij een late boeking meteen alleen de code-mail.
    Daarnaast skip_if_booked_late: niet als de boeking pas op of na de dag van dit bericht kwam."""
    if _booked_late(step, r):
        return True
    for later in all_steps:
        if later is step or not later.enabled or later.when != "days_before_arrival":
            continue
        if step.when == "days_before_arrival" and later.days >= step.days:
            continue  # niet later dan deze stap
        if is_due(later, r, today) and later.conditions_met(r) and not _booked_late(later, r):
            return True
    return False


def detail_window_days(hotel_id: str) -> int:
    """Vanaf hoeveel dagen voor aankomst de details van een reservatie nodig zijn: de vroegste
    stap voor aankomst (over alle flows), plus een dag marge."""
    days = [s.days for s in steps(hotel_id) if s.when == "days_before_arrival"]
    return max(days) + 1 if days else DEFAULT_DETAIL_DAYS


def needs_details_after_booking(hotel_id: str) -> bool:
    """Is er in een flow een stap meteen na de boeking (dan zijn de contactgegevens meteen nodig)?"""
    return any(s.when == "after_booking" for s in steps(hotel_id))
