"""Proces: het label ONTBIJT op het planbord zetten bij wie ontbijt heeft.

Alleen als de hoofdschakelaar [schakelaars] ontbijt_labels aan staat (per omgeving, standaard uit).

Ontbijt als:
- het tarief ontbijt inbegrepen heeft ("NRF BREAKFAST INCL", "STANDARD RATE BREAKFAST INCL"). "BREAKFAST EXCL"
  en tarieven zonder vermelding (bv. LAST MINUTE) hebben geen ontbijt;
- of de folio ontbijt als extra heeft, voor alle personen en alle nachten: 2 personen, 3 nachten = 6 ontbijten.
  Minder (bv. maar voor één persoon): nog geen label, wel een uitleg in het robotlog.
Het label komt op elke kamer van de reservatie. Bestaande labels blijven staan, er wordt er alleen een bijgezet;
een label wordt nooit weggenomen. Een reservatie met label wordt onthouden (breakfast_labeled_at) en niet meer
bekeken. Schrijven in Lighthouse alleen in PRD, of op reservaties van een testgast ([test] guest_names).

Wanneer: reservaties die binnen [ontbijt] label_dagen (standaard 14) aankomen of nu verblijven. Het proces werkt
met wat de robot al gelezen heeft (tarief uit de lijst, folio van de detailpagina bij "Reservaties bijwerken"),
en leest alleen het planbord van die periode om het label te zetten.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime, timedelta

from hotel_checkin.core import clock, safety
from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.models import Reservation, ReservationStatus
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse
from hotel_checkin.pms.lighthouse_parse import rate_plans_from

TASK = "ontbijt_labels"
_INCL = re.compile(r"BREAKFAST\s*INCL|ONTBIJT\s*INBEGREPEN|INCL\w*\s*BREAKFAST", re.IGNORECASE)
_BREAKFAST_LINE = re.compile(r"ontbijt|breakfast|petit[- ]d[ée]jeuner|fr[üu]hst[üu]ck", re.IGNORECASE)


def label_name(hotel_id: str) -> str:
    return hotel_setting(hotel_id, "ONTBIJT_LABEL", default="ONTBIJT", shared=False) or "ONTBIJT"


def days_ahead(hotel_id: str) -> int:
    return int(hotel_setting(hotel_id, "ONTBIJT_LABEL_DAGEN", default="14", shared=False) or 14)


def breakfast(r: Reservation) -> tuple[bool, str]:
    """Heeft deze reservatie ontbijt? (ja/nee, uitleg in woorden)."""
    plans = [p.strip() for p in (r.rate_plan or "").split(",") if p.strip()]
    plans += [p for x in r.folio for p in rate_plans_from(x["label"])]
    if any(_INCL.search(p) for p in plans):
        return True, "tarief met ontbijt (" + ", ".join(sorted({p for p in plans if _INCL.search(p)})) + ")"
    lines = [x for x in r.folio if _BREAKFAST_LINE.search(x["label"]) and not rate_plans_from(x["label"])]
    if not lines:
        return False, "geen ontbijt in het tarief of de folio"
    count = sum(x["qty"] or 1 for x in lines)
    nights = (r.departure - r.arrival).days
    if not r.guest_count or nights <= 0:
        return False, f"{count} ontbijt(en) in de folio, aantal personen of nachten onbekend"
    needed = r.guest_count * nights
    who = (f"{r.guest_count} {'persoon' if r.guest_count == 1 else 'personen'} x "
           f"{nights} {'nacht' if nights == 1 else 'nachten'}")
    if count >= needed:
        return True, f"{count} {'ontbijt' if count == 1 else 'ontbijten'} in de folio voor {who}"
    return False, f"maar {count} van {needed} ontbijten in de folio ({who})"


def candidate(r: Reservation, today: date, horizon: int) -> bool:
    if r.status == ReservationStatus.CANCELLED or r.breakfast_labeled_at or r.departure <= today:
        return False
    if r.arrival > today + timedelta(days=horizon):
        return False
    return safety.may_write_pms(r.hotel_id, r.guest.first_name, r.guest.last_name)


def due(hotel_id: str, today: date) -> list[Reservation]:
    """Reservaties waarvoor nu een label gezet moet worden (schakelaar aan, ontbijt volgens wat bewaard is).
    Leeg = de robot hoeft hiervoor Lighthouse niet te openen."""
    from hotel_checkin.processes.send_messages import switch

    if not switch(hotel_id, "ontbijt_labels"):
        return []
    horizon = days_ahead(hotel_id)
    return [r for r in guests.list_reservations(hotel_id) if candidate(r, today, horizon) and breakfast(r)[0]]


def run(hotel_id: str, lh, today: date | None = None) -> dict:
    """Alle reservaties die in aanmerking komen. Geeft een samenvatting voor het robotlog (log_run)."""
    from hotel_checkin.core import progress
    from hotel_checkin.processes.send_messages import switch

    result: dict = {"checked": 0, "labeled": [], "no": 0, "partial": [], "errors": [], "off": False}
    if not switch(hotel_id, "ontbijt_labels"):
        result["off"] = True
        return result
    today = today or clock.today(hotel_id)
    todo = [r for r in sorted(guests.list_reservations(hotel_id), key=lambda x: x.arrival)
            if candidate(r, today, days_ahead(hotel_id))]
    progress.step(hotel_id, TASK, f"{len(todo)} reservaties nakijken (tarief en folio)", force=True)
    name = label_name(hotel_id)
    for n, r in enumerate(todo, 1):
        result["checked"] += 1
        label = r.booking_number or r.reservation_id[:8]
        yes, why = breakfast(r)
        if not yes:
            if why.startswith("maar "):
                result["partial"].append(f"{label}: {why}")
            else:
                result["no"] += 1
            continue
        progress.step(hotel_id, TASK, f"{n} van {len(todo)}: {label}, label zetten ({why})")
        try:
            board = lighthouse.reservation_labels(hotel_id, r.reservation_id, r.arrival, r.departure, lh)
            label_id = board["names"].get(name)
            if not label_id:
                raise RuntimeError(f"label {name} bestaat niet op het planbord")
            if not board["rooms"]:
                raise RuntimeError("reservatie niet gevonden op het planbord")
            added = 0
            for room in board["rooms"]:
                if label_id not in room["labels"]:
                    lighthouse.add_label(hotel_id, r.reservation_id, room["accommodation_id"], room["labels"],
                                         label_id, lh)
                    added += 1
            # Nakijken: staat het label er nu op elke kamer?
            after = lighthouse.reservation_labels(hotel_id, r.reservation_id, r.arrival, r.departure, lh)
            missing = [x for x in after["rooms"] if label_id not in x["labels"]]
            if missing:
                raise RuntimeError(f"label staat er niet na het bewaren ({len(missing)} kamer(s))")
        except Exception as exc:
            logging.exception("%s: ontbijt-label %s", hotel_id, label)
            result["errors"].append(f"{label}: {exc}")
            continue
        r.breakfast_labeled_at = datetime.now(UTC)
        guests.save_reservation(r, fields=guests.BREAKFAST_FIELDS)
        rooms = len(board["rooms"])
        result["labeled"].append(f"{label}: {why}" + (f", {rooms} kamers" if rooms > 1 else "")
                                 + ("" if added else " (label stond er al)"))
    return result


def log_idle(hotel_id: str, today: date | None = None) -> None:
    """Regel in het robotlog als er nu geen label te zetten is, met waarom."""
    from hotel_checkin.processes.send_messages import switch

    started = datetime.now(UTC)
    if not switch(hotel_id, "ontbijt_labels"):
        note = "schakelaar Ontbijt labels staat uit: niets gedaan"
    else:
        today = today or clock.today(hotel_id)
        horizon = days_ahead(hotel_id)
        near = [r for r in guests.list_reservations(hotel_id)
                if r.status != ReservationStatus.CANCELLED and r.departure > today
                and r.arrival <= today + timedelta(days=horizon)]
        labeled = [r for r in near if r.breakfast_labeled_at]
        checks = [(r, *breakfast(r)) for r in near if not r.breakfast_labeled_at]
        partial = [f"{r.booking_number or ''}: {why}" for r, yes, why in checks if not yes and why.startswith("maar ")]
        parts = [f"niets te doen nu: {len(near)} reservaties met aankomst binnen {horizon} dagen of nu in het hotel",
                 f"{len(labeled)} met label {label_name(hotel_id)}",
                 f"{len(checks) - len(partial)} zonder ontbijt"]
        if partial:
            parts.append(f"{len(partial)} met te weinig ontbijten in de folio: " + "; ".join(partial[:5]))
        note = ", ".join(parts)
    guests.log_robot_run(hotel_id, TASK, started, True, 0, 0, note)


def log_run(hotel_id: str, started: datetime, result: dict) -> None:
    """Eigen regel in het robotlog: te doen = nagekeken, gedaan = label gezet; de notitie zegt waarom."""
    if result["off"]:
        return
    parts = [f"{result['checked']} reservaties nagekeken (aankomst binnen {days_ahead(hotel_id)} dagen of nu in het hotel)"]
    parts.append(f"{len(result['labeled'])} label(s) {label_name(hotel_id)} gezet: " + "; ".join(result["labeled"])
                 if result["labeled"] else "geen label gezet")
    if result["partial"]:
        parts.append(f"{len(result['partial'])} met te weinig ontbijten in de folio, nog geen label: "
                     + "; ".join(result["partial"][:8]))
    if result["no"]:
        parts.append(f"{result['no']} zonder ontbijt")
    if result["errors"]:
        parts.append(f"{len(result['errors'])} fout: " + "; ".join(result["errors"][:5]))
    errors = len(result["errors"])
    guests.log_robot_run(hotel_id, TASK, started, not errors or result["checked"] > errors, result["checked"],
                         len(result["labeled"]), ". ".join(parts), skipped=errors)
