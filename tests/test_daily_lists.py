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


def _all_remarks(monkeypatch):
    """Schoonmaaklijst met aantal personen en vrije opmerkingen ([kuislijst] personen en opmerkingen = true)."""
    orig = dl.settings
    monkeypatch.setattr(dl, "settings", lambda h, k: orig(h, k) | ({"persons": True, "notes": True} if k == "cleaning" else {}))


def test_cleaning_list_only_what_housekeeping_needs():
    """Standaard: geen aantal personen en geen vrije opmerkingen (de schoonmaakploeg leest geen Nederlands)."""
    _r("b", "12", DAY, 1, persons=3, remarks="Please a baby cot. Arrival 20h")
    assert _row(dl.build("lucca", "cleaning", DAY), "12")["remark"] == ""


def test_cleaning_list(monkeypatch):
    _all_remarks(monkeypatch)
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
    assert dl.run("lucca", datetime(today.year, today.month, today.day, 16, 59, tzinfo=TZ)) == []
    at = datetime(today.year, today.month, today.day, 17, 0, tzinfo=TZ)
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


def test_make_list_is_done_by_the_robot_and_never_sends(setup, robot):
    """Lijst maken in de monitor: de robot leest de reservaties van die dag (folio) en maakt de lijst, als eigen
    taak in zijn run. Lijst maken verstuurt niets."""
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    _r("b", "21", DAY + timedelta(days=3), 2)
    t = datetime(2026, 11, 5, 9, 0, tzinfo=TZ)
    assert dl.request("lucca", "breakfast", DAY, by="frederic", send_now=False, now=t)["requested"]
    assert robot == [1] and not repo.daily_lists("lucca", "breakfast")
    assert [p["day"] for p in dl.view("lucca", "breakfast")["pending"]] == [DAY.isoformat()]
    # De robot: wie op die dag in het hotel is nalezen, dan de lijst maken
    keys = dl.pending_reads("lucca")
    assert keys == [f"breakfast:{DAY.isoformat()}"]
    assert [r.reservation_id for r in dl.refresh_due("lucca")] == ["a"]
    assert dl.run("lucca", t + timedelta(minutes=1)) == []  # nog niet gemaakt: wachten
    assert dl.robot_make("lucca", keys, t + timedelta(minutes=3)) == keys
    made = repo.daily_lists("lucca", "breakfast")[0]
    assert made["generated_by"] == "frederic" and made["total"] == 2 and not made["sent"]
    assert "nagelezen om 09:03" in repo.robot_runs("lucca", task="ontbijtlijst")[0]["error"]
    assert dl.pending_reads("lucca") == []
    assert dl.run("lucca", t + timedelta(minutes=4)) == [f"breakfast {DAY.isoformat()}"]  # aanvraag afgesloten
    assert not setup and dl.view("lucca", "breakfast")["pending"] == []  # geen mail


def test_make_and_send_robot_makes_function_app_sends(setup, robot):
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    t = datetime(2026, 11, 5, 9, 0, tzinfo=TZ)
    dl.request("lucca", "breakfast", DAY, by="frederic", send_now=True, now=t)
    dl.robot_make("lucca", dl.pending_reads("lucca"), t + timedelta(minutes=3))
    assert not setup  # de robot verstuurt niet
    assert dl.run("lucca", t + timedelta(minutes=4)) == [f"breakfast {DAY.isoformat()}"]
    assert len(setup) == 1 and repo.daily_lists("lucca", "breakfast")[0]["sent"][0]["ok"]
    assert "verstuurd" in repo.robot_runs("lucca", task="ontbijtlijst")[0]["error"]


def test_new_request_replaces_send(setup, robot):
    """Eerst Maken en versturen, daarna Lijst maken: de laatste vraag geldt, er gaat niets weg."""
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    t = datetime(2026, 11, 5, 9, 0, tzinfo=TZ)
    dl.request("lucca", "breakfast", DAY, send_now=True, now=t)
    dl.request("lucca", "breakfast", DAY, send_now=False, now=t + timedelta(minutes=1))
    dl.robot_make("lucca", dl.pending_reads("lucca"), t + timedelta(minutes=3))
    dl.run("lucca", t + timedelta(minutes=4))
    assert not setup


