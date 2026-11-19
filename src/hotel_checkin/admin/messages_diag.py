"""Diagnose (alleen lezen): mislukte berichten van een hotel, zonder namen of adressen (tijdstip, soort, kanaal, fout)."""

import sys
from collections import Counter

from hotel_checkin.guests import repository as repo


def main(hotel_id: str) -> None:
    failed = [m for ms in repo.messages_for_hotel(hotel_id).values() for m in ms if not m.get("ok")]
    print("mislukt:", len(failed))
    print("per dag:", sorted(Counter(str(m.get("sent_at", ""))[:10] for m in failed).items())[-10:])
    for m in sorted(failed, key=lambda m: str(m.get("sent_at", "")))[-15:]:
        print(" ", str(m.get("sent_at", ""))[:16], m.get("message_type"), m.get("channel"), "|", str(m.get("error", ""))[:90])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "lucca")
