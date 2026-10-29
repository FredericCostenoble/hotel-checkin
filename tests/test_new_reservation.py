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


def test_robot_since_last_successful_run():
    from datetime import timedelta, timezone

    from hotel_checkin import robot

    now = datetime.now(timezone.utc)
    assert now - robot._since("lucca", None) > timedelta(hours=47)  # nog nooit gedraaid: 48 uur
    started = now - timedelta(minutes=30)
    repo.log_robot_run("lucca", "nieuwe_reservaties", started, True, 3, 1)
    assert abs((robot._since("lucca", None) - (started - timedelta(hours=1))).total_seconds()) < 1
    assert now - robot._since("lucca", 5) < timedelta(hours=5, seconds=5)
