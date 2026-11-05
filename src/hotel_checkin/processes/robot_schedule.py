"""Proces: de robot als vangnet op vaste tijden starten, vanuit de Function App.

De robot (Container Apps Job) start nooit meer op een eigen schema in Azure: een container starten om niets te doen
kost geld. De Function App kijkt elke minuut (timer van de meldingen) en start de robot alleen als:
- de robot iets te doen heeft (niet alle hoofdschakelaars uit, send_messages.robot_needed), en
- het een vast uur is (om de [robot] check_minutes vanaf middernacht, bv. 60 = elk heel uur; instelling in de monitor,
  per omgeving; 0 = nooit op schema, alleen bij een meldingsmail, een gevraagde lijst of de knop "Robot nu draaien"),
  en er sinds dat uur nog geen run was.
Een bevroren omgeving (alle hoofdschakelaars uit) start dus geen enkele container.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from hotel_checkin.core.config import hotel_setting
from hotel_checkin.guests import repository as guests

STATE = "robot_schedule_started"  # RobotState: wanneer deze timer de robot voor het laatst startte (of probeerde)
RETRY_MINUTES = 10  # mislukt starten: zo lang wachten voor een nieuwe poging


def minutes(hotel_id: str) -> float:
    return float(hotel_setting(hotel_id, "ROBOT_CHECK_MINUTES", default="60", shared=False) or 0)


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

    progress.step(hotel_id, "robot", f"gestart op schema (om de {minutes(hotel_id):g} minuten): Azure start de robot",
                  force=True)
    return "robot gestart op schema"
