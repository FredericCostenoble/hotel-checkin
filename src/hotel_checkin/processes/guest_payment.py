"""Proces: de gast klikte in de gast-app op Betalen.

Of de betaling binnen is, staat in Lighthouse (folio, openstaand saldo). De robot leest dat bij het bijwerken van de
reservaties. Zodra de gast op Betalen klikt, vragen we die nalezing meteen aan (refresh_requests, zelfde weg als een
meldingsmail van Lighthouse) en starten we de robot als hij niet al bezig is. De app toont intussen "betaling wordt
verwerkt"; na de nalezing ziet de gast "betaald" en, als de kamer nu betaald is, volgt de code met de code-mail.

Hoogstens één keer per THROTTLE per reservatie, zodat herhaald klikken de robot niet telkens start.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from hotel_checkin.core.models import Channel, Reservation, SendResult
from hotel_checkin.guests import repository as guests

MESSAGE_TYPE = "app_pay"
THROTTLE = timedelta(minutes=10)


def _state_key(r: Reservation) -> str:
    return f"app_pay_{r.reservation_id}"


def pay_started(hotel_id: str, r: Reservation, now: datetime) -> bool:
    """Vraag een nalezing van de reservatie aan (en start de robot). False als het niet nodig is of net gebeurde."""
    if r.open_amount is None or r.open_amount <= 0.004:
        return False
    last = guests.get_state(hotel_id, _state_key(r))
    if last:
        try:
            if now - datetime.fromisoformat(last) < THROTTLE:
                return False
        except ValueError:
            pass
    guests.set_state(hotel_id, _state_key(r), now.isoformat())
    from hotel_checkin.processes import refresh_requests

    refresh_requests.request(hotel_id, [r.arrival])
    note = "gast klikte op Betalen in de gast-app; de reservatie wordt opnieuw gelezen"
    try:
        from hotel_checkin.admin import cloud_robot
        from hotel_checkin.processes import send_messages

        if cloud_robot.available() and send_messages.robot_needed(hotel_id) and not cloud_robot.running():
            if not cloud_robot.start():
                note += f" (robot niet gestart: {cloud_robot.LAST_ERROR}; volgende run)"
    except Exception as exc:  # noqa: BLE001 - de volgende run leest het toch
        logging.warning("%s: robot niet gestart na Betalen: %s", hotel_id, exc)
        note += " (robot niet gestart, volgende run)"
    guests.log_message(hotel_id, r.reservation_id, MESSAGE_TYPE, SendResult(Channel.APP, "betalen", True), note=note)
    return True
