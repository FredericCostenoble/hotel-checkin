"""Overschrijving van Booking.com, betaallink uit de mail van Lighthouse (review 02/11)."""

from datetime import date, timedelta

import pytest

from hotel_checkin.core.models import Guest, Reservation
from hotel_checkin.guests import repository as repo
from hotel_checkin.pms.lighthouse_mail import parse_payment_mail
from hotel_checkin.pms.lighthouse_parse import booking_prepay, free_cancel_days
from hotel_checkin.processes import booking_payout, mail_trigger

NRF = ("Opmerkingen:\n ResGlobalInfo Booking.com PrePay:payment_on_Booking.com (Payout type: BankTransfer)362 EUR"
       "** THIS RESERVATION HAS BEEN PRE-PAID **\nAnnuleringsvoorwaarden : De gast betaalt de totaalprijs van de "
       "reservering als hij/zij annuleert op elk moment.\nAlready collected by Booking.com: 362.00 EUR\n"
       "Still to be collected from the guest: 12.60 EUR")
FLEX = ("PrePay:payment_on_Booking.com (Payout type: BankTransfer)1054,8 EUR** THIS RESERVATION HAS BEEN PRE-PAID **"
        "\nAnnuleringsvoorwaarden : De gast kan gratis annuleren tot 3 dagen voor aankomst.")
MAIL = """Beste
Betaal uw openstaande saldo
Als de knop in deze e-mail niet zichtbaar is, kopieer dan de volgende URL en plak deze direct in uw browser::
https://reservationmanager.mylighthouse.com/visitor/payment/99831d8b-4faa-4c66-b354-e431bb8e22ef
OVERZICHT RESERVERING
Reserveringsnummer
CPB-4276-002755
Totaal
€ 118,40"""


@pytest.fixture(autouse=True)
def memory(monkeypatch):
    repo.use_memory_store()
    monkeypatch.setenv("LUCCA_SCHAKELAARS_OVERSCHRIJVINGEN", "true")  # hoofdschakelaar aan


def test_remark_amount_and_cancellation():
    assert booking_prepay(NRF) == 362.0 and booking_prepay(FLEX) == 1054.8
    assert booking_prepay("Opmerkingen: gast komt laat") is None
    assert free_cancel_days(NRF) == 0 and free_cancel_days(FLEX) == 3 and free_cancel_days("") is None


def _r(remarks, arrival_in, non_refundable=None, folio_room=362.0, last="Brand"):
    a = date(2026, 11, 2) + timedelta(days=arrival_in)
    r = Reservation("lucca", f"r{arrival_in}{last}", Guest("Ann", last), a, a + timedelta(days=1),
                    source="Booking.com", remarks=remarks, non_refundable=non_refundable)
    r.folio = [{"label": "Quad kamer - NRF BREAKFAST EXCL", "qty": None, "amount": folio_room},
               {"label": "Citytax", "qty": 3, "amount": 12.6}]
    r.open_amount = round(folio_room + 12.6, 2)  # nog niets betaald
    return r


def test_when_and_how_much():
    today = date(2026, 11, 2)
    assert booking_payout.due(_r(NRF, 50), today)  # niet annuleerbaar: meteen
    assert not booking_payout.due(_r(FLEX, 10), today)  # annuleerbaar: nog niet
    assert booking_payout.due(_r(FLEX, 2), today)  # 2 dagen voor aankomst
    assert booking_payout.room_price(_r(NRF, 5)) == 362.0  # zonder toeristenbelasting
    assert booking_payout.amount_for(_r(NRF, 5)) == 362.0
    # testgast zonder opmerking van Booking.com: de kamerprijs, om te oefenen
    assert booking_payout.amount_for(_r(None, 5, folio_room=110.0, last="meersseman")) == 110.0
    assert booking_payout.amount_for(_r(None, 5, folio_room=110.0)) is None


def test_only_prd_or_test_guest(monkeypatch):
    cfg = __import__("hotel_checkin.core.workflow", fromlist=["config"]).config("lucca")
    today = date(2026, 11, 2)
    monkeypatch.setenv("APP_ENV", "tst")
    assert not booking_payout.candidate(_r(NRF, 5, True), cfg, today)  # echte gast in TST: alleen lezen
    assert booking_payout.candidate(_r(NRF, 5, True, last="Meersseman"), cfg, today)
    monkeypatch.setenv("APP_ENV", "prd")
    assert booking_payout.candidate(_r(NRF, 5, True), cfg, today)


VCC = ("ResGlobalInfo Booking.com Virtual credit card ** THIS RESERVATION HAS BEEN PRE-PAID **\n"
       "Annuleringsvoorwaarden : De gast betaalt de totaalprijs van de reservering als hij/zij annuleert op elk moment.")


def test_virtual_card_room_price_without_extras():
    r = _r(VCC, 30, True)
    r.folio.append({"label": "Ontbijt", "qty": 2, "amount": 36.0})  # extra: blijft open
    assert booking_payout.virtual_card(VCC) and not booking_payout.virtual_card(NRF)
    assert booking_payout.room_price(r) == 362.0  # alleen de kamerlijn
    assert booking_payout.amount_for(r) == 362.0  # geen bedrag in de opmerking: de kamerprijs


