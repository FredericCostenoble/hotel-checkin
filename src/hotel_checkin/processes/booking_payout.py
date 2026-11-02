"""Proces: de overschrijving van Booking.com in Lighthouse registreren.

Bij "Payments by Booking.com" int Booking.com de kamerprijs zelf en stort ze per overschrijving door.
De opmerking van de reservatie zegt dat: 'PrePay:payment_on_Booking.com (Payout type: BankTransfer)362 EUR'.
Dan registreert de robot onder Transacties een betaling "Overschrijving" van dat bedrag. Daarna staat
alleen de toeristenbelasting nog open (betaalverzoek aan de gast).

Wanneer:
- niet annuleerbaar (annuleringsvoorwaarden "op elk moment", of tarief NRF): meteen;
- annuleerbaar of niet gekend: vanaf 2 dagen voor aankomst (dan kan de gast via Booking.com niet meer
  annuleren), en alleen als de reservatie niet geannuleerd is.
Controles, vlak ervoor op de detailpagina (altijd opnieuw gelezen):
- het bedrag uit de opmerking = de kamerprijs in de folio (alles behalve de toeristenbelasting);
  klopt het niet, dan niets registreren en een melding in het berichtenlog (monitor);
- staat er al een overschrijving bij de transacties, dan niets (nooit dubbel).
Schrijven in Lighthouse alleen in PRD, of op reservaties van een testgast ([test] guest_names).
Een testgast zonder opmerking van Booking.com: de kamerprijs uit de folio, om te oefenen.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from hotel_checkin.core import clock, safety, workflow
from hotel_checkin.core.models import Channel, Reservation, ReservationStatus, SendResult
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse
from hotel_checkin.pms.lighthouse_parse import booking_prepay, free_cancel_days

TASK = "overschrijving_booking"
DAYS_BEFORE = 2
COMMENT = "Booking.com overschrijving (automatisch)"
MESSAGE_TYPE = "booking_payout"
_CITY_TAX = workflow.CITY_TAX_LABELS


def room_price(r: Reservation) -> float | None:
    """Kamerprijs uit de folio: alle lijnen behalve de toeristenbelasting. None = folio niet gekend."""
    if not r.folio:
        return None
    return round(sum(x["amount"] for x in r.folio if not any(k in x["label"].lower() for k in _CITY_TAX)), 2)


def is_test(r: Reservation) -> bool:
    return safety.is_test_guest(r.hotel_id, r.guest.first_name, r.guest.last_name)


def already_registered(r: Reservation) -> bool:
    return bool(r.payout_registered_at) or any("overschrijving" in t.lower() for t in r.transactions)


def candidate(r: Reservation, cfg: dict, today: date) -> bool:
    """Komt deze reservatie in aanmerking (op basis van wat bewaard is)? De detailpagina wordt daarna
    toch opnieuw gelezen."""
    if r.status == ReservationStatus.CANCELLED or r.departure < today or r.payout_registered_at:
        return False
    if not (workflow.flow_for(r.hotel_id, r, cfg) == "booking" or is_test(r)):
        return False
    if not safety.may_write_pms(r.hotel_id, r.guest.first_name, r.guest.last_name):
        return False
    return r.non_refundable is True or r.arrival - timedelta(days=DAYS_BEFORE) <= today or r.remarks is None


def due(r: Reservation, today: date) -> bool:
    """Nu registreren? Niet annuleerbaar: meteen. Anders vanaf 2 dagen voor aankomst."""
    days = free_cancel_days(r.remarks)
    sure_nrf = days == 0 or (days is None and r.non_refundable is True)
    return sure_nrf or r.arrival - timedelta(days=DAYS_BEFORE) <= today


def amount_for(r: Reservation) -> float | None:
    paid_by_booking = booking_prepay(r.remarks)
    if paid_by_booking is None and is_test(r):
        return room_price(r)  # oefenen op een testreservatie zonder opmerking van Booking.com
    return paid_by_booking


def _log(r: Reservation, ok: bool, note: str) -> None:
    guests.log_message(r.hotel_id, r.reservation_id, MESSAGE_TYPE,
                       SendResult(Channel.PMS, "Lighthouse", ok, error=None if ok else note), note=note)


def handle(hotel_id: str, stored: Reservation, lh, today: date) -> str | None:
    """Eén reservatie: detailpagina lezen, controleren, registreren. Geeft een korte uitleg terug als er
    iets gebeurde of misliep (voor het robotlog), anders None."""
    label = stored.booking_number or stored.reservation_id[:8]
    r = lighthouse.get_reservation(hotel_id, stored.reservation_id, lh)  # altijd de huidige toestand
    r.guest.first_name = r.guest.first_name or stored.guest.first_name
    r.guest.last_name = r.guest.last_name or stored.guest.last_name
    # Opmerking, transacties en annuleerbaarheid bewaren: dan moet deze reservatie pas opnieuw gelezen
    # worden als ze aan de beurt is (annuleerbaar: 2 dagen voor aankomst)
    stored.remarks, stored.transactions = r.remarks, r.transactions
    if r.non_refundable is not None:
        stored.non_refundable = r.non_refundable
    guests.save_reservation(stored, fields=("remarks", "transactions", "non_refundable"))
    if r.status == ReservationStatus.CANCELLED or not due(r, today):
        return None
    amount = amount_for(r)
    if amount is None:
        return None  # geen overschrijving door Booking.com (bv. de gast betaalt zelf)
    if already_registered(r):
        stored.payout_registered_at = stored.payout_registered_at or datetime.now(UTC)
        guests.save_reservation(stored, fields=guests.PAYOUT_FIELDS)
        return None
    price = room_price(r)
    if price is None or abs(price - amount) > 0.01:
        note = (f"Overschrijving Booking.com niet geregistreerd: bedrag in de opmerking {amount:.2f} EUR, "
                f"kamerprijs in de folio {'onbekend' if price is None else f'{price:.2f} EUR'}. Nakijken in Lighthouse.")
        already = [m for m in guests.messages_for(hotel_id, r.reservation_id)
                   if m["message_type"] == MESSAGE_TYPE and not m["ok"] and m.get("note") == note]
        if not already:  # één melding, niet bij elke run opnieuw
            _log(stored, False, note)
        return f"{label}: bedrag klopt niet ({amount:.2f} tegenover {price})"
    if not safety.may_write_pms(hotel_id, r.guest.first_name, r.guest.last_name):
        return None
    after = lighthouse.add_payment(hotel_id, r.reservation_id, "bank_transfer", amount, COMMENT, lh)
    open_after = after.open_amount
    stored.payout_registered_at = datetime.now(UTC)
    guests.save_reservation(stored, fields=guests.PAYOUT_FIELDS)
    note = f"Overschrijving Booking.com {amount:.2f} EUR geregistreerd" + (
        f", nog open {open_after:.2f} EUR" if open_after is not None else "")
    _log(stored, True, note)
    return f"{label}: {note}"


def run(hotel_id: str, lh, today: date | None = None) -> list[str]:
    """Alle reservaties die in aanmerking komen, binnen een al geopende Lighthouse-sessie (robot)."""
    today = today or clock.today(hotel_id)
    cfg = workflow.config(hotel_id)
    done: list[str] = []
    for r in guests.list_reservations(hotel_id):
        if not candidate(r, cfg, today):
            continue
        try:
            result = handle(hotel_id, r, lh, today)
        except Exception as exc:
            logging.exception("%s: overschrijving %s", hotel_id, r.booking_number)
            result = f"{r.booking_number or r.reservation_id[:8]}: fout {type(exc).__name__}"
        if result:
            done.append(result)
    return done
