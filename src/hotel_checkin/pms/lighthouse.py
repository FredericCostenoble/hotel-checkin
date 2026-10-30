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
    python -m hotel_checkin.pms.lighthouse lucca --detail <uuid>
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta

from hotel_checkin.core.models import AccessCode, Guest, Reservation, ReservationStatus
from hotel_checkin.pms.lighthouse_browser import LighthouseSession
from hotel_checkin.pms.lighthouse_parse import TZ, parse_contact, parse_detail, parse_list_row

LIST_PATH = "/Customer/Reservations/List"  # standaard gesorteerd op boekdatum, nieuwste eerst
MAX_PAGES = 30  # 15 per pagina; genoeg voor de eerste keer (30 dagen)


def _rows_on_page(hotel_id: str, page, skipped: list[str]) -> list[Reservation]:
    out = []
    for row in page.locator("table.table-bordered > tbody > tr").all():
        cells = row.locator(":scope > td").all()
        if len(cells) < 4:
            continue
        link = row.locator("a[href*='/Reservations/Detail/']").first
        href = link.get_attribute("href") if link.count() else ""
        try:
            out.append(parse_list_row(
                hotel_id, cells[1].inner_text(), cells[2].inner_text(), cells[3].inner_text(), href or ""
            ))
        except ValueError as exc:
            # Eén onleesbare rij mag de rest niet tegenhouden; zonder gastgegevens melden
            number = re.search(r"[A-Z]{2,5}-\d+-\d+", cells[1].inner_text())
            skipped.append(f"{number.group(0) if number else 'rij'}: {exc}")
    return out


def get_new_reservations(
    hotel_id: str, since: datetime, session: LighthouseSession | None = None,
    skipped: list[str] | None = None,
) -> list[Reservation]:
    """Reservaties die sinds `since` geboekt zijn (veld "Gemaakt op"), nieuwste eerst.

    Contactgegevens (e-mail, telefoon, taal) staan niet in de lijst; die komen uit get_reservation.
    Rijen die niet gelezen konden worden, komen in `skipped` (reservatienummer en reden).
    """
    skipped = skipped if skipped is not None else []
    if since.tzinfo is None:
        since = since.replace(tzinfo=TZ)
    if session is None:
        with LighthouseSession(hotel_id) as lh:
            return get_new_reservations(hotel_id, since, lh, skipped)

    page = session.goto(LIST_PATH)
    found: list[Reservation] = []
    for _ in range(MAX_PAGES):
        rows = _rows_on_page(hotel_id, page, skipped)
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


DETAIL_PATH = "/Customer/Reservations/Detail/{id}"

# Leest de detailpagina uit. Klikt alleen op het oog bij Contactgegevens (toont e-mail en
# telefoon, haalt ze op via /Customer/Reservations/ContactDetails/{id}); wijzigt niets.
_DETAIL_JS = r"""() => {
  const txt = e => (e ? e.innerText : '') || '';
  const widget = title => {
    const h = [...document.querySelectorAll('h1,h2,h3,h4,header *')].find(e => e.textContent.trim() === title);
    return h ? (h.closest('.jarviswidget') || h.parentElement.parentElement) : null;
  };
  const rooms = [...document.querySelectorAll('select')]
    .filter(s => [...s.options].some(o => o.text === 'INGECHECKT'))
    .map(s => ({ status: s.selectedOptions[0]?.text || '', text: txt(s.closest('tr') || s.parentElement.parentElement) }));
  const contactName = document.querySelector('#contact-name');
  const trans = [...document.querySelectorAll('*')].find(e => e.childElementCount === 0 && e.textContent.trim() === 'Transacties');
  return {
    title: txt(document.querySelector('h1')),
    contact_name: txt(contactName),
    contact_line: txt(contactName && contactName.closest('li')),
    phone: txt(document.querySelector('[data-field="telephone"]')),
    email: txt(document.querySelector('[data-field="email"]')),
    general: txt(widget('Algemene informatie')),
    rooms,
    paid_text: txt(trans && (trans.closest('.jarviswidget, .col-md-6, .col-lg-6') || trans.parentElement.parentElement)),
    // Hele folio (lijnen links, transacties rechts): eerste blok rond "Transacties" waar ook "Totaal" in staat
    folio_text: (() => { let b = trans; while (b && b !== document.body && !/\bTotaal\b/.test(b.innerText || '')) b = b.parentElement;
                         return b && b !== document.body ? txt(b) : ''; })(),
  };
}"""


