"""Gemeenschappelijke testinstellingen.

Standaard draaien de tests alsof het productie is (APP_ENV=prd), zodat ontvangers niet omgeleid
worden. De omleiding buiten productie wordt apart getest in test_safety.py.
"""

import pytest


@pytest.fixture(autouse=True)
def _production_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prd")


@pytest.fixture(autouse=True)
def _self_test_done(monkeypatch, request):
    """De dagelijkse zelftest van Lighthouse niet in elke test (eigen tests in test_pms_health.py)."""
    if request.module.__name__.endswith("test_pms_health"):
        return
    from hotel_checkin.processes import pms_health

    monkeypatch.setattr(pms_health, "due", lambda *a, **k: False)
    pms_health._cache.clear()
