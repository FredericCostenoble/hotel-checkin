"""Gegevens voor de opvolgpagina (web/admin). Alleen lezen, behalve de robot starten.

Bevat gastgegevens: in de cloud alleen achter een Microsoft-login.
"""

from __future__ import annotations

import json

import threading
from datetime import date, datetime, timedelta, timezone

from hotel_checkin.core.addresses import relay_platform
from hotel_checkin.core.hotels import list_hotels, load_hotel
from hotel_checkin.guests import repository as repo

_robot_lock = threading.Lock()
_robot_state: dict[str, str] = {}  # hotel_id -> "bezig" / laatste fout


def hotels() -> list[dict]:
    """Hotels voor de keuzelijst, met waar berichten in deze omgeving echt naartoe gaan: in PRD naar
    de gast, daarbuiten naar het testadres en testnummer (leeg = er wordt niets verstuurd)."""
    from hotel_checkin.core import safety
    from hotel_checkin.processes import send_messages

    prd = safety.is_production()
    return [{"id": h, "name": load_hotel(h)["hotel"]["naam"], "production": prd,
             "test_email": "" if prd else (safety.test_address("email", h) or ""),
             "test_phone": "" if prd else (safety.test_address("phone", h) or ""),
             "phone_enabled": send_messages.phone_enabled(h)}
            for h in list_hotels()]


def reservations(hotel_id: str) -> list[dict]:
    from hotel_checkin.guests import profiles

    from hotel_checkin.core import workflow
    from hotel_checkin.processes import send_messages

    all_profiles = profiles.list_profiles(hotel_id)
    periods = {g.guest_id: g.stay_periods for g in all_profiles}
    muted = {g.guest_id: set(g.muted_channels) for g in all_profiles}
    own_email = {g.guest_id: g.email for g in all_profiles if g.email_own and g.email}
    # Adressen en nummers uit het gastprofiel (ook van vroegere verblijven), voor de keuzelijst bij versturen
    profile_contacts = {g.guest_id: {"emails": list(dict.fromkeys(e for e in [g.email, g.backup_email, *g.known_emails] if e)),
                                     "phones": list(dict.fromkeys(p for p in [g.phone, g.backup_phone, *g.known_phones] if p))}
                        for g in all_profiles}
    phone = send_messages.phone_enabled(hotel_id)
    from hotel_checkin.pms.lighthouse_browser import base_url
    lighthouse = base_url(hotel_id) + "/Customer/Reservations/Detail/"
    cfg, ready = workflow.config(hotel_id), send_messages.ready_steps(hotel_id)
    begin, on, today = send_messages.start(hotel_id), send_messages.enabled(hotel_id), date.today()

    def earlier_stays(r) -> int:
        """Verblijven van de gast buiten de periode van deze reservatie (terugkerende gast)."""
        a, d = r.arrival.isoformat(), r.departure.isoformat()
        return sum(1 for pa, pd in periods.get(r.guest_id, []) if not (a < pd and d > pa))
    out = []
    for r in repo.list_reservations(hotel_id):
        msgs = repo.messages_for(hotel_id, r.reservation_id)
        out.append({
            "id": r.reservation_id,
            "booking_number": r.booking_number or "",
            "lighthouse_url": lighthouse + r.reservation_id,  # het id is de GUID van Lighthouse
            "arrival": r.arrival.isoformat(),
            "departure": r.departure.isoformat(),
            "guest": f"{r.guest.first_name} {r.guest.last_name}".strip(),
            "email": r.guest.email or "",
            "phone": r.guest.phone or "",
            "backup_email": r.guest.backup_email or "",
            "backup_phone": r.guest.backup_phone or "",
            "relay_email": r.guest.relay_email or "",
            "email_platform": relay_platform(r.guest.email) or "",
            "relay_platform": relay_platform(r.guest.relay_email) or "",
            "profile_emails": profile_contacts.get(r.guest_id or "", {}).get("emails", []),
            "profile_phones": profile_contacts.get(r.guest_id or "", {}).get("phones", []),
            "language": r.guest.language,
            "guests": r.guest_count,
            "room_type": r.room_type or "",
            "rooms": r.rooms,
            "source": r.source or "",
            "flow": workflow.flow_for(hotel_id, r, cfg),  # welke workflow: volgens "Via" (en betaalstatus)
            "pms_status": r.pms_status or "",
            "status": r.status.value,
            "booked_at": r.booked_at.isoformat() if r.booked_at else "",
            "checkin_completed_at": r.checkin_completed_at.isoformat() if r.checkin_completed_at else "",
            "guest_id": r.guest_id or "",
            "guest_stays": earlier_stays(r) if r.guest_id else 0,
            "added_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            "plan": send_messages.plan(hotel_id, r, msgs, cfg, ready, today, begin, on, phone,
                                       muted.get(r.guest_id or "", set()), own_email.get(r.guest_id or "")),
            "messages": [
                {"type": m["message_type"], "channel": m["channel"], "ok": m["ok"], "at": m["sent_at"],
                 "to": m.get("recipient", ""), "delivered_to": m.get("delivered_to", ""), "status": m.get("status") or ("sent" if m["ok"] else "failed"),
                 "error": m.get("error", ""), "note": m.get("note", ""), "status_at": m.get("status_at", "")}
                for m in msgs
            ],
        })
    return out


