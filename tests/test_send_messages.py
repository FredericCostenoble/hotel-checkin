"""Proces send_messages: bevestiging één keer, alleen nieuwe reservaties, in TST naar het testadres."""

from datetime import UTC, date, datetime, timedelta

import pytest

from hotel_checkin.core import workflow
from hotel_checkin.core.models import Channel, Guest, Reservation, ReservationStatus, SendResult
from hotel_checkin.guests import repository as repo
from hotel_checkin.messaging import templates
from hotel_checkin.processes import send_messages


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    repo.use_memory_store()
    monkeypatch.setenv("APP_ENV", "tst")
    monkeypatch.setenv("LUCCA_SCHAKELAARS_BERICHTEN", "true")  # hoofdschakelaar berichten aan
    monkeypatch.setattr(send_messages, "start", lambda h: datetime(2026, 10, 30, tzinfo=UTC))
    sent = []

    def fake_send(to, subject, html_body, sender=None, reply_to=None, **kw):
        sent.append((to, subject))
        return SendResult(Channel.EMAIL, to, True)
    monkeypatch.setattr(send_messages.email, "send_email", fake_send)
    return sent


def _res(rid, email="jan@example.com", arrival_in=30, status=ReservationStatus.READY_FOR_CHECKIN, paid=True):
    arr = date.today() + timedelta(days=arrival_in)
    r = Reservation("lucca", rid, Guest("Jan", "Voorbeeld", email=email, language="nl"), arr,
                    arr + timedelta(days=2), status=status, booking_number="CPB-1-" + rid, paid=paid)
    return repo.save_reservation(r)


def test_confirmation_once(setup):
    _res("r1")
    assert send_messages.run("lucca") == 1 and send_messages.run("lucca") == 0
    assert len(setup) == 1 and "Hotel Lucca" in setup[0][1]
    assert repo.was_sent("lucca", "r1", "confirmation", "email")
    assert repo.robot_runs("lucca")[0]["task"] == "berichten"


def test_old_reservations_and_cancelled_get_nothing(setup, monkeypatch):
    monkeypatch.setattr(send_messages, "start", lambda h: datetime.now(UTC) + timedelta(hours=1))
    _res("old")
    assert send_messages.run("lucca") == 0
    monkeypatch.setattr(send_messages, "start", lambda h: datetime(2026, 10, 30, tzinfo=UTC))
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


def test_disabled_by_main_switch(monkeypatch, setup):
    monkeypatch.setenv("APP_ENV", "prd")
    monkeypatch.delenv("LUCCA_SCHAKELAARS_BERICHTEN")  # standaard uit
    _res("r1")
    assert send_messages.run("lucca") == 0 and setup == []


def test_format_date():
    d = date(2026, 11, 14)
    assert templates.format_date(d, "nl") == "zaterdag 14 november 2026"
    assert templates.format_date(d, "de") == "Samstag, 14. November 2026"


def test_late_booking_prd_without_salto_gets_confirmation(setup, monkeypatch):
    _res("late", arrival_in=2)  # binnen het venster van access_code
    # PRD zonder Salto: de code-mail kan nog niet weg, dus vervangt ze de bevestiging niet
    monkeypatch.setattr(send_messages, "test_mode", lambda h: False)
    assert send_messages.run("lucca") == 1
    assert repo.was_sent("lucca", "late", "confirmation") and not repo.was_sent("lucca", "late", "access_code")


def test_late_booking_one_mail_with_confirmation_content(setup, monkeypatch):
    from hotel_checkin.core import workflow

    _res("late2", arrival_in=1)  # TST zonder Salto: meteen de code-mail (XXXXXX)
    bodies = []
    real = send_messages.send_mail
    monkeypatch.setattr(send_messages, "send_mail",
                        lambda h, step, r, cfg, to, extra=None: bodies.append(step.mail_content()) or real(h, step, r, cfg, to=to))
    assert send_messages.run("lucca") == 1
    assert repo.was_sent("lucca", "late2", "access_code") and not repo.was_sent("lucca", "late2", "confirmation")
    # de code-mail kreeg de inhoud van de weggevallen bevestiging erbij
    assert bodies[0]["code"] and bodies[0]["reservation"] and bodies[0]["checkin_form"]
    step = next(s for s in workflow.steps("lucca", "booking") if s.step == "access_code")
    assert not step.mail_content().get("checkin_form")  # de instelling zelf blijft ongewijzigd


def test_booking_on_arrival_day_gets_code(setup):
    _res("today", arrival_in=0)
    assert send_messages.run("lucca") == 1
    assert repo.was_sent("lucca", "today", "access_code")


