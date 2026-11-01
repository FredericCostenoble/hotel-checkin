"""Context van de lopende robotrun (container), voor het robotlog in de monitor.

De robot noteert bij het starten wanneer het proces begon en welke run van Azure dit is
(CONTAINER_APP_JOB_EXECUTION_NAME, door Azure gezet). Elke regel die hij in het logboek schrijft,
krijgt die mee. Zo toont de monitor de hele opstart: Azure start de run, de container start,
browser starten, aanmelden, klaar om te lezen. Buiten de robot (Function App) is er geen context.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

_ctx: dict = {}


def start(process_started: float, execution: str = "") -> None:
    """process_started: time.time() zo vroeg mogelijk in het proces (begin van robot.py)."""
    _ctx.clear()
    _ctx.update(process_started=process_started, execution=execution or "")


def clear() -> None:
    _ctx.clear()


def fields() -> dict:
    """Extra velden voor een logregel van de robot (leeg buiten de robot)."""
    if not _ctx:
        return {}
    return {"process_started_at": datetime.fromtimestamp(_ctx["process_started"], UTC).isoformat(),
            "execution": _ctx["execution"]}


def seconds_since_start() -> float | None:
    """Seconden sinds het proces begon, of None buiten de robot."""
    return round(time.time() - _ctx["process_started"], 1) if _ctx else None
