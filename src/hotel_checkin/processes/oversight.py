"""Proces: bewaking. Een dagelijks overzicht van de aankomsten en waarschuwingen als iets misloopt.

Kijkt naar het resultaat (heeft elke gast wat hij nodig heeft?), niet alleen of de programma's draaiden.
Zo valt ook een fout op die niemand voorzag (Lighthouse-scherm veranderd, rechten op de mailbox verlopen,
Salto onbereikbaar, ...).

- Overzicht om [bewaking] overzicht_uur (07:30): aankomsten van vandaag en morgen, per kamer: contact, kamer
  betaald, code, code-mail verstuurd, code in Lighthouse. Problemen bovenaan in het rood.
- Controle om [bewaking] controle_uren (17:00, 20:00): zijn er problemen bij de aankomsten van vandaag en
  morgen, dan meteen een waarschuwing (alleen als er iets nieuws is).
- Robot: mist de robot een gepland uur van het vangnet, dan een waarschuwing ([bewaking] monitoring)
  (hoogstens eens per 3 uur).
Naar [bewaking] email. Buiten PRD naar het testadres (core/safety.py). Draait in de Function App (timer),
los van de robot: een robot die stilvalt, kan zichzelf niet melden.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, date, datetime, timedelta

from hotel_checkin.core import clock, safety, workflow
from hotel_checkin.core.hotels import load_hotel
from hotel_checkin.core.models import Reservation, ReservationStatus
from hotel_checkin.guests import repository as guests
from hotel_checkin.messaging import email, report

TASK = "bewaking"
STATE = "oversight"  # RobotState: wat vandaag al gedaan is


def settings(hotel_id: str) -> dict:
    cfg = load_hotel(hotel_id).get("bewaking", {})
    to = cfg.get("email") or []
    return {"email": [to] if isinstance(to, str) else list(to), "overview": cfg.get("overzicht_uur", "07:30"),
            "checks": list(cfg.get("controle_uren", [])), "robot_hours": float(cfg.get("robot_max_uren", 3)),
            # Eén schakelaar voor alle waarschuwingen en de herstelrobot ([bewaking] monitoring, standaard aan)
            "monitoring": str(cfg.get("monitoring", True)).lower() in ("true", "1", "ja")}


def _state(hotel_id: str) -> dict:
    try:
        return json.loads(guests.get_state(hotel_id, STATE) or "{}")
    except ValueError:
        return {}


def _save_state(hotel_id: str, st: dict) -> None:
    guests.set_state(hotel_id, STATE, json.dumps(st))


def row(hotel_id: str, r: Reservation, day: date, today: date, code_active: bool, messaging_on: bool,
        salto_live: bool = True) -> dict:
    """Eén aankomst met wat ze nodig heeft, en wat ontbreekt (problemen)."""
    from hotel_checkin.processes import pms_sync

    msgs = guests.messages_for(hotel_id, r.reservation_id)
    code_mail = any(m["message_type"] == "access_code" and m["ok"] and m["channel"] != "salto" for m in msgs)
    code_due = any(s.step == "access_code" and s.enabled and workflow.is_due(s, r, today)
                   for s in workflow.steps_for(hotel_id, r))
    paid = workflow.room_paid(r)
    has_code = bool(r.access_codes)
    in_pms = bool(r.access_codes) and r.pms_codes_line == pms_sync.wanted_line(r)
    problems = []  # echt mis: iemand moet iets doen (rood)
    info = []  # gewoon goed om te weten, geen fout (grijs)
    if not (r.guest.email or r.guest.phone):
        problems.append("geen e-mailadres of gsm-nummer")
    if code_active and code_due:
        if not paid:
            info.append("betaalt nog: de code volgt na betaling (of aan de receptie)")
        elif salto_live and not has_code:
            problems.append("nog geen pincode bij Salto")
        elif messaging_on and not code_mail:
            problems.append("code-mail niet verstuurd")
        if has_code and safety.is_production() and not in_pms:
            problems.append("code staat nog niet in Lighthouse")
    if not r.rooms:
        problems.append("nog geen kamer toegewezen")
    failed = [m for m in msgs if not m["ok"] and m["message_type"] in ("access_code", "pms_sync", "booking_payout")
              and not any(x["ok"] and x["message_type"] == m["message_type"] for x in msgs if x["RowKey"] > m["RowKey"])]
    if failed:
        problems.append("fout: " + (failed[-1].get("error") or failed[-1].get("note") or "")[:120])
    return {"nummer": r.booking_number or r.reservation_id[:8], "kamer": ", ".join(r.rooms) or "?",
            "gast": f"{r.guest.first_name} {r.guest.last_name}".strip(), "via": r.source or "",
            "contact": "ja" if (r.guest.email or r.guest.phone) else "nee",
            "betaald": paid, "code": has_code if (code_active and salto_live) else "-",
            "code_mail": code_mail if (code_active and messaging_on) else "-", "lighthouse": in_pms if has_code else "-",
            "problemen": problems, "info": info, "_day": day.isoformat()}


def arrivals(hotel_id: str, today: date) -> dict[str, list[dict]]:
    from hotel_checkin.processes import send_messages

    code_active = "access_code" in send_messages.ready_steps(hotel_id) and (
        send_messages.salto_ready(hotel_id) or send_messages.test_mode(hotel_id))
    on = send_messages.enabled(hotel_id)
    salto_live = send_messages.salto_ready(hotel_id)  # zonder Salto (TST): code-mail met XXXXXX, geen echte code
    out = {"today": [], "tomorrow": []}
    for r in guests.list_reservations(hotel_id):
        if r.status == ReservationStatus.CANCELLED:
            continue
        for key, day in (("today", today), ("tomorrow", today + timedelta(days=1))):
            if r.arrival == day:
                out[key].append(row(hotel_id, r, day, today, code_active, on, salto_live))
    return out


GRACE_MINUTES = 30  # zoveel na een vast uur van het vangnet moet de run van dat uur gelukt zijn


def robot_problem(hotel_id: str, max_hours: float, now: datetime | None = None) -> str | None:
    """Alarm alleen als de robot een gepland uur van het vangnet gemist heeft: het uur is meer dan GRACE_MINUTES
    voorbij en er is sinds dat uur geen geslaagde run (ook niet door een melding van Lighthouse). Zo geeft een
    omgeving die maar om de 4 uur draait (TST) geen alarm tussen twee runs. Een bevroren omgeving (robot niet
    nodig) geeft nooit alarm. Zonder vangnet (0 minuten): alarm na max_hours zonder geslaagde run."""
    from hotel_checkin.processes import new_reservation, robot_schedule
    from hotel_checkin.processes.send_messages import robot_needed

    if not robot_needed(hotel_id):
        return None
    runs = guests.robot_runs(hotel_id, limit=20, task=new_reservation.TASK)
    ok = [r for r in runs if r.get("ok")]
    if not ok:
        return "de robot heeft nog geen geslaagde run" if runs else None
    last = datetime.fromisoformat(ok[0]["started_at"])
    now = (now or datetime.now(UTC)).astimezone(clock.tz(hotel_id))
    every = robot_schedule.minutes(hotel_id)
    if every > 0:
        slot = robot_schedule._slot_start(every, now)
        if now - slot < timedelta(minutes=GRACE_MINUTES):
            slot -= timedelta(minutes=max(int(every), 5))  # de run van dit uur mag nog bezig zijn: het vorige uur
        missed = last < slot
        what = f"geen geslaagde run voor het geplande uur van {slot:%H:%M}"
    else:
        missed = now - last > timedelta(hours=max_hours)
        what = f"geen geslaagde run in {max_hours:g} uur"
    if not missed:
        return None
    err = next((r.get("error") for r in runs if not r.get("ok")), "")
    return (f"de robot lukte niet meer sinds {last.astimezone(clock.tz(hotel_id)):%d/%m %H:%M} ({what})"
            + (f": {err[:150]}" if err else ""))


def health_warning(hotel_id: str) -> str | None:
    """Rode waarschuwing als de zelftest van Lighthouse een probleem vond (processes/pms_health.py), in gewone woorden."""
    from hotel_checkin.processes import pms_health

    st = pms_health.state(hotel_id)
    if st.get("ok") is not False:
        return None
    since = datetime.fromisoformat(st.get("since") or st["checked_at"]).astimezone(clock.tz(hotel_id))
    return (f"LIGHTHOUSE IS VERANDERD (sinds {since:%d/%m %H:%M}). De robot vindt niet meer alles terug in Lighthouse. "
            "Daarom zet hij tijdelijk niets meer in Lighthouse: geen pincode in de opmerking, geen kamerstatus, geen "
            "labels, geen overschrijvingen, geen betaalverzoeken. Hij leest wel nog alles, en pincodes die al "
            "verstuurd zijn, blijven werken.")


def repair_steps(hotel_id: str) -> list[str]:
    """Wat er met de herstelling gebeurt en wat te doen, voor iemand zonder IT-kennis (onder de rode waarschuwing)."""
    from hotel_checkin.processes import pms_health, repair

    health = pms_health.state(hotel_id)
    if health.get("ok") is not False:
        return []
    s = repair.status(hotel_id)
    manual = ("Tot het opgelost is: wat de robot anders in Lighthouse zet, doe je zelf (pincode in de opmerking, kamer "
              "op KLAAR OM IN TE CHECKEN, label ONTBIJT). De pincodes staan in de monitor.")
    if s.get("fix") and s.get("fix_on_tst"):
        return [f"Er staat een oplossing klaar om te testen: {s['fix'].get('summary', '')}",
                "Wat te doen (alleen Frederic of Seppe):",
                f"1. Open de testomgeving: {repair.tst_url()} (bovenaan staat wat er nieuw is).",
                "2. Kijk of de reservaties van vandaag en morgen kloppen (kamers, data) en maak een schoonmaaklijst.",
                ("3. Klopt alles en staat er 'zelftest in orde', klik dan bovenaan op 'Deze versie naar PRD zetten'. "
                 "Na ongeveer 5 minuten werkt de robot weer gewoon en krijg je de mail 'Opgelost'."),
                "Twijfel je? Niets doen en Frederic verwittigen.",
                manual]
    if not s.get("github") or "niet" in str(health.get("repair", "")):
        return ["De herstelrobot kon niet starten. Frederic moet dit bekijken.", manual]
    return [("De herstelrobot zoekt een oplossing. Je krijgt een mail zodra ze klaar is om te testen. Je hoeft nu "
             "niets te doen."), manual]


def monitor_banner(hotel_id: str, s: dict) -> dict | None:
    """Balk bovenaan de monitor: wat er aan de hand is en wat te doen (s = repair.status).
    {"level": "red"|"blue", "lines": [...], "promote": bool} of None."""
    warn = health_warning(hotel_id)
    own = (s.get("repair") or {}).get("id")
    fix = s.get("fix") or {}
    if s.get("env") == "tst" and own and own == fix.get("id"):
        health = s.get("health") or {}
        if s.get("tested_here"):
            test = "Zelftest op TST met deze versie: in orde."
        elif health.get("ok") is False:
            test = ("Zelftest op TST met deze versie: NIET in orde ("
                    + "; ".join(f"{f['part']}: {f['why']}" for f in health.get("failures", [])) + "). Niet naar PRD zetten.")
        else:
            test = "Zelftest op TST met deze versie: nog bezig. Vernieuw deze pagina binnen enkele minuten."
        prd = (s.get("prd") or {}).get("version")
        return {"level": "blue", "promote": True, "lines": [
            f"TESTVERSIE v{s.get('version')} met een oplossing voor een wijziging in Lighthouse"
            + (f". PRD draait nog v{prd}." if prd else "."),
            f"Wat is er anders: {fix.get('summary', '')}",
            test,
            "Testen: kijk of de reservaties van vandaag en morgen kloppen (kamers, data) en maak een schoonmaaklijst.",
            ("Klopt alles, klik dan op 'Deze versie naar PRD zetten' (alleen Frederic of Seppe). Twijfel je: niets "
             "doen en Frederic verwittigen.")]}
    if warn:
        return {"level": "red", "promote": False, "lines": [warn, *repair_steps(hotel_id)]}
    return None


def _monitor_url() -> str:
    host = os.environ.get("MONITOR_HOST") or os.environ.get("WEBSITE_HOSTNAME") or ""
    return f"https://{host}/monitor/" if host else "/monitor/"


def _send(hotel_id: str, subject: str, html_body: str) -> bool:
    cfg = settings(hotel_id)
    sender = load_hotel(hotel_id).get("verzending", {}).get("mail_afzender")
    if not safety.is_production():  # testomgeving: meteen zichtbaar, niet te verwarren met de echte mail
        subject = f"[TEST] {subject}"
        html_body = ('<p style="font-family:Arial,sans-serif;font-size:13px;color:#8A90A0;">Testomgeving (TST): '
                     'de echte toestand staat in de mail van productie.</p>' + html_body)
    ok = True
    for to in cfg["email"]:
        res = email.send_email(to=to, subject=subject, html_body=html_body, sender=sender, hotel_id=hotel_id)
        ok = ok and res.ok
        if not res.ok:
            logging.error("%s: bewakingsmail naar %s mislukt: %s", hotel_id, to, res.error)
    return ok


# Taken uit het robotlog die in het overzicht komen, met hun naam voor de lezer
_TASK_NAMES = {"overschrijving_booking": "Overschrijvingen", "ontbijt_labels": "Ontbijt labels",
               "lighthouse_bijwerken": "Pincode en status in Lighthouse", "nieuwe_reservaties": "Nieuwe reservaties",
               "oude_boekingen": "Oudere boekingen", "betaalverzoeken": "Betaalverzoeken", "berichten": "Berichten", "meldingen": "Mailbox nakijken",
               "ontbijtlijst": "Ontbijtlijst", "kuislijst": "Schoonmaaklijst"}


_PER_RESERVATION = re.compile(r"\b([A-Z]{2,5}-\d+-\d+): ([^;|]+?)(?=;|\||\.\s+(?:[A-Z]|\d+ [a-z]{4,})|\.?$| En nog)")


def robot_failures(hotel_id: str, hours: int = 24) -> list[str]:
    """Wat NU nog misloopt, voor onder de tabellen. Alleen de laatste run van elke taak telt: was een probleem
    tijdelijk (de volgende run lukte, bv. een storing bij Microsoft), dan staat het er niet meer. Per reservatie één
    regel met de reden en het tijdstip; bij een taak alleen de fout zelf (niet de hele notitie)."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    runs = sorted((r for r in guests.robot_runs(hotel_id, limit=500)
                   if datetime.fromisoformat(r["started_at"]) >= since), key=lambda x: x["started_at"])
    latest: dict[str, dict] = {}
    count: dict[str, int] = {}  # in hoeveel runs dezelfde reservatie misliep
    for r in runs:
        latest[r.get("task")] = r
        for number, _ in _PER_RESERVATION.findall(_failed_part(r.get("error") or "")):
            count[number] = count.get(number, 0) + 1
    tz = clock.tz(hotel_id)
    out = []
    for task, r in latest.items():
        if r.get("ok") and not int(r.get("skipped") or 0):
            continue  # laatste run in orde: wat eerder misliep, is opgelost
        name = _TASK_NAMES.get(task, task)
        at = datetime.fromisoformat(r["started_at"]).astimezone(tz)
        text = (r.get("error") or "").strip()
        found = _PER_RESERVATION.findall(_failed_part(text))
        for number, why in found:
            n = count.get(number, 1)
            out.append(f"{number} ({name}): {why.strip()}, laatste keer {at:%d/%m %H:%M}"
                       + (f" ({n} runs)" if n > 1 else ""))
        if not found:
            n = sum(1 for x in runs if x.get("task") == task and not (x.get("ok") and not int(x.get("skipped") or 0)))
            out.append(f"{name}: {_failed_part(text) or text}"[:220] + f", laatste keer {at:%d/%m %H:%M}"
                       + (f" ({n} keer)" if n > 1 else ""))
    return out


