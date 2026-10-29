"""Lighthouse-tekst omzetten, met verzonnen voorbeeldgegevens in de opmaak van Lighthouse."""

from datetime import date, datetime

from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.pms.lighthouse_parse import TZ, parse_date, parse_list_row, rooms_from, split_name

GENERAL = """ID CPB-4276-009999
Status Nieuw
Via Expedia (1234567890)
Type reis Vakantie
Gemaakt op 29 okt. 2026 15:44
Aantal gasten 2
Aantal accommodaties 1
Verblijf donderdag, 22 apr. 2027 - zaterdag, 24 apr. 2027 (2 Nachten)
Verwacht om 14:30
Creditcard invullen"""

HREF = "https://reservationmanager.mylighthouse.com/Customer/Reservations/Detail/0A1B2C3D-1111-2222-3333-444455556666"


def test_parse_list_row():
    r = parse_list_row("lucca", GENERAL, "Jan Voorbeeld", "Superior double  ! Nog geen accommodatie.\nNRF BREAKFAST EXCL, € 335,07\n\nTotaalprijs € 351,87", HREF)
    assert r.reservation_id == "0a1b2c3d-1111-2222-3333-444455556666"
    assert r.booking_number == "CPB-4276-009999" and r.pms_status == "Nieuw"
    assert r.status == ReservationStatus.READY_FOR_CHECKIN
    assert r.source == "Expedia" and r.guest_count == 2
    assert (r.arrival, r.departure) == (date(2027, 4, 22), date(2027, 4, 24))
    assert r.booked_at == datetime(2026, 10, 29, 15, 44, tzinfo=TZ)
    assert (r.guest.first_name, r.guest.last_name) == ("Jan", "Voorbeeld")
    assert r.room_type == "Superior double" and r.rooms == []


def test_cancelled_and_assigned_room():
    general = GENERAL.replace("Status Nieuw", "Status Geannuleerd")
    r = parse_list_row("lucca", general, "MARIA DE VOORBEELD", "Dubbel kamer\t30 DOUBLE ROOM\nSTANDARD RATE, € 202,73", HREF)
    assert r.status == ReservationStatus.CANCELLED
    assert r.rooms == ["30"] and r.room_type == "Dubbel kamer"
    assert r.guest.last_name == "DE VOORBEELD"


def test_helpers():
    assert parse_date("vrijdag, 07 mei 2027") == date(2027, 5, 7)
    assert parse_date("1 sept. 2026") == date(2026, 9, 1)
    assert rooms_from("Superior double\n11 - SUPERIOR DOUBLE ROOM\nNRF BREAKFAST INCL, € 10") == ["11"]
    assert split_name("Madonna") == ("", "Madonna")


def test_label_on_separate_line():
    general = GENERAL.replace("Verblijf donderdag", "Verblijf\ndonderdag")
    r = parse_list_row("lucca", general, "Jan Voorbeeld", "Superior double", HREF)
    assert r.arrival == date(2027, 4, 22)


def test_missing_stay_gives_clear_error():
    import pytest

    with pytest.raises(ValueError, match="geen verblijfsdata"):
        parse_list_row("lucca", "ID CPB-1-2\nStatus Nieuw", "Jan", "x", HREF)


def test_label_glued_to_value():
    glued = "\n".join(line.replace(" ", "", 1) if not line.startswith(("Type", "Gemaakt", "Aantal", "Verwacht")) else line
                      for line in GENERAL.splitlines())
    glued = glued.replace("Gemaakt op ", "Gemaakt op").replace("Aantal gasten ", "Aantal gasten")
    r = parse_list_row("lucca", glued, "Jan Voorbeeld", "Superior double", HREF)
    assert r.booking_number == "CPB-4276-009999" and r.pms_status == "Nieuw"
    assert r.arrival == date(2027, 4, 22) and r.guest_count == 2
    assert r.booked_at.hour == 15


DETAIL = {
    "title": "Reservering  CPB-4276-001258 - Jan Voorbeeld",
    "contact_name": "Jan Voorbeeld",
    "contact_line": "Jan Voorbeeld (DE)",
    "phone": "+49 151 2345 6789",
    "email": "Jan@Example.com",
    "general": "Via Booking.com\nStatus: Nieuw\nType reis: Vakantie\nGemaakt op dinsdag, 24 feb. 2026 om 18:51\n"
               "Aankomst op zondag, 25 okt. 2026 om 14:30\nVertrek op donderdag, 29 okt. 2026",
    "rooms": [{"status": "INGECHECKT", "text": "zo 25 okt. 2026 - do 29 okt. 2026\n15 DOUBLE ROOM"},
              {"status": "INGECHECKT", "text": "zo 25 okt. 2026 - do 29 okt. 2026\n16 TWIN ROOM"}],
    "paid_text": "Transacties\nVolledig betaald\nVisa",
}


def test_parse_detail():
    from hotel_checkin.pms.lighthouse_parse import parse_detail

    r = parse_detail("lucca", "0A1B2C3D-1111-2222-3333-444455556666", DETAIL)
    assert r.guest.email == "jan@example.com" and r.guest.phone == "+4915123456789"
    assert r.guest.country == "DE" and r.guest.language == "de"
    assert (r.arrival, r.departure) == (date(2026, 10, 25), date(2026, 10, 29))
    assert r.rooms == ["15", "16"] and r.paid is True
    assert r.status == ReservationStatus.CHECKED_IN and r.source == "Booking.com"
    assert r.booking_number == "CPB-4276-001258" and r.pms_status == "Nieuw"


def test_parse_detail_cancelled_and_open():
    from hotel_checkin.pms.lighthouse_parse import parse_detail

    d = DETAIL | {"general": DETAIL["general"].replace("Status: Nieuw", "Status: Geannuleerd"),
                  "paid_text": "Transacties\nOpenstaand", "email": "", "contact_line": "Jan (XX)"}
    r = parse_detail("lucca", "x", d)
    assert r.status == ReservationStatus.CANCELLED and r.paid is False
    assert r.guest.email is None and r.guest.language == "en"
