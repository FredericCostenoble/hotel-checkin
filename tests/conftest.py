"""Gemeenschappelijke testinstellingen.

Standaard draaien de tests alsof het productie is (APP_ENV=prd), zodat ontvangers niet omgeleid
worden. De omleiding buiten productie wordt apart getest in test_safety.py.
"""

import pytest


@pytest.fixture(autouse=True)
def _production_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "prd")
