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


class _Session:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture(autouse=True)
def fake_lighthouse(monkeypatch):
    monkeypatch.setattr(new_reservation.lighthouse, "connect", lambda h: _Session())
    detail = _res(email="jan@example.com", phone="+4915100000", language="de", country="DE")
    monkeypatch.setattr(new_reservation.lighthouse, "get_reservation", lambda h, rid, lh=None: detail)


def test_new_reservation_gets_details(monkeypatch):
    monkeypatch.setattr(new_reservation.lighthouse, "get_new_reservations", lambda *a, **k: [_res()])
    assert new_reservation.run("lucca", datetime(2000, 1, 1)) == 1
    r = repo.get_reservation("lucca", "u1")
    assert r.guest.email == "jan@example.com" and r.guest.language == "de" and r.guest.country == "DE"


def test_new_and_merge(monkeypatch):
    monkeypatch.setattr(new_reservation.lighthouse, "get_new_reservations", lambda *a, **k: [_res()])
    assert new_reservation.run("lucca", datetime(2000, 1, 1)) == 1
    token = repo.get_reservation("lucca", "u1").token
    repo.mark_checkin_completed("lucca", "u1", "jan@example.com", "+32470000000", "fr")

    assert new_reservation.run("lucca", datetime(2000, 1, 1)) == 0
    r = repo.get_reservation("lucca", "u1")
    assert r.token == token and r.guest.email == "jan@example.com" and r.guest.language == "fr"


def test_robot_since_newest_stored_booking():
    from datetime import timedelta, timezone

    from hotel_checkin import robot

    now = datetime.now(timezone.utc)
    assert now - robot._since("lucca", None) > timedelta(days=29)  # niets opgeslagen: 30 dagen
    r = _res()
    r.booked_at = now - timedelta(hours=5)
    repo.save_reservation(r)
    assert abs((robot._since("lucca", None) - (r.booked_at - timedelta(hours=1))).total_seconds()) < 1
    assert now - robot._since("lucca", 5) < timedelta(hours=5, seconds=5)


def test_robot_main_runs(monkeypatch):
    import sys

    from hotel_checkin import robot

    called = []
    monkeypatch.setattr(robot.new_reservation, "run", lambda h, since: called.append(h) or 0)
    monkeypatch.setattr(sys, "argv", ["robot"])
    monkeypatch.delenv("ROBOT_HOTEL", raising=False)
    assert robot.main() == 0 and called == ["lucca"]


def test_robot_rereads_after_skipped_rows():
    from datetime import timedelta, timezone

    from hotel_checkin import robot

    now = datetime.now(timezone.utc)
    r = _res()
    r.booked_at = now - timedelta(hours=2)
    repo.save_reservation(r)
    window = now - timedelta(days=3)
    repo.log_robot_run("lucca", new_reservation.TASK, now, True, 16, 10, "6 overgeslagen", since=window, skipped=6)
    assert robot._since("lucca", None) == window  # zelfde periode opnieuw
    repo.log_robot_run("lucca", new_reservation.TASK, now + timedelta(seconds=5), True, 16, 6, since=window, skipped=0)
    assert robot._since("lucca", None) == r.booked_at - timedelta(hours=1)  # alles gelukt: verder


def test_backfill_missing_contact(monkeypatch):
    from datetime import date

    stored = _res()
    stored.reservation_id = "u2"
    from datetime import timedelta

    soon = date.today() + timedelta(days=3)
    stored.arrival, stored.departure = soon, soon + timedelta(days=1)
    repo.save_reservation(stored)  # opgeslagen zonder e-mail, aankomst binnen 8 dagen
    later = _res()
    later.reservation_id = "u3"
    later.arrival, later.departure = date(2099, 1, 1), date(2099, 1, 2)
    repo.save_reservation(later)  # verre aankomst: nog niet nodig
    monkeypatch.setattr(new_reservation.lighthouse, "get_new_reservations", lambda *a, **k: [])
    new_reservation.run("lucca", datetime(2000, 1, 1))
    assert repo.get_reservation("lucca", "u2").guest.email == "jan@example.com"
    assert repo.get_reservation("lucca", "u3").guest.email is None
    assert "aangevuld" in repo.robot_runs("lucca")[0]["error"]
