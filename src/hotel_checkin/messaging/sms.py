"""Bouwblok 2: SMS sturen via Twilio.

Afzendnummer per hotel: config/hotels/<hotel_id>.toml, [twilio] sms_from.
Twilio-account: gedeeld (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), zie core/config.py.
In de proefversie van Twilio kan alleen naar geverifieerde nummers gestuurd worden.

Snel testen in de codespace:
    python -m hotel_checkin.messaging.sms +32470123456 [hotel_id]
"""

from __future__ import annotations

import sys

import httpx

from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.models import Channel, SendResult
from hotel_checkin.messaging._twilio import send_message


def send_sms(hotel_id: str, to: str, text: str, client: httpx.Client | None = None,
             status_callback: str | None = None) -> SendResult:
    """Stuur een SMS namens een hotel naar een nummer in E.164-formaat (bv. +32470123456)."""
    return send_message(
        hotel_id, Channel.SMS, to=to, from_=hotel_setting(hotel_id, "TWILIO_SMS_FROM"),
        body=text, client=client, status_callback=status_callback,
    )


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("Gebruik: python -m hotel_checkin.messaging.sms <nummer in +32-formaat> [hotel_id]")
    hotel = sys.argv[2] if len(sys.argv) == 3 else "lucca"
    result = send_sms(hotel, sys.argv[1], "Testbericht van het bouwblok SMS (hotel-checkin).")
    print(result)
    sys.exit(0 if result.ok else 1)
