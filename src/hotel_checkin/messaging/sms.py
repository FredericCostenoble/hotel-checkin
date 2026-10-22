"""Bouwblok 2: SMS sturen via Twilio.

Instellingen: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_SMS_FROM.
In de proefversie van Twilio kan alleen naar geverifieerde nummers gestuurd worden.

Snel testen in de codespace:
    python -m hotel_checkin.messaging.sms +32470123456
"""

from __future__ import annotations

import sys

import httpx

from hotel_checkin.core.config import get_setting
from hotel_checkin.core.models import Channel, SendResult
from hotel_checkin.messaging._twilio import send_message


def send_sms(to: str, text: str, client: httpx.Client | None = None) -> SendResult:
    """Stuur een SMS naar een nummer in E.164-formaat (bv. +32470123456)."""
    return send_message(
        Channel.SMS, to=to, from_=get_setting("TWILIO_SMS_FROM"), body=text, client=client
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Gebruik: python -m hotel_checkin.messaging.sms <nummer in +32-formaat>")
    result = send_sms(sys.argv[1], "Testbericht van het bouwblok SMS (hotel-checkin).")
    print(result)
    sys.exit(0 if result.ok else 1)
