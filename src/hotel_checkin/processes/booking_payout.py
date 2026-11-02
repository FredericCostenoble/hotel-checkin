"""Proces: de overschrijving van Booking.com in Lighthouse registreren.

Alleen als de hoofdschakelaar [schakelaars] overschrijvingen aan staat (per omgeving, standaard uit).

Welke reservaties (Booking.com, "Payments by Booking.com"):
- de opmerking vermeldt een overschrijving: 'PrePay:payment_on_Booking.com (Payout type: BankTransfer)362 EUR';
  dat bedrag moet gelijk zijn aan de kamerprijs in de folio;
- of de opmerking vermeldt een virtuele kredietkaart ("Virtual credit card"); daar staat geen bedrag bij,
  dus de kamerprijs uit de folio.
Dan registreert de robot onder Transacties een betaling "Overschrijving" van de kamerprijs. Daarna staan
alleen de toeristenbelasting en eventuele extra's (bv. ontbijt) nog open.

Wanneer:
- niet annuleerbaar (annuleringsvoorwaarden "op elk moment", of tarief NRF): meteen, ook ver op voorhand;
- anders: vanaf 2 dagen voor aankomst (dan kan de gast via Booking.com niet meer annuleren), en alleen als
  de reservatie niet geannuleerd is. Vanaf dan wordt ze bij elke robotrun opnieuw nagekeken.
Controles, vlak ervoor op de detailpagina (altijd opnieuw gelezen):
- klopt het bedrag niet met de kamerprijs, dan niets registreren en één melding in het berichtenlog;
- staat er al een overschrijving bij de transacties, dan niets (nooit dubbel). Wat geregistreerd is,
  wordt bij de reservatie onthouden (payout_registered_at) en niet meer bekeken.
Schrijven in Lighthouse alleen in PRD, of op reservaties van een testgast ([test] guest_names).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import UTC, date, datetime, timedelta

from hotel_checkin.core import clock, safety, workflow
from hotel_checkin.core.models import Channel, Reservation, ReservationStatus, SendResult
from hotel_checkin.guests import repository as guests
from hotel_checkin.pms import lighthouse
from hotel_checkin.pms.lighthouse_parse import (
    booking_collected,
    booking_prepay,
    free_cancel_days,
    rate_plans_from,
)
from hotel_checkin.processes.send_messages import switch

TASK = "overschrijving_booking"
DAYS_BEFORE = 2
COMMENT = "Booking.com overschrijving (automatisch)"
MESSAGE_TYPE = "booking_payout"
_CITY_TAX = workflow.CITY_TAX_LABELS


def _city_tax(line: dict) -> bool:
    return any(k in line["label"].lower() for k in _CITY_TAX)


def room_price(r: Reservation) -> float | None:
    """Kamerprijs uit de folio: de kamerlijnen ("Superior double - NRF BREAKFAST EXCL"), zonder
    toeristenbelasting en extra's (bv. ontbijt). Geen kamerlijn herkend: alles behalve de toeristenbelasting.
    None = folio niet gekend."""
    if not r.folio:
        return None
    rooms = [x for x in r.folio if rate_plans_from(x["label"]) and not _city_tax(x)]
    lines = rooms or [x for x in r.folio if not _city_tax(x)]
    return round(sum(x["amount"] for x in lines), 2)


_VCC = re.compile(r"virtual\s*credit\s*card|virtuele\s*kredietkaart", re.IGNORECASE)


def virtual_card(remarks: str | None) -> bool:
    """Betaalt Booking.com met een virtuele kredietkaart (vermeld in de opmerking)?"""
    return bool(_VCC.search(remarks or ""))


def paid_by_booking(r: Reservation) -> bool:
    """Betaalt Booking.com de kamer (overschrijving of virtuele kaart)?"""
    return booking_prepay(r.remarks) is not None or virtual_card(r.remarks)


def already_registered(r: Reservation) -> bool:
    return bool(r.payout_registered_at) or any("overschrijving" in t.lower() for t in r.transactions)


def candidate(r: Reservation, cfg: dict, today: date) -> bool:
    """Komt deze reservatie in aanmerking (op basis van wat bewaard is)? De detailpagina wordt daarna
    toch opnieuw gelezen."""
    if r.status == ReservationStatus.CANCELLED or r.arrival < today or r.payout_registered_at:
        return False  # alleen toekomstige reservaties (aankomst vandaag of later)
    if not switch(r.hotel_id, "overschrijvingen"):
        return False
    if workflow.flow_for(r.hotel_id, r, cfg) != "booking":
        return False
    if not safety.may_write_pms(r.hotel_id, r.guest.first_name, r.guest.last_name):
        return False
    if r.remarks is None:
        # Nog nooit gelezen. Annuleerbaar volgens het tarief uit de lijst (bv. STANDARD RATE): pas lezen vanaf
        # 2 dagen voor aankomst. Niet annuleerbaar (NRF) of onbekend: meteen lezen.
        return r.non_refundable is not False or r.arrival - timedelta(days=DAYS_BEFORE) <= today
    if not paid_by_booking(r):
        return False  # de gast betaalt zelf: niets te doen
    return due(r, today)  # zelfde regel als vlak voor het registreren: anders bij elke run opnieuw lezen


def due(r: Reservation, today: date) -> bool:
    """Nu registreren? Niet annuleerbaar: meteen. Anders vanaf 2 dagen voor aankomst."""
    days = free_cancel_days(r.remarks)
    sure_nrf = days == 0 or (days is None and r.non_refundable is True)
    return sure_nrf or r.arrival - timedelta(days=DAYS_BEFORE) <= today


def amount_for(r: Reservation) -> float | None:
    """Te registreren bedrag: dat van de overschrijving uit de opmerking; bij een virtuele kredietkaart
    (zonder bedrag) de kamerprijs. None = Booking.com betaalt niet (de gast betaalt zelf)."""
    prepay = booking_prepay(r.remarks)
    if prepay is not None:
        return prepay
    if virtual_card(r.remarks):
        return room_price(r)
    return None


def _log(r: Reservation, ok: bool, note: str) -> None:
    guests.log_message(r.hotel_id, r.reservation_id, MESSAGE_TYPE,
                       SendResult(Channel.PMS, "Lighthouse", ok, error=None if ok else note), note=note)


def handle(hotel_id: str, stored: Reservation, lh, today: date) -> tuple[str, str | None]:
    """Eén reservatie: detailpagina lezen, controleren, registreren. Geeft (status, uitleg) terug; status is
    registered, problem, early (annuleerbaar, nog te vroeg), self (gast betaalt zelf), already (al betaald),
    cancelled of skipped. Uitleg alleen bij registered en problem (voor het robotlog)."""
    label = stored.booking_number or stored.reservation_id[:8]
    # Altijd de huidige toestand; contactgegevens zijn hier niet nodig (sneller, en geen wachttijd als ze
    # gemaskeerd blijven)
    r = lighthouse.get_reservation(hotel_id, stored.reservation_id, lh, contact=False)
    if not r.remarks or r.open_amount is None:
        # Pagina niet volledig gelezen: niet als "gast betaalt zelf" tellen, volgende run opnieuw
        raise RuntimeError("opmerking of saldo niet gevonden op de pagina")
    r.guest.first_name = r.guest.first_name or stored.guest.first_name
    r.guest.last_name = r.guest.last_name or stored.guest.last_name
    # Opmerking, transacties en annuleerbaarheid bewaren: dan moet deze reservatie pas opnieuw gelezen
    # worden als ze aan de beurt is (annuleerbaar: 2 dagen voor aankomst)
    stored.remarks, stored.transactions = r.remarks, r.transactions
    if r.non_refundable is not None:
        stored.non_refundable = r.non_refundable
    guests.save_reservation(stored, fields=("remarks", "transactions", "non_refundable"))
    if r.status == ReservationStatus.CANCELLED:
        return "cancelled", None
    amount = amount_for(r)
    if amount is None or amount <= 0:
        return "self", None  # geen overschrijving door Booking.com (de gast betaalt zelf), of geen kamerprijs
    if not due(r, today):
        return "early", None
    if already_registered(r):
        stored.payout_registered_at = stored.payout_registered_at or datetime.now(UTC)
        guests.save_reservation(stored, fields=guests.PAYOUT_FIELDS)
        return "already", None
    problem = check(r, amount)
    if problem:
        note = f"Overschrijving Booking.com niet geregistreerd: {problem}. Nakijken in Lighthouse."
        already = [m for m in guests.messages_for(hotel_id, r.reservation_id)
                   if m["message_type"] == MESSAGE_TYPE and not m["ok"] and m.get("note") == note]
        if not already:  # één melding, niet bij elke run opnieuw
            _log(stored, False, note)
        return "problem", f"{label}: {problem}"
    if not safety.may_write_pms(hotel_id, r.guest.first_name, r.guest.last_name):
        return "skipped", None
    after = lighthouse.add_payment(hotel_id, r.reservation_id, "bank_transfer", amount, COMMENT, lh,
                                   min_open=amount)
    # De betaling staat erbij (add_payment wacht daarop): onthouden, ook als het saldo hieronder niet klopt
    stored.payout_registered_at = datetime.now(UTC)
    guests.save_reservation(stored, fields=guests.PAYOUT_FIELDS)
    open_after = after.open_amount
    expected = round(r.open_amount - amount, 2)
    note = f"Overschrijving Booking.com {amount:.2f} EUR geregistreerd" + (
        f", nog open {open_after:.2f} EUR" if open_after is not None else "")
    if open_after is None or abs(open_after - expected) > 0.01:
        note += f" (verwacht nog open {expected:.2f} EUR: nakijken in Lighthouse)"
        _log(stored, False, note)
    else:
        _log(stored, True, note)
    return "registered", f"{label}: {amount:.2f} EUR" + (
        f" (nog open {open_after:.2f} EUR)" if open_after is not None else "")


def check(r: Reservation, amount: float) -> str | None:
    """Mag dit bedrag geregistreerd worden? None = ja, anders de reden (voor de melding).
    - het bedrag = de kamerprijs in de folio (zonder toeristenbelasting en extra's);
    - vermeldt Booking.com een geïnd bedrag, dan moet dat ook gelijk zijn;
    - het openstaande saldo is gekend en minstens dat bedrag (anders is er al iets betaald, bv. de virtuele
      kaart al aangerekend, of een vorige poging die toch gelukt is): nooit meer registreren dan wat open staat."""
    price = room_price(r)
    if price is None:
        return f"bedrag {amount:.2f} EUR, kamerprijs in de folio onbekend"
    if abs(price - amount) > 0.01:
        return f"bedrag in de opmerking {amount:.2f} EUR, kamerprijs in de folio {price:.2f} EUR"
    collected = booking_collected(r.remarks)
    if collected is not None and abs(collected - amount) > 0.01:
        return f"kamerprijs {amount:.2f} EUR, door Booking.com geïnd {collected:.2f} EUR"
    if r.open_amount is None:
        return "openstaand saldo niet gelezen"
    if r.open_amount < amount - 0.01:
        return f"nog maar {r.open_amount:.2f} EUR open, minder dan {amount:.2f} EUR (al iets betaald?)"
    return None


MAX_SECONDS = 4 * 60  # per run; de rest in een volgende run (wat gelezen is, wordt onthouden)


def log_idle(hotel_id: str, today: date | None = None) -> None:
    """Regel in het robotlog als er nu niets te doen is (Lighthouse wordt dan niet geopend), met waarom."""
    from hotel_checkin.processes.send_messages import switch

    started = datetime.now(UTC)
    if not switch(hotel_id, "overschrijvingen"):
        note = "schakelaar Overschrijvingen staat uit: niets gedaan"
    else:
        today = today or clock.today(hotel_id)
        cfg = workflow.config(hotel_id)
        future = [r for r in guests.list_reservations(hotel_id)
                  if r.status != ReservationStatus.CANCELLED and r.arrival >= today
                  and workflow.flow_for(hotel_id, r, cfg) == "booking"]
        done = [r for r in future if r.payout_registered_at]
        waiting = sorted((r for r in future if not r.payout_registered_at and r.remarks is not None
                          and paid_by_booking(r) and not due(r, today)), key=lambda r: r.arrival)
        flex_unread = [r for r in future if r.remarks is None and r.non_refundable is False]
        own = [r for r in future if r.remarks is not None and not paid_by_booking(r)]
        parts = [f"niets te doen nu: {len(future)} toekomstige reservaties van Booking.com",
                 f"{len(done)} geregistreerd of al betaald"]
        if waiting or flex_unread:
            nxt = min([*waiting, *flex_unread], key=lambda r: r.arrival)
            parts.append(f"{len(waiting) + len(flex_unread)} annuleerbaar, pas vanaf 2 dagen voor aankomst "
                         f"(eerstvolgende {nxt.booking_number or ''} vanaf {nxt.arrival - timedelta(days=DAYS_BEFORE):%d/%m})")
        if own:
            parts.append(f"{len(own)} zonder betaling door Booking.com (gast betaalt zelf)")
        note = ", ".join(parts)
    guests.log_robot_run(hotel_id, TASK, started, True, 0, 0, note)


def log_run(hotel_id: str, started: datetime, result: dict) -> None:
    """Eigen regel in het robotlog (taak "Overschrijvingen"). Gevonden = gelezen in Lighthouse,
    nieuw = geregistreerd. De notitie zegt per soort wat er gebeurde."""
    c = result["counts"]
    parts = [f"{result['read']} reservaties van Booking.com gelezen"]
    if c.get("registered"):
        parts.append(f"{c['registered']} overschrijving(en) geregistreerd: " + "; ".join(result["registered"]))
    else:
        parts.append("niets geregistreerd")
    if c.get("problem"):
        parts.append(f"{c['problem']} niet geregistreerd, nakijken: " + "; ".join(result["problems"]))
    if c.get("early"):
        parts.append(f"{c['early']} annuleerbaar, pas vanaf 2 dagen voor aankomst")
    if c.get("self"):
        parts.append(f"{c['self']} zonder betaling door Booking.com (gast betaalt zelf)")
    if c.get("already"):
        parts.append(f"{c['already']} al betaald (Overschrijving stond er al)")
    if c.get("error"):
        parts.append(f"{c['error']} fout bij lezen: " + "; ".join(result["errors"][:5]))
    if result["left"]:
        parts.append(f"nog {result['left']} te lezen in een volgende run (tijd op)")
    # Te doen: reservaties die nagekeken moesten worden; gedaan: geregistreerde overschrijvingen
    # Resultaat: ok; deels (skipped > 0) als enkele reservaties een fout gaven; fout alleen als niets lukte
    errors = c.get("error", 0)
    guests.log_robot_run(hotel_id, TASK, started, not errors or result["read"] > errors,
                         result["read"] + result["left"], c.get("registered", 0), ". ".join(parts), skipped=errors)


def run(hotel_id: str, lh, today: date | None = None, deadline: float | None = None) -> dict:
    """Alle toekomstige reservaties die in aanmerking komen, binnen een al geopende Lighthouse-sessie (robot).
    Eerst wie het eerst aankomt. Stopt na MAX_SECONDS (of eerder aan de deadline); de volgende run gaat verder.
    Geeft een samenvatting terug voor het robotlog (log_run)."""
    today = today or clock.today(hotel_id)
    cfg = workflow.config(hotel_id)
    from hotel_checkin.core import run_context

    stop = run_context.stop_at(MAX_SECONDS)
    if deadline is not None:
        stop = min(stop, deadline)
    todo = [r for r in sorted(guests.list_reservations(hotel_id), key=lambda x: x.arrival) if candidate(r, cfg, today)]
    result: dict = {"read": 0, "counts": {}, "registered": [], "problems": [], "errors": [], "left": 0}
    from hotel_checkin.core import progress

    progress.step(hotel_id, TASK, f"{len(todo)} reservaties na te kijken", force=True)
    for i, r in enumerate(todo):
        progress.step(hotel_id, TASK, f"{i + 1} van {len(todo)}: {r.booking_number or ''}, "
                                      f"{result['counts'].get('registered', 0)} geregistreerd tot nu")
        if time.monotonic() > stop:
            result["left"] = len(todo) - i
            break
        try:
            status, text = handle(hotel_id, r, lh, today)
        except Exception as exc:
            logging.exception("%s: overschrijving %s", hotel_id, r.booking_number)
            status, text = "error", f"{r.booking_number or r.reservation_id[:8]}: {type(exc).__name__}: {str(exc)[:160]}"
        result["read"] += 1
        result["counts"][status] = result["counts"].get(status, 0) + 1
        if text:
            {"registered": result["registered"], "problem": result["problems"], "error": result["errors"]}[status].append(text)
    return result
