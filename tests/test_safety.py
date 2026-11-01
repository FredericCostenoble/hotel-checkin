"""Buiten productie mag geen bericht naar een echte gast vertrekken."""

import json
from urllib.parse import parse_qs

import httpx
import pytest

from hotel_checkin.messaging.email import send_email
from hotel_checkin.messaging.sms import send_sms


def _client(captured):
    def handler(request):
        captured["body"] = request.content
        return httpx.Response(202 if "graph" in str(request.url) else 201, json={"sid": "SM1"})

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.fixture(autouse=True)
def hotel_test_settings(monkeypatch):
    """Testadres en testnummer van het hotel (sectie [test]), los van wat in lucca.toml staat."""
    from hotel_checkin.core import hotels

    values = {"email": "test@hotellucca.be", "phone": "+32476000000"}
    real = hotels.load_hotel

    def load(hotel_id):
        cfg = real(hotel_id)
        return {**cfg, "test": dict(values)}

    monkeypatch.setattr(hotels, "load_hotel", load)
    return values


def test_email_redirected_in_tst(monkeypatch):
    monkeypatch.setenv("APP_ENV", "tst")
    captured = {}
    r = send_email("gast@example.com", "Uw verblijf", "<p>x</p>", sender="checkin@hotellucca.be",
                   client=_client(captured), hotel_id="lucca")
    msg = json.loads(captured["body"])["message"]
    assert r.ok
    assert msg["toRecipients"][0]["emailAddress"]["address"] == "test@hotellucca.be"
    assert msg["subject"] == "[TST voor gast@example.com] Uw verblijf"


def test_nothing_sent_without_test_address(monkeypatch, hotel_test_settings):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("TEST_EMAIL", "omgeving@example.com")  # bestaat niet meer: telt niet
    hotel_test_settings["email"] = ""
    captured = {}
    r = send_email("gast@example.com", "x", "x", sender="checkin@hotellucca.be", client=_client(captured),
                   hotel_id="lucca")
    assert not r.ok and "testadres" in r.error and not captured
    r = send_email("gast@example.com", "x", "x", sender="checkin@hotellucca.be", client=_client(captured))
    assert not r.ok and not captured  # zonder hotel: nooit


def test_sms_redirected_in_dev(monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "t")
    monkeypatch.setenv("TWILIO_SMS_FROM", "+4915800000000")
    captured = {}
    send_sms("lucca", "+32470111111", "Hallo", client=_client(captured))
    form = {k: v[0] for k, v in parse_qs(captured["body"].decode()).items()}
    assert form["To"] == "+32476000000"
    assert form["Body"] == "[DEV voor +32470111111] Hallo"


def test_production_sends_to_guest(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prd")
    captured = {}
    send_email("gast@example.com", "x", "x", sender="checkin@hotellucca.be", client=_client(captured))
    msg = json.loads(captured["body"])["message"]
    assert msg["toRecipients"][0]["emailAddress"]["address"] == "gast@example.com"


def test_test_address_from_hotel_settings(monkeypatch):
    """Alleen het adres uit de instellingen van het hotel (monitor of hotelbestand), niets anders."""
    from hotel_checkin.core import hotel_settings, hotels, safety
    from hotel_checkin.guests import repository as repo

    monkeypatch.undo()  # echte load_hotel (met wijzigingen uit de monitor)
    repo.use_memory_store()
    hotels.forget_overrides()
    monkeypatch.setenv("APP_ENV", "tst")
    assert safety.route("email", "gast@example.com", "lucca")[0] == "frederic@hotellucca.be"  # hotelbestand
    hotel_settings.save("lucca", {"test": {"email": "fred@example.com"}}, "x")
    real, prefix = safety.route("email", "gast@example.com", "lucca")
    assert real == "fred@example.com" and "gast@example.com" in prefix
    hotel_settings.save("lucca", {"test": {"email": ""}}, "x")
    monkeypatch.setenv("TEST_EMAIL", "omgeving@example.com")
    assert safety.route("email", "gast@example.com", "lucca")[0] is None  # leeg = geen mails
    monkeypatch.setenv("APP_ENV", "prd")
    assert safety.route("email", "gast@example.com", "lucca")[0] == "gast@example.com"
    hotels.forget_overrides()
