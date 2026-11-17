"""Bouwblok spraak (Twilio): het antwoord op een binnenkomende oproep op het Twilio-nummer.

Doet één ding: TwiML maken die de oproep doorschakelt naar een nummer. Welk nummer, beslist het proces
(processes/call_forward.py).
"""

from __future__ import annotations

from xml.sax.saxutils import escape


def forward_twiml(number: str, timeout_seconds: int = 30) -> str:
    """TwiML: de oproep doorschakelen naar dit nummer (de beller ziet geen verschil)."""
    digits = "".join(c for c in number if c.isdigit() or c == "+")
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<Response><Dial timeout="{int(timeout_seconds)}">{escape(digits)}</Dial></Response>')
