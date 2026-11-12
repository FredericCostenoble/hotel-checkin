"""Proces: de robot als vangnet op vaste tijden starten, vanuit de Function App.

De robot (Container Apps Job) start nooit meer op een eigen schema in Azure: een container starten om niets te doen
kost geld. De Function App kijkt elke minuut (timer van de meldingen) en start de robot alleen als:
- de robot iets te doen heeft (niet alle hoofdschakelaars uit, send_messages.robot_needed), en
- het een vast uur is (om de [robot] check_minutes vanaf middernacht, bv. 60 = elk heel uur; instelling in de monitor,
  per omgeving; 0 = nooit op schema, alleen bij een meldingsmail, een gevraagde lijst of de knop "Robot nu draaien"),
  en er sinds dat uur nog geen run was.
's Nachts ([robot] nacht_van tot nacht_tot, bv. 23:00 tot 06:00) gebeurt er met nieuwe reservaties toch niets: dan
start de robot alleen op de nachtelijke uren ([robot] nacht_uren, hoogstens MAX_NIGHT_RUNS), niet op de gewone
vaste uren, en ook niet door een meldingsmail (die wacht tot het einde van de nacht, mail_trigger).
Een bevroren omgeving (alle hoofdschakelaars uit) start dus geen enkele container.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from hotel_checkin.core.config import hotel_setting
from hotel_checkin.guests import repository as guests

STATE = "robot_schedule_started"  # RobotState: wanneer deze timer de robot voor het laatst startte (of probeerde)
RETRY_MINUTES = 10  # mislukt starten: zo lang wachten voor een nieuwe poging
MAX_NIGHT_RUNS = 3  # meer runs per nacht heeft geen zin (kost)


def minutes(hotel_id: str) -> float:
    return float(hotel_setting(hotel_id, "ROBOT_CHECK_MINUTES", default="60", shared=False) or 0)


def _times(raw) -> list[tuple[int, int]]:
    """Uren uit een instelling ("01:00, 04:00" of een lijst), als (uur, minuut)."""
    import re

    out = []
    for h, m in re.findall(r"(\d{1,2}):(\d{2})", str(raw or "")):
        if int(h) < 24 and int(m) < 60:
            out.append((int(h), int(m)))
    return out


def night_window(hotel_id: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """Begin en einde van de nacht ([robot] nacht_van, nacht_tot), of None als er geen nacht ingesteld is."""
    start = _times(hotel_setting(hotel_id, "ROBOT_NACHT_VAN", default="", shared=False))
    end = _times(hotel_setting(hotel_id, "ROBOT_NACHT_TOT", default="", shared=False))
    if not start or not end or start[0] == end[0]:
        return None
    return start[0], end[0]


def night_times(hotel_id: str) -> list[tuple[int, int]]:
    """De nachtelijke uren van het vangnet ([robot] nacht_uren), hoogstens MAX_NIGHT_RUNS, alleen binnen de nacht."""
    window = night_window(hotel_id)
    if window is None:
        return []
    times = sorted(set(_times(hotel_setting(hotel_id, "ROBOT_NACHT_UREN", default="", shared=False))))
    return [t for t in times if _in_window(t, window)][:MAX_NIGHT_RUNS]


def _in_window(t: tuple[int, int], window: tuple[tuple[int, int], tuple[int, int]]) -> bool:
    start, end = window
    return (start <= t or t < end) if start > end else start <= t < end


def is_night(hotel_id: str, now: datetime | None = None) -> bool:
    """Is het nu nacht voor dit hotel (lokale tijd)?"""
    from hotel_checkin.core import clock

    window = night_window(hotel_id)
    if window is None:
        return False
    now = (now or datetime.now(UTC)).astimezone(clock.tz(hotel_id))
    return _in_window((now.hour, now.minute), window)


def _night_slot_start(hotel_id: str, now: datetime) -> datetime | None:
    """Het laatste nachtelijke uur dat al voorbij is in deze nacht (now in lokale tijd), of None."""
    window = night_window(hotel_id)
    (sh, sm), _ = window
    begin = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    if begin > now:
        begin -= timedelta(days=1)  # de nacht begon gisteren
    found = None
    for h, m in night_times(hotel_id):
        for day in (0, 1):
            t = (begin + timedelta(days=day)).replace(hour=h, minute=m)
            if begin <= t <= now and (found is None or t > found):
                found = t
    return found


def _last_run(hotel_id: str) -> datetime | None:
    """Begin van de laatste run die nieuwe reservaties las (ook gestart door een meldingsmail of de knop)."""
    from hotel_checkin.processes import new_reservation

    runs = guests.robot_runs(hotel_id, limit=1, task=new_reservation.TASK)
    return datetime.fromisoformat(runs[0]["started_at"]) if runs else None


def slots(every: float) -> list[str]:
    """Vaste uren van het vangnet ("HH:MM"), elke dag vanaf middernacht om de `every` minuten, bv. om de 60 minuten:
    00:00, 01:00, ... De ontbijt- en schoonmaaklijst kiezen een van deze uren: dan is hun robotrun meteen de run van
    het vangnet, zonder extra run."""
    if every <= 0:
        return []
    step = max(int(every), 5)
    return [f"{m // 60:02d}:{m % 60:02d}" for m in range(0, 24 * 60, step)]


def _slot_start(every: float, now: datetime) -> datetime:
    step = max(int(every), 5)
    minute = now.hour * 60 + now.minute
    start = minute - minute % step
    return now.replace(hour=start // 60, minute=start % 60, second=0, microsecond=0)


def due(hotel_id: str, now: datetime | None = None) -> bool:
    """Op de vaste uren (slots): de robot starten als er sinds het begin van dit uur nog geen run was (ook niet door
    een meldingsmail of een gevraagde lijst) en hij nog niet gestart werd."""
    from hotel_checkin.core import clock
    from hotel_checkin.processes.send_messages import robot_needed

    every = minutes(hotel_id)
    if every <= 0 or not robot_needed(hotel_id):
        return False
    now = (now or datetime.now(UTC)).astimezone(clock.tz(hotel_id))
    if is_night(hotel_id, now):
        start = _night_slot_start(hotel_id, now)
        if start is None:
            return False  # nog geen nachtelijk uur voorbij
    else:
        start = _slot_start(every, now)
    last = _last_run(hotel_id)
    tried = guests.get_state(hotel_id, STATE)
    if tried and datetime.fromisoformat(tried) >= start and now - datetime.fromisoformat(tried) < timedelta(
            minutes=RETRY_MINUTES):
        return False  # net gestart (of geprobeerd): de robot heeft tijd nodig om te starten
    if tried and datetime.fromisoformat(tried) >= start and last and last >= start:
        return False
    return last is None or last < start - timedelta(minutes=1)


def run(hotel_id: str, now: datetime | None = None) -> str:
    """Aangeroepen door de timer (elke minuut). Geeft terug wat er gebeurde (leeg = niets)."""
    from hotel_checkin.admin import cloud_robot

    if not cloud_robot.available() or not due(hotel_id, now):
        return ""
    now = now or datetime.now(UTC)
    guests.set_state(hotel_id, STATE, now.isoformat())
    if cloud_robot.running():
        return "robot is al bezig"
    ok = cloud_robot.start()
    if not ok:
        logging.warning("%s: robot niet gestart op schema: %s", hotel_id, cloud_robot.LAST_ERROR)
        guests.log_robot_run(hotel_id, "robot", now, False, 0, 0,
                             f"robot niet gestart op schema: {cloud_robot.LAST_ERROR}. "
                             f"Opnieuw over {RETRY_MINUTES} minuten")
        return f"robot niet gestart: {cloud_robot.LAST_ERROR}"
    from hotel_checkin.core import progress

    why = "op een nachtelijk uur" if is_night(hotel_id, now) else f"op schema (om de {minutes(hotel_id):g} minuten)"
    progress.step(hotel_id, "robot", f"gestart {why}: Azure start de robot", force=True)
    return "robot gestart op schema"
