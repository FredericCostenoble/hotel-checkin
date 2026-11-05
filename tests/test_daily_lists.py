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
    if room == "20":
        kw.setdefault("room_names", {"20": "APARTMENT"})
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
    assert data["rows"][0]["room"] == "20" and _row(data, "20")["count"] == 2  # appartement, bovenaan
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
    assert data["controle"] == "verantwoordelijke housekeeping" and data["extra_rows"] == ["TOILETTEN"]
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
        assert ws["A4"].value == 20 and ws["B4"].value == "Apartment"
        html = lists.mail_html(data, "Hotel Lucca", ["x"])
        assert "<table" in html and "Apartment" in html
    ws = load_workbook(io.BytesIO(lists.xlsx(dl.build("lucca", "cleaning", DAY), "L"))).active
    assert ws["E1"].value == "Controle: verantwoordelijke housekeeping"


def test_room_descriptions_from_lighthouse():
    """Omschrijving uit Lighthouse naast het nummer, ook voor kamers die nu leeg zijn (onthouden)."""
    from hotel_checkin.pms.lighthouse_parse import room_names_from

    assert room_names_from("Superior double\n11 - SUPERIOR DOUBLE ROOM\nNRF BREAKFAST INCL, € 10") == \
        {"11": "SUPERIOR DOUBLE ROOM"}
    r = _r("a", "11", DAY - timedelta(days=1), 1, room_names={"11": "SUPERIOR DOUBLE ROOM"})
    assert repo.get_reservation("lucca", r.reservation_id).room_names == {"11": "SUPERIOR DOUBLE ROOM"}
    assert _row(dl.build("lucca", "cleaning", DAY), "11")["desc"] == "Superior double room"
    repo.delete_reservation("lucca", r.reservation_id)
    assert _row(dl.build("lucca", "breakfast", DAY), "11")["desc"] == "Superior double room"
    assert _row(dl.build("lucca", "breakfast", DAY), "12")["desc"] == ""


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
    """Zonder robot in de cloud (codespace): op het uur meteen, met wat er is."""
    monkeypatch.setenv("LUCCA_SCHAKELAARS_KUISLIJST", "true")
    today = DAY - timedelta(days=1)
    assert dl.run("lucca", datetime(today.year, today.month, today.day, 17, 40, tzinfo=TZ)) == []
    at = datetime(today.year, today.month, today.day, 17, 45, tzinfo=TZ)
    assert dl.run("lucca", at) == [f"cleaning {DAY.isoformat()}"]  # ontbijtlijst staat uit
    assert dl.run("lucca", at + timedelta(minutes=5)) == []  # niet twee keer
    assert len(setup) == 1
    assert dl.next_day("lucca", "cleaning", at) == DAY + timedelta(days=1)
    assert dl.next_day("lucca", "cleaning", at - timedelta(hours=1)) == DAY


@pytest.fixture
def robot(monkeypatch):
    """Robot in de cloud (Azure): starten wordt geteld, nooit echt gestart."""
    from hotel_checkin.admin import cloud_robot

    starts = []
    monkeypatch.setattr(cloud_robot, "available", lambda: True)
    monkeypatch.setattr(cloud_robot, "running", lambda execs=None: False)
    monkeypatch.setattr(cloud_robot, "start", lambda: starts.append(1) or True)
    return starts


def test_make_first_lets_the_robot_read(setup, robot):
    """Lijst maken in de monitor: eerst leest de robot de reservaties van die dag (folio), dan pas de lijst."""
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    _r("b", "21", DAY + timedelta(days=3), 2)
    t = datetime(2026, 11, 5, 9, 0, tzinfo=TZ)
    assert dl.request("lucca", "breakfast", DAY, by="frederic", send_now=False, now=t)["requested"]
    assert robot == [1] and not repo.daily_lists("lucca", "breakfast")
    assert dl.view("lucca", "breakfast")["pending"] == [DAY.isoformat()]
    # De robot leest wie op die dag in het hotel is, en noteert dat
    assert dl.pending_reads("lucca") == [f"breakfast:{DAY.isoformat()}"]
    assert [r.reservation_id for r in dl.refresh_due("lucca")] == ["a"]
    assert dl.run("lucca", t + timedelta(minutes=1)) == []  # nog niet nagelezen: wachten
    dl.refresh_done("lucca", dl.pending_reads("lucca"), t + timedelta(minutes=3))
    assert dl.pending_reads("lucca") == []
    assert dl.run("lucca", t + timedelta(minutes=4)) == [f"breakfast {DAY.isoformat()}"]
    assert repo.daily_lists("lucca", "breakfast")[0]["generated_by"] == "frederic" and not setup  # niet verstuurd
    assert "nagelezen om 09:03" in repo.robot_runs("lucca", task="ontbijtlijst")[0]["error"]
    assert dl.view("lucca", "breakfast")["pending"] == []


def test_robot_restarted_and_fallback_after_30_minutes(setup, robot):
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    t = datetime(2026, 11, 5, 9, 0, tzinfo=TZ)
    dl.request("lucca", "cleaning", DAY, send_now=True, now=t)
    assert dl.run("lucca", t + timedelta(minutes=2)) == [] and robot == [1]  # net gestart
    assert dl.run("lucca", t + timedelta(minutes=7))[0].endswith("robot gestart om na te lezen") and robot == [1, 1]
    assert dl.run("lucca", t + timedelta(minutes=31)) == [f"cleaning {DAY.isoformat()}"]
    assert len(setup) == 1 and "niet nagelezen" in repo.robot_runs("lucca", task="kuislijst")[0]["error"]


def test_automatic_list_robot_5_minutes_before(setup, robot, monkeypatch):
    monkeypatch.setenv("LUCCA_SCHAKELAARS_ONTBIJTLIJST", "true")
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    today = DAY - timedelta(days=1)
    t = datetime(today.year, today.month, today.day, 17, 39, tzinfo=TZ)
    assert dl.run("lucca", t) == [] and robot == []
    assert dl.run("lucca", t + timedelta(minutes=1))[0].startswith(f"breakfast:{DAY.isoformat()}: aangevraagd")
    assert robot == [1]
    dl.refresh_done("lucca", dl.pending_reads("lucca"), t + timedelta(minutes=3))
    assert dl.run("lucca", t + timedelta(minutes=4)) == []  # nagelezen, maar pas om 17:45 versturen
    assert dl.run("lucca", t + timedelta(minutes=6)) == [f"breakfast {DAY.isoformat()}"] and len(setup) == 1
    assert dl.run("lucca", t + timedelta(minutes=8)) == []  # één keer per dag


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
