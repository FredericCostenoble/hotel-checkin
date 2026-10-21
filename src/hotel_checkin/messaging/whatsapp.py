"""Bouwblok 1: WhatsApp sturen via Twilio (WhatsApp Business).

Berichten die het hotel als eerste stuurt, moeten een door Meta goedgekeurde template
gebruiken. Binnen 24 uur na een bericht van de gast mag vrije tekst.
"""

from __future__ import annotations

from hotel_checkin.core.models import SendResult


def send_whatsapp_template(to: str, template_sid: str, variables: dict[str, str]) -> SendResult:
    """Stuur een goedgekeurde template (bv. de code-mail van D-1)."""
    raise NotImplementedError("Bouwblok WhatsApp (template): nog te implementeren")


def send_whatsapp_text(to: str, text: str) -> SendResult:
    """Stuur vrije tekst. Werkt alleen binnen 24 uur na het laatste bericht van de gast."""
    raise NotImplementedError("Bouwblok WhatsApp (vrije tekst): nog te implementeren")
