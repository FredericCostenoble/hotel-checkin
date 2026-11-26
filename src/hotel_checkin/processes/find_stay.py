"""Proces: een gast ter plaatse vraagt de link naar zijn verblijfspagina opnieuw (QR-code aan de deur of in de kamer).

De pagina na de QR-code (web/checkin/find.html) toont nooit iets van een reservatie. Ze stuurt de link alleen naar een
adres of nummer dat al in de reservatie staat; wie iets gokt, stuurt hoogstens de echte gast een bericht. Drie manieren:

- e-mail of gsm: de gast typt een adres of nummer. Staat dat in een reservatie die vandaag loopt of morgen begint,
  dan gaat de link naar dat adres of nummer (sms). Het antwoord is altijd hetzelfde, gevonden of niet.
- naam: familienaam en vertrekdatum. Kloppen beide, dan gaat de link naar de contacten van de reservatie en tonen we
  waar naartoe, gemaskeerd (j•••@gmail.com, +32 4•• •• •• 74), zodat de gast weet waar hij moet kijken. Een adres of
  nummer van een boekingsplatform heet "bericht via Booking.com"; daarvan gaat er maar één (het adres, anders het
  nummer). Platformcontacten alleen als er geen eigen adres of nummer is.
- WhatsApp: zie processes/incoming.py (de gast schrijft eerst, het antwoord mag vrije tekst zijn).

Limieten tegen gokken en spam: per toestel (IP) en per ingetypte waarde een paar pogingen per uur, en per reservatie
hoogstens één verzending per MIN_GAP. Elke verzending staat in het berichtenlog (type stay_link).
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import unicodedata
from datetime import UTC, date, datetime, timedelta

from hotel_checkin.core.addresses import is_own_email, relay_platform
from hotel_checkin.core.models import Reservation, ReservationStatus, SendResult
from hotel_checkin.guests import repository as guests

TRIES_PER_CLIENT = 6  # per uur, per toestel
TRIES_PER_VALUE = 3  # per uur, per ingetypt adres, nummer of naam
MIN_GAP = timedelta(minutes=10)  # per reservatie
HOUR = timedelta(hours=1)
DOT = "•"


# ------------------------------------------------------------ zoeken


def _today(hotel_id: str) -> date:
    from hotel_checkin.core import clock

    return clock.today(hotel_id)


def current(hotel_id: str, today: date | None = None) -> list[Reservation]:
    """Reservaties die vandaag lopen of morgen beginnen (niet geannuleerd, met een link)."""
    today = today or _today(hotel_id)
    return [r for r in guests.list_reservations(hotel_id)
            if r.status != ReservationStatus.CANCELLED and r.token
            and r.arrival <= today + timedelta(days=1) and r.departure >= today]


def _phone(raw: str | None) -> str | None:
    from hotel_checkin.checkin.service import normalize_phone, placeholder_phone

    p = normalize_phone(raw or "") if raw else None
    return p if p and not placeholder_phone(p) else None


def _emails(r: Reservation) -> list[str]:
    return [e.strip().lower() for e in (r.guest.email, r.guest.backup_email, r.guest.relay_email) if e and "@" in e]


def _phones(r: Reservation) -> list[str]:
    return [p for p in (_phone(r.guest.phone), _phone(r.guest.backup_phone)) if p]


def _plain(text: str) -> str:
    """Kleine letters, zonder accenten en leestekens (Müller = muller, De Smet = de smet)."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _name_matches(r: Reservation, typed: str) -> bool:
    last, words = _plain(r.guest.last_name), f" {_plain(typed)} "
    return bool(last) and f" {last} " in words


def by_email(hotel_id: str, email: str, today: date | None = None) -> list[Reservation]:
    e = (email or "").strip().lower()
    return [r for r in current(hotel_id, today) if e and e in _emails(r)]


def by_phone(hotel_id: str, phone: str, today: date | None = None) -> list[Reservation]:
    p = _phone(phone)
    return [r for r in current(hotel_id, today) if p and p in _phones(r)]


def by_name(hotel_id: str, name: str, departure: date, today: date | None = None) -> list[Reservation]:
    return [r for r in current(hotel_id, today) if r.departure == departure and _name_matches(r, name)]


# ------------------------------------------------------------ waar naartoe


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:1]}{DOT * 3}@{domain}"


def mask_phone(phone: str) -> str:
    digits = phone.lstrip("+")
    cc = 2 if digits[:2] in ("32", "31", "33", "49", "43", "44", "34", "39", "41", "45", "46", "47", "48") else \
        1 if digits[:1] in ("1", "7") else 3
    rest = digits[cc:]
    hidden = "".join(DOT if ch.isdigit() else ch for ch in rest[1:-2])
    return f"+{digits[:cc]} {rest[:1]}{hidden}{rest[-2:]}"


