"""Voortgang van de robot, live te volgen in de monitor (instellingen, Robot).

De robot noteert per hotel welke taak bezig is en hoe ver ze staat ("Overschrijvingen: 3 van 12,
CPB-4276-002751"). Eén regel in de opslag (state robot_progress), overschreven bij elke stap en gewist als de
run klaar is. Hoogstens om de 2 seconden geschreven, behalve bij een nieuwe taak, zodat het de robot niet
vertraagt. Mislukt het schrijven, dan gaat de robot gewoon verder.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime

KEY = "robot_progress"
_last: dict[str, tuple[float, str]] = {}  # hotel -> (laatst geschreven, taak)
_started: dict[str, str] = {}  # hotel -> start van de run
_task_started: dict[str, str] = {}  # hotel -> start van de huidige taak


def step(hotel_id: str, task: str, text: str, force: bool = False) -> None:
    """Noteer wat de robot nu doet. task = de taaknaam uit het robotlog (bv. "overschrijving_booking")."""
    now = time.monotonic()
    last = _last.get(hotel_id)
    new_task = not last or last[1] != task
    if not (force or new_task) and last and now - last[0] < 2:
        return
    stamp = datetime.now(UTC).isoformat()
    _started.setdefault(hotel_id, stamp)
    if new_task:
        _task_started[hotel_id] = stamp
    _last[hotel_id] = (now, task)
    try:
        from hotel_checkin.guests import repository as guests

        guests.set_state(hotel_id, KEY, json.dumps({
            "run": os.environ.get("CONTAINER_APP_JOB_EXECUTION_NAME", ""),
            "task": task, "text": text[:300], "run_started": _started[hotel_id],
            "task_started": _task_started[hotel_id], "updated": stamp}))
    except Exception:
        logging.debug("voortgang niet bewaard", exc_info=True)


def finish(hotel_id: str, text: str = "klaar: alle taken gedaan, Azure sluit de robot af") -> None:
    """Alle taken zijn gedaan. De live regel blijft staan zolang Azure de run nog als bezig toont
    (afsluiten van de container duurt even), daarna verdwijnt ze in de monitor."""
    try:
        from hotel_checkin.guests import repository as guests

        stamp = datetime.now(UTC).isoformat()
        guests.set_state(hotel_id, KEY, json.dumps({
            "run": os.environ.get("CONTAINER_APP_JOB_EXECUTION_NAME", ""), "task": "robot", "text": text,
            "run_started": _started.get(hotel_id, stamp), "task_started": stamp, "updated": stamp, "done": True}))
    except Exception:
        logging.debug("voortgang niet bewaard", exc_info=True)
    _last.pop(hotel_id, None)
    _started.pop(hotel_id, None)
    _task_started.pop(hotel_id, None)


def done(hotel_id: str) -> None:
    """Geen live regel meer (bv. run overgeslagen)."""
    _last.pop(hotel_id, None)
    _started.pop(hotel_id, None)
    _task_started.pop(hotel_id, None)
    try:
        from hotel_checkin.guests import repository as guests

        guests.delete_state(hotel_id, KEY)
    except Exception:
        logging.debug("voortgang niet gewist", exc_info=True)


def current(hotel_id: str) -> dict | None:
    """Wat de robot nu doet (voor de monitor), of None."""
    try:
        from hotel_checkin.guests import repository as guests

        raw = guests.get_state(hotel_id, KEY)
        return json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001
        return None
