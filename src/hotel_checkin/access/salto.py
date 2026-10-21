"""Bouwblok 6: code reserveren bij Salto KS via de KS Connect API.

Dit blok praat alleen met Salto. Het wegschrijven van de code in Lighthouse gebeurt in
`pms/lighthouse.py`, de procesmodule roept beide na elkaar op.
"""

from __future__ import annotations

from datetime import datetime

from hotel_checkin.core.models import AccessCode


def reserve_code(
    reservation_id: str,
    room: str,
    valid_from: datetime,
    valid_until: datetime,
    guest_name: str,
) -> AccessCode:
    """Maak een code aan voor deze kamer en periode en geef ze terug."""
    raise NotImplementedError("Bouwblok Salto (code reserveren): nog te implementeren")


def cancel_code(code: AccessCode) -> None:
    """Trek een code in (annulatie of wijziging van de reservatie)."""
    raise NotImplementedError("Bouwblok Salto (code intrekken): nog te implementeren")
