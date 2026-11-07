"""Moeilijk trappen lopen: vraag op het check-in-formulier, interne memo in Lighthouse, schoonmaaklijst."""

from datetime import UTC, date, datetime

import pytest

from hotel_checkin.checkin import service
from hotel_checkin.core.models import Guest, Reservation
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import stairs_memo


@pytest.fixture(autouse=True)
def memory():
    repo.use_memory_store()


def _save(room_type="Twin room", token="tok", arrival=date(2099, 1, 1), **kw):
    r = Reservation("lucca", "R1", Guest("Anna", "Peeters", "anna@example.com", None, "nl"), arrival,
                    date(2099, 1, 3), room_type=room_type, token=token, rooms=["16"], booking_number="CPB-1", **kw)
    return repo.save_reservation(r)


def test_question_only_for_ordinary_rooms():
    assert service.stairs_question("lucca", "Twin room")["nl"]["q"].startswith("Een van de gasten")
    assert service.stairs_question("lucca", "Family apartment") is None  # appartement: geen andere kamer
    assert service.stairs_question("lucca", "Historical Suite") is None
    assert service.stairs_question("lucca", "Superior double", ["FAMILY APARTMENT"]) is None


def test_form_stores_answer_only_when_asked():
    _save()
    assert service.form_data("tok")["stairs"] and service.form_data("tok")["stairs_help"] is False
    ok, _ = service.submit("tok", {"email": "anna@example.com", "language": "nl", "stairs_help": True})
    assert ok and repo.get_reservation("lucca", "R1").stairs_help is True
    assert service.form_data("tok")["stairs_help"] is True
    service.submit("tok", {"email": "anna@example.com", "language": "nl", "stairs_help": False})
    assert repo.get_reservation("lucca", "R1").stairs_help is False


def test_form_ignores_answer_for_apartment():
    _save(room_type="Family apartment")
    assert service.form_data("tok")["stairs"] is None
    service.submit("tok", {"email": "anna@example.com", "language": "nl", "stairs_help": True})
    assert repo.get_reservation("lucca", "R1").stairs_help is None


def test_parse_internal_memo_form():
    from hotel_checkin.pms.lighthouse_parse import parse_internal_memo_form

    html = ('<form action="/Customer/Reservations/EditInternalMemo" class="form-horizontal" id="frm-edit-internal-memo" '
            'method="post"><input data-val="true" id="ID" name="ID" type="hidden" value="51299db6" />'
            '<textarea class="form-control" id="InternalMemo" name="InternalMemo" rows="2">\r\nwilt douche, geen bad</textarea>'
            '<button type="submit">Bewaren</button><input name="__RequestVerificationToken" type="hidden" value="CfDJ8&amp;x" />'
            '</form>')
    f = parse_internal_memo_form(html)
    assert f == {"action": "/Customer/Reservations/EditInternalMemo", "memo": "wilt douche, geen bad",
                 "fields": {"ID": "51299db6", "__RequestVerificationToken": "CfDJ8&x"}}


def test_robot_appends_memo_once(monkeypatch):
    from hotel_checkin.pms import lighthouse

    monkeypatch.setenv("LUCCA_SCHAKELAARS_RESERVATIES", "true")
    monkeypatch.setattr("hotel_checkin.core.safety.is_production", lambda: True)
    _save(stairs_help=True, internal_memo="wilt douche, geen bad")
    monkeypatch.setattr(stairs_memo, "settings", lambda h: {"memo": stairs_memo.DEFAULT_MEMO, "label": "", "max_floor": 1})
    calls = []
    monkeypatch.setattr(lighthouse, "append_internal_memo", lambda h, rid, line, lh: calls.append(line) or "added")
    today = date(2099, 1, 1)
    assert [r.reservation_id for r in stairs_memo.due("lucca", today)] == ["R1"]
    result = stairs_memo.run("lucca", object(), today)
    assert result["done"] == ["CPB-1 (memo aangevuld)"] and calls == [stairs_memo.settings("lucca")["memo"]]
    r = repo.get_reservation("lucca", "R1")
    assert r.stairs_memo_at and r.internal_memo.startswith("wilt douche, geen bad\n")
    assert stairs_memo.due("lucca", today) == []  # één keer