def test_main_switch_and_which_reservations(monkeypatch):
    cfg = __import__("hotel_checkin.core.workflow", fromlist=["config"]).config("lucca")
    today = date(2026, 11, 2)
    monkeypatch.setenv("APP_ENV", "prd")
    assert booking_payout.candidate(_r(None, 40), cfg, today)  # nieuw, nog niet gelezen: meteen lezen
    assert booking_payout.candidate(_r(NRF, 40, True), cfg, today)  # niet annuleerbaar: meteen
    assert booking_payout.candidate(_r(VCC, 40, True), cfg, today)
    assert not booking_payout.candidate(_r(FLEX, 10, False), cfg, today)  # annuleerbaar: nog niet
    assert booking_payout.candidate(_r(FLEX, 2, False), cfg, today)  # 2 dagen voor aankomst: wel
    assert not booking_payout.candidate(_r("Opmerkingen: gast betaalt zelf", 1, False), cfg, today)
    monkeypatch.delenv("LUCCA_SCHAKELAARS_OVERSCHRIJVINGEN")  # hoofdschakelaar standaard uit
    assert not booking_payout.candidate(_r(NRF, 40, True), cfg, today)


def test_registers_once_and_checks_amount(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prd")
    calls = []
    stored = repo.save_reservation(_r(NRF, 5, True))
    detail = _r(NRF, 5, True)
    monkeypatch.setattr(booking_payout.lighthouse, "get_reservation", lambda h, rid, lh: detail)

    def add(h, rid, method, amount, comment, lh, min_open=None):
        assert min_open == amount  # vlak voor het klikken nog eens het saldo nakijken
        calls.append((method, amount))
        detail.transactions = ["Overschrijving", f"€ {amount}"]
        detail.open_amount = 12.6
        return detail

    monkeypatch.setattr(booking_payout.lighthouse, "add_payment", add)
    status, note = booking_payout.handle("lucca", stored, None, date(2026, 11, 2))
    assert status == "registered" and calls == [("bank_transfer", 362.0)] and "nog open 12.60" in note
    assert repo.get_reservation("lucca", stored.reservation_id).payout_registered_at
    assert booking_payout.handle("lucca", stored, None, date(2026, 11, 2))[0] == "already" and len(calls) == 1
    # bedrag klopt niet met de folio: niets registreren, één melding
    other = repo.save_reservation(_r(NRF, 6, True))
    detail2 = _r(NRF, 6, True, folio_room=300.0)
    monkeypatch.setattr(booking_payout.lighthouse, "get_reservation", lambda h, rid, lh: detail2)
    assert booking_payout.handle("lucca", other, None, date(2026, 11, 2))[0] == "problem"
    booking_payout.handle("lucca", other, None, date(2026, 11, 2))
    assert len(calls) == 1
    assert len([m for m in repo.messages_for("lucca", other.reservation_id) if not m["ok"]]) == 1


def test_never_more_than_open_and_booking_amount_checked(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prd")
    calls = []
    monkeypatch.setattr(booking_payout.lighthouse, "add_payment", lambda *a, **k: calls.append(a))
    # virtuele kaart al aangerekend aan de balie (geen Overschrijving): nog maar de toeristenbelasting open
    stored = repo.save_reservation(_r(VCC, 5, True))
    detail = _r(VCC, 5, True)
    detail.open_amount = 12.6
    monkeypatch.setattr(booking_payout.lighthouse, "get_reservation", lambda h, rid, lh: detail)
    assert "open" in booking_payout.handle("lucca", stored, None, date(2026, 11, 2))[1]
    # saldo niet gelezen (transacties niet geladen): niets doen
    detail.open_amount = None
    assert "niet gelezen" in booking_payout.handle("lucca", stored, None, date(2026, 11, 2))[1]
    # Booking.com vermeldt een ander geïnd bedrag dan de kamerprijs
    detail2 = _r(VCC + "\nAlready collected by Booking.com: 300.00 EUR", 5, True)
    monkeypatch.setattr(booking_payout.lighthouse, "get_reservation", lambda h, rid, lh: detail2)
    assert "geïnd 300.00" in booking_payout.handle("lucca", stored, None, date(2026, 11, 2))[1]
    assert calls == []


def test_flexible_rate_not_read_until_two_days(monkeypatch):
    cfg = __import__("hotel_checkin.core.workflow", fromlist=["config"]).config("lucca")
    monkeypatch.setenv("APP_ENV", "prd")
    today = date(2026, 11, 2)
    assert not booking_payout.candidate(_r(None, 30, False), cfg, today)  # STANDARD RATE: pas 2 dagen ervoor
    assert booking_payout.candidate(_r(None, 2, False), cfg, today)
    assert booking_payout.candidate(_r(None, 30, True), cfg, today)  # NRF: meteen


def test_run_summary_for_robot_log(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prd")
    repo.save_reservation(_r(NRF, 5, True))
    repo.save_reservation(_r(FLEX, 1, False, folio_room=1054.8, last="Flex"))
    details = {"r5Brand": _r(NRF, 5, True), "r1Flex": _r(FLEX, 1, False, folio_room=1054.8, last="Flex")}
    monkeypatch.setattr(booking_payout.lighthouse, "get_reservation", lambda h, rid, lh: details[rid])

    def add(h, rid, method, amount, comment, lh, min_open=None):
        details[rid].transactions = ["Overschrijving"]
        details[rid].open_amount = 12.6
        return details[rid]

    monkeypatch.setattr(booking_payout.lighthouse, "add_payment", add)
    logged = []
    monkeypatch.setattr(booking_payout.guests, "log_robot_run", lambda *a, **k: logged.append(a))
    result = booking_payout.run("lucca", None, date(2026, 11, 2))
    booking_payout.log_run("lucca", __import__("datetime").datetime.now(), result)
    assert result["read"] == 2 and result["counts"]["registered"] == 2
    note = logged[0][-1]
    assert "2 reservaties van Booking.com gelezen" in note and "2 overschrijving(en) geregistreerd" in note


def test_only_future_reservations(monkeypatch):
    cfg = __import__("hotel_checkin.core.workflow", fromlist=["config"]).config("lucca")
    monkeypatch.setenv("APP_ENV", "prd")
    assert not booking_payout.candidate(_r(NRF, -1, True), cfg, date(2026, 11, 2))  # al aangekomen
    assert booking_payout.candidate(_r(NRF, 0, True), cfg, date(2026, 11, 2))  # komt vandaag


def test_payment_mail_link_saved_and_moved(monkeypatch):
    p = parse_payment_mail("Betaalverzoek", MAIL)
    assert p.booking_number == "CPB-4276-002755" and p.link.endswith("e431bb8e22ef") and p.amount == 118.4
    assert parse_payment_mail("Vraag", "Hallo, hebben jullie parking?") is None
    r = _r(None, 5, last="meersseman")
    r.booking_number = "CPB-4276-002755"
    repo.save_reservation(r)
    moved = []
    monkeypatch.setattr(mail_trigger.mailbox, "move_message", lambda h, mid, folder: moved.append(folder) or True)
    assert mail_trigger._payment_links("lucca", [{"id": "m1", "subject": "x", "text": MAIL}]) == 1
    assert repo.get_reservation("lucca", r.reservation_id).pay_link.endswith("e431bb8e22ef")
    assert moved == ["Betaalverzoeken"]


def test_door_code_line_on_top_keeps_rest():
    """Lighthouse: "Deur Pin code: ..." bovenaan de opmerking, de rest blijft staan (review 02/11)."""
    from hotel_checkin.pms.lighthouse_parse import door_code_line, with_door_codes

    booking = "\nResGlobalInfo\n Booking.com\n PrePay:payment_on_Booking.com (Payout type: BankTransfer)362 EUR"
    one = door_code_line([("16", "2242")])
    assert one == "Deur Pin code: 2242"
    assert with_door_codes(booking, one) == "Deur Pin code: 2242 |\n" + booking
    assert with_door_codes("", one) == "Deur Pin code: 2242"
    two = door_code_line([("16", "2242"), ("21", "9911")])
    assert two == "Deur Pin code: kamer 16: 2242, kamer 21: 9911"
    # nieuwe codes (bv. kamer erbij): onze vorige regel vervangen, niet verdubbelen
    assert with_door_codes(with_door_codes(booking, one), two) == two + " |\n" + booking


def test_pms_sync_only_with_codes_and_allowed(monkeypatch):
    from hotel_checkin.processes import pms_sync

    monkeypatch.setenv("APP_ENV", "tst")
    r = _r(None, 5, last="meersseman")
    assert not pms_sync.candidate(r)  # nog geen code
    r.access_codes = [{"room": "16", "pin": "2242"}]
    assert pms_sync.candidate(r)
    written, statuses = [], []
    monkeypatch.setattr(pms_sync.lighthouse, "set_comments", lambda h, rid, compose, lh: written.append(compose("oud")))
    detail = _r(None, 5, last="meersseman")
    detail.room_statuses = ["none"]
    monkeypatch.setattr(pms_sync.lighthouse, "get_reservation", lambda h, rid, lh: detail)
    monkeypatch.setattr(pms_sync.lighthouse, "set_room_status", lambda h, rid, s, lh: statuses.append(s) or [s])
    repo.save_reservation(r)
    assert "KLAAR OM IN TE CHECKEN" in pms_sync.handle("lucca", r, None)
    assert written == ["Deur Pin code: 2242 |\noud"] and statuses == ["readyforcheckin"]
    assert not pms_sync.candidate(repo.get_reservation("lucca", r.reservation_id))  # klaar, niet opnieuw
    other = _r(None, 6)
    other.access_codes = [{"room": "16", "pin": "1"}]
    assert not pms_sync.candidate(other)  # echte gast in TST: alleen lezen
