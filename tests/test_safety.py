"""Buiten productie mag geen bericht naar een echte gast vertrekken."""

import json
from urllib.parse import parse_qs

import httpx

from hotel_checkin.messaging.email import send_email
from hotel_checkin.messaging.sms import send_sms


def _client(captured):
    def handler(request):
        captured["body"] = request.content
        return httpx.Response(202 if "graph" in str(request.url) else 201, json={"sid": "SM1"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_email_redirected_in_tst(monkeypatch):
    monkeypatch.setenv("APP_ENV", "tst")
    monkeypatch.setenv("TEST_EMAIL", "test@hotellucca.be")
    captured = {}
    r = send_email("gast@example.com", "Uw verblijf", "<p>x</p>", sender="checkin@hotellucca.be",
                   client=_client(captured))
    msg = json.loads(captured["body"])["message"]
    assert r.ok
    assert msg["toRecipients"][0]["emailAddress"]["address"] == "test@hotellucca.be"
    assert msg["subject"] == "[TST voor gast@example.com] Uw verblijf"


def test_nothing_sent_without_test_address(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("TEST_EMAIL", raising=False)
    monkeypatch.delenv("KEY_VAULT_URL", raising=False)
    captured = {}
    r = send_email("gast@example.com", "x", "x", sender="checkin@hotellucca.be", client=_client(captured))
    assert not r.ok and "TEST_EMAIL" in r.error and not captured


def test_sms_redirected_in_dev(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("TEST_PHONE", "+32476000000")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "t")
    monkeypatch.setenv("TWILIO_SMS_FROM", "+4915800000000")
    captured = {}
    send_sms("+32470111111", "Hallo", client=_client(captured))
    form = {k: v[0] for k, v in parse_qs(captured["body"].decode()).items()}
    assert form["To"] == "+32476000000"
    assert form["Body"] == "[DEV voor +32470111111] Hallo"


def test_production_sends_to_guest(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prd")
    captured = {}
    send_email("gast@example.com", "x", "x", sender="checkin@hotellucca.be", client=_client(captured))
    msg = json.loads(captured["body"])["message"]
    assert msg["toRecipients"][0]["emailAddress"]["address"] == "gast@example.com"
