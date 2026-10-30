"""Gastprofielen: koppelen, samenvoegen, meetellen, voorstellen en opruimen (verzonnen gasten)."""

from datetime import date, timedelta

import pytest

from hotel_checkin.core.models import Guest, Reservation, ReservationStatus
from hotel_checkin.guests import profiles
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import guest_profiles as gp
from hotel_checkin.processes import maintenance


@pytest.fixture(autouse=True)
def memory():
    repo.use_memory_store()


def _res(rid, first="Jan", last="Voorbeeld", email=None, phone=None, country="BE", days_ago=None, **kw):
    arr = date.today() - timedelta(days=days_ago) if days_ago is not None else date.today() + timedelta(days=10)
    r = Reservation("lucca", rid, Guest(first, last, email=email, phone=phone, country=country),
                    arr, arr + timedelta(days=2), guest_count=2, source=kw.pop("source", "Booking.com"),
                    rooms=kw.pop("rooms", ["12"]), room_type="Double", **kw)
    return repo.save_reservation(r)


def test_relay_addresses_and_name_key():
    assert not gp.is_own_email("5347148687-abcd@guest.booking.com")
    assert gp.is_own_email("jan@example.com")
    assert gp.name_key("DE VOORBEELD", "Maria") == gp.name_key("María", "de Voorbeeld")


def test_same_phone_links_booking_com_and_direct():
    a = gp.link(_res("r1", email="111-x@guest.booking.com", phone="+32470000001"))
    b = gp.link(_res("r2", email="jan@example.com", phone="+32470000001", source="Direct"))
    assert a.guest_id == b.guest_id
    g = profiles.get_profile("lucca", a.guest_id)
    assert g.email == "jan@example.com" and g.email_own  # eigen adres vervangt doorstuuradres
    assert sorted(g.reservation_ids) == ["r1", "r2"]


def test_checkin_form_brings_two_profiles_together():
    a = gp.link(_res("r1", email="111-x@guest.booking.com"))
    b = gp.link(_res("r2", email="jan@example.com"))
    assert a.guest_id != b.guest_id  # alleen de naam: niet automatisch
    r1 = repo.mark_checkin_completed("lucca", "r1", "jan@example.com", None, "nl")
    g = gp.link(r1)
    assert len(profiles.list_profiles("lucca")) == 1 and g.from_checkin_form
    assert repo.get_reservation("lucca", "r2").guest_id == g.guest_id


def test_possible_matches_and_different():
    a = gp.link(_res("r1", "Maria", "De Voorbeeld"))
    b = gp.link(_res("r2", "DE VOORBEELD", "Maria"))
    gp.link(_res("r3", "Maria", "De Voorbeeld", country="FR"))  # ander land: geen voorstel
    m = gp.possible_matches("lucca")
    assert [(x["reason"]) for x in m] == ["same_name"] and {m[0]["a"], m[0]["b"]} == {a.guest_id, b.guest_id}
    profiles.mark_different("lucca", a.guest_id, b.guest_id)
    assert gp.possible_matches("lucca") == []


def test_count_stay_once_and_merge_sums():
    r = _res("r1", phone="+32470000001", days_ago=10)
    g = gp.link(r)
    assert gp.count_stay(repo.get_reservation("lucca", "r1")) and not gp.count_stay(repo.get_reservation("lucca", "r1"))
    other = gp.link(_res("r2", "Jan", "Voorbeelt", days_ago=40, source="Direct", rooms=["4"]))
    gp.count_stay(repo.get_reservation("lucca", "r2"))
    merged = gp.merge("lucca", g.guest_id, other.guest_id)
    assert (merged.stays, merged.nights, merged.persons) == (2, 4, 4)
    assert merged.channels == {"Booking.com": 1, "Direct": 1} and merged.rooms == {"12": 1, "4": 1}
    assert repo.get_reservation("lucca", "r2").guest_id == merged.guest_id


