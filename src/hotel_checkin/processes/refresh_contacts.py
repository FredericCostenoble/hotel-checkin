"""Proces: contactgegevens en reservaties opnieuw nalezen in Lighthouse.

Voor reservaties met aankomst binnenkort die nog geen e-mailadres hebben: het adres kan later
nog in Lighthouse komen. Voor aankomsten van de komende dagen (code-mail) ook kamer, betaling en
status, want kamers worden vaak pas later toegewezen.

De lijst van nieuwe boekingen toont geen wijzigingen of annuleringen van oudere boekingen. Daarom
ook opnieuw lezen: reservaties met een bericht dat vandaag of morgen moet (bv. de herinnering, zodat
een geannuleerde gast ze niet krijgt), en reservaties met een aankomst- of vertrekdag uit een melding
"gewijzigd" of "geannuleerd" (processes/refresh_requests.py). Draait minder vaak dan het zoeken naar nieuwe reservaties (de robot
beslist wanneer, instelling [robot] contact_refresh_hours in het hotelbestand).
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime, timedelta

from hotel_checkin.core import clock, run_context, workflow
from hotel_checkin.core.models import ReservationStatus
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse
from hotel_checkin.processes import grant_access, guest_profiles, refresh_requests
from hotel_checkin.processes.new_reservation import _apply_contact, _ContactStats

TASK = "contactgegevens_nalezen"

# Zolang er tijd is: een run mag in Azure max. 15 minuten duren. Wat niet past, doet de volgende run.
MAX_SECONDS = 10 * 60


def due(hotel_id: str) -> list:
    """Niet geannuleerde reservaties met aankomst binnen het venster van de workflow, zonder
    e-mailadres en nog niet door de gast aangevuld. Eerst wie het eerst aankomt."""
    today = clock.today(hotel_id)
    horizon = today + timedelta(days=workflow.detail_window_days(hotel_id))
    todo = [r for r in guests.list_reservations(hotel_id)
            if not r.guest.email and not r.checkin_completed_at
            and r.status != ReservationStatus.CANCELLED and r.departure >= today and r.arrival <= horizon]
    return sorted(todo, key=lambda r: r.arrival)


def message_due_soon(hotel_id: str, r, cfg: dict, sent: set[str], today: date) -> bool:
    """Moet er vandaag of morgen een bericht voor aankomst weg dat nog niet verstuurd is? Dan eerst
    nakijken of de reservatie intussen niet geannuleerd of gewijzigd is."""
    if r.status == ReservationStatus.CANCELLED:
        return False
    for step in workflow._steps_from(cfg, workflow.flow_for(hotel_id, r, cfg)):
        if (step.enabled and step.when == "days_before_arrival" and step.step not in sent
                and today <= step.due_date(r) <= today + timedelta(days=1)):
            return True
    return False


def arrivals_due(hotel_id: str, requested: set[str] | None = None) -> list:
    """Reservaties waarvan kamer, betaling en status opnieuw gelezen moeten worden:
    - binnenkort de code-mail en nog geen pincode (kamers worden vaak pas later toegewezen);
    - met pincode en nog niet vertrokken (kamer, data of status veranderd?);
    - net vertrokken (betaalstatus voor een betaalverzoek na vertrek);
    - vandaag of morgen een bericht voor aankomst (geannuleerd of verzet?);
    - aankomst- of vertrekdag uit een melding "gewijzigd" of "geannuleerd" (requested, ISO-dagen)."""
    today = clock.today(hotel_id)
    requested = requested or set()
    cfg = workflow.config(hotel_id)
    days = max([s.days for s in workflow.steps(hotel_id) if s.step == "access_code"] or [0]) + 1
    sent = {rid: {m["message_type"] for m in rows if m.get("ok")}
            for rid, rows in guests.messages_for_hotel(hotel_id).items()}
    todo = [r for r in guests.list_reservations(hotel_id)
            if (not r.access_pin and r.status != ReservationStatus.CANCELLED
                and today <= r.arrival <= today + timedelta(days=days))
            or (r.access_codes and r.departure >= today)
            or (r.status != ReservationStatus.CANCELLED and today - timedelta(days=2) <= r.departure <= today)
            or message_due_soon(hotel_id, r, cfg, sent.get(r.reservation_id, set()), today)
            or (r.status != ReservationStatus.CANCELLED and r.departure >= today
                and (r.arrival.isoformat() in requested or r.departure.isoformat() in requested))]
    return sorted(todo, key=lambda r: r.arrival)


def _apply_detail(r, d) -> None:
    """Kamer, betaling, status en Lighthouse-status van de detailpagina; contact alleen aanvullen."""
    r.rooms = d.rooms or r.rooms
    r.arrival, r.departure = d.arrival, d.departure
    r.paid = d.paid if d.paid is not None else r.paid
    if d.open_amount is not None:  # prijzen en openstaand bedrag voor de betaalknop in de mail
        r.open_amount, r.folio, r.folio_total = d.open_amount, d.folio, d.folio_total
    r.status = d.status
    r.pms_status = d.pms_status or r.pms_status
    if d.rate_plan:  # tarief uit de folio; anders blijft dat uit de lijst
        r.rate_plan, r.non_refundable = d.rate_plan, d.non_refundable
    r.remarks = d.remarks if d.remarks is not None else r.remarks
    r.transactions = d.transactions
    r.room_statuses = d.room_statuses or r.room_statuses
    if not r.checkin_completed_at:
        r.guest.email = r.guest.email or d.guest.email
        r.guest.phone = r.guest.phone or d.guest.phone


def run(hotel_id: str) -> int:
    """Lees de contactgegevens van die reservaties opnieuw. Geeft het aantal gevonden e-mailadressen terug."""
    started = datetime.now(UTC)
    requested = refresh_requests.requested(hotel_id)
    todo = due(hotel_id)
    arrivals = [r for r in arrivals_due(hotel_id, requested) if r.reservation_id not in {x.reservation_id for x in todo}]
    finished = True  # alles gelezen binnen de tijd (dan zijn de gevraagde dagen klaar)
    from hotel_checkin.processes import booking_payout

    cfg, today = workflow.config(hotel_id), clock.today(hotel_id)
    from hotel_checkin.processes import pms_sync

    payouts = [r for r in guests.list_reservations(hotel_id) if booking_payout.candidate(r, cfg, today)]
    syncs = [r for r in guests.list_reservations(hotel_id) if pms_sync.candidate(r)]
    payout_notes: list[str] = []
    sync_notes: list[str] = []
    details_read = 0
    access_changes: list[str] = []
    stats = _ContactStats()
    skipped: list[str] = []
    timings: dict[str, float] = {}  # gemeten duur per onderdeel (seconden), voor de monitor
    try:
        if todo or arrivals or payouts or syncs:
            t0 = time.monotonic()
            with lighthouse.connect(hotel_id) as lh:
                timings["login"] = round(time.monotonic() - t0, 1)
                timings.update({f"lh_{k}": v for k, v in getattr(lh, "timings", {}).items()})
                ready = run_context.seconds_since_start()  # sinds de container startte, aangemeld en klaar om te lezen
                if ready is not None:
                    timings["ready"] = ready
                deadline = time.monotonic() + MAX_SECONDS
                for reservation in todo:
                    if time.monotonic() > deadline:
                        finished = False
                        break
                    try:
                        t0 = time.monotonic()
                        contact = lighthouse.get_contact(hotel_id, reservation.reservation_id, lh)
                        stats.add(contact, time.monotonic() - t0)
                    except Exception as exc:  # noqa: BLE001 - volgende keer opnieuw
                        skipped.append(f"{reservation.booking_number or 'reservatie'}: {type(exc).__name__}")
                        continue
                    _apply_contact(reservation, contact)
                    guests.save_reservation(reservation, fields=guests.CONTACT_FIELDS)
                    if contact.email or contact.phone:
                        guest_profiles.link(reservation)
                # Aankomsten van de komende dagen: kamer en betaling voor de code-mail
                for reservation in arrivals:
                    if time.monotonic() > deadline:
                        finished = False
                        break
                    try:
                        detail = lighthouse.get_reservation(hotel_id, reservation.reservation_id, lh)
                    except Exception as exc:  # noqa: BLE001 - volgende keer opnieuw
                        skipped.append(f"{reservation.booking_number or 'reservatie'}: {type(exc).__name__}")
                        continue
                    _apply_detail(reservation, detail)
                    guests.save_reservation(reservation, fields=guests.DETAIL_FIELDS)
                    details_read += 1
                    if reservation.access_codes:
                        try:
                            changes = grant_access.follow_changes(hotel_id, reservation)
                        except Exception as exc:  # noqa: BLE001 - volgende keer opnieuw
                            skipped.append(f"{reservation.booking_number or 'reservatie'}: Salto {exc}")
                            continue
                        if changes:
                            access_changes.append(f"{reservation.booking_number}: {'; '.join(changes)}")
                # Overschrijving van Booking.com registreren (PRD of testgast), zie booking_payout.py
                if payouts and time.monotonic() <= deadline:
                    payout_notes = booking_payout.run(hotel_id, lh, today)
                # Pincode in de opmerking en kamers op KLAAR OM IN TE CHECKEN (PRD of testgast), zie pms_sync.py
                if syncs and time.monotonic() <= deadline:
                    sync_notes = pms_sync.run(hotel_id, lh)
    except Exception as exc:
        guests.log_robot_run(hotel_id, TASK, started, False, len(todo), 0, f"{type(exc).__name__}: {exc}", timings=timings)
        raise
    if finished and not skipped:
        refresh_requests.done(hotel_id, requested)
    parts = [stats.note()] if stats.read else []
    if requested:
        parts.append("nagelezen na melding: " + ", ".join(sorted(requested)))
    if details_read:
        parts.append(f"{details_read} aankomsten en verblijven nagekeken (kamer, data, betaling)")
    if access_changes:
        parts.append("Salto aangepast: " + ", ".join(access_changes))
    if sync_notes:
        parts.append("Lighthouse bijgewerkt: " + "; ".join(sync_notes))
    if payout_notes:
        parts.append("Overschrijving Booking.com: " + "; ".join(payout_notes))
    if skipped:
        parts.append(f"{len(skipped)} niet gelezen: " + "; ".join(skipped[:5]))
    guests.log_robot_run(hotel_id, TASK, started, True, len(todo) + len(arrivals), stats.with_email, ". ".join(parts) or None,
                         skipped=len(skipped), timings=timings | stats.timings())
    return stats.with_email
