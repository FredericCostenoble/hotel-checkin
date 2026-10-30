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
    "mar": 3, "may": 5, "oct": 10,  # Engels (bv. meldingen van Cubilis)
}
_DATE = r"(\d{1,2})\s+([a-z]{3})[a-z]*\.?\s+(\d{4})"
# Taal afleiden uit het land (Lighthouse toont de taal niet op de detailpagina). De gast kan
# ze zelf aanpassen in het check-in-formulier.
COUNTRY_LANGUAGE = {
    "NL": "nl", "BE": "nl", "SR": "nl",
    "FR": "fr", "LU": "fr", "MC": "fr",
    "DE": "de", "AT": "de", "LI": "de", "CH": "de",
}

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
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        for label in labels:
            if line == label and i + 1 < len(lines):
                # Label en waarde op aparte regels
                out[label] = lines[i + 1]
            elif line.startswith(label):
                # Met of zonder spatie: in de headless browser plakken label en waarde soms aan
                # elkaar ("IDCPB-4276-002731", "Verblijfdonderdag, ...")
                out[label] = line[len(label):].lstrip(" :\t")
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
        raise ValueError(f"geen link naar de reservatie (velden: {', '.join(f) or 'geen'})")
    if " - " not in f.get("Verblijf", ""):
        raise ValueError(f"geen verblijfsdata (velden: {', '.join(f) or 'geen'})")
    arrival_text, _, departure_text = f.get("Verblijf", "").partition(" - ")
    contact_line = contact.strip().splitlines()[0] if contact.strip() else ""
    country = re.search(r"\(([A-Z]{2})\)", contact)
    country_code = country.group(1) if country else None
    first, last = split_name(re.sub(r"\s*\([A-Z]{2}\)\s*", " ", contact_line))
    via = f.get("Via", "")
    first_line = accommodations.strip().splitlines()[0] if accommodations.strip() else ""
    room_type = re.split(r"\s{2,}|\t|!", first_line)[0].strip() or None
    guests = re.search(r"\d+", f.get("Aantal gasten", ""))
    return Reservation(
        hotel_id=hotel_id,
        reservation_id=uuid.group(0).lower(),
        guest=Guest(first_name=first, last_name=last, country=country_code,
                    language=COUNTRY_LANGUAGE.get(country_code or "", "en")),
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


# ---------------------------------------------------------------- detailpagina



def _after(label: str, text: str) -> str:
    m = re.search(rf"(?m)^\s*{re.escape(label)}\s*:?\s*(.+)$", text)
    return m.group(1).strip() if m else ""


def accommodation_status(statuses: list[str]) -> ReservationStatus:
    """Status per kamer (KLAAR OM IN TE CHECKEN / INGECHECKT / UITGECHECKT) naar één status."""
    s = [x.upper() for x in statuses if x and x != "-"]
    if s and all(x == "UITGECHECKT" for x in s):
        return ReservationStatus.CHECKED_OUT
    if s and all(x in ("INGECHECKT", "UITGECHECKT") for x in s):
        return ReservationStatus.CHECKED_IN
    return ReservationStatus.READY_FOR_CHECKIN


def parse_detail(hotel_id: str, reservation_id: str, d: dict) -> Reservation:
    """Gegevens van de detailpagina (zie lighthouse.py, _read_detail) naar een Reservation.

    d: title, contact_name, contact_line, phone, email, general (tekst blok Algemene informatie),
       rooms (lijst van {status, text}), paid_text (tekst blok Transacties).
    """
    from hotel_checkin.checkin.service import normalize_phone

    general = d.get("general", "")
    pms_status = _after("Status", general)
    country = re.search(r"\(([A-Z]{2})\)", d.get("contact_line", ""))
    country_code = country.group(1) if country else None
    first, last = split_name(d.get("contact_name", ""))
    email = (d.get("email") or "").strip().lower()
    arrival_line = _after("Aankomst op", general)
    departure_line = _after("Vertrek op", general)
    booked_line = _after("Gemaakt op", general)
    number = re.search(r"[A-Z]{2,5}-\d+-\d+", d.get("title", ""))
    rooms: list[str] = []
    for r in d.get("rooms", []):
        rooms += [x for x in rooms_from(r.get("text", "")) if x not in rooms]
    status = (ReservationStatus.CANCELLED if "annul" in pms_status.lower()
              else accommodation_status([r.get("status", "") for r in d.get("rooms", [])]))
    paid_text = d.get("paid_text", "").lower()
    folio = parse_folio(d.get("folio_text", "") or d.get("paid_text", ""))
    return Reservation(
        hotel_id=hotel_id,
        reservation_id=reservation_id.lower(),
        guest=Guest(
            first_name=first,
            last_name=last,
            email=email if "@" in email else None,
            phone=normalize_phone(d.get("phone") or ""),
            language=COUNTRY_LANGUAGE.get(country_code or "", "en"),
            country=country_code,
        ),
        arrival=parse_date(arrival_line),
        departure=parse_date(departure_line),
        rooms=rooms,
        status=status,
        source=_after("Via", general) or None,
        paid=True if "volledig betaald" in paid_text else (False if paid_text else None),
        open_amount=folio["open"],
        folio=folio["lines"],
        folio_total=folio["total"],
        booking_number=number.group(0) if number else None,
        pms_status=pms_status or None,
        booked_at=parse_datetime(booked_line) if booked_line else None,
    )


_EURO = re.compile(r"€\s*(-?[\d.]+,\d{2})")
_FOLIO_SKIP = ("extra toevoegen", "folio sluiten", "factuur maken", "toevoegen")


def _euro(text: str) -> float:
    return float(text.replace(".", "").replace(",", "."))


def parse_folio(text: str) -> dict:
    """Folio van de detailpagina: lijnen (kamer, toeristenbelasting, extra's), totaal en openstaand saldo.

    Links staan de lijnen ("Quad kamer - STANDARD RATE ... € 215,00", "Citytax 4 x € 16,80",
    "Totaal € 231,80"), rechts de transacties met "Openstaand saldo van € 231,80" of "volledig betaald".
    Bedrag en omschrijving mogen op dezelfde regel (tabel) of op opeenvolgende regels staan.
    Geeft {"lines": [{"label", "qty", "amount"}], "total": float|None, "open": float|None}.
    """
    before, _, after = text.partition("Transacties")
    out: dict = {"lines": [], "total": None, "open": None}
    opened = re.search(r"Openstaand saldo van\s*€\s*(-?[\d.]+,\d{2})", text)
    if opened:
        out["open"] = _euro(opened.group(1))
    elif "volledig betaald" in text.lower():
        out["open"] = 0.0
    pending, pending_qty, total_next = "", None, False
    for raw in before.splitlines():
        line = " ".join(raw.replace("\t", " ").split())
        if not line or line.lower() in _FOLIO_SKIP:
            continue
        amounts = _EURO.findall(line)
        label = _EURO.split(line)[0].strip()
        if label.lower().startswith("totaal") or total_next:
            if amounts:
                out["total"], total_next = _euro(amounts[-1]), False
            else:
                total_next = True
            continue
        only_qty = re.fullmatch(r"(\d+)\s*[x×]", line)
        if only_qty:  # aantal op een eigen regel, bij de omschrijving erboven
            pending_qty = int(only_qty.group(1))
            continue
        if not amounts:
            pending, pending_qty = line, None
            continue
        qty = re.search(r"(\d+)\s*[x×]\s*$", label)
        if qty:
            label = label[:qty.start()].strip()
        out["lines"].append({"label": label or pending, "qty": int(qty.group(1)) if qty else pending_qty,
                             "amount": _euro(amounts[-1])})
        pending, pending_qty = "", None
    return out


def parse_contact(text: str) -> dict | None:
    """Antwoord van /Customer/Reservations/ContactDetails/{id} (wat het oog-icoon ophaalt) naar
    {"email", "phone"}. JSON of HTML; None als er geen bruikbare gegevens in staan."""
    import json

    email = phone = ""
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if data is not None:
        def walk(x, key=""):
            nonlocal email, phone
            if isinstance(x, dict):
                for k, v in x.items():
                    walk(v, k.lower())
            elif isinstance(x, list):
                for v in x:
                    walk(v, key)
            elif isinstance(x, str):
                if not email and _EMAIL.fullmatch(x.strip()):
                    email = x.strip()
                elif not phone and any(w in key for w in ("phone", "tel", "gsm", "mobile")):
                    phone = x.strip()
        walk(data)
    else:
        m = re.search(r'data-field="telephone"[^>]*>([^<]*)<', text)
        phone = m.group(1).strip() if m else ""
        m = re.search(r'data-field="email"[^>]*>([^<]*)<', text) or _EMAIL.search(text)
        email = (m.group(1) if m.groups() else m.group(0)).strip() if m else ""
    if "*" in email + phone:
        return None  # nog gemaskeerd
    from hotel_checkin.checkin.service import normalize_phone

    out = {"email": email.lower() if _EMAIL.fullmatch(email) else None, "phone": normalize_phone(phone)}
    return out if out["email"] or out["phone"] else None


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
