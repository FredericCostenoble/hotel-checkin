"""Bouwblok 9: logica achter het online check-in-formulier.

Het formulier (web/checkin) roept twee API-aanroepen op:
- GET  /api/checkin/<token>  -> form_data(token): gegevens om te tonen
- POST /api/checkin/<token>  -> submit(token, ...): contactgegevens bewaren

De gast herkennen we alleen aan het geheime token in zijn link. Het formulier vraagt alleen
contactgegevens; reservatiegegevens worden alleen-lezen getoond.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

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
        "favicon_url": c["hotel"].get("favicon_url", ""),
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
# Voorbeeld in een bepaalde fase, om de gast-app te bekijken: voorbeeld-<hotel_id>.<variant>
DEMO_VARIANTS = ("before", "done", "unpaid", "code", "stay", "after", "rooms")
STAY_PAGE_DAYS = 14  # zo lang na vertrek toont de app nog de bedankpagina (review, betalen), daarna "afgelopen"


def _now(hotel_id: str) -> datetime:
    from hotel_checkin.core import clock

    return datetime.now(clock.tz(hotel_id))


def _times(hotel_id: str) -> dict:
    """Uren uit het hotelbestand: check-in (receptie van), check-out, receptie en ontbijt."""
    from hotel_checkin.core.hotels import load_hotel

    c = load_hotel(hotel_id)
    rec, co, br = c.get("receptie", {}), c.get("checkout", {}), c.get("ontbijt", {})
    return {"checkin_from": rec.get("van", ""), "checkout_until": co.get("tot", ""),
            "front_door_until": co.get("voordeur_tot", ""),
            "reception_from": rec.get("van", ""), "reception_until": rec.get("tot", ""),
            "breakfast_from": br.get("van", ""), "breakfast_until": br.get("tot", "")}


def _wifi(hotel_id: str) -> dict | None:
    """Wifi: per kamer (QR-code op de kamer) of één netwerk voor iedereen ([wifi]). None = niets tonen."""
    from hotel_checkin.core.hotels import load_hotel

    w = load_hotel(hotel_id).get("wifi", {})
    if w.get("per_kamer", True):
        return {"per_room": True}
    if not str(w.get("naam") or "").strip():
        return None
    return {"per_room": False, "name": w.get("naam", ""), "password": w.get("wachtwoord", "")}


def _rooms(hotel_id: str, rooms: list[str]) -> list[dict]:
    """Per kamer: verdieping, eigen naam en uitleg over een eigen ingang, in alle talen (de gast kan wisselen)."""
    from hotel_checkin.processes import guest_unlock
    from hotel_checkin.processes.send_messages import room_info

    out = []
    for room in rooms:
        per_lang = {lang: room_info(hotel_id, room, lang) for lang in LANGUAGES}
        out.append({"room": room, "floor": per_lang["en"]["floor"],
                    "name": {lang: v["name"] for lang, v in per_lang.items()},
                    "access": {lang: v["access"] for lang, v in per_lang.items()},
                    "own_entrance": guest_unlock.own_entrance(hotel_id, room)})
    return out


def _code_date(hotel_id: str, r) -> date | None:
    """Dag waarop de code-mail (en dus de code in de app) volgt volgens de workflow van deze reservatie."""
    from hotel_checkin.core import workflow

    for s in workflow.steps_for(hotel_id, r):
        if s.step == "access_code" and s.enabled:
            return s.due_date(r)
    return None


def phase(hotel_id: str, r, now: datetime) -> str:
    """Fase van het verblijf voor de app: before (voor de code), code (code klaar, nog niet aangekomen),
    stay (van check-in tot check-out) of after (na de check-out)."""
    from hotel_checkin.core import workflow
    from hotel_checkin.processes import grant_access

    if now >= grant_access.checkout_at(hotel_id, r):
        return "after"
    if now >= grant_access.period(hotel_id, r)[0]:
        return "stay"
    if r.access_codes and workflow.room_paid(r):
        return "code"
    return "before"


def pay_info(r) -> dict | None:
    """Openstaand bedrag volgens Lighthouse (folio), met de betaallink als die er is (processes/pay_requests.py).
    None = nog niet gekend (folio nog niet gelezen). kind: city_tax (kamer betaald, alleen de toeristenbelasting
    staat open) of balance; paid: niets meer open."""
    if r.open_amount is None:
        return None
    from hotel_checkin.core import workflow
    from hotel_checkin.processes.send_messages import money

    params = workflow.config(r.hotel_id)["parameters"]
    currency = params["currency"]
    open_amount = max(0.0, float(r.open_amount))
    paid = r.paid is True or open_amount <= 0.004
    out = {"open": round(open_amount, 2), "amount": money(open_amount, currency), "paid": paid,
           "url": None if paid else (r.pay_link or None),
           "kind": "city_tax" if not paid and workflow.room_paid(r) else "balance", "tax": None}
    nights = (r.departure - r.arrival).days
    if out["kind"] == "city_tax" and r.guest_count and params.get("city_tax_unit") == "person_night":
        rate = float(params["city_tax_amount"])
        if abs(rate * r.guest_count * nights - open_amount) < 0.01:
            out["tax"] = {"persons": r.guest_count, "nights": nights, "rate": money(rate, currency)}
    return out


def _access(hotel_id: str, r, completed: bool, now: datetime, ph: str) -> dict:
    """Toegang voor de app. De pincodes alleen als de gast zijn gegevens invulde, de kamer betaald is en er een
    code bij Salto is (de code-mail is dan ook vertrokken). Ontgrendelen alleen als dat mag (processes/guest_unlock.py)."""
    from hotel_checkin.core import workflow
    from hotel_checkin.processes import guest_unlock

    room_paid = workflow.room_paid(r)
    code_day = _code_date(hotel_id, r)
    out = {"room_paid": room_paid, "code_date": code_day.isoformat() if code_day else None,
           "front_door": guest_unlock.has_front_door(hotel_id, r), "codes": [], "unlock": None}
    if not (completed and room_paid and r.access_codes and ph in ("code", "stay")):
        return out
    out["codes"] = [{"room": c["room"], "pin": c["pin"]} for c in r.access_codes if c.get("pin")]
    if guest_unlock.allowed(hotel_id, r):
        out["unlock"] = {d: {"from": a.isoformat(), "until": b.isoformat()}
                         for d in guest_unlock.doors(hotel_id, r)
                         for a, b in [guest_unlock.window(hotel_id, r, d)]}
    return out


def _hotel_extra(hotel_id: str) -> dict:
    from urllib.parse import quote

    from hotel_checkin.core.hotels import load_hotel

    c = load_hotel(hotel_id)
    h = c["hotel"]
    digits = re.sub(r"\D", "", h.get("telefoon", ""))
    return {"whatsapp": f"https://wa.me/{digits}" if digits else "",
            "map_url": "https://www.google.com/maps/search/?api=1&query=" + quote(f"{h['naam']}, {h['adres']}"),
            "review_url": c.get("reviews", {}).get("google_url", "") or c.get("reviews", {}).get("other_url", "")}


def _demo(token: str, now: datetime) -> dict | None:
    """Voorbeeldreservatie voor de link in de voorbeeldmail (voorbeeld-<hotel_id>), of een fase van de gast-app
    (voorbeeld-<hotel_id>.<variant>, zie DEMO_VARIANTS). Wordt nooit bewaard; ontgrendelen doet niets."""
    from hotel_checkin.core.hotels import list_hotels

    hotel_id, _, variant = token[len(DEMO_PREFIX):].partition(".")
    if hotel_id not in list_hotels() or (variant and variant not in DEMO_VARIANTS):
        return None
    today = now.date()
    arrival = {"code": today + timedelta(days=1), "unpaid": today + timedelta(days=1), "stay": today, "after": today - timedelta(days=2)}.get(
        variant, today + timedelta(days=14))
    departure = arrival + timedelta(days=2)
    rooms = ["16", "21"] if variant == "rooms" else ["16"]
    completed = variant not in ("", "before")
    tz = now.tzinfo
    t = _times(hotel_id)
    start = datetime.combine(arrival, datetime.strptime(t["checkin_from"] or "14:00", "%H:%M").time(), tzinfo=tz)
    end = datetime.combine(departure, datetime.strptime(t["checkout_until"] or "11:00", "%H:%M").time(), tzinfo=tz)
    ph = {"code": "code", "stay": "stay", "rooms": "stay", "after": "after"}.get(variant, "before")
    if variant == "stay" and now < start:  # vandaag aangekomen, maar het is nog geen check-in-uur
        start = now - timedelta(hours=1)
    paid = variant != "unpaid"
    codes = [{"room": x, "pin": p} for x, p in zip(rooms, ("2242", "7305"))] if ph in ("code", "stay") else []
    doors = (["front"] + [f"room:{x}" for x in rooms])
    return {
        "state": "open", "demo": True, "phase": ph, "first_name": "Anna", "last_name": "Peeters",
        "arrival": arrival.isoformat(), "departure": departure.isoformat(), "guest_count": 2, "nights": 2,
        "room_type": "Superior Double Room", "rooms": _rooms(hotel_id, rooms),
        "email": "anna.peeters@example.com", "phone": "+32470123456" if completed else "", "country": "BE",
        "backup_email": "", "backup_phone": "", "language": "nl", "completed": completed, "no_marketing": False,
        "hotel": {**hotel_info(hotel_id, "nl"), **_hotel_extra(hotel_id)}, "times": t, "wifi": _wifi(hotel_id),
        "stairs": stairs_question(hotel_id, "Superior Double Room"), "stairs_help": False,
        "pay": ({"open": 16.8, "amount": "\u20ac\u00a016,80", "paid": False, "url": "#", "kind": "city_tax",
                 "tax": {"persons": 2, "nights": 2, "rate": "\u20ac\u00a04,20"}} if paid else
                {"open": 236.8, "amount": "\u20ac\u00a0236,80", "paid": False, "url": "#", "kind": "balance", "tax": None}),
        "access": {"room_paid": paid, "code_date": (arrival - timedelta(days=2)).isoformat(), "front_door": True,
                   "codes": codes,
                   "unlock": ({d: {"from": start.isoformat(), "until": end.isoformat()} for d in doors}
                              if codes else None)},
    }


def form_data(token: str, today: date | None = None, now: datetime | None = None, visit: bool = False) -> dict | None:
    """Alles voor de gast-app. None als het token onbekend is. state: open, cancelled of closed; phase: before,
    code, stay of after (zie phase). Wat de gast nog niet mag zien (de pincode voor hij zijn gegevens invulde of
    zolang de kamer niet betaald is), staat er niet in.
    visit: de gast opende de pagina (niet het automatisch verversen); wordt bijgehouden voor de monitor."""
    if token.startswith(DEMO_PREFIX):
        hotel_id = token[len(DEMO_PREFIX):].partition(".")[0]
        from hotel_checkin.core.hotels import list_hotels

        if hotel_id not in list_hotels():
            return None
        return _demo(token, now or _now(hotel_id))
    r = repo.get_by_token(token) if token else None
    if r is None:
        return None
    now = now or _now(r.hotel_id)
    if today is not None:  # oude aanroep met alleen een dag: middag van die dag
        now = datetime.combine(today, datetime.min.time().replace(hour=12), tzinfo=now.tzinfo)
    ph = phase(r.hotel_id, r, now)
    if r.status == ReservationStatus.CANCELLED:
        state = "cancelled"
    elif r.departure + timedelta(days=STAY_PAGE_DAYS) < now.date():
        state = "closed"
    else:
        state = "open"
    from hotel_checkin.core.addresses import is_own_email

    email = r.guest.email or ""
    # Doorstuuradres van Booking.com, Expedia, ... niet voorstellen: de gast vult zijn eigen adres in
    shown = email if is_own_email(email) else ""
    completed = r.checkin_completed_at is not None
    access = _access(r.hotel_id, r, completed, now, ph) if state == "open" else None
    if visit:
        try:
            repo.record_visit(r.hotel_id, r.reservation_id, bool(access and access["codes"]))
        except Exception:  # de pagina moet altijd laden
            logging.warning("%s: bezoek aan de verblijfspagina niet bewaard", r.hotel_id, exc_info=True)
    return {
        "state": state,
        "phase": ph,
        "first_name": r.guest.first_name,
        "last_name": r.guest.last_name,
        "arrival": r.arrival.isoformat(),
        "departure": r.departure.isoformat(),
        "guest_count": r.guest_count,
        "nights": (r.departure - r.arrival).days,
        "room_type": r.room_type or "",
        "rooms": _rooms(r.hotel_id, list(r.rooms)),
        "email": shown,
        "phone": r.guest.phone or "",
        "country": r.guest.country or "",
        "backup_email": r.guest.backup_email or "",
        "backup_phone": r.guest.backup_phone or "",
        "language": r.guest.language,
        "completed": completed,
        "no_marketing": repo.is_opted_out(r.hotel_id, email) if email else False,
        "hotel": {**hotel_info(r.hotel_id, r.guest.language), **_hotel_extra(r.hotel_id)},
        "times": _times(r.hotel_id),
        "wifi": _wifi(r.hotel_id),
        "stairs": stairs_question(r.hotel_id, r.room_type, list(r.room_names.values())),
        "stairs_help": bool(r.stairs_help),
        "pay": pay_info(r) if state == "open" else None,
        "access": access,
    }


def unlock(token: str, door: str, now: datetime | None = None) -> tuple[bool, str]:
    """Deur openen vanuit de app (processes/guest_unlock.py). Geeft (ok, reden) terug."""
    if token.startswith(DEMO_PREFIX):  # voorbeeld: niets openen, wel "gelukt" tonen
        return (True, "opened") if form_data(token) else (False, "not_found")
    r = repo.get_by_token(token) if token else None
    if r is None:
        return False, "not_found"
    from hotel_checkin.processes import guest_unlock

    return guest_unlock.open_door(r.hotel_id, r, str(door or ""), now or _now(r.hotel_id))


def door_status(token: str, now: datetime | None = None) -> dict | None:
    """Toestand van de deuren (vergrendeld, bereikbaar) voor de app, tijdens het verblijf. None = niets te tonen."""
    if token.startswith(DEMO_PREFIX):
        d = form_data(token)
        if not d or not (d.get("access") or {}).get("unlock"):
            return None
        return {door: {"online": True, "locked": True} for door in d["access"]["unlock"]}
    r = repo.get_by_token(token) if token else None
    if r is None:
        return None
    from hotel_checkin.processes import guest_unlock

    return guest_unlock.door_status(r.hotel_id, r, now or _now(r.hotel_id))


def pay_started(token: str, now: datetime | None = None) -> bool:
    """De gast klikte op Betalen: Lighthouse meteen opnieuw laten lezen (processes/guest_payment.py)."""
    if token.startswith(DEMO_PREFIX):
        return False
    r = repo.get_by_token(token) if token else None
    if r is None:
        return False
    from hotel_checkin.processes import guest_payment

    return guest_payment.pay_started(r.hotel_id, r, now or _now(r.hotel_id))


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
    if data.get("phase") == "after":
        return False, {"state": "closed"}

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
