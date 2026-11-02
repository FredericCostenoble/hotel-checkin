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
import html
import re
import time
from datetime import datetime, timedelta

from hotel_checkin.core.models import AccessCode, Guest, Reservation, ReservationStatus
from hotel_checkin.pms.lighthouse_browser import LighthouseSession
from hotel_checkin.pms.lighthouse_parse import (
    TZ,
    parse_contact,
    parse_detail,
    parse_folio,
    parse_list_row,
)

LIST_PATH = "/Customer/Reservations/List"  # standaard gesorteerd op boekdatum, nieuwste eerst
_ROWS = "table.table-bordered > tbody > tr"
# Lijst klaar zodra er rijen staan. De lijst toont alle reservaties (ook oude), dus ze is nooit leeg;
# zou ze toch leeg zijn, dan na 20 s verder met wat er is.
_LIST_READY = "() => document.querySelectorAll('table.table-bordered > tbody > tr').length > 0"
MAX_PAGES = 30  # 15 per pagina; genoeg voor de eerste keer (30 dagen)


def _rows_on_page(hotel_id: str, page, skipped: list[str]) -> list[Reservation]:
    out = []
    for row in page.locator(_ROWS).all():
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

    page = session.goto(LIST_PATH, ready=_LIST_READY)
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
        # Volgende pagina: klaar zodra de eerste rij een andere is (niet wachten tot het netwerk stil is)
        first = page.locator(_ROWS).first.inner_text()
        next_link.click()
        session._wait_loaded(
            "first => { const r = document.querySelector('table.table-bordered > tbody > tr');"
            " return !!r && r.innerText !== first; }", arg=first)
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
    .map(s => ({ status: s.selectedOptions[0]?.text || '', value: s.value || '', text: txt(s.closest('tr') || s.parentElement.parentElement) }));
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
    // Regels onder Transacties, zonder het formulier om een betaling toe te voegen (de keuzelijst
    // bevat ook het woord "Overschrijving")
    transactions: (() => { const t = [...document.querySelectorAll('*')].find(e => e.childElementCount === 0 && e.textContent.trim() === 'Transacties');
                           if (!t) return [];
                           const box = (t.closest('.jarviswidget, .col-md-6, .col-lg-6') || t.parentElement.parentElement).cloneNode(true);
                           box.querySelectorAll('fieldset, form, select, input, button').forEach(e => e.remove());
                           return txt(box).split('\n').map(s => s.trim()).filter(Boolean); })(),
    // Blok "Opmerkingen:" onder Algemene informatie (betaalinfo van Booking.com, wensen van de gast, ...)
    remarks: (() => { const h = [...document.querySelectorAll('*')].find(e => e.childElementCount === 0
                        && /^Opmerkingen:?$/.test(e.textContent.trim()));
                      if (!h) return '';
                      const box = h.closest('.alert, .well, .panel, .note, div') || h.parentElement;
                      return txt(box.parentElement && txt(box).trim() === h.textContent.trim() ? box.parentElement : box); })(),
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
    # Klaar zodra de transacties ingevuld zijn (laden asynchroon); geen transactieblok: na 10 s verder
    page = session.goto(DETAIL_PATH.format(id=reservation_id), ready=_TRANSACTIONS_LOADED, timeout=10_000)
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


ROOM_STATUSES = ("none", "readyforcheckin", "checkin", "checkout")  # keuzelijst per kamer (kleur in Lighthouse)


def set_room_status(hotel_id: str, reservation_id: str, status: str, session: LighthouseSession) -> list[str]:
    """Status van elke kamer van de reservatie zetten, zoals de keuzelijst per kamer het doet (Lighthouse
    bewaart meteen). Kamers die al op die status staan, blijven zo. Bij INGECHECKT opent Lighthouse een
    venster voor zijn eigen sleutelsysteem: dat wordt gesloten zonder iets te bevestigen.
    Geeft de status per kamer terug zoals ze daarna is. Fout als Lighthouse iets anders dan Success meldt
    (bv. GuestsMissingInfo: gegevens van de gasten ontbreken)."""
    if status not in ROOM_STATUSES:
        raise ValueError(status)
    page = session.goto(DETAIL_PATH.format(id=reservation_id), ready=_TRANSACTIONS_LOADED, timeout=10_000)
    session.close_popups()
    selects = page.locator("select.btn_checkinout")
    for i in range(selects.count()):
        sel = selects.nth(i)
        if sel.input_value() == status:
            continue
        with page.expect_response(lambda r: "EditAccommodationCheckInOut" in r.url, timeout=20_000) as resp:
            sel.select_option(status)
        answer = resp.value.json() if resp.value.ok else {"status": f"HTTP {resp.value.status}"}
        if answer.get("status") != "Success":
            raise RuntimeError(f"Lighthouse weigerde status {status}: {answer.get('status')}")
        if status in ("checkin", "checkout"):
            session.close_popups()  # venster van het sleutelsysteem van Lighthouse: niets bevestigen
    return [selects.nth(i).input_value() for i in range(selects.count())]


