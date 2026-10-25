"""Tests voor bouwblok 5 (opslag) met een eenvoudige tabel in het geheugen, zonder Azure."""

from datetime import date

import pytest

from hotel_checkin.core.models import Channel, Guest, Reservation, SendResult
from hotel_checkin.guests import repository as repo


FakeTable = repo.MemoryTable


@pytest.fixture(autouse=True)
def fake_tables(monkeypatch):
    tables: dict[str, FakeTable] = {}
    monkeypatch.setattr(repo, "_client_factory", lambda name: tables.setdefault(name, FakeTable()))
    return tables


def _reservation(rid="abc-123"):
    return Reservation(
        hotel_id="lucca",
        reservation_id=rid,
        guest=Guest("Anna", "Peeters", "Anna@Example.com", "+32470000000", "nl"),
        arrival=date(2026, 11, 14),
        departure=date(2026, 11, 16),
        rooms=["14"],
        source="Booking.com",
        room_type="Superior Double",
    )


def test_save_and_get_keeps_token():
    saved = repo.save_reservation(_reservation())
    assert saved.token
    again = repo.save_reservation(_reservation())  # opnieuw binnengekomen, zonder token
    assert again.token == saved.token
    r = repo.get_reservation("lucca", "abc-123")
    assert r.guest.email == "anna@example.com" and r.rooms == ["14"] and r.paid is None


def test_get_by_token_and_phone():
    saved = repo.save_reservation(_reservation())
    assert repo.get_by_token(saved.token).reservation_id == "abc-123"
    assert repo.get_by_token("onbestaand") is None
    assert [r.reservation_id for r in repo.find_by_phone("lucca", "+32470000000")] == ["abc-123"]


def test_mark_checkin_completed():
    repo.save_reservation(_reservation())
    r = repo.mark_checkin_completed("lucca", "abc-123", "nieuw@example.com", None, "fr")
    assert r.checkin_completed_at is not None
    assert repo.get_reservation("lucca", "abc-123").guest.language == "fr"


def test_message_log_and_duplicates():
    repo.log_message("lucca", "abc-123", "bevestiging", SendResult(Channel.EMAIL, "a@b.c", ok=False, error="x"))
    assert not repo.was_sent("lucca", "abc-123", "bevestiging")
    repo.log_message("lucca", "abc-123", "bevestiging", SendResult(Channel.EMAIL, "a@b.c", ok=True))
    assert repo.was_sent("lucca", "abc-123", "bevestiging")
    assert repo.was_sent("lucca", "abc-123", "bevestiging", "email")
    assert not repo.was_sent("lucca", "abc-123", "bevestiging", "sms")
    assert len(repo.messages_for("lucca", "abc-123")) == 2


def test_opt_out_is_case_insensitive():
    repo.add_opt_out("lucca", " Anna@Example.com ", "checkin_form")
    assert repo.is_opted_out("lucca", "anna@example.com")
    assert not repo.is_opted_out("lucca", "ander@example.com")


@pytest.mark.parametrize(
    "given,stored",
    [
        ("nl", "nl"), ("NL-nl", "nl"), ("nl_BE", "nl"),
        ("FR", "fr"), ("fr-CA", "fr"), ("FR-ch", "fr"), ("Fr", "fr"), ("fr-BE", "fr"),
        ("de-DE", "de"), ("de-AT", "de"), ("DE-ch", "de"),
        ("en", "en"), ("EN-us", "en"), ("it", "en"), ("es-ES", "en"), ("", "en"), (None, "en"),
    ],
)
def test_language_rule(given, stored):
    r = _reservation()
    r.guest.language = given
    repo.save_reservation(r)
    assert repo.get_reservation("lucca", "abc-123").guest.language == stored


def test_ids_with_special_characters():
    repo.save_reservation(_reservation("a/b#c?d"))
    assert repo.get_reservation("lucca", "a/b#c?d") is not None


def test_hotels_are_separated():
    a = _reservation("R-1")
    b = _reservation("R-1")
    b.hotel_id = "ander-hotel"
    b.guest.first_name = "Bert"
    repo.save_reservation(a)
    repo.save_reservation(b)
    assert repo.get_reservation("lucca", "R-1").guest.first_name == "Anna"
    assert repo.get_reservation("ander-hotel", "R-1").guest.first_name == "Bert"
    assert [r.hotel_id for r in repo.find_by_phone("lucca", "+32470000000")] == ["lucca"]
    repo.add_opt_out("lucca", "anna@example.com", "checkin_form")
    assert repo.is_opted_out("lucca", "anna@example.com")
    assert not repo.is_opted_out("ander-hotel", "anna@example.com")
    repo.log_message("lucca", "R-1", "bevestiging", SendResult(Channel.EMAIL, "a@b.c", ok=True))
    assert repo.was_sent("lucca", "R-1", "bevestiging")
    assert not repo.was_sent("ander-hotel", "R-1", "bevestiging")
