"""Proces: de robot als vangnet op vaste tijden starten, vanuit de Function App.

De robot (Container Apps Job) start nooit meer op een eigen schema in Azure: een container starten om niets te doen
kost geld. De Function App kijkt elke minuut (timer van de meldingen) en start de robot alleen als:
- de robot iets te doen heeft (niet alle hoofdschakelaars uit, send_messages.robot_needed), en
- de vorige run of start langer geleden is dan [robot] check_minutes (instelling in de monitor, per omgeving;
  0 = nooit op schema, alleen bij een meldingsmail, een gevraagde lijst of de knop "Robot nu draaien").
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


def due(hotel_id: str, now: datetime | None = None) -> bool:
    from hotel_checkin.processes.send_messages import robot_needed

    every = minutes(hotel_id)
    if every <= 0 or not robot_needed(hotel_id):
        return False
    now = now or datetime.now(UTC)
    last = _last_run(hotel_id)
    tried = guests.get_state(hotel_id, STATE)
    if tried and now - datetime.fromisoformat(tried) < timedelta(minutes=min(every, RETRY_MINUTES)):
        return False  # net gestart (of geprobeerd): de robot heeft tijd nodig om te starten
    # 2 minuten marge: een run begint nooit op dezelfde seconde
    return last is None or now - last >= timedelta(minutes=every) - timedelta(minutes=2)


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
        return f"robot niet gestart: {cloud_robot.LAST_ERROR}"
    from hotel_checkin.core import progress

    progress.step(hotel_id, "robot", f"gestart op schema (om de {minutes(hotel_id):g} minuten): Azure start de robot",
                  force=True)
    return "robot gestart op schema"
