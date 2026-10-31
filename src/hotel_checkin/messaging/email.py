"""Bouwblok 3: mail sturen via Microsoft Graph vanuit de eigen M365-mailbox.

Opzet in de Hotel Lucca-omgeving:
- Entra app registration `hotel-checkin` (client ID 8f92b706-81a1-443c-9ac9-6806bb2d481c).
- GEEN Graph API-permissie Mail.Send in Entra (die zou voor alle mailboxen gelden).
- Exchange RBAC for Applications: rol "Application Mail.Send" met scope
  `hotel-checkin-mailbox`, die alleen checkin@hotellucca.be bevat.

Aanmelden gebeurt via azure-identity (DefaultAzureCredential). In de codespace leest die
AZURE_TENANT_ID, AZURE_CLIENT_ID en AZURE_CLIENT_SECRET uit de Codespaces-secrets.

Snel testen in de codespace:
    python -m hotel_checkin.messaging.email jouw@adres.be
"""

from __future__ import annotations

import base64
import sys

import httpx

from hotel_checkin.core.config import get_setting
from hotel_checkin.core.models import Channel, SendResult
from hotel_checkin.core.safety import route

GRAPH_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"


def _get_token() -> str:
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential().get_token(GRAPH_SCOPE).token


def send_email(
    to: str,
    subject: str,
    html_body: str,
    attachments: list[tuple[str, bytes]] | None = None,
    sender: str | None = None,
    client: httpx.Client | None = None,
    reply_to: str | None = None,
    hotel_id: str | None = None,
) -> SendResult:
    """Stuur een mail. Geeft altijd een SendResult terug, gooit geen fout bij een mislukte verzending.

    attachments: lijst van (bestandsnaam, inhoud).
    sender: standaard de instelling MAIL_SENDER (checkin@hotellucca.be, puur technisch).
    reply_to: waar antwoorden van de gast naartoe gaan, normaal het contactadres van het hotel
              (config/hotels/<hotel_id>.toml, [hotel] email).
    Buiten productie gaat de mail naar het testadres (core/safety.py): dat van het hotel als
    hotel_id gegeven is (instellingen, sectie [test]), anders TEST_EMAIL van de omgeving.
    client: alleen voor tests, om de HTTP-aanroep te vervangen.
    """
    sender = sender or get_setting("MAIL_SENDER")
    real_to, prefix = route("email", to, hotel_id)
    if real_to is None:
        return SendResult(channel=Channel.EMAIL, to=to, ok=False, error=prefix)
    message: dict = {
        "subject": prefix + subject,
        "body": {"contentType": "HTML", "content": html_body},
        "toRecipients": [{"emailAddress": {"address": real_to}}],
    }
    if reply_to and reply_to.lower() != sender.lower():
        message["replyTo"] = [{"emailAddress": {"address": reply_to}}]
    if attachments:
        message["attachments"] = [
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name,
                "contentBytes": base64.b64encode(content).decode("ascii"),
            }
            for name, content in attachments
        ]

    try:
        http = client or httpx.Client(timeout=30)
        response = http.post(
            f"{GRAPH_URL}/users/{sender}/sendMail",
            headers={"Authorization": f"Bearer {_get_token() if client is None else 'test'}"},
            json={"message": message, "saveToSentItems": True},
        )
    except Exception as exc:  # noqa: BLE001 - netwerk- of aanmeldfout
        return SendResult(channel=Channel.EMAIL, to=to, ok=False, error=str(exc))

    if response.status_code == 202:
        return SendResult(
            channel=Channel.EMAIL,
            to=to,
            ok=True,
            provider_id=response.headers.get("request-id"),
        )
    return SendResult(
        channel=Channel.EMAIL,
        to=to,
        ok=False,
        error=f"Graph {response.status_code}: {response.text[:500]}",
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Gebruik: python -m hotel_checkin.messaging.email <ontvanger>")
    result = send_email(
        to=sys.argv[1],
        subject="Testmail hotel-checkin",
        html_body="<p>Dit is een testmail van het bouwblok mail.</p>",
    )
    print(result)
    sys.exit(0 if result.ok else 1)
