"""Bouwblok 1: WhatsApp sturen via Twilio (WhatsApp Business).

Berichten die het hotel als eerste stuurt, moeten een door Meta goedgekeurde template
gebruiken (in Twilio een Content Template met een ContentSid, beginnend met HX).
Binnen 24 uur na een bericht van de gast mag vrije tekst.

WhatsApp-nummer per hotel: config/hotels/<hotel_id>.toml, [twilio] whatsapp_from (zonder
het voorvoegsel "whatsapp:"). Twilio-account: gedeeld, zie core/config.py.
"""

from __future__ import annotations

import httpx

from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.models import Channel, SendResult
from hotel_checkin.messaging._twilio import send_message


def _wa(number: str) -> str:
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"


def send_whatsapp_template(
    hotel_id: str,
    to: str,
    template_sid: str,
    variables: dict[str, str] | None = None,
    client: httpx.Client | None = None,
    status_callback: str | None = None,
) -> SendResult:
    """Stuur een goedgekeurde template (bv. de code op D-1). Variabelen: {"1": "Jan", ...}."""
    result = send_message(
        hotel_id,
        Channel.WHATSAPP,
        to=_wa(to),
        from_=_wa(hotel_setting(hotel_id, "TWILIO_WHATSAPP_FROM")),
        content_sid=template_sid,
        content_variables=variables,
        client=client,
        status_callback=status_callback,
    )
    result.to = to
    return result


def send_whatsapp_text(
    hotel_id: str, to: str, text: str, client: httpx.Client | None = None
) -> SendResult:
    """Stuur vrije tekst. Werkt alleen binnen 24 uur na het laatste bericht van de gast."""
    result = send_message(
        hotel_id,
        Channel.WHATSAPP,
        to=_wa(to),
        from_=_wa(hotel_setting(hotel_id, "TWILIO_WHATSAPP_FROM")),
        body=text,
        client=client,
    )
    result.to = to
    return result
