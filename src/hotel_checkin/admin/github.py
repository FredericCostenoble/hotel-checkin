"""Bouwblok: GitHub (de repo met de code). Alleen voor het herstellen na een wijziging in Lighthouse:
een workflow starten (herstelrobot, uitrol naar PRD) en opvragen welke versie waar draait.

Token: GITHUB_DEPLOY_TOKEN (Key Vault, secret github-deploy-token): fine-grained, alleen deze repo,
rechten Actions lezen en schrijven en Contents lezen. Repo: GITHUB_REPO (standaard FredericCostenoble/hotel-checkin).
Beslist niets: dat doet het proces (processes/repair.py).
"""

from __future__ import annotations

import base64
import json

import httpx as requests

from hotel_checkin.core.config import get_setting

API = "https://api.github.com"
TIMEOUT = 20


def _repo() -> str:
    return get_setting("GITHUB_REPO", default="FredericCostenoble/hotel-checkin", required=False)


def available() -> bool:
    return bool(get_setting("GITHUB_DEPLOY_TOKEN", required=False))


def _headers() -> dict:
    return {"Authorization": f"Bearer {get_setting('GITHUB_DEPLOY_TOKEN')}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "hotel-checkin"}


def run_workflow(workflow: str, inputs: dict, ref: str = "main") -> None:
    r = requests.post(f"{API}/repos/{_repo()}/actions/workflows/{workflow}/dispatches", headers=_headers(),
                      json={"ref": ref, "inputs": inputs}, timeout=TIMEOUT)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"GitHub {r.status_code}: {r.text[:200]}")


def last_deploy(env: str) -> dict | None:
    """Laatste geslaagde uitrol naar env (tst of prd): {"version", "sha", "at"} of None.
    De naam van elke uitrol is "Deploy tst" of "Deploy prd" (run-name in deploy.yml)."""
    r = requests.get(f"{API}/repos/{_repo()}/actions/workflows/deploy.yml/runs", headers=_headers(),
                     params={"status": "success", "per_page": 30}, timeout=TIMEOUT)
    r.raise_for_status()
    for run in r.json().get("workflow_runs", []):
        if run.get("display_title", "").strip().lower() == f"deploy {env}":
            return {"version": run["run_number"], "sha": run["head_sha"], "at": run["updated_at"]}
    return None


def main_sha() -> str:
    r = requests.get(f"{API}/repos/{_repo()}/commits/main", headers=_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["sha"]


def file_on_main(path: str) -> str | None:
    r = requests.get(f"{API}/repos/{_repo()}/contents/{path}", headers=_headers(), params={"ref": "main"},
                     timeout=TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return base64.b64decode(r.json()["content"]).decode("utf-8")


def json_at(path: str, ref: str) -> dict | None:
    r = requests.get(f"{API}/repos/{_repo()}/contents/{path}", headers=_headers(), params={"ref": ref}, timeout=TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    try:
        return json.loads(base64.b64decode(r.json()["content"]).decode("utf-8"))
    except ValueError:
        return None


def json_on_main(path: str) -> dict | None:
    text = file_on_main(path)
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None
