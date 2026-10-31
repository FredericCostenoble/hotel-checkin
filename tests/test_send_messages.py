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
        repo.log_message("lucca", rid, "confirmation", SendResult(Channel.EMAIL, "jan@example.com", True))
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


def test_phone_whatsapp_then_sms_fallback(setup, monkeypatch):
    monkeypatch.setattr(send_messages, "phone_enabled", lambda h: True)
    monkeypatch.setattr(send_messages, "whatsapp_template", lambda h, s, lang: "HX123")
    calls = []
    monkeypatch.setattr(send_messages.whatsapp, "send_whatsapp_template",
                        lambda h, to, sid, variables, status_callback=None: calls.append(("wa", variables))
                        or SendResult(Channel.WHATSAPP, to, True, provider_id="SM1"))
    monkeypatch.setattr(send_messages.sms, "send_sms",
                        lambda h, to, text, status_callback=None: calls.append(("sms", text))
                        or SendResult(Channel.SMS, to, True))
    r = _res("p1")
    r.guest.phone = "+32470000001"
    repo.save_reservation(r)
    send_messages.run("lucca")
    assert [c[0] for c in calls] == ["wa"] and calls[0][1]["1"] == "Jan" and "http" in calls[0][1]["2"]
    send_messages.run("lucca")
    assert len(calls) == 1  # WhatsApp gelukt: niets meer
    # Twilio meldt later: geen WhatsApp op dit nummer -> volgende run per sms
    wa = [m for m in repo.messages_for("lucca", "p1") if m["channel"] == "whatsapp"][0]
    send_messages.twilio_status("lucca", "p1", wa["RowKey"], "undelivered", "63003")
    send_messages.run("lucca")
    assert [c[0] for c in calls] == ["wa", "sms"]
    rows = repo.messages_for("lucca", "p1")
    assert {(m["channel"], m["ok"]) for m in rows} == {("email", True), ("whatsapp", False), ("sms", True)}
    assert any(m.get("note") == "terugval: geen WhatsApp" for m in rows)


def test_failed_mail_retried_max_three_times(setup, monkeypatch):
    monkeypatch.setattr(send_messages.email, "send_email",
                        lambda *a, **k: SendResult(Channel.EMAIL, k["to"], False, error="403"))
    _res("f1")
    for _ in range(5):
        send_messages.run("lucca")
    assert len(repo.messages_for("lucca", "f1")) == 3


def test_twilio_signature():
    import base64
    import hashlib
    import hmac

    from hotel_checkin.messaging import _twilio

    url, params = "https://x.azurewebsites.net/api/twilio/status?h=lucca&r=1&m=2", {"MessageStatus": "delivered", "To": "+32"}
    token = "secret"
    sig = base64.b64encode(hmac.new(token.encode(), (url + "MessageStatusdeliveredTo+32").encode(), hashlib.sha1).digest()).decode()
    import pytest as _p
    mp = _p.MonkeyPatch()
    mp.setattr(_twilio, "hotel_setting", lambda h, n, **k: token)
    try:
        assert _twilio.valid_signature("lucca", url, params, sig)
        assert not _twilio.valid_signature("lucca", url, {**params, "MessageStatus": "read"}, sig)
    finally:
        mp.undo()


def test_plan_timeline(setup):
    from hotel_checkin.core import workflow

    r = _res("t1")
    send_messages.run("lucca")
    rows = repo.messages_for("lucca", "t1")
    plan = send_messages.plan("lucca", r, rows, workflow.config("lucca"), send_messages.ready_steps("lucca"),
                              date.today(), send_messages.start("lucca"), True)
    states = {p["step"]: p["state"] for p in plan}
    assert states["confirmation"] == "sent" and states["reminder"] == "planned"
    assert states["thank_you"] == "planned"
    code = next(p for p in plan if p["step"] == "access_code")
    assert code["state"] == "planned" and code["reason"] == "not_ready"  # Salto nog niet ingesteld
    assert code["due"] == (r.arrival - timedelta(days=2)).isoformat()
    pay = next(p for p in plan if p["step"] == "payment_request")
    assert pay["state"] == "skipped" and pay["reason"].startswith("condition:")  # betaalstatus onbekend


