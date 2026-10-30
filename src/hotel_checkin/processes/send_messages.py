"""Proces: de berichten uit de workflow van een hotel versturen (bevestiging, herinnering, ...).

Leest de workflow (core/workflow.py: per flow, standaard uit het hotelbestand, gewijzigd in de
monitor) en beslist per reservatie welke flow geldt en welke stap nu moet gebeuren. Elk bericht wordt één keer verstuurd (berichtenlog, tabel Messages).
Buiten PRD gaat alles naar het testadres (core/safety.py).

Veiligheid: alleen reservaties die na [messaging] start toegevoegd werden, en alleen als
[messaging] enabled_<omgeving> = true. Zo krijgen de reservaties die er al waren geen mail.

Late boeking (bv. 2 dagen voor aankomst): stappen met replaced_by = ["access_code"] vallen weg,
de gast krijgt meteen alleen de code-mail.

Kanalen (geen keuze voor de gast): altijd per mail. Is er een gsm-nummer, dan ook per WhatsApp;
heeft het nummer geen WhatsApp, dan per sms. Voorlopig alleen e-mail (Twilio nog niet betaald). Stappen die meer vragen dan een bericht (access_code: eerst een code
bij Salto) of een kanaal dat er nog niet is (sms, WhatsApp), worden overgeslagen.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from hotel_checkin.core import workflow
from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.models import Channel, Reservation, SendResult
from hotel_checkin.core.safety import environment
from hotel_checkin.guests import repository as guests
from hotel_checkin.messaging import email, templates

TASK = "berichten"
READY_STEPS = ("confirmation", "reminder")  # stappen die alleen een bericht zijn


def enabled(hotel_id: str) -> bool:
    flag = hotel_setting(hotel_id, f"MESSAGING_ENABLED_{environment().upper()}", default="false", shared=False)
    return str(flag).lower() == "true"


def start(hotel_id: str) -> datetime | None:
    value = hotel_setting(hotel_id, "MESSAGING_START", required=False, shared=False)
    if not value:
        return None
    s = datetime.fromisoformat(str(value))
    return s if s.tzinfo else s.replace(tzinfo=timezone.utc)


CITY_TAX_UNIT_TEXT = {
    "nl": {"person_night": "{bedrag} per persoon per nacht", "person_stay": "{bedrag} per persoon per verblijf"},
    "fr": {"person_night": "{bedrag} par personne et par nuit", "person_stay": "{bedrag} par personne et par séjour"},
    "en": {"person_night": "{bedrag} per person per night", "person_stay": "{bedrag} per person per stay"},
    "de": {"person_night": "{bedrag} pro Person und Nacht", "person_stay": "{bedrag} pro Person und Aufenthalt"},
}


def money(amount: float, currency: str = "EUR") -> str:
    symbol = {"EUR": "€"}.get(currency, currency)
    return f"{symbol} {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pay_data(hotel_id: str, r: Reservation, cfg: dict, open_amount: float | None = None) -> dict[str, str]:
    """Velden voor de betaalknop: toeristenbelasting (volgens de parameters) en openstaand bedrag."""
    p = cfg["parameters"]
    lang = r.guest.language if r.guest.language in CITY_TAX_UNIT_TEXT else "en"
    return {
        "toeristenbelasting": money(workflow.city_tax(hotel_id, r, cfg), p["currency"]),
        "toeristenbelasting_tarief": CITY_TAX_UNIT_TEXT[lang][p["city_tax_unit"]].format(
            bedrag=money(p["city_tax_amount"], p["currency"])),
        "openstaand_bedrag": money(open_amount, p["currency"]) if open_amount is not None else "",
        "kanaal": r.source or "",
    }


def mail_content(step: workflow.Step, r: Reservation) -> dict[str, bool]:
    """Inhoud van de mail voor deze gast: geen link naar het formulier als het al ingevuld is."""
    content = step.mail_content()
    if r.checkin_completed_at:
        content["checkin_form"] = False
    return content


def payments_ready(hotel_id: str) -> bool:
    """Betaalknop pas als Saferpay ingesteld is (nog niet gebouwd)."""
    return bool(hotel_setting(hotel_id, "SAFERPAY_TERMINAL_ID", required=False, shared=False))


def message_data(hotel_id: str, r: Reservation) -> dict[str, str]:
    lang = r.guest.language
    return {
        "voornaam": r.guest.first_name or r.guest.last_name, "achternaam": r.guest.last_name,
        "reservatienummer": r.booking_number or "", "kamertype": r.room_type or "",
        "kamernummer": ", ".join(r.rooms), "aankomst": templates.format_date(r.arrival, lang),
        "vertrek": templates.format_date(r.departure, lang), "token": r.token or "",
    }


def send(hotel_id: str, step: workflow.Step, r: Reservation, cfg: dict) -> SendResult:
    pay = step.pay if payments_ready(hotel_id) else "none"
    data = {**message_data(hotel_id, r), **pay_data(hotel_id, r, cfg)}
    msg = templates.render(hotel_id, step.step, r.guest.language, data, mail_content(step, r), pay)
    reply_to = templates.load_hotel_config(hotel_id).get("hotel", {}).get("email")
    sender = hotel_setting(hotel_id, "VERZENDING_MAIL_AFZENDER", shared=False)
    return email.send_email(to=r.guest.email, subject=msg.subject, html_body=msg.html, sender=sender,
                            reply_to=reply_to)


def run(hotel_id: str, today: date | None = None) -> int:
    """Verstuur wat nu moet. Geeft het aantal verstuurde berichten terug."""
    if not enabled(hotel_id):
        return 0
    begin = start(hotel_id)
    if begin is None:
        logging.warning("%s: [messaging] start ontbreekt, niets verstuurd", hotel_id)
        return 0
    today = today or date.today()
    started = datetime.now(timezone.utc)
    cfg = workflow.config(hotel_id)
    sent, failed = [], []
    for r in guests.list_reservations(hotel_id):
        if not r.created_at or r.created_at < begin or not r.guest.email:
            continue
        flow = workflow.flow_for(hotel_id, r, cfg)  # kanaal en betaalstatus
        all_steps = [s for s in workflow._steps_from(cfg, flow) if s.enabled]
        for step in [s for s in all_steps if s.step in READY_STEPS and "email" in s.channels]:
            if not workflow.is_due(step, r, today) or not step.conditions_met(r):
                continue
            if workflow.is_replaced(step, r, today, all_steps):
                continue
            if guests.was_sent(hotel_id, r.reservation_id, step.step, Channel.EMAIL.value):
                continue
            result = send(hotel_id, step, r, cfg)
            guests.log_message(hotel_id, r.reservation_id, step.step, result)
            (sent if result.ok else failed).append(f"{step.step} {r.booking_number or r.reservation_id[:8]}"
                                                   + ("" if result.ok else f" ({result.error})"))
    if sent or failed:
        note = ", ".join(sent) + (f". Mislukt: {'; '.join(failed)}" if failed else "")
        guests.log_robot_run(hotel_id, TASK, started, not failed, len(sent) + len(failed), len(sent), note[:1900])
    return len(sent)
