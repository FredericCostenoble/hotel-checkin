"""De link naar de verblijfspagina opnieuw vragen ter plaatse (processes/find_stay.py, QR-code)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from hotel_checkin.core.models import Channel, Guest, Reservation, SendResult
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import find_stay, incoming

TODAY = date(2026, 11, 25)
NOW = datetime(2026, 11, 25, 15, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def sent(monkeypatch):
    repo.use_memory_store()
    out = {"mail": [], "wa": [], "sms": []}
    monkeypatch.setattr("hotel_checkin.messaging.email.send_email",
                        lambda to, subject, html_body, **k: out["mail"].append((to, subject, html_body))
                        or SendResult(Channel.EMAIL, to, True))
    monkeypatch.setattr("hotel_checkin.messaging.whatsapp.send_whatsapp_text",
                        lambda h, to, text, **k: out["wa"].append((to, text)) or SendResult(Channel.WHATSAPP, to, True))
    monkeypatch.setattr("hotel_checkin.messaging.sms.send_sms",
                        lambda h, to, text, **k: out["sms"].append((to, text)) or SendResult(Channel.SMS, to, True))
    monkeypatch.setattr("hotel_checkin.processes.send_messages.phone_enabled", lambda h: True)
    monkeypatch.setattr("hotel_checkin.core.clock.today", lambda h: TODAY)
    return out


def _res(rid="R1", email="anna@gmail.com", phone="+32476123474", consent=True, last="Müller", arrival=TODAY,
         departure=date(2026, 11, 27), source=None, relay=None):
    g = Guest("Anna", last, email, phone, "nl", phone_consent=[phone] if consent and phone else None, relay_email=relay)
    r = Reservation("lucca", rid, g, arrival, departure, rooms=["16"], token=f"tok-{rid}", source=source)
    repo.save_reservation(r)
    return r


def test_masks():
    assert find_stay.mask_email("jan.peeters@gmail.com") == "j•••@gmail.com"
    assert find_stay.mask_phone("+32476123474") == "+32 4••••••74"


def test_email_always_same_answer(sent):
    _res()
    assert find_stay.request("lucca", "email", "ANNA@gmail.com", client="1.1.1.1", now=NOW) == {"status": "ok"}
    assert sent["mail"][0][0] == "ANNA@gmail.com" and "tok-R1" in sent["mail"][0][2]
    assert find_stay.request("lucca", "email", "iemand@anders.be", client="1.1.1.1", now=NOW) == {"status": "ok"}
    assert len(sent["mail"]) == 1  # niet gevonden: niets verstuurd, zelfde antwoord
    assert repo.messages_for("lucca", "R1")[0]["message_type"] == "stay_link"


def test_only_current_reservations(sent):
    _res(arrival=TODAY + timedelta(days=5), departure=TODAY + timedelta(days=7))
    find_stay.request("lucca", "phone", "0476 12 34 74", client="1.1.1.1", now=NOW)
    assert sent["sms"] == []
    _res(rid="R2", arrival=TODAY + timedelta(days=1), departure=TODAY + timedelta(days=3))
    find_stay.request("lucca", "phone", "0476 12 34 74", client="1.1.1.2", now=NOW)
    assert sent["sms"][0][0] == "+32476123474" and "tok-R2" in sent["sms"][0][1]


def test_name_and_departure_shows_masked_targets(sent):
    _res()
    out = find_stay.request("lucca", "name", "anna muller", "2026-11-27", client="1.1.1.1", now=NOW)
    assert out == {"status": "sent", "to": [{"channel": "email", "shown": "a•••@gmail.com"},
                                            {"channel": "sms", "shown": "+32 4••••••74"}]}
    assert len(sent["mail"]) == 1 and len(sent["sms"]) == 1
    assert find_stay.request("lucca", "name", "Müller", "2026-11-28", client="1.1.1.2", now=NOW) == {"status": "not_found"}


def test_platform_contacts_one_message_and_no_address_shown(sent):
    _res(email="x7k2@guest.booking.com", phone="+44770090012", consent=False, source="Booking.com")
    out = find_stay.request("lucca", "name", "Müller", "2026-11-27", client="1.1.1.1", now=NOW)
    assert out == {"status": "sent", "to": [{"platform": "Booking.com"}]}
    assert [m[0] for m in sent["mail"]] == ["x7k2@guest.booking.com"] and sent["sms"] == []
    # Geen platformadres: dan het platformnummer, ook als "bericht via" getoond
    _res(rid="R2", email=None, phone="+44770090013", consent=False, last="Smith", source="Expedia")
    out = find_stay.request("lucca", "name", "Smith", "2026-11-27", client="1.1.1.3", now=NOW)
    assert out == {"status": "sent", "to": [{"platform": "Expedia"}]} and sent["sms"][0][0] == "+44770090013"


def test_limits(sent):
    _res()
    for _ in range(find_stay.TRIES_PER_VALUE):
        find_stay.request("lucca", "name", "Peeters", "2026-11-27", client="9.9.9.9", now=NOW)
    assert find_stay.request("lucca", "name", "Peeters", "2026-11-27", client="9.9.9.8", now=NOW)["status"] == "limit"
    assert find_stay.request("lucca", "name", "Peeters", "2026-11-27", client="9.9.9.8",
                             now=NOW + timedelta(hours=2))["status"] == "not_found"
    # per reservatie hoogstens één verzending per 10 minuten
    find_stay.request("lucca", "email", "anna@gmail.com", client="2.2.2.2", now=NOW)
    find_stay.request("lucca", "email", "anna@gmail.com", client="2.2.2.3", now=NOW + timedelta(minutes=2))
    assert len(sent["mail"]) == 1


def test_invalid():
    assert find_stay.request("lucca", "email", "geen-adres", client="1", now=NOW) == {"status": "invalid"}
    assert find_stay.request("lucca", "name", "Peeters", "morgen", client="1", now=NOW) == {"status": "invalid"}
    assert find_stay.request("lucca", "x", "y", client="1", now=NOW) == {"status": "invalid"}


def test_whatsapp_keyword_replies_with_link_also_for_platform_number(sent):
    _res(email="x7k2@guest.booking.com", phone="+44770090012", consent=False)
    out = incoming.handle("lucca", "whatsapp", "+44770090012", "My stay", now=NOW)
    assert out["stay_link"] == "sent" and not out["forwarded"]
    assert sent["wa"][0][0] == "+44770090012" and "tok-R1" in sent["wa"][0][1] and sent["mail"] == []
    out = incoming.handle("lucca", "whatsapp", "+447700900999", "Mijn verblijf", now=NOW)
    assert out["stay_link"] == "not_found" and "geen reservatie" in sent["wa"][1][1]
    # Een gewone vraag gaat zoals vroeger naar het hotel
    assert incoming.handle("lucca", "whatsapp", "+44770090012", "Is er parking?", now=NOW)["forwarded"]
