"""Lighthouse-tekst omzetten, met verzonnen voorbeeldgegevens in de opmaak van Lighthouse."""

from datetime import date, datetime

from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.pms.lighthouse_parse import (
    TZ,
    parse_date,
    parse_list_row,
    rooms_from,
    split_name,
)

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
    assert r.internal_memo is None  # tekstvak niet op de pagina: niet gekend
    r = parse_detail("lucca", "0A1B2C3D-1111-2222-3333-444455556666", {**DETAIL, "internal_memo": "\nwilt douche, geen bad"})
    assert r.internal_memo == "wilt douche, geen bad"


def test_parse_detail_cancelled_and_open():
    from hotel_checkin.pms.lighthouse_parse import parse_detail

    d = DETAIL | {"general": DETAIL["general"].replace("Status: Nieuw", "Status: Geannuleerd"),
                  "paid_text": "Transacties\nOpenstaand", "email": "", "contact_line": "Jan (XX)"}
    r = parse_detail("lucca", "x", d)
    assert r.status == ReservationStatus.CANCELLED and r.paid is False
    assert r.guest.email is None and r.guest.language == "en"


def test_list_row_country():
    r = parse_list_row("lucca", GENERAL, "Jan Voorbeeld (DE)\nBooking.com", "Superior double", HREF)
    assert (r.guest.first_name, r.guest.last_name) == ("Jan", "Voorbeeld")
    assert r.guest.country == "DE" and r.guest.language == "de"


def test_parse_contact():
    from hotel_checkin.pms.lighthouse_parse import parse_contact

    assert parse_contact('{"Email": "Jan@Example.com", "Telephone": "+49 151 2345 6789"}') == {
        "email": "jan@example.com", "phone": "+4915123456789"}
    html = '<span data-field="telephone">0470 12 34 56</span> <span data-field="email">jan@example.com</span>'
    assert parse_contact(html) == {"email": "jan@example.com", "phone": "+32470123456"}
    assert parse_contact('<span data-field="email">j***@***.com</span>') is None
    assert parse_contact("<html>login</html>") is None


def test_parse_folio_table_and_lines():
    from hotel_checkin.pms.lighthouse_parse import parse_folio

    table = ("Folio sluiten\nExtra toevoegen\n24 QUAD KAMER - 2e verdiep\n"
             "Quad kamer - STANDARD RATE BREAKFAST EXCL\t€ 215,00\nCitytax\t4 x\t€ 16,80\nTotaal\t€ 231,80\n"
             "Transacties\nOpenstaand saldo van € 231,80")
    f = parse_folio(table)
    assert f["lines"] == [{"label": "Quad kamer - STANDARD RATE BREAKFAST EXCL", "qty": None, "amount": 215.0},
                          {"label": "Citytax", "qty": 4, "amount": 16.8}]
    assert f["total"] == 231.8 and f["open"] == 231.8
    lines = ("Quad kamer\n€ 215,00\nCitytax\n4 x\n€ 16,80\nTotaal\n€ 1.231,80\n"
             "Transacties\nOverschrijving € 1.000,00\nDe reservering is volledig betaald")
    f = parse_folio(lines)
    assert f["lines"][1] == {"label": "Citytax", "qty": 4, "amount": 16.8}
    assert f["total"] == 1231.8 and f["open"] == 0.0
    assert parse_folio("") == {"lines": [], "total": None, "open": None}


def test_rate_plan_and_non_refundable():
    """Tarief uit de lijst en uit de folio; NRF = niet annuleerbaar (review 02/11)."""
    from hotel_checkin.pms.lighthouse_parse import non_refundable, rate_plans_from

    assert rate_plans_from("Superior double  ! Nog geen accommodatie.\nNRF BREAKFAST EXCL, € 335,07") == ["NRF BREAKFAST EXCL"]
    assert rate_plans_from("Dubbel kamer\t30 DOUBLE ROOM\nSTANDARD RATE, € 202,73") == ["STANDARD RATE"]
    assert rate_plans_from("Superior double - NRF BREAKFAST EXCL\nCitytax") == ["NRF BREAKFAST EXCL"]
    assert non_refundable(["NRF BREAKFAST EXCL"]) is True
    assert non_refundable(["STANDARD RATE"]) is False
    assert non_refundable(["NRF BREAKFAST EXCL", "STANDARD RATE"]) is False  # één kamer annuleerbaar
    assert non_refundable([]) is None
    r = parse_list_row("lucca", GENERAL, "Jan Voorbeeld", "Superior double  ! Nog geen accommodatie.\nNRF BREAKFAST EXCL, € 335,07", HREF)
    assert r.rate_plan == "NRF BREAKFAST EXCL" and r.non_refundable is True


def test_charge_modal_days():
    """Venster Bewerken van een ontbijtregel: kamer, aantal per nacht en de aangevinkte dagen."""
    from hotel_checkin.pms.lighthouse_parse import parse_charge_modal

    html = """<h4>Ontbijt</h4><div>22 BUDGET DOUBLE ROOM</div>
      <select name="Amount"><option value="0">0</option><option value="1" selected="selected">1</option></select>
      <label><input type="checkbox" class="js-all"> Dagen (1 van 3)</label>
      <label><input type="checkbox" name="Days" value="x"> 05 nov. 2026</label>
      <label><input type="checkbox" name="Days" value="y" checked="checked"> 06 nov. 2026</label>
      <label><input type="checkbox" name="Days" value="z"> 07 nov. 2026</label>"""
    assert parse_charge_modal(html) == {"room": "22", "per_night": 1, "days": {"2026-11-06": 1}}
    assert parse_charge_modal("<div>niets</div>") is None