def test_robot_restarted_and_fallback_after_30_minutes(setup, robot):
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    t = datetime(2026, 11, 5, 9, 0, tzinfo=TZ)
    dl.request("lucca", "cleaning", DAY, send_now=True, now=t)
    assert dl.run("lucca", t + timedelta(minutes=2)) == [] and robot == [1]  # net gestart
    assert dl.run("lucca", t + timedelta(minutes=7))[0].endswith("robot gestart") and robot == [1, 1]
    assert dl.run("lucca", t + timedelta(minutes=31)) == [f"cleaning {DAY.isoformat()}"]
    assert len(setup) == 1 and "maakte de lijst niet" in repo.robot_runs("lucca", task="kuislijst")[0]["error"]


def test_automatic_list_uses_the_robot_run_of_that_hour(setup, robot, monkeypatch):
    """Automatische lijst op een vast uur van de robot (17:00): op het uur gevraagd, de robot maakt ze in die run."""
    monkeypatch.setenv("LUCCA_SCHAKELAARS_ONTBIJTLIJST", "true")
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    today = DAY - timedelta(days=1)
    t = datetime(today.year, today.month, today.day, 16, 59, tzinfo=TZ)
    assert dl.run("lucca", t) == [] and robot == []
    assert dl.run("lucca", t + timedelta(minutes=1))[0].startswith(f"breakfast:{DAY.isoformat()}: aangevraagd")
    assert robot == [1]
    dl.robot_make("lucca", dl.pending_reads("lucca"), t + timedelta(minutes=3))
    assert dl.run("lucca", t + timedelta(minutes=4)) == [f"breakfast {DAY.isoformat()}"] and len(setup) == 1
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
    # vuilbak: de lijst van die dag wissen
    assert call("POST", "lists", {"kind": "breakfast", "day": DAY.isoformat(), "action": "delete"}).status_code == 200
    assert json.loads(call("GET", "lists", {"kind": "breakfast"}).get_body())["records"] == []


def test_frozen_when_all_switches_off(monkeypatch):
    """Alle hoofdschakelaars uit (bv. TST als PRD goed loopt): de robot heeft niets te doen en start niet."""
    from hotel_checkin.processes import mail_trigger, send_messages

    monkeypatch.setenv("LUCCA_SCHAKELAARS_RESERVATIES", "false")
    monkeypatch.setenv("LUCCA_ROBOT_MAIL_TRIGGER", "true")
    assert not send_messages.robot_needed("lucca") and not mail_trigger.enabled("lucca")
    monkeypatch.setenv("LUCCA_SCHAKELAARS_RESERVATIES", "true")
    assert send_messages.robot_needed("lucca") and mail_trigger.enabled("lucca")


def test_robot_schedule_from_the_function_app(monkeypatch):
    """Geen schema in Azure: de Function App start de robot op vaste uren (om de [robot] check_minutes vanaf
    middernacht), niet als er sinds dat uur al een run was, nooit als alles uit staat."""
    from hotel_checkin.admin import cloud_robot
    from hotel_checkin.processes import new_reservation, robot_schedule

    starts = []
    monkeypatch.setattr(cloud_robot, "available", lambda: True)
    monkeypatch.setattr(cloud_robot, "running", lambda execs=None: False)
    monkeypatch.setattr(cloud_robot, "start", lambda: starts.append(1) or True)
    monkeypatch.setenv("LUCCA_SCHAKELAARS_RESERVATIES", "true")
    assert robot_schedule.slots(60)[:3] == ["00:00", "01:00", "02:00"] and len(robot_schedule.slots(240)) == 6
    t = datetime(2026, 11, 5, 9, 0, tzinfo=TZ)
    repo.log_robot_run("lucca", new_reservation.TASK, t - timedelta(minutes=30), True)  # 08:30 (meldingsmail)
    assert robot_schedule.run("lucca", t - timedelta(minutes=10)) == ""  # 08:50: run van 08:30 hoort bij dit uur
    assert robot_schedule.run("lucca", t) == "robot gestart op schema" and starts == [1]  # 09:00
    assert robot_schedule.run("lucca", t + timedelta(minutes=2)) == "" and starts == [1]  # net gestart
    repo.log_robot_run("lucca", new_reservation.TASK, t + timedelta(minutes=1), True)  # de run van 09:00
    assert robot_schedule.run("lucca", t + timedelta(minutes=30)) == "" and starts == [1]
    monkeypatch.setenv("LUCCA_SCHAKELAARS_RESERVATIES", "false")  # alles uit: bevroren
    assert robot_schedule.run("lucca", t + timedelta(hours=5)) == "" and starts == [1]


