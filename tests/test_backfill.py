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
    monkeypatch.setattr(backfill.lighthouse, "get_contact",
                        lambda h, rid, lh: Guest("", "", email=f"{rid}@example.com", phone="", language="", country=None))
    backfill.run("lucca", None)
    assert repo.get_reservation("lucca", "future") and repo.get_reservation("lucca", "past") is None
    assert backfill.done("lucca")
    note = repo.robot_runs("lucca", task=backfill.TASK)[0]["error"]
    assert "2 toekomstige nieuw bewaard" in note and "Klaar" in note  # ook lang geleden geboekt, als het verblijf nog komt


def test_old_booking_follows_the_normal_rules():
    r = repo.save_reservation(_r("future", 40, 300))  # lang geleden geboekt, nu binnengehaald
    assert not send_messages.before_start(r, datetime.now(UTC) - timedelta(days=3))


def test_imported_old_booking_skips_confirmation_but_gets_reminder():
    from hotel_checkin.core import workflow

    r = repo.save_reservation(_r("future", 10, 300))  # geboekt 300 dagen geleden, nu binnengehaald
    steps = {s.step: s for s in workflow.steps("lucca")}
    assert workflow.stored_late(r)
    assert not workflow.is_due(steps["confirmation"], r, TODAY)  # moment van de boeking is voorbij
    fresh = repo.save_reservation(_r("fresh", 10, 0))
    assert not workflow.stored_late(fresh) and workflow.is_due(steps["confirmation"], fresh, TODAY)
