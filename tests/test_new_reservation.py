"""Proces nieuwe reservatie: gegevens van de gast blijven behouden."""

from datetime import date, datetime

import pytest

from hotel_checkin.core.models import Guest, Reservation
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import new_reservation


@pytest.fixture(autouse=True)
def memory(monkeypatch):
    repo.use_memory_store()


def _res(**guest):
    return Reservation("lucca", "u1", Guest("Jan", "Voorbeeld", **guest), date(2099, 1, 1), date(2099, 1, 2))


def test_new_and_merge(monkeypatch):
    monkeypatch.setattr(new_reservation.lighthouse, "get_new_reservations", lambda h, s: [_res()])
    assert new_reservation.run("lucca", datetime(2000, 1, 1)) == 1
    token = repo.get_reservation("lucca", "u1").token
    repo.mark_checkin_completed("lucca", "u1", "jan@example.com", "+32470000000", "fr")

    assert new_reservation.run("lucca", datetime(2000, 1, 1)) == 0
    r = repo.get_reservation("lucca", "u1")
    assert r.token == token and r.guest.email == "jan@example.com" and r.guest.language == "fr"
