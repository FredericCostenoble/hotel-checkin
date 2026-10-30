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


@app.route(route="api/twilio/status", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def twilio_status(req: func.HttpRequest) -> func.HttpResponse:
    """Twilio meldt of een WhatsApp of sms afgeleverd is. Alleen met een geldige handtekening van Twilio."""
    from urllib.parse import parse_qsl

    from hotel_checkin.messaging._twilio import valid_signature
    from hotel_checkin.processes import send_messages

    hotel, rid, mid = req.params.get("h", ""), req.params.get("r", ""), req.params.get("m", "")
    form = dict(parse_qsl(req.get_body().decode("utf-8", "replace")))
    if hotel not in list_hotels() or not valid_signature(hotel, req.url, form, req.headers.get("X-Twilio-Signature", "")):
        return func.HttpResponse(status_code=403)
    status = form.get("MessageStatus", "")
    if status in ("delivered", "read", "undelivered", "failed"):
        send_messages.twilio_status(hotel, rid, mid, status, form.get("ErrorCode", ""))
    return func.HttpResponse(status_code=204)


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
    if what == "preview" and req.method == "POST":
        # Voorbeeldmail voor een stap (tabblad Workflow)
        try:
            return _json(200, admin.workflow_preview(hotel, req.get_json()))
        except ValueError:
            return _json(400, {"error": "json"})
    if what == "workflow":
        # Tabblad Workflow: lezen, wijzigen (met wie en wanneer) of terug naar de standaard
        if req.method == "GET":
            return _json(200, admin.workflow_view(hotel))
        if req.method == "POST" and req.params.get("action") == "reset":
            return _json(200, admin.workflow_reset(hotel))
        if req.method == "POST":
            try:
                body = req.get_json()
            except ValueError:
                return _json(400, {"error": "json"})
            ok, data = admin.workflow_save(hotel, body, _admin_user(req) or "")
            return _json(200 if ok else 400, data)
    if req.method == "GET" and what == "guests":
        return _json(200, admin.guests(hotel))
    if req.method == "POST" and what == "maintenance":
        # Knop "Synchroniseren": gasten koppelen, voorbije verblijven meetellen, opruimen
        from hotel_checkin.processes import maintenance

        return _json(200, maintenance.run(hotel))
    if req.method == "POST" and what == "guests":
        # Mogelijke dubbels: samenvoegen of onthouden dat het andere personen zijn
        a, b = req.params.get("a", ""), req.params.get("b", "")
        if req.params.get("action") == "merge":
            return _json(200, {"ok": admin.merge_guests(hotel, a, b)})
        if req.params.get("action") == "different":
            return _json(200, {"ok": admin.mark_guests_different(hotel, a, b)})
        if req.params.get("action") == "channels":
            # kanalen voor één gast uitzetten: ?action=channels&a=<guest_id>&muted=email,sms
            muted = [c for c in req.params.get("muted", "").split(",") if c]
            return _json(200, {"ok": admin.set_muted_channels(hotel, a, muted)})
        return _json(400, {"error": "action"})
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
        if req.params.get("all") == "1":
            return _json(200, {"deleted": admin.delete_runs(hotel, req.params.get("task"))})
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



@app.timer_trigger(schedule="0 */2 * * * *", arg_name="timer", run_on_startup=False, use_monitor=False)
def send_messages(timer: func.TimerRequest) -> None:
    """Elke 2 minuten: berichten uit de workflow versturen die nu moeten (processes/send_messages.py)."""
    import logging

    from hotel_checkin.processes import send_messages as process

    for hotel_id in list_hotels():
        try:
            process.run(hotel_id)
        except Exception:  # noqa: BLE001
            logging.exception("%s: berichten versturen mislukt", hotel_id)