def _failed_part(text: str) -> str:
    """Alleen wat niet lukte uit een notitie ("niet gelezen: ...", "fout: ...", "overgeslagen: ..."), niet wat de
    robot gewoon deed of opmerkte. Niet knippen in een datum ("07 nov. 2026")."""
    parts = re.split(r"\.\s+(?=[A-Z]|\d+ [a-z]{4,})", text)
    keep = [x for x in parts if re.search(r"niet gelezen:|overgeslagen:|\bfout:", x)]
    return " ".join(keep)


def failure_advice(lines: list[str]) -> str:
    """Wat de manager met de lijst onderaan moet doen, in gewone woorden."""
    if not lines:
        return ""
    return ("Wat te doen: meestal niets, de robot probeert het elk uur opnieuw. Staat dezelfde reservatie er morgen nog, "
            "kijk ze dan zelf na in Lighthouse (kamer, data, betaling) en verwittig Frederic.")


def activity(hotel_id: str, hours: int = 24) -> list[str]:
    """Wat er de voorbije 24 uur gebeurde, in een paar regels: wat gedaan werd en wat misliep (kort; de details
    staan onder de tabellen, zie robot_failures)."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    runs = [r for r in guests.robot_runs(hotel_id, limit=500) if datetime.fromisoformat(r["started_at"]) >= since]
    if not runs:
        return [f"De voorbije {hours} uur deed de robot niets (geen runs)."]
    robot_runs = len({r.get("execution") for r in runs if r.get("execution")})
    done = {}
    problems: dict[str, int] = {}  # zelfde melding maar één keer, met het aantal keer
    for r in runs:
        task = r.get("task")
        if task in _TASK_NAMES and int(r.get("new") or 0):
            done[task] = done.get(task, 0) + int(r["new"])
        if not r.get("ok") or int(r.get("skipped") or 0):
            text = f"{_TASK_NAMES.get(task, task)}: {(r.get('error') or '').strip()[:200]}"
            problems[text] = problems.get(text, 0) + 1
    words = {"overschrijving_booking": "overschrijving(en) geregistreerd", "ontbijt_labels": "ontbijtlabel(s) gezet",
             "lighthouse_bijwerken": "reservatie(s) bijgewerkt in Lighthouse", "nieuwe_reservaties": "nieuwe reservatie(s)",
             "oude_boekingen": "oudere boeking(en) binnengehaald", "betaalverzoeken": "betaalverzoek(en) gemaakt", "berichten": "bericht(en) verstuurd",
             "meldingen": "betaallink(s) bewaard", "ontbijtlijst": "ontbijtlijst(en) verstuurd",
             "kuislijst": "schoonmaaklijst(en) verstuurd"}
    out = [f"De voorbije {hours} uur: {robot_runs} robotrun(s)"
           + (", " + ", ".join(f"{n} {words[t]}" for t, n in done.items()) if done else ", niets geregistreerd of gezet")
           + "."]
    if robot_failures(hotel_id, hours):  # wat vanzelf weer in orde kwam, is voor niemand nuttig: niet vermelden
        out.append("Er loopt nog iets mis: zie onderaan.")
    return out


def send_overview(hotel_id: str, today: date) -> bool:
    a = arrivals(hotel_id, today)
    problems = sum(1 for rows in a.values() for x in rows if x["problemen"])
    name = load_hotel(hotel_id)["hotel"]["naam"]
    unpaid = sum(1 for rows in a.values() for x in rows if x["info"] and not x["problemen"])
    intro = [f"{len(a['today'])} aankomst(en) vandaag, {len(a['tomorrow'])} morgen."
             + (f" {problems} met een probleem (rood): nakijken." if problems else " Geen problemen.")
             + (f" {unpaid} betaalt nog (code volgt na betaling), dat is normaal." if unpaid else "")]
    from hotel_checkin.processes.send_messages import switch

    rp = robot_problem(hotel_id, settings(hotel_id)["robot_hours"]) if switch(hotel_id, "reservaties") else None
    if rp:
        intro.append(f"Let op: {rp}.")
    intro += activity(hotel_id)
    failures = robot_failures(hotel_id)
    banners = [("red", text) for text in [health_warning(hotel_id)] if text]
    banners += [("orange", line) for line in repair_steps(hotel_id)]
    unread = [x for x in failures if "niet gelezen" in x or "Error" in x or "niet volledig geladen" in x]
    if failures and not any(level == "red" for level, _ in banners):
        banners.append(("orange", f"Opgelet: de robot heeft nu {len(failures)} probleem/problemen"
                                  + (f" ({len(unread)} reservatie(s) nog niet gelezen)" if unread else "")
                                  + ". Zie onderaan wat, bij welke reservatie en wat te doen."))
    body = report.overview_html(f"{name}: aankomsten {today:%d/%m}", intro,
                                [(f"Vandaag {today:%d/%m}", a["today"]), (f"Morgen {today + timedelta(days=1):%d/%m}", a["tomorrow"])],
                                _monitor_url(), problems=failures, banners=banners,
                                advice=failure_advice(failures))
    subject = f"{name}: aankomsten {today:%d/%m}" + (f" ({problems} probleem)" if problems == 1 else f" ({problems} problemen)" if problems else "")
    return _send(hotel_id, subject, body)


def check(hotel_id: str, today: date, st: dict) -> int:
    """Waarschuwing als er bij de aankomsten van vandaag en morgen iets ontbreekt dat nog niet gemeld werd."""
    a = arrivals(hotel_id, today)
    bad = [x for rows in a.values() for x in rows if x["problemen"]]
    signature = sorted(f"{x['nummer']}:{'|'.join(x['problemen'])}" for x in bad)
    reported = set(st.get("reported", {}).get(today.isoformat(), []))
    if not bad or set(signature) <= reported:
        return 0
    name = load_hotel(hotel_id)["hotel"]["naam"]
    body = report.overview_html(f"Let op: {len(bad)} aankomst(en) zonder alles wat nodig is",
                                ["Dit moet nagekeken worden, anders staat de gast misschien zonder code aan de deur."],
                                [(f"Vandaag {today:%d/%m}", [x for x in a["today"] if x["problemen"]]),
                                 (f"Morgen {today + timedelta(days=1):%d/%m}", [x for x in a["tomorrow"] if x["problemen"]])],
                                _monitor_url())
    if _send(hotel_id, f"WAARSCHUWING {name}: {len(bad)} aankomst(en) niet in orde", body):
        st.setdefault("reported", {})[today.isoformat()] = sorted(reported | set(signature))
    return len(bad)


def _due(now_hm: str, at: str, done: bool) -> bool:
    return not done and now_hm >= at


def run(hotel_id: str, now: datetime | None = None) -> list[str]:
    """Aangeroepen door de timer (elke 15 minuten). Geeft terug wat er verstuurd werd."""
    cfg = settings(hotel_id)
    if not cfg["email"]:
        return []
    now = now or datetime.now(clock.tz(hotel_id))
    today, hm = now.date(), now.strftime("%H:%M")
    st = _state(hotel_id)
    st["reported"] = {k: v for k, v in st.get("reported", {}).items() if k >= (today - timedelta(days=2)).isoformat()}
    done: list[str] = []
    day = st.setdefault("days", {}).setdefault(today.isoformat(), {})
    st["days"] = {k: v for k, v in st["days"].items() if k >= (today - timedelta(days=2)).isoformat()}
    if _due(hm, cfg["overview"], day.get("overview")) and send_overview(hotel_id, today):
        day["overview"] = True
        done.append(f"mail verstuurd naar {', '.join(cfg['email'])}: dagelijks overzicht van vandaag en morgen")
    for at in cfg["checks"]:
        if _due(hm, at, day.get(f"check_{at}")):
            n = check(hotel_id, today, st)
            day[f"check_{at}"] = True
            done.append(f"controle van {at}: " + (f"{n} aankomst(en) met een probleem, mail verstuurd naar {', '.join(cfg['email'])}"
                                                  if n else "alle aankomsten in orde, geen mail nodig"))
    from hotel_checkin.processes.send_messages import switch

    rp = robot_problem(hotel_id, cfg["robot_hours"]) if cfg["monitoring"] and switch(hotel_id, "reservaties") else None
    last = st.get("robot_alert_at")
    if rp and (not last or datetime.fromisoformat(last) < datetime.now(UTC) - timedelta(hours=3)):
        name = load_hotel(hotel_id)["hotel"]["naam"]
        if _send(hotel_id, f"WAARSCHUWING {name}: robot Lighthouse werkt niet",
                 report.overview_html("De robot voor Lighthouse werkt niet", [
                     rp[0].upper() + rp[1:] + ".",
                     ("Nieuwe reservaties en wijzigingen komen dan niet binnen. Nakijken in de monitor "
                      "(instellingen, Robot) of de robot opnieuw starten.")], [], _monitor_url())):
            st["robot_alert_at"] = datetime.now(UTC).isoformat()
            done.append(f"mail verstuurd naar {', '.join(cfg['email'])}: waarschuwing, {rp}")
    # Zelftest van Lighthouse: meteen een waarschuwing (één keer per probleem), en een mail als het opgelost is
    from hotel_checkin.processes import pms_health

    health = pms_health.state(hotel_id)
    warn = health_warning(hotel_id) if cfg["monitoring"] else None  # monitoring uit: alleen in het dagelijkse overzicht
    name = load_hotel(hotel_id)["hotel"]["naam"]
    if warn and st.get("health_alerted") != health.get("since") and _send(
            hotel_id, f"WAARSCHUWING {name}: Lighthouse is veranderd, de robot schrijft niets meer",
            report.overview_html("Lighthouse is veranderd", repair_steps(hotel_id), [], _monitor_url(),
                                 banners=[("red", warn)])):
        st["health_alerted"] = health.get("since")
        done.append(f"mail verstuurd naar {', '.join(cfg['email'])}: waarschuwing, Lighthouse veranderd")
    if warn:  # oplossing klaar om te testen op TST: meteen laten weten (één keer per oplossing)
        from hotel_checkin.processes import repair

        rs = repair.status(hotel_id)
        fix_id = (rs.get("fix") or {}).get("id")
        if rs.get("fix_on_tst") and fix_id and st.get("fix_announced") != fix_id and _send(
                hotel_id, f"{name}: oplossing klaar om te testen", report.overview_html(
                    "Oplossing klaar om te testen", repair_steps(hotel_id), [], _monitor_url(),
                    banners=[("red", warn)])):
            st["fix_announced"] = fix_id
            done.append(f"mail verstuurd naar {', '.join(cfg['email'])}: oplossing klaar om te testen op TST")
    elif cfg["monitoring"] and health.get("ok") and st.get("health_alerted") and _send(
            hotel_id, f"Opgelost {name}: de robot werkt weer volledig in Lighthouse",
            report.overview_html("Lighthouse: opgelost", [
                "De zelftest vindt weer alles wat de robot nodig heeft. De robot schrijft weer in Lighthouse."],
                [], _monitor_url())):
        st.pop("health_alerted", None)
        done.append(f"mail verstuurd naar {', '.join(cfg['email'])}: Lighthouse weer in orde")
    _save_state(hotel_id, st)
    if done:
        guests.log_robot_run(hotel_id, TASK, datetime.now(UTC), True, 0, 0, "; ".join(done))
    return done
