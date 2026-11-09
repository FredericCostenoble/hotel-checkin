"""Zelftest van Lighthouse: probleem -> bewijs, niets meer schrijven, rode waarschuwing; opgelost -> weer schrijven."""

from datetime import date

import pytest

from hotel_checkin.core import safety
from hotel_checkin.guests import repository as repo
from hotel_checkin.pms import lighthouse
from hotel_checkin.processes import oversight, pms_health


@pytest.fixture(autouse=True)
def memory(monkeypatch):
    repo.use_memory_store()
    pms_health._cache.clear()
    monkeypatch.setattr(pms_health.clock, "today", lambda h: date(2026, 11, 9))


def _test(monkeypatch, broken: bool):
    def fake(hotel_id, lh, sample, day):
        parts = [{"part": "reservatielijst", "ok": True, "why": "", "html": ""},
                 {"part": "detailpagina", "ok": not broken, "why": "blok Interne memo niet gevonden" if broken else "",
                  "html": "<html>nieuwe pagina</html>" if broken else ""},
                 {"part": "planbord", "ok": True, "why": "", "html": ""}]
        return parts
    monkeypatch.setattr(lighthouse, "self_test", fake)


def test_once_a_day(monkeypatch):
    _test(monkeypatch, False)
    assert pms_health.due("lucca")
    st = pms_health.run("lucca", object())
    assert st["ok"] and not pms_health.due("lucca") and not pms_health.blocked("lucca")


def test_change_blocks_writes_keeps_evidence_and_warns(monkeypatch):
    _test(monkeypatch, True)
    st = pms_health.run("lucca", object())
    assert st["ok"] is False and pms_health.blocked("lucca")
    assert not safety.may_write_pms("lucca", "Anna", "Peeters")  # PRD, maar Lighthouse veranderd: niets schrijven
    ev = repo.evidence_list("lucca")
    assert ev[0]["part"] == "detailpagina" and repo.get_evidence("lucca", ev[0]["key"]) == "<html>nieuwe pagina</html>"
    warn = oversight.health_warning("lucca")
    assert warn.startswith("LIGHTHOUSE IS VERANDERD")
    html = oversight.report.overview_html("t", [], [], "/m", banners=[("red", warn)])
    assert "#B42318" in html and "LIGHTHOUSE IS VERANDERD" in html
    # Opgelost (bv. na een herstelling): de volgende zelftest is in orde, de robot mag weer schrijven
    _test(monkeypatch, False)
    pms_health.run("lucca", object())
    assert not pms_health.blocked("lucca") and safety.may_write_pms("lucca", "Anna", "Peeters")
    assert oversight.health_warning("lucca") is None
