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
