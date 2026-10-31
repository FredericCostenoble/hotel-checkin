"""Bescherming van gasten buiten productie.

APP_ENV bepaalt de omgeving: "prd" (productie), "tst" (test in Azure) of "dev" (codespace, standaard).
Buiten "prd" gaat geen enkel bericht naar een echte gast: alles wordt omgeleid naar TEST_EMAIL
(mails) of TEST_PHONE (sms en WhatsApp). De oorspronkelijke ontvanger staat in het onderwerp of
vooraan in de tekst. Is er geen testadres ingesteld, dan wordt er niets verstuurd.

Het testadres per hotel staat in de instellingen (monitor, tabblad Hotel, sectie [test]); leeg =
het testadres van de omgeving (instelling TEST_EMAIL / TEST_PHONE van de Function App).
"""

from __future__ import annotations

import os

from hotel_checkin.core.config import get_setting


def environment() -> str:
    return (os.environ.get("APP_ENV") or "dev").strip().lower()


def is_production() -> bool:
    return environment() == "prd"


def test_address(kind: str, hotel_id: str | None = None) -> str | None:
    """Testadres (kind "email") of testnummer ("phone"): eerst dat van het hotel (instellingen),
    anders dat van de omgeving. None als er geen is."""
    setting = "TEST_EMAIL" if kind == "email" else "TEST_PHONE"
    if hotel_id:
        from hotel_checkin.core.config import hotel_setting

        return hotel_setting(hotel_id, setting, required=False) or None
    return get_setting(setting, required=False) or None


def route(kind: str, to: str, hotel_id: str | None = None) -> tuple[str | None, str]:
    """Geeft (echte ontvanger, voorvoegsel) terug. kind: "email" of "phone".

    In productie: (to, ""). Daarbuiten: (testadres, "[TST voor <to>] ") of (None, reden).
    """
    if is_production():
        return to, ""
    setting = "TEST_EMAIL" if kind == "email" else "TEST_PHONE"
    test = test_address(kind, hotel_id)
    if not test:
        return None, f"Niet verstuurd: {setting} is niet ingesteld (omgeving {environment()})."
    return test, f"[{environment().upper()} voor {to}] "
