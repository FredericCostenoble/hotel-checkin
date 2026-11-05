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
import logging
import re
import time
from datetime import datetime, timedelta

from hotel_checkin.core.models import AccessCode, Guest, Reservation, ReservationStatus
from hotel_checkin.pms.lighthouse_browser import LighthouseSession
from hotel_checkin.pms.lighthouse_parse import (
    BREAKFAST_LABEL,
    TZ,
    charge_days_query,
    parse_charge,
    parse_contact,
    parse_detail,
    parse_folio,
    parse_list_row,
    parse_planboard,
    rate_plans_from,
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


def list_page(hotel_id: str, number: int, session: LighthouseSession, skipped: list[str] | None = None
              ) -> list[Reservation]:
    """Eén pagina van de reservatielijst (15 per pagina, nieuwste boeking eerst; pagina 0 = de nieuwste).
    Leeg = voorbij de laatste pagina."""
    page = session.goto(f"{LIST_PATH}?CurrentPage={number}", ready=_LIST_READY, timeout=8_000)
    return _rows_on_page(hotel_id, page, skipped if skipped is not None else [])


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
  const trans = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,legend,strong,b,span,div,p')].find(e => [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim() === 'Transacties');
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
    transactions: (() => { const t = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,legend,strong,b,span,div,p')].find(e => [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim() === 'Transacties');
                           if (!t) return [];
                           const box = (t.closest('.jarviswidget, .col-md-6, .col-lg-6') || t.parentElement.parentElement).cloneNode(true);
                           box.querySelectorAll('fieldset, form, select, input, button').forEach(e => e.remove());
                           return txt(box).split('\n').map(s => s.trim()).filter(Boolean); })(),
    // Blok "Opmerkingen:" onder Algemene informatie (betaalinfo van Booking.com, wensen van de gast, ...)
    // De kop heeft een icoon (paperclip) en staat in een <p>; de opmerking zelf in de volgende <p>, samen in een <li>.
    remarks: (() => { const own = e => [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
                      const h = [...document.querySelectorAll('strong,b,span,p,div,label,h4,h5')]
                        .find(e => /^Opmerkingen:?$/.test(own(e)) || (e.childElementCount === 0 && /^Opmerkingen:?$/.test(e.textContent.trim())));
                      if (!h) return '';
                      let box = h.closest('li') || h.closest('p')?.parentElement || h.parentElement;
                      while (box && box !== document.body && txt(box).replace(/Opmerkingen:?/, '').trim() === '') box = box.parentElement;
                      return box && box !== document.body ? txt(box).replace(/^\s*Opmerkingen:?\s*/, '') : ''; })(),
    // Hele folio (lijnen links, transacties rechts): eerste blok rond "Transacties" waar ook "Totaal" in staat
    // Extra's in de folio met hun venster "Bewerken" (3 puntjes): daar staan de dagen, bv. bij ontbijt
    folio_charges: [...document.querySelectorAll('.js-folio-component-overview tr')]
      .map(r => ({ label: (r.querySelector('td.componentline')?.innerText || '').trim(),
                   url: r.querySelector('a[data-loadingmodal*="CreateOrUpdateFolioCharge"]')?.getAttribute('data-loadingmodal') || '' }))
      .filter(x => x.label && x.url),
    folio_text: (() => { let b = trans; while (b && b !== document.body && !/\bTotaal\b/.test(b.innerText || '')) b = b.parentElement;
                         return b && b !== document.body ? txt(b) : ''; })(),
  };
}"""


# Transacties laden asynchroon: klaar als het blok meer toont dan zijn titel en niets meer laadt.
_TRANSACTIONS_LOADED = r"""() => {
  const t = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,legend,strong,b,span,div,p')].find(e => [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim() === 'Transacties');
  if (!t) return false;
  const box = t.closest('.jarviswidget, .col-md-6, .col-lg-6') || t.parentElement.parentElement;
  // Het laadsymbool staat altijd in de kop (verborgen als het klaar is): alleen een zichtbaar telt
  const busy = [...box.querySelectorAll('.fa-spin, .spinner, .loading, .paymentloader')].some(e => e.offsetParent !== null);
  return !busy && /Openstaand saldo|volledig betaald|Saldo/i.test(box.innerText);
}"""


def _read_detail(session: LighthouseSession, hotel_id: str, reservation_id: str, contact: bool = True) -> Reservation:
    # Klaar zodra de transacties ingevuld zijn (laden asynchroon); geen transactieblok: na 10 s verder
    page = session.goto(DETAIL_PATH.format(id=reservation_id), ready=_TRANSACTIONS_LOADED, timeout=10_000)
    session.close_popups()
    d = page.evaluate(_DETAIL_JS)
    if contact and "*" in (d.get("email") or "") + (d.get("phone") or ""):
        # Gemaskeerd: rechtstreeks opvragen wat het oog-icoon ophaalt (zelfde als manueel op het oogje
        # klikken, maar zonder klik en zonder wachten tot het op het scherm staat)
        found = _contact_request(session, reservation_id)
        if found:
            d["email"], d["phone"] = found["email"] or "", found["phone"] or ""
        else:
            logging.info("%s: contactgegevens niet opgehaald bij %s", hotel_id, reservation_id)
    reservation = parse_detail(hotel_id, reservation_id, d)
    # Nagekeken (explore --charge-ids, 05/11/2026): het venster en de dagen opvragen wijzigt niets in Lighthouse, het
    # nummer van de regel blijft hetzelfde. (Het venster in de pagina zelf openen deed dat wel: dat doet de robot niet.)
    _read_charge_days(hotel_id, session, reservation, d.get("folio_charges") or [])
    return reservation


def _read_charge_days(hotel_id: str, session: LighthouseSession, reservation: Reservation, charges: list[dict]) -> None:
    """Voor ontbijtregels in de folio: welke dagen en hoeveel per dag, uit het venster "Bewerken" (wat de 3 puntjes
    openen). Opgevraagd zoals dat venster het doet, zonder iets aan te klikken of te bewaren. Komt bij de folioregel:
    {"days": {"2026-11-06": 1}, "room": "22"}. Lukt het niet, dan blijft de regel zoals ze was."""
    lines = [x for x in reservation.folio if BREAKFAST_LABEL.search(x["label"]) and not rate_plans_from(x["label"])]
    if lines and not any(BREAKFAST_LABEL.search(c["label"]) for c in charges):
        for x in lines:
            x["days_error"] = "venster Bewerken niet gevonden in de folio"
    for charge in charges:
        if not BREAKFAST_LABEL.search(charge["label"]):
            continue
        line = next((x for x in lines if "days" not in x and x["label"].strip() == charge["label"].strip()), None)
        if line is None:
            continue
        try:
            info = _charge_days(session, charge["url"])
            error = "" if info else "geen gekozen dag in het venster"
        except Exception as exc:  # noqa: BLE001 - dan zonder dagen (nakijken op de lijst, met de reden)
            info, error = None, f"{type(exc).__name__}: {str(exc)[:80]}"
        if info and info["days"]:
            line["days"], line["room"] = info["days"], info["room"]
        else:
            line["days_error"] = error  # komt op de ontbijtlijst bij "nakijken"
            logging.info("%s: dagen van %s niet gelezen bij %s: %s", hotel_id, charge["label"],
                         reservation.reservation_id, error)


CHARGE_DAYS_PATH = "/Customer/Folios/CalculateDays"  # wat het venster "Bewerken" opvraagt voor het blok "Dagen"


def _charge_days(session: LighthouseSession, modal_url: str) -> dict | None:
    """Venster "Bewerken" van een extra (kamer, aantal per nacht) en de dagen die het zelf opvraagt, zonder het venster
    te openen. {"room", "per_night", "days": {"2026-11-06": 1}} of None."""
    headers = {"X-Requested-With": "XMLHttpRequest"}
    modal = session.page.request.get(session.base + html.unescape(modal_url), headers=headers)
    if not modal.ok or "/Customer/" not in modal.url:
        return None
    body = modal.text()
    query = charge_days_query(body)
    if not query:
        return None
    days = session.page.request.get(session.base + CHARGE_DAYS_PATH, params=query, headers=headers)
    if not days.ok or "/Customer/" not in days.url:
        return None
    return parse_charge(body, days.text())


def _contact_request(session: LighthouseSession, reservation_id: str) -> dict | None:
    """E-mail en telefoon via de opvraging achter het oog-icoon. None als dat niet lukt."""
    try:
        resp = session.page.request.get(
            session.base + CONTACT_PATH.format(id=reservation_id),
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        return parse_contact(resp.text()) if resp.ok and "/Customer/" in resp.url else None
    except Exception:  # noqa: BLE001
        return None


def get_reservation(hotel_id: str, reservation_id: str, session: LighthouseSession | None = None,
                    contact: bool = True) -> Reservation:
    """Detail van één reservatie: contactgegevens, land (en taal), status per kamer, betaling, annulering.
    contact=False: de gemaskeerde contactgegevens niet openklikken (sneller, bv. voor de betaling)."""
    if session is None:
        with LighthouseSession(hotel_id) as lh:
            return _read_detail(lh, hotel_id, reservation_id, contact)
    return _read_detail(session, hotel_id, reservation_id, contact)


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
    found = _contact_request(session, reservation_id)
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
    open_now = parse_folio(page.evaluate(_DETAIL_JS).get("folio_text") or "")["open"]
    if min_open is not None and (open_now is None or open_now < min_open - 0.01):
        raise RuntimeError(f"openstaand saldo {open_now} lager dan {min_open:.2f}: niets toegevoegd")
    form = page.locator("fieldset:has(select[name=PaymentMethodID])").first
    form.locator("select[name=PaymentMethodID]").select_option(label=label)
    form.locator("input[name=Value]").fill(f"{amount:.2f}")
    form.locator("input[name=Comment]").fill(comment)
    form.locator("button.AddPaymentBtn").click()
    # Klaar zodra het openstaande saldo veranderd is. Lighthouse toont de opmerking niet bij de transactie
    # (alleen "Overschrijving, Betaald € 362,00"), dus daarop wachten liep altijd in een time-out, terwijl
    # de betaling wel geboekt was.
    before = "" if open_now is None else f"{open_now:.2f}".replace(".", ",")
    page.wait_for_function(
        """b => { const t = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,legend,strong,b,span,div,p')].find(e => [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim() === 'Transacties');
                  const box = t && (t.closest('.jarviswidget, .col-md-6, .col-lg-6') || t.parentElement.parentElement);
                  if (!box || [...box.querySelectorAll('.fa-spin, .paymentloader')].some(e => e.offsetParent !== null)) return false;
                  const m = box.innerText.replace(/\u00a0/g, ' ').match(/Openstaand saldo van €\\s*(-?[\\d.]+,\\d{2})/);
                  if (!m) return /volledig betaald/i.test(box.innerText);
                  return m[1].replace(/\\./g, '') !== b; }""", arg=before.replace(".", ""), timeout=20_000)
    return _read_detail(session, hotel_id, reservation_id)


_PAY_MODAL = 'a[data-loadingmodal*="/Customer/PaymentRequest/index/"]'  # kaarticoon "Online transactie toevoegen"


def create_payment_request(hotel_id: str, reservation_id: str, send_to: str, template: str, language: str,
                           session: LighthouseSession) -> float:
    """Een betaalverzoek (online transactie, type Betaling, Stuur verzoek) voor het openstaande saldo maken,
    zoals het kaarticoontje bij de folio. De mail gaat naar `send_to` (de eigen mailbox, nooit de gast): het
    veld "Stuur e-mail naar" wordt op "Een ander e-mailadres" gezet en vlak voor het versturen nagekeken.
    Geeft het bedrag terug. Fout zonder iets te versturen als iets niet klopt. Of en wanneer: het proces."""
    page = session.goto(DETAIL_PATH.format(id=reservation_id), ready=_TRANSACTIONS_LOADED, timeout=10_000)
    session.close_popups()
    page.locator(_PAY_MODAL).first.click()
    form = page.locator("#SaveFormPaymentRequest")
    form.wait_for(state="attached", timeout=15_000)
    modal = page.locator(".modal:has(#SaveFormPaymentRequest)").first
    modal.locator('a[data-fieldvalue="Payment"]:visible').first.click(timeout=10_000)
    # "Stuur verzoek" staat er per soort transactie; alleen de zichtbare, en alleen als het nog niet gekozen is
    if form.locator("[name=ActionSubType]").input_value() != "SendRequest":
        modal.locator('a[data-fieldvalue="SendRequest"]:visible').first.click(timeout=10_000)
    page.wait_for_function("() => document.querySelector('#SaveFormPaymentRequest [name=ActionType]')?.value === 'Payment'"
                           " && document.querySelector('#SaveFormPaymentRequest [name=ActionSubType]')?.value === 'SendRequest'",
                           timeout=5_000)
    modal.locator('input[name=requestChargesType][value="0"]:visible').first.check(timeout=10_000)  # openstaand saldo
    # Ontvanger: altijd "een ander e-mailadres" (lege waarde) met de eigen mailbox
    modal.locator("select.js-sendtoselect:visible").first.select_option(value="", timeout=10_000)
    modal.locator("input[name=SendToCustom]:visible").first.fill(send_to, timeout=10_000)
    modal.locator("select.js-templateselect:visible").first.select_option(label=template, timeout=10_000)
    langs = modal.locator("select.js-languageselect:visible").first
    if language in [o.get_attribute("value") for o in langs.locator("option").all()]:
        langs.select_option(value=language)
    check = page.evaluate("""() => { const m = document.querySelector('#SaveFormPaymentRequest');
        const sel = m.querySelector('select.js-sendtoselect');
        const amount = [...m.querySelectorAll('input[type=number]')].find(i => i.offsetParent !== null);
        return { to: m.querySelector('[name=SendToCustom]').value, choice: sel ? sel.value : null,
                 type: m.querySelector('[name=ActionType]').value, sub: m.querySelector('[name=ActionSubType]').value,
                 amount: amount ? parseFloat(amount.value) : null }; }""")
    if check["to"] != send_to or check["choice"] not in ("", None) or check["type"] != "Payment" \
            or check["sub"] != "SendRequest" or not check["amount"] or check["amount"] <= 0:
        modal.locator('input[value="Sluiten"]').first.click()
        raise RuntimeError(f"betaalverzoek niet verstuurd, venster niet zoals verwacht: {check}")
    modal.locator("#SaveFormPaymentRequestSubmit").first.click(timeout=10_000)
    # Klaar zodra het venster dicht is (Lighthouse bewaart en verstuurt de mail)
    page.wait_for_function("() => { const m = document.querySelector('#SaveFormPaymentRequest');"
                           " return !m || !m.closest('.modal') || m.closest('.modal').offsetParent === null; }",
                           timeout=20_000)
    return float(check["amount"])


PLANBOARD_PATH = "/Customer/Planboard/{start}/{end}"  # planbord voor een periode (HTML, zonder te klikken)
LABELS_PATH = "/Customer/Planboard/UpdateLabelsAccomodation"  # wat het menu Labels op het planbord doet

def reservation_labels(hotel_id: str, reservation_id: str, arrival, departure, session: LighthouseSession) -> dict:
    """Labels op het planbord per kamer van een reservatie, en welk nummer elk label heeft.
    Geeft {"rooms": [{"accommodation_id", "labels": [label-id], "unit"}], "names": {naam: label-id}}.
    Alleen lezen: het planbord van die periode wordt opgevraagd, niet geopend of aangeklikt."""
    resp = session.page.request.get(session.base + PLANBOARD_PATH.format(start=arrival.isoformat(),
                                                                         end=departure.isoformat()))
    if not resp.ok or "/Customer/" not in resp.url:
        raise RuntimeError(f"planbord niet gelezen ({resp.status})")
    return parse_planboard(resp.text(), reservation_id)


def add_label(hotel_id: str, reservation_id: str, accommodation_id: str, current: list[str], label_id: str,
              session: LighthouseSession) -> None:
    """Een label toevoegen aan een kamer van een reservatie, zoals het menu Labels op het planbord.
    Lighthouse bewaart de hele lijst: de bestaande labels gaan mee, er wordt er alleen een bijgezet.
    Of dit mag en wanneer, beslist het proces."""
    labels = list(dict.fromkeys([*current, label_id]))
    resp = session.page.request.post(session.base + LABELS_PATH, form={
        "reservationid": reservation_id, "accomodationid": accommodation_id, "labels": ",".join(labels)},
        headers={"X-Requested-With": "XMLHttpRequest"})
    if not resp.ok:
        raise RuntimeError(f"label niet bewaard ({resp.status})")


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
