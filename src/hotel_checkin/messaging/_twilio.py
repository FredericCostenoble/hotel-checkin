"""Gedeelde Twilio-aanroep voor de bouwblokken SMS en WhatsApp (intern, niet rechtstreeks gebruiken).

Gebruikt de Twilio Messages REST API met httpx, zonder de Twilio-SDK.
Instellingen: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN.
"""

from __future__ import annotations

import json

import httpx

from hotel_checkin.core.config import get_setting
from hotel_checkin.core.models import Channel, SendResult
from hotel_checkin.core.safety import route

TWILIO_API = "https://api.twilio.com/2010-04-01"


def send_message(
    channel: Channel,
    to: str,
    from_: str,
    body: str | None = None,
    content_sid: str | None = None,
    content_variables: dict[str, str] | None = None,
    client: httpx.Client | None = None,
) -> SendResult:
    """Verstuur via Twilio. Ofwel `body` (vrije tekst), ofwel `content_sid` (sjabloon)."""
    if (body is None) == (content_sid is None):
        raise ValueError("Geef ofwel body, ofwel content_sid op")

    whatsapp = to.startswith("whatsapp:")
    real_to, prefix = route("phone", to.removeprefix("whatsapp:"))
    if real_to is None:
        return SendResult(channel=channel, to=to, ok=False, error=prefix)
    to = f"whatsapp:{real_to}" if whatsapp else real_to
    if prefix and body is not None:
        body = prefix + body

    account_sid = get_setting("TWILIO_ACCOUNT_SID")
    auth_token = get_setting("TWILIO_AUTH_TOKEN")

    data: dict[str, str] = {"To": to, "From": from_}
    if body is not None:
        data["Body"] = body
    else:
        data["ContentSid"] = content_sid  # type: ignore[assignment]
        if content_variables:
            data["ContentVariables"] = json.dumps(content_variables)

    try:
        http = client or httpx.Client(timeout=30)
        response = http.post(
            f"{TWILIO_API}/Accounts/{account_sid}/Messages.json",
            data=data,
            auth=(account_sid, auth_token),
        )
    except Exception as exc:  # noqa: BLE001 - netwerkfout
        return SendResult(channel=channel, to=to, ok=False, error=str(exc))

    if response.status_code in (200, 201):
        return SendResult(channel=channel, to=to, ok=True, provider_id=response.json().get("sid"))
    try:
        detail = response.json()
        error = f"Twilio {response.status_code}, code {detail.get('code')}: {detail.get('message')}"
    except ValueError:
        error = f"Twilio {response.status_code}: {response.text[:500]}"
    return SendResult(channel=channel, to=to, ok=False, error=error)