def runs(hotel_id: str) -> dict:
    return {"running": _robot_state.get(hotel_id) == "bezig", "runs": [
        {k: e.get(k) for k in ("task", "started_at", "finished_at", "ok", "found", "new", "error", "skipped")}
        | {"timings": json.loads(e.get("timings") or "{}"), "id": e.get("RowKey")}
        for e in repo.robot_runs(hotel_id, limit=200)
    ]}


def guests(hotel_id: str) -> dict:
    """Gastprofielen en mogelijke dubbels voor de monitor."""
    from hotel_checkin.guests import profiles
    from hotel_checkin.processes import guest_profiles

    opted_out = {e for e in repo.opted_out_emails(hotel_id)}
    res_by_guest: dict[str, list] = {}
    for r in repo.list_reservations(hotel_id):
        if r.guest_id:
            res_by_guest.setdefault(r.guest_id, []).append(r)
    out = []
    for g in profiles.list_profiles(hotel_id):
        channels = sorted(g.channels.items(), key=lambda kv: -kv[1])
        rooms = sorted(g.rooms.items(), key=lambda kv: -kv[1])
        out.append({
            "id": g.guest_id, "name": f"{g.first_name} {g.last_name}".strip(),
            "email": g.email or "", "email_own": g.email_own, "phone": g.phone or "",
            "backup_email": g.backup_email or "", "backup_phone": g.backup_phone or "",
            "known_emails": g.known_emails, "known_phones": g.known_phones,
            "relay_emails": sorted({r.guest.relay_email or r.guest.email for r in res_by_guest.get(g.guest_id, [])
                                    if relay_platform(r.guest.relay_email or r.guest.email)}),
            "language": g.language, "country": g.country or "", "form": g.from_checkin_form,
            "opt_out": bool(g.email and g.email.lower() in opted_out),
            "first_stay": g.first_stay.isoformat() if g.first_stay else "",
            "last_stay": g.last_stay.isoformat() if g.last_stay else "",
            "stays": g.stays, "nights": g.nights, "cancellations": g.cancellations,
            "last_cancelled": g.last_cancelled.isoformat() if g.last_cancelled else "",
            "avg_nights": round(g.nights / g.stays, 1) if g.stays else None,
            "avg_persons": round(g.persons / g.persons_stays, 1) if g.persons_stays else None,
            "rooms": [k for k, _ in rooms], "room_type": max(g.room_types, key=g.room_types.get) if g.room_types else "",
            "channels": [{"name": k, "count": v} for k, v in channels],
            "preferred_channel": channels[0][0] if channels else "",
            "muted": g.muted_channels,
            "reservations": g.reservation_ids,
            "updated_at": g.updated_at.isoformat() if g.updated_at else "",
        })
    return {"guests": out, "matches": guest_profiles.possible_matches(hotel_id)}


def merge_guests(hotel_id: str, keep: str, other: str) -> bool:
    from hotel_checkin.processes import guest_profiles

    return hotel_id in list_hotels() and guest_profiles.merge(hotel_id, keep, other) is not None