def test_maintenance_keeps_guest_deletes_old_reservation():
    _res("old", phone="+32470000001", days_ago=50)
    _res("future", phone="+32470000002")
    cancelled = _res("cancelled", "Ann", "Test", days_ago=60)
    cancelled.status = ReservationStatus.CANCELLED
    repo.save_reservation(cancelled)
    done = maintenance.run("lucca")
    assert done["counted"] == 1 and done["reservations_deleted"] == 2
    assert repo.get_reservation("lucca", "old") is None and repo.get_reservation("lucca", "future")
    names = sorted((g.first_name, g.stays) for g in profiles.list_profiles("lucca"))
    assert names == [("Ann", 0), ("Jan", 0), ("Jan", 1)]  # Ann (geannuleerd) blijft bereikbaar; gast van "old" blijft
    assert "onderhoud" == repo.robot_runs("lucca")[0]["task"]


def test_monitor_guests_view():
    from hotel_checkin.admin import service

    a = gp.link(_res("r1", "Maria", "De Voorbeeld", email="1-x@guest.booking.com"))
    gp.link(_res("r2", "DE VOORBEELD", "Maria", email="maria@example.be"))
    repo.add_opt_out("lucca", "maria@example.be", "checkin_form")
    data = service.guests("lucca")
    by = {g["email"]: g for g in data["guests"]}
    assert by["1-x@guest.booking.com"]["email_own"] is False and by["maria@example.be"]["opt_out"]
    assert len(data["matches"]) == 1
    assert service.mark_guests_different("lucca", data["matches"][0]["a"], data["matches"][0]["b"])
    assert service.guests("lucca")["matches"] == []
    res = {r["id"]: r for r in service.reservations("lucca")}
    assert res["r1"]["guest_id"] == a.guest_id


def test_two_rooms_same_nights_is_one_stay():
    r1 = _res("r1", phone="+32470000001", days_ago=10, rooms=["12"])
    r2 = _res("r2", phone="+32470000001", days_ago=10, rooms=["14"])
    gp.link(r1)
    gp.link(r2)
    r3 = _res("r3", phone="+32470000001", days_ago=5, rooms=["12"], source="Direct")  # aansluitend: apart verblijf
    gp.link(r3)
    for rid in ("r1", "r2", "r3"):
        gp.count_stay(repo.get_reservation("lucca", rid))
    g = profiles.list_profiles("lucca")[0]
    assert (g.stays, g.nights) == (2, 4)
    assert g.rooms == {"12": 2, "14": 1} and g.channels == {"Booking.com": 1, "Direct": 1}
    assert g.persons_stays == 2 and g.persons == 6  # 2 kamers x 2 pers. + 2 pers.


def test_maintenance_recounts_old_style_profiles():
    gp.link(_res("r1", phone="+32470000001", days_ago=10))
    gp.link(_res("r2", phone="+32470000001", days_ago=10))
    for rid in ("r1", "r2"):
        gp.count_stay(repo.get_reservation("lucca", rid))
    g = profiles.list_profiles("lucca")[0]
    g.stays, g.stay_periods = 2, []  # zoals geteld voor deze wijziging
    profiles.save_profile(g)
    maintenance.run("lucca")
    assert profiles.list_profiles("lucca")[0].stays == 1


def test_cancelled_guest_kept_and_counted():
    r = _res("c1", "Ann", "Test", email="ann@example.com", days_ago=60)
    r.status = ReservationStatus.CANCELLED
    repo.save_reservation(r)
    g = gp.link(r)
    assert g.cancellations == 1 and not gp.count_cancellation(repo.get_reservation("lucca", "c1"))
    maintenance.run("lucca")  # reservatie weg, gast blijft (annulering)
    assert repo.get_reservation("lucca", "c1") is None
    kept = profiles.list_profiles("lucca")
    assert [(x.first_name, x.cancellations) for x in kept] == [("Ann", 1)]
    assert maintenance.run("lucca", today=date.today() + timedelta(days=800))["guests_deleted"] == 1


def test_extra_contact_is_proposed_not_merged():
    from hotel_checkin.guests import profiles
    from hotel_checkin.processes import guest_profiles

    a = profiles.new_profile("lucca")
    a.first_name, a.last_name, a.email, a.backup_email = "Jan", "Peeters", "jan@telenet.be", "els@gmail.com"
    b = profiles.new_profile("lucca")
    b.first_name, b.last_name, b.email = "Els", "Maes", "els@gmail.com"
    profiles.save_profile(a)
    profiles.save_profile(b)
    m = guest_profiles.possible_matches("lucca")
    assert {"a": min(a.guest_id, b.guest_id), "b": max(a.guest_id, b.guest_id), "reason": "extra_contact"} in m
