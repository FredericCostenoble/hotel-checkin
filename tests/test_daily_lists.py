"""Ontbijtlijst en kuislijst (processes/daily_lists.py, messaging/lists.py)."""

import io
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import azure.functions as func
import pytest
from openpyxl import load_workbook

from hotel_checkin.core.models import Channel, Guest, Reservation, ReservationStatus, SendResult
from hotel_checkin.guests import repository as repo
from hotel_checkin.messaging import lists
from hotel_checkin.processes import daily_lists as dl

DAY = date(2026, 11, 6)  # de dag van de lijst (vrijdag)
TZ = dl.clock.tz("lucca")


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    repo.use_memory_store()
    mails = []
    monkeypatch.setattr("hotel_checkin.messaging.email.send_email",
                        lambda to, subject, html_body, **k: mails.append((to, subject, html_body, k))
                        or SendResult(Channel.EMAIL, to, True))
    return mails


def _r(rid, room, arrival, nights, persons=2, rate="STANDARD RATE BREAKFAST EXCL", folio=(), **kw):
    r = Reservation("lucca", rid, Guest("Ann", "Brand"), arrival, arrival + timedelta(days=nights),
                    rooms=[room] if isinstance(room, str) else list(room), guest_count=persons, rate_plan=rate,
                    booking_number="CPB-" + rid, **kw)
    r.folio = [{"label": "Superior double - " + rate, "qty": None, "amount": 300.0}, *folio]
    return repo.save_reservation(r)


def _row(data, room):
    return next(x for x in data["rows"] if x.get("room") == room)


