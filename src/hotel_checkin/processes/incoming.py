"""Proces: een gast (of iemand van het personeel) antwoordt op het nummer van de automatische berichten.

Dat nummer staat niet op de WhatsApp Business-app van het hotel: niemand leest het. Daarom:
1. het bericht gaat per mail naar het hotel ([twilio] doorsturen, anders [hotel] email), met de reservatie als het
   nummer bij een reservatie hoort;
2. de afzender krijgt een automatisch antwoord met het gewone WhatsApp-nummer en het telefoonnummer van het hotel
   (texts/<taal>.toml, [incoming] antwoord), hoogstens één keer per REPLY_EVERY per nummer, en niet aan het
   personeel (de nummers van de ontbijt- en schoonmaaklijst);
3. in het berichtenlog van de reservatie (type incoming), zonder de tekst zelf.

Twilio roept /api/twilio/incoming?h=<hotel_id> op (function_app.py); in Twilio in te stellen bij het nummer en de
WhatsApp-afzender ("A message comes in"). Buiten PRD gaan mail en antwoord naar het testadres en -nummer (core/safety.py).
"""

from __future__ import annotations

import html
import logging
from datetime import UTC, date, datetime, timedelta

from hotel_checkin.core.hotels import load_hotel
from hotel_checkin.core.models import Channel, Reservation, ReservationStatus, SendResult
from hotel_checkin.guests import repository as guests

REPLY_EVERY = timedelta(hours=12)
REPLY_STATE = "incoming_reply:{number}"
COUNTRY_LANGUAGE = {"+32": "nl", "+31": "nl", "+33": "fr", "+49": "de", "+43": "de"}  # als de reservatie onbekend is


def _reservation(hotel_id: str, number: str, today: date) -> Reservation | None:
    """De reservatie van dit nummer die nu loopt of het eerst komt (anders de laatste)."""
    found = [r for r in guests.find_by_phone(hotel_id, number) if r.status != ReservationStatus.CANCELLED]
    if not found:
        return None
    coming = sorted((r for r in found if r.departure >= today), key=lambda r: r.arrival)
    return coming[0] if coming else max(found, key=lambda r: r.departure)


def _staff(hotel_id: str, number: str) -> bool:
    from hotel_checkin.checkin.service import normalize_phone

    hotel = load_hotel(hotel_id)
    numbers = [*(hotel.get("ontbijtlijst", {}).get("whatsapp") or []), *(hotel.get("kuislijst", {}).get("whatsapp") or [])]
    return any(normalize_phone(str(n)) == number for n in numbers)


def _language(r: Reservation | None, number: str) -> str:
    from hotel_checkin.processes.send_messages import normalize_language

    if r is not None:
        return normalize_language(r.guest.language)
    return next((lang for prefix, lang in COUNTRY_LANGUAGE.items() if number.startswith(prefix)), "en")


def reply_text(hotel_id: str, language: str) -> str:
    from hotel_checkin.messaging import templates

    config = templates.load_hotel_config(hotel_id)
    fields = templates._config_fields(config)
    return templates._fill(templates.load_texts(hotel_id, language)["incoming"]["antwoord"], fields)


def _mail(hotel_id: str, channel: str, number: str, body: str, media: int, r: Reservation | None) -> list[SendResult]:
    from hotel_checkin.messaging import email

    hotel = load_hotel(hotel_id)
    to = hotel.get("twilio", {}).get("doorsturen") or [hotel["hotel"]["email"]]
    to = [to] if isinstance(to, str) else list(to)
    who = number
    if r is not None:
        who += f" ({r.guest.first_name} {r.guest.last_name}, kamer {', '.join(r.rooms) or '?'}, " \
               f"{r.arrival:%d/%m} tot {r.departure:%d/%m})"
    name = "WhatsApp" if channel == "whatsapp" else "Sms"
    p = '<p style="font-family:Arial,sans-serif;font-size:14px;">'
    quote = html.escape(body or "(geen tekst)").replace("\n", "<br>")
    box = "font-family:Arial,sans-serif;font-size:15px;border-left:3px solid #B4BCCC;margin:8px 0;padding:4px 12px;"
    parts = [f"{p}{name} van {html.escape(who)} op het nummer van de automatische berichten:</p>",
             f'<blockquote style="{box}">{quote}</blockquote>']
    if media:
        parts.append(f"{p}Met {media} bijlage(n) (foto, document, ...): die staan alleen in Twilio.</p>")
    parts.append(f"{p}Antwoorden kan niet op dit nummer: neem contact op via de WhatsApp-app van het hotel of bel "
                 f"{html.escape(number)}.</p>")
    sender = hotel.get("verzending", {}).get("mail_afzender")
    return [email.send_email(to=t, subject=f"{name} van {who}", html_body="\n".join(parts), sender=sender,
                             hotel_id=hotel_id) for t in to]


def handle(hotel_id: str, channel: str, number: str, body: str, media: int = 0, now: datetime | None = None) -> dict:
    """Een binnenkomend bericht verwerken. channel: "whatsapp" of "sms"; number: +32..."""
    from hotel_checkin.core import clock
    from hotel_checkin.messaging import sms, whatsapp
    from hotel_checkin.processes.send_messages import phone_enabled

    now = now or datetime.now(UTC)
    r = _reservation(hotel_id, number, clock.today(hotel_id))
    mails = _mail(hotel_id, channel, number, body, media, r)
    out = {"forwarded": all(m.ok for m in mails), "replied": False, "reservation": r.reservation_id if r else ""}
    if r is not None:
        guests.log_message(hotel_id, r.reservation_id, "incoming",
                           SendResult(Channel(channel), number, True),
                           note="bericht van de gast, per mail doorgestuurd naar het hotel"
                                if out["forwarded"] else "bericht van de gast, doorsturen per mail mislukt")
    if not out["forwarded"]:
        logging.error("%s: %s van %s niet doorgestuurd: %s", hotel_id, channel, number,
                      "; ".join(m.error or "" for m in mails))
    if _staff(hotel_id, number) or not phone_enabled(hotel_id):
        return out
    key = REPLY_STATE.format(number=number)
    last = guests.get_state(hotel_id, key)
    if last and now - datetime.fromisoformat(last) < REPLY_EVERY:
        return out
    text = reply_text(hotel_id, _language(r, number))
    # Antwoord binnen 24 uur na het bericht van de gast: vrije tekst mag (ook op WhatsApp)
    res = whatsapp.send_whatsapp_text(hotel_id, number, text) if channel == "whatsapp" else sms.send_sms(hotel_id, number, text)
    if res.ok:
        guests.set_state(hotel_id, key, now.isoformat())
    out["replied"] = res.ok
    return out
