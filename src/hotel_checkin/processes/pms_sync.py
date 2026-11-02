"""Proces: de pincode en de status in Lighthouse zetten zodra de gast zijn code heeft.

Kleuren in Lighthouse: roze = reservatie, bruin = KLAAR OM IN TE CHECKEN, geel = INGECHECKT.
Zodra er voor de reservatie een pincode bij Salto is (de gast krijgt ze in de code-mail):
- bovenaan de opmerking (venster Bewerken bij Algemene informatie) de regel "Deur Pin code: 2242",
  of bij meer kamers "Deur Pin code: kamer 16: 2242, kamer 21: 9911". De rest van de opmerking blijft
  staan (bv. de betaalinfo van Booking.com); een vorige regel van ons wordt vervangen;
- elke kamer op KLAAR OM IN TE CHECKEN (bruin), als ze nog niet verder staat (ingecheckt of uitgecheckt).
INGECHECKT (geel) zet de receptie, of later de robot als Salto meldt dat de gast met zijn code binnen was.
Schrijven in Lighthouse alleen in PRD, of op reservaties van een testgast ([test] guest_names).
"""

from __future__ import annotations

import logging

from hotel_checkin.core import safety
from hotel_checkin.core.models import Channel, Reservation, ReservationStatus, SendResult
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse
from hotel_checkin.pms.lighthouse_parse import door_code_line, with_door_codes

MESSAGE_TYPE = "pms_sync"
_FURTHER = ("checkin", "checkout")


def wanted_line(r: Reservation) -> str | None:
    return door_code_line([(c["room"], c["pin"]) for c in r.access_codes]) if r.access_codes else None


def candidate(r: Reservation) -> bool:
    """Moet er iets in Lighthouse gezet worden? Code nog niet (of een andere) in de opmerking, of een kamer
    nog niet op bruin."""
    if r.status == ReservationStatus.CANCELLED or not r.access_codes:
        return False
    if not safety.may_write_pms(r.hotel_id, r.guest.first_name, r.guest.last_name):
        return False
    return r.pms_codes_line != wanted_line(r) or any(s not in ("readyforcheckin", *_FURTHER) for s in r.room_statuses or ["none"])


def handle(hotel_id: str, r: Reservation, lh) -> str | None:
    line = wanted_line(r)
    label = r.booking_number or r.reservation_id[:8]
    done = []
    if r.pms_codes_line != line:
        lighthouse.set_comments(hotel_id, r.reservation_id, lambda current: with_door_codes(current, line), lh)
        r.pms_codes_line = line
        done.append("code in de opmerking")
    if any(s not in ("readyforcheckin", *_FURTHER) for s in r.room_statuses or ["none"]):
        detail = lighthouse.get_reservation(hotel_id, r.reservation_id, lh)  # huidige status per kamer
        if any(s not in ("readyforcheckin", *_FURTHER) for s in detail.room_statuses):
            r.room_statuses = lighthouse.set_room_status(hotel_id, r.reservation_id, "readyforcheckin", lh)
            done.append("kamer(s) op KLAAR OM IN TE CHECKEN")
        else:
            r.room_statuses = detail.room_statuses
    guests.save_reservation(r, fields=guests.PMS_SYNC_FIELDS)
    if done:
        note = ", ".join(done)
        guests.log_message(hotel_id, r.reservation_id, MESSAGE_TYPE, SendResult(Channel.PMS, "Lighthouse", True), note=note)
        return f"{label}: {note}"
    return None


TASK = "lighthouse_bijwerken"


def log_run(hotel_id: str, started, checked: int, notes: list[str]) -> None:
    """Eigen regel in het robotlog (taak "Pincode en status in Lighthouse")."""
    errors = [n for n in notes if ": fout " in n]
    done = [n for n in notes if n not in errors]
    note = (f"{checked} reservaties met een code nagekeken. "
            + (f"{len(done)} bijgewerkt: " + "; ".join(done) if done else "niets te doen (alles stond al goed)")
            + (f". {len(errors)} fout: " + "; ".join(errors) if errors else ""))
    guests.log_robot_run(hotel_id, TASK, started, not errors, checked, len(done), note)


def run(hotel_id: str, lh) -> list[str]:
    from hotel_checkin.core import progress

    out = []
    todo = [r for r in guests.list_reservations(hotel_id) if candidate(r)]
    for n, r in enumerate(todo, 1):
        progress.step(hotel_id, TASK, f"{n} van {len(todo)}: {r.booking_number or ''}", force=n == 1)
        try:
            result = handle(hotel_id, r, lh)
        except Exception as exc:
            logging.exception("%s: Lighthouse bijwerken %s", hotel_id, r.booking_number)
            guests.log_message(hotel_id, r.reservation_id, MESSAGE_TYPE,
                               SendResult(Channel.PMS, "Lighthouse", False, error=f"{type(exc).__name__}: {exc}"[:300]))
            result = f"{r.booking_number or r.reservation_id[:8]}: fout {type(exc).__name__}"
        if result:
            out.append(result)
    return out
