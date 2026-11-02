"""Bouwblok: de mail "Betaal uw openstaande saldo" van Lighthouse herkennen. Alleen tekst omzetten.

De robot maakt in Lighthouse een betaalverzoek met als ontvanger checkin@ van het hotel (de gast
krijgt die mail niet). In de mail staan het reservatienummer en de betaallink:

    Als de knop in deze e-mail niet zichtbaar is, kopieer dan de volgende URL ...
    https://reservationmanager.mylighthouse.com/visitor/payment/99831d8b-4faa-4c66-b354-e431bb8e22ef
    Reserveringsnummer
    CPB-4276-002755

De betaallink zetten we in onze eigen mail aan de gast (betaalknop).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LINK = re.compile(r"https://[a-z0-9.-]*mylighthouse\.com/visitor/payment/[0-9a-f-]{36}", re.IGNORECASE)
_NUMBER = re.compile(r"[A-Z]{2,5}-\d{3,}-\d{3,}")
_AMOUNT = re.compile(r"Outstanding balance\s*(?:\d+\s*)?€\s*([\d.]+,\d{2})|Totaal\s*€\s*([\d.]+,\d{2})", re.IGNORECASE)


@dataclass
class PaymentRequestMail:
    booking_number: str
    link: str
    amount: float | None = None


def parse_payment_mail(subject: str, text: str) -> PaymentRequestMail | None:
    """Betaalverzoek van Lighthouse naar PaymentRequestMail, of None als het er geen is."""
    link = _LINK.search(text or "")
    number = re.search(r"Reserveringsnummer\s*:?\s*(" + _NUMBER.pattern + ")", text or "") or _NUMBER.search(
        f"{subject}\n{text}")
    if not link or not number:
        return None
    m = _AMOUNT.search(text)
    amount = float((m.group(1) or m.group(2)).replace(".", "").replace(",", ".")) if m else None
    return PaymentRequestMail(booking_number=number.group(1) if number.lastindex else number.group(0),
                              link=link.group(0), amount=amount)
