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
from hotel_checkin.core.addresses import is_own_email
from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.models import Reservation, SendResult, normalize_language
from hotel_checkin.core.safety import environment
from hotel_checkin.guests import repository as guests
from hotel_checkin.messaging import email, sms, templates, whatsapp

TASK = "berichten"
READY_STEPS = ("confirmation", "reminder", "thank_you")  # stappen die alleen een bericht zijn


def ready_steps(hotel_id: str) -> tuple[str, ...]:
    """access_code pas als Salto ingesteld is (eerst een pincode maken, dan versturen)."""
    from hotel_checkin.access import salto

    steps = READY_STEPS + (("access_code",) if salto.configured(hotel_id) else ())
    # betaalverzoek pas met een betaalknop (Saferpay) en het openstaande bedrag uit Lighthouse
    return steps + (("payment_request",) if payments_ready(hotel_id) else ())


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


def pay_data(hotel_id: str, r: Reservation, cfg: dict, open_amount: float | None = None) -> dict:
    """Velden voor de betaalknop: openstaand bedrag (uit de folio in Lighthouse) met de prijzen
    erboven (_folio: lijnen, _total, _paid, _open), en de toeristenbelasting volgens de parameters."""
    p = cfg["parameters"]
    open_amount = r.open_amount if open_amount is None else open_amount
    cur = p["currency"]
    folio = []
    for x in r.folio:
        label = x["label"] + (f" ({x['qty']}×)" if x.get("qty") else "")
        folio.append((label, money(x["amount"], cur)))
    paid = (r.folio_total - open_amount) if r.folio_total is not None and open_amount is not None else None
    lang = r.guest.language if r.guest.language in CITY_TAX_UNIT_TEXT else "en"
    return {
        "toeristenbelasting": money(workflow.city_tax(hotel_id, r, cfg), p["currency"]),
        "toeristenbelasting_tarief": CITY_TAX_UNIT_TEXT[lang][p["city_tax_unit"]].format(
            bedrag=money(p["city_tax_amount"], p["currency"])),
        "openstaand_bedrag": money(open_amount, p["currency"]) if open_amount is not None else "",
        "kanaal": r.source or "",
        "_folio": folio,
        "_total": money(r.folio_total, cur) if r.folio_total is not None else "",
        "_paid": money(paid, cur) if paid and paid > 0.004 else "",
        "_open": money(open_amount, cur) if open_amount is not None else "",
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
        "_rooms": list(r.rooms),  # meer dan één kamer: "6 kamers: 31, 14, ..." in plaats van het kamertype
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


def send_mail(hotel_id: str, step: workflow.Step, r: Reservation, cfg: dict, to: str | None = None) -> SendResult:
    msg, _ = _rendered(hotel_id, step, r, cfg)
    reply_to = templates.load_hotel_config(hotel_id).get("hotel", {}).get("email")
    sender = hotel_setting(hotel_id, "VERZENDING_MAIL_AFZENDER", shared=False)
    return email.send_email(to=to or r.guest.email, subject=msg.subject, html_body=msg.html, sender=sender, hotel_id=hotel_id,
                            reply_to=reply_to)


_LOOKUP = object()


def profile_email(r: Reservation) -> str | None:
    """Eigen e-mailadres uit het gastprofiel (bv. van een vorig verblijf of check-in-formulier)."""
    from hotel_checkin.guests import profiles

    g = profiles.get_profile(r.hotel_id, r.guest_id) if r.guest_id else None
    return g.email if g and g.email_own and is_own_email(g.email) else None


def recipients(r: Reservation, kind: str, own_from_profile=_LOOKUP) -> list[str]:
    """Adressen van de gast. kind: "email" of "phone". Dubbels vallen weg.

    E-mail: de eigen adressen van de reservatie (hoofdadres en extra adres, het check-in-formulier
    gaat voor). Is er geen eigen adres, dan het eigen adres uit het gastprofiel (terugkerende gast).
    Pas als er nergens een eigen adres is: het doorstuuradres van Booking.com, Expedia, ... Dat is per
    reservatie verschillend en wordt dus nooit bij een andere reservatie gebruikt.
    """
    if kind == "phone":
        values = [r.guest.phone, r.guest.backup_phone]
    else:
        values = [v for v in (r.guest.email, r.guest.backup_email) if is_own_email(v)]
        if not values:
            own = profile_email(r) if own_from_profile is _LOOKUP else own_from_profile
            values = [own] if own else [v for v in (r.guest.email, r.guest.relay_email) if v]
    out: list[str] = []
    for v in values:
        if v and v.strip().lower() not in [o.lower() for o in out]:
            out.append(v.strip())
    return out


def _same(a: str, b: str) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def deliver(hotel_id: str, step: workflow.Step, r: Reservation, cfg: dict,
            only: tuple[str, str] | None = None, note: str = "") -> list[tuple[str, SendResult]]:
    """Stuur één stap naar de gast via alle kanalen en adressen die nu aan de beurt zijn.

    Per adres (hoofdadres en extra adres uit het formulier): altijd per mail (tenzij het hotel
    een kanaal voor deze gast uitzette). Per gsm-nummer ook per WhatsApp; heeft het nummer geen
    WhatsApp (mislukt meteen, of Twilio meldt het later), dan per sms. Elke poging staat in het
    berichtenlog met de ontvanger; na MAX_ATTEMPTS mislukte pogingen per kanaal en adres stopt het.

    only=(kanaal, adres): opnieuw versturen vanuit de monitor, alleen dat kanaal en adres, ook als
    het al eens lukte. note komt in het berichtenlog.
    """
    rows = [m for m in guests.messages_for(hotel_id, r.reservation_id) if m["message_type"] == step.step]
    muted = muted_channels(hotel_id, r)

    def done(channel: str, to: str) -> bool:
        return any(m["ok"] and m["channel"] == channel and _same(m.get("recipient", ""), to) for m in rows)

    def tries(channel: str, to: str) -> int:
        return sum(1 for m in rows if m["channel"] == channel and _same(m.get("recipient", ""), to))

    def wanted(channel: str, to: str) -> bool:
        if only:
            return only[0] == channel and _same(only[1], to)
        return channel not in muted and not done(channel, to) and tries(channel, to) < MAX_ATTEMPTS

    out: list[tuple[str, SendResult]] = []
    for to in recipients(r, "email"):
        if wanted("email", to):
            result = send_mail(hotel_id, step, r, cfg, to=to)
            guests.log_message(hotel_id, r.reservation_id, step.step, result, note=note)
            out.append(("email", result))
    phones = recipients(r, "phone")
    if not phones or not phone_enabled(hotel_id) or (only and only[0] == "email"):
        return out
    msg, data = _rendered(hotel_id, step, r, cfg)
    template = whatsapp_template(hotel_id, step.step, r.guest.language)
    values = {**data, "checkin_link": templates.checkin_link(hotel_id, r.token or "", normalize_language(r.guest.language))}
    variables = {str(i): str(values.get(k, "")) for i, k in enumerate(WHATSAPP_VARIABLES.get(step.step, ()), 1)}
    for to in phones:
        if not only and (done("whatsapp", to) or done("sms", to)):
            continue
        wa_ok = False
        if template and ((only and wanted("whatsapp", to)) or
                         (not only and "whatsapp" not in muted and tries("whatsapp", to) == 0)):
            mid = guests.new_message_id()
            result = whatsapp.send_whatsapp_template(hotel_id, to, template, variables,
                                                     status_callback=status_url(hotel_id, r.reservation_id, mid))
            guests.log_message(hotel_id, r.reservation_id, step.step, result, message_id=mid, note=note)
            out.append(("whatsapp", result))
            wa_ok = result.ok
        if wa_ok or not msg.sms or not wanted("sms", to):
            continue  # sms alleen als WhatsApp mislukt (meteen of later gemeld door Twilio)
        mid = guests.new_message_id()
        result = sms.send_sms(hotel_id, to, msg.sms, status_callback=status_url(hotel_id, r.reservation_id, mid))
        fallback = "terugval: geen WhatsApp" if template and not only else ""
        guests.log_message(hotel_id, r.reservation_id, step.step, result, message_id=mid,
                           note=", ".join(x for x in (note, fallback) if x))
        out.append(("sms", result))
    return out


def resend(hotel_id: str, reservation_id: str, step_name: str, channel: str, to: str, user: str) -> dict:
    """Eén bericht nu (opnieuw) versturen vanuit de monitor, naar één kanaal en adres.
    Buiten PRD gaat het zoals altijd naar het testadres (core/safety.py)."""
    if not enabled(hotel_id):
        return {"ok": False, "error": "Berichten staan uit in deze omgeving"}
    r = guests.get_reservation(hotel_id, reservation_id)
    if r is None:
        return {"ok": False, "error": "Reservatie niet gevonden"}
    if not any(_same(to, a) for a in recipients(r, "email" if channel == "email" else "phone")):
        return {"ok": False, "error": "Onbekend adres voor deze reservatie"}
    if channel != "email" and not phone_enabled(hotel_id):
        return {"ok": False, "error": "WhatsApp en sms zijn nog niet actief"}
    cfg = workflow.config(hotel_id)
    step = next((s for s in workflow._steps_from(cfg, workflow.flow_for(hotel_id, r, cfg)) if s.step == step_name), None)
    if step is None or step.step not in ready_steps(hotel_id):
        return {"ok": False, "error": "Dit bericht kan nog niet verstuurd worden"}
    if step.step == "access_code" and not code_ready(hotel_id, r, []):
        return {"ok": False, "error": "Nog geen pincode bij Salto"}
    results = deliver(hotel_id, step, r, cfg, only=(channel, to), note=f"opnieuw verstuurd door {user or 'monitor'}")
    if not results:
        return {"ok": False, "error": "Niets verstuurd (geen sjabloon of sms-tekst voor dit kanaal)"}
    return {"ok": all(res.ok for _, res in results),
            "error": "; ".join(res.error or "" for _, res in results if not res.ok)}


def muted_channels(hotel_id: str, r: Reservation) -> set[str]:
    """Kanalen die het hotel voor deze gast uitzette (tabblad Gasten), om boze klanten te vermijden."""
    from hotel_checkin.guests import profiles

    if not r.guest_id:
        return set()
    g = profiles.get_profile(hotel_id, r.guest_id)
    return set(g.muted_channels) if g else set()


def plan(hotel_id: str, r: Reservation, rows: list[dict], cfg: dict, ready: tuple[str, ...],
         today: date, begin: datetime | None, on: bool, phone: bool = False,
         muted: set[str] | frozenset = frozenset(), own_email=_LOOKUP) -> list[dict]:
    """De tijdlijn van één reservatie voor de monitor: per stap van haar flow wat er gebeurde of
    nog gaat gebeuren. state: sent, failed, planned, due, skipped, off. reason bij skipped/off.
    channels: per kanaal wat er gebeurt (mail altijd; WhatsApp met gsm-nummer, sms als terugval).
    Het scherm toont per kanaal de pogingen uit het berichtenlog."""
    channels = []
    for to in recipients(r, "email", own_email):
        channels.append({"channel": "email", "to": to, "reason": "muted" if "email" in muted else ""})
    off = "" if phone else "phone_off"
    for to in recipients(r, "phone"):
        channels.append({"channel": "whatsapp", "to": to, "reason": "muted" if "whatsapp" in muted else off})
        channels.append({"channel": "sms", "to": to, "reason": "muted" if "sms" in muted else off or "fallback"})
    flow = workflow.flow_for(hotel_id, r, cfg)
    steps = workflow._steps_from(cfg, flow)
    active = [s for s in steps if s.enabled]
    out = []
    for step in steps:
        mine = [m for m in rows if m["message_type"] == step.step]
        due = step.due_date(r) or (r.created_at.date() if r.created_at else None)
        item = {"step": step.step, "when": step.when, "days": step.days,
                "due": due.isoformat() if due else "", "state": "", "reason": "", "channels": channels}
        failed_now = [c for c in step.only_if if not workflow.CONDITIONS[c](r)]
        if any(m["ok"] for m in mine):
            item["state"] = "sent"
        elif mine:
            item["state"] = "failed"
        elif not step.enabled:
            item.update(state="off", reason="disabled")
        elif not on:
            item.update(state="off", reason="messaging_off")
        elif not r.created_at or (begin and r.created_at < begin):
            item.update(state="off", reason="before_start")
        elif failed_now:
            item.update(state="skipped", reason="condition:" + ",".join(failed_now))
        elif workflow._booked_late(step, r):
            item.update(state="skipped", reason="booked_late")
        elif workflow.is_due(step, r, today):
            if workflow.is_replaced(step, r, today, active):
                item.update(state="skipped", reason="later_due")
            elif step.step not in ready:
                item.update(state="planned", reason="not_ready", due=today.isoformat())  # zodra dit gebouwd is
            elif not (recipients(r, "email", own_email) or recipients(r, "phone")):
                item.update(state="skipped", reason="no_contact")
            else:
                item["state"] = "due"
        elif due and due > today:
            item.update(state="planned", reason="" if step.step in ready else "not_ready")
        else:
            item.update(state="skipped", reason="window_passed")
        out.append(item)
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
