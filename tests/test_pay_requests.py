"""Betaalverzoeken in Lighthouse (processes/pay_requests.py)."""

from datetime import date, timedelta

import pytest

from hotel_checkin.core.models import Guest, Reservation
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import pay_requests as pr

TODAY = date(2026, 11, 2)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    repo.use_memory_store()
    monkeypatch.setenv("APP_ENV", "prd")
    monkeypatch.setenv("LUCCA_SCHAKELAARS_BERICHTEN", "true")


def _r(arrival_in=2, open_amount=8.4, last="Brand", rid="r1"):
    a = TODAY + timedelta(days=arrival_in)
    r = Reservation("lucca", rid, Guest("Ann", last, language="nl"), a, a + timedelta(days=1), source="Booking.com")
    r.open_amount = open_amount
    return r


def test_only_when_a_pay_mail_is_near_and_something_is_open():
    cfg = pr.workflow.config("lucca")
    assert pr.candidate(_r(arrival_in=1), TODAY, cfg)  # betaalverzoek na vertrek binnen 2 dagen
    assert pr.candidate(_r(arrival_in=30), TODAY, cfg) is None  # nog ver weg
    assert pr.candidate(_r(arrival_in=1, open_amount=0), TODAY, cfg) is None  # niets open
    done = _r(arrival_in=1)
    done.pay_link = "https://x"
    assert pr.candidate(done, TODAY, cfg) is None


def test_creates_once_and_sends_to_own_mailbox(monkeypatch):
    repo.save_reservation(_r(arrival_in=1))
    calls = []
    monkeypatch.setattr(pr.lighthouse, "create_payment_request",
                        lambda h, rid, to, tpl, lang, lh: calls.append((rid, to, tpl)) or 8.4)
    monkeypatch.setattr("hotel_checkin.messaging.mailbox.mailbox_address", lambda h: "checkin@hotellucca.be")
    result = pr.run("lucca", None, TODAY)
    assert calls == [("r1", "checkin@hotellucca.be", "Betaalverzoek")] and len(result["made"]) == 1
    assert pr.run("lucca", None, TODAY)["todo"] == 0  # één keer per reservatie


def test_tst_only_test_guest(monkeypatch):
    monkeypatch.setenv("APP_ENV", "tst")
    cfg = pr.workflow.config("lucca")
    assert pr.candidate(_r(arrival_in=1), TODAY, cfg) is None
    assert pr.candidate(_r(arrival_in=1, last="Meersseman"), TODAY, cfg)


def test_existing_link_means_no_request(monkeypatch):
    monkeypatch.setenv("APP_ENV", "tst")
    cfg = pr.workflow.config("lucca")
    r = _r(arrival_in=1, last="Meersseman")
    assert pr.candidate(r, TODAY, cfg)
    r.pay_link = "https://handmatig"
    assert pr.candidate(r, TODAY, cfg) is None  # link bestaat al, ook bij een testgast


def test_reads_open_amount_first_when_unknown(monkeypatch):
    r = _r(arrival_in=1, open_amount=None)
    repo.save_reservation(r)
    detail = _r(arrival_in=1, open_amount=8.4)
    monkeypatch.setattr(pr.lighthouse, "get_reservation", lambda h, rid, lh, contact=True: detail)
    made = []
    monkeypatch.setattr(pr.lighthouse, "create_payment_request", lambda *a: made.append(a[1]) or 8.4)
    monkeypatch.setattr("hotel_checkin.messaging.mailbox.mailbox_address", lambda h: "checkin@hotellucca.be")
    assert pr.run("lucca", None, TODAY)["made"] and made == ["r1"]


def test_pay_mail_waits_for_link_at_most_two_hours():
    from datetime import UTC, datetime

    from hotel_checkin.processes import send_messages as sm

    cfg = pr.workflow.config("lucca")
    step = next(s for s in pr.workflow.steps("lucca", "booking") if s.step == "access_code")
    r = _r(arrival_in=1)
    assert sm.waiting_for_pay_link("lucca", step, r, cfg, TODAY)  # robot gaat het verzoek maken: wachten
    r.pay_requested_at = datetime.now(UTC) - timedelta(hours=3)
    assert not sm.waiting_for_pay_link("lucca", step, r, cfg, TODAY)  # na 2 uur toch versturen
    r.pay_link = "https://pay"
    assert not sm.waiting_for_pay_link("lucca", step, r, cfg, TODAY)
