"""Proces send_messages: bevestiging één keer, alleen nieuwe reservaties, in TST naar het testadres."""

from datetime import date, datetime, timedelta, timezone

import pytest

from hotel_checkin.core.models import Channel, Guest, Reservation, ReservationStatus, SendResult
from hotel_checkin.guests import repository as repo
from hotel_checkin.messaging import templates
from hotel_checkin.processes import send_messages


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    repo.use_memory_store()
    monkeypatch.setenv("APP_ENV", "tst")
    monkeypatch.setattr(send_messages, "start", lambda h: datetime(2026, 10, 30, tzinfo=timezone.utc))
    sent = []

    def fake_send(to, subject, html_body, sender=None, reply_to=None, **kw):
        sent.append((to, subject))
        return SendResult(Channel.EMAIL, to, True)
    monkeypatch.setattr(send_messages.email, "send_email", fake_send)
    return sent


def _res(rid, email="jan@example.com", arrival_in=30, status=ReservationStatus.READY_FOR_CHECKIN):
    arr = date.today() + timedelta(days=arrival_in)
    r = Reservation("lucca", rid, Guest("Jan", "Voorbeeld", email=email, language="nl"), arr,
                    arr + timedelta(days=2), status=status, booking_number="CPB-1-" + rid)
    return repo.save_reservation(r)


def test_confirmation_once(setup):
    _res("r1")
    assert send_messages.run("lucca") == 1 and send_messages.run("lucca") == 0
    assert len(setup) == 1 and "Hotel Lucca" in setup[0][1]
    assert repo.was_sent("lucca", "r1", "confirmation", "email")
    assert repo.robot_runs("lucca")[0]["task"] == "berichten"


def test_old_reservations_and_cancelled_get_nothing(setup, monkeypatch):
    monkeypatch.setattr(send_messages, "start", lambda h: datetime.now(timezone.utc) + timedelta(hours=1))
    _res("old")
    assert send_messages.run("lucca") == 0
    monkeypatch.setattr(send_messages, "start", lambda h: datetime(2026, 10, 30, tzinfo=timezone.utc))
    repo.delete_reservation("lucca", "old")
    _res("c", status=ReservationStatus.CANCELLED)
    _res("noemail", email=None)
    assert send_messages.run("lucca") == 0 and setup == []


def test_reminder_seven_days_before(setup, monkeypatch):
    # reservaties al 10 dagen gekend (vóór de dag van de herinnering), bevestiging al verstuurd
    real_now = repo._now
    monkeypatch.setattr(repo, "_now", lambda: real_now() - timedelta(days=10))
    _res("r1", arrival_in=5)
    _res("r2", arrival_in=5)
    monkeypatch.setattr(repo, "_now", real_now)
    monkeypatch.setattr(send_messages, "start", lambda h: real_now() - timedelta(days=30))
    for rid in ("r1", "r2"):
        repo.log_message("lucca", rid, "confirmation", SendResult(Channel.EMAIL, "x", True))
    repo.mark_checkin_completed("lucca", "r2", "jan@example.com", None, "nl")  # formulier ingevuld
    assert send_messages.run("lucca") == 1
    assert repo.was_sent("lucca", "r1", "reminder") and not repo.was_sent("lucca", "r2", "reminder")


def test_disabled_in_prd(monkeypatch, setup):
    monkeypatch.setenv("APP_ENV", "prd")
    _res("r1")
    assert send_messages.run("lucca") == 0 and setup == []


def test_format_date():
    d = date(2026, 11, 14)
    assert templates.format_date(d, "nl") == "zaterdag 14 november 2026"
    assert templates.format_date(d, "de") == "Samstag, 14. November 2026"


def test_late_booking_gets_only_code_mail(setup):
    _res("late", arrival_in=2)  # binnen het venster van access_code
    assert send_messages.run("lucca") == 0  # geen bevestiging, geen herinnering (code-mail volgt met Salto)
    assert not repo.was_sent("lucca", "late", "confirmation")


def test_booked_five_days_before_no_reminder(setup):
    _res("r5", arrival_in=5)  # bevestiging ja, herinnering niet (boeking kwam na de herinneringsdag)
    assert send_messages.run("lucca") == 1
    assert repo.was_sent("lucca", "r5", "confirmation") and not repo.was_sent("lucca", "r5", "reminder")
