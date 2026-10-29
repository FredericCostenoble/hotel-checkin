"""Volgorde van instellingen per hotel: eigen geheim, dan hotelbestand, dan gedeeld."""

import pytest

from hotel_checkin.core.config import hotel_setting


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("KEY_VAULT_URL", raising=False)
    for name in ("TWILIO_SMS_FROM", "LUCCA_TWILIO_SMS_FROM", "TWILIO_AUTH_TOKEN",
                 "LUCCA_TWILIO_AUTH_TOKEN", "LIGHTHOUSE_PASSWORD", "LUCCA_LIGHTHOUSE_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


def test_hotel_file_before_shared(monkeypatch):
    monkeypatch.setenv("TWILIO_SMS_FROM", "+111")
    assert hotel_setting("lucca", "TWILIO_SMS_FROM") == "+4915888620339"


def test_own_secret_before_hotel_file(monkeypatch):
    monkeypatch.setenv("LUCCA_TWILIO_SMS_FROM", "+222")
    assert hotel_setting("lucca", "TWILIO_SMS_FROM") == "+222"


def test_shared_when_hotel_has_nothing(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "gedeeld")
    assert hotel_setting("lucca", "TWILIO_AUTH_TOKEN") == "gedeeld"
    monkeypatch.setenv("LUCCA_TWILIO_AUTH_TOKEN", "eigen")
    assert hotel_setting("lucca", "TWILIO_AUTH_TOKEN") == "eigen"


def test_hotel_only_never_uses_shared(monkeypatch):
    monkeypatch.setenv("LIGHTHOUSE_PASSWORD", "van-een-ander")
    with pytest.raises(KeyError):
        hotel_setting("lucca", "LIGHTHOUSE_PASSWORD", shared=False)
    monkeypatch.setenv("LUCCA_LIGHTHOUSE_PASSWORD", "x")
    assert hotel_setting("lucca", "LIGHTHOUSE_PASSWORD", shared=False) == "x"
