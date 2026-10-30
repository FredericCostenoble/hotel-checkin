"""Proces: gasten synchroniseren en opruimen per hotel.

Geen eigen schema: draait met de knop "Synchroniseren" in de monitor, en één keer per dag mee in
een run van de robot die toch al draait. Telt nooit iets dubbel (stay_counted_at).

1. Reservaties zonder gastprofiel koppelen (processes/guest_profiles.py).
2. Voorbije, niet geannuleerde verblijven meetellen in het gastprofiel.
3. Reservaties (en hun berichtenlog) verwijderen zodra het vertrek langer dan
   [retention] reservation_days geleden is (Lucca: 30, zoals in de privacyverklaring).
   Alleen als het verblijf al meegeteld is of geannuleerd werd.
4. Gastprofielen verwijderen als het laatste verblijf langer dan [retention] guest_days geleden
   is (Lucca: 730, soft opt-in "max. 2 jaar na het laatste verblijf"), en profielen zonder
   verblijf en zonder reservaties meer.
De blokkeerlijst voor marketing (MarketingOptOut) blijft altijd staan.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.guests import profiles
from hotel_checkin.guests import repository as guests
from hotel_checkin.processes import guest_profiles

TASK = "onderhoud"
STATE_KEY = "maintenance_last_day"


def due(hotel_id: str, today: date | None = None) -> bool:
    """Vandaag nog niet gesynchroniseerd?"""
    return guests.get_state(hotel_id, STATE_KEY) != (today or date.today()).isoformat()


def _days(hotel_id: str, name: str, default: int) -> int:
    return int(hotel_setting(hotel_id, name, default=str(default), shared=False))


def run(hotel_id: str, today: date | None = None) -> dict:
    started = datetime.now(timezone.utc)
    today = today or date.today()
    keep_res = _days(hotel_id, "RETENTION_RESERVATION_DAYS", 30)
    keep_guest = _days(hotel_id, "RETENTION_GUEST_DAYS", 730)
    done = {"linked": 0, "counted": 0, "reservations_deleted": 0, "guests_deleted": 0}
    try:
        pool = profiles.list_profiles(hotel_id)
        reservations = guests.list_reservations(hotel_id)
        for r in reservations:
            if not r.guest_id and guest_profiles.link(r, pool):
                done["linked"] += 1
            if guest_profiles.count_stay(r, today):
                done["counted"] += 1
        remaining: set[str] = set()
        for r in guests.list_reservations(hotel_id):
            old = r.departure < today - timedelta(days=keep_res)
            if old and (r.stay_counted_at or r.status == ReservationStatus.CANCELLED or not r.guest_id):
                guests.delete_reservation(hotel_id, r.reservation_id)
                done["reservations_deleted"] += 1
            else:
                remaining.add(r.reservation_id)
        for g in profiles.list_profiles(hotel_id):
            g.reservation_ids = [x for x in g.reservation_ids if x in remaining]
            expired = g.last_stay and g.last_stay < today - timedelta(days=keep_guest)
            empty = not g.stays and not g.reservation_ids
            if expired or empty:
                profiles.delete_profile(hotel_id, g.guest_id)
                done["guests_deleted"] += 1
            else:
                profiles.save_profile(g)
    except Exception as exc:
        guests.log_robot_run(hotel_id, TASK, started, False, error=f"{type(exc).__name__}: {exc}")
        raise
    note = (f"{done['linked']} gekoppeld, {done['counted']} verblijven meegeteld, "
            f"{done['reservations_deleted']} reservaties verwijderd (vertrek voor "
            f"{today - timedelta(days=keep_res):%d/%m/%Y}), {done['guests_deleted']} gasten verwijderd")
    guests.log_robot_run(hotel_id, TASK, started, True, done["counted"], done["linked"], note)
    guests.set_state(hotel_id, STATE_KEY, today.isoformat())
    return done
