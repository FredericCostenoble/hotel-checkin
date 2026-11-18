"""Tests voor de logica van het check-in-formulier, met tabellen in het geheugen."""

from datetime import date

import pytest

from hotel_checkin.checkin import service
from hotel_checkin.core.models import Guest, Reservation, ReservationStatus
from hotel_checkin.guests import repository as repo
from tests.test_repository import FakeTable


@pytest.fixture(autouse=True)
def fake_tables(monkeypatch):
    tables: dict[str, FakeTable] = {}
    monkeypatch.setattr(repo, "_client_factory", lambda name: tables.setdefault(name, FakeTable()))


def _save(status=ReservationStatus.READY_FOR_CHECKIN, departure=date(2099, 1, 3)):
    r = Reservation(
        hotel_id="lucca",
        reservation_id="R1",
        guest=Guest("Anna", "Peeters", "anna@example.com", None, "nl"),
        arrival=date(2099, 1, 1),
        departure=departure,
        status=status,
        room_type="Twin",
        token="tok",
    )
    repo.save_reservation(r)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0476 89 62 74", "+32476896274"),
        ("+32 476/89.62.74", "+32476896274"),
        ("0049 151 2345678", "+491512345678"),
        ("12", None),
        ("abc", None),
    ],
)
def test_normalize_phone(raw, expected):
    assert service.normalize_phone(raw) == expected


def test_form_data_states():
    assert service.form_data("onbekend") is None
    _save()
    d = service.form_data("tok")
    assert d["state"] == "open" and d["first_name"] == "Anna" and not d["completed"]
    assert d["hotel"]["name"] == "Hotel Lucca"
    _save(status=ReservationStatus.CANCELLED)
    assert service.form_data("tok")["state"] == "cancelled"
    _save(departure=date(2000, 1, 2))
    assert service.form_data("tok")["state"] == "closed"


def test_submit_ok_with_opt_out():
    _save()
    ok, errors = service.submit("tok", {"email": " Anna.P@Example.com ", "phone": "0476 89 62 74", "language": "fr", "no_marketing": True, "backup_email": "Partner@Example.com", "backup_phone": "+33 6 12 34 56 78"})
    assert ok and errors == {}
    r = repo.get_reservation("lucca", "R1")
    assert r.guest.email == "anna.p@example.com" and r.guest.phone == "+32476896274"
    assert r.guest.language == "fr" and r.checkin_completed_at is not None
    assert repo.is_opted_out("lucca", "anna.p@example.com")
    assert r.guest.backup_email == "partner@example.com" and r.guest.backup_phone == "+33612345678"
    assert service.form_data("tok")["completed"] and service.form_data("tok")["no_marketing"]


def test_submit_validation_and_no_opt_out():
    _save()
    ok, errors = service.submit("tok", {"email": "geen-mail", "phone": "12", "backup_email": "x@", "backup_phone": "abc", "language": "nl"})
    assert not ok and errors == {"email": "invalid", "phone": "invalid", "backup_email": "invalid", "backup_phone": "invalid"}
    ok, _ = service.submit("tok", {"email": "anna@example.com", "phone": "", "language": "xx"})
    assert ok and not repo.is_opted_out("lucca", "anna@example.com")
    assert repo.get_reservation("lucca", "R1").guest.language == "nl"


def test_submit_refused_when_not_open():
    _save(status=ReservationStatus.CANCELLED)
    assert service.submit("tok", {"email": "a@b.be"}) == (False, {"state": "cancelled"})
    assert service.submit("x", {"email": "a@b.be"}) == (False, {"token": "not_found"})



def test_demo_link_from_example_mail_is_never_saved():
    from hotel_checkin.checkin import service

    data = service.form_data("voorbeeld-lucca")
    assert data["state"] == "open" and data["demo"] and data["first_name"] == "Anna"
    assert service.form_data("voorbeeld-onbekend") is None
    ok, errors = service.submit("voorbeeld-lucca", {"email": "a@b.be", "language": "nl"})
    assert ok and not errors
    assert service.submit("voorbeeld-lucca", {"email": "fout"})[1] == {"email": "invalid"}


def test_relay_address_not_prefilled():
    from datetime import date, timedelta

    from hotel_checkin.checkin import service
    from hotel_checkin.core.models import Guest, Reservation
    from hotel_checkin.guests import repository as repo

    repo.use_memory_store()
    arr = date.today() + timedelta(days=10)
    r = repo.save_reservation(Reservation("lucca", "relay1", Guest("Jan", "Peeters", email="jpeete.123@guest.booking.com"),
                                          arr, arr + timedelta(days=1)))
    assert service.form_data(r.token)["email"] == ""