def add_contact(hotel_id: str, reservation_id: str, email: str, phone: str) -> dict:
    """Met de hand een e-mailadres of gsm-nummer toevoegen aan een reservatie (monitor), bv. als
    Lighthouse er geen heeft. Komt als hoofdadres als er nog geen is, anders als extra adres.
    Daarna kunnen berichten (met de hand of automatisch) verstuurd worden."""
    from hotel_checkin.checkin.service import EMAIL_RE, normalize_phone
    from hotel_checkin.processes import guest_profiles

    r = repo.get_reservation(hotel_id, reservation_id) if hotel_id in list_hotels() else None
    if r is None:
        return {"ok": False, "error": "Reservatie niet gevonden"}
    email = (email or "").strip().lower()
    if email and not EMAIL_RE.match(email):
        return {"ok": False, "error": "Ongeldig e-mailadres"}
    number = normalize_phone(phone) if (phone or "").strip() else None
    if (phone or "").strip() and number is None:
        return {"ok": False, "error": "Ongeldig gsm-nummer (met landcode, bv. +32...)"}
    if not email and not number:
        return {"ok": False, "error": "Geef een e-mailadres of gsm-nummer"}
    if email:
        if not r.guest.email:
            r.guest.email = email
        elif email != r.guest.email.lower():
            r.guest.backup_email = email
    if number:
        if not r.guest.phone:
            r.guest.phone = number
        elif number != r.guest.phone:
            r.guest.backup_phone = number
    saved = repo.save_reservation(r)
    try:
        guest_profiles.link(saved)
    except Exception:  # noqa: BLE001 - het adres is bewaard; het profiel volgt bij het synchroniseren
        pass
    return {"ok": True}


def resend(hotel_id: str, reservation_id: str, step: str, channel: str, to: str, user: str) -> dict:
    from hotel_checkin.processes import send_messages

    if hotel_id not in list_hotels() or channel not in ("email", "whatsapp", "sms"):
        return {"ok": False, "error": "Onbekend hotel of kanaal"}
    return send_messages.resend(hotel_id, reservation_id, step, channel, to, user)


def set_muted_channels(hotel_id: str, guest_id: str, muted: list[str]) -> bool:
    """Kanalen voor één gast uit- of aanzetten (tabblad Gasten)."""
    from hotel_checkin.guests import profiles

    g = profiles.get_profile(hotel_id, guest_id) if hotel_id in list_hotels() else None
    if g is None:
        return False
    g.muted_channels = sorted({c for c in muted if c in ("email", "whatsapp", "sms")})
    profiles.save_profile(g)
    return True


def mark_guests_different(hotel_id: str, a: str, b: str) -> bool:
    from hotel_checkin.guests import profiles

    if hotel_id not in list_hotels() or not a or not b:
        return False
    profiles.mark_different(hotel_id, a, b)
    return True


def delete_run(hotel_id: str, run_id: str) -> bool:
    return hotel_id in list_hotels() and repo.delete_robot_run(hotel_id, run_id)


def delete_runs(hotel_id: str, task: str | None = None) -> int:
    """Alle regels uit het robotlogboek (of alleen die van één taak) verwijderen."""
    return repo.delete_robot_runs(hotel_id, task or None) if hotel_id in list_hotels() else 0


def start_robot(hotel_id: str, hours: int = 48) -> bool:
    """Start de robot (nieuwe reservaties) op de achtergrond. False als hij al loopt."""
    from hotel_checkin.processes import new_reservation

    if hotel_id not in list_hotels() or not _robot_lock.acquire(blocking=False):
        return False

    _robot_state[hotel_id] = "bezig"

    def work():
        try:
            new_reservation.run(hotel_id, datetime.now(timezone.utc) - timedelta(hours=hours))
            _robot_state[hotel_id] = ""
        except Exception as exc:  # noqa: BLE001 - staat ook in het robotlog
            _robot_state[hotel_id] = str(exc)
        finally:
            _robot_lock.release()

    threading.Thread(target=work, daemon=True).start()
    return True


# ---------------------------------------------------------------- workflow (tabblad Workflow)


