"""Proces: de berichten uit de workflow van een hotel versturen (bevestiging, herinnering, ...).

Leest de workflow (core/workflow.py: per flow, standaard uit het hotelbestand, gewijzigd in de
monitor) en beslist per reservatie welke flow geldt en welke stap nu moet gebeuren. Elk bericht wordt één keer verstuurd (berichtenlog, tabel Messages).
Buiten PRD gaat alles naar het testadres (core/safety.py).

Veiligheid: alleen reservaties die na [messaging] start toegevoegd werden, en alleen als
[messaging] enabled_<omgeving> = true. Zo krijgen de reservaties die er al waren geen mail.

Late boeking (bv. 2 dagen voor aankomst): stappen met replaced_by = ["access_code"] vallen weg,
de gast krijgt meteen alleen de code-mail.

Kanalen (geen keuze voor de gast): altijd per mail. Is er een gsm-nummer, dan ook per WhatsApp;
heeft het nummer geen WhatsApp, dan per sms. WhatsApp en sms pas als [messaging] phone = true
(Twilio betaald, WhatsApp-sjablonen goedgekeurd: [whatsapp] template_<stap>_<taal> = "HX..."). Stappen die meer vragen dan een bericht (access_code: eerst een code
bij Salto) of een kanaal dat er nog niet is (sms, WhatsApp), worden overgeslagen.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from urllib.parse import urlencode

from hotel_checkin.core import workflow
from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.models import Reservation, SendResult
from hotel_checkin.core.safety import environment
from hotel_checkin.guests import repository as guests
from hotel_checkin.messaging import email, sms, templates, whatsapp

TASK = "berichten"
READY_STEPS = ("confirmation", "reminder")  # stappen die alleen een bericht zijn


def ready_steps(hotel_id: str) -> tuple[str, ...]:
    """access_code pas als Salto ingesteld is (eerst een pincode maken, dan versturen)."""
    from hotel_checkin.access import salto

    return READY_STEPS + (("access_code",) if salto.configured(hotel_id) else ())


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
    code = {}
    if r.access_pin:
        code = {"pincode": r.access_pin,
                "code_geldig_van": templates.format_moment(r.access_valid_from, lang) if r.access_valid_from else "",
                "code_geldig_tot": templates.format_moment(r.access_valid_until, lang) if r.access_valid_until else ""}
    return {**code,
        "voornaam": r.guest.first_name or r.guest.last_name, "achternaam": r.guest.last_name,
        "reservatienummer": r.booking_number or "", "kamertype": r.room_type or "",
        "kamernummer": ", ".join(r.rooms), "aankomst": templates.format_date(r.arrival, lang),
        "vertrek": templates.format_date(r.departure, lang), "token": r.token or "",
    }


MAX_ATTEMPTS = 3  # per stap en kanaal; daarna niet meer opnieuw (staat rood in de monitor)
# WhatsApp-sjabloon: welke gegevens in welke plaats ({{1}}, {{2}}, ...), per berichttype
WHATSAPP_VARIABLES = {
    "confirmation": ("voornaam", "checkin_link"),
    "reminder": ("voornaam", "checkin_link"),
    "access_code": ("voornaam", "pincode", "kamernummer"),
}


def phone_enabled(hotel_id: str) -> bool:
    """WhatsApp en sms aan? (zodra Twilio betaald is en de sjablonen goedgekeurd zijn)"""
    return str(hotel_setting(hotel_id, "MESSAGING_PHONE", default="false", shared=False)).lower() == "true"


def whatsapp_template(hotel_id: str, step: str, language: str) -> str | None:
    """Goedgekeurd WhatsApp-sjabloon (Twilio ContentSid, HX...) voor dit bericht en deze taal."""
    return hotel_setting(hotel_id, f"WHATSAPP_TEMPLATE_{step.upper()}_{language.upper()}", required=False, shared=False) \
        or hotel_setting(hotel_id, f"WHATSAPP_TEMPLATE_{step.upper()}_EN", required=False, shared=False)


def status_url(hotel_id: str, reservation_id: str, message_id: str) -> str | None:
    """Adres waar Twilio meldt of het bericht aankwam (alleen in Azure)."""
    host = os.environ.get("WEBSITE_HOSTNAME")
    if not host:
        return None
    return f"https://{host}/api/twilio/status?" + urlencode({"h": hotel_id, "r": reservation_id, "m": message_id})


def _rendered(hotel_id: str, step: workflow.Step, r: Reservation, cfg: dict):
    pay = step.pay if payments_ready(hotel_id) else "none"
    data = {**message_data(hotel_id, r), **pay_data(hotel_id, r, cfg)}
    return templates.render(hotel_id, step.step, r.guest.language, data, mail_content(step, r), pay), data


def send_mail(hotel_id: str, step: workflow.Step, r: Reservation, cfg: dict) -> SendResult:
    msg, _ = _rendered(hotel_id, step, r, cfg)
    reply_to = templates.load_hotel_config(hotel_id).get("hotel", {}).get("email")
    sender = hotel_setting(hotel_id, "VERZENDING_MAIL_AFZENDER", shared=False)
    return email.send_email(to=r.guest.email, subject=msg.subject, html_body=msg.html, sender=sender,
                            reply_to=reply_to)


def deliver(hotel_id: str, step: workflow.Step, r: Reservation, cfg: dict) -> list[tuple[str, SendResult]]:
    """Stuur één stap naar de gast via alle kanalen die nu aan de beurt zijn.

    Altijd per mail. Met gsm-nummer ook per WhatsApp; heeft het nummer geen WhatsApp (mislukt
    meteen, of Twilio meldt het later), dan per sms. Elke poging staat in het berichtenlog;
    na MAX_ATTEMPTS mislukte pogingen per kanaal stopt het.
    """
    rows = [m for m in guests.messages_for(hotel_id, r.reservation_id) if m["message_type"] == step.step]
    ok = {c: any(m["ok"] and m["channel"] == c for m in rows) for c in ("email", "whatsapp", "sms")}
    tries = {c: sum(1 for m in rows if m["channel"] == c) for c in ("email", "whatsapp", "sms")}
    out: list[tuple[str, SendResult]] = []
    if r.guest.email and not ok["email"] and tries["email"] < MAX_ATTEMPTS:
        result = send_mail(hotel_id, step, r, cfg)
        guests.log_message(hotel_id, r.reservation_id, step.step, result)
        out.append(("email", result))
    if not (r.guest.phone and phone_enabled(hotel_id)) or ok["whatsapp"] or ok["sms"]:
        return out
    msg, data = _rendered(hotel_id, step, r, cfg)
    template = whatsapp_template(hotel_id, step.step, r.guest.language)
    if template and tries["whatsapp"] == 0:
        mid = guests.new_message_id()
        values = {**data, "checkin_link": templates.checkin_link(hotel_id, r.token or "")}
        variables = {str(i): str(values.get(k, "")) for i, k in enumerate(WHATSAPP_VARIABLES.get(step.step, ()), 1)}
        result = whatsapp.send_whatsapp_template(hotel_id, r.guest.phone, template, variables,
                                                 status_callback=status_url(hotel_id, r.reservation_id, mid))
        guests.log_message(hotel_id, r.reservation_id, step.step, result, message_id=mid)
        out.append(("whatsapp", result))
        if result.ok:
            return out  # sms alleen als WhatsApp mislukt (meteen of later gemeld door Twilio)
    if tries["sms"] < MAX_ATTEMPTS and msg.sms:
        mid = guests.new_message_id()
        result = sms.send_sms(hotel_id, r.guest.phone, msg.sms,
                              status_callback=status_url(hotel_id, r.reservation_id, mid))
        note = "terugval: geen WhatsApp" if template else ""
        guests.log_message(hotel_id, r.reservation_id, step.step, result, message_id=mid, note=note)
        out.append(("sms", result))
    return out


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
    ready = ready_steps(hotel_id)
    sent, failed = [], []
    for r in guests.list_reservations(hotel_id):
        if not r.created_at or r.created_at < begin or not (r.guest.email or r.guest.phone):
            continue
        flow = workflow.flow_for(hotel_id, r, cfg)  # kanaal en betaalstatus
        all_steps = [s for s in workflow._steps_from(cfg, flow) if s.enabled]
        for step in [s for s in all_steps if s.step in ready]:
            if not workflow.is_due(step, r, today) or not step.conditions_met(r):
                continue
            if workflow.is_replaced(step, r, today, all_steps):
                continue
            if step.step == "access_code" and not code_ready(hotel_id, r, failed):
                continue
            for channel, result in deliver(hotel_id, step, r, cfg):
                label = f"{step.step} {channel} {r.booking_number or r.reservation_id[:8]}"
                (sent if result.ok else failed).append(label + ("" if result.ok else f" ({result.error})"))
    if sent or failed:
        note = ", ".join(sent) + (f". Mislukt: {'; '.join(failed)}" if failed else "")
        guests.log_robot_run(hotel_id, TASK, started, not failed, len(sent) + len(failed), len(sent), note[:1900])
    return len(sent)


def code_ready(hotel_id: str, r: Reservation, failed: list[str]) -> bool:
    """Pincode bij Salto maken als ze er nog niet is. Zonder kamer: later opnieuw (stil).
    Andere fout: in het berichtenlog (kanaal salto), max. MAX_ATTEMPTS keer."""
    from hotel_checkin.access import salto
    from hotel_checkin.core.models import Channel
    from hotel_checkin.processes import grant_access

    if r.access_pin:
        return True
    if not r.rooms:
        return False
    tries = sum(1 for m in guests.messages_for(hotel_id, r.reservation_id)
                if m["message_type"] == "access_code" and m["channel"] == "salto")
    if tries >= MAX_ATTEMPTS:
        return False
    try:
        grant_access.grant(hotel_id, r)
    except Exception as exc:  # noqa: BLE001 - in het logboek, volgende run opnieuw
        error = f"{type(exc).__name__}: {exc}" if not isinstance(exc, salto.SaltoError) else str(exc)
        guests.log_message(hotel_id, r.reservation_id, "access_code",
                           SendResult(Channel.SALTO, "Salto", False, error=error))
        failed.append(f"access_code salto {r.booking_number or r.reservation_id[:8]} ({error})")
        return False
    return True


def twilio_status(hotel_id: str, reservation_id: str, message_id: str, status: str, error_code: str = "") -> None:
    """Statusmelding van Twilio verwerken. Mislukte WhatsApp: de volgende run stuurt een sms."""
    error = f"Twilio {status}" + (f", code {error_code}" if error_code else "")
    guests.update_message_status(hotel_id, reservation_id, message_id, status, error)
