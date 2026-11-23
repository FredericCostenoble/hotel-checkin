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
    b = gp.link(_res("r2", email="jan@example.com", days_ago=60))
    assert a.guest_id != b.guest_id  # alleen de naam, andere nachten: niet automatisch
    r1 = repo.mark_checkin_completed("lucca", "r1", "jan@example.com", None, "nl")
    g = gp.link(r1)
    assert len(profiles.list_profiles("lucca")) == 1 and g.from_checkin_form
    assert repo.get_reservation("lucca", "r2").guest_id == g.guest_id


def test_possible_matches_and_different():
    a = gp.link(_res("r1", "Maria", "De Voorbeeld"))
    b = gp.link(_res("r2", "DE VOORBEELD", "Maria", days_ago=60))
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
    gp.link(_res("r2", "DE VOORBEELD", "Maria", email="maria@example.be", days_ago=60))
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
    assert {"a": min(a.guest_id, b.guest_id), "b": max(a.guest_id, b.guest_id), "reason": "extra_contact",
            "contact": "els@gmail.com"} in m  # het gedeelde adres staat erbij


def _rsv(rid, first, last, email=None, phone=None):
    from datetime import date, timedelta

    from hotel_checkin.core.models import Guest, Reservation

    arr = date.today() + timedelta(days=20)
    return repo.save_reservation(Reservation("lucca", rid, Guest(first, last, email=email, phone=phone), arr,
                                             arr + timedelta(days=1)))


def test_old_address_still_recognises_guest_after_form_change():
    from hotel_checkin.processes import guest_profiles

    g = guest_profiles.link(_rsv("m1", "Jan", "Peeters", email="jan@telenet.be"))
    saved = repo.mark_checkin_completed("lucca", "m1", "jan.peeters@gmail.com", "+32470111222", "nl")
    guest_profiles.link(saved)
    # nieuwe boeking via Booking.com met het oude adres: zelfde gast
    again = guest_profiles.link(_rsv("m2", "Jan", "Peeters", email="jan@telenet.be"))
    assert again.guest_id == g.guest_id
    # zelfde gsm-nummer, andere naam (partner): niet samengevoegd, wel voorgesteld
    partner = guest_profiles.link(_rsv("m3", "Els", "Maes", phone="+32470111222"))
    assert partner.guest_id != g.guest_id
    reasons = {m["reason"] for m in guest_profiles.possible_matches("lucca")}
    assert "same_contact" in reasons


def test_relay_address_never_matches():
    from hotel_checkin.processes import guest_profiles

    a = guest_profiles.link(_rsv("b1", "Ann", "Dewit", email="ann.1@guest.booking.com"))
    r2 = _rsv("b2", "Ann", "Dewit", email="ann.1@guest.booking.com")
    r2.arrival, r2.departure = r2.arrival + timedelta(days=30), r2.departure + timedelta(days=30)
    b = guest_profiles.link(repo.save_reservation(r2))
    assert a.guest_id != b.guest_id  # alleen voorgesteld als zelfde naam, nooit automatisch


@pytest.mark.parametrize("a,b,reason", [
    (("Jan", "Van den Broucke"), ("Jan", "Vandenbroucke"), "same_name"),
    (("Pieter", "De Smet"), ("Pieter", "Desmet"), "same_name"),
    (("Maria", "Peeters"), ("Marie", "Peters"), "similar_name"),
    (("J.", "Peeters"), ("Jan", "Peeters"), "similar_name"),
    (("Anna Maria", "Peeters"), ("Anna", "Peeters"), "similar_name"),
    (("Kathy", "Janssens"), ("Cathy", "Jansens"), "similar_name"),
    (("Tom", "Maes"), ("Tim", "Maes"), None),
    (("Jan", "Peeters"), ("Els", "Peeters"), None),
])
def test_name_variants(a, b, reason):
    """Tussenvoegsels, klank, initialen en extra voornamen (review 01/11)."""
    from hotel_checkin.guests import profiles
    from hotel_checkin.processes import guest_profiles

    for first, last in (a, b):
        g = profiles.new_profile("lucca")
        g.first_name, g.last_name, g.country = first, last, "BE"
        profiles.save_profile(g)
    found = [m["reason"] for m in guest_profiles.possible_matches("lucca")]
    assert found == ([reason] if reason else [])


def test_placeholder_phone_of_expedia_never_matches():
    """Expedia geeft gasten het nepnummer +11111111111111: geen koppeling, geen voorstel, geen bericht."""
    from hotel_checkin.checkin.service import normalize_phone, placeholder_phone

    assert placeholder_phone("+11111111111111") and placeholder_phone("+32000000000")
    assert not placeholder_phone("+32470000001") and normalize_phone("+11111111111111") is None
    a = gp.link(_res("e1", "Bas", "Schutte", email="f80yuq3f8k@m.expediapartnercentral.com", phone="+11111111111111",
                     source="Expedia"))
    b = gp.link(_res("e2", "Eva", "Krikken", email="tlvudwu8y9@m.expediapartnercentral.com", phone="+11111111111111",
                     source="Expedia"))
    assert a.guest_id != b.guest_id and gp.possible_matches("lucca") == []