def test_code_mail_placeholder_in_test(setup):
    from hotel_checkin.core import workflow

    r = _res("ph1", arrival_in=2, paid=None)  # betaalstatus onbekend: betaalknop (nog zonder link)
    step = next(s for s in workflow.steps("lucca", "website") if s.step == "access_code")
    msg, _data = send_messages._rendered("lucca", step, r, workflow.config("lucca"))
    assert "XXXXXX" in msg.html and "Salto is nog niet actief" in msg.html and "Nog geen betaallink" in msg.html


def test_booked_five_days_before_no_reminder(setup):
    _res("r5", arrival_in=5)  # bevestiging ja, herinnering niet (boeking kwam na de herinneringsdag)
    assert send_messages.run("lucca") == 1
    assert repo.was_sent("lucca", "r5", "confirmation") and not repo.was_sent("lucca", "r5", "reminder")


def _all_whatsapp(monkeypatch):
    """Elke stap ook per WhatsApp (in de standaardworkflow gaat de bevestiging alleen per mail)."""
    monkeypatch.setattr(workflow, "channels_of", lambda raw: ["email", "whatsapp"])


def test_confirmation_only_by_mail(setup, monkeypatch):
    """Kanalen per stap (workflow): de bevestiging alleen per mail, ook met een gsm-nummer."""
    monkeypatch.setattr(send_messages, "phone_enabled", lambda h: True)
    monkeypatch.setattr(send_messages, "whatsapp_template", lambda h, s, lang: "HX123")
    calls = []
    monkeypatch.setattr(send_messages.whatsapp, "send_whatsapp_template", lambda *a, **k: calls.append(a))
    r = _res("c1")
    r.guest.phone = "+32470000001"
    r.guest.phone_consent = ["+32470000001"]
    repo.save_reservation(r)
    send_messages.run("lucca")
    assert repo.was_sent("lucca", "c1", "confirmation") and not calls
    item = send_messages.plan("lucca", r, [], workflow.config("lucca"), send_messages.READY_STEPS,
                              date.today(), None, True, phone=True)[0]
    assert {c["channel"]: c["reason"] for c in item["channels"]}["whatsapp"] == "step_off"


def test_phone_whatsapp_then_sms_fallback(setup, monkeypatch):
    _all_whatsapp(monkeypatch)
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
    r.guest.phone_consent = ["+32470000001"]
    repo.save_reservation(r)
    send_messages.run("lucca")
    assert [c[0] for c in calls] == ["wa"] and calls[0][1]["1"] == "Jan" and calls[0][1]["2"].endswith("&lang=nl") and "http" not in calls[0][1]["2"]
    send_messages.run("lucca")
    assert len(calls) == 1  # WhatsApp gelukt: niets meer
    # Twilio meldt later: geen WhatsApp op dit nummer -> volgende run per sms
    wa = next(m for m in repo.messages_for("lucca", "p1") if m["channel"] == "whatsapp")
    send_messages.twilio_status("lucca", "p1", wa["RowKey"], "undelivered", "63003")
    send_messages.run("lucca")
    assert [c[0] for c in calls] == ["wa", "sms"]
    rows = repo.messages_for("lucca", "p1")
    assert {(m["channel"], m["ok"]) for m in rows} == {("email", True), ("whatsapp", False), ("sms", True)}
    assert any(m.get("note") == "terugval: geen WhatsApp" for m in rows)


def test_phone_only_with_consent_from_the_form(setup):
    """WhatsApp en sms alleen naar nummers die de gast zelf in het check-in-formulier invulde."""
    r = _res("k1")
    r.guest.phone = "+32470000001"  # van de boekingssite
    repo.save_reservation(r)
    assert send_messages.recipients(repo.get_reservation("lucca", "k1"), "phone") == []
    repo.mark_checkin_completed("lucca", "k1", "jan@example.com", None, "nl", backup_phone="+32470000009")
    r = repo.get_reservation("lucca", "k1")
    assert r.guest.phone_consent == ["+32470000009"]
    assert send_messages.recipients(r, "phone") == ["+32470000009"]  # niet het nummer van de boekingssite
    repo.mark_checkin_completed("lucca", "k1", "jan@example.com", "+32470000005", "nl")
    assert send_messages.recipients(repo.get_reservation("lucca", "k1"), "phone") == ["+32470000005"]


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
    assert code["state"] == "planned"  # in TST ook zonder Salto (met XXXXXX)
    assert code["due"] == (r.arrival - timedelta(days=2)).isoformat()
    assert not any(p["step"] == "payment_request" for p in plan)  # nu de betaalknop in de bedankmail


