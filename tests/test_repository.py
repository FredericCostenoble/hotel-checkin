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
    r = repo.get_reservation("abc-123")
    assert r.guest.email == "anna@example.com" and r.rooms == ["14"] and r.paid is None


def test_get_by_token_and_phone():
    saved = repo.save_reservation(_reservation())
    assert repo.get_by_token(saved.token).reservation_id == "abc-123"
    assert repo.get_by_token("onbestaand") is None
    assert [r.reservation_id for r in repo.find_by_phone("+32470000000")] == ["abc-123"]


def test_mark_checkin_completed():
    repo.save_reservation(_reservation())
    r = repo.mark_checkin_completed("abc-123", "nieuw@example.com", None, "fr")
    assert r.checkin_completed_at is not None
    assert repo.get_reservation("abc-123").guest.language == "fr"


def test_message_log_and_duplicates():
    repo.log_message("abc-123", "bevestiging", SendResult(Channel.EMAIL, "a@b.c", ok=False, error="x"))
    assert not repo.was_sent("abc-123", "bevestiging")
    repo.log_message("abc-123", "bevestiging", SendResult(Channel.EMAIL, "a@b.c", ok=True))
    assert repo.was_sent("abc-123", "bevestiging")
    assert repo.was_sent("abc-123", "bevestiging", "email")
    assert not repo.was_sent("abc-123", "bevestiging", "sms")
    assert len(repo.messages_for("abc-123")) == 2


def test_opt_out_is_case_insensitive():
    repo.add_opt_out(" Anna@Example.com ", "checkin_form")
    assert repo.is_opted_out("anna@example.com")
    assert not repo.is_opted_out("ander@example.com")


def test_ids_with_special_characters():
    repo.save_reservation(_reservation("a/b#c?d"))
    assert repo.get_reservation("a/b#c?d") is not None
