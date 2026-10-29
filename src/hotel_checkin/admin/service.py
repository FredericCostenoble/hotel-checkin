"""Gegevens voor de opvolgpagina (web/admin). Alleen lezen, behalve de robot starten.

Bevat gastgegevens: in de cloud alleen achter een Microsoft-login.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from hotel_checkin.core.hotels import list_hotels, load_hotel
from hotel_checkin.guests import repository as repo

_robot_lock = threading.Lock()
_robot_state: dict[str, str] = {}  # hotel_id -> "bezig" / laatste fout


def hotels() -> list[dict]:
    return [{"id": h, "name": load_hotel(h)["hotel"]["naam"]} for h in list_hotels()]


def reservations(hotel_id: str) -> list[dict]:
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
            "messages": [
                {"type": m["message_type"], "channel": m["channel"], "ok": m["ok"], "at": m["sent_at"]}
                for m in msgs
            ],
        })
    return out


def runs(hotel_id: str) -> dict:
    return {"running": _robot_state.get(hotel_id) == "bezig", "runs": [
        {k: e.get(k) for k in ("task", "started_at", "finished_at", "ok", "found", "new", "error")}
        for e in repo.robot_runs(hotel_id)
    ]}


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
