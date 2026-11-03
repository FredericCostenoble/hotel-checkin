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
    assert any("overzicht" in d for d in oversight.run("lucca", morning))
    to, subject, body = setup[0]
    assert to == "management@hotellucca.be" and "aankomsten 03/11" in subject
    assert "CPB-b" in body and "betaalt nog" in body  # grijs: nog niet betaald is geen fout
    assert "(1 probleem)" in subject  # alleen CPB-a (betaald, geen code-mail); CPB-b telt niet mee
    assert not any("overzicht" in d for d in oversight.run("lucca", morning + timedelta(minutes=15)))  # niet twee keer


def _with(monkeypatch, **extra):
    """Bewaking met extra instellingen (standaard: alleen het ochtendoverzicht)."""
    base = oversight.settings
    monkeypatch.setattr(oversight, "settings", lambda h: base(h) | extra)


def test_only_morning_mail_by_default(setup):
    evening = datetime(2026, 11, 3, 17, 5, tzinfo=oversight.clock.tz("lucca"))
    repo.log_robot_run("lucca", "nieuwe_reservaties", datetime.now(UTC) - timedelta(hours=5), False, error="TimeoutError")
    assert oversight.run("lucca", evening) == [] or all("overzicht" in d for d in oversight.run("lucca", evening))
    assert not [m for m in setup if "WAARSCHUWING" in m[1]]  # geen controle- of robotmail


def test_overview_tells_what_happened(setup):
    repo.log_robot_run("lucca", "overschrijving_booking", datetime.now(UTC) - timedelta(hours=2), True, 5, 2, "x")
    repo.log_robot_run("lucca", "ontbijt_labels", datetime.now(UTC) - timedelta(hours=2), True, 3, 1, "y", skipped=1)
    lines = oversight.activity("lucca")
    assert "2 overschrijving(en) geregistreerd" in lines[0] and "1 ontbijtlabel(s) gezet" in lines[0]
    assert lines[1].startswith("Wat misliep: Ontbijt labels: y")


def test_same_problem_counted_once(setup):
    for _ in range(3):
        repo.log_robot_run("lucca", "meldingen", datetime.now(UTC) - timedelta(hours=1), False, 1, 0, "robot niet gestart")
    line = oversight.activity("lucca")[1]
    assert line.count("robot niet gestart") == 1 and "(3 keer)" in line


def test_check_warns_once_for_missing_code_mail(setup, monkeypatch):
    _with(monkeypatch, checks=["17:00", "20:00"])
    today = date(2026, 11, 3)
    r = _res("c", today, paid=True)
    r.access_codes = [{"room": "16", "pin": "2242"}]
    repo.save_reservation(r, fields=repo.SALTO_FIELDS)
    evening = datetime(2026, 11, 3, 17, 5, tzinfo=oversight.clock.tz("lucca"))
    done = oversight.run("lucca", evening)
    warn = [m for m in setup if "WAARSCHUWING" in m[1]]
    assert warn and "code-mail niet verstuurd" in warn[0][2] and any("controle van 17:00" in d for d in done)
    oversight.run("lucca", evening.replace(hour=20, minute=5))  # zelfde probleem: niet opnieuw melden
    assert len([m for m in setup if "WAARSCHUWING" in m[1]]) == 1
    repo.log_message("lucca", "c", "access_code", SendResult(Channel.EMAIL, "ann@example.com", True))
    assert oversight.row("lucca", repo.get_reservation("lucca", "c"), today, today, True, True)["problemen"] == []


def test_robot_down_alert(setup, monkeypatch):
    _with(monkeypatch, robot_alert=True)
    repo.log_robot_run("lucca", "nieuwe_reservaties", datetime.now(UTC) - timedelta(hours=5), True)
    repo.log_robot_run("lucca", "nieuwe_reservaties", datetime.now(UTC) - timedelta(hours=1), False, error="TimeoutError")
    assert "lukte niet meer" in oversight.robot_problem("lucca", 3)
    oversight.run("lucca", datetime(2026, 11, 3, 6, 0, tzinfo=oversight.clock.tz("lucca")))
    assert any("robot Lighthouse werkt niet" in m[1] for m in setup)
    repo.log_robot_run("lucca", "nieuwe_reservaties", datetime.now(UTC), True)
    assert oversight.robot_problem("lucca", 3) is None
