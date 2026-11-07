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

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


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


# Niet annuleerbaar tarief: "NRF BREAKFAST EXCL", "Non-refundable", "Niet terugbetaalbaar", "Non remboursable"
_NON_REFUNDABLE = re.compile(r"\bNRF\b|non[- ]?refundable|niet[- ]?terugbetaalbaar|non[- ]?remboursable|nicht erstattbar",
                             re.IGNORECASE)


def rate_plans_from(text: str) -> list[str]:
    """Tarieven uit de kolom Accommodaties van de lijst ("NRF BREAKFAST EXCL, € 335,07") of uit
    folio-lijnen ("Superior double - NRF BREAKFAST EXCL"). Zonder dubbels, in volgorde."""
    # Hoofdletters ("NRF BREAKFAST EXCL") of gewone tekst ("Non-refundable rate including breakfast BDC", zoals
    # Booking.com-tarieven heten)
    found = re.findall(r"(?m)^[ \t]*([A-Za-z][\w &/+.()'-]*?[A-Za-z0-9)])[ \t]*,[ \t]*€", text)
    found += re.findall(r"(?m)[ \t]-[ \t]+([A-Za-z][\w &/+.()'-]*?[A-Za-z0-9)])[ \t]*$", text)
    return list(dict.fromkeys(x.strip() for x in found))


def non_refundable(plans: list[str]) -> bool | None:
    """True als alle tarieven niet annuleerbaar zijn, False als er een annuleerbaar bij is, None = geen tarief."""
    if not plans:
        return None
    return all(_NON_REFUNDABLE.search(p) for p in plans)


def _amount(text: str) -> float:
    """Bedrag zoals Booking.com het schrijft: "362", "638,61", "1054,8" of "1.054,80"."""
    t = text.strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return float(t)


def booking_prepay(remarks: str | None) -> float | None:
    """Bedrag dat Booking.com zelf int en per overschrijving doorstort, uit de opmerking:
    'PrePay:payment_on_Booking.com (Payout type: BankTransfer)362 EUR'. None = geen overschrijving."""
    m = re.search(r"Payout type:\s*Bank\s*Transfer\)\s*([\d.,]+)\s*EUR", remarks or "", re.IGNORECASE)
    return _amount(m.group(1)) if m else None


def booking_collected(remarks: str | None) -> float | None:
    """Bedrag dat Booking.com al geïnd heeft, uit de opmerking: 'Already collected by Booking.com: 362.00 EUR',
    of het bedrag achter een ander uitbetalingstype ('Payout type: VirtualCreditCard)362 EUR').
    Alleen om na te kijken. None = niet vermeld."""
    text = remarks or ""
    m = re.search(r"Already collected by Booking\.com:\s*([\d.,]+)\s*EUR", text, re.IGNORECASE)
    if not m:
        m = re.search(r"Payout type:\s*[^)]*\)\s*([\d.,]+)\s*EUR", text, re.IGNORECASE)
    return _amount(m.group(1)) if m else None


def free_cancel_days(remarks: str | None) -> int | None:
    """Tot hoeveel dagen voor aankomst de gast gratis kan annuleren, uit de annuleringsvoorwaarden
    van Booking.com ('De gast kan gratis annuleren tot 3 dagen voor aankomst'). 0 = nooit gratis
    ('... als hij/zij annuleert op elk moment'). None = niet gevonden."""
    text = remarks or ""
    m = re.search(r"gratis annuleren tot (\d+) dag(?:en)? voor aankomst|cancel free of charge until (\d+) days? before arrival",
                  text, re.IGNORECASE)
    if m:
        return int(m.group(1) or m.group(2))
    if re.search(r"annuleert op elk moment|cancels? at any time", text, re.IGNORECASE):
        return 0
    return None


DOOR_CODE_PREFIX = "Deur Pin code:"


def door_code_line(codes: list[tuple[str, str]]) -> str:
    """Regel bovenaan de opmerking in Lighthouse: "Deur Pin code: 2242" (één kamer) of
    "Deur Pin code: kamer 16: 2242, kamer 21: 9911" (meer kamers)."""
    if len(codes) == 1:
        return f"{DOOR_CODE_PREFIX} {codes[0][1]}"
    return f"{DOOR_CODE_PREFIX} " + ", ".join(f"kamer {room}: {pin}" for room, pin in codes)


# Scheiding tussen onze regel en de rest: een pijp en een nieuwe regel. Lighthouse toont een gewone nieuwe
# regel op de reservatiepagina als een spatie; met de pijp blijft het daar leesbaar ("Deur Pin code: 320 | ..."),
# in het venster Bewerken staat de code op een eigen regel.
SEPARATOR = " |\n"


