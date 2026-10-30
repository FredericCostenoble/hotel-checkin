"""Verkenning van Lighthouse, alleen lezen, om de robot te bouwen.

    python -m hotel_checkin.pms.explore lucca
    python -m hotel_checkin.pms.explore lucca --show     # met zichtbare browser (niet in de codespace)
    python -m hotel_checkin.pms.explore lucca --page /Customer/Reservations/Detail/<id>
    python -m hotel_checkin.pms.explore lucca --detail          # detailpagina, contactgegevens getoond
    python -m hotel_checkin.pms.explore lucca --status [<id>]   # hoe de status (inchecken) werkt, klikt NIETS

Klikt niets aan en wijzigt niets. Schrijft naar lighthouse-explore/ (niet in git):
- <pagina>.png: schermafbeelding, alleen voor jezelf (bevat gastgegevens)
- structuur.md: opbouw van de pagina's ZONDER gastgegevens (kolomtitels, velden,
  linkpatronen met id's vervangen). Dit bestand mag gedeeld worden.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from hotel_checkin.pms.lighthouse_browser import LighthouseSession

# Let op: /Customer/Reservations opent het formulier "nieuwe reservering"; niet gebruiken.
PAGES = [
    "/Customer/Dashboard",
    "/Customer/Reservations/List",
    "/Customer/Settings/KeySystems",
    "/Customer/Settings/OnlineCheckIn",
]
OUT = Path("lighthouse-explore")

# Draait in de pagina: verzamelt structuur, geen inhoud van cellen.
_JS = r"""
() => {
  const txt = el => (el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 60);
  const pattern = h => h.replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, '{uuid}').replace(/\d{2,}/g, '{n}');
  const tables = [...document.querySelectorAll('table')].map(t => ({
    id: t.id, cls: t.className,
    headers: [...t.querySelectorAll('thead th, tr:first-child th')].map(txt),
    rows: t.querySelectorAll('tbody tr').length,
    cellClasses: [...(t.querySelector('tbody tr')?.children || [])].map(c => c.className).slice(0, 20),
  }));
  const fields = [...document.querySelectorAll('input, select, textarea, button')].map(f => ({
    tag: f.tagName.toLowerCase(), type: f.type || '', name: f.name || '', id: f.id || '',
    label: f.tagName === 'BUTTON' ? txt(f) : (f.labels?.[0] ? txt(f.labels[0]) : (f.placeholder || '')),
  }));
  const links = [...new Set([...document.querySelectorAll('a[href]')]
    .map(a => pattern(new URL(a.href, location.href).pathname)))].sort();
  const headings = [...document.querySelectorAll('h1,h2,h3,h4,legend,.panel-title,.card-title')].map(txt).filter(Boolean);
  return { url: pattern(location.pathname), title: document.title, headings, tables, fields, links };
}
"""


def _md(info: dict) -> str:
    out = [f"## {info['url']}", f"Titel: {info['title']}", ""]
    if info["headings"]:
        out += ["Koppen: " + " | ".join(dict.fromkeys(info["headings"])), ""]
    for i, t in enumerate(info["tables"], 1):
        out.append(f"Tabel {i} (id={t['id']!r}, class={t['cls']!r}, {t['rows']} rijen)")
        out.append("  kolommen: " + " | ".join(t["headers"]))
        if t["cellClasses"]:
            out.append("  celklassen: " + " | ".join(t["cellClasses"]))
    out.append("")
    out.append("Velden en knoppen:")
    seen = set()
    for f in info["fields"]:
        key = (f["tag"], f["type"], f["name"], f["id"], f["label"])
        if key in seen or f["type"] == "hidden":
            continue
        seen.add(key)
        out.append(f"  {f['tag']} type={f['type']} name={f['name']} id={f['id']} label={f['label']!r}")
    out.append("")
    out.append("Linkpatronen:")
    out += [f"  {link}" for link in info["links"]]
    return "\n".join(out) + "\n\n"


def _mask(text: str, names: list[str]) -> str:
    """Gastgegevens weglaten: namen, e-mail, telefoon, lange vrije tekst (opmerkingen, memo)."""
    out = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        # Meldingen: "Nieuwe reservering" / "Reservering geannuleerd" gevolgd door "Naam / datums"
        if i and lines[i - 1] in ("Nieuwe reservering", "Reservering geannuleerd", "Reservering gewijzigd") and " / " in line:
            line = "<naam> / " + line.split(" / ", 1)[1]
        line = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<email>", line)
        line = re.sub(r"\+?\d[\d ./()-]{6,}\d", "<tel>", line)
        for n in names:
            if len(n) > 1:
                line = re.sub(re.escape(n), "<naam>", line, flags=re.I)
        if len(line) > 80:
            line = f"<tekst {len(line)} tekens>"
        out.append(line)
    return "\n".join(out)


def explore_detail(lh: LighthouseSession, path: str) -> str:
    """Detailpagina van een reservering: tekst voor en na het tonen van de verborgen contactgegevens,
    met gastgegevens weggelaten. Klikt alleen op het oog-icoon (tonen), wijzigt niets."""
    page = lh.goto(path)
    page.wait_for_timeout(3000)  # folio en transacties laden asynchroon
    title = page.locator("h1, h2, .page-title").first.inner_text() if page.locator("h1, h2, .page-title").count() else ""
    guest = title.split(" - ", 1)[1] if " - " in title else ""
    names = [w.strip(",") for w in guest.split() if not w.startswith("(")]  # landcode (DE) behouden
    report = ["## Detail (voor tonen)", _mask(page.locator("body").inner_text(), names), ""]
    lh.close_popups()
    # Alleen het oog-icoon in het blok Contactgegevens (er staat er ook een bij de betalingen)
    eye = page.locator(
        "xpath=//*[normalize-space(text())='Contactgegevens']"
        "/ancestor::*[.//*[contains(@class,'fa-eye')]][1]//*[contains(@class,'fa-eye')]"
    ).first
    if eye.count():
        requests: list[str] = []
        page.on("request", lambda r: requests.append(f"{r.method} {re.sub(r'[0-9a-f]{8}-[0-9a-f-]{27,}', '{uuid}', r.url)}"))
        eye.click()
        page.wait_for_timeout(3000)
        report += ["## Verzoeken na klik op het oog", *[f"- {x}" for x in requests if "mylighthouse" in x], ""]
        # Opbouw van het blok Contactgegevens, met alle teksten en waarden gemaskeerd
        html = page.evaluate(r"""() => {
          const h = [...document.querySelectorAll('*')].find(e => e.childElementCount === 0 && e.textContent.trim() === 'Contactgegevens');
          let box = h;
          while (box && !box.querySelector('[class*="fa-eye"]')) box = box.parentElement;
          if (!box) return 'blok niet gevonden';
          const c = box.cloneNode(true);
          const mask = v => /@|\d{5,}/.test(v) ? '<waarde>' : v;
          const walk = n => {
            if (n.nodeType === 3) { const t = n.textContent.trim(); if (t && !/^[A-Z]:$|^\*+$|^Contactgegevens$/.test(t)) n.textContent = '<tekst>'; }
            if (n.nodeType === 1) { for (const a of [...n.attributes]) n.setAttribute(a.name, mask(a.value)); }
            n.childNodes.forEach(walk);
          };
          walk(c);
          return c.outerHTML.replace(/\s+/g, ' ').slice(0, 6000);
        }""")
        report += ["## HTML blok Contactgegevens (gemaskeerd)", html, ""]
        page.screenshot(path=str(OUT / "detail-na-oog.png"), full_page=True)
        report += ["## Detail (na tonen contactgegevens)", _mask(page.locator("body").inner_text(), names), ""]
    else:
        report.append("Geen oog-icoon gevonden.")
    selects = page.evaluate("""() => [...document.querySelectorAll('select')].map(s => ({
        id: s.id, name: s.name, selected: s.selectedOptions[0]?.text || '',
        options: [...s.options].map(o => o.text).slice(0, 12) }))""")
    report.append("## Keuzelijsten")
    report += [f"- id={x['id']} name={x['name']} gekozen={x['selected']!r} opties={x['options']}" for x in selects]
    return "\n".join(report) + "\n"


# --status: hoe verandert Lighthouse de status van een reservering (KLAAR OM IN TE CHECKEN,
# INGECHECKT, UITGECHECKT)? Alleen lezen: geen enkele klik, geen waarde wijzigen. Na het aanmelden
# wordt elk verzoek dat geen GET is geblokkeerd, zodat er zeker niets verandert.
_STATUS_JS = r"""(words) => {
  const uuid = v => String(v).replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, '{uuid}');
  const mask = v => /@|\d{6,}/.test(v) ? '<waarde>' : uuid(v).slice(0, 200);
  const attrs = el => Object.fromEntries([...el.attributes].filter(a => a.name !== 'style').map(a => [a.name, mask(a.value)]));
  const handlers = el => {
    try {
      const ev = window.jQuery && jQuery._data && jQuery._data(el, 'events');
      if (!ev) return {};
      return Object.fromEntries(Object.entries(ev).map(([k, hs]) => [k, hs.map(h => uuid(h.handler.toString()).slice(0, 2500))]));
    } catch (e) { return { error: String(e) }; }
  };
  const formOf = el => { const f = el.closest('form'); return f ? { action: uuid(f.action || ''), method: f.method,
      inputs: [...f.querySelectorAll('input,select')].map(i => `${i.type || i.tagName.toLowerCase()} ${i.name}`).slice(0, 40) } : null; };
  const statusSelects = [...document.querySelectorAll('select')]
    .filter(s => [...s.options].some(o => /INGECHECKT|IN TE CHECKEN|UITGECHECKT/i.test(o.text)))
    .map(s => ({ attrs: attrs(s), options: [...s.options].map(o => `${o.value} = ${o.text}`), selected: s.selectedOptions[0]?.text || '',
                 handlers: handlers(s), form: formOf(s),
                 parentHandlers: s.parentElement ? handlers(s.parentElement) : {} }));
  const re = new RegExp(words.join('|'), 'i');
  const buttons = [...document.querySelectorAll('a,button,li,[role=menuitem],[onclick]')]
    .filter(e => e.childElementCount < 4 && re.test((e.innerText || e.title || '').trim()) && (e.innerText || '').trim().length < 40)
    .slice(0, 40)
    .map(e => ({ tag: e.tagName.toLowerCase(), text: (e.innerText || e.title || '').trim(), attrs: attrs(e), handlers: handlers(e), form: formOf(e),
                 visible: !!(e.offsetWidth || e.offsetHeight) }));
  const inline = [...document.querySelectorAll('script:not([src])')].map(s => s.textContent)
    .flatMap(t => t.split('\n').filter(l => re.test(l) || /\/Customer\/[A-Za-z]+\/[A-Za-z]*(Status|Check|State)/.test(l)))
    .map(l => uuid(l.trim()).slice(0, 300)).slice(0, 60);
  const scripts = [...document.querySelectorAll('script[src]')].map(s => s.src);
  return { url: uuid(location.pathname), statusSelects, buttons, inline, scripts };
}"""

_STATUS_WORDS = ["Inchecken", "Uitchecken", "Ingecheckt", "Uitgecheckt", "In te checken", "No.?show", "Check.?in", "Check.?out", "Status"]


def _script_hits(page, scripts: list[str]) -> list[str]:
    """Regels uit de JavaScript-bestanden van Lighthouse die over status of inchecken gaan (alleen lezen)."""
    hits = []
    for src in scripts:
        if "mylighthouse" not in src and not src.startswith("/"):
            continue
        try:
            body = page.evaluate("u => fetch(u).then(r => r.text())", src)
        except Exception:  # noqa: BLE001
            continue
        for m in re.finditer(r"[^;{}\n]{0,160}(?:Check[Ii]n|CheckOut|ChangeStatus|SetStatus|UpdateStatus|/Status)[^;{}\n]{0,160}", body):
            hits.append(f"{src.rsplit('/', 1)[-1][:60]}: {re.sub(r'[0-9a-f]{8}-[0-9a-f-]{27,}', '{uuid}', m.group(0).strip())}")
            if len(hits) > 150:
                return hits
    return hits


def explore_status(lh: LighthouseSession, detail_id: str | None) -> str:
    page = lh.goto("/Customer/Dashboard")  # meldt aan indien nodig
    blocked: list[str] = []

    def guard(route):
        if route.request.method != "GET":
            blocked.append(f"{route.request.method} {re.sub(r'[0-9a-f]{8}-[0-9a-f-]{27,}', '{uuid}', route.request.url)}")
            return route.abort()
        return route.continue_()
    page.route("**/*", guard)  # vanaf nu kan er niets meer gewijzigd worden

    report = ["# Status van een reservering wijzigen (verkenning, niets uitgevoerd)", ""]
    paths = ["/Customer/Dashboard"]
    if not detail_id:
        link = page.locator("a[href*='/Customer/Reservations/Detail/']").first
        if link.count():
            detail_id = link.get_attribute("href").rstrip("/").rsplit("/", 1)[-1]
    if detail_id:
        paths.append(f"/Customer/Reservations/Detail/{detail_id}")
    paths.append("/Customer/Planboard")
    all_scripts: list[str] = []
    for path in paths:
        page = lh.goto(path)
        page.wait_for_timeout(4000)  # alles laten laden (folio, planbord)
        info = page.evaluate(_STATUS_JS, _STATUS_WORDS)
        all_scripts += info["scripts"]
        report += [f"## {info['url']}", "", "### Keuzelijsten met de status"]
        for s in info["statusSelects"]:
            report += [f"- attributen: {s['attrs']}", f"  gekozen: {s['selected']!r}", f"  opties: {s['options']}",
                       f"  formulier: {s['form']}", f"  handlers: {s['handlers']}", f"  handlers ouder: {s['parentHandlers']}"]
        if not info["statusSelects"]:
            report.append("- geen")
        report += ["", "### Knoppen en menu-items (inchecken, uitchecken, status)"]
        for b in info["buttons"]:
            report += [f"- {b['tag']} {b['text']!r} zichtbaar={b['visible']} attributen={b['attrs']}",
                       f"  formulier: {b['form']}", f"  handlers: {b['handlers']}"]
        report += ["", "### Regels in scripts op de pagina", *[f"    {x}" for x in info["inline"]], ""]
    report += ["## Regels in de JavaScript-bestanden", *[f"    {x}" for x in _script_hits(page, list(dict.fromkeys(all_scripts)))], ""]
    report += ["## Geblokkeerde verzoeken (geen GET, dus niet uitgevoerd)", *([f"- {x}" for x in blocked] or ["- geen"]), ""]
    return "\n".join(report) + "\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("hotel_id")
    p.add_argument("--show", action="store_true", help="zichtbare browser")
    p.add_argument("--page", action="append", help="extra pagina, bv. /Customer/Reservations/Detail/<id>")
    p.add_argument("--detail", nargs="?", const="first",
                   help="alleen de detailpagina van een reservering (uuid, of de eerste van het dashboard)")
    p.add_argument("--status", nargs="?", const="", help="hoe de status gewijzigd wordt (uuid of de eerste van het dashboard); klikt niets")
    args = p.parse_args()

    if args.status is not None:
        OUT.mkdir(exist_ok=True)
        with LighthouseSession(args.hotel_id, headless=not args.show, debug_dir=OUT) as lh:
            (OUT / "status.md").write_text(explore_status(lh, args.status or None), encoding="utf-8")
        print(f"Klaar: {OUT}/status.md (zonder gastgegevens). Er werd niets aangeklikt of gewijzigd.")
        return

    if args.detail:
        OUT.mkdir(exist_ok=True)
        with LighthouseSession(args.hotel_id, headless=not args.show, debug_dir=OUT) as lh:
            path = f"/Customer/Reservations/Detail/{args.detail}"
            if args.detail == "first":
                lh.goto("/Customer/Dashboard")
                link = lh.page.locator("a[href*='/Customer/Reservations/Detail/']").first
                path = link.get_attribute("href").split("mylighthouse.com")[-1]
            (OUT / "detail.md").write_text(explore_detail(lh, path), encoding="utf-8")
        print(f"Klaar: {OUT}/detail.md (zonder gastgegevens) en {OUT}/detail-na-oog.png (alleen voor jou).")
        return

    OUT.mkdir(exist_ok=True)
    report = []
    with LighthouseSession(args.hotel_id, headless=not args.show, debug_dir=OUT) as lh:
        paths = PAGES + (args.page or [])
        # Eerste reservering van het dashboard erbij, om de detailpagina te leren kennen
        lh.goto("/Customer/Dashboard")
        detail = lh.page.locator("a[href*='/Customer/Reservations/Detail/']").first
        if detail.count():
            paths.append(detail.get_attribute("href").split("mylighthouse.com")[-1])
        for path in paths:
            page = lh.goto(path)
            name = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27,}", "id", path.lower())
            name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")[:60]
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
            report.append(_md(page.evaluate(_JS)))
            print(f"ok  {path}")
    (OUT / "structuur.md").write_text("".join(report), encoding="utf-8")
    print(f"Klaar: {OUT}/structuur.md (deelbaar) en schermafbeeldingen (alleen voor jou).")


if __name__ == "__main__":
    main()
