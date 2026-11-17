"""Doorschakelen van oproepen op het Twilio-nummer (processes/call_forward.py)."""

import base64
import hashlib
import hmac
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import azure.functions as func

from hotel_checkin.messaging import voice
from hotel_checkin.processes import call_forward

TZ = ZoneInfo("Europe/Brussels")
HOTEL, NIGHT = "+32 478 08 30 49", "+32 471 18 15 74"


def at(h, m=0):
    return datetime(2026, 11, 17, h, m, tzinfo=TZ)


def test_day_to_hotel_evening_to_emergency_number():
    for t, expect in ((at(8), HOTEL), (at(12), HOTEL), (at(18, 29), HOTEL), (at(18, 30), NIGHT), (at(23), NIGHT),
                      (at(3), NIGHT), (at(7, 59), NIGHT)):
        assert call_forward.number("lucca", t) == expect, t


def test_empty_window_always_hotel(monkeypatch):
    from hotel_checkin.core import hotels

    orig = hotels.load_hotel
    monkeypatch.setattr(call_forward, "load_hotel", lambda h: orig(h) | {"doorschakelen": {"avond_van": ""}})
    assert call_forward.number("lucca", at(23)) == HOTEL


def test_twiml():
    assert voice.forward_twiml("+32 478 08 30 49") == (
        '<?xml version="1.0" encoding="UTF-8"?><Response><Dial timeout="30">+32478083049</Dial></Response>')


def test_route_needs_twilio_signature(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import function_app as fa

    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setattr(call_forward, "number", lambda h: NIGHT)
    fn = fa.twilio_voice.build().get_user_function()
    url = "https://x.example/api/twilio/voice?h=lucca"
    params = {"From": "+32470000000", "To": "+32460250399"}
    body = b"From=%2B32470000000&To=%2B32460250399"
    bad = func.HttpRequest("POST", url, params={"h": "lucca"}, body=body, headers={"X-Twilio-Signature": "x"})
    assert fn(bad).status_code == 403
    data = url + "".join(k + params[k] for k in sorted(params))
    sig = base64.b64encode(hmac.new(b"token", data.encode(), hashlib.sha1).digest()).decode()
    ok = func.HttpRequest("POST", url, params={"h": "lucca"}, body=body, headers={"X-Twilio-Signature": sig})
    res = fn(ok)
    assert res.status_code == 200 and b"+32471181574" in res.get_body()
