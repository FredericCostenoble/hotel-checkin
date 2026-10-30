"""Bouwblok Salto (nagebootste API) en proces grant_access: per boeking gebruiker, access group,
deuren, periode, pincode; opruimen bij een fout en na vertrek."""

import json
from datetime import date, datetime, timedelta

import httpx
import pytest

from hotel_checkin.access import salto
from hotel_checkin.core.models import Guest, Reservation, ReservationStatus
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import grant_access

SETTINGS = {"SALTO_SITE_ID": "site1", "SALTO_USERNAME": "robot@hotel", "SALTO_PASSWORD": "pw",
            "SALTO_CLIENT_ID": "cid", "SALTO_CLIENT_SECRET": "sec", "SALTO_GUEST_ROLE_ID": "role-guest"}


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    repo.use_memory_store()
    salto._tokens.clear()
    monkeypatch.setattr(salto, "hotel_setting", lambda h, n, default=None, required=True, shared=True: SETTINGS.get(n, default))
    monkeypatch.setattr(salto, "load_hotel", lambda h: {"salto": {"common_lock_ids": ["front"], "rooms": {"12": "lock12", "14": ["lock14a", "lock14b"]}}}, raising=False)


def fake_api(calls, fail_on=None):
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        calls.append((req.method, path, json.loads(req.content) if req.content and req.method != "POST" or (req.content and not path.endswith("/token")) else None))
        if path.endswith("/connect/token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert req.headers["Authorization"] == "Bearer tok"
        if fail_on and fail_on in path and req.method == "POST":
            return httpx.Response(400, json={"error": "nope"})
        if req.method == "POST" and path.endswith("/users") and "/access_groups/" not in path:
            return httpx.Response(200, json={"id": "user1"})
        if req.method == "POST" and path.endswith("/access_groups"):
            return httpx.Response(200, json={"id": "group1"})
        if req.method == "PUT" and path.endswith("/pin"):
            return httpx.Response(200, json="482916")
        return httpx.Response(200, json={})
    return httpx.Client(transport=httpx.MockTransport(handler))


def _res(rooms=("12",)):
    r = Reservation("lucca", "r1", Guest("Jan", "Voorbeeld"), date(2099, 1, 10), date(2099, 1, 12),
                    rooms=list(rooms), booking_number="CPB-1")
    return repo.save_reservation(r)


def test_lock_ids_for_rooms():
    assert salto.lock_ids_for("lucca", ["12", "14"]) == ["front", "lock12", "lock14a", "lock14b"]
    with pytest.raises(salto.SaltoError, match="99"):
        salto.lock_ids_for("lucca", ["99"])


def test_grant_full_sequence(monkeypatch):
    calls = []
    client = fake_api(calls)
    for name in ("create_user", "create_access_group", "add_locks", "add_time_schedule", "add_user_to_group", "create_pin",
                 "delete_user", "delete_access_group"):
        fn = getattr(salto, name)
        monkeypatch.setattr(grant_access.salto, name, lambda *a, _fn=fn, **k: _fn(*a, client=client, **k))
    r = _res()
    pin = grant_access.grant("lucca", r)
    assert pin == "482916"
    paths = [(m, p.replace("/v1.2/sites/site1", "").replace("/v1.1/sites/site1", "")) for m, p, _ in calls if not p.endswith("token")]
    assert paths == [("POST", "/users"), ("POST", "/access_groups"), ("POST", "/access_groups/group1/locks"),
                     ("POST", "/access_groups/group1/locks"), ("POST", "/access_groups/group1/time_schedules"),
                     ("POST", "/access_groups/group1/users"), ("PUT", "/users/user1/pin")]
    schedule = next(b for m, p, b in calls if p.endswith("time_schedules"))
    assert schedule["start_date"] == "2099-01-10T14:00:00" and schedule["end_date"] == "2099-01-12T11:00:00"
    saved = repo.get_reservation("lucca", "r1")
    assert (saved.access_pin, saved.salto_user_id, saved.salto_group_id) == ("482916", "user1", "group1")
    assert grant_access.grant("lucca", saved) == "482916" and len(calls) == len([c for c in calls])  # geen nieuwe oproepen


def test_grant_cleans_up_on_failure(monkeypatch):
    calls = []
    client = fake_api(calls, fail_on="time_schedules")
    for name in ("create_user", "create_access_group", "add_locks", "add_time_schedule", "add_user_to_group", "create_pin",
                 "delete_user", "delete_access_group"):
        fn = getattr(salto, name)
        monkeypatch.setattr(grant_access.salto, name, lambda *a, _fn=fn, **k: _fn(*a, client=client, **k))
    with pytest.raises(salto.SaltoError):
        grant_access.grant("lucca", _res())
    deletes = [p for m, p, _ in calls if m == "DELETE"]
    assert any(p.endswith("/access_groups/group1") for p in deletes) and any(p.endswith("/users/user1") for p in deletes)
    assert repo.get_reservation("lucca", "r1").access_pin is None


def test_no_room_no_access():
    with pytest.raises(salto.SaltoError, match="kamer"):
        grant_access.grant("lucca", _res(rooms=()))


def test_code_mail_sends_pin(monkeypatch):
    from hotel_checkin.core.models import Channel, SendResult
    from hotel_checkin.processes import send_messages

    monkeypatch.setenv("APP_ENV", "tst")
    monkeypatch.setattr(send_messages, "start", lambda h: datetime(2000, 1, 1).astimezone())
    monkeypatch.setattr(salto, "configured", lambda h: True)
    sent = []
    monkeypatch.setattr(send_messages.email, "send_email",
                        lambda to, subject, html_body, **k: sent.append(html_body) or SendResult(Channel.EMAIL, to, True))

    def fake_grant(h, r):
        r.access_pin, r.salto_user_id = "482916", "user1"
        r.access_valid_from = datetime(2099, 1, 1, 14, 0)
        r.access_valid_until = datetime(2099, 1, 3, 11, 0)
        repo.save_reservation(r)
        return "482916"
    monkeypatch.setattr(grant_access, "grant", fake_grant)
    arrival = date.today() + timedelta(days=2)
    r = Reservation("lucca", "c1", Guest("Jan", "Voorbeeld", email="jan@example.com", language="nl"), arrival,
                    arrival + timedelta(days=2), rooms=["12"], source="Booking.com", booking_number="CPB-9")
    repo.save_reservation(r)
    assert send_messages.run("lucca") == 1
    assert "482916" in sent[0] and "1 januari, 14:00" in sent[0]
    assert repo.was_sent("lucca", "c1", "access_code", "email")


def test_maintenance_revokes_after_departure(monkeypatch):
    from hotel_checkin.processes import maintenance

    revoked = []
    monkeypatch.setattr(grant_access, "_cleanup", lambda h, u, g: revoked.append((u, g)))
    r = Reservation("lucca", "d1", Guest("A", "B"), date.today() - timedelta(days=3), date.today() - timedelta(days=1),
                    salto_user_id="u", salto_group_id="g", access_pin="1")
    repo.save_reservation(r)
    c = Reservation("lucca", "d2", Guest("C", "D"), date.today() + timedelta(days=9), date.today() + timedelta(days=10),
                    status=ReservationStatus.CANCELLED, salto_user_id="u2", salto_group_id="g2")
    repo.save_reservation(c)
    assert maintenance.run("lucca")["access_revoked"] == 2
    assert sorted(revoked) == [("u", "g"), ("u2", "g2")]
    assert repo.get_reservation("lucca", "d1").access_pin is None
