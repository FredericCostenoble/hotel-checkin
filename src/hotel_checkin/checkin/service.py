"""Bouwblok 9: logica achter het online check-in-formulier.

Het formulier (web/checkin) roept twee API-aanroepen op:
- GET  /api/checkin/<token>  -> form_data(token): gegevens om te tonen
- POST /api/checkin/<token>  -> submit(token, ...): contactgegevens bewaren

De gast herkennen we alleen aan het geheime token in zijn link. Het formulier vraagt alleen
contactgegevens; reservatiegegevens worden alleen-lezen getoond.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.guests import repository as repo
from hotel_checkin.messaging.templates import LANGUAGES, load_hotel_config

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def placeholder_phone(phone: str | None) -> bool:
    """Nepnummer van een boekingssite (bv. Expedia: +11111111111111): na de landcode overal hetzelfde cijfer.
    Zo'n nummer is van niemand: nooit gebruiken om gasten te koppelen of een bericht te sturen."""
    digits = re.sub(r"\D", "", phone or "")
    return len(digits) >= 8 and (len(set(digits)) == 1 or len(set(digits[3:])) == 1)


def normalize_phone(raw: str) -> str | None:
    """Maak een gsm-nummer E.164 (+32...). Belgische nummers mogen met 0 beginnen. None = ongeldig of een
    nepnummer van een boekingssite (placeholder_phone)."""
    s = re.sub(r"[\s.\-/()]", "", raw or "")
    if not s:
        return None
    if s.startswith("00"):
        s = "+" + s[2:]
    elif s.startswith("0"):
        s = "+32" + s[1:]
    return s if re.fullmatch(r"\+\d{8,15}", s) and not placeholder_phone(s) else None


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


def stairs_question(hotel_id: str, room_type: str | None, room_names: list[str] | None = None) -> dict | None:
    """Vraag "moeilijk trappen lopen" voor het formulier, per taal {"nl": {"q", "text"}, ...}, of None als het hotel
    ze niet stelt ([checkin] trappen_vraag_*) of bij dit kamertype niet van kamer kan wisselen ([checkin] trappen_niet_bij,
    bv. appartement of suite)."""
    from hotel_checkin.core.hotels import load_hotel

    c = load_hotel(hotel_id).get("checkin", {})
    out = {lang: {"q": str(c.get(f"trappen_vraag_{lang}") or "").strip(), "text": str(c.get(f"trappen_uitleg_{lang}") or "").strip()}
           for lang in LANGUAGES}
    if not any(v["q"] for v in out.values()):
        return None
    fallback = out.get("en") if out.get("en", {}).get("q") else next(v for v in out.values() if v["q"])
    out = {lang: v if v["q"] else fallback for lang, v in out.items()}
    words = [str(w).lower() for w in (c.get("trappen_niet_bij") or []) if str(w).strip()]
    types = " ".join([room_type or "", *(room_names or [])]).lower()
    if any(w in types for w in words):
        return None
    return out


DEMO_PREFIX = "voorbeeld-"  # link in de voorbeeldmail van de monitor: voorbeeld-<hotel_id>


def _demo(token: str, today: date) -> dict | None:
    """Voorbeeldreservatie voor de link in de voorbeeldmail. Wordt nooit bewaard."""
    from hotel_checkin.core.hotels import list_hotels

    hotel_id = token[len(DEMO_PREFIX):]
    if hotel_id not in list_hotels():
        return None
    arrival = today + timedelta(days=14)
    return {
        "state": "open", "demo": True, "first_name": "Anna", "last_name": "Peeters",
        "arrival": arrival.isoformat(), "departure": (arrival + timedelta(days=2)).isoformat(),
        "room_type": "Superior Double Room", "email": "anna.peeters@example.com", "phone": "", "country": "BE",
        "backup_email": "", "backup_phone": "", "language": "nl", "completed": False, "no_marketing": False,
        "hotel": hotel_info(hotel_id, "nl"), "stairs": stairs_question(hotel_id, "Superior Double Room"),
        "stairs_help": False,
    }


