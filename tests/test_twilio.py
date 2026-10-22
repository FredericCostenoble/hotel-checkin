"""Tests voor de bouwblokken SMS en WhatsApp, zonder echte Twilio-aanroep."""

import json
from urllib.parse import parse_qs

import httpx
import pytest

from hotel_checkin.messaging.sms import send_sms
from hotel_checkin.messaging.whatsapp import send_whatsapp_template, send_whatsapp_text


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_SMS_FROM", "+4915800000000")
    monkeypatch.setenv("TWILIO_WHATSAPP_FROM", "+14155238886")


def _client(status: int, captured: dict, payload: dict | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["form"] = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        return httpx.Response(status, json=payload or {"sid": "SM123"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sms_ok():
    captured: dict = {}
    result = send_sms("+32470000000", "Hallo", client=_client(201, captured))
    assert result.ok and result.provider_id == "SM123"
    assert captured["url"].endswith("/Accounts/ACtest/Messages.json")
    assert captured["form"] == {"To": "+32470000000", "From": "+4915800000000", "Body": "Hallo"}


def test_sms_error_is_returned_not_raised():
    result = send_sms(
        "+32470000000",
        "Hallo",
        client=_client(400, {}, {"code": 21608, "message": "unverified number"}),
    )
    assert not result.ok and "21608" in result.error


def test_whatsapp_template():
    captured: dict = {}
    result = send_whatsapp_template(
        "+32470000000", "HXabc", {"1": "Jan"}, client=_client(201, captured)
    )
    assert result.ok and result.to == "+32470000000"
    form = captured["form"]
    assert form["To"] == "whatsapp:+32470000000"
    assert form["From"] == "whatsapp:+14155238886"
    assert form["ContentSid"] == "HXabc"
    assert json.loads(form["ContentVariables"]) == {"1": "Jan"}


def test_whatsapp_text():
    captured: dict = {}
    send_whatsapp_text("+32470000000", "Hoi", client=_client(201, captured))
    assert captured["form"]["Body"] == "Hoi"
