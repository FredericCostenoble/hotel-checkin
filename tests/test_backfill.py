"""Eenmalig oudere boekingen voor toekomstige verblijven (processes/backfill.py)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from hotel_checkin.core.models import Guest, Reservation
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import backfill, send_messages

TODAY = date.today()


@pytest.fixture(autouse=True)
def setup():
    repo.use_memory_store()


def _r(rid, arrival_in, booked_days_ago):
    a = TODAY + timedelta(days=arrival_in)
    return Reservation("lucca", rid, Guest("Ann", "Brand"), a, a + timedelta(days=2), source="Booking.com",
                       booked_at=datetime.now(UTC) - timedelta(days=booked_days_ago))


def test_stores_only_future_and_finishes(monkeypatch):
    pages = [[_r("future", 40, 300), _r("past", -30, 320)], [_r("old", 10, 800)], []]
    monkeypatch.setattr(backfill.lighthouse, "list_page", lambda h, n, lh, sk: pages[n] if n < len(pages) else [])
    backfill.run("lucca", None)
    assert repo.get_reservation("lucca", "future") and repo.get_reservation("lucca", "past") is None
    assert backfill.done("lucca")
    note = repo.robot_runs("lucca", task=backfill.TASK)[0]["error"]
    assert "2 toekomstige nieuw bewaard" in note and "Klaar" in note  # ook lang geleden geboekt, als het verblijf nog komt


def test_old_booking_gets_no_messages():
    r = repo.save_reservation(_r("future", 40, 300))
    assert send_messages.before_start(r, datetime.now(UTC) - timedelta(days=3))  # geboekt voor de start
    r2 = repo.save_reservation(_r("new", 40, 1))
    assert not send_messages.before_start(r2, datetime.now(UTC) - timedelta(days=3))