def test_charge_days_like_lighthouse():
    """Zoals Lighthouse het geeft: het venster met het blok Dagen leeg, de dagen apart (CalculateDays)."""
    from hotel_checkin.pms.lighthouse_parse import charge_days_query, parse_charge_modal

    modal = """<div class="modal-body"><div>
                    22 BUDGET DOUBLE ROOM
                </div>
      <select id="accommodations-dropdown" name="SelectedAccommodation"><option value="c0" selected="selected">22 BUDGET DOUBLE ROOM - COMPACT DOUBLE ROOM</option></select>
      <select id="extras-dropdown" name="SelectedExtra"><option value="" selected>Kies extra</option>
        <option value="1156459" selected="selected">Ontbijt  (&#x20AC; 18,00 per nacht)</option></select>
      <select class="form-control" id="charge-amount" name="Amount"><option>1</option><option selected="selected">2</option></select>
      <div id="days-display"
                data-folioMaskId="f1"
                data-extraId="1156459"
                data-chargeId="20388259"
                data-accommodationId="c0"
                data-extraisdaily="true">
        <div class="days-container"></div></div>"""
    days = """<div class="days-container"><div class="form-group checkbox-container">
        <input class="js-day-checkbox form-control" name="SelectedDates" type="checkbox" value="2026-11-06T00:00:00" checked="" disabled="">
        <label>06 nov. 2026</label></div><div class="form-group checkbox-container">
        <input class="js-day-checkbox form-control" name="SelectedDates" type="checkbox" value="2026-11-07T00:00:00" disabled="">
        <label>07 nov. 2026</label></div></div>"""
    assert charge_days_query(modal) == {"accommodationId": "c0", "extraId": "1156459", "chargeId": "20388259",
                                        "folioMaskId": "f1", "isToFolio": "false"}
    assert parse_charge_modal(modal + days) == {"room": "22", "per_night": 2, "days": {"2026-11-06": 2}}


def test_charge_days_json():
    """CalculateDays geeft JSON met per dag isSelected."""
    from hotel_checkin.pms.lighthouse_parse import parse_charge

    modal = """<div>
                    22 BUDGET DOUBLE ROOM
                </div><select id="charge-amount" name="Amount"><option selected="selected">1</option><option>2</option></select>"""
    days = '[{"date":"2026-11-06T00:00:00","formattedDate":"06 nov. 2026","isSelected":true},' \
           '{"date":"2026-11-07T00:00:00","formattedDate":"07 nov. 2026","isSelected":false}]'
    assert parse_charge(modal, days) == {"room": "22", "per_night": 1, "days": {"2026-11-06": 1}}
    assert parse_charge(modal, "[]") is None


def test_room_name_not_the_rate_below():
    from hotel_checkin.pms.lighthouse_parse import room_names_from

    assert room_names_from("20 FAMILY APARTMENT\nSTANDARD RATE BREAKFAST EXCL") == {"20": "FAMILY APARTMENT"}


def test_rate_plan_in_normal_case():
    """Booking.com-tarieven in gewone tekst (CPB-4276-002390): ontbijt inbegrepen herkennen."""
    from hotel_checkin.pms.lighthouse_parse import rate_plans_from

    assert rate_plans_from("Family apartment - Non-refundable rate including breakfast BDC") == \
        ["Non-refundable rate including breakfast BDC"]
    assert rate_plans_from("Non-refundable rate including breakfast BDC, € 796,07") == \
        ["Non-refundable rate including breakfast BDC"]
    assert rate_plans_from("Citytax") == [] and rate_plans_from("Ontbijt") == []


def test_detail_group_with_different_dates_per_room():
    """Groep met kamers op verschillende data: geen datum bij Aankomst/Vertrek, dan de vroegste en laatste van de kamers."""
    import pytest

    from hotel_checkin.pms.lighthouse_parse import parse_detail

    d = {**DETAIL, "general": "Via Booking.com\nStatus: Nieuw\nAankomst op\nVertrek op",
         "rooms": [{"status": "", "text": "vr 6 nov. 2026 - zo 8 nov. 2026\n22 BUDGET DOUBLE ROOM"},
                   {"status": "", "text": "za 7 nov. 2026 - ma 9 nov. 2026\n24 QUAD ROOM"}]}
    r = parse_detail("lucca", "0A1B2C3D-1111-2222-3333-444455556666", d)
    assert (r.arrival, r.departure) == (date(2026, 11, 6), date(2026, 11, 9))
    with pytest.raises(ValueError, match="geen aankomst of vertrek: .*kamers: 'geen kamers'"):
        parse_detail("lucca", "x", {**d, "rooms": []})


def test_detail_dates_note_is_not_an_error():
    from hotel_checkin.pms.lighthouse_parse import parse_detail

    d = {**DETAIL, "general": "Via Booking.com\nStatus: Nieuw\nAankomst op verschillende\nVertrek op do 29 okt. 2026"}
    r = parse_detail("lucca", "0A1B2C3D-1111-2222-3333-444455556666", d)
    assert (r.arrival, r.departure) == (date(2026, 10, 25), date(2026, 10, 29))
    assert r.read_notes == [("data van de kamers gebruikt (25/10 tot 29/10), want Aankomst op 'verschillende', "
                             "Vertrek op 'do 29 okt. 2026'")]
    assert parse_detail("lucca", "0A1B2C3D-1111-2222-3333-444455556666", DETAIL).read_notes == []