def test_same_name_same_nights_is_same_guest():
    """Opnieuw geboekt na annulering, of een groep met meer kamers: andere doorstuuradressen, zelfde naam en nachten."""
    a = gp.link(_res("e1", "Sophia", "Sharp", email="x1@m.expediapartnercentral.com", status=ReservationStatus.CANCELLED))
    b = gp.link(_res("e2", "Sophia", "Sharp", email="x2@m.expediapartnercentral.com"))
    c = gp.link(_res("e3", "SHARP", "Sophia", email="x3@guest.booking.com", rooms=["14"]))
    assert a.guest_id == b.guest_id == c.guest_id
    assert len(profiles.list_profiles("lucca")) == 1 and gp.possible_matches("lucca") == []


def test_maintenance_merges_existing_same_stay_profiles_but_not_marked_different():
    ids = []
    for rid in ("s1", "s2", "s3"):
        r = _res(rid, "Sophia", "Sharp")
        g = profiles.new_profile("lucca")
        g.first_name, g.last_name, g.country, g.reservation_ids = "Sophia", "Sharp", "BE", [rid]
        profiles.save_profile(g)
        r.guest_id = g.guest_id
        repo.save_reservation(r, fields=("guest_id",))
        ids.append(g.guest_id)
    later = _res("s4", "Sophia", "Sharp", days_ago=90)  # andere nachten: niet samen
    g = profiles.new_profile("lucca")
    g.first_name, g.last_name, g.reservation_ids = "Sophia", "Sharp", ["s4"]
    profiles.save_profile(g)
    later.guest_id = g.guest_id
    repo.save_reservation(later, fields=("guest_id",))
    profiles.mark_different("lucca", ids[0], ids[2])
    assert gp.merge_same_stay("lucca") == 1  # s2 gaat bij s1 of bij s3; s1 en s3 komen nooit samen
    left = {r.reservation_id: r.guest_id for r in repo.list_reservations("lucca")}
    assert left["s2"] in (left["s1"], left["s3"]) and left["s1"] != left["s3"]
    assert left["s4"] not in (left["s1"], left["s3"]) and len(profiles.list_profiles("lucca")) == 3


def test_merge_once_only_once():
    for rid in ("o1", "o2"):
        r = _res(rid, "Sophia", "Sharp")
        g = profiles.new_profile("lucca")
        g.first_name, g.last_name, g.reservation_ids = "Sophia", "Sharp", [rid]
        profiles.save_profile(g)
        r.guest_id = g.guest_id
        repo.save_reservation(r, fields=("guest_id",))
    assert maintenance.merge_once("lucca") == 1
    assert maintenance.merge_once("lucca") is None and len(profiles.list_profiles("lucca")) == 1


def test_similar_first_name_alone_is_not_the_same_guest():
    """Joanne en Johannes lijken op elkaar, maar met een andere familienaam is het niet dezelfde gast."""
    g = gp.link(_res("j1", "Johannes", "Lindblom"))
    assert not gp.names_fit("Joanne", "Mitchell", g)
    assert gp.names_fit("Jan", "Verschraeghen", profiles.get_profile("lucca", gp.link(_res("v1", "Jan", "Verschraegen")).guest_id))


def test_split_wrong_link_from_before_the_placeholder_fix():
    """Vroeger gekoppeld op het nepnummer van Expedia: Mitchell Joanne in het profiel van Lindblom Johannes.
    Het onderhoud maakt haar los, geeft haar een eigen profiel en telt haar verblijf daar (niet meer bij hem)."""
    gp.link(_res("l1", "Johannes", "Lindblom", phone="+11111111111"))
    m = _res("m1", "Joanne", "Mitchell", phone="+11111111111", days_ago=4, rooms=["33"])
    g = profiles.list_profiles("lucca")[0]
    m.guest_id = g.guest_id  # zoals de foute koppeling van vroeger
    repo.save_reservation(m)
    g.reservation_ids.append("m1")
    profiles.save_profile(g)
    assert gp.count_stay(repo.get_reservation("lucca", "m1"))
    g = profiles.get_profile("lucca", g.guest_id)
    assert g.stays == 1 and g.rooms == {"33": 1}
    maintenance.run("lucca")
    g = profiles.get_profile("lucca", g.guest_id)
    assert g.reservation_ids == ["l1"] and g.stays == 0 and g.rooms == {} and g.stay_periods == []
    other = profiles.get_profile("lucca", repo.get_reservation("lucca", "m1").guest_id)
    assert other.guest_id != g.guest_id and other.last_name == "Mitchell" and other.stays == 1


