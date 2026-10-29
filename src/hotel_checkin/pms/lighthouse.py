"""Bouwblok 4 (en wegschrijven naar Lighthouse).

Voorlopig via browserautomatisatie (Playwright, headless Chromium) met een aparte
robotgebruiker per hotel (zonder MFA), zie lighthouse_browser.py. Sessiecookies bewaard tussen runs.
Als Lighthouse een API aanbiedt, komt er een tweede implementatie achter dezelfde functies.

Aandachtspunten uit de projectnotities:
- De folio/transacties laden asynchroon: altijd wachten tot de pagina volledig geladen is.
- De sleutelknop verschijnt pas als de status INGECHECKT is.
"""

from __future__ import annotations

from datetime import datetime

from hotel_checkin.core.models import AccessCode, Reservation, ReservationStatus


def get_new_reservations(since: datetime) -> list[Reservation]:
    """Reservaties die sinds `since` aangemaakt of gewijzigd zijn."""
    raise NotImplementedError("Bouwblok Lighthouse (lezen): nog te implementeren")


def get_reservation(reservation_id: str) -> Reservation:
    """Detail van één reservatie, inclusief betaalstatus."""
    raise NotImplementedError("Bouwblok Lighthouse (detail): nog te implementeren")


def store_access_code(code: AccessCode) -> None:
    """Schrijf de Salto-code weg bij de reservatie in Lighthouse."""
    raise NotImplementedError("Bouwblok Lighthouse (code wegschrijven): nog te implementeren")


def set_status(reservation_id: str, status: ReservationStatus) -> None:
    """Zet de status van de reservatie (bv. INGECHECKT)."""
    raise NotImplementedError("Bouwblok Lighthouse (status): nog te implementeren")
