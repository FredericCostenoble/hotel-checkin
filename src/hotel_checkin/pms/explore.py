"""Verkenning van Lighthouse, alleen lezen, om de robot te bouwen.

    python -m hotel_checkin.pms.explore lucca
    python -m hotel_checkin.pms.explore lucca --show     # met zichtbare browser (niet in de codespace)
    python -m hotel_checkin.pms.explore lucca --page /Customer/Reservations/Detail/<id>
    python -m hotel_checkin.pms.explore lucca --detail          # detailpagina, contactgegevens getoond

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
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
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
    eye = page.locator("i.fa-eye, .fa-eye, [class*='eye']").first
    if eye.count():
        eye.click()
        page.wait_for_timeout(2000)
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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("hotel_id")
    p.add_argument("--show", action="store_true", help="zichtbare browser")
    p.add_argument("--page", action="append", help="extra pagina, bv. /Customer/Reservations/Detail/<id>")
    p.add_argument("--detail", nargs="?", const="first",
                   help="alleen de detailpagina van een reservering (uuid, of de eerste van het dashboard)")
    args = p.parse_args()

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
