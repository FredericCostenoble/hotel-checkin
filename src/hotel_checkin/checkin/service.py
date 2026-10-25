"""Bouwblok 9: logica achter het online check-in-formulier.

Het formulier (web/checkin) roept twee API-aanroepen op:
- GET  /api/checkin/<token>  -> form_data(token): gegevens om te tonen
- POST /api/checkin/<token>  -> submit(token, ...): contactgegevens bewaren

De gast herkennen we alleen aan het geheime token in zijn link. Het formulier vraagt alleen
contactgegevens; reservatiegegevens worden alleen-lezen getoond.
"""

from __future__ import annotations

import re
from datetime import date

from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.guests import repository as repo
from hotel_checkin.messaging.templates import LANGUAGES, load_hotel_config

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def normalize_phone(raw: str) -> str | None:
    """Maak een gsm-nummer E.164 (+32...). Belgische nummers mogen met 0 beginnen. None = ongeldig."""
    s = re.sub(r"[\s.\-/()]", "", raw or "")
    if not s:
        return None
    if s.startswith("00"):
        s = "+" + s[2:]
    elif s.startswith("0"):
        s = "+32" + s[1:]
    return s if re.fullmatch(r"\+\d{8,15}", s) else None


def hotel_info(hotel_id: str, language: str) -> dict:
    """Hotelgegevens voor de pagina (logo, adres, kleuren, privacylink), uit config/hotels/<hotel_id>.toml."""
    c = load_hotel_config(hotel_id)
    lang = language if language in LANGUAGES else "en"
    return {
        "name": c["hotel"]["naam"],
        "address": c["hotel"]["adres"],
        "phone": c["hotel"]["telefoon"],
        "email": c["hotel"]["email"],
        "website": c["hotel"]["website"],
        "logo_url": c["hotel"]["logo_url"],
        "privacy_url": c["privacy"][f"url_{lang}"],
        "privacy_urls": {k[4:]: v for k, v in c["privacy"].items() if k.startswith("url_")},
        "colors": c["kleuren"],
    }


def form_data(token: str, today: date | None = None) -> dict | None:
    """None als het token onbekend is. state: open, cancelled of closed."""
    r = repo.get_by_token(token) if token else None
    if r is None:
        return None
    today = today or date.today()
    if r.status == ReservationStatus.CANCELLED:
        state = "cancelled"
    elif r.departure < today:
        state = "closed"
    else:
        state = "open"
    email = r.guest.email or ""
    return {
        "state": state,
        "first_name": r.guest.first_name,
        "last_name": r.guest.last_name,
        "arrival": r.arrival.isoformat(),
        "departure": r.departure.isoformat(),
        "room_type": r.room_type or "",
        "email": email,
        "phone": r.guest.phone or "",
        "country": r.guest.country or "",
        "backup_email": r.guest.backup_email or "",
        "backup_phone": r.guest.backup_phone or "",
        "language": r.guest.language,
        "completed": r.checkin_completed_at is not None,
        "no_marketing": repo.is_opted_out(r.hotel_id, email) if email else False,
        "hotel": hotel_info(r.hotel_id, r.guest.language),
    }


def submit(token: str, form: dict) -> tuple[bool, dict]:
    """Bewaar de contactgegevens uit het formulier. Geeft (ok, fouten) terug.

    form: email, phone, backup_email, backup_phone, language, no_marketing.
    Telefoonnummers komen normaal al in +-formaat van het formulier (landkeuze + nummer).
    """
    data = form_data(token)
    if data is None:
        return False, {"token": "not_found"}
    if data["state"] != "open":
        return False, {"state": data["state"]}

    def text(key: str) -> str:
        return str(form.get(key) or "").strip()

    errors: dict[str, str] = {}
    email = text("email").lower()
    if not EMAIL_RE.match(email):
        errors["email"] = "invalid"
    backup_email = text("backup_email").lower()
    if backup_email and not EMAIL_RE.match(backup_email):
        errors["backup_email"] = "invalid"

    phones: dict[str, str | None] = {}
    for key in ("phone", "backup_phone"):
        phones[key] = None
        if text(key):
            phones[key] = normalize_phone(text(key))
            if phones[key] is None:
                errors[key] = "invalid"

    language = text("language")
    if language not in LANGUAGES:
        language = data["language"]
    if errors:
        return False, errors

    r = repo.get_by_token(token)
    if form.get("no_marketing"):
        repo.add_opt_out(r.hotel_id, email, "checkin_form")
    repo.mark_checkin_completed(
        r.hotel_id, r.reservation_id, email, phones["phone"], language,
        backup_email=backup_email or None, backup_phone=phones["backup_phone"],
    )
    return True, {}
