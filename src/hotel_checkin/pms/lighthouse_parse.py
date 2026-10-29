"""Tekst van Lighthouse-pagina's omzetten naar gegevens (zonder browser, dus apart te testen).

Lighthouse toont alles in het Nederlands (taal van de robotgebruiker), bv.:
    Gemaakt op 29 okt. 2026 15:44
    Verblijf donderdag, 22 apr. 2027 - zaterdag, 24 apr. 2027 (2 Nachten)
"""

from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from hotel_checkin.core.models import Guest, Reservation, ReservationStatus

TZ = ZoneInfo("Europe/Brussels")

MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "maa": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}
_DATE = r"(\d{1,2})\s+([a-z]{3})[a-z]*\.?\s+(\d{4})"
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def parse_date(text: str) -> date:
    m = re.search(_DATE, text.lower())
    if not m:
        raise ValueError(f"Geen datum gevonden in {text!r}")
    return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))


def parse_datetime(text: str) -> datetime:
    d = parse_date(text)
    m = re.search(r"(\d{1,2}):(\d{2})", text)
    hour, minute = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=TZ)


def _fields(text: str) -> dict[str, str]:
    """Regels 'Label Waarde' uit de kolom Algemene informatie."""
    labels = ("ID", "Status", "Via", "Type reis", "Gemaakt op", "Aantal gasten",
              "Aantal accommodaties", "Verblijf", "Verwacht om")
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        for label in labels:
            if line.startswith(label + " ") or line.startswith(label + "\t"):
                out[label] = line[len(label):].strip()
    return out


def status_from_pms(pms_status: str) -> ReservationStatus:
    return ReservationStatus.CANCELLED if "annul" in pms_status.lower() else ReservationStatus.READY_FOR_CHECKIN


def split_name(full_name: str) -> tuple[str, str]:
    """Lighthouse toont "Voornaam Achternaam" (soms in hoofdletters). Achternaam = laatste woord(en) na de eerste."""
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return "", parts[0]
    return parts[0], " ".join(parts[1:])


def rooms_from(text: str) -> list[str]:
    """Toegewezen kamers, bv. '30 DOUBLE ROOM' of '11 - SUPERIOR DOUBLE ROOM' geeft ['30'] en ['11']."""
    return re.findall(r"(?m)(?:^|\s)(\d{1,3})\s*-?\s*[A-Z]{3,}(?:\s+[A-Z]{2,})*\s*$", text)


def parse_list_row(hotel_id: str, general: str, contact: str, accommodations: str, detail_href: str) -> Reservation:
    """Een rij uit Reserveringen > Overzicht."""
    f = _fields(general)
    uuid = _UUID.search(detail_href or "")
    if not uuid:
        raise ValueError("Geen link naar de reservatie gevonden")
    arrival_text, _, departure_text = f.get("Verblijf", "").partition(" - ")
    first, last = split_name(contact.strip().splitlines()[0] if contact.strip() else "")
    via = f.get("Via", "")
    first_line = accommodations.strip().splitlines()[0] if accommodations.strip() else ""
    room_type = re.split(r"\s{2,}|\t|!", first_line)[0].strip() or None
    guests = re.search(r"\d+", f.get("Aantal gasten", ""))
    return Reservation(
        hotel_id=hotel_id,
        reservation_id=uuid.group(0).lower(),
        guest=Guest(first_name=first, last_name=last),
        arrival=parse_date(arrival_text),
        departure=parse_date(departure_text),
        rooms=rooms_from(accommodations),
        status=status_from_pms(f.get("Status", "")),
        source=re.sub(r"\s*\(.*\)\s*$", "", via) or None,
        room_type=room_type,
        booking_number=f.get("ID") or None,
        pms_status=f.get("Status") or None,
        guest_count=int(guests.group(0)) if guests else None,
        booked_at=parse_datetime(f["Gemaakt op"]) if f.get("Gemaakt op") else None,
    )
