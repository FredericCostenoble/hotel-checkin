"""Bouwblok Salto (nagebootste API) en proces grant_access: per boeking gebruiker, access group,
deuren, periode, pincode; opruimen bij een fout en na vertrek."""

import json
from datetime import UTC, date, datetime, timedelta

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
    monkeypatch.setenv("LUCCA_SCHAKELAARS_BERICHTEN", "true")  # hoofdschakelaar berichten aan
    salto._tokens.clear()
    monkeypatch.setattr(salto, "hotel_setting", lambda h, n, default=None, required=True, shared=True: SETTINGS.get(n, default))
    monkeypatch.setattr(salto, "load_hotel", lambda h: {"salto": {"common_lock_ids": ["front"], "rooms": {"12": "lock12", "14": ["lock14a", "lock14b"]}}}, raising=False)
    # Standaard: Salto kiest de code en geen telling van gebruikers (apart getest hieronder)
    monkeypatch.setattr(grant_access, "pin_length", lambda h: None)
    monkeypatch.setattr(grant_access, "max_users", lambda h: None)


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
    codes = grant_access.grant("lucca", r)
    assert [c["pin"] for c in codes] == ["482916"]
    paths = [(m, p.replace("/v1.2/sites/site1", "").replace("/v1.1/sites/site1", "")) for m, p, _ in calls if not p.endswith("token")]
    # kamerdeur (tot 12:00) en voordeur (tot het einde van de vertrekdag) in twee access groups, één code
    assert paths == [("POST", "/users"), ("POST", "/access_groups"), ("POST", "/access_groups/group1/locks"),
                     ("POST", "/access_groups/group1/time_schedules"), ("POST", "/access_groups/group1/users"),
                     ("POST", "/access_groups"), ("POST", "/access_groups/group1/locks"),
                     ("POST", "/access_groups/group1/time_schedules"), ("POST", "/access_groups/group1/users"),
                     ("PUT", "/users/user1/pin")]
    locks = [b["lock_id"] for m, p, b in calls if p.endswith("/locks")]
    assert locks == ["lock12", "front"]
    room, front = [b for m, p, b in calls if p.endswith("time_schedules")]
    assert room["start_date"] == "2099-01-10T14:00:00" and room["end_date"] == "2099-01-12T12:00:00"
    assert front["end_date"] == "2099-01-12T23:59:00"
    pin_body = next(b for m, p, b in calls if p.endswith("/pin"))
    assert pin_body["expiry_date"] == "2099-01-12T23:59:00"
    saved = repo.get_reservation("lucca", "r1")
    assert saved.access_codes[0]["pin"] == "482916" and saved.access_codes[0]["front_group_id"] == "group1"
    before = len(calls)
    assert grant_access.grant("lucca", saved)[0]["pin"] == "482916" and len(calls) == before  # geen nieuwe oproepen


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
        r.access_codes = [{"room": "12", "pin": "482916", "user_id": "user1", "group_id": "g1", "schedule_id": None}]
        r.access_valid_from = datetime(2099, 1, 1, 14, 0)
        r.access_valid_until = datetime(2099, 1, 3, 11, 0)
        repo.save_reservation(r)
        return r.access_codes
    monkeypatch.setattr(grant_access, "grant", fake_grant)
    arrival = date.today() + timedelta(days=2)
    r = Reservation("lucca", "c1", Guest("Jan", "Voorbeeld", email="jan@example.com", language="nl"), arrival,
                    arrival + timedelta(days=2), rooms=["12"], source="Booking.com", booking_number="CPB-9", paid=True)
    repo.save_reservation(r)
    assert send_messages.run("lucca") == 1
    assert "482916" in sent[0] and "1 januari, 14:00" in sent[0]
    assert repo.was_sent("lucca", "c1", "access_code", "email")