def form_data(token: str, today: date | None = None) -> dict | None:
    """None als het token onbekend is. state: open, cancelled of closed."""
    if token.startswith(DEMO_PREFIX):
        return _demo(token, today or date.today())
    r = repo.get_by_token(token) if token else None
    if r is None:
        return None
    from hotel_checkin.core import clock

    today = today or clock.today(r.hotel_id)
    if r.status == ReservationStatus.CANCELLED:
        state = "cancelled"
    elif r.departure < today:
        state = "closed"
    else:
        state = "open"
    from hotel_checkin.core.addresses import is_own_email

    email = r.guest.email or ""
    # Doorstuuradres van Booking.com, Expedia, ... niet voorstellen: de gast vult zijn eigen adres in
    shown = email if is_own_email(email) else ""
    return {
        "state": state,
        "first_name": r.guest.first_name,
        "last_name": r.guest.last_name,
        "arrival": r.arrival.isoformat(),
        "departure": r.departure.isoformat(),
        "room_type": r.room_type or "",
        "rooms": list(r.rooms),
        "email": shown,
        "phone": r.guest.phone or "",
        "country": r.guest.country or "",
        "backup_email": r.guest.backup_email or "",
        "backup_phone": r.guest.backup_phone or "",
        "language": r.guest.language,
        "completed": r.checkin_completed_at is not None,
        "no_marketing": repo.is_opted_out(r.hotel_id, email) if email else False,
        "hotel": hotel_info(r.hotel_id, r.guest.language),
        "stairs": stairs_question(r.hotel_id, r.room_type, list(r.room_names.values())),
        "stairs_help": bool(r.stairs_help),
    }


def submit(token: str, form: dict) -> tuple[bool, dict]:
    """Bewaar de contactgegevens uit het formulier. Geeft (ok, fouten) terug.

    form: email, phone, backup_email, backup_phone, language, no_marketing, stairs_help (alleen als de vraag er stond).
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
    if data.get("demo"):  # voorbeeld: alles gecontroleerd, niets bewaard
        return True, {}

    stairs = bool(form.get("stairs_help")) if data.get("stairs") else None  # alleen als de vraag op het formulier stond
    r = repo.get_by_token(token)
    # Eerst de indiening zelf bewaren (vangnet): wat de gast invulde, gaat nooit verloren
    repo.save_form_submission(r.hotel_id, r.reservation_id, {
        "email": email, "phone": phones["phone"], "backup_email": backup_email or None,
        "backup_phone": phones["backup_phone"], "language": language, "no_marketing": bool(form.get("no_marketing")),
        **({"stairs_help": stairs} if stairs is not None else {})})
    if form.get("no_marketing"):
        repo.add_opt_out(r.hotel_id, email, "checkin_form")
    saved = repo.mark_checkin_completed(
        r.hotel_id, r.reservation_id, email, phones["phone"], language,
        backup_email=backup_email or None, backup_phone=phones["backup_phone"], stairs_help=stairs,
    )
    # In het berichtenlog van de reservatie, zodat het in de monitor zichtbaar is
    from hotel_checkin.core.models import Channel, SendResult

    repo.log_message(r.hotel_id, r.reservation_id, "checkin_form",
                     SendResult(Channel.FORM, email, True), note="check-in-formulier ingevuld door de gast")
    # De gast gaf zelf zijn gegevens: die gaan voor in het gastprofiel (en kunnen profielen samenbrengen)
    try:
        from hotel_checkin.processes import guest_profiles

        if saved is not None:
            guest_profiles.link(saved)
    except Exception:
        import logging

        logging.exception("gastprofiel niet bijgewerkt")
    return True, {}


def reapply_forms(hotel_id: str) -> int:
    """Vangnet: elke indiening van het formulier moet in de reservatie staan. Staat ze er niet (meer)
    in, bv. door een fout bij het bijwerken, dan opnieuw toepassen. Geeft het aantal herstelde terug."""
    from datetime import datetime

    fixed = 0
    for f in repo.all_form_submissions(hotel_id):
        r = repo.get_reservation(hotel_id, f["reservation_id"]) if "reservation_id" in f else None
        if r is None:
            continue
        submitted = datetime.fromisoformat(f["submitted_at"])
        if r.checkin_completed_at and r.checkin_completed_at >= submitted and (r.guest.email or "") == (f.get("email") or ""):
            continue
        repo.mark_checkin_completed(hotel_id, r.reservation_id, f.get("email"), f.get("phone"), f.get("language"),
                                    backup_email=f.get("backup_email"), backup_phone=f.get("backup_phone"),
                                    stairs_help=f.get("stairs_help"))
        fixed += 1
    return fixed
