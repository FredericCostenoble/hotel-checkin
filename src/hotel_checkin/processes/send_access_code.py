"""Proces: code aanmaken en doorsturen, 1 dag voor aankomst.

Volgorde van bouwblokken:
  1. Lighthouse: reservatie ophalen, controleren dat ze betaald en INGECHECKT is
  2. Salto: code reserveren per kamer
  3. Lighthouse: code wegschrijven bij de reservatie
  4. Mail en WhatsApp (of SMS) naar de gast
"""

from __future__ import annotations

from datetime import datetime

from hotel_checkin.access import salto
from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.messaging import email
from hotel_checkin.pms import lighthouse


def run(hotel_id: str, reservation_id: str, check_in_time: datetime, check_out_time: datetime) -> None:
    reservation = lighthouse.get_reservation(hotel_id, reservation_id)
    if not reservation.paid or reservation.status != ReservationStatus.CHECKED_IN:
        # Nog niet klaar: geen code. Het proces probeert het later opnieuw.
        return

    for room in reservation.rooms:
        code = salto.reserve_code(
            reservation_id=reservation.reservation_id,
            room=room,
            valid_from=check_in_time,
            valid_until=check_out_time,
            guest_name=f"{reservation.guest.first_name} {reservation.guest.last_name}",
        )
        lighthouse.store_access_code(hotel_id, code)

    if reservation.guest.email:
        email.send_email(
            to=reservation.guest.email,
            subject="Uw toegangscode",  # TODO: tekst en taal via templates
            html_body="",
        )
