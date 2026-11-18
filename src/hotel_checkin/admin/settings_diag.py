"""Diagnose (alleen lezen): laden de instellingen van de monitor met de gegevens van deze omgeving?
Toont de secties en welke secties in de monitor gewijzigd zijn (geen waarden)."""

import sys

from hotel_checkin.core import hotel_settings, hotels
from hotel_checkin.guests import repository


def main(hotel_id: str) -> None:
    doc = repository.get_config_doc(hotel_id, hotels.SETTINGS_DOC)
    print("gewijzigd in de monitor:", sorted(((doc or {}).get("value") or {}).keys()))
    v = hotel_settings.view(hotel_id)
    print("secties:", [s["section"] for s in v["sections"]])
    sw = next((s for s in v["sections"] if s["section"] == "schakelaars"), None)
    print("schakelaars:", [(f["key"], f["type"], f["value"], f["default"], f["env"], f["choices"]) for f in sw["fields"]] if sw else "ONTBREEKT")
    print("bewaard schakelaars:", ((doc or {}).get("value") or {}).get("schakelaars"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "lucca")