# Transacties laden asynchroon: klaar als het blok meer toont dan zijn titel en niets meer laadt.
_TRANSACTIONS_LOADED = r"""() => {
  const t = [...document.querySelectorAll('*')].find(e => e.childElementCount === 0 && e.textContent.trim() === 'Transacties');
  if (!t) return false;
  const box = t.closest('.jarviswidget, .col-md-6, .col-lg-6') || t.parentElement.parentElement;
  return !box.querySelector('.fa-spin, .spinner, .loading') && box.innerText.trim().length > 20;
}"""


def _read_detail(session: LighthouseSession, hotel_id: str, reservation_id: str) -> Reservation:
    page = session.goto(DETAIL_PATH.format(id=reservation_id))
    try:
        page.wait_for_function(_TRANSACTIONS_LOADED, timeout=10_000)
    except Exception:  # noqa: BLE001 - geen transactieblok: verder met wat er is
        pass
    session.close_popups()
    toggle = page.locator(".js-masked-contact-toggle").first
    if toggle.count() and "*" in (page.locator('[data-field="email"]').first.inner_text() or "*"):
        toggle.click()
        page.wait_for_function(
            "() => !(document.querySelector('[data-field=\"email\"]')?.innerText || '').includes('*')",
            timeout=15_000,
        )
    return parse_detail(hotel_id, reservation_id, page.evaluate(_DETAIL_JS))


def get_reservation(hotel_id: str, reservation_id: str, session: LighthouseSession | None = None) -> Reservation:
    """Detail van één reservatie: contactgegevens, land (en taal), status per kamer, betaling, annulering."""
    if session is None:
        with LighthouseSession(hotel_id) as lh:
            return _read_detail(lh, hotel_id, reservation_id)
    return _read_detail(session, hotel_id, reservation_id)


CONTACT_PATH = "/Customer/Reservations/ContactDetails/{id}"


def get_contact(hotel_id: str, reservation_id: str, session: LighthouseSession | None = None) -> Guest:
    """Alleen e-mail, telefoon en land van de gast.

    Snel: vraagt rechtstreeks op wat het oog-icoon ophaalt (geen pagina openen, niets klikken).
    Lukt dat niet (ander antwoord, sessie verlopen), dan via de volledige detailpagina.
    Guest.first_name/last_name zijn leeg bij de snelle weg; country alleen als de detailpagina gelezen werd.
    """
    if session is None:
        with LighthouseSession(hotel_id) as lh:
            return get_contact(hotel_id, reservation_id, lh)
    try:
        resp = session.page.request.get(
            session.base + CONTACT_PATH.format(id=reservation_id),
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        found = parse_contact(resp.text()) if resp.ok and "/Customer/" in resp.url else None
    except Exception:  # noqa: BLE001 - dan de volledige pagina
        found = None
    if found:
        return Guest(first_name="", last_name="", email=found["email"], phone=found["phone"], language="",
                     country=None)
    return _read_detail(session, hotel_id, reservation_id).guest


def connect(hotel_id: str) -> LighthouseSession:
    """Eén aangemelde sessie voor meerdere oproepen na elkaar:

        with lighthouse.connect("lucca") as lh:
            for r in lighthouse.get_new_reservations("lucca", since, lh): ...
            detail = lighthouse.get_reservation("lucca", r.reservation_id, lh)
    """
    return LighthouseSession(hotel_id)


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
    p.add_argument("--detail", help="toon de detailgegevens van deze reservatie (uuid), zonder namen")
    args = p.parse_args()
    if args.detail:
        r = get_reservation(args.hotel_id, args.detail)
        print(f"{r.booking_number}  {r.arrival} > {r.departure}  kamers {','.join(r.rooms) or '-'}  "
              f"status {r.status.value} ({r.pms_status})  betaald {r.paid}  land {r.guest.country}  "
              f"taal {r.guest.language}  e-mail {'ja' if r.guest.email else 'nee'}  "
              f"telefoon {'ja' if r.guest.phone else 'nee'}")
        return
    since = datetime.now(TZ) - timedelta(hours=args.hours)
    rows = get_new_reservations(args.hotel_id, since)
    for r in rows:
        print(f"{r.booking_number}  geboekt {r.booked_at:%d/%m %H:%M}  {r.arrival} > {r.departure}  "
              f"{r.guest_count or '?'} pers.  kamer {','.join(r.rooms) or '-'}  {r.source}  {r.pms_status}")
    print(f"{len(rows)} reservaties sinds {since:%d/%m %H:%M}")


if __name__ == "__main__":
    main()
