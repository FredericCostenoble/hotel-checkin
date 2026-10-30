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
    from azure.identity import DefaultAzureCredential

    token = DefaultAzureCredential().get_token(f"{ARM}/.default").token
    return {"Authorization": f"Bearer {token}"}


def start() -> bool:
    """Start een run nu. Zelfde instellingen als de geplande runs, plus ROBOT_MANUAL=1: dan leest de
    robot alle hotels, ook als hun eigen interval ([robot] check_minutes) nog niet om is."""
    job = os.environ["ROBOT_JOB_ID"]
    headers = _headers()
    body: dict = {}
    r = httpx.get(f"{ARM}{job}?api-version={API_VERSION}", headers=headers, timeout=30)
    if r.status_code == 200:
        containers = r.json().get("properties", {}).get("template", {}).get("containers", [])
        for c in containers:
            c["env"] = [e for e in c.get("env", []) if e.get("name") != "ROBOT_MANUAL"] + [
                {"name": "ROBOT_MANUAL", "value": "1"}]
        if containers:
            body = {"containers": containers}
    r = httpx.post(f"{ARM}{job}/start?api-version={API_VERSION}", json=body, headers=headers, timeout=30)
    return r.status_code in (200, 202)


def executions(limit: int = 10) -> list[dict]:
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