def test_breakfast_per_day_from_lighthouse():
    """Ontbijt als extra met de dagen uit Lighthouse: alleen op die dag, met het aantal van die dag."""
    line = {"label": "Ontbijt", "qty": 5, "amount": 90.0, "days": {DAY.isoformat(): 5}, "room": "20"}
    _r("a", "20", DAY - timedelta(days=2), 3, persons=5, folio=[line])
    assert _row(dl.build("lucca", "breakfast", DAY), "20")["count"] == 5
    other = dl.build("lucca", "breakfast", DAY + timedelta(days=1))  # andere dag: geen ontbijt
    assert _row(other, "20")["count"] is None and not _row(other, "20")["check"]


def test_breakfast_label_on_planboard_means_every_day():
    """Label ONTBIJT op het planbord (ook met de hand gezet): ontbijt elke dag voor iedereen."""
    _r("a", "24", DAY - timedelta(days=1), 2, persons=2, pms_labels=["ONTBIJT"])
    assert _row(dl.build("lucca", "breakfast", DAY), "24")["count"] == 2


def test_planboard_labels_parse():
    from hotel_checkin.pms.lighthouse_parse import parse_planboard_labels

    html = """<div class="unitlabel" data-labelid="15912" data-labelname="ONTBIJT"></div>
      <div data-reservation="ABC" data-accommodationid="a1" data-labelids="15912,7"></div>
      <div data-reservation="def" data-accommodationid="a2" data-labelids=""></div>"""
    assert parse_planboard_labels(html) == {"abc": ["7", "ONTBIJT"], "def": []}


def test_booking_boilerplate_is_not_a_remark():
    words = dl.settings("lucca", "cleaning")["words"]
    text = ("Kinderen en extra bedden: Kinderen van alle leeftijden zijn toegestaan. U heeft geen kinderbedjes "
            "toegevoegd. U heeft geen extra bedden toegevoegd. Graag een babybed voor onze zoon.")
    assert dl.notes([text], words) == ["Graag een babybed voor onze zoon."]


# ---------------------------------------------------------------- planbord (per kamer eigen data, personen, labels)

PLANBOARD = Path(__file__).parent / "fixtures" / "planboard_2026-11-07.html"  # planbord van 7/11, zonder gastnamen


def _plan(day):
    from hotel_checkin.pms.lighthouse_parse import parse_planboard_stays

    parsed = parse_planboard_stays(PLANBOARD.read_text())
    dl.save_planboard("lucca", day, parsed, datetime(2026, 11, 7, 8, 0, tzinfo=TZ))
    return parsed


def test_planboard_parse():
    from hotel_checkin.pms.lighthouse_parse import parse_planboard_stays

    parsed = parse_planboard_stays(PLANBOARD.read_text())
    assert parsed["units"]["51902"] == {"room": "20", "name": "FAMILY APARTMENT"}
    assert parsed["units"]["47192"]["room"] == "11"  # "11 - SUPERIOR DOUBLE ROOM"
    assert parsed["units"]["45333"]["room"] == ""  # DUMMY
    apt = next(x for x in parsed["stays"] if x["room"] == "20" and x["arrival"] == "2026-11-06")
    assert apt["persons"] == 6 and apt["labels"] == ["LATE ARRIVAL", "ONTBIJT"] and apt["departure"] == "2026-11-08"


