"""De Lighthouse-robot als los programma (container in Azure Container Apps).

Draait op schema (bv. elk kwartier) en op vraag via de knop "Robot nu draaien" op de
opvolgpagina. Leest Lighthouse alleen; schrijft niets in Lighthouse.

    python -m hotel_checkin.robot                  # alle hotels, sinds de vorige geslaagde run
    python -m hotel_checkin.robot --hotel lucca --hours 48

Zonder --hours leest de robot alles sinds de start van de vorige geslaagde run (min 1 uur
marge), of de laatste 48 uur als hij nog nooit gedraaid heeft.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

from hotel_checkin.core.hotels import list_hotels
from hotel_checkin.guests import repository as guests
from hotel_checkin.processes import new_reservation


def _since(hotel_id: str, hours: int | None) -> datetime:
    now = datetime.now(timezone.utc)
    if hours:
        return now - timedelta(hours=hours)
    last_ok = next((r for r in guests.robot_runs(hotel_id) if r.get("ok")), None)
    if last_ok:
        return datetime.fromisoformat(last_ok["started_at"]) - timedelta(hours=1)
    return now - timedelta(hours=48)


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
        except Exception:  # noqa: BLE001 - staat ook in het robotlog (opvolgpagina)
            logging.exception("%s: robot mislukt", hotel_id)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