def test_maintenance_revokes_after_departure(monkeypatch):
    from hotel_checkin.processes import maintenance

    revoked = []
    monkeypatch.setattr(grant_access, "_cleanup", lambda h, u, g, f=None: revoked.append((u, g)))
    r = Reservation("lucca", "d1", Guest("A", "B"), date.today() - timedelta(days=3), date.today() - timedelta(days=1),
                    access_codes=[{"room": "12", "pin": "1", "user_id": "u", "group_id": "g"}])
    repo.save_reservation(r)
    c = Reservation("lucca", "d2", Guest("C", "D"), date.today() + timedelta(days=9), date.today() + timedelta(days=10),
                    status=ReservationStatus.CANCELLED, access_codes=[{"room": "14", "pin": "2", "user_id": "u2", "group_id": "g2"}])
    repo.save_reservation(c)
    assert maintenance.run("lucca")["access_revoked"] == 2
    assert sorted(revoked) == [("u", "g"), ("u2", "g2")]
    assert repo.get_reservation("lucca", "d1").access_pin is None


def test_room_change_keeps_user_and_pin(monkeypatch):
    calls = []
    monkeypatch.setattr(grant_access.salto, "change_locks", lambda h, g, add, remove: calls.append(("locks", g, add, remove)))
    monkeypatch.setattr(grant_access.salto, "update_time_schedule", lambda h, g, s, a, b: calls.append(("schedule", s, a, b)))
    r = _res(rooms=("12",))
    r.access_codes = [{"room": "12", "pin": "482916", "user_id": "u", "group_id": "g", "schedule_id": "s"}]
    r.access_valid_from, r.access_valid_until = grant_access.period("lucca", r)
    repo.save_reservation(r)
    r.rooms = ["14"]
    assert grant_access.follow_changes("lucca", r) == ["kamer 12 naar 14"]
    assert calls == [("locks", "g", ["lock14a", "lock14b"], ["lock12"])]
    r.departure = r.departure + timedelta(days=1)  # verblijf verlengd
    assert grant_access.follow_changes("lucca", r)[0].startswith("periode")
    assert calls[-1][0] == "schedule" and calls[-1][3].day == 13
    saved = repo.get_reservation("lucca", "r1")
    assert saved.access_pin == "482916" and saved.access_rooms == ["14"] and saved.access_codes[0]["user_id"] == "u"


def test_cancel_revokes_immediately(monkeypatch):
    removed = []
    monkeypatch.setattr(grant_access, "_cleanup", lambda h, u, g, f=None: removed.append((u, g)))
    r = _res()
    r.access_codes = [{"room": "12", "pin": "1", "user_id": "u", "group_id": "g"}]
    r.status = ReservationStatus.CANCELLED
    assert grant_access.follow_changes("lucca", r) == ["geannuleerd: toegang ingetrokken"] and removed == [("u", "g")]


def test_one_code_per_room_and_room_changes(monkeypatch):
    """Meer kamers: elke kamer haar eigen code. Kamer gewisseld: zelfde code; kamer erbij: nieuwe code;
    kamer weg: die code weg (review 02/11)."""
    made, cleaned, locks = [], [], []

    def fake_room(h, r, room, a, b):
        made.append(room)
        return {"room": room, "pin": f"pin{room}", "user_id": f"u{room}", "group_id": f"g{room}", "schedule_id": None}

    monkeypatch.setattr(grant_access, "_grant_room", fake_room)
    monkeypatch.setattr(grant_access, "_cleanup", lambda h, u, g, f=None: cleaned.append(g))
    monkeypatch.setattr(grant_access.salto, "change_locks", lambda h, g, add, remove: locks.append((g, add, remove)))
    monkeypatch.setattr(grant_access.salto, "add_time_schedule", lambda *a: "s")
    r = _res(rooms=("12", "14"))
    codes = grant_access.grant("lucca", r)
    assert [(c["room"], c["pin"]) for c in codes] == [("12", "pin12"), ("14", "pin14")] and made == ["12", "14"]
    r.rooms = ["12", "16"]  # 14 werd 16: deur wisselen, zelfde code
    monkeypatch.setattr(salto, "load_hotel", lambda h: {"salto": {"common_lock_ids": ["front"], "rooms": {
        "12": "lock12", "14": ["lock14a", "lock14b"], "16": "lock16"}}}, raising=False)
    assert grant_access.follow_changes("lucca", r)[0] == "kamer 14 naar 16"
    assert locks == [("g14", ["lock16"], ["lock14a", "lock14b"])]
    assert [(m["from"], m["to"]) for m in r.room_moves] == [("14", "16")]  # bericht aan de gast volgt
    r.rooms = ["12"]  # kamer weg
    assert "kamer 16: code ingetrokken" in grant_access.follow_changes("lucca", r) and cleaned == ["g14"]
    r.rooms = ["12", "21"]  # kamer erbij
    monkeypatch.setattr(salto, "load_hotel", lambda h: {"salto": {"common_lock_ids": ["front"], "rooms": {
        "12": "lock12", "21": "lock21"}}}, raising=False)
    assert "kamer 21: nieuwe code" in grant_access.follow_changes("lucca", r)
    saved = repo.get_reservation("lucca", "r1")
    assert [(c["room"], c["pin"]) for c in saved.access_codes] == [("12", "pin12"), ("21", "pin21")]