def with_door_codes(comments: str | None, line: str) -> str:
    """De opmerking met de coderegel bovenaan. De rest blijft precies staan; een vorige coderegel van ons
    (bv. na een kamerwissel) wordt vervangen, niet verdubbeld."""
    rest = comments or ""
    first, _sep, after = rest.lstrip("\n").partition("\n")
    if first.strip().startswith(DOOR_CODE_PREFIX):
        rest = after
    return line + (SEPARATOR + rest if rest else "")


_ROOM_LINE = r"(?m)(?:^|\s)(\d{1,3})[ \t]*-?[ \t]*([A-Z]{3,}(?:[ \t]+[A-Z]{2,})*)[ \t]*$"  # één regel, niet het tarief eronder


def room_names_from(text: str) -> dict[str, str]:
    """Omschrijving van elke toegewezen kamer zoals Lighthouse ze toont: '11 - SUPERIOR DOUBLE ROOM' geeft
    {'11': 'SUPERIOR DOUBLE ROOM'}."""
    return {m.group(1): m.group(2) for m in re.finditer(_ROOM_LINE, text)}


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
    plans = rate_plans_from(accommodations)
    return Reservation(
        hotel_id=hotel_id,
        reservation_id=uuid.group(0).lower(),
        guest=Guest(first_name=first, last_name=last, country=country_code,
                    language=COUNTRY_LANGUAGE.get(country_code or "", "en")),
        arrival=parse_date(arrival_text),
        departure=parse_date(departure_text),
        rooms=rooms_from(accommodations),
        room_names=room_names_from(accommodations),
        status=status_from_pms(f.get("Status", "")),
        source=re.sub(r"\s*\(.*\)\s*$", "", via) or None,
        room_type=room_type,
        rate_plan=", ".join(plans) or None,
        non_refundable=non_refundable(plans),
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
    room_names: dict[str, str] = {}
    room_statuses: list[str] = []
    for r in d.get("rooms", []):
        rooms += [x for x in rooms_from(r.get("text", "")) if x not in rooms]
        room_names.update(room_names_from(r.get("text", "")))
        room_statuses.append((r.get("value") or "").strip())
    status = (ReservationStatus.CANCELLED if "annul" in pms_status.lower()
              else accommodation_status([r.get("status", "") for r in d.get("rooms", [])]))
    paid_text = d.get("paid_text", "").lower()
    folio = parse_folio(d.get("folio_text", "") or d.get("paid_text", ""))
    plans = rate_plans_from("\n".join(x["label"] for x in folio["lines"]))
    # Annuleringsvoorwaarden uit de opmerking (Booking.com) gaan voor op de naam van het tarief
    cancel_days = free_cancel_days(d.get("remarks"))
    refund = (cancel_days == 0) if cancel_days is not None else non_refundable(plans)
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
        room_names=room_names,
        status=status,
        source=_after("Via", general) or None,
        paid=True if "volledig betaald" in paid_text else (False if paid_text else None),
        open_amount=folio["open"],
        rate_plan=", ".join(plans) or None,
        non_refundable=refund,
        remarks=(d.get("remarks") or "").strip() or None,
        internal_memo=None if d.get("internal_memo") is None else (d.get("internal_memo") or "").strip(),
        room_statuses=room_statuses,
        transactions=[t.strip() for t in d.get("transactions", []) if t and t.strip()],
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
    before, _, _after = text.partition("Transacties")
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


BREAKFAST_LABEL = re.compile(r"ontbijt|breakfast|petit[- ]d[ée]jeuner|fr[üu]hst[üu]ck", re.IGNORECASE)


def parse_charge_modal(text: str) -> dict | None:
    """Venster "Bewerken" van een extra in de folio (bv. Ontbijt): kamer, aantal per nacht en de aangevinkte dagen.
    Geeft {"room": "22", "per_night": 1, "days": {"2026-11-06": 1}} of None als er niets bruikbaars in staat.
    De dagen staan als vinkjes met een datum ("06 nov. 2026"); het vinkje "Dagen (1 van 3)" zonder datum telt niet."""
    from html.parser import HTMLParser

    boxes: list[dict] = []  # vinkjes in volgorde: {"checked", "date"}
    selects: list[dict] = []
    texts: list[str] = []

    def as_date(value: str) -> date | None:
        value = (value or "").strip()
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:T.*)?", value)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        try:
            return parse_date(value) if re.search(_DATE, value.lower()) else None
        except (ValueError, KeyError):
            return None

    class P(HTMLParser):
        option: dict | None = None

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "input" and (a.get("type") or "").lower() == "checkbox":
                boxes.append({"checked": "checked" in a, "date": as_date(a.get("value") or "")
                              or as_date(a.get("data-date") or "")})
            elif tag == "select":
                selects.append({"name": a.get("name") or a.get("id") or "", "options": [], "selected": None})
            elif tag == "option" and selects:
                self.option = {"value": a.get("value") or "", "selected": "selected" in a, "text": ""}
                selects[-1]["options"].append(self.option)

        def handle_endtag(self, tag):
            if tag == "option":
                self.option = None

        def handle_data(self, data):
            t = " ".join(data.split())
            if not t:
                return
            texts.append(t)
            if self.option is not None:
                self.option["text"] += t
            if boxes and boxes[-1]["date"] is None and not boxes[-1].get("text"):
                boxes[-1]["text"] = t
                boxes[-1]["date"] = as_date(t)

    P().feed(text)
    per_night = None
    # Het aantal staat in de keuzelijst Amount ("Bedrag per nacht"); andere keuzelijsten (kamer, extra) tellen niet
    amount = [x for x in selects if x["name"].lower() in ("amount", "charge-amount")]
    for s in amount:
        chosen = next((o for o in s["options"] if o["selected"]), None)
        if chosen and re.fullmatch(r"\d+", (chosen["value"] or chosen["text"]).strip()):
            per_night = int((chosen["value"] or chosen["text"]).strip())
            break
    days = sorted(b["date"] for b in boxes if b["checked"] and b["date"])
    if not days:
        return None
    room = next((m.group(1) for t in texts if (m := re.match(r"^(\d{1,3})\s*-?\s*[A-Z]{3,}", t))), None)
    return {"room": room, "per_night": per_night or 1, "days": {d.isoformat(): per_night or 1 for d in days}}


