"""Proces: herstellen na een wijziging in Lighthouse, ook als Frederic er niet is.

1. De zelftest (processes/pms_health.py) vindt een probleem: de robot schrijft niets meer in Lighthouse en
   vraagt de herstelrobot een oplossing (GitHub-workflow repair.yml, één keer per probleem).
2. De herstelrobot past de code aan met het bewaarde bewijs. Slagen alle tests, dan gaat de oplossing vanzelf
   naar TST (nooit naar PRD). Ze laat een notitie achter in config/repair.json (id, wat er veranderde).
3. Op TST draait de zelftest meteen opnieuw (ensure_selftest), op het echte Lighthouse.
4. De mail en de monitor zeggen in gewone woorden wat er aan de hand is en wat te doen. Op TST kunnen alleen
   de mensen uit [beheer] prd_vrijgeven de oplossing naar PRD zetten (promote), en alleen als de zelftest op TST
   in orde is en er intussen niets anders bij kwam.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime

from hotel_checkin.admin import github
from hotel_checkin.core import safety
from hotel_checkin.core.config import get_setting
from hotel_checkin.core.hotels import hotels_dir, load_hotel
from hotel_checkin.guests import repository as guests

TASK = "herstelling"
SELFTEST_REQUEST = "pms_health_request"  # RobotState: de zelftest moet opnieuw (nieuwe versie op TST)
_cache: dict[str, tuple[float, dict]] = {}


def _read(name: str) -> dict:
    try:
        return json.loads((hotels_dir().parent / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build() -> dict:
    """Deze versie: {"version", "sha", "built"} (config/build.json, geschreven bij de uitrol)."""
    return _read("build.json")


def own_repair() -> dict:
    """De laatste herstelling in deze versie: {"id", "summary", "at"} (config/repair.json) of {}."""
    return _read("repair.json")


def env() -> str:
    return "prd" if safety.is_production() else "tst"


def allowed(hotel_id: str, user: str | None) -> bool:
    users = [str(u).strip().lower() for u in load_hotel(hotel_id).get("beheer", {}).get("prd_vrijgeven", [])]
    return bool(user) and user.strip().lower() in users


def tst_url() -> str:
    return get_setting("TST_MONITOR_URL", default="https://func-checkin-tst-jplymq.azurewebsites.net/monitor/",
                       required=False)


def request(hotel_id: str, failures: list[dict]) -> str:
    """De herstelrobot vragen een oplossing te zoeken (vanuit de zelftest, één keer per probleem)."""
    if not github.available():
        return "herstelrobot niet ingesteld (geen GitHub-token)"
    try:
        github.run_workflow("repair.yml", {"environment": env(), "hotel": hotel_id})
    except Exception as exc:
        logging.exception("herstelrobot niet gestart")
        return f"herstelrobot niet gestart: {type(exc).__name__}"
    return "herstelrobot gevraagd een oplossing te zoeken"


def status(hotel_id: str, fresh: bool = False) -> dict:
    """Wat draait waar, en staat er een oplossing klaar? (GitHub, 5 minuten onthouden)
    {"env", "version", "repair", "prd", "tst", "fix_on_tst", "fix", "health", "can_promote", "why_not"}"""
    from hotel_checkin.processes import pms_health

    now = time.monotonic()
    hit = _cache.get(hotel_id)
    if hit and not fresh and now - hit[0] < 300:
        out = dict(hit[1])
    else:
        out = {"env": env(), "version": build().get("version"), "sha": build().get("sha", ""),
               "repair": own_repair(), "prd": None, "tst": None, "fix": None, "fix_on_tst": False,
               "github": github.available()}
        if github.available():
            try:
                out["prd"], out["tst"] = github.last_deploy("prd"), github.last_deploy("tst")
                main_repair = github.json_on_main("config/repair.json") or {}
                prd_repair = (github.json_at("config/repair.json", out["prd"]["sha"]) or {}) if out["prd"] else {}
                fix = main_repair if main_repair.get("id") and main_repair.get("id") != prd_repair.get("id") else None
                out["fix"] = fix
                out["fix_on_tst"] = bool(fix and out["tst"] and out["tst"]["sha"] == github.main_sha())
            except Exception as exc:  # noqa: BLE001 - zonder GitHub geen knop, de rest werkt
                logging.warning("GitHub niet bereikbaar: %s", exc)
                out["github_error"] = type(exc).__name__
        _cache[hotel_id] = (now, dict(out))
    health = pms_health.state(hotel_id)
    out["health"] = {"ok": health.get("ok"), "checked_at": health.get("checked_at", ""),
                     "failures": health.get("failures", []), "since": health.get("since", "")}
    tested = bool(health.get("ok")) and health.get("checked_at", "") >= (build().get("built_utc") or "")
    out["tested_here"] = tested
    out["can_promote"], out["why_not"] = _promotable(out)
    return out


def _promotable(s: dict) -> tuple[bool, str]:
    if s["env"] != "tst":
        return False, "alleen op TST"
    if not s.get("github"):
        return False, "knop nog niet ingesteld (GitHub-token ontbreekt)"
    if not s.get("fix"):
        return False, "geen nieuwe oplossing om naar PRD te zetten"
    if not s.get("fix_on_tst"):
        return False, "de oplossing staat nog niet op TST"
    if not s.get("tested_here"):
        return False, "de zelftest op TST met deze versie is nog niet gebeurd of niet in orde"
    return True, ""


def ensure_selftest(hotel_id: str) -> bool:
    """Op TST: draait er een nieuwe versie met een herstelling waarvoor de zelftest nog niet gebeurde, dan de
    zelftest vragen en de robot starten (één keer per versie). Aangeroepen door de timer."""
    from hotel_checkin.admin import cloud_robot
    from hotel_checkin.processes import pms_health

    b = build()
    if env() != "tst" or not own_repair() or not b.get("built_utc"):
        return False
    if pms_health.state(hotel_id).get("checked_at", "") >= b["built_utc"]:
        return False
    if guests.get_state(hotel_id, SELFTEST_REQUEST) == str(b.get("version")):
        return False
    guests.set_state(hotel_id, SELFTEST_REQUEST, str(b.get("version")))
    try:
        cloud_robot.start()
    except Exception:
        logging.exception("robot niet gestart voor de zelftest")
    return True


def promote(hotel_id: str, user: str | None) -> tuple[bool, str]:
    """Knop op TST: de geteste versie naar PRD zetten."""
    if not allowed(hotel_id, user):
        return False, "Alleen Frederic of Seppe mogen een versie naar PRD zetten."
    s = status(hotel_id, fresh=True)
    if not s["can_promote"]:
        return False, f"Kan nu niet: {s['why_not']}."
    if s["tst"]["sha"] != s["sha"]:
        return False, "Er staat intussen een andere versie op TST. Laad de pagina opnieuw en test die eerst."
    try:
        github.run_workflow("deploy.yml", {"environment": "prd"})
    except Exception as exc:  # noqa: BLE001
        return False, f"Uitrol naar PRD niet gestart ({type(exc).__name__}). Probeer later opnieuw."
    _cache.pop(hotel_id, None)
    note = (f"{user} zette versie v{s['version']} (herstelling: {s['fix'].get('summary', '')}) naar PRD; "
            "de uitrol duurt ongeveer 5 minuten")
    guests.log_robot_run(hotel_id, TASK, datetime.now(UTC), True, 1, 1, note)
    _mail(hotel_id, f"Versie v{s['version']} wordt naar PRD gezet",
          [f"{user} heeft op TST de herstelling naar PRD gezet: {s['fix'].get('summary', '')}.",
           ("Over ongeveer 5 minuten draait PRD deze versie. Daarna doet de robot de zelftest; is die in orde, dan "
            "schrijft hij weer in Lighthouse en krijg je de mail 'Opgelost'.")])
    return True, "De uitrol naar PRD is gestart. Over ongeveer 5 minuten draait PRD deze versie."


def _mail(hotel_id: str, title: str, lines: list[str]) -> None:
    from hotel_checkin.messaging import report
    from hotel_checkin.processes import oversight

    name = load_hotel(hotel_id)["hotel"]["naam"]
    oversight._send(hotel_id, f"{name}: {title}", report.overview_html(title, lines, [], oversight._monitor_url()))
