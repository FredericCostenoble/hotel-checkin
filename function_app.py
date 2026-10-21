"""Azure Functions (Python v2-model): dunne wrappers rond de processen en bouwblokken.

De Lighthouse-robot zelf (headless browser) draait als Azure Container Apps Job,
niet in deze Function App.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import azure.functions as func

from hotel_checkin.processes import new_reservation

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.timer_trigger(schedule="0 */10 * * * *", arg_name="timer", run_on_startup=False)
def poll_new_reservations(timer: func.TimerRequest) -> None:
    since = datetime.now(timezone.utc) - timedelta(minutes=15)
    count = new_reservation.run(since)
    logging.info("Nieuwe reservaties verwerkt: %s", count)


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("ok")
