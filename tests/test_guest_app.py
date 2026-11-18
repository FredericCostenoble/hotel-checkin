"""Gast-app: deuren openen (processes/guest_unlock.py), Betalen (processes/guest_payment.py) en het Salto-blok open_lock."""

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from hotel_checkin.access import salto
from hotel_checkin.core.models import Guest, Reservation
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import guest_payment, guest_unlock

TZ = ZoneInfo("Europe/Brussels")
SALTO = {"common_lock_ids": ["front"], "rooms": {"16": "lock16", "2": ["lock2door", "lock2room"]}}


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    repo.use_memory_store()
    monkeypatch.setenv("LUCCA_SCHAKELAARS_ONTGRENDELEN", "true")
    monkeypatch.setattr(salto, "load_hotel", lambda h: {"salto": SALTO}, raising=False)
    monkeypatch.setattr(salto, "configured", lambda h: True)
    monkeypatch.setenv("APP_ENV", "prd")


def _res(rooms=("16",), completed=True, paid=True, rid="r1"):
    r = Reservation("lucca", rid, Guest("Jan", "Voorbeeld"), date(2099, 1, 10), date(2099, 1, 12), rooms=list(rooms))
    r.paid = paid
    r.access_codes = [{"room": x, "pin": "1234", "user_id": "u", "group_id": "g"} for x in rooms]
    r.access_valid_from = datetime(2099, 1, 10, 14, tzinfo=TZ)
    r.access_valid_until = datetime(2099, 1, 12, 12, tzinfo=TZ)
    if completed:
        r.checkin_completed_at = datetime(2099, 1, 1, tzinfo=TZ)
    return repo.save_reservation(r)


def _opened(monkeypatch):
    opened = []
    monkeypatch.setattr(salto, "open_lock", lambda h, lock_id, client=None: opened.append(lock_id))
    return opened


def test_open_own_room_and_front_door_within_period(monkeypatch):
    opened = _opened(monkeypatch)
    r = _res()
    now = datetime(2099, 1, 10, 15, tzinfo=TZ)
    assert guest_unlock.doors("lucca", r) == ["front", "room:16"]
    assert guest_unlock.open_door("lucca", r, "front", now) == (True, "opened")
    assert guest_unlock.open_door("lucca", r, "room:16", now) == (True, "opened")
    assert opened == ["front", "lock16"]
    log = [m for m in repo.messages_for("lucca", "r1") if m["message_type"] == "app_unlock"]
    assert [m["note"] for m in log] == ["voordeur geopend via de gast-app", "kamer 16 geopend via de gast-app"]


def test_refusals(monkeypatch):
    opened = _opened(monkeypatch)
    r = _res()
    assert guest_unlock.open_door("lucca", r, "room:21", datetime(2099, 1, 10, 15, tzinfo=TZ)) == (False, "unknown_door")
    assert guest_unlock.open_door("lucca", r, "front", datetime(2099, 1, 10, 13, tzinfo=TZ)) == (False, "too_early")
    # kamer tot kamer_tot (12:00), voordeur tot het einde van de vertrekdag
    assert guest_unlock.open_door("lucca", r, "room:16", datetime(2099, 1, 12, 13, tzinfo=TZ)) == (False, "too_late")
    assert guest_unlock.open_door("lucca", r, "front", datetime(2099, 1, 12, 13, tzinfo=TZ)) == (True, "opened")
    assert opened == ["front"]
    assert guest_unlock.open_door("lucca", _res(completed=False, rid="r2"), "front", datetime(2099, 1, 10, 15, tzinfo=TZ))[1] == "not_allowed"
    assert guest_unlock.open_door("lucca", _res(paid=None, rid="r3"), "front", datetime(2099, 1, 10, 15, tzinfo=TZ))[1] == "not_allowed"
    monkeypatch.setenv("LUCCA_SCHAKELAARS_ONTGRENDELEN", "false")
    assert guest_unlock.open_door("lucca", _res(), "front", datetime(2099, 1, 10, 15, tzinfo=TZ))[1] == "not_allowed"


