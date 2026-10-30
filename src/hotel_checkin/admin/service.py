"""Gegevens voor de opvolgpagina (web/admin). Alleen lezen, behalve de robot starten.

Bevat gastgegevens: in de cloud alleen achter een Microsoft-login.
"""

from __future__ import annotations

import json

import threading
from datetime import datetime, timedelta, timezone

from hotel_checkin.core.hotels import list_hotels, load_hotel
from hotel_checkin.guests import repository as repo

_robot_lock = threading.Lock()
_robot_state: dict[str, str] = {}  # hotel_id -> "bezig" / laatste fout


def hotels() -> list[dict]:
    return [{"id": h, "name": load_hotel(h)["hotel"]["naam"]} for h in list_hotels()]


def reservations(hotel_id: str) -> list[dict]:
    from hotel_checkin.guests import profiles

    periods = {g.guest_id: g.stay_periods for g in profiles.list_profiles(hotel_id)}

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
            "arrival": r.arrival.isoformat(),
            "departure": r.departure.isoformat(),
            "guest": f"{r.guest.first_name} {r.guest.last_name}".strip(),
            "email": r.guest.email or "",
            "phone": r.guest.phone or "",
            "language": r.guest.language,
            "guests": r.guest_count,
            "room_type": r.room_type or "",
            "rooms": r.rooms,
            "source": r.source or "",
            "pms_status": r.pms_status or "",
            "status": r.status.value,
            "booked_at": r.booked_at.isoformat() if r.booked_at else "",
            "checkin_completed_at": r.checkin_completed_at.isoformat() if r.checkin_completed_at else "",
            "guest_id": r.guest_id or "",
            "guest_stays": earlier_stays(r) if r.guest_id else 0,
            "added_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            "messages": [
                {"type": m["message_type"], "channel": m["channel"], "ok": m["ok"], "at": m["sent_at"]}
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
    out = []
    for g in profiles.list_profiles(hotel_id):
        channels = sorted(g.channels.items(), key=lambda kv: -kv[1])
        rooms = sorted(g.rooms.items(), key=lambda kv: -kv[1])
        out.append({
            "id": g.guest_id, "name": f"{g.first_name} {g.last_name}".strip(),
            "email": g.email or "", "email_own": g.email_own, "phone": g.phone or "",
            "language": g.language, "country": g.country or "", "form": g.from_checkin_form,
            "message_channels": g.message_channels,
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
            "reservations": g.reservation_ids,
            "updated_at": g.updated_at.isoformat() if g.updated_at else "",
        })
    return {"guests": out, "matches": guest_profiles.possible_matches(hotel_id)}


def merge_guests(hotel_id: str, keep: str, other: str) -> bool:
    from hotel_checkin.processes import guest_profiles

    return hotel_id in list_hotels() and guest_profiles.merge(hotel_id, keep, other) is not None


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

    return {**workflow.config(hotel_id), "choices": {
        "flows": list(workflow.FLOWS), "when": list(workflow.WHEN), "channels": list(workflow.CHANNELS),
        "pay": list(workflow.PAY), "conditions": list(workflow.CONDITIONS), "steps": list(workflow.STEP_TYPES),
        "city_tax_units": list(workflow.CITY_TAX_UNITS),
    }}


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
    data = {**templates.sample_data(language), **send_messages.pay_data(hotel_id, sample, cfg, open_amount=245.0),
            "betaal_link": "#betalen"}
    msg = templates.render(hotel_id, step.step, language, data, step.mail_content(), step.pay)
    return {"subject": msg.subject, "html": msg.html}
