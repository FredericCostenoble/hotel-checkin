"""Proces mail_trigger: een melding van Cubilis start de robot, gewone mails niet."""

from datetime import datetime, timedelta, timezone

import pytest

from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import mail_trigger


@pytest.fixture(autouse=True)
def memory(monkeypatch):
    repo.use_memory_store()
    starts = []
    monkeypatch.setattr(mail_trigger.cloud_robot, "available", lambda: True)
    monkeypatch.setattr(mail_trigger.cloud_robot, "running", lambda: False)
    monkeypatch.setattr(mail_trigger.cloud_robot, "start", lambda: starts.append(1) or True)
    return starts


def _mail(sender, subject, minutes_ago=1):
    return {"id": subject, "received_at": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
            "sender": sender, "subject": subject, "text": "Reserveringsnummer: 12345678"}


def test_notice_starts_robot(monkeypatch, memory):
    monkeypatch.setattr(mail_trigger.mailbox, "list_messages", lambda h, since: [
        _mail("noreply@cubilis.com", "Cancelled reservation via Booking.com (12345678)"),
        _mail("someone@example.com", "Question about breakfast")])
    assert mail_trigger.run("lucca") == 1 and memory == [1]
    run = repo.robot_runs("lucca")[0]
    assert run["task"] == "meldingen" and "geannuleerd 12345678" in run["error"]
    assert repo.get_state("lucca", mail_trigger.STATE_KEY)  # leesgrens verzet


def test_ordinary_mail_no_robot_no_log(monkeypatch, memory):
    monkeypatch.setattr(mail_trigger.mailbox, "list_messages", lambda h, since: [
        _mail("someone@example.com", "Question about breakfast")])
    assert mail_trigger.run("lucca") == 0 and memory == []
    assert repo.robot_runs("lucca") == []


def test_robot_busy_retries_next_minute(monkeypatch, memory):
    monkeypatch.setattr(mail_trigger.cloud_robot, "running", lambda: True)
    monkeypatch.setattr(mail_trigger.mailbox, "list_messages", lambda h, since: [
        _mail("no-reply@cubilis.eu", "Nieuwe reservering bij Lucca Hotel - Brugge (12345678)")])
    mail_trigger.run("lucca")
    assert memory == [] and repo.get_state("lucca", mail_trigger.STATE_KEY) is None


def test_mailbox_error_logged_once_per_hour(monkeypatch):
    def boom(h, since):
        raise RuntimeError("403")
    monkeypatch.setattr(mail_trigger.mailbox, "list_messages", boom)
    mail_trigger.run("lucca")
    mail_trigger.run("lucca")
    assert len(repo.robot_runs("lucca")) == 1


def test_enabled_per_hotel():
    assert mail_trigger.enabled("lucca")