def test_outside_production_only_test_guests(monkeypatch):
    _opened(monkeypatch)
    monkeypatch.setenv("APP_ENV", "tst")
    now = datetime(2099, 1, 10, 15, tzinfo=TZ)
    assert guest_unlock.open_door("lucca", _res(), "front", now)[1] == "not_allowed"
    r = _res()
    r.guest = Guest("Seppe", "Meersseman")
    assert guest_unlock.open_door("lucca", r, "front", now) == (True, "opened")


def test_rate_limit_and_failure_logged(monkeypatch):
    _opened(monkeypatch)
    r = _res()
    now = datetime(2099, 1, 10, 15, tzinfo=TZ)
    monkeypatch.setattr(repo, "_now", lambda: now)
    for _ in range(guest_unlock.MAX_OPENS):
        assert guest_unlock.open_door("lucca", r, "front", now)[0]
    assert guest_unlock.open_door("lucca", r, "front", now) == (False, "too_many")
    assert guest_unlock.open_door("lucca", r, "front", now + timedelta(minutes=11))[0]

    def boom(h, lock_id, client=None):
        raise salto.SaltoError("Salto PATCH: 409 offline")
    monkeypatch.setattr(salto, "open_lock", boom)
    assert guest_unlock.open_door("lucca", r, "room:16", now + timedelta(minutes=11)) == (False, "failed")
    failed = [m for m in repo.messages_for("lucca", "r1") if not m["ok"]]
    assert len(failed) == 1 and "offline" in failed[0]["error"]


def test_own_entrance_room_has_no_front_door_tile(monkeypatch):
    from hotel_checkin.core import hotels

    real = hotels.load_hotel
    monkeypatch.setattr(hotels, "load_hotel", lambda h: {**real(h), "kamers": {"2": {"toegang_nl": "eigen ingang"}}})
    opened = _opened(monkeypatch)
    r = _res(rooms=("2",))
    assert guest_unlock.doors("lucca", r) == ["room:2"]
    assert guest_unlock.open_door("lucca", r, "room:2", datetime(2099, 1, 10, 15, tzinfo=TZ)) == (True, "opened")
    assert opened == ["lock2door", "lock2room"]


def test_salto_open_lock_call(monkeypatch):
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/connect/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        calls.append((req.method, req.url.path, json.loads(req.content)))
        return httpx.Response(200)
    settings = {"SALTO_SITE_ID": "site1", "SALTO_USERNAME": "u", "SALTO_PASSWORD": "p", "SALTO_CLIENT_ID": "c",
                "SALTO_CLIENT_SECRET": "s"}
    monkeypatch.setattr(salto, "hotel_setting", lambda h, n, default=None, required=True, shared=True: settings.get(n, default))
    salto._tokens.clear()
    salto.open_lock("lucca", "lock16", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert calls == [("PATCH", "/v1.2/sites/site1/locks/lock16/locking", {"locked_state": "unlocked"})]


def test_pay_started_requests_refresh_once(monkeypatch):
    from hotel_checkin.admin import cloud_robot
    from hotel_checkin.processes import refresh_requests

    monkeypatch.setattr(cloud_robot, "available", lambda: False)
    r = _res()
    now = datetime(2099, 1, 8, 10, tzinfo=TZ)
    assert not guest_payment.pay_started("lucca", r, now)  # niets open (betaald, saldo onbekend)
    r.open_amount = 16.8
    assert guest_payment.pay_started("lucca", r, now)
    assert refresh_requests.requested("lucca") == {"2099-01-10"}
    assert not guest_payment.pay_started("lucca", r, now + timedelta(minutes=5))  # net gevraagd
    assert guest_payment.pay_started("lucca", r, now + timedelta(minutes=11))
    assert [m["message_type"] for m in repo.messages_for("lucca", "r1")] == ["app_pay", "app_pay"]
