"""De Lighthouse-robot als los programma (container in Azure Container Apps).

Draait op schema (bv. elk kwartier) en op vraag via de knop "Robot nu draaien" op de
opvolgpagina. Leest Lighthouse alleen; schrijft niets in Lighthouse.

    python -m hotel_checkin.robot                  # alle hotels, sinds de nieuwste opgeslagen boeking
    python -m hotel_checkin.robot --hotel lucca --hours 48

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
from hotel_checkin.processes import new_reservation


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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--hotel", default=os.environ.get("ROBOT_HOTEL") or None)
    p.add_argument("--hours", type=int, default=None)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    failed = False
    for hotel_id in [args.hotel] if args.hotel else list_hotels():
        since = _since(hotel_id, args.hours)
        try:
            new = new_reservation.run(hotel_id, since)
            logging.info("%s: %s nieuwe reservaties", hotel_id, new)
            # Log van de robot opruimen (standaard 30 dagen, instelling ROBOT_LOG_DAYS)
            guests.prune_robot_runs(hotel_id, int(os.environ.get("ROBOT_LOG_DAYS") or 30))
        except Exception:  # noqa: BLE001 - staat ook in het robotlog (opvolgpagina)
            logging.exception("%s: robot mislukt", hotel_id)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