def parse_charge(modal: str, days_json: str) -> dict | None:
    """Venster "Bewerken" (kamer, aantal per nacht) met het antwoord van CalculateDays, dat JSON geeft:
    [{"date": "2026-11-06T00:00:00", "formattedDate": "06 nov. 2026", "isSelected": true}].
    Geeft {"room", "per_night", "days": {"2026-11-06": 1}} of None als er geen gekozen dag is."""
    import json

    try:
        rows = json.loads(days_json)
    except ValueError:
        return parse_charge_modal(modal + days_json)  # toch HTML (zoals het venster het toont)
    chosen = sorted(str(x.get("date") or "")[:10] for x in rows if isinstance(x, dict) and x.get("isSelected"))
    chosen = [d for d in chosen if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)]
    if not chosen:
        return None
    head = parse_charge_modal(modal + "".join(
        f'<input type="checkbox" checked value="{d}">' for d in chosen)) or {}
    per_night = head.get("per_night") or 1
    return {"room": head.get("room"), "per_night": per_night, "days": {d: per_night for d in chosen}}


def charge_days_query(text: str) -> dict | None:
    """Uit het venster "Bewerken": de gegevens waarmee het venster zelf de dagen opvraagt (blok "Dagen",
    /Customer/Folios/CalculateDays). None als het venster geen dagen heeft."""
    m = re.search(r'<div[^>]*id="days-display"[^>]*>', text)
    if not m:
        return None
    attrs = {k.lower(): v for k, v in re.findall(r'(data-[\w-]+)="([^"]*)"', m.group(0))}
    query = {"accommodationId": attrs.get("data-accommodationid"), "extraId": attrs.get("data-extraid"),
             "chargeId": attrs.get("data-chargeid"), "folioMaskId": attrs.get("data-foliomaskid")}
    return query | {"isToFolio": "false"} if all(query.values()) else None


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


def parse_planboard_labels(text: str) -> dict[str, list[str]]:
    """HTML van het planbord: per reservatie de namen van de labels op haar kamers, bv. {"<uuid>": ["ONTBIJT"]}."""
    from html.parser import HTMLParser

    names: dict[str, str] = {}
    ids: dict[str, set[str]] = {}

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if a.get("data-labelid") and a.get("data-labelname"):
                names.setdefault(a["data-labelid"], a["data-labelname"].strip())
            if a.get("data-reservation") and a.get("data-accommodationid"):
                ids.setdefault(a["data-reservation"].lower(), set()).update(
                    x for x in (a.get("data-labelids") or "").split(",") if x)

    P().feed(text)
    return {rid: sorted(names.get(x, x) for x in labels) for rid, labels in ids.items()}


_ROOM_NUMBER = re.compile(r"^\s*(\d{1,4})\b\s*-?\s*(.*)$")


