"""Bouwblok 5: gastgegevens wegschrijven en lezen (Azure Table Storage).

Bewaartermijn en wat er precies bewaard wordt, beslist de verwerkingsverantwoordelijke.
Bewaar alleen wat nodig is voor de check-in en het wettelijke gastenregister.
"""

from __future__ import annotations

from hotel_checkin.core.models import Guest, Reservation


def save_guest(reservation: Reservation) -> None:
    """Sla de gast en de koppeling met de reservatie op (insert of update)."""
    raise NotImplementedError("Bouwblok gastgegevens (opslaan): nog te implementeren")


def get_guest(reservation_id: str) -> Guest | None:
    """Haal de gast op die bij een reservatie hoort."""
    raise NotImplementedError("Bouwblok gastgegevens (lezen): nog te implementeren")


def find_by_phone(phone: str) -> list[Reservation]:
    """Reservaties waarvan de gast dit gsm-nummer heeft (gebruikt door de telefooncentrale)."""
    raise NotImplementedError("Bouwblok gastgegevens (zoeken op nummer): nog te implementeren")