def workflow_view(hotel_id: str) -> dict:
    """De geldende workflow plus de keuzes voor het scherm."""
    from hotel_checkin.core import workflow
    from hotel_checkin.processes import send_messages

    cfg = workflow.config(hotel_id)
    # Welke waarden van "Via" (Lighthouse) bij welke flow terechtkomen, uit de bewaarde reservaties
    seen: dict[str, dict[str, int]] = {f: {} for f in workflow.FLOWS}
    for r in repo.list_reservations(hotel_id):
        flow, via = workflow.flow_for(hotel_id, r, cfg), r.source or "?"
        seen[flow][via] = seen[flow].get(via, 0) + 1
    return {**cfg, "ready": list(send_messages.ready_steps(hotel_id)),
            "seen_sources": {f: sorted(v.items(), key=lambda kv: -kv[1]) for f, v in seen.items()}, "choices": {
        "flows": list(workflow.FLOWS), "when": list(workflow.WHEN), "channels": list(workflow.CHANNELS),
        "pay": list(workflow.PAY), "conditions": list(workflow.CONDITIONS), "steps": list(workflow.STEP_TYPES),
        "city_tax_units": list(workflow.CITY_TAX_UNITS),
    }}


def settings_view(hotel_id: str) -> dict:
    """Instellingen van het hotel (tabblad Hotel op de instellingenpagina)."""
    from hotel_checkin.core import hotel_settings

    return hotel_settings.view(hotel_id)


def settings_save(hotel_id: str, changes: dict, user: str) -> tuple[bool, dict]:
    from hotel_checkin.core import hotel_settings

    try:
        return True, hotel_settings.save(hotel_id, changes, user)
    except ValueError as exc:
        return False, {"error": str(exc)}


def settings_reset(hotel_id: str) -> dict:
    from hotel_checkin.core import hotel_settings

    return hotel_settings.reset(hotel_id)


def workflow_save(hotel_id: str, cfg: dict, user: str) -> tuple[bool, dict]:
    """(True, nieuwe workflow) of (False, {"error": uitleg})."""
    from hotel_checkin.core import workflow

    try:
        workflow.save_config(hotel_id, cfg, user)
    except ValueError as exc:
        return False, {"error": str(exc)}
    return True, workflow_view(hotel_id)


def workflow_reset(hotel_id: str) -> dict:
    from hotel_checkin.core import workflow

    workflow.reset_config(hotel_id)
    return workflow_view(hotel_id)


def workflow_preview(hotel_id: str, body: dict) -> dict:
    """Voorbeeldmail voor een stap zoals ze nu op het scherm staat (ook niet bewaard), met
    voorbeeldgegevens. body: {"step": {...}, "flow": "booking", "language": "nl"}."""
    from datetime import date, timedelta

    from hotel_checkin.core import workflow
    from hotel_checkin.core.models import Guest, Reservation
    from hotel_checkin.messaging import templates
    from hotel_checkin.processes import send_messages

    language = body.get("language") or "nl"
    raw = body.get("step") or {}
    cfg = workflow.config(hotel_id)
    try:
        if body.get("parameters"):
            cfg = {**cfg, "parameters": workflow.validate(hotel_id, {"parameters": body["parameters"], "flows": cfg["flows"]})["parameters"]}
        step = workflow.Step(step=raw["step"], when=raw.get("when", "after_booking"), days=int(raw.get("days", 0) or 0),
                             pay=raw.get("pay", "none"), content={k: bool(v) for k, v in (raw.get("content") or {}).items()})
    except (KeyError, TypeError, ValueError) as exc:
        return {"error": str(exc)}
    source = {"booking": "Booking.com", "expedia": "Expedia"}.get(body.get("flow", ""), "Website")
    arrival = date.today() + timedelta(days=14)
    sample = Reservation(hotel_id, "voorbeeld", Guest("Anna", "Peeters", language=language), arrival,
                         arrival + timedelta(days=2), guest_count=2, source=source)
    # voorbeeldfolio: kamer voor 2 nachten, toeristenbelasting voor 2 personen, voorschot betaald
    sample.folio = [{"label": "Superior Double Room - Standard rate", "qty": None, "amount": 240.0},
                    {"label": "Citytax", "qty": 4, "amount": 20.0}]
    sample.folio_total, sample.open_amount = 260.0, 245.0
    data = {**templates.sample_data(language), **send_messages.pay_data(hotel_id, sample, cfg),
            "token": "voorbeeld-" + hotel_id,  # werkende link naar het formulier (voorbeeld, niets bewaard)
            "betaal_link": "#betalen"}
    msg = templates.render(hotel_id, step.step, language, data, step.mail_content(), step.pay)
    return {"subject": msg.subject, "html": msg.html}