def test_old_single_code_is_read_as_one_entry():
    """Codes bewaard voor 02/11 (één code voor alle kamers) blijven bruikbaar en op te ruimen."""
    e = {"access_pin": "1234", "salto_user_id": "u", "salto_group_id": "g", "salto_schedule_id": "s",
         "access_rooms": '["12", "14"]'}
    assert repo._codes_from(e) == [{"room": "12, 14", "pin": "1234", "user_id": "u", "group_id": "g", "schedule_id": "s"}]


def test_code_mail_and_sms_per_room():
    """Code-mail: één regel per kamer met de pijl achter de code; sms en WhatsApp: één bericht per kamer;
    verdieping = eerste cijfer van het kamernummer; één kamer: de pijl meteen achter de code (review 02/11)."""
    from hotel_checkin.core import workflow
    from hotel_checkin.processes import send_messages

    r = Reservation("lucca", "m1", Guest("Ann", "Peeters", language="nl"), date(2099, 1, 1), date(2099, 1, 3),
                    rooms=["16", "21"])
    r.access_codes = [{"room": "16", "pin": "2242"}, {"room": "21", "pin": "9911"}]
    step = next(s for s in workflow.steps("lucca", "booking") if s.step == "access_code")
    msg, _ = send_messages._rendered("lucca", step, r, workflow.config("lucca"))
    assert "Kamer 16, 1e verdieping: " in msg.html and "2242&nbsp;↵" in msg.html and "9911&nbsp;↵" in msg.html
    assert "Kamer 21, 2e verdieping: 9911 ↵" in msg.text and "eigen ingang" not in msg.html.lower()
    texts = [t for _, t, _ in send_messages.phone_messages("lucca", step, r, "x", {"hotel_naam": "Hotel Lucca"})]
    assert texts == ["Uw verblijf @ Hotel Lucca, kamer 16 verdiep 1, code: 2242 ↵",
                     "Uw verblijf @ Hotel Lucca, kamer 21 verdiep 2, code: 9911 ↵"]
    r.rooms, r.access_codes = ["16"], [{"room": "16", "pin": "2242"}]
    one, _ = send_messages._rendered("lucca", step, r, workflow.config("lucca"))
    assert "2242 ↵" in one.html and "Uw persoonlijke pincode<" in one.html


def test_rooms_with_own_entrance():
    """Kamer 2 (suite om de hoek) en 20 (appartement naast het hotel): eigen naam, geen verdieping,
    uitleg over de ingang onder de code, in de taal van de gast."""
    from hotel_checkin.core import workflow
    from hotel_checkin.processes import send_messages

    assert send_messages.room_info("lucca", "12", "nl")["floor"] == "1"
    assert send_messages.room_info("lucca", "2", "nl") | {"access": ""} == {
        "floor": "", "name": "historische suite", "short": "eigen ingang Kuipersstraat", "access": ""}
    r = Reservation("lucca", "m2", Guest("Ann", "Peeters", language="en"), date(2099, 1, 1), date(2099, 1, 3),
                    rooms=["2"])
    r.access_codes = [{"room": "2", "pin": "1111"}]
    step = next(s for s in workflow.steps("lucca", "booking") if s.step == "access_code")
    msg, _ = send_messages._rendered("lucca", step, r, workflow.config("lucca"))
    assert "Please note: own entrance".upper() in msg.text and "turn left into Kuipersstraat" in msg.html
    assert send_messages.phone_messages("lucca", step, r, "x", {"hotel_naam": "Hotel Lucca"})[0][1] == \
        "Your stay @ Hotel Lucca, room 2 (own entrance Kuipersstraat), code: 1111 ↵"
    r.guest.language, r.rooms = "nl", ["20", "14"]
    r.access_codes = [{"room": "20", "pin": "2020"}, {"room": "14", "pin": "1414"}]
    msg, _ = send_messages._rendered("lucca", step, r, workflow.config("lucca"))
    assert "Kamer 20, appartement naast het hotel: 2020 ↵" in msg.text and "Kamer 14, 1e verdieping: 1414 ↵" in msg.text
    assert "<strong>Kamer 20, appartement naast het hotel:</strong> Uw appartement is in het gebouw rechts" in msg.html


