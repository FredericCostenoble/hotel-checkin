"""Bouwblok 2: SMS sturen via Twilio."""

from __future__ import annotations

from hotel_checkin.core.models import SendResult


def send_sms(to: str, text: str) -> SendResult:
    """Stuur een SMS naar een nummer in E.164-formaat (bv. +32470123456)."""
    raise NotImplementedError("Bouwblok SMS: nog te implementeren (Twilio Messages API)")
