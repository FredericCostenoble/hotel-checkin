"""Proces: de berichten uit de workflow van een hotel versturen (bevestiging, herinnering, ...).

Leest de workflow ([[workflow]] in config/hotels/<hotel_id>.toml) en beslist per reservatie
welke stap nu moet gebeuren. Elk bericht wordt één keer verstuurd (berichtenlog, tabel Messages).
Buiten PRD gaat alles naar het testadres (core/safety.py).

Veiligheid: alleen reservaties die na [messaging] start toegevoegd werden, en alleen als
[messaging] enabled_<omgeving> = true. Zo krijgen de reservaties die er al waren geen mail.

Late boeking (bv. 2 dagen voor aankomst): stappen met replaced_by = ["access_code"] vallen weg,
de gast krijgt meteen alleen de code-mail.

Voorlopig alleen e-mail. Stappen die meer vragen dan een bericht (access_code: eerst een code
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


def message_data(hotel_id: str, r: Reservation) -> dict[str, str]:
    lang = r.guest.language
    return {
        "voornaam": r.guest.first_name or r.guest.last_name, "achternaam": r.guest.last_name,
        "reservatienummer": r.booking_number or "", "kamertype": r.room_type or "",
        "kamernummer": ", ".join(r.rooms), "aankomst": templates.format_date(r.arrival, lang),
        "vertrek": templates.format_date(r.departure, lang), "token": r.token or "",
    }


def send(hotel_id: str, step: str, r: Reservation) -> SendResult:
    msg = templates.render(hotel_id, step, r.guest.language, message_data(hotel_id, r))
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
    all_steps = workflow.steps(hotel_id)
    steps = [s for s in all_steps if s.step in READY_STEPS and "email" in s.channels]
    sent, failed = [], []
    for r in guests.list_reservations(hotel_id):
        if not r.created_at or r.created_at < begin or not r.guest.email:
            continue
        for step in steps:
            if not workflow.is_due(step, r, today) or not step.conditions_met(r):
                continue
            if workflow.is_replaced(step, r, today, all_steps):
                continue
            if guests.was_sent(hotel_id, r.reservation_id, step.step, Channel.EMAIL.value):
                continue
            result = send(hotel_id, step.step, r)
            guests.log_message(hotel_id, r.reservation_id, step.step, result)
            (sent if result.ok else failed).append(f"{step.step} {r.booking_number or r.reservation_id[:8]}"
                                                   + ("" if result.ok else f" ({result.error})"))
    if sent or failed:
        note = ", ".join(sent) + (f". Mislukt: {'; '.join(failed)}" if failed else "")
        guests.log_robot_run(hotel_id, TASK, started, not failed, len(sent) + len(failed), len(sent), note[:1900])
    return len(sent)