def set_comments(hotel_id: str, reservation_id: str, compose, session: LighthouseSession) -> str:
    """De opmerking van de reservatie aanpassen (venster Bewerken bij Algemene informatie, veld Comments).
    compose(huidige tekst) geeft de nieuwe tekst; de huidige tekst wordt altijd vlak ervoor gelezen.
    Geeft de bewaarde tekst terug."""
    page = session.goto(DETAIL_PATH.format(id=reservation_id), ready=_TRANSACTIONS_LOADED, timeout=10_000)
    session.close_popups()
    page.locator("a.btnEditGeneralSettings").first.click()
    box = page.locator("#txtComments")
    box.wait_for(state="visible")
    new = compose(box.input_value())
    box.fill(new)
    # Lighthouse kijkt eerst na of de tekst een kredietkaartnummer bevat (CheckTextContainsCreditCard),
    # bewaart dan en laadt de pagina opnieuw. Nakijken met een aparte aanvraag (niet via de pagina, die
    # herlaadt): klaar zodra Lighthouse de nieuwe tekst teruggeeft, geen vaste wachttijd.
    page.locator("input[type=submit][value=Bewaren]").first.click()
    saved = None
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        resp = session.page.request.get(session.base + f"/Customer/Reservations/EditGeneralSettings/{reservation_id}",
                                        headers={"X-Requested-With": "XMLHttpRequest"})
        m = re.search(r'<textarea[^>]*id="txtComments"[^>]*>(.*?)</textarea>', resp.text(), re.DOTALL)
        value = html.unescape(m.group(1)).replace("\r\n", "\n") if m else None
        if value is not None and value.strip() == new.strip():
            saved = value
            break
        time.sleep(0.5)  # opnieuw vragen tot Lighthouse de nieuwe tekst heeft
    if saved is None:
        raise RuntimeError("Opmerking niet bewaard in Lighthouse (bv. geweigerd als kredietkaartnummer)")
    return saved


PAYMENT_METHODS = {"bank_transfer": "Overschrijving"}  # naam in de keuzelijst "Selecteer een betaalmethode"


def add_payment(hotel_id: str, reservation_id: str, method: str, amount: float, comment: str,
                session: LighthouseSession, min_open: float | None = None) -> Reservation:
    """Een betaling toevoegen onder Transacties van de reservatie (veld Selecteer een betaalmethode,
    bedrag, opmerking, knop Toevoegen). Klikt verder nergens op. Geeft de reservatie terug zoals ze
    daarna op de detailpagina staat, zodat het proces kan nakijken of de betaling erbij staat.

    Of dit mag (PRD of testgast) en wanneer, beslist het proces, niet dit blok. Met min_open: vlak voor het
    klikken nog eens nakijken dat minstens zoveel open staat (fout zonder iets te doen als dat niet zo is of
    het saldo niet te lezen is), zodat twee runs na elkaar nooit dubbel betalen."""
    label = PAYMENT_METHODS[method]
    page = session.goto(DETAIL_PATH.format(id=reservation_id), ready=_TRANSACTIONS_LOADED, timeout=10_000)
    session.close_popups()
    if min_open is not None:
        open_now = parse_folio(page.evaluate(_DETAIL_JS).get("folio_text") or "")["open"]
        if open_now is None or open_now < min_open - 0.01:
            raise RuntimeError(f"openstaand saldo {open_now} lager dan {min_open:.2f}: niets toegevoegd")
    form = page.locator("fieldset:has(select[name=PaymentMethodID])").first
    form.locator("select[name=PaymentMethodID]").select_option(label=label)
    form.locator("input[name=Value]").fill(f"{amount:.2f}")
    form.locator("input[name=Comment]").fill(comment)
    form.locator("button.AddPaymentBtn").click()
    # Klaar zodra de opmerking bij de transacties staat (niet wachten tot het netwerk stil is)
    page.wait_for_function(
        """c => { const t = [...document.querySelectorAll('*')].find(e => e.childElementCount === 0 && e.textContent.trim() === 'Transacties');
                  const b = t && (t.closest('.jarviswidget, .col-md-6, .col-lg-6') || t.parentElement.parentElement);
                  if (!b) return false; const k = b.cloneNode(true); k.querySelectorAll('fieldset').forEach(e => e.remove());
                  return k.innerText.includes(c); }""", arg=comment, timeout=20_000)
    return _read_detail(session, hotel_id, reservation_id)


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
