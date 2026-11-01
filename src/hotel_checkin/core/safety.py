"""Bescherming van gasten buiten productie.

APP_ENV bepaalt de omgeving: "prd" (productie), "tst" (test in Azure) of "dev" (codespace, standaard).
Buiten "prd" gaat geen enkel bericht naar een echte gast: alles wordt omgeleid naar het testadres
(mails) of testnummer (sms en WhatsApp) van het hotel. De oorspronkelijke ontvanger staat in het
onderwerp of vooraan in de tekst.

Het testadres en testnummer staan alleen in de instellingen van het hotel (monitor, tabblad Hotel,
sectie [test], standaard uit config/hotels/<hotel_id>.toml). Leeg = er wordt niets verstuurd.
Er is geen testadres per omgeving meer.
"""

from __future__ import annotations

import os


def environment() -> str:
    return (os.environ.get("APP_ENV") or "dev").strip().lower()


def is_production() -> bool:
    return environment() == "prd"


def test_address(kind: str, hotel_id: str | None = None) -> str | None:
    """Testadres (kind "email") of testnummer ("phone") uit de instellingen van het hotel, of None."""
    if not hotel_id:
        return None
    from hotel_checkin.core.hotels import load_hotel

    value = str(load_hotel(hotel_id).get("test", {}).get("email" if kind == "email" else "phone") or "").strip()
    return value or None


def route(kind: str, to: str, hotel_id: str | None = None) -> tuple[str | None, str]:
    """Geeft (echte ontvanger, voorvoegsel) terug. kind: "email" of "phone".

    In productie: (to, ""). Daarbuiten: (testadres, "[TST voor <to>] ") of (None, reden).
    """
    if is_production():
        return to, ""
    test = test_address(kind, hotel_id)
    if not test:
        what = "testadres e-mail" if kind == "email" else "testnummer sms en WhatsApp"
        return None, f"Niet verstuurd: geen {what} in de instellingen van het hotel (omgeving {environment()})."
    return test, f"[{environment().upper()} voor {to}] "
