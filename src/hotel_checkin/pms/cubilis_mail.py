"""Bouwblok: een meldingsmail van Lighthouse/Cubilis herkennen (nieuwe, gewijzigde of geannuleerde
reservatie). Alleen tekst omzetten: geen mailbox, geen browser, geen beslissingen.

Lighthouse stuurt de meldingen via Cubilis (channel manager) naar info@ van het hotel; een regel
in die mailbox stuurt ze door naar checkin@ (afzender blijft Cubilis). Voorbeeld:

    Onderwerp: Nieuwe reservering bij Lucca Hotel - Brugge (61978386)
    Reserveringsnummer: 61978386,
    Gemaakt door <naam> op 30 oktober 2026 11:16.
    Aankomst:  maandag 2 november 2026
    Vertrek:   dinsdag 3 november 2026

Let op: het nummer is het Cubilis-nummer, niet het Lighthouse-nummer (CPB-...).
Ook Engelse meldingen ("New reservation via ...", "Cancelled reservation via ...").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from hotel_checkin.pms.lighthouse_parse import parse_date

SENDER_DOMAINS = ("cubilis.com", "cubilis.eu")

_KINDS = (  # volgorde telt: "geannuleerd" voor "reservering"
    ("cancelled", r"annul|cancel"),
    ("modified", r"wijzig|modif|changed|updated|aangepast"),
    ("new", r"nieuw|new reservation|nouvelle"),
)


@dataclass
class ReservationNotice:
    kind: str  # new, modified, cancelled
    number: str | None  # Cubilis-nummer
    arrival: date | None = None
    departure: date | None = None
    channel: str | None = None  # bv. Booking.com (uit "via ..."), als vermeld


def _strip_forward(subject: str) -> str:
    return re.sub(r"^\s*((fw|fwd|tr|wg|re)\s*:\s*)+", "", subject, flags=re.I).strip()


def is_from_cubilis(sender: str, text: str = "") -> bool:
    """Rechtstreeks van Cubilis, of met de hand doorgestuurd (dan staat Cubilis in de tekst)."""
    if any(sender.lower().endswith("@" + d) for d in SENDER_DOMAINS):
        return True
    return bool(re.search(r"^\s*(From|Van|De|Von):\s*Cubilis", text, re.I | re.M))


def _date_after(label: str, text: str) -> date | None:
    m = re.search(rf"{label}\s*:?\s*\n?\s*\n?\s*([^\n]+)", text, re.I)
    if not m:
        return None
    try:
        return parse_date(m.group(1))
    except (ValueError, KeyError):
        return None


def parse_notice(sender: str, subject: str, text: str) -> ReservationNotice | None:
    """Melding van Cubilis naar ReservationNotice, of None als het geen reservatiemelding is."""
    if not is_from_cubilis(sender, text):
        return None
    subj = _strip_forward(subject)
    kind = next((k for k, pattern in _KINDS if re.search(pattern, subj, re.I)), None)
    if kind is None or not re.search(r"reserv|booking", subj, re.I):
        return None
    number = re.search(r"\((\d{5,})\)", subj) or re.search(
        r"(?:Reserveringsnummer|Reservation number|Numéro de réservation)\s*:?\s*(\d{5,})", text, re.I)
    channel = re.search(r"\bvia\s+(.+?)(?:\s*\(|\s+-\s+|$)", subj, re.I)
    # In een doorgestuurde mail staat de originele tekst na de doorstuurkop
    body = text.split("Subject:", 1)[-1] if "Subject:" in text else text
    return ReservationNotice(
        kind=kind,
        number=number.group(1) if number else None,
        arrival=_date_after(r"(?:Aankomst|Arrival|Arrivée)", body),
        departure=_date_after(r"(?:Vertrek|Departure|Départ)", body),
        channel=channel.group(1).strip() if channel else None,
    )
