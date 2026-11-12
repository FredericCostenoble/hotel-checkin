"""Label ONTBIJT op het planbord (processes/breakfast_labels.py)."""

from datetime import date, timedelta

import pytest

from hotel_checkin.core.models import Guest, Reservation
from hotel_checkin.guests import repository as repo
from hotel_checkin.pms.lighthouse_parse import parse_planboard
from hotel_checkin.processes import breakfast_labels as bl

TODAY = date(2026, 11, 2)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    repo.use_memory_store()
    monkeypatch.setenv("APP_ENV", "prd")
    monkeypatch.setenv("LUCCA_SCHAKELAARS_ONTBIJT_LABELS", "true")


def _r(rate="STANDARD RATE BREAKFAST EXCL", folio=(), persons=2, nights=3, rid="r1", arrival_in=3):
    a = TODAY + timedelta(days=arrival_in)
    r = Reservation("lucca", rid, Guest("Ann", "Brand"), a, a + timedelta(days=nights), source="Booking.com",
                    rate_plan=rate, guest_count=persons)
    r.folio = [{"label": "Superior double - " + rate, "qty": None, "amount": 300.0}, *folio]
    return r


def test_rules():
    assert bl.breakfast(_r("NRF BREAKFAST INCL"))[0]
    assert not bl.breakfast(_r("LAST MINUTE"))[0]  # zonder vermelding: geen ontbijt
    assert not bl.breakfast(_r("NRF BREAKFAST EXCL"))[0]
    six = [{"label": "Ontbijt", "qty": 6, "amount": 120.0}]
    yes, why = bl.breakfast(_r(folio=six))
    assert yes and "6 ontbijten" in why and "2 personen x 3 nachten" in why
    no, why = bl.breakfast(_r(folio=[{"label": "Ontbijt", "qty": 3, "amount": 60.0}]))
    assert not no and "maar 3 van 6" in why


PLANBOARD = """<div class="unitlabel" data-labelid="15912" data-labelname="ONTBIJT"></div>
<div class="unitlabel" data-labelid="15913" data-labelname="LATE ARRIVAL"></div>
<div class="reservation acco_a1" data-reservation="r1" data-accommodationid="a1" data-labelids="15913" data-unit="51902"></div>
<div class="reservation acco_a1" data-reservation="r1" data-accommodationid="a1" data-labelids="15913"></div>
<div class="reservation acco_b1" data-reservation="other" data-accommodationid="b1" data-labelids=""></div>"""


def test_parse_planboard():
    p = parse_planboard(PLANBOARD, "r1")
    assert p["names"]["ONTBIJT"] == "15912"
    assert p["rooms"] == [{"accommodation_id": "a1", "unit": "51902", "labels": ["15913"]}]


def test_label_added_keeps_existing_and_only_once(monkeypatch):
    r = repo.save_reservation(_r("NRF BREAKFAST INCL"))
    state = {"labels": ["15913"]}
    posted = []
    monkeypatch.setattr(bl.lighthouse, "reservation_labels", lambda *a: {
        "rooms": [{"accommodation_id": "a1", "unit": "", "labels": list(state["labels"])}],
        "names": {"ONTBIJT": "15912"}})

    def add(h, rid, acc, current, label_id, lh):
        posted.append((acc, current, label_id))
        state["labels"] = [*current, label_id]

    monkeypatch.setattr(bl.lighthouse, "add_label", add)
    result = bl.run("lucca", None, TODAY)
    assert posted == [("a1", ["15913"], "15912")]  # LATE ARRIVAL blijft staan
    assert len(result["labeled"]) == 1 and repo.get_reservation("lucca", r.reservation_id).breakfast_labeled_at
    assert bl.run("lucca", None, TODAY)["checked"] == 0 and len(posted) == 1  # onthouden


def test_switch_off_does_nothing(monkeypatch):
    monkeypatch.delenv("LUCCA_SCHAKELAARS_ONTBIJT_LABELS")
    repo.save_reservation(_r("NRF BREAKFAST INCL"))
    assert bl.due("lucca", TODAY) == [] and bl.run("lucca", None, TODAY)["off"]


def test_new_reservation_folio_read_once_then_label(monkeypatch):
    """Nieuw, folio nog niet gekend: één keer lezen; ontbijt bijgeboekt voor alle personen en nachten: label."""
    r = _r("STANDARD RATE BREAKFAST EXCL", arrival_in=200)  # ver in de toekomst: ook nagekeken
    r.folio = []
    repo.save_reservation(r)
    assert bl.due("lucca", TODAY)  # folio onbekend: nakijken
    detail = _r("STANDARD RATE BREAKFAST EXCL", folio=[{"label": "Ontbijt", "qty": 6, "amount": 120.0}],
                arrival_in=200)
    reads = []
    monkeypatch.setattr(bl.lighthouse, "get_reservation",
                        lambda h, rid, lh, contact=True: reads.append(rid) or detail)
    monkeypatch.setattr(bl.lighthouse, "reservation_labels", lambda *a: {
        "rooms": [{"accommodation_id": "a1", "unit": "", "labels": ["15912"]}], "names": {"ONTBIJT": "15912"}})
    monkeypatch.setattr(bl.lighthouse, "add_label", lambda *a: None)
    result = bl.run("lucca", None, TODAY)
    assert reads == ["r1"] and result["read"] == 1 and len(result["labeled"]) == 1


def test_no_breakfast_known_folio_not_read_again():
    repo.save_reservation(_r("STANDARD RATE BREAKFAST EXCL"))  # folio gekend, geen ontbijt
    assert bl.due("lucca", TODAY) == []


def test_including_breakfast_rate_in_normal_case():
    from datetime import date

    from hotel_checkin.core.models import Guest, Reservation
    from hotel_checkin.processes.breakfast_labels import breakfast

    r = Reservation("lucca", "x", Guest("E", "B"), date(2026, 11, 6), date(2026, 11, 8), guest_count=6)
    r.folio = [{"label": "Family apartment - Non-refundable rate including breakfast BDC", "qty": None, "amount": 796.07},
               {"label": "Citytax", "qty": 12, "amount": 50.4}]
    assert breakfast(r)[0]


def test_not_yet_placed_is_status_not_error(monkeypatch):
    """Nog geen kamer op het planbord (nieuw, nog niet geplaatst): geen fout, label volgt in een latere run."""
    r = repo.save_reservation(_r("NRF BREAKFAST INCL"))
    monkeypatch.setattr(bl.lighthouse, "reservation_labels", lambda *a: {"rooms": [], "names": {"ONTBIJT": "15912"}})
    logged = []
    monkeypatch.setattr(bl.guests, "log_robot_run", lambda *a, **k: logged.append((a, k)))
    result = bl.run("lucca", None, TODAY)
    assert result["errors"] == [] and len(result["unplaced"]) == 1
    assert not repo.get_reservation("lucca", r.reservation_id).breakfast_labeled_at  # volgende run opnieuw
    bl.log_run("lucca", TODAY, result)
    (_, _, _, ok, *_), kw = logged[0]
    note = logged[0][0][-1]
    assert ok and kw["skipped"] == 0 and "nog niet geplaatst" in note and "fout" not in note
