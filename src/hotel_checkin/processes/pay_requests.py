"""Proces: betaalverzoeken in Lighthouse maken, zodat de mails aan de gast een betaalknop hebben.

Lighthouse maakt de betaallink. De robot maakt een betaalverzoek (online transactie, Betaling, Stuur verzoek)
voor het openstaande saldo en laat de mail naar de eigen mailbox gaan (checkin@), nooit naar de gast. De
mailcontrole haalt de link uit die mail en bewaart ze bij de reservatie (mail_trigger._payment_links); de
volgende mail aan de gast toont de knop Betalen.

Wanneer: voor een bericht met betaalknop (stap met pay, bv. de code-mail of het betaalverzoek na vertrek), vanaf
[betaalverzoek] dagen_vooraf (standaard 2) dagen voor dat bericht, als er iets openstaat en er nog geen link is.
Eén keer per reservatie (pay_requested_at). Alleen als Berichten aan staat (zonder mails geen link nodig).
Schrijven in Lighthouse alleen in PRD of op reservaties van een testgast ([test] guest_names).
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime, timedelta

from hotel_checkin.core import clock, safety, workflow
from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.models import Channel, Reservation, ReservationStatus, SendResult
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse

TASK = "betaalverzoeken"
MESSAGE_TYPE = "pay_request"
MAX_SECONDS = 3 * 60
WAIT_FOR_MAIL = timedelta(hours=2)  # geen link na zoveel tijd: melden


def template(hotel_id: str) -> str:
    return hotel_setting(hotel_id, "BETAALVERZOEK_TEMPLATE", default="Betaalverzoek", shared=False) or "Betaalverzoek"


def days_ahead(hotel_id: str) -> int:
    return int(hotel_setting(hotel_id, "BETAALVERZOEK_DAGEN_VOORAF", default="2", shared=False) or 2)


def pay_step_soon(hotel_id: str, r: Reservation, today: date, cfg: dict) -> str | None:
    """Naam van een bericht met betaalknop dat binnenkort (of nu) aan de beurt is, anders None."""
    flow = workflow.flow_for(hotel_id, r, cfg)
    lead = days_ahead(hotel_id)
    for s in workflow._steps_from(cfg, flow):
        if not s.enabled or s.pay == "none":
            continue
        due = s.due_date(r)
        if due is None:
            continue
        if due - timedelta(days=lead) <= today <= due + timedelta(days=workflow.AFTER_DEPARTURE_WINDOW):
            return s.step
    return None


def candidate(r: Reservation, today: date, cfg: dict, unknown_open: bool = False) -> str | None:
    """Moet er nu een betaalverzoek gemaakt worden? Geeft het bericht terug waarvoor, anders None.
    unknown_open: ook als het saldo nog niet gelezen is (de taak leest het dan eerst)."""
    if r.status == ReservationStatus.CANCELLED or r.pay_requested_at:
        return None
    if r.pay_link:
        return None  # link bestaat al (bv. met de hand gemaakt)
    if r.open_amount is None and not unknown_open:
        return None
    if r.open_amount is not None and r.open_amount <= 0.01:
        return None
    if not safety.may_write_pms(r.hotel_id, r.guest.first_name, r.guest.last_name):
        return None
    return pay_step_soon(r.hotel_id, r, today, cfg)


def due(hotel_id: str, today: date | None = None) -> list[Reservation]:
    from hotel_checkin.processes.send_messages import switch

    if not switch(hotel_id, "berichten"):
        return []
    today = today or clock.today(hotel_id)
    cfg = workflow.config(hotel_id)
    return [r for r in guests.list_reservations(hotel_id) if candidate(r, today, cfg, unknown_open=True)]


def waiting_too_long(hotel_id: str) -> list[Reservation]:
    """Betaalverzoek gemaakt, maar na WAIT_FOR_MAIL nog geen link uit de mailbox."""
    now = datetime.now(UTC)
    return [r for r in guests.list_reservations(hotel_id)
            if r.pay_requested_at and not r.pay_link and now - r.pay_requested_at > WAIT_FOR_MAIL
            and r.status != ReservationStatus.CANCELLED and r.departure >= clock.today(hotel_id) - timedelta(days=7)]


def run(hotel_id: str, lh, today: date | None = None) -> dict:
    from hotel_checkin.core import progress, run_context
    from hotel_checkin.messaging import mailbox

    today = today or clock.today(hotel_id)
    cfg = workflow.config(hotel_id)
    todo = sorted(due(hotel_id, today), key=lambda r: r.arrival)
    result: dict = {"todo": len(todo), "made": [], "errors": [], "left": 0}
    if not todo:
        return result
    send_to = mailbox.mailbox_address(hotel_id)
    stop = run_context.stop_at(MAX_SECONDS)
    progress.step(hotel_id, TASK, f"{len(todo)} betaalverzoek(en) te maken", force=True)
    for n, r in enumerate(todo, 1):
        if time.monotonic() > stop:
            result["left"] = len(todo) - n + 1
            break
        label = r.booking_number or r.reservation_id[:8]
        if r.open_amount is None:  # saldo nog niet gekend: eerst de pagina lezen
            progress.step(hotel_id, TASK, f"{n} van {len(todo)}: {label}, openstaand saldo lezen")
            try:
                d = lighthouse.get_reservation(hotel_id, r.reservation_id, lh, contact=False)
            except Exception as exc:  # noqa: BLE001
                result["errors"].append(f"{label}: saldo niet gelezen ({type(exc).__name__}: {str(exc)[:120]})")
                continue
            if d.open_amount is None:
                result["errors"].append(f"{label}: openstaand saldo niet gevonden op de pagina")
                continue
            r.open_amount, r.folio, r.folio_total = d.open_amount, d.folio, d.folio_total
            guests.save_reservation(r, fields=("open_amount", "folio", "folio_total"))
            if r.open_amount <= 0.01:
                result["nothing_open"] = result.get("nothing_open", 0) + 1
                continue
        step = candidate(r, today, cfg)
        if not step:
            continue
        progress.step(hotel_id, TASK, f"{n} van {len(todo)}: {label} (voor {step})")
        try:
            amount = lighthouse.create_payment_request(hotel_id, r.reservation_id, send_to, template(hotel_id),
                                                       (r.guest.language or "nl")[:2], lh)
        except Exception as exc:
            logging.exception("%s: betaalverzoek %s", hotel_id, label)
            result["errors"].append(f"{label}: {type(exc).__name__}: {str(exc)[:160]}")
            continue
        r.pay_requested_at = datetime.now(UTC)
        guests.save_reservation(r, fields=guests.PAY_REQUEST_FIELDS)
        note = f"betaalverzoek van {amount:.2f} EUR gemaakt in Lighthouse, mail naar {send_to} (voor {step})"
        guests.log_message(hotel_id, r.reservation_id, MESSAGE_TYPE, SendResult(Channel.PMS, "Lighthouse", True),
                           note=note)
        result["made"].append(f"{label}: {amount:.2f} EUR")
    return result


def log_run(hotel_id: str, started: datetime, result: dict) -> None:
    from hotel_checkin.messaging import mailbox

    late = waiting_too_long(hotel_id)
    if result["todo"]:
        parts = [f"{len(result['made'])} betaalverzoek(en) gemaakt, mail naar {mailbox.mailbox_address(hotel_id)}: "
                 + "; ".join(result["made"]) if result["made"] else "geen betaalverzoek gemaakt"]
    else:
        from hotel_checkin.processes.send_messages import switch

        if not switch(hotel_id, "berichten"):
            parts = ["schakelaar Berichten en Salto staat uit: geen betaalverzoeken (zonder mails geen link nodig)"]
        else:
            parts = [(f"niets te doen nu: geen bericht met betaalknop binnen {days_ahead(hotel_id)} dagen "
                      "zonder betaallink")]
    if result["errors"]:
        parts.append(f"{len(result['errors'])} fout: " + "; ".join(result["errors"][:5]))
    if result["left"]:
        parts.append(f"nog {result['left']} in een volgende run (tijd op)")
    if late:
        parts.append(f"{len(late)} zonder link na 2 uur (mail niet aangekomen in de mailbox?): "
                     + ", ".join(r.booking_number or r.reservation_id[:8] for r in late[:5]))
    errors = len(result["errors"]) + len(late)
    guests.log_robot_run(hotel_id, TASK, started, not result["errors"] or bool(result["made"]), result["todo"],
                         len(result["made"]), ". ".join(parts), skipped=errors)
