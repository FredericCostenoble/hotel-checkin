"""Azure Functions (Python v2-model): dunne wrappers rond de processen en bouwblokken.

De Lighthouse-robot zelf (headless browser) draait als Azure Container Apps Job,
niet in deze Function App.

Ook de API van het check-in-formulier draait hier (de pagina's zelf staan in Static Web Apps):
    GET  /api/checkin/{token}
    POST /api/checkin/{token}   body: {"email", "phone", "backup_email", "backup_phone", "language", "no_marketing"}
Toegelaten herkomst (CORS) wordt in Azure ingesteld, zie infra/main.bicep.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import azure.functions as func

from hotel_checkin.checkin import service as checkin
from hotel_checkin.core.hotels import list_hotels
from hotel_checkin.processes import new_reservation

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.timer_trigger(schedule="0 */10 * * * *", arg_name="timer", run_on_startup=False)
def poll_new_reservations(timer: func.TimerRequest) -> None:
    # Staat uit tot het Lighthouse-bouwblok klaar is (instelling POLL_ENABLED=true in Azure).
    if os.environ.get("POLL_ENABLED", "").lower() != "true":
        return
    since = datetime.now(timezone.utc) - timedelta(minutes=15)
    for hotel_id in list_hotels():
        count = new_reservation.run(hotel_id, since)
        logging.info("%s: %s nieuwe reservaties", hotel_id, count)


@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("ok")


def _json(status: int, obj) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(obj), status_code=status, mimetype="application/json",
        headers={"Cache-Control": "no-store"},
    )


@app.route(route="checkin/{token}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_checkin(req: func.HttpRequest) -> func.HttpResponse:
    data = checkin.form_data(req.route_params.get("token", ""))
    return _json(200, data) if data else _json(404, {"error": "not_found"})


@app.route(route="checkin/{token}", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def post_checkin(req: func.HttpRequest) -> func.HttpResponse:
    try:
        p = req.get_json()
    except ValueError:
        return _json(400, {"ok": False, "errors": {"body": "invalid"}})
    if not isinstance(p, dict):
        return _json(400, {"ok": False, "errors": {"body": "invalid"}})
    ok, errors = checkin.submit(req.route_params.get("token", ""), p)
    return _json(200 if ok else 400, {"ok": ok, "errors": errors})