def parse_planboard_stays(text: str) -> dict:
    """HTML van het planbord: alle kamers en per kamer wie er wanneer verblijft. Elke kamer van een reservatie is
    een eigen blok met eigen data (een groep kan kamers met andere data hebben). Geen gastnamen.
    {"units": {unit: {"room": "20", "name": "FAMILY APARTMENT"}},
     "stays": [{"reservation", "accommodation", "unit", "room", "arrival", "departure", "persons", "labels": [naam]}]}
    room = kamernummer (leeg voor een kamer zonder nummer, bv. DUMMY); persons = het getal voor "×" in het blok."""
    from html.parser import HTMLParser

    units: dict[str, dict] = {}
    names: dict[str, str] = {}
    stays: dict[str, dict] = {}

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.unit = ""  # rij tr.unit waarin we zitten (kamernaam)
            self.room_text: list[str] | None = None
            self.block: dict | None = None  # blok waarvan we de tekst lezen (aantal personen)
            self.depth = 0

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            cls = (a.get("class") or "").split()
            if tag == "tr" and "unit" in cls and a.get("data-id"):
                self.unit = a["data-id"]
            if tag == "div" and "roomname" in cls and self.unit:
                self.room_text = []
            if a.get("data-labelid") and a.get("data-labelname"):
                names.setdefault(a["data-labelid"], a["data-labelname"].strip())
            if self.block is not None and tag == "div":
                self.depth += 1
            if "planned-accommodation" in cls and a.get("data-accommodationid") and a.get("data-reservation"):
                acc = a["data-accommodationid"]
                stays.setdefault(acc, {
                    "reservation": a["data-reservation"].lower(), "accommodation": acc, "unit": a.get("data-unit", ""),
                    "arrival": a.get("data-arrival", ""), "departure": a.get("data-departure", ""), "persons": None,
                    "labels": [x for x in (a.get("data-labelids") or "").split(",") if x], "_text": []})
                if tag == "div" and self.block is None:
                    self.block, self.depth = stays[acc], 1

        def handle_endtag(self, tag):
            if tag == "div" and self.room_text is not None:
                name = " ".join(" ".join(self.room_text).split())
                if name:
                    m = _ROOM_NUMBER.match(name)
                    units.setdefault(self.unit, {"room": m.group(1) if m else "",
                                                 "name": (m.group(2) if m else name).strip()})
                self.room_text = None
            if tag == "tr":
                self.unit = ""
            if self.block is not None and tag == "div":
                self.depth -= 1
                if self.depth <= 0:
                    self.block = None

        def handle_data(self, data):
            if self.room_text is not None:
                self.room_text.append(data)
            if self.block is not None:
                self.block["_text"].append(data)

    P().feed(text)
    out = []
    for s in stays.values():
        m = re.search(r"(\d{1,3})\s*[×x]", " ".join(s.pop("_text")))
        s["persons"] = int(m.group(1)) if m else None
        s["labels"] = sorted(names.get(x, x) for x in s["labels"])
        s["room"] = (units.get(s["unit"]) or {}).get("room", "")
        out.append(s)
    return {"units": units, "stays": out}


def parse_planboard(text: str, reservation_id: str) -> dict:
    """HTML van het planbord: de kamers (accommodaties) van één reservatie met hun labels, en de nummers van
    alle labels. {"rooms": [{"accommodation_id", "labels": [id], "unit"}], "names": {naam: id}}."""
    from html.parser import HTMLParser

    rooms: dict[str, dict] = {}
    names: dict[str, str] = {}

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if a.get("data-labelid") and a.get("data-labelname"):
                names.setdefault(a["data-labelname"].strip(), a["data-labelid"])
            if a.get("data-reservation") == reservation_id and a.get("data-accommodationid"):
                acc = a["data-accommodationid"]
                rooms.setdefault(acc, {"accommodation_id": acc, "unit": a.get("data-unit", ""),
                                       "labels": [x for x in (a.get("data-labelids") or "").split(",") if x]})

    P().feed(text)
    return {"rooms": list(rooms.values()), "names": names}


def parse_internal_memo_form(text: str) -> dict | None:
    """HTML van de detailpagina: het blok "Interne memo" (formulier frm-edit-internal-memo).
    {"action", "fields": {naam: waarde} (ID, __RequestVerificationToken, ...), "memo": huidige tekst} of None."""
    import html as _html

    m = re.search(r'<form[^>]*id="frm-edit-internal-memo"[^>]*>(.*?)</form>', text, re.DOTALL)
    if not m:
        return None
    form = m.group(0)
    action = re.search(r'action="([^"]+)"', form)
    fields = {}
    for tag in re.findall(r"<input[^>]*>", form):
        name, value = re.search(r'name="([^"]*)"', tag), re.search(r'value="([^"]*)"', tag)
        if name:
            fields[name.group(1)] = _html.unescape(value.group(1)) if value else ""
    area = re.search(r'<textarea[^>]*name="InternalMemo"[^>]*>(.*?)</textarea>', form, re.DOTALL)
    if area is None:
        return None
    memo = _html.unescape(area.group(1))
    return {"action": _html.unescape(action.group(1)) if action else "", "fields": fields,
            "memo": memo.replace("\r\n", "\n").strip("\n")}
