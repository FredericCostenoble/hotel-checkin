"""Paginering van de lijsten in de monitor op de server, met de index (guests/index.py)."""

from datetime import date, timedelta

import pytest

from hotel_checkin.admin import service
from hotel_checkin.core.models import Guest, Reservation, ReservationStatus
from hotel_checkin.guests import index, profiles
from hotel_checkin.guests import repository as repo


@pytest.fixture
def setup():
    repo.use_memory_store()
    base = date(2026, 12, 1)
    for i in range(120):
        r = Reservation(hotel_id="lucca", reservation_id=f"r{i:03}", booking_number=f"CPB-{i:03}",
                        arrival=base + timedelta(days=i % 30), departure=base + timedelta(days=i % 30 + 2),
                        guest=Guest(first_name=f"Gast{i:03}", last_name="Test", email=f"g{i}@example.com"),
                        status=ReservationStatus.CANCELLED if i % 10 == 0 else ReservationStatus.READY_FOR_CHECKIN)
        repo.save_reservation(r)
        g = profiles.new_profile("lucca")
        g.first_name, g.last_name, g.reservation_ids, g.stays = f"Gast{i:03}", "Test", [r.reservation_id], i % 4
        profiles.save_profile(g)
    return base


def test_reservations_per_50_with_next(setup):
    p1 = service.list_request("lucca", "reservations", {"page": "1"})
    assert len(p1["items"]) == 50 and p1["total"] == 120 and p1["next"] == 50
    p3 = service.list_request("lucca", "reservations", {"page": "1", "offset": "100"})
    assert len(p3["items"]) == 20 and p3["next"] is None
    arr = [x["arrival"] for x in p1["items"]]
    assert arr == sorted(arr)  # standaard op aankomst


def test_reservations_search_filter_sort(setup):
    res = service.list_request("lucca", "reservations", {"page": "1", "q": "gast007"})
    assert [x["booking_number"] for x in res["items"]] == ["CPB-007"]
    res = service.list_request("lucca", "reservations", {"page": "1", "status": "cancelled"})
    assert res["total"] == 12 and all(x["status"] == "cancelled" for x in res["items"])
    res = service.list_request("lucca", "reservations", {"page": "1", "sort": "guest", "dir": "desc"})
    assert res["items"][0]["guest"] == "Gast119 Test"
    res = service.list_request("lucca", "reservations", {"page": "1", "ids": "r005,r077"})
    assert sorted(x["id"] for x in res["items"]) == ["r005", "r077"]


def test_window_for_today_without_paging(setup):
    d = setup + timedelta(days=5)
    res = service.list_request("lucca", "reservations", {"page": "1", "window": f"{d},{d}"})
    assert res["items"] and all(x["departure"] >= d.isoformat() and x["arrival"] <= d.isoformat() for x in res["items"])
    assert res["next"] is None


def test_guests_per_50_and_index_follows_changes(setup):
    p1 = service.list_request("lucca", "guests", {"page": "1"})
    assert len(p1["guests"]) == 50 and p1["total"] == 120 and "matches" in p1
    g = profiles.list_profiles("lucca")[0]
    profiles.delete_profile("lucca", g.guest_id)
    assert service.list_request("lucca", "guests", {"page": "1"})["total"] == 119
    repo.delete_reservation("lucca", "r001")
    assert service.list_request("lucca", "reservations", {"page": "1"})["total"] == 119


def test_index_rebuilt_when_missing(setup):
    repo.set_state("lucca", "list_index_version", "0")
    t = repo._table(index.T_RES_INDEX)
    for e in list(t.query_entities("PartitionKey eq 'lucca'"))[:30]:
        t.delete_entity(e["PartitionKey"], e["RowKey"])
    assert service.list_request("lucca", "reservations", {"page": "1"})["total"] == 120


def test_without_page_the_old_full_list(setup):
    assert len(service.list_request("lucca", "reservations", {})) == 120
    assert len(service.list_request("lucca", "guests", {})["guests"]) == 120


def test_failed_message_problem_and_dismiss(setup):
    from hotel_checkin.core.models import Channel, SendResult

    repo.log_message("lucca", "r005", "confirmation", SendResult(channel=Channel.EMAIL, to="a@b.c", ok=False,
                     error='Graph 403: {"error":{"code":"ErrorAccessDenied"}}'))
    assert "r005" in repo.failed_message_reservations("lucca")
    m = service.list_request("lucca", "reservations", {"page": "1", "ids": "r005"})["items"][0]["messages"][-1]
    assert m["problem"] == "mail_rights" and not m["dismissed_at"]
    assert service.dismiss_failed("lucca", "r005", "fred")["dismissed"] == 1
    assert "r005" not in repo.failed_message_reservations("lucca")
    assert repo.messages_for("lucca", "r005")[-1]["dismissed_by"] == "fred"  # blijft in het logboek


def test_guest_days_zero_keeps_profiles_forever(monkeypatch):
    from hotel_checkin.processes import maintenance

    repo.use_memory_store()  # zonder de testgegevens hierboven (die hebben verblijven zonder periodes)
    monkeypatch.setenv("LUCCA_RETENTION_GUEST_DAYS", "0")
    g = profiles.new_profile("lucca")
    g.first_name, g.last_name, g.stays, g.last_stay = "Ann", "Oud", 1, date(2000, 1, 1)
    g.stay_periods = [["2000-01-01", "2000-01-03"]]
    profiles.save_profile(g)
    maintenance.run("lucca", today=date(2026, 12, 1))
    assert profiles.get_profile("lucca", g.guest_id) is not None