def test_detach_gives_own_profile_or_the_right_one_and_never_back():
    """Ontkoppelen: eigen profiel, of het profiel dat zeker dezelfde gast is; nooit terug bij het oude."""
    gp.link(_res("a1", "Jan", "Voorbeeld", email="jan@example.com"))
    piet = gp.link(_res("p1", "Piet", "Anders", email="piet@example.com", days_ago=40))
    wrong = _res("p2", "Piet", "Anders", email="piet@example.com", days_ago=5)
    g = profiles.list_profiles("lucca")
    jan = next(x for x in g if x.last_name == "Voorbeeld")
    wrong.guest_id = jan.guest_id
    repo.save_reservation(wrong)
    jan.reservation_ids.append("p2")
    profiles.save_profile(jan)
    gp.count_stay(repo.get_reservation("lucca", "p2"))
    new = gp.detach("lucca", "p2")
    assert new.guest_id == piet.guest_id and sorted(new.reservation_ids) == ["p1", "p2"] and new.stays == 1
    assert profiles.get_profile("lucca", jan.guest_id).reservation_ids == ["a1"]
    assert profiles.get_profile("lucca", jan.guest_id).stays == 0
    assert gp.detach("lucca", "a1") is None  # enige reservatie van Jan: niets te ontkoppelen


def test_marketing_per_address_hotel_cannot_override_the_guest():
    """Vinkje Marketing: het hotel kan het uit- en weer aanzetten, maar niet aanzetten als de gast het zelf weigerde."""
    from hotel_checkin.admin import service as admin

    assert admin.set_marketing("lucca", "jan@example.com", False)["ok"]
    assert repo.is_opted_out("lucca", "jan@example.com") and repo.opt_out_source("lucca", "jan@example.com") == "monitor"
    assert admin.set_marketing("lucca", "jan@example.com", True)["ok"] and not repo.is_opted_out("lucca", "jan@example.com")
    repo.add_opt_out("lucca", "piet@example.com", "checkin_form")
    r = admin.set_marketing("lucca", "piet@example.com", True)
    assert not r["ok"] and "gast" in r["error"] and repo.is_opted_out("lucca", "piet@example.com")


def test_robot_follows_the_ticks_per_address_and_merge_keeps_them():
    """De robot volgt de vinkjes Verblijf: het hotel kan het doorstuuradres in plaats van het eigen adres laten gebruiken,
    of een gsm-nummer uitzetten. Bij samenvoegen blijven de vinkjes van beide gasten (uit gaat voor)."""
    from hotel_checkin.admin import service as admin
    from hotel_checkin.processes import send_messages as sm

    r = _res("x1", "Jan", "Voorbeeld", email="jan@example.com", phone="+32470000009", source="Expedia")
    r.guest.relay_email = "abc@m.expediapartnercentral.com"
    r.guest.phone_consent = ["+32470000009"]
    repo.save_reservation(r)
    g = gp.link(repo.get_reservation("lucca", "x1"))
    r = repo.get_reservation("lucca", "x1")
    assert sm.recipients(r, "email") == ["jan@example.com"]
    assert admin.set_contact_pref("lucca", g.guest_id, "email", "jan@example.com", False)
    assert admin.set_contact_pref("lucca", g.guest_id, "email", "abc@m.expediapartnercentral.com", True)
    assert sm.recipients(r, "email") == ["abc@m.expediapartnercentral.com"]  # omgewisseld
    assert admin.set_contact_pref("lucca", g.guest_id, "whatsapp", "+32470000009", False)
    assert sm.recipients(r, "phone") == ["+32470000009"]  # sms staat nog aan
    prefs, muted, _e, _p = sm.contact_prefs(r)
    assert not sm.use_channel(prefs, muted, "whatsapp", "+32470000009") and sm.use_channel(prefs, muted, "sms", "+32470000009")
    assert not admin.set_contact_pref("lucca", g.guest_id, "sms", "+11111111111", True)  # nepnummer: nooit
    other = gp.link(_res("x2", "Jan", "Voorbeeld", email="jan2@example.com", days_ago=60))
    other.contact_prefs = {"email:jan@example.com": True, "email:jan2@example.com": False}
    profiles.save_profile(other)
    kept = gp.merge("lucca", g.guest_id, other.guest_id)
    assert kept.contact_prefs["email:jan@example.com"] is False  # bij de ene uit: uit
    assert kept.contact_prefs["email:jan2@example.com"] is False and kept.contact_prefs["email:abc@m.expediapartnercentral.com"]


def test_shared_number_of_booking_site_is_not_a_reason():
    """Het vaste nummer van Expedia (+61730836162) staat bij veel verschillende gasten: geen voorstel om samen te voegen."""
    from hotel_checkin.guests import profiles
    from hotel_checkin.processes import guest_profiles

    for first, last in (("Cheryl", "Hall"), ("Paul", "Goldberg"), ("Amy", "Oshea")):
        g = profiles.new_profile("lucca")
        g.first_name, g.last_name, g.phone = first, last, "+61730836162"
        profiles.save_profile(g)
    assert not [m for m in guest_profiles.possible_matches("lucca") if m.get("contact") == "+61730836162"]
