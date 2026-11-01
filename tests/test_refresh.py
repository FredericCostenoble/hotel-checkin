"""Nalezen van reservaties: annuleringen en wijzigingen van oudere boekingen tijdig zien."""

from datetime import date, timedelta

import pytest

from hotel_checkin.core.models import Guest, Reservation, ReservationStatus
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import refresh_contacts, refresh_requests


@pytest.fixture(autouse=True)
def memory():
    repo.use_memory_store()


def _save(rid, arrival, **kw):
    r = Reservation("lucca", rid, Guest("Jan", "Voorbeeld", email="jan@example.com"), arrival,
                    arrival + timedelta(days=2), source="Booking.com", **kw)
    return repo.save_reservation(r)


def test_reservation_with_reminder_tomorrow_is_read_again():
    """Herinnering 7 dagen voor aankomst: de dag ervoor opnieuw lezen (geannuleerd?)."""
    today = date.today()
    _save("soon", today + timedelta(days=8))
    _save("later", today + timedelta(days=20))
    _save("gone", today + timedelta(days=8), status=ReservationStatus.CANCELLED)
    ids = [r.reservation_id for r in refresh_contacts.arrivals_due("lucca")]
    assert ids == ["soon"]


def test_requested_days_from_notice():
    today = date.today()
    _save("a", today + timedelta(days=30))
    _save("b", today + timedelta(days=31))
    refresh_requests.request("lucca", [today + timedelta(days=30)])
    ids = [r.reservation_id for r in refresh_contacts.arrivals_due("lucca", refresh_requests.requested("lucca"))]
    assert ids == ["a"]
    refresh_requests.done("lucca", {(today + timedelta(days=30)).isoformat()})
    assert refresh_requests.requested("lucca") == set()
