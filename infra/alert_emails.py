"""Adressen voor de waarschuwingen van Azure: [bewaking] email van elk hotel (config/hotels/*.toml).

Het platform (Function App, robot) is gedeeld door alle hotels: valt het stil, dan moet elk hotel het weten.
Gebruikt bij de uitrol (.github/workflows/deploy.yml); geeft de adressen met een komma ertussen.
Let op: dit zijn de adressen uit het hotelbestand; een adres dat alleen in de monitor gewijzigd werd,
geldt pas voor deze waarschuwingen nadat het ook in het hotelbestand staat.

    python3 infra/alert_emails.py config/hotels
"""

import sys
import tomllib
from pathlib import Path


def emails(folder: Path) -> list[str]:
    out: list[str] = []
    for f in sorted(folder.glob("*.toml")):
        with open(f, "rb") as fh:
            value = tomllib.load(fh).get("bewaking", {}).get("email") or []
        for mail in [value] if isinstance(value, str) else value:
            mail = str(mail).strip().lower()
            if mail and mail not in out:
                out.append(mail)
    return out


if __name__ == "__main__":
    print(",".join(emails(Path(sys.argv[1] if len(sys.argv) > 1 else "config/hotels"))))
