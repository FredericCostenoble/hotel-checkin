"""Antwoorden van gasten op het nummer van de automatische berichten (processes/incoming.py)."""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import azure.functions as func
import pytest

from hotel_checkin.core.models import Channel, Guest, Reservation, SendResult
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import incoming

NOW = datetime(2026, 11, 11, 20, 0)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    repo.use_memory_store()
    sent = {"mail": [], "wa": [], "sms": []}
    monkeypatch.setattr("hotel_checkin.messaging.email.send_email",
                        lambda to, subject, html_body, **k: sent["mail"].append((to, subject, html_body))
                        or SendResult(Channel.EMAIL, to, True))
    monkeypatch.setattr("hotel_checkin.messaging.whatsapp.send_whatsapp_text",
                        lambda h, to, text, **k: sent["wa"].append((to, text)) or SendResult(Channel.WHATSAPP, to, True))
    monkeypatch.setattr("hotel_checkin.messaging.sms.send_sms",
                        lambda h, to, text, **k: sent["sms"].append((to, text)) or SendResult(Channel.SMS, to, True))
    monkeypatch.setattr("hotel_checkin.processes.send_messages.phone_enabled", lambda h: True)
    monkeypatch.setattr("hotel_checkin.core.clock.today", lambda h: date(2026, 11, 11))
    return sent


def test_forward_and_reply_once(setup):
    r = Reservation("lucca", "R1", Guest("Marie", "Dupont", "m@example.com", "+33612345678", "fr"),
                    date(2026, 11, 20), date(2026, 11, 22), rooms=["14"])
    repo.save_reservation(r)
    out = incoming.handle("lucca", "whatsapp", "+33612345678", "Peut-on garer la voiture ?", now=NOW)
    assert out == {"forwarded": True, "replied": True, "reservation": "R1"}
    to, subject, body = setup["mail"][0]
    assert to == "info@hotellucca.be" and "Marie Dupont" in subject and "kamer 14" in subject
    assert "garer la voiture" in body
    assert "ce numéro envoie uniquement" in setup["wa"][0][1] and "+32 478 08 30 49" in setup["wa"][0][1]
    assert [m["message_type"] for m in repo.messages_for("lucca", "R1")] == ["incoming"]
    # tweede bericht kort daarna: wel doorgestuurd, geen tweede antwoord
    out = incoming.handle("lucca", "whatsapp", "+33612345678", "Merci", now=NOW + timedelta(hours=1))
    assert out["forwarded"] and not out["replied"] and len(setup["wa"]) == 1 and len(setup["mail"]) == 2


def test_unknown_number_by_sms(setup):
    out = incoming.handle("lucca", "sms", "+491511234567", "Hallo", now=NOW)
    assert out["reservation"] == "" and out["replied"]
    assert "Diese Nummer sendet nur" in setup["sms"][0][1] and not setup["wa"]


def test_staff_gets_no_reply(setup, monkeypatch):
    from hotel_checkin.core import hotels

    orig = hotels.load_hotel
    monkeypatch.setattr(incoming, "load_hotel",
                        lambda h: orig(h) | {"kuislijst": {"whatsapp": ["0470 12 34 56"]}})
    out = incoming.handle("lucca", "whatsapp", "+32470123456", "ok", now=NOW)
    assert out["forwarded"] and not out["replied"]


def test_route_needs_twilio_signature(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import function_app as fa

    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    calls = []
    monkeypatch.setattr(incoming, "handle", lambda *a: calls.append(a))
    fn = fa.twilio_incoming.build().get_user_function()
    url = "https://x.example/api/twilio/incoming?h=lucca"
    body = b"From=whatsapp%3A%2B32470000000&Body=Hallo&NumMedia=0"
    bad = func.HttpRequest("POST", url, params={"h": "lucca"}, body=body, headers={"X-Twilio-Signature": "x"})
    assert fn(bad).status_code == 403 and not calls
    import base64
    import hashlib
    import hmac

    params = {"From": "whatsapp:+32470000000", "Body": "Hallo", "NumMedia": "0"}
    data = url + "".join(k + params[k] for k in sorted(params))
    sig = base64.b64encode(hmac.new(b"token", data.encode(), hashlib.sha1).digest()).decode()
    ok = func.HttpRequest("POST", url, params={"h": "lucca"}, body=body, headers={"X-Twilio-Signature": sig})
    res = fn(ok)
    assert res.status_code == 200 and calls == [("lucca", "whatsapp", "+32470000000", "Hallo", 0)]
