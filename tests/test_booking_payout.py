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
def memory():
    repo.use_memory_store()


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


def test_registers_once_and_checks_amount(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prd")
    calls = []
    stored = repo.save_reservation(_r(NRF, 5, True))
    detail = _r(NRF, 5, True)
    monkeypatch.setattr(booking_payout.lighthouse, "get_reservation", lambda h, rid, lh: detail)

    def add(h, rid, method, amount, comment, lh):
        calls.append((method, amount))
        detail.transactions = ["Overschrijving", f"€ {amount}"]
        detail.open_amount = 12.6
        return detail

    monkeypatch.setattr(booking_payout.lighthouse, "add_payment", add)
    note = booking_payout.handle("lucca", stored, None, date(2026, 11, 2))
    assert calls == [("bank_transfer", 362.0)] and "nog open 12.60" in note
    assert repo.get_reservation("lucca", stored.reservation_id).payout_registered_at
    assert booking_payout.handle("lucca", stored, None, date(2026, 11, 2)) is None and len(calls) == 1
    # bedrag klopt niet met de folio: niets registreren, één melding
    other = repo.save_reservation(_r(NRF, 6, True))
    detail2 = _r(NRF, 6, True, folio_room=300.0)
    monkeypatch.setattr(booking_payout.lighthouse, "get_reservation", lambda h, rid, lh: detail2)
    assert "klopt niet" in booking_payout.handle("lucca", other, None, date(2026, 11, 2))
    booking_payout.handle("lucca", other, None, date(2026, 11, 2))
    assert len(calls) == 1
    assert len([m for m in repo.messages_for("lucca", other.reservation_id) if not m["ok"]]) == 1


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