def test_cleaning_from_planboard():
    day = date(2026, 11, 7)
    _plan(day)
    # De groep (7 kamers, 6/11 tot 8/11) kent de robot als één reservatie met maar één kamer: het planbord geeft ze allemaal
    _r("ce6dec79-f6e4-41ad-8f7b-92b08ad9dd88", "22", date(2026, 11, 6), 2, persons=14,
       remarks="Graag een babybed in de kamer")
    data = dl.build("lucca", "cleaning", day)
    rows = [x for x in data["rows"] if not x.get("sep")]
    pick = lambda k: sorted((x["room"] for x in rows if x[k]), key=int)
    assert pick("leave") == ["12", "14", "30", "31"]
    assert pick("stay") == ["11", "15", "16", "20", "22", "24", "25", "32"]
    assert pick("checkin") == ["12", "21", "30", "31", "33"]
    assert data["totals"] == {"leave": 4, "stay": 8, "checkin": 5}
    assert "Double opmaken" not in _row(data, "32")["remark"]  # label DOUBLE OPMAKEN telt alleen op een twin kamer
    assert "Late arrival" in _row(data, "30")["remark"] and "Late arrival" not in _row(data, "31")["remark"]  # vertrekker
    assert _row(data, "12")["remark"] == ""  # standaard geen aantal personen
    assert _row(data, "24")["desc"] == "QUAD KAMER - 2e verdiep"  # omschrijving uit het planbord
    assert data["source"].startswith("planbord van 08:00")
    assert not any("babybed" in x["remark"] for x in rows)  # vrije opmerking van de groep: standaard niet (stond bij 16)


def test_breakfast_from_planboard():
    day = date(2026, 11, 7)
    _plan(day)
    data = dl.build("lucca", "breakfast", day)
    assert _row(data, "20")["count"] == 6  # label ONTBIJT, 6 personen (CPB-4276-002390)
    assert _row(data, "15")["count"] == 2 and _row(data, "14")["count"] == 1
    assert _row(data, "12")["count"] == 1  # wie de nacht ervoor sliep, niet wie op 7/11 aankomt
    assert _row(data, "11")["check"]  # label, maar aantal personen niet op het planbord
    s31 = _row(data, "31")  # geen label en reservatie niet gekend: nakijken
    assert s31["check"] and s31["count"] is None and "nakijken" in s31["remark"]
    assert _row(data, "33")["count"] is None and not _row(data, "33")["check"]  # komt pas aan


def test_robot_reads_planboard_for_requested_list(robot, monkeypatch):
    """Lijst maken (knop of uur): de robot opent Lighthouse, leest het planbord en maakt de lijst, ook met de
    schakelaar Reservaties uit en zonder reservaties om na te lezen."""
    from contextlib import contextmanager

    from hotel_checkin.pms import lighthouse
    from hotel_checkin.pms.lighthouse_parse import parse_planboard_stays
    from hotel_checkin.processes import pay_requests, refresh_contacts

    monkeypatch.setenv("LUCCA_SCHAKELAARS_RESERVATIES", "false")
    day = date(2026, 11, 8)
    opened, asked = [], []

    @contextmanager
    def connect(hotel_id):
        opened.append(hotel_id)
        yield object()

    def stays(hotel_id, start, end, lh):
        asked.append((start, end))
        return parse_planboard_stays(PLANBOARD.read_text())

    monkeypatch.setattr(lighthouse, "connect", connect)
    monkeypatch.setattr(lighthouse, "planboard_stays", stays)
    monkeypatch.setattr(pay_requests, "run", lambda *a: {"todo": 0, "made": [], "errors": [], "left": 0})
    dl.request("lucca", "cleaning", day, by="frederic", now=datetime(2026, 11, 7, 9, 0, tzinfo=TZ))
    refresh_contacts.run("lucca")
    assert opened == ["lucca"] and asked == [(date(2026, 11, 7), day)]
    made = repo.get_daily_list("lucca", "cleaning", day.isoformat())
    assert made["totals"] == {"leave": 13, "stay": 0, "checkin": 9} and made["source"].startswith("planbord van")
    assert dl.pending_reads("lucca") == []


