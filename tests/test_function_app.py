"""Opvolgpagina in Azure: alleen na aanmelden (ingebouwde login), check-in-API blijft open."""

import sys
from pathlib import Path

import azure.functions as func
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import function_app as fa  # noqa: E402
from hotel_checkin.guests import repository as repo  # noqa: E402


def _fn(builder):
    return builder.build().get_user_function()


def _req(url, headers=None, params=None, method="GET"):
    return func.HttpRequest(method, url, headers=headers or {}, route_params=params or {}, body=b"")


@pytest.fixture(autouse=True)
def memory():
    repo.use_memory_store()


def test_admin_closed_without_auth_setting(monkeypatch):
    monkeypatch.delenv("ADMIN_AUTH", raising=False)
    # Ook met een (vervalste) header blijft het dicht als de login niet aan staat
    r = _fn(fa.admin_hotels)(_req("/api/monitor/hotels", {"x-ms-client-principal-name": "x@y"}))
    assert r.status_code == 401


def test_admin_needs_login(monkeypatch):
    monkeypatch.setenv("ADMIN_AUTH", "easyauth")
    assert _fn(fa.admin_hotels)(_req("/api/monitor/hotels")).status_code == 401
    assert _fn(fa.admin_page)(_req("/monitor/", params={"path": ""})).status_code == 302


def test_admin_with_login(monkeypatch):
    monkeypatch.setenv("ADMIN_AUTH", "easyauth")
    h = {"x-ms-client-principal-name": "frederic@hotellucca.be"}
    assert _fn(fa.admin_hotels)(_req("/api/monitor/hotels", h)).status_code == 200
    r = _fn(fa.admin_api)(_req("/api/monitor/lucca/reservations", h, {"hotel": "lucca", "what": "reservations"}))
    assert r.status_code == 200
    page = _fn(fa.admin_page)(_req("/monitor/", h, {"path": ""}))
    assert page.status_code == 200 and b"Opvolging" in page.get_body()
    bad = _fn(fa.admin_page)(_req("/monitor/../x", h, {"path": "../../function_app.py"}))
    assert bad.status_code == 404


def test_checkin_api_stays_open(monkeypatch):
    monkeypatch.setenv("ADMIN_AUTH", "easyauth")
    r = _fn(fa.get_checkin)(_req("/api/checkin/x", params={"token": "x"}))
    assert r.status_code == 404  # onbekend token, maar geen login gevraagd