def test_muted_email_for_guest(setup):
    from hotel_checkin.guests import profiles

    g = profiles.new_profile("lucca")
    g.muted_channels = ["email"]
    profiles.save_profile(g)
    r = _res("m1")
    r.guest_id = g.guest_id
    repo.save_reservation(r)
    assert send_messages.run("lucca") == 0 and not setup


def test_backup_contacts_get_messages_and_resend(setup, monkeypatch):
    monkeypatch.setattr(send_messages, "phone_enabled", lambda h: True)
    monkeypatch.setattr(send_messages, "whatsapp_template", lambda h, s, lang: None)
    texts = []
    monkeypatch.setattr(send_messages.sms, "send_sms",
                        lambda h, to, text, status_callback=None: texts.append(to) or SendResult(Channel.SMS, to, True))
    r = _res("b1")
    r.guest.backup_email, r.guest.phone, r.guest.backup_phone = "Partner@example.com", "+32470000001", "+32470000002"
    repo.save_reservation(r)
    send_messages.run("lucca")
    assert sorted(to for to, _ in setup) == ["jan@example.com", "partner@example.com"]
    assert texts == ["+32470000001", "+32470000002"]
    rows = repo.messages_for("lucca", "b1")
    assert {m["recipient"] for m in rows} == {"jan@example.com", "partner@example.com", "+32470000001", "+32470000002"}
    send_messages.run("lucca")
    assert len(setup) == 2  # niets dubbel
    out = send_messages.resend("lucca", "b1", "confirmation", "email", "partner@example.com", "frederic")
    assert out["ok"] and len(setup) == 3
    assert any(m["note"] == "opnieuw verstuurd door frederic" for m in repo.messages_for("lucca", "b1"))
    assert not send_messages.resend("lucca", "b1", "confirmation", "email", "other@example.com", "x")["ok"]


def test_form_address_beats_relay_which_is_kept(setup):
    r = _res("ota1", email="jp.123@guest.booking.com")
    assert send_messages.recipients(r, "email") == ["jp.123@guest.booking.com"]
    saved = repo.mark_checkin_completed("lucca", "ota1", "jan@telenet.be", None, "nl")
    assert saved.guest.email == "jan@telenet.be" and saved.guest.relay_email == "jp.123@guest.booking.com"
    assert send_messages.recipients(saved, "email") == ["jan@telenet.be"]


def test_returning_guest_own_address_beats_relay(setup):
    from hotel_checkin.guests import profiles

    g = profiles.new_profile("lucca")
    g.email, g.email_own = "jan@telenet.be", True
    profiles.save_profile(g)
    r = _res("ota2", email="jp.999@guest.booking.com")
    r.guest_id = g.guest_id
    repo.save_reservation(r)
    assert send_messages.recipients(r, "email") == ["jan@telenet.be"]
    r.guest_id = None
    assert send_messages.recipients(r, "email") == ["jp.999@guest.booking.com"]


def test_add_contact_by_hand(setup):
    from hotel_checkin.admin import service

    _res("nc1", email=None)
    assert not service.add_contact("lucca", "nc1", "fout", "")["ok"]
    assert service.add_contact("lucca", "nc1", "Jan@Telenet.be", "0470 12 34 56")["ok"]
    r = repo.get_reservation("lucca", "nc1")
    assert r.guest.email == "jan@telenet.be" and r.guest.phone.startswith("+32")
    service.add_contact("lucca", "nc1", "tweede@telenet.be", "")
    assert repo.get_reservation("lucca", "nc1").guest.backup_email == "tweede@telenet.be"
