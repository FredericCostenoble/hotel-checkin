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


def test_monitoring_off_only_morning_mail(setup, monkeypatch):
    """[bewaking] monitoring uit: geen aparte waarschuwingen, alleen het dagelijkse overzicht."""
    orig = oversight.settings
    monkeypatch.setattr(oversight, "settings", lambda h: orig(h) | {"monitoring": False})
    evening = datetime(2026, 11, 3, 17, 5, tzinfo=oversight.clock.tz("lucca"))
    repo.log_robot_run("lucca", "nieuwe_reservaties", datetime.now(UTC) - timedelta(hours=5), False, error="TimeoutError")
    assert oversight.run("lucca", evening) == [] or all("overzicht" in d for d in oversight.run("lucca", evening))
    assert not [m for m in setup if "WAARSCHUWING" in m[1]]  # geen controle- of robotmail


def test_monitoring_on_by_default():
    assert oversight.settings("lucca")["monitoring"] is True


def test_overview_tells_what_happened(setup):
    repo.log_robot_run("lucca", "overschrijving_booking", datetime.now(UTC) - timedelta(hours=2), True, 5, 2, "x")
    repo.log_robot_run("lucca", "ontbijt_labels", datetime.now(UTC) - timedelta(hours=2), True, 3, 1, "y", skipped=1)
    lines = oversight.activity("lucca")
    assert "2 overschrijving(en) geregistreerd" in lines[0] and "1 ontbijtlabel(s) gezet" in lines[0]
    assert lines[1] == "Er loopt nog iets mis: zie onderaan."
    assert _no_time(oversight.robot_failures("lucca")) == ["Ontbijt labels: y"]


def test_same_problem_counted_once(setup):
    for _ in range(3):
        repo.log_robot_run("lucca", "meldingen", datetime.now(UTC) - timedelta(hours=1), False, 1, 0, "robot niet gestart")
    assert _no_time(oversight.robot_failures("lucca")) == ["Mailbox nakijken: robot niet gestart (3 keer)"]


def test_failures_per_reservation_under_the_tables(setup):
    """Dezelfde reservatie die in elke run niet gelezen kan worden: één regel met de reden, onder de tabellen."""
    note = ("33 aankomsten en verblijven nagekeken (kamer, data, betaling). 2 niet gelezen: "
            "CPB-4276-001805: ValueError (Geen datum gevonden in ''); CPB-4276-002417: ValueError")
    for _ in range(2):
        repo.log_robot_run("lucca", "contactgegevens_nalezen", datetime.now(UTC) - timedelta(hours=1), True, 35, 33,
                           note, skipped=2)
    assert _no_time(oversight.robot_failures("lucca")) == [
        "CPB-4276-001805 (contactgegevens_nalezen): ValueError (Geen datum gevonden in '') (2 runs)",
        "CPB-4276-002417 (contactgegevens_nalezen): ValueError (2 runs)"]
    assert ", laatste keer " in oversight.robot_failures("lucca")[0]  # wanneer het laatst misliep


def test_reason_with_a_date_is_not_cut(setup):
    note = ("33 aankomsten en verblijven nagekeken. 1 niet gelezen: CPB-4276-001805: RuntimeError (pagina niet volledig "
            "geladen na zaterdag, 07 nov. 2026 om 14:30)")
    repo.log_robot_run("lucca", "contactgegevens_nalezen", datetime.now(UTC), True, 34, 33, note, skipped=1)
    assert _no_time(oversight.robot_failures("lucca")) == [
        ("CPB-4276-001805 (contactgegevens_nalezen): RuntimeError (pagina niet volledig geladen na zaterdag, "
         "07 nov. 2026 om 14:30)")]


def test_only_what_still_fails(setup):
    """Een tijdelijke storing die de volgende run al weg is (bv. 502 bij Microsoft), staat er niet meer."""
    t = datetime.now(UTC)
    repo.log_robot_run("lucca", "meldingen", t - timedelta(hours=3), False, 1, 0, "HTTPStatusError: 502 Bad Gateway")
    repo.log_robot_run("lucca", "meldingen", t - timedelta(hours=2), True, 1, 1, "ok")
    note = "280 reservaties nagekeken. 8 met te weinig ontbijten in de folio, nog geen label: CPB-1-2: maar 1 van 4"
    repo.log_robot_run("lucca", "ontbijt_labels", t - timedelta(hours=1), True, 280, 0, note + ". 1 fout: CPB-1-3: TimeoutError",
                       skipped=1)
    assert _no_time(oversight.robot_failures("lucca")) == ["CPB-1-3 (Ontbijt labels): TimeoutError"]


def _no_time(lines):
    import re

    return [re.sub(r", laatste keer \d\d/\d\d \d\d:\d\d", "", x) for x in lines]
    html = oversight.report.overview_html("t", [], [], "/m", problems=oversight.robot_failures("lucca"))
    assert "Wat de robot niet lukte" in html and "CPB-4276-001805" in html


def test_robot_alert_only_when_a_planned_run_was_missed(setup, monkeypatch):
    """TST draait om de 4 uur (00:00, 04:00, 08:00 ...): tussen twee runs geen alarm, pas als een gepland uur
    meer dan een halfuur voorbij is zonder geslaagde run."""
    from hotel_checkin.processes import new_reservation

    monkeypatch.setenv("LUCCA_ROBOT_CHECK_MINUTES", "240")
    monkeypatch.setenv("LUCCA_SCHAKELAARS_RESERVATIES", "true")
    tz = oversight.clock.tz("lucca")
    repo.log_robot_run("lucca", new_reservation.TASK, datetime(2026, 11, 9, 4, 18, tzinfo=tz), True, 0, 0, "ok")
    assert oversight.robot_problem("lucca", 3, datetime(2026, 11, 9, 7, 55, tzinfo=tz)) is None  # 08:00 nog niet
    assert oversight.robot_problem("lucca", 3, datetime(2026, 11, 9, 8, 20, tzinfo=tz)) is None  # run van 08:00 bezig
    alarm = oversight.robot_problem("lucca", 3, datetime(2026, 11, 9, 8, 40, tzinfo=tz))  # 08:00 gemist
    assert alarm and "08:00" in alarm


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


def test_not_placed_is_todo_not_problem():
    """Nog geen kamer: gewone manier van werken (te doen, rood), geen probleem."""
    from hotel_checkin.messaging import report

    today = date(2026, 11, 12)
    r = Reservation("lucca", "np", Guest("Ann", "Brand", email="a@b.be"), today, today + timedelta(days=1))
    row = oversight.row("lucca", repo.save_reservation(r), today, today, True, True)
    assert row["todo"] == ["nog niet geplaatst: kamer toewijzen"] and row["problemen"] == []
    html = report.overview_html("t", [], [("Vandaag", [row])], "https://x")
    assert "#FDECEC" in html and "kamer toewijzen" in html
