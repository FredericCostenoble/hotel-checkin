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
    """Start een run nu (zelfde instellingen als de geplande runs)."""
    job = os.environ["ROBOT_JOB_ID"]
    r = httpx.post(f"{ARM}{job}/start?api-version={API_VERSION}", json={}, headers=_headers(), timeout=30)
    return r.status_code in (200, 202)


def running() -> bool:
    job = os.environ["ROBOT_JOB_ID"]
    r = httpx.get(f"{ARM}{job}/executions?api-version={API_VERSION}", headers=_headers(), timeout=30)
    if r.status_code != 200:
        return False
    return any(e.get("properties", {}).get("status") in ("Running", "Processing")
               for e in r.json().get("value", []))