def targets(r: Reservation) -> list[dict]:
    """Waar de link naartoe gaat: eerst de eigen adressen en nummers van de gast (ingevuld in het check-in-formulier);
    alleen als er geen zijn, één bericht via het boekingsplatform (het doorstuuradres, anders het nummer)."""
    consent = {_phone(p) for p in (r.guest.phone_consent or [])}
    out: list[dict] = []
    for e in dict.fromkeys(e for e in (r.guest.email, r.guest.backup_email) if is_own_email(e)):
        out.append({"channel": "email", "to": e, "shown": mask_email(e)})
    for p in dict.fromkeys(p for p in _phones(r) if p in consent):
        out.append({"channel": "sms", "to": p, "shown": mask_phone(p)})
    if out:
        return out
    relay = next((e for e in (r.guest.email, r.guest.relay_email) if e and relay_platform(e)), None)
    platform = relay_platform(relay) if relay else (r.source or "").strip() or "platform"
    if relay:
        return [{"channel": "email", "to": relay, "platform": platform}]
    phone = next(iter(_phones(r)), None)
    return [{"channel": "sms", "to": phone, "platform": platform}] if phone else []


# ------------------------------------------------------------ versturen


def _texts(hotel_id: str, language: str) -> tuple[dict, dict]:
    from hotel_checkin.messaging import templates

    config = templates.load_hotel_config(hotel_id)
    return templates.load_texts(hotel_id, language)["find_stay"], templates._config_fields(config)


def _mail_html(hotel_id: str, r: Reservation, link: str, language: str) -> tuple[str, str]:
    from hotel_checkin.messaging import templates

    t, fields = _texts(hotel_id, language)
    fields = {**fields, "voornaam": r.guest.first_name or "", "link": link}
    colors = templates.load_hotel_config(hotel_id).get("kleuren", {})
    acc = colors.get("accent_donker", "#5C6478")
    p = '<p style="font-family:Arial,sans-serif;font-size:15px;line-height:1.5;color:#2B2F38;">'
    body = "".join(f"{p}{html.escape(templates._fill(x, fields))}</p>" for x in t["mail"])
    button = (f'<p style="margin:22px 0;"><a href="{html.escape(link)}" style="display:inline-block;background:{acc};'
              f'color:#fff;font-family:Arial,sans-serif;font-size:16px;font-weight:bold;text-decoration:none;'
              f'padding:14px 22px;border-radius:10px;">{html.escape(templates._fill(t["knop"], fields))}</a></p>')
    return templates._fill(t["onderwerp"], fields), body + button


def _send(hotel_id: str, r: Reservation, target: dict, how: str) -> SendResult:
    from hotel_checkin.core.hotels import load_hotel
    from hotel_checkin.messaging import email, sms, templates
    from hotel_checkin.processes.send_messages import normalize_language

    language = normalize_language(r.guest.language)
    link = templates.checkin_link(hotel_id, r.token, language)
    if target["channel"] == "email":
        subject, body = _mail_html(hotel_id, r, link, language)
        hotel = load_hotel(hotel_id)
        res = email.send_email(to=target["to"], subject=subject, html_body=body, hotel_id=hotel_id,
                               sender=hotel.get("verzending", {}).get("mail_afzender"),
                               reply_to=hotel["hotel"]["email"])
    else:
        t, fields = _texts(hotel_id, language)
        res = sms.send_sms(hotel_id, target["to"], templates._fill(t["sms"], {**fields, "link": link}))
    note = f"link naar de verblijfspagina op vraag van de gast ({how})"
    try:
        guests.log_message(hotel_id, r.reservation_id, "stay_link", res, note=note)
    except Exception:
        logging.warning("%s: stay_link niet gelogd", hotel_id, exc_info=True)
    return res


# ------------------------------------------------------------ limieten


def _hits(hotel_id: str, key: str, now: datetime) -> list[str]:
    raw = guests.get_state(hotel_id, key)
    try:
        hits = json.loads(raw) if raw else []
    except ValueError:
        hits = []
    return [h for h in hits if now - datetime.fromisoformat(h) < HOUR]


def _allowed(hotel_id: str, key: str, limit: int, now: datetime) -> bool:
    """Telt deze poging mee en zegt of ze nog mag."""
    hits = _hits(hotel_id, key, now)
    if len(hits) >= limit:
        return False
    guests.set_state(hotel_id, key, json.dumps([*hits, now.isoformat()]))
    return True


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]  # geen adressen of namen in de toestand


def _recent(hotel_id: str, r: Reservation, now: datetime) -> bool:
    last = guests.get_state(hotel_id, f"find:res:{r.reservation_id}")
    return bool(last) and now - datetime.fromisoformat(last) < MIN_GAP


# ------------------------------------------------------------ de vraag


