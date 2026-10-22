"""Bouwblok 1: WhatsApp sturen via Twilio (WhatsApp Business).

Berichten die het hotel als eerste stuurt, moeten een door Meta goedgekeurde template
gebruiken (in Twilio een Content Template met een ContentSid, beginnend met HX).
Binnen 24 uur na een bericht van de gast mag vrije tekst.

Instellingen: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM (nummer, zonder
het voorvoegsel "whatsapp:").
"""

from __future__ import annotations

import httpx

from hotel_checkin.core.config import get_setting
from hotel_checkin.core.models import Channel, SendResult
from hotel_checkin.messaging._twilio import send_message


def _wa(number: str) -> str:
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"


def send_whatsapp_template(
    to: str,
    template_sid: str,
    variables: dict[str, str] | None = None,
    client: httpx.Client | None = None,
) -> SendResult:
    """Stuur een goedgekeurde template (bv. de code op D-1). Variabelen: {"1": "Jan", ...}."""
    result = send_message(
        Channel.WHATSAPP,
        to=_wa(to),
        from_=_wa(get_setting("TWILIO_WHATSAPP_FROM")),
        content_sid=template_sid,
        content_variables=variables,
        client=client,
    )
    result.to = to
    return result


def send_whatsapp_text(to: str, text: str, client: httpx.Client | None = None) -> SendResult:
    """Stuur vrije tekst. Werkt alleen binnen 24 uur na het laatste bericht van de gast."""
    result = send_message(
        Channel.WHATSAPP,
        to=_wa(to),
        from_=_wa(get_setting("TWILIO_WHATSAPP_FROM")),
        body=text,
        client=client,
    )
    result.to = to
    return result
