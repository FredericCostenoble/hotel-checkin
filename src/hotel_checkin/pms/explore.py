"""Verkenning van Lighthouse, alleen lezen, om de robot te bouwen.

    python -m hotel_checkin.pms.explore lucca
    python -m hotel_checkin.pms.explore lucca --show     # met zichtbare browser (niet in de codespace)
    python -m hotel_checkin.pms.explore lucca --page /Customer/Reservations/Detail/<id>

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

PAGES = ["/Customer/Dashboard", "/Customer/Reservations", "/Customer/Planboard"]
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


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("hotel_id")
    p.add_argument("--show", action="store_true", help="zichtbare browser")
    p.add_argument("--page", action="append", help="extra pagina, bv. /Customer/Reservations/Detail/<id>")
    args = p.parse_args()

    OUT.mkdir(exist_ok=True)
    report = []
    with LighthouseSession(args.hotel_id, headless=not args.show, debug_dir=OUT) as lh:
        for path in PAGES + (args.page or []):
            page = lh.goto(path)
            name = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")[:60]
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
            report.append(_md(page.evaluate(_JS)))
            print(f"ok  {path}")
    (OUT / "structuur.md").write_text("".join(report), encoding="utf-8")
    print(f"Klaar: {OUT}/structuur.md (deelbaar) en schermafbeeldingen (alleen voor jou).")


if __name__ == "__main__":
    main()
