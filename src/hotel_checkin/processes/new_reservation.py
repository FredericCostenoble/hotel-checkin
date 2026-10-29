"""Proces: nieuwe reservatie binnengekomen in Lighthouse.

Voorbeeld van hoe een proces de bouwblokken combineert. Een proces bevat geen
technische details van Lighthouse, Salto of Twilio; die zitten in de bouwblokken.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse


def run(hotel_id: str, since: datetime) -> int:
    """Haal nieuwe reservaties van een hotel op en bewaar ze. Geeft het aantal nieuwe reservaties terug.

    Wat de gast zelf invulde in het check-in-formulier (contactgegevens, taal) en het token
    blijven behouden; Lighthouse overschrijft dat niet. Elke run wordt gelogd (opvolgpagina).
    Volgende stappen (bevestigingsmail, herinnering, code) komen in aparte processen.
    """
    started = datetime.now(timezone.utc)
    found = new = 0
    skipped: list[str] = []
    try:
        for reservation in lighthouse.get_new_reservations(hotel_id, since, skipped=skipped):
            found += 1
            existing = guests.get_reservation(hotel_id, reservation.reservation_id)
            if existing is None:
                new += 1
            else:
                _keep_known(reservation, existing)
            guests.save_reservation(reservation)
    except Exception as exc:
        guests.log_robot_run(hotel_id, TASK, started, False, found, new, f"{type(exc).__name__}: {exc}",
                             since=since, skipped=len(skipped))
        raise
    note = f"{len(skipped)} rij(en) overgeslagen: " + "; ".join(skipped[:5]) if skipped else None
    guests.log_robot_run(hotel_id, TASK, started, True, found, new, note, since=since, skipped=len(skipped))
    return new


TASK = "nieuwe_reservaties"


def _keep_known(reservation, existing) -> None:
    reservation.token = existing.token
    reservation.checkin_completed_at = existing.checkin_completed_at
    reservation.paid = existing.paid if reservation.paid is None else reservation.paid
    if existing.checkin_completed_at:
        reservation.guest = existing.guest
        return
    # De lijst bevat geen contactgegevens: eerder opgehaalde waarden niet wissen
    for field in ("email", "phone", "language", "country"):
        if not getattr(reservation.guest, field) or field == "language":
            setattr(reservation.guest, field, getattr(existing.guest, field))
