"""Azure Functions (Python v2-model): dunne wrappers rond de processen en bouwblokken.

De Lighthouse-robot zelf (headless browser) draait als Azure Container Apps Job
(src/hotel_checkin/robot.py), niet in deze Function App.

Ook de API van het check-in-formulier draait hier (de pagina's zelf staan in Static Web Apps):
    GET  /api/checkin/{token}
    POST /api/checkin/{token}   body: {"email", "phone", "backup_email", "backup_phone", "language", "no_marketing"}
Toegelaten herkomst (CORS) wordt in Azure ingesteld, zie infra/main.bicep.

Opvolgpagina (bevat gastgegevens): /monitor/ en /api/monitor/..., alleen na aanmelden met een
Microsoft-account (ingebouwde login van Azure, zie infra/README.md). Zonder die login
(instelling ADMIN_AUTH leeg) blijft de opvolgpagina dicht.

Routes staan volledig uitgeschreven (routePrefix is leeg in host.json). /admin (ook in /api/admin) is in Azure
Functions gereserveerd, daarom /monitor/.
"""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path

import azure.functions as func

from hotel_checkin.admin import cloud_robot
from hotel_checkin.admin import service as admin
from hotel_checkin.checkin import service as checkin
from hotel_checkin.core.hotels import list_hotels

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="api/health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("ok")


def _json(status: int, obj) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(obj), status_code=status, mimetype="application/json",
        headers={"Cache-Control": "no-store"},
    )


@app.route(route="api/checkin/{token}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def get_checkin(req: func.HttpRequest) -> func.HttpResponse:
    data = checkin.form_data(req.route_params.get("token", ""))
    return _json(200, data) if data else _json(404, {"error": "not_found"})


@app.route(route="api/checkin/{token}", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def post_checkin(req: func.HttpRequest) -> func.HttpResponse:
    try:
        p = req.get_json()
    except ValueError:
        return _json(400, {"ok": False, "errors": {"body": "invalid"}})
    if not isinstance(p, dict):
        return _json(400, {"ok": False, "errors": {"body": "invalid"}})
    ok, errors = checkin.submit(req.route_params.get("token", ""), p)
    return _json(200 if ok else 400, {"ok": ok, "errors": errors})


# ---------------------------------------------------------------- opvolgpagina

ADMIN_WEB = Path(__file__).parent / "web" / "admin"


def _admin_user(req: func.HttpRequest) -> str | None:
    """Aangemelde gebruiker volgens de ingebouwde login van Azure, anders None.

    Azure verwijdert X-MS-*-headers die van buiten komen; ze zijn dus alleen aanwezig na aanmelden.
    """
    if os.environ.get("ADMIN_AUTH") != "easyauth":
        return None
    return req.headers.get("x-ms-client-principal-name") or None


def _login_redirect() -> func.HttpResponse:
    return func.HttpResponse(status_code=302, headers={
        "Location": "/.auth/login/aad?post_login_redirect_uri=/monitor/"})


@app.route(route="monitor/{*path}", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def admin_page(req: func.HttpRequest) -> func.HttpResponse:
    if not _admin_user(req):
        return _login_redirect()
    rel = req.route_params.get("path") or "index.html"
    file = (ADMIN_WEB / rel).resolve()
    if not file.is_relative_to(ADMIN_WEB.resolve()) or not file.is_file():
        return func.HttpResponse("Not found", status_code=404)
    return func.HttpResponse(file.read_bytes(), mimetype=mimetypes.guess_type(file.name)[0],
                             headers={"Cache-Control": "no-store"})


@app.route(route="monitor", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def admin_root(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(status_code=302, headers={"Location": "/monitor/"})


@app.route(route="api/monitor/hotels", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def admin_hotels(req: func.HttpRequest) -> func.HttpResponse:
    if not _admin_user(req):
        return _json(401, {"error": "login"})
    return _json(200, admin.hotels())


@app.route(route="api/monitor/{hotel}/{what}", methods=["GET", "POST", "DELETE"], auth_level=func.AuthLevel.ANONYMOUS)
def admin_api(req: func.HttpRequest) -> func.HttpResponse:
    if not _admin_user(req):
        return _json(401, {"error": "login"})
    hotel, what = req.route_params["hotel"], req.route_params["what"]
    if hotel not in list_hotels():
        return _json(404, {"error": "hotel"})
    if req.method == "GET" and what == "reservations":
        return _json(200, admin.reservations(hotel))
    if req.method == "GET" and what == "runs":
        data = admin.runs(hotel)
        if cloud_robot.available():
            data["executions"] = cloud_robot.executions()
            data["running"] = cloud_robot.running(data["executions"])
        return _json(200, data | {"can_run": cloud_robot.available(), "cloud": True})
    if req.method == "POST" and what == "run":
        # De robot (browser) draait als Container Apps Job, niet in de Function App
        if not cloud_robot.available():
            return _json(501, {"error": "robot_not_in_cloud"})
        return _json(200, {"started": cloud_robot.start()})
    if req.method == "DELETE" and what == "runs":
        # Eén regel uit het robotlogboek verwijderen (vuilbakje in de monitor)
        return _json(200, {"deleted": admin.delete_run(hotel, req.params.get("id", ""))})
    return _json(404, {"error": "not_found"})


@app.timer_trigger(schedule="0 * * * * *", arg_name="timer", run_on_startup=False, use_monitor=False)
def mail_trigger(timer: func.TimerRequest) -> None:
    """Elke minuut: meldingen van Lighthouse/Cubilis in de mailbox starten de robot (processes/mail_trigger.py)."""
    import logging

    from hotel_checkin.processes import mail_trigger as process

    for hotel_id in list_hotels():
        try:
            if process.enabled(hotel_id):
                process.run(hotel_id)
        except Exception:  # noqa: BLE001 - het volgende hotel mag niet tegengehouden worden
            logging.exception("%s: mail_trigger mislukt", hotel_id)