def test_cleaning_twin_and_special_request():
    """Twin kamer (16): DOUBLE OPMAKEN bij de opmerkingen. SPECIAAL VERZOEK: de interne memo, of nakijken."""
    day = date(2026, 11, 8)
    _plan(day)
    data = dl.build("lucca", "cleaning", day)
    assert _row(data, "16")["remark"] == "DOUBLE"  # label DOUBLE OPMAKEN als DOUBLE ([kuislijst] label_tekst)
    day = date(2026, 11, 9)
    _plan(day)
    s14 = _row(dl.build("lucca", "cleaning", day), "14")  # label SPECIAAL VERZOEK, memo nog niet gelezen
    assert s14["check"] and "interne memo nakijken" in s14["remark"]
    _r("51299db6-b392-4f28-8728-2d66444f5c85", "14", day, 1, internal_memo="Bloemen en kaartje op de kamer")
    s14 = _row(dl.build("lucca", "cleaning", day), "14")
    assert not s14["check"] and "Speciaal verzoek: Bloemen en kaartje op de kamer" in s14["remark"]


def test_pdf_and_signed_link(monkeypatch):
    """De pdf voor de WhatsApp aan het personeel: alleen met een geldige, niet vervallen link."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    _r("c", "23", DAY - timedelta(days=1), 3, folio=[{"label": "Ontbijt", "qty": 2, "amount": 40.0}],
       remarks="Graag 1pax glutenfree ontbijt 🥐")  # emoji: geen fout in de pdf
    data = dl.generate("lucca", "breakfast", DAY)
    content = lists.pdf(data, "Hotel Lucca")
    assert content[:5] == b"%PDF-" and lists.pdf_name(data) == f"ontbijtlijst-{DAY.isoformat()}.pdf"
    now = datetime(2026, 11, 5, 17, 45, tzinfo=TZ)
    path = dl.pdf_path("lucca", data, now)
    hotel, kind, day, expires, sig, name = path.split("/")
    assert (hotel, kind, day, name) == ("lucca", "breakfast", DAY.isoformat(), lists.pdf_name(data))
    assert dl.pdf_for_link(hotel, kind, day, expires, sig, now)[1][:5] == b"%PDF-"
    assert dl.pdf_for_link(hotel, kind, day, expires, "0" * 32, now) is None  # andere handtekening
    assert dl.pdf_for_link(hotel, "cleaning", day, expires, sig, now) is None  # ander lijst
    assert dl.pdf_for_link(hotel, kind, day, expires, sig, now + timedelta(hours=25)) is None  # vervallen
    cleaning = dl.generate("lucca", "cleaning", DAY)
    assert lists.pdf(cleaning, "Hotel Lucca")[:5] == b"%PDF-"

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import function_app as fa

    monkeypatch.setattr(dl, "datetime", type("D", (datetime,), {"now": staticmethod(lambda tz=None: now)}))
    fn = fa.list_pdf.build().get_user_function()
    req = func.HttpRequest("GET", "/api/lists/" + path, body=b"", route_params=dict(zip(
        ("hotel", "kind", "day", "expires", "sig", "name"), path.split("/"), strict=True)))
    res = fn(req)
    assert res.status_code == 200 and res.mimetype == "application/pdf" and res.get_body()[:5] == b"%PDF-"


def test_whatsapp_list_with_pdf(monkeypatch):
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    from hotel_checkin.processes import send_messages

    orig = dl.settings
    monkeypatch.setattr(dl, "settings", lambda h, k: orig(h, k) | {"email": [], "whatsapp": ["0470 12 34 56"]})
    monkeypatch.setattr(send_messages, "phone_enabled", lambda h: True)
    monkeypatch.setattr(send_messages, "whatsapp_template", lambda h, s, lang: "HX" + s)
    sent = []
    monkeypatch.setattr("hotel_checkin.messaging.whatsapp.send_whatsapp_template",
                        lambda h, to, sid, v, **k: sent.append((to, sid, v)) or SendResult(Channel.WHATSAPP, to, True))
    _r("a", "20", DAY - timedelta(days=1), 2, rate="STANDARD RATE BREAKFAST INCL")
    data = dl.build("lucca", "breakfast", DAY)
    out = dl.send("lucca", data)
    to, sid, v = sent[0]
    assert out[0]["ok"] and to == "+32470123456" and sid == "HXbreakfast_list"
    assert v["1"] == lists.day_text(DAY.isoformat()) and v["2"].startswith("2 personen in 1 kamers")
    assert "volgens" not in v["2"] and v["3"].startswith(f"lucca/breakfast/{DAY.isoformat()}/")