def test_no_code_when_room_not_paid(monkeypatch):
    """Vaste regel: geen pincode bij Salto en geen code-mail zolang de kamer niet betaald is."""
    from hotel_checkin.processes import send_messages

    monkeypatch.setattr(salto, "configured", lambda h: True)
    made = []
    monkeypatch.setattr(grant_access, "grant", lambda h, r: made.append(r.reservation_id))
    r = _res()
    r.open_amount, r.folio = 118.4, [{"label": "Kamer", "qty": None, "amount": 110.0},
                                     {"label": "Citytax", "qty": 2, "amount": 8.4}]
    assert not send_messages.code_ready("lucca", r, []) and made == []
    r.open_amount = 8.4  # alleen de toeristenbelasting staat nog open
    assert send_messages.code_ready("lucca", r, []) and made == ["r1"]


def test_own_four_digit_pin_rules():
    """Eigen pincode van 4 cijfers: niet 1111, geen reeks 1234 of 4321, niet een code die in gebruik is."""
    for _ in range(300):
        pin = grant_access.new_pin(4, {"2242"})
        assert len(pin) == 4 and pin.isdigit() and pin != "2242"
        assert len(set(pin)) > 1 and pin not in ("0123", "1234", "2345", "3456", "4567", "5678", "6789",
                                                "9876", "8765", "7654", "6543", "5432", "4321", "3210")


def test_custom_pin_used_when_length_set(monkeypatch):
    monkeypatch.setattr(grant_access, "pin_length", lambda h: 4)
    got = []
    for name in ("create_user", "create_access_group", "add_locks", "add_time_schedule", "add_user_to_group"):
        monkeypatch.setattr(grant_access.salto, name, lambda *a, _n=name, **k: f"{_n}-id")
    monkeypatch.setattr(grant_access.salto, "set_custom_pin", lambda h, u, pin, expiry: got.append(pin) or pin)
    monkeypatch.setattr(grant_access.salto, "create_pin", lambda *a, **k: pytest.fail("Salto mocht de code niet kiezen"))
    codes = grant_access.grant("lucca", _res())
    assert len(got) == 1 and codes[0]["pin"] == got[0] and len(got[0]) == 4


def test_user_limit_stops_new_codes(monkeypatch):
    monkeypatch.setattr(grant_access, "max_users", lambda h: 150)
    monkeypatch.setattr(grant_access.salto, "count_users", lambda h: 145)
    monkeypatch.setattr(grant_access, "_grant_room", lambda *a: pytest.fail("geen nieuwe gebruiker"))
    with pytest.raises(salto.SaltoError, match="maximum"):
        grant_access.grant("lucca", _res())


def test_users_removed_right_after_checkout(monkeypatch):

    removed = []
    monkeypatch.setattr(grant_access, "_cleanup", lambda h, u, g, f=None: removed.append(g))
    r = _res()
    r.access_codes = [{"room": "12", "pin": "1", "user_id": "u", "group_id": "g"}]
    r.arrival, r.departure = date.today() - timedelta(days=2), date.today()
    r.access_valid_until = datetime.now(UTC) - timedelta(minutes=5)
    monkeypatch.setattr(grant_access.salto, "update_time_schedule", lambda *a: None)
    monkeypatch.setattr(grant_access.salto, "add_time_schedule", lambda *a: "s")
    # vertrekdag: de voordeur werkt nog tot het einde van de dag, dus nog niet opruimen
    assert "vertrokken: toegang ingetrokken" not in grant_access.follow_changes("lucca", r) and removed == []
    r.arrival, r.departure = date.today() - timedelta(days=3), date.today() - timedelta(days=1)
    assert grant_access.follow_changes("lucca", r) == ["vertrokken: toegang ingetrokken"] and removed == ["g"]
