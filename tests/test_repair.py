"""Herstelling na een wijziging in Lighthouse: wat de mensen zien en de knop naar PRD op TST."""

import json

import pytest

from hotel_checkin.admin import github
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import oversight, pms_health, repair

FIX = {"id": "202611091200", "summary": "Aankomst staat nu in een ander blok; de robot leest het daar."}


@pytest.fixture(autouse=True)
def setup(monkeypatch, tmp_path):
    repo.use_memory_store()
    pms_health._cache.clear()
    repair._cache.clear()
    monkeypatch.setenv("APP_ENV", "tst")
    monkeypatch.setattr(repair, "build", lambda: {"version": 360, "sha": "abc", "built_utc": "2026-11-09T11:00:00"})
    monkeypatch.setattr(repair, "own_repair", lambda: FIX)
    monkeypatch.setattr(github, "available", lambda: True)
    monkeypatch.setattr(github, "last_deploy", lambda e: {"prd": {"version": 354, "sha": "old"},
                                                          "tst": {"version": 360, "sha": "abc"}}[e])
    monkeypatch.setattr(github, "json_on_main", lambda p: FIX)
    monkeypatch.setattr(github, "json_at", lambda p, ref: None)
    monkeypatch.setattr(github, "main_sha", lambda: "abc")
    runs = []
    monkeypatch.setattr(github, "run_workflow", lambda w, inputs: runs.append((w, inputs)))
    return runs


def _health(ok, at="2026-11-09T11:05:00+00:00"):
    repo.set_state("lucca", pms_health.STATE, json.dumps({"ok": ok, "checked_at": at, "failures": [] if ok else [
        {"part": "detailpagina", "why": "blok Interne memo niet gevonden"}], "since": at}))
    pms_health._cache.clear()


def test_only_frederic_and_seppe():
    assert repair.allowed("lucca", "Frederic@hotellucca.be") and repair.allowed("lucca", "management@hotellucca.be")
    assert not repair.allowed("lucca", "iemand@hotellucca.be") and not repair.allowed("lucca", None)


def test_tst_banner_and_promote_after_selftest(setup):
    _health(None, at="")
    s = repair.status("lucca")
    assert not s["can_promote"] and "zelftest" in s["why_not"]
    banner = oversight.monitor_banner("lucca", s)
    assert banner["level"] == "blue" and banner["promote"] and "PRD draait nog v354" in banner["lines"][0]
    assert "nog bezig" in banner["lines"][2]
    ok, msg = repair.promote("lucca", "management@hotellucca.be")
    assert not ok and "zelftest" in msg and setup == []
    _health(True)  # zelftest op TST met deze versie in orde
    assert repair.status("lucca")["can_promote"]
    assert not repair.promote("lucca", "iemand@hotellucca.be")[0]
    ok, msg = repair.promote("lucca", "management@hotellucca.be")
    assert ok and setup == [("deploy.yml", {"environment": "prd"})]


def test_prd_mail_tells_what_to_do(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prd")
    _health(False)
    steps = oversight.repair_steps("lucca")
    assert steps[0].startswith("Er staat een oplossing klaar om te testen") and any("TST" in x or "testomgeving" in x
                                                                                   for x in steps)
    assert oversight.health_warning("lucca").startswith("LIGHTHOUSE IS VERANDERD")
    assert oversight.monitor_banner("lucca", repair.status("lucca"))["level"] == "red"


def test_new_problem_asks_the_repair_robot(setup, monkeypatch):
    from hotel_checkin.pms import lighthouse

    monkeypatch.setattr(lighthouse, "self_test", lambda *a: [{"part": "planbord", "ok": False, "why": "x", "html": ""}])
    pms_health.run("lucca", object())
    pms_health.run("lucca", object())  # zelfde probleem: niet opnieuw
    assert setup == [("repair.yml", {"environment": "tst", "hotel": "lucca"})]


def test_selftest_right_after_deploy_on_prd_only_when_blocked(setup, monkeypatch):
    from hotel_checkin.admin import cloud_robot

    started = []
    monkeypatch.setattr(cloud_robot, "start", lambda: started.append(1))
    monkeypatch.setenv("APP_ENV", "prd")
    monkeypatch.setattr(repair, "env", lambda: "prd")
    _health(True, at="2026-11-09T00:01:00+00:00")  # PRD in orde: geen extra run
    assert not repair.ensure_selftest("lucca") and started == []
    _health(False, at="2026-11-09T00:01:00+00:00")  # geblokkeerd, zelftest van voor de uitrol: meteen opnieuw
    assert repair.ensure_selftest("lucca") and started == [1]
    assert repo.get_state("lucca", repair.SELFTEST_REQUEST) == "360"  # pms_health.due ziet de vraag
    assert not repair.ensure_selftest("lucca") and started == [1]  # één keer per versie
