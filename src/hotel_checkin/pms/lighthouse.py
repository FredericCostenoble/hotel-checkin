"""Bouwblok 4: Lighthouse lezen (en later wegschrijven), per hotel.

Via browserautomatisatie (Playwright, headless Chromium) met een aparte robotgebruiker
per hotel (zonder MFA), zie lighthouse_browser.py. Sessiecookies bewaard tussen runs.
Als Lighthouse ooit een API aanbiedt, komt er een tweede implementatie achter dezelfde functies.

Aandachtspunten:
- Pagina's altijd volledig laten laden (folio/transacties laden asynchroon).
- /Customer/Reservations opent het formulier "nieuwe reservering": niet gebruiken.
- In de lijst staan knoppen Bevestigen en Annuleren: de robot klikt daar nooit op.
- Schrijven in Lighthouse gebeurt alleen in PRD (core/safety.py).

Testen in de codespace (toont geen gastnamen):
    python -m hotel_checkin.pms.lighthouse lucca --hours 24
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from hotel_checkin.core.models import AccessCode, Reservation, ReservationStatus
from hotel_checkin.pms.lighthouse_browser import LighthouseSession
from hotel_checkin.pms.lighthouse_parse import TZ, parse_list_row

LIST_PATH = "/Customer/Reservations/List"  # standaard gesorteerd op boekdatum, nieuwste eerst
MAX_PAGES = 10


def _rows_on_page(hotel_id: str, page) -> list[Reservation]:
    out = []
    for row in page.locator("table.table-bordered > tbody > tr").all():
        cells = row.locator(":scope > td").all()
        if len(cells) < 4:
            continue
        link = row.locator("a[href*='/Reservations/Detail/']").first
        href = link.get_attribute("href") if link.count() else ""
        out.append(parse_list_row(
            hotel_id, cells[1].inner_text(), cells[2].inner_text(), cells[3].inner_text(), href or ""
        ))
    return out


def get_new_reservations(hotel_id: str, since: datetime, session: LighthouseSession | None = None) -> list[Reservation]:
    """Reservaties die sinds `since` geboekt zijn (veld "Gemaakt op"), nieuwste eerst.

    Contactgegevens (e-mail, telefoon, taal) staan niet in de lijst; die komen uit get_reservation.
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=TZ)
    if session is None:
        with LighthouseSession(hotel_id) as lh:
            return get_new_reservations(hotel_id, since, lh)

    page = session.goto(LIST_PATH)
    found: list[Reservation] = []
    for _ in range(MAX_PAGES):
        rows = _rows_on_page(hotel_id, page)
        for r in rows:
            if r.booked_at and r.booked_at < since:
                return found
            found.append(r)
        next_link = page.locator("ul.pagination a:has-text('›'), ul.pagination a[rel=next], .pagination li:last-child a").first
        if not rows or not next_link.count():
            break
        next_link.click()
        session._wait_loaded()
    return found


def get_reservation(hotel_id: str, reservation_id: str) -> Reservation:
    """Detail van één reservatie: contactgegevens, taal, betaalstatus."""
    raise NotImplementedError("Bouwblok Lighthouse (detail): volgende stap")


def store_access_code(hotel_id: str, code: AccessCode) -> None:
    """Schrijf de Salto-code weg bij de reservatie in Lighthouse (alleen PRD)."""
    raise NotImplementedError("Bouwblok Lighthouse (code wegschrijven): nog te implementeren")


def set_status(hotel_id: str, reservation_id: str, status: ReservationStatus) -> None:
    """Zet de status van de reservatie (bv. INGECHECKT), alleen PRD."""
    raise NotImplementedError("Bouwblok Lighthouse (status): nog te implementeren")


def main() -> None:
    p = argparse.ArgumentParser(description="Nieuwe reservaties uit Lighthouse tonen (alleen lezen)")
    p.add_argument("hotel_id")
    p.add_argument("--hours", type=int, default=24)
    args = p.parse_args()
    since = datetime.now(TZ) - timedelta(hours=args.hours)
    rows = get_new_reservations(args.hotel_id, since)
    for r in rows:
        print(f"{r.booking_number}  geboekt {r.booked_at:%d/%m %H:%M}  {r.arrival} > {r.departure}  "
              f"{r.guest_count or '?'} pers.  kamer {','.join(r.rooms) or '-'}  {r.source}  {r.pms_status}")
    print(f"{len(rows)} reservaties sinds {since:%d/%m %H:%M}")


if __name__ == "__main__":
    main()
