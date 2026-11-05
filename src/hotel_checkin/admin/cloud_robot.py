"""De robot in Azure (Container Apps Job) starten en volgen vanuit de opvolgpagina.

De Function App gebruikt haar eigen identiteit (rol op de job, zie infra/main.bicep).
Instelling ROBOT_JOB_ID: resource-id van de job. Leeg = geen robot in deze omgeving.
"""

from __future__ import annotations

import os

import httpx

ARM = "https://management.azure.com"
API_VERSION = "2024-03-01"


def available() -> bool:
    return bool(os.environ.get("ROBOT_JOB_ID"))


def _headers() -> dict:
    from hotel_checkin.core.clients import azure_credential

    token = azure_credential().get_token(f"{ARM}/.default").token
    return {"Authorization": f"Bearer {token}"}


LAST_ERROR = ""  # waarom de laatste start() mislukte (voor het log)


def start() -> bool:
    """Start een run nu, met de instellingen van de job zelf. Geen aangepaste instellingen meesturen: de rol
    "Container Apps Jobs Operator" van de Function App mag een run starten, maar niet de instellingen ervan
    wijzigen (Azure: JobStartOverrideAuthorizationFailed). ROBOT_MANUAL=1 staat daarom vast in de job
    (infra/main.bicep): elke start leest alle hotels."""
    job = os.environ["ROBOT_JOB_ID"]
    r = httpx.post(f"{ARM}{job}/start?api-version={API_VERSION}", headers=_headers(), timeout=30)
    global LAST_ERROR
    LAST_ERROR = "" if r.status_code in (200, 202) else f"Azure antwoordde {r.status_code}: {r.text[:200]}"
    return r.status_code in (200, 202)


def executions(limit: int = 30) -> list[dict]:
    """Laatste runs van de job volgens Azure (ook runs die mislukten voor ze iets konden loggen)."""
    job = os.environ["ROBOT_JOB_ID"]
    r = httpx.get(f"{ARM}{job}/executions?api-version={API_VERSION}", headers=_headers(), timeout=30)
    if r.status_code != 200:
        return []
    out = [{
        "name": e.get("name", ""),
        "status": e.get("properties", {}).get("status", ""),
        "start": e.get("properties", {}).get("startTime", ""),
        "end": e.get("properties", {}).get("endTime", ""),
    } for e in r.json().get("value", [])]
    return sorted(out, key=lambda e: e["start"], reverse=True)[:limit]


def running(execs: list[dict] | None = None) -> bool:
    return any(e["status"] in ("Running", "Processing") for e in (execs if execs is not None else executions()))
