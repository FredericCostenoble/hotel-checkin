"""API van het check-in-formulier (Azure Static Web Apps, beheerde Functions, Python v2-model).

Bij de deployment worden src/hotel_checkin en config/ naar deze map gekopieerd (zie README).
Routes (Static Web Apps zet er /api voor):
    GET  /api/checkin/{token}
    POST /api/checkin/{token}   body: {"email", "phone", "language", "no_marketing"}
"""

import json

import azure.functions as func

from hotel_checkin.checkin import service

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _json(status: int, obj) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(obj), status_code=status, mimetype="application/json",
        headers={"Cache-Control": "no-store"},
    )


@app.route(route="checkin/{token}", methods=["GET"])
def get_checkin(req: func.HttpRequest) -> func.HttpResponse:
    data = service.form_data(req.route_params.get("token", ""))
    return _json(200, data) if data else _json(404, {"error": "not_found"})


@app.route(route="checkin/{token}", methods=["POST"])
def post_checkin(req: func.HttpRequest) -> func.HttpResponse:
    try:
        p = req.get_json()
    except ValueError:
        return _json(400, {"ok": False, "errors": {"body": "invalid"}})
    ok, errors = service.submit(
        req.route_params.get("token", ""), str(p.get("email", "")), str(p.get("phone", "")),
        str(p.get("language", "")), bool(p.get("no_marketing", False)),
    )
    return _json(200 if ok else 400, {"ok": ok, "errors": errors})
