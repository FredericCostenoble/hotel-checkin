"""De Lighthouse-robot als los programma (container in Azure Container Apps).

Draait op schema (bv. elke 20 minuten) en op vraag via de knop "Robot nu draaien" op de
opvolgpagina. Leest Lighthouse alleen; schrijft niets in Lighthouse.

    python -m hotel_checkin.robot                  # alle hotels, sinds de nieuwste opgeslagen boeking
    python -m hotel_checkin.robot --hotel lucca --hours 48

Schema van de job per omgeving: GitHub-variabele ROBOT_SCHEDULE (cron, UTC), standaard elke
20 minuten. Per hotel kan het trager: [robot] check_minutes in het hotelbestand, per omgeving te
overschrijven met Key Vault-geheim <hotel>-robot-check-minutes. Op vraag (knop in de monitor,
ROBOT_MANUAL=1) worden alle hotels gelezen.

Elke run zoekt nieuwe reservaties (en leest van nieuwe meteen de contactgegevens). Om de zoveel
uur ([robot] contact_refresh_hours in het hotelbestand, standaard 2) leest hij ook de
contactgegevens opnieuw van reservaties die binnenkort aankomen en nog geen e-mailadres hebben.

Zonder --hours leest de robot alles sinds de nieuwste boeking die al opgeslagen is (min 1 uur
marge), of de laatste 30 dagen als er nog niets opgeslagen is. Had de vorige run een fout of
overgeslagen rijen, dan leest hij dezelfde periode opnieuw.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from hotel_checkin.core.hotels import list_hotels
from hotel_checkin.guests import repository as guests
from hotel_checkin.core.config import hotel_setting
from hotel_checkin.processes import new_reservation, refresh_contacts


def _since(hotel_id: str, hours: int | None) -> datetime:
    """Vanaf welke boekdatum lezen.

    - Met --hours: een vast aantal uren terug.
    - Had de vorige run een fout of overgeslagen rijen: opnieuw vanaf dezelfde datum, zodat die
      rijen nog eens geprobeerd worden (bestaande reservaties worden gewoon bijgewerkt).
    - Anders: de nieuwste opgeslagen boeking (min 1 uur marge), of 30 dagen als er nog niets is.
    """
    now = datetime.now(timezone.utc)
    if hours:
        return now - timedelta(hours=hours)
    runs = [r for r in guests.robot_runs(hotel_id) if r.get("task") == new_reservation.TASK]
    if runs and runs[0].get("since") and (not runs[0].get("ok") or int(runs[0].get("skipped") or 0)):
        return datetime.fromisoformat(runs[0]["since"])
    booked = [r.booked_at for r in guests.list_reservations(hotel_id) if r.booked_at]
    if booked:
        return max(booked) - timedelta(hours=1)
    return now - timedelta(days=30)


def _check_due(hotel_id: str) -> bool:
    """Is het tijd om opnieuw naar nieuwe reservaties te kijken voor dit hotel?"""
    if os.environ.get("ROBOT_MANUAL"):
        return True
    minutes = float(hotel_setting(hotel_id, "ROBOT_CHECK_MINUTES", default="20", shared=False))
    runs = [r for r in guests.robot_runs(hotel_id) if r.get("task") == new_reservation.TASK and r.get("ok")]
    if not runs:
        return True
    last = datetime.fromisoformat(runs[0]["started_at"])
    # 2 minuten marge: een run op schema start nooit precies op dezelfde seconde
    return datetime.now(timezone.utc) - last >= timedelta(minutes=minutes) - timedelta(minutes=2)


def _refresh_due(hotel_id: str) -> bool:
    """Is het tijd om de contactgegevens opnieuw na te lezen?"""
    hours = float(hotel_setting(hotel_id, "ROBOT_CONTACT_REFRESH_HOURS", default="2", shared=False))
    runs = [r for r in guests.robot_runs(hotel_id) if r.get("task") == refresh_contacts.TASK and r.get("ok")]
    if not runs:
        return True
    last = datetime.fromisoformat(runs[0]["started_at"])
    # 5 minuten marge, zodat een run op schema net na het uur niet een beurt overslaat
    return datetime.now(timezone.utc) - last >= timedelta(hours=hours) - timedelta(minutes=5)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--hotel", default=os.environ.get("ROBOT_HOTEL") or None)
    p.add_argument("--hours", type=int, default=None)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    failed = False
    for hotel_id in [args.hotel] if args.hotel else list_hotels():
        if not args.hours and not _check_due(hotel_id):
            logging.info("%s: interval nog niet om, overgeslagen", hotel_id)
            continue
        since = _since(hotel_id, args.hours)
        try:
            new = new_reservation.run(hotel_id, since)
            logging.info("%s: %s nieuwe reservaties", hotel_id, new)
            if _refresh_due(hotel_id):
                found = refresh_contacts.run(hotel_id)
                logging.info("%s: %s e-mailadressen gevonden bij nalezen", hotel_id, found)
            # Log van de robot opruimen (standaard 30 dagen, instelling ROBOT_LOG_DAYS)
            guests.prune_robot_runs(hotel_id, int(os.environ.get("ROBOT_LOG_DAYS") or 30))
        except Exception:  # noqa: BLE001 - staat ook in het robotlog (opvolgpagina)
            logging.exception("%s: robot mislukt", hotel_id)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
