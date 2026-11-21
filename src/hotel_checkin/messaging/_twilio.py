"""Gedeelde Twilio-aanroep voor de bouwblokken SMS en WhatsApp (intern, niet rechtstreeks gebruiken).

Gebruikt de Twilio Messages REST API met httpx, zonder de Twilio-SDK.
Instellingen per hotel (core/config.py, hotel_setting): TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN.
Normaal gedeeld door alle hotels; een hotel kan een eigen account krijgen via <hotel>-twilio-...
"""

from __future__ import annotations

import json

import httpx

from hotel_checkin.core import clients
from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.models import Channel, SendResult
from hotel_checkin.core.safety import route

TWILIO_API = "https://api.twilio.com/2010-04-01"


def send_message(
    hotel_id: str,
    channel: Channel,
    to: str,
    from_: str,
    body: str | None = None,
    content_sid: str | None = None,
    content_variables: dict[str, str] | None = None,
    client: httpx.Client | None = None,
    status_callback: str | None = None,
) -> SendResult:
    """Verstuur via Twilio. Ofwel `body` (vrije tekst), ofwel `content_sid` (sjabloon).
    status_callback: adres dat Twilio oproept als het bericht afgeleverd of mislukt is."""
    if (body is None) == (content_sid is None):
        raise ValueError("Geef ofwel body, ofwel content_sid op")

    whatsapp = to.startswith("whatsapp:")
    guest = to.removeprefix("whatsapp:")  # in het log: het nummer van de gast (zo weet deliver() wat al lukte)
    real_to, prefix = route("phone", guest, hotel_id)
    if real_to is None:
        return SendResult(channel=channel, to=guest, ok=False, error=prefix)
    to = f"whatsapp:{real_to}" if whatsapp else real_to
    if prefix and body is not None:
        body = prefix + body

    account_sid = hotel_setting(hotel_id, "TWILIO_ACCOUNT_SID")
    auth_token = hotel_setting(hotel_id, "TWILIO_AUTH_TOKEN")

    data: dict[str, str] = {"To": to, "From": from_}
    if status_callback:
        data["StatusCallback"] = status_callback
    if body is not None:
        data["Body"] = body
    else:
        data["ContentSid"] = content_sid  # type: ignore[assignment]
        if content_variables:
            data["ContentVariables"] = json.dumps(content_variables)

    try:
        http = client or clients.http()
        response = http.post(
            f"{TWILIO_API}/Accounts/{account_sid}/Messages.json",
            data=data,
            auth=(account_sid, auth_token),
        )
    except Exception as exc:  # noqa: BLE001 - netwerkfout
        return SendResult(channel=channel, to=guest, ok=False, error=str(exc), delivered_to=real_to)

    if response.status_code in (200, 201):
        return SendResult(channel=channel, to=guest, ok=True, provider_id=response.json().get("sid"), delivered_to=real_to)
    try:
        detail = response.json()
        error = f"Twilio {response.status_code}, code {detail.get('code')}: {detail.get('message')}"
    except ValueError:
        error = f"Twilio {response.status_code}: {response.text[:500]}"
    return SendResult(channel=channel, to=guest, ok=False, error=error, delivered_to=real_to)


def public_urls(url: str, headers: dict[str, str] | None = None) -> list[str]:
    """Mogelijke adressen zoals Twilio ze ondertekende. Achter Azure (eigen domein, proxy) ziet de Function App
    soms een ander adres dan Twilio: intern http, een andere host of een poort. Het pad en de query blijven."""
    from urllib.parse import urlsplit, urlunsplit

    h = {k.lower(): v for k, v in (headers or {}).items()}
    parts = urlsplit(url)
    hosts = [parts.netloc]
    for name in ("x-forwarded-host", "x-original-host", "disguised-host", "host"):
        for value in (h.get(name) or "").split(","):
            if value.strip():
                hosts.append(value.strip())
    out: list[str] = []
    for host in hosts:
        for netloc in (host, host.split(":")[0]):
            for scheme in (parts.scheme, "https"):
                candidate = urlunsplit((scheme, netloc, parts.path, parts.query, ""))
                if candidate not in out:
                    out.append(candidate)
    return out


def valid_signature(hotel_id: str, url: str | list[str], params: dict[str, str], signature: str) -> bool:
    """Komt een oproep echt van Twilio? (X-Twilio-Signature: HMAC-SHA1 van adres + parameters).
    url mag een lijst zijn (public_urls): geldig als één ervan klopt."""
    import base64
    import hashlib
    import hmac
    import logging

    token = hotel_setting(hotel_id, "TWILIO_AUTH_TOKEN", required=False) or ""
    if not token:
        logging.warning("Twilio-handtekening: geen TWILIO_AUTH_TOKEN voor %s", hotel_id)
        return False
    urls = [url] if isinstance(url, str) else list(url)
    tail = "".join(k + params[k] for k in sorted(params))
    for u in urls:
        expected = base64.b64encode(hmac.new(token.encode(), (u + tail).encode(), hashlib.sha1).digest()).decode()
        if hmac.compare_digest(expected, signature or ""):
            return True
    logging.warning("Twilio-handtekening ongeldig voor %s; geprobeerd: %s", hotel_id, ", ".join(urls))
    return False
