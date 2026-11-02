"""Proces: bewaking. Een dagelijks overzicht van de aankomsten en waarschuwingen als iets misloopt.

Kijkt naar het resultaat (heeft elke gast wat hij nodig heeft?), niet alleen of de programma's draaiden.
Zo valt ook een fout op die niemand voorzag (Lighthouse-scherm veranderd, rechten op de mailbox verlopen,
Salto onbereikbaar, ...).

- Overzicht om [bewaking] overzicht_uur (07:30): aankomsten van vandaag en morgen, per kamer: contact, kamer
  betaald, code, code-mail verstuurd, code in Lighthouse. Problemen bovenaan in het rood.
- Controle om [bewaking] controle_uren (17:00, 20:00): zijn er problemen bij de aankomsten van vandaag en
  morgen, dan meteen een waarschuwing (alleen als er iets nieuws is).
- Robot: lukte de taak "nieuwe reservaties" al [bewaking] robot_max_uren niet meer, dan een waarschuwing
  (hoogstens eens per 3 uur).
Naar [bewaking] email. Buiten PRD naar het testadres (core/safety.py). Draait in de Function App (timer),
los van de robot: een robot die stilvalt, kan zichzelf niet melden.
"""

from __future__ import annotations

import json
import logging
import os
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
            "robot_alert": str(cfg.get("robot_waarschuwing", False)).lower() in ("true", "1", "ja")}


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
                   for s in workflow._steps_from(workflow.config(hotel_id), workflow.flow_for(hotel_id, r)))
    paid = workflow.room_paid(r)
    has_code = bool(r.access_codes)
    in_pms = bool(r.access_codes) and r.pms_codes_line == pms_sync.wanted_line(r)
    problems = []
    if not (r.guest.email or r.guest.phone):
        problems.append("geen e-mailadres of gsm-nummer")
    if code_active and code_due:
        if not paid:
            problems.append("kamer nog niet betaald: geen code")
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
            "problemen": problems, "_day": day.isoformat()}


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


def robot_problem(hotel_id: str, max_hours: float) -> str | None:
    from hotel_checkin.processes import new_reservation

    runs = guests.robot_runs(hotel_id, limit=20, task=new_reservation.TASK)
    ok = [r for r in runs if r.get("ok")]
    if not ok:
        return "de robot heeft nog geen geslaagde run" if runs else None
    last = datetime.fromisoformat(ok[0]["started_at"])
    if datetime.now(UTC) - last > timedelta(hours=max_hours):
        err = next((r.get("error") for r in runs if not r.get("ok")), "")
        return f"de robot lukte niet meer sinds {last.astimezone(clock.tz(hotel_id)):%d/%m %H:%M}" + (f" ({err[:150]})" if err else "")
    return None


def _monitor_url() -> str:
    host = os.environ.get("MONITOR_HOST") or os.environ.get("WEBSITE_HOSTNAME") or ""
    return f"https://{host}/monitor/" if host else "/monitor/"


def _send(hotel_id: str, subject: str, html_body: str) -> bool:
    cfg = settings(hotel_id)
    sender = load_hotel(hotel_id).get("verzending", {}).get("mail_afzender")
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
               "oude_boekingen": "Oudere boekingen", "betaalverzoeken": "Betaalverzoeken", "berichten": "Berichten", "meldingen": "Meldingen per mail"}


def activity(hotel_id: str, hours: int = 24) -> list[str]:
    """Wat er de voorbije 24 uur gebeurde, in een paar regels: wat gedaan werd en wat misliep."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    runs = [r for r in guests.robot_runs(hotel_id, limit=500) if datetime.fromisoformat(r["started_at"]) >= since]
    if not runs:
        return [f"De voorbije {hours} uur deed de robot niets (geen runs)."]
    robot_runs = len({r.get("execution") for r in runs if r.get("execution")})
    done = {}
    problems = []
    for r in runs:
        task = r.get("task")
        if task in _TASK_NAMES and int(r.get("new") or 0):
            done[task] = done.get(task, 0) + int(r["new"])
        if not r.get("ok") or int(r.get("skipped") or 0):
            problems.append(f"{_TASK_NAMES.get(task, task)}: {(r.get('error') or '')[:200]}")
    words = {"overschrijving_booking": "overschrijving(en) geregistreerd", "ontbijt_labels": "ontbijtlabel(s) gezet",
             "lighthouse_bijwerken": "reservatie(s) bijgewerkt in Lighthouse", "nieuwe_reservaties": "nieuwe reservatie(s)",
             "oude_boekingen": "oudere boeking(en) binnengehaald", "betaalverzoeken": "betaalverzoek(en) gemaakt", "berichten": "bericht(en) verstuurd",
             "meldingen": "betaallink(s) bewaard"}
    out = [f"De voorbije {hours} uur: {robot_runs} robotrun(s)"
           + (", " + ", ".join(f"{n} {words[t]}" for t, n in done.items()) if done else ", niets geregistreerd of gezet")
           + "."]
    if problems:
        out.append(f"Wat misliep ({len(problems)}): " + " | ".join(problems[:8]) + ". Details in de monitor (Robot).")
    return out


def send_overview(hotel_id: str, today: date) -> bool:
    a = arrivals(hotel_id, today)
    problems = sum(1 for rows in a.values() for x in rows if x["problemen"])
    name = load_hotel(hotel_id)["hotel"]["naam"]
    intro = [f"{len(a['today'])} aankomsten vandaag, {len(a['tomorrow'])} morgen."
             + (f" {problems} met een probleem (rood)." if problems else " Alles in orde.")]
    rp = robot_problem(hotel_id, settings(hotel_id)["robot_hours"])
    if rp:
        intro.append(f"Let op: {rp}.")
    intro += activity(hotel_id)
    body = report.overview_html(f"{name}: aankomsten {today:%d/%m}", intro,
                                [(f"Vandaag {today:%d/%m}", a["today"]), (f"Morgen {today + timedelta(days=1):%d/%m}", a["tomorrow"])],
                                _monitor_url())
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
    rp = robot_problem(hotel_id, cfg["robot_hours"]) if cfg["robot_alert"] else None
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
    _save_state(hotel_id, st)
    if done:
        guests.log_robot_run(hotel_id, TASK, datetime.now(UTC), True, 0, 0, "; ".join(done))
    return done
