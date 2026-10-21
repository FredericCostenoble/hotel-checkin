"""Bouwblok 3: mail sturen via Microsoft Graph vanuit de eigen M365-mailbox.

Vereist een Entra app registration met applicatierechten Mail.Send, beperkt tot de
afzendermailbox via een Exchange Application Access Policy (of RBAC for Applications).
"""

from __future__ import annotations

from hotel_checkin.core.models import Channel, SendResult


def send_email(
    to: str,
    subject: str,
    html_body: str,
    attachments: list[tuple[str, bytes]] | None = None,
) -> SendResult:
    """Stuur een mail. Geeft altijd een SendResult terug, gooit geen fout bij een mislukte verzending."""
    raise NotImplementedError("Bouwblok mail: nog te implementeren (Graph sendMail)")


__all__ = ["send_email", "Channel"]