def request(hotel_id: str, method: str, value: str, departure: str = "", client: str = "",
            now: datetime | None = None, today: date | None = None) -> dict:
    """method: email, phone of name. Antwoord: {"status": "ok"} (e-mail en gsm: altijd, gevonden of niet),
    {"status": "sent", "to": [...]} of {"status": "not_found"} (naam), {"status": "limit"} of {"status": "invalid"}."""
    now = now or datetime.now(UTC)
    value = (value or "").strip()
    if method not in ("email", "phone", "name") or not value or len(value) > 200:
        return {"status": "invalid"}
    dep = None
    if method == "name":
        try:
            dep = date.fromisoformat(departure)
        except (TypeError, ValueError):
            return {"status": "invalid"}
    elif (method == "phone" and not _phone(value)) or (method == "email" and ("@" not in value or " " in value)):
        return {"status": "invalid"}
    key_value = _plain(value) + (f"|{dep}" if dep else "") if method == "name" else value.lower()
    if not _allowed(hotel_id, f"find:client:{_digest(client or '-')}", TRIES_PER_CLIENT, now) \
            or not _allowed(hotel_id, f"find:value:{_digest(method + ':' + key_value)}", TRIES_PER_VALUE, now):
        return {"status": "limit"}

    if method == "email":
        found = [(r, [{"channel": "email", "to": value}]) for r in by_email(hotel_id, value, today)]
    elif method == "phone":
        p = _phone(value)
        found = [(r, [{"channel": "sms", "to": p}]) for r in by_phone(hotel_id, value, today)]
    else:
        found = [(r, targets(r)) for r in by_name(hotel_id, value, dep, today)]
        if not found:
            return {"status": "not_found"}

    shown: list[dict] = []
    for r, tgts in found:
        if not _recent(hotel_id, r, now):
            sent = [t for t in tgts if t.get("to") and _send(hotel_id, r, t, method).ok]
            if sent:
                guests.set_state(hotel_id, f"find:res:{r.reservation_id}", now.isoformat())
        for t in tgts:
            item = {"platform": t["platform"]} if t.get("platform") else {"channel": t["channel"], "shown": t["shown"]} \
                if t.get("shown") else None
            if item and item not in shown:
                shown.append(item)
    if method == "name":
        return {"status": "sent", "to": shown}
    return {"status": "ok"}


# ------------------------------------------------------------ via WhatsApp (of sms) naar het hotelnummer


def keyword_language(hotel_id: str, body: str) -> str | None:
    """De taal als het bericht de vooraf ingevulde tekst van de QR-code is ("Mijn verblijf", "My stay", ...)."""
    from hotel_checkin.messaging.templates import LANGUAGES

    typed = _plain(body)
    for lang in LANGUAGES:
        try:
            if typed and typed == _plain(_texts(hotel_id, lang)[0]["whatsapp_tekst"]):
                return lang
        except (KeyError, FileNotFoundError):
            continue
    return None


def reply_request(hotel_id: str, channel: str, number: str, language: str, now: datetime | None = None,
                  today: date | None = None) -> dict:
    """De gast stuurde de tekst van de QR-code naar het hotelnummer. Staat zijn nummer in een reservatie die vandaag
    loopt of morgen begint (ook een nummer van Booking.com of Expedia: hij schrijft zelf eerst), dan krijgt hij zijn
    link terug op hetzelfde kanaal; anders uitleg. WhatsApp zelf bewijst van welk nummer het bericht komt."""
    from hotel_checkin.messaging import sms, templates, whatsapp
    from hotel_checkin.processes.send_messages import normalize_language

    now = now or datetime.now(UTC)
    send = (lambda text: whatsapp.send_whatsapp_text(hotel_id, number, text)) if channel == "whatsapp" \
        else (lambda text: sms.send_sms(hotel_id, number, text))
    if not _allowed(hotel_id, f"find:value:{_digest('chat:' + number)}", TRIES_PER_VALUE, now):
        return {"status": "limit", "replied": False}
    found = by_phone(hotel_id, number, today)
    if not found:
        t, fields = _texts(hotel_id, language)
        res = send(templates._fill(t["whatsapp_niet_gevonden"], fields))
        return {"status": "not_found", "replied": res.ok}
    ok = True
    for r in found:
        lang = normalize_language(r.guest.language)
        t, fields = _texts(hotel_id, lang)
        link = templates.checkin_link(hotel_id, r.token, lang)
        res = send(templates._fill(t["whatsapp_gevonden"], {**fields, "voornaam": r.guest.first_name or "", "link": link}))
        ok = ok and res.ok
        try:
            guests.log_message(hotel_id, r.reservation_id, "stay_link", res,
                               note=f"link naar de verblijfspagina op vraag van de gast ({channel}, QR-code)")
        except Exception:
            logging.warning("%s: stay_link niet gelogd", hotel_id, exc_info=True)
    return {"status": "sent", "replied": ok, "reservations": [r.reservation_id for r in found]}


def page_info(hotel_id: str, language: str) -> dict:
    """Wat de pagina na de QR-code nodig heeft: hotel (logo, kleuren, telefoon), de WhatsApp-link en het nummer
    om nu te bellen (zelfde regel als het doorschakelen: receptie tijdens de receptie-uren, 's avonds het noodnummer,
    anders de gsm van het hotel)."""
    from hotel_checkin.checkin.service import hotel_info
    from hotel_checkin.processes import call_forward
    from hotel_checkin.messaging import whatsapp
    from hotel_checkin.processes.send_messages import phone_enabled

    t, _ = _texts(hotel_id, language)
    wa = whatsapp.chat_link(hotel_id, t["whatsapp_tekst"]) if phone_enabled(hotel_id) else ""
    return {"hotel": hotel_info(hotel_id, language), "whatsapp": wa, "call": call_forward.number(hotel_id)}