def test_form_submission_kept_and_reapplied():
    from datetime import date, timedelta

    from hotel_checkin.checkin import service
    from hotel_checkin.core.models import Guest, Reservation
    from hotel_checkin.guests import repository as repo

    repo.use_memory_store()
    arr = date.today() + timedelta(days=8)
    r = repo.save_reservation(Reservation("lucca", "fs1", Guest("Caner", "Adnan", email="ac.2@guest.booking.com"), arr,
                                          arr + timedelta(days=3)))
    ok, _ = service.submit(r.token, {"email": "caner@elbonet.be", "language": "en"})
    assert ok and repo.form_submissions("lucca", "fs1")[0]["email"] == "caner@elbonet.be"
    assert any(m["message_type"] == "checkin_form" for m in repo.messages_for("lucca", "fs1"))
    # iets wist het adres en de bevestiging (bv. een fout): het vangnet zet het terug
    broken = repo.get_reservation("lucca", "fs1")
    entity = repo._to_entity(broken)
    entity["email"], entity["checkin_completed_at"] = "ac.2@guest.booking.com", ""
    repo._table(repo.T_RESERVATIONS).upsert_entity(entity)
    assert service.reapply_forms("lucca") == 1
    assert repo.get_reservation("lucca", "fs1").guest.email == "caner@elbonet.be"
    assert service.reapply_forms("lucca") == 0


def test_pay_info_in_app():
    """Openstaand bedrag volgens de folio, met de betaallink van Lighthouse als die er is."""
    _save()
    assert service.form_data("tok")["pay"] is None  # folio nog niet gelezen
    r = repo.get_reservation("lucca", "R1")
    r.open_amount, r.guest_count = 16.8, 2
    r.folio = [{"label": "Kamer", "qty": None, "amount": 300.0}, {"label": "Citytax", "qty": 4, "amount": 16.8}]
    repo.save_reservation(r)
    pay = service.form_data("tok")["pay"]
    assert pay["amount"] == "€\u00a016,80" and pay["url"] is None and not pay["paid"] and pay["kind"] == "city_tax"
    assert pay["tax"] == {"persons": 2, "nights": 2, "rate": "€\u00a04,20"}
    r.pay_link = "https://pay.example/abc"
    repo.save_reservation(r)
    assert service.form_data("tok")["pay"]["url"] == "https://pay.example/abc"
    r.open_amount = 0
    repo.save_reservation(r)
    assert service.form_data("tok")["pay"]["paid"] and service.form_data("tok")["pay"]["url"] is None
    assert service.form_data("voorbeeld-lucca")["pay"]["url"]  # voorbeeld in de monitor


def _at(day, hour):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime(day.year, day.month, day.day, hour, tzinfo=ZoneInfo("Europe/Brussels"))


def test_phases_and_code_only_after_checkin_and_payment():
    _save()
    r = repo.get_reservation("lucca", "R1")
    r.rooms, r.paid = ["16"], True
    r.access_codes = [{"room": "16", "pin": "2242", "user_id": "u", "group_id": "g"}]
    r.access_valid_from = _at(date(2099, 1, 1), 14)
    repo.save_reservation(r)
    d = service.form_data("tok", now=_at(date(2098, 12, 30), 10))
    assert d["phase"] == "code" and d["access"]["codes"] == []  # gegevens nog niet ingevuld: geen code
    assert d["access"]["code_date"] == "2098-12-30"
    ok, _ = service.submit("tok", {"email": "anna@example.com", "language": "nl"})
    assert ok
    d = service.form_data("tok", now=_at(date(2098, 12, 30), 10))
    assert d["completed"] and d["access"]["codes"] == [{"room": "16", "pin": "2242"}]
    assert d["access"]["unlock"] is None  # schakelaar ontgrendelen staat uit
    assert service.form_data("tok", now=_at(date(2099, 1, 1), 15))["phase"] == "stay"
    after = service.form_data("tok", now=_at(date(2099, 1, 3), 12))
    assert after["phase"] == "after" and after["state"] == "open" and after["access"]["codes"] == []
    assert service.form_data("tok", now=_at(date(2099, 1, 30), 12))["state"] == "closed"
    # kamer niet betaald: geen code
    r = repo.get_reservation("lucca", "R1")
    r.paid, r.open_amount = None, 300.0
    repo.save_reservation(r)
    assert service.form_data("tok", now=_at(date(2098, 12, 30), 10))["access"]["codes"] == []


def test_submit_refused_after_checkout():
    _save()
    from hotel_checkin.checkin import service as s

    real = s._now
    try:
        s._now = lambda hotel_id: _at(date(2099, 1, 4), 9)
        assert s.submit("tok", {"email": "a@b.be"}) == (False, {"state": "closed"})
    finally:
        s._now = real


def test_demo_variants():
    for v in service.DEMO_VARIANTS:
        assert service.form_data(f"voorbeeld-lucca.{v}")["demo"]
    assert service.form_data("voorbeeld-lucca.onbekend") is None
    assert service.form_data("voorbeeld-lucca.stay")["access"]["codes"]
    assert service.unlock("voorbeeld-lucca.stay", "front") == (True, "opened")
    assert not service.pay_started("voorbeeld-lucca")


def test_checkin_suffix(monkeypatch):
    from hotel_checkin.messaging import templates

    monkeypatch.delenv("CHECKIN_FORM_URL", raising=False)
    assert templates.checkin_suffix("lucca", "abc", "fr") == "abc&lang=fr"
    monkeypatch.setenv("CHECKIN_FORM_URL", "https://test.example/form?r={token}")
    assert templates.checkin_suffix("lucca", "abc") == "abc"
