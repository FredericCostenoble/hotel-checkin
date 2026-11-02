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