def test_not_outside_prd_for_real_guests(monkeypatch):
    monkeypatch.setenv("LUCCA_SCHAKELAARS_RESERVATIES", "true")
    monkeypatch.setattr("hotel_checkin.core.safety.is_production", lambda: False)
    _save(stairs_help=True)
    assert stairs_memo.due("lucca", date(2099, 1, 1)) == []


def test_cleaning_list_remark():
    from hotel_checkin.processes import daily_lists as dl

    _save(stairs_help=True, stairs_memo_at=datetime.now(UTC))
    data = dl.build_cleaning("lucca", date(2099, 1, 1), repo.list_reservations("lucca"), [])
    row = next(x for x in data["rows"] if x.get("room") == "16")
    assert row["checkin"] and dl.STAIRS_REMARK in row["remark"]


def test_append_internal_memo_keeps_existing_text():
    from hotel_checkin.pms import lighthouse

    memo = {"text": "wilt douche, geen bad"}
    posted = []

    class Resp:
        def __init__(self, body=""):
            self.ok, self.status, self.url, self.body = True, 200, "https://x/Customer/Reservations/Detail/1", body

        def text(self):
            return self.body

    def page():
        return ('<form action="/Customer/Reservations/EditInternalMemo" id="frm-edit-internal-memo" method="post">'
                '<input name="ID" type="hidden" value="1" /><textarea id="InternalMemo" name="InternalMemo">\n'
                + memo["text"] + '</textarea><input name="__RequestVerificationToken" type="hidden" value="t" /></form>')

    class Req:
        def get(self, url, **k):
            return Resp(page())

        def post(self, url, form=None, **k):
            posted.append((url, form))
            memo["text"] = form["InternalMemo"]
            return Resp()

    class Session:
        base = "https://x"
        page = type("P", (), {"request": Req()})()

    line = "Moeilijk ter been (check-in-formulier): lagere verdieping indien vrij"
    assert lighthouse.append_internal_memo("lucca", "1", line, Session()) == "added"
    assert posted == [("https://x/Customer/Reservations/EditInternalMemo",
                       {"ID": "1", "__RequestVerificationToken": "t", "InternalMemo": "wilt douche, geen bad\n" + line})]
    assert lighthouse.append_internal_memo("lucca", "1", line, Session()) == "present" and len(posted) == 1


def test_label_only_on_low_floor(monkeypatch):
    """NIET VERPLAATSEN alleen als de gast al op een lage verdieping ligt; later verplaatst naar beneden: alsnog."""
    from hotel_checkin.pms import lighthouse

    monkeypatch.setenv("LUCCA_SCHAKELAARS_RESERVATIES", "true")
    monkeypatch.setattr("hotel_checkin.core.safety.is_production", lambda: True)
    monkeypatch.setattr(lighthouse, "append_internal_memo", lambda *a: "added")
    labels = []
    monkeypatch.setattr(lighthouse, "reservation_labels", lambda *a: {
        "names": {"NIET VERPLAATSEN": "15907"}, "rooms": [{"accommodation_id": "acc", "labels": ["15912"]}]})
    monkeypatch.setattr(lighthouse, "add_label", lambda h, rid, acc, cur, lid, lh: labels.append((acc, cur, lid)))
    r = _save(stairs_help=True)
    r.rooms = ["32"]  # 3e verdieping: alleen de memo
    repo.save_reservation(r)
    today = date(2099, 1, 1)
    assert stairs_memo.run("lucca", object(), today)["done"] == ["CPB-1 (memo aangevuld)"] and labels == []
    assert stairs_memo.due("lucca", today) == []  # niets meer te doen zolang hij boven ligt
    r = repo.get_reservation("lucca", "R1")
    r.rooms = ["12"]  # verplaatst naar de 1e verdieping
    repo.save_reservation(r)
    done = stairs_memo.run("lucca", object(), today)["done"]
    assert done == ["CPB-1 (label NIET VERPLAATSEN (kamer 12))"] and labels == [("acc", ["15912"], "15907")]
    assert stairs_memo.due("lucca", today) == []