def test_breakfast_list():
    _r("a", "20", DAY - timedelta(days=2), 3, rate="STANDARD RATE BREAKFAST INCL")  # vertrekt op DAY: ontbijt
    _r("b", "16", DAY - timedelta(days=1), 2, persons=1, rate="NRF BREAKFAST EXCL",
       folio=[{"label": "Ontbijt", "qty": 2, "amount": 40.0}])  # alle nachten bijgeboekt
    _r("c", "23", DAY - timedelta(days=1), 3, folio=[{"label": "Ontbijt", "qty": 2, "amount": 40.0}],
       remarks="Graag 1pax glutenfree ontbijt. PrePay: payment on Booking.com")  # 2 van 6: nakijken
    _r("d", "11", DAY, 2, rate="STANDARD RATE BREAKFAST INCL")  # komt pas aan: geen ontbijt op DAY
    _r("e", "12", DAY - timedelta(days=1), 2)  # geen ontbijt
    _r("f", ["30", "31", "32"], DAY - timedelta(days=1), 2, persons=5, rate="STANDARD RATE BREAKFAST INCL")
    _r("g", "33", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL", status=ReservationStatus.CANCELLED)
    data = dl.build("lucca", "breakfast", DAY)
    assert data["rows"][0]["room"] == "App" and _row(data, "App")["count"] == 2  # kamer 20 = App, bovenaan
    assert _row(data, "16")["count"] == 1
    c = _row(data, "23")
    assert c["count"] is None and c["check"] and "nakijken" in c["remark"] and "glutenfree" in c["remark"]
    assert "PrePay" not in c["remark"]  # alleen zinnen met een van de woorden
    assert _row(data, "11")["count"] is None and _row(data, "12")["count"] is None
    assert [_row(data, x)["count"] for x in ("30", "31", "32")] == [2, 2, 1]
    assert "samen met 31, 32 (5 pers.)" in _row(data, "30")["remark"]
    assert _row(data, "33")["count"] is None  # geannuleerd
    assert data["total"] == 2 + 1 + 5 and data["check"] == 1
    assert {"sep": True} in data["rows"] and not data["rows"][-1].get("sep")


def test_cleaning_list():
    _r("a", "12", DAY - timedelta(days=2), 2)  # vertrek
    _r("b", "12", DAY, 1, persons=3, remarks="Please a baby cot. Arrival 20h")  # en dezelfde dag check in
    _r("c", "21", DAY - timedelta(days=1), 3, remarks="Romantische versiering voor verjaardag")  # blijft
    _r("d", "24", DAY + timedelta(days=1), 1)  # later: niet op de lijst
    data = dl.build("lucca", "cleaning", DAY)
    r12 = _row(data, "12")
    assert r12["leave"] and r12["checkin"] and not r12["stay"]
    assert "3 pers." in r12["remark"] and "baby cot" in r12["remark"] and "Arrival" not in r12["remark"]
    r21 = _row(data, "21")
    assert r21["stay"] and not r21["leave"] and "Romantische versiering" in r21["remark"]
    assert not any(_row(data, "24")[k] for k in ("leave", "stay", "checkin"))
    assert data["totals"] == {"leave": 1, "stay": 1, "checkin": 1}
    assert data["controle"] == "Iqbal" and data["extra_rows"] == ["TOILETTEN"]
    assert "vertrek 1 (12)" in lists.summary(data) and "12: vertrek, check in" in lists.text(data, "Hotel Lucca")


def test_room_without_number():
    _r("a", [], DAY, 2)
    data = dl.build("lucca", "cleaning", DAY)
    unknown = _row(data, "?")
    assert unknown["checkin"] and unknown["check"] and "nog geen kamer" in unknown["remark"]


def test_excel_like_the_hand_made_list():
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    for kind in ("breakfast", "cleaning"):
        data = dl.build("lucca", kind, DAY) | {"generated_at": "2026-11-05T18:00+01:00"}
        ws = load_workbook(io.BytesIO(lists.xlsx(data, "Hotel Lucca"))).active
        assert ws["A1"].value == lists.TITLES[kind] and ws["C1"].value.date() == DAY
        assert ws["A4"].value == "App"
        html = lists.mail_html(data, "Hotel Lucca", ["x"])
        assert "<table" in html and "App" in html
    assert load_workbook(io.BytesIO(lists.xlsx(dl.build("lucca", "cleaning", DAY), "L"))).active["D1"].value == "Controle: Iqbal"


def test_generate_sends_mail_with_excel_and_keeps_15(setup):
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    data = dl.generate("lucca", "breakfast", DAY, by="frederic@hotellucca.be", send_now=True)
    to, subject, body, k = setup[0]
    assert to == "management@hotellucca.be" and "ontbijtlijst vrijdag 06/11/2026" in subject and "<table" in body
    name, content = k["attachments"][0]
    assert name.endswith(".xlsx") and content[:2] == b"PK"
    assert data["sent"][0]["ok"] and repo.get_daily_list("lucca", "breakfast", DAY.isoformat())["generated_by"]
    run = repo.robot_runs("lucca", task="ontbijtlijst")[0]
    assert run["ok"] and "2 personen in 1 kamers" in run["error"]
    for i in range(20):
        dl.generate("lucca", "breakfast", DAY + timedelta(days=i + 1))
    kept = repo.daily_lists("lucca", "breakfast")
    assert len(kept) == 15 and kept[0]["day"] == (DAY + timedelta(days=20)).isoformat()


def test_whatsapp_waits_for_twilio(monkeypatch):
    monkeypatch.setattr(dl, "settings", lambda h, k: {"time": "18:00", "days": 1, "email": [], "words": [],
                                                       "whatsapp": ["+32470123456"], "controle": "", "extra_rows": []})
    sent = dl.send("lucca", dl.build("lucca", "cleaning", DAY))
    assert sent[0]["skipped"] and "staan uit" in sent[0]["error"]


def test_timer_once_after_the_hour(setup, monkeypatch):
    monkeypatch.setenv("LUCCA_SCHAKELAARS_KUISLIJST", "true")
    today = DAY - timedelta(days=1)
    assert dl.run("lucca", datetime(today.year, today.month, today.day, 17, 55, tzinfo=TZ)) == []
    at = datetime(today.year, today.month, today.day, 18, 5, tzinfo=TZ)
    assert dl.run("lucca", at) == [f"cleaning {DAY.isoformat()}"]  # ontbijtlijst staat uit
    assert dl.run("lucca", at + timedelta(minutes=5)) == []  # niet twee keer
    assert len(setup) == 1
    assert dl.next_day("lucca", "cleaning", at) == DAY + timedelta(days=1)
    assert dl.next_day("lucca", "cleaning", at - timedelta(hours=1)) == DAY


def test_robot_reads_the_day_before_sending(monkeypatch):
    monkeypatch.setenv("LUCCA_SCHAKELAARS_ONTBIJTLIJST", "true")
    _r("a", "20", DAY - timedelta(days=1), 2)
    _r("b", "21", DAY + timedelta(days=3), 2)
    today = DAY - timedelta(days=1)
    early = datetime(today.year, today.month, today.day, 12, 0, tzinfo=TZ)
    assert dl.refresh_due("lucca", early) == []  # nog te vroeg
    window = datetime(today.year, today.month, today.day, 16, 0, tzinfo=TZ)
    assert [r.reservation_id for r in dl.refresh_due("lucca", window)] == ["a"]
    dl.refresh_done("lucca", window)
    assert dl.refresh_due("lucca", window + timedelta(hours=1)) == []  # één keer per lijst


def test_monitor_routes(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import function_app as fa

    monkeypatch.setenv("ADMIN_AUTH", "easyauth")
    h = {"x-ms-client-principal-name": "frederic@hotellucca.be", "x-monitor": "1"}
    fn = fa.admin_api.build().get_user_function()

    def call(method, what, params):
        url = f"/api/monitor/lucca/{what}?" + "&".join(f"{k}={v}" for k, v in params.items())
        return fn(func.HttpRequest(method, url, headers=h, params=params, route_params={"hotel": "lucca", "what": what},
                                   body=b""))

    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    assert call("POST", "lists", {"kind": "breakfast", "day": DAY.isoformat()}).status_code == 200
    got = call("GET", "lists", {"kind": "breakfast"})
    import json

    body = json.loads(got.get_body())
    assert body["records"][0]["day"] == DAY.isoformat() and "<table" in body["records"][0]["html"]
    x = call("GET", "list-xlsx", {"kind": "breakfast", "day": DAY.isoformat()})
    assert x.status_code == 200 and x.get_body()[:2] == b"PK"
    assert call("GET", "lists", {"kind": "lunch"}).status_code == 400