def test_thank_you_with_open_amount_has_pay_section_after_stay():
    from hotel_checkin.messaging import templates

    texts = templates.load_texts("lucca", "nl")
    with_pay = templates.compose_blocks(texts, "thank_you", {"message": True}, "open_amount")
    without = templates.compose_blocks(texts, "thank_you", {"message": True}, "none")
    assert [b for b in with_pay if b.get("module") == "pay"] and not [b for b in without if b.get("module") == "pay"]
    assert "bij aankomst" not in str(with_pay)  # eigen tekst na vertrek, niet die van voor de aankomst


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
    _all_whatsapp(monkeypatch)
    monkeypatch.setattr(send_messages, "phone_enabled", lambda h: True)
    monkeypatch.setattr(send_messages, "whatsapp_template", lambda h, s, lang: None)
    texts = []
    monkeypatch.setattr(send_messages.sms, "send_sms",
                        lambda h, to, text, status_callback=None: texts.append(to) or SendResult(Channel.SMS, to, True))
    r = _res("b1")
    r.guest.backup_email, r.guest.phone, r.guest.backup_phone = "Partner@example.com", "+32470000001", "+32470000002"
    r.guest.phone_consent = ["+32470000001", "+32470000002"]
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
    # ander adres mag (met de hand), wordt niet bij de reservatie bewaard; ongeldig adres niet
    assert send_messages.resend("lucca", "b1", "confirmation", "email", "Other@Example.com", "x")["ok"]
    assert repo.get_reservation("lucca", "b1").guest.backup_email == "partner@example.com"
    assert not send_messages.resend("lucca", "b1", "confirmation", "email", "fout", "x")["ok"]


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


def test_room_change_message_once_with_same_code(setup, monkeypatch):
    """Kamerwissel na de code-mail: één bericht, nieuwe kamer en dezelfde code (review 02/11)."""
    from hotel_checkin.core.models import Channel, SendResult

    sent = []
    monkeypatch.setattr(send_messages.email, "send_email",
                        lambda to, subject, html_body, **k: sent.append((subject, html_body)) or SendResult(Channel.EMAIL, to, True))
    r = _res("rc1", arrival_in=0)
    r.rooms = ["16"]
    r.access_codes = [{"room": "16", "pin": "2242", "user_id": "u", "group_id": "g"}]
    r.room_moves = [{"from": "14", "to": "16", "at": "2026-11-02T10:50:00+01:00"}]
    repo.save_reservation(r)
    cfg = send_messages.workflow.config("lucca")
    assert send_messages.notify_room_change("lucca", r, cfg, date.today()) == []  # code nog niet verstuurd
    repo.log_message("lucca", "rc1", "access_code", SendResult(Channel.EMAIL, "jan@example.com", True))
    out = send_messages.notify_room_change("lucca", r, cfg, date.today())
    assert [c for c, _, _ in out] == ["email"] and "gewijzigd" in sent[0][0]
    assert "kamer 16, 1e verdieping" in sent[0][1] and "kamer 14" in sent[0][1] and "2242 ↵" in sent[0][1]
    assert send_messages.notify_room_change("lucca", r, cfg, date.today()) == []  # niet twee keer
    r.room_moves.append({"from": "16", "to": "2", "at": "2026-11-02T12:00:00+01:00"})  # nog eens, naar de suite
    r.access_codes[0]["room"] = "2"
    out = send_messages.notify_room_change("lucca", r, cfg, date.today())
    assert len(out) == 1 and "Kuipersstraat" in sent[-1][1]


def test_nfr_without_sections_gets_no_confirmation(setup):
    cfg = send_messages.workflow.config("lucca")
    cfg["flows"]["website"]["steps"][0]["rates"] = {"nfr": {k: False for k in send_messages.workflow.SECTIONS}}
    send_messages.workflow.save_config("lucca", cfg, "test")
    nfr = _res("n1")
    nfr.non_refundable = True
    repo.save_reservation(nfr)
    _res("s1")
    assert send_messages.run("lucca") == 1 and repo.was_sent("lucca", "s1", "confirmation", "email")
    assert not repo.was_sent("lucca", "n1", "confirmation", "email")
    plan = send_messages.plan("lucca", repo.get_reservation("lucca", "n1"), [], send_messages.workflow.config("lucca"),
                              send_messages.ready_steps("lucca"), date.today(), send_messages.start("lucca"), True)
    assert next(p for p in plan if p["step"] == "confirmation")["reason"] == "rate_off_nfr"
