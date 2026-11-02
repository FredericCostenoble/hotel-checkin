"""Bewaking: dagelijks overzicht, controle op het resultaat, waarschuwing als de robot stilvalt."""

from datetime import UTC, date, datetime, timedelta

import pytest

from hotel_checkin.core.models import Channel, Guest, Reservation, SendResult
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import oversight


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    repo.use_memory_store()
    monkeypatch.setenv("LUCCA_SCHAKELAARS_BERICHTEN", "true")  # hoofdschakelaar berichten aan
    mails = []
    monkeypatch.setenv("APP_ENV", "tst")
    monkeypatch.setattr(oversight.email, "send_email",
                        lambda to, subject, html_body, **k: mails.append((to, subject, html_body)) or SendResult(Channel.EMAIL, to, True))
    return mails


def _res(rid, arrival, **kw):
    r = Reservation("lucca", rid, Guest("Ann", "Peeters", email="ann@example.com", language="nl"), arrival,
                    arrival + timedelta(days=1), rooms=["16"], booking_number="CPB-" + rid, source="Booking.com", **kw)
    return repo.save_reservation(r)


def test_overview_once_in_the_morning(setup):
    today = date(2026, 11, 3)
    _res("a", today, paid=True)
    _res("b", today + timedelta(days=1))
    morning = datetime(2026, 11, 3, 7, 35, tzinfo=oversight.clock.tz("lucca"))
    assert "overzicht" in oversight.run("lucca", morning)
    to, subject, body = setup[0]
    assert to == "management@hotellucca.be" and "aankomsten 03/11" in subject
    assert "CPB-b" in body and "kamer nog niet betaald" in body  # rood: kamer niet betaald, geen code
    assert "overzicht" not in oversight.run("lucca", morning + timedelta(minutes=15))  # niet twee keer


def test_check_warns_once_for_missing_code_mail(setup):
    today = date(2026, 11, 3)
    r = _res("c", today, paid=True)
    r.access_codes = [{"room": "16", "pin": "2242"}]
    repo.save_reservation(r, fields=repo.SALTO_FIELDS)
    evening = datetime(2026, 11, 3, 17, 5, tzinfo=oversight.clock.tz("lucca"))
    done = oversight.run("lucca", evening)
    warn = [m for m in setup if m[1].startswith("WAARSCHUWING")]
    assert warn and "code-mail niet verstuurd" in warn[0][2] and any("controle 17:00" in d for d in done)
    oversight.run("lucca", evening.replace(hour=20, minute=5))  # zelfde probleem: niet opnieuw melden
    assert len([m for m in setup if m[1].startswith("WAARSCHUWING")]) == 1
    repo.log_message("lucca", "c", "access_code", SendResult(Channel.EMAIL, "ann@example.com", True))
    assert oversight.row("lucca", repo.get_reservation("lucca", "c"), today, today, True, True)["problemen"] == []


def test_robot_down_alert(setup):
    repo.log_robot_run("lucca", "nieuwe_reservaties", datetime.now(UTC) - timedelta(hours=5), True)
    repo.log_robot_run("lucca", "nieuwe_reservaties", datetime.now(UTC) - timedelta(hours=1), False, error="TimeoutError")
    assert "lukte niet meer" in oversight.robot_problem("lucca", 3)
    oversight.run("lucca", datetime(2026, 11, 3, 6, 0, tzinfo=oversight.clock.tz("lucca")))
    assert any("robot Lighthouse werkt niet" in m[1] for m in setup)
    repo.log_robot_run("lucca", "nieuwe_reservaties", datetime.now(UTC), True)
    assert oversight.robot_problem("lucca", 3) is None
