"""Bouwblok: de ontbijtlijst en de kuislijst opmaken als Excel, als HTML (mail en monitor) en als korte tekst
(WhatsApp of sms). Alleen opmaak: wat erop staat, beslist het proces (processes/daily_lists.py).

Zelfde opbouw als de lijsten die het hotel met de hand maakte: per kamer een rij, een lege rij tussen de
verdiepingen, opmerkingen achteraan. Een lijst (dict):
- soort "breakfast": rows = [{"room", "count", "remark", "check"}] (check = nakijken in Lighthouse), total;
- soort "cleaning": rows = [{"room", "leave", "stay", "checkin", "remark"}], totals {"leave", "stay", "checkin"},
  controle (naam), extra_rows (vaste rijen onderaan, bv. TOILETTEN).
Een rij {"sep": True} is een lege rij (nieuwe verdieping).
"""

from __future__ import annotations

import html
import io
from datetime import date

TITLES = {"breakfast": "ONTBIJTLIJST", "cleaning": "CLEANINGLIST"}
DAYS_NL = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")


def day_text(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{DAYS_NL[d.weekday()]} {d:%d/%m/%Y}"


def file_name(data: dict, hotel_name: str) -> str:
    what = "Ontbijtlijst" if data["kind"] == "breakfast" else "Kuislijst"
    return f"{what} {hotel_name} {data['day']}.xlsx"


def subject(data: dict, hotel_name: str) -> str:
    what = "Ontbijtlijst" if data["kind"] == "breakfast" else "Kuislijst"
    return f"{hotel_name}: {what.lower()} {day_text(data['day'])}"


# ---------------------------------------------------------------- Excel


def xlsx(data: dict, hotel_name: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Blad1"
    bold, big = Font(bold=True), Font(bold=True, size=14)
    thin = Side(style="thin", color="999999")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    yellow = PatternFill("solid", fgColor="FFF2A8")
    ws["A1"], ws["B1"], ws["C1"] = TITLES[data["kind"]], "Date:", date.fromisoformat(data["day"])
    ws["A1"].font, ws["C1"].font = big, bold
    ws["C1"].number_format = "dddd dd/mm/yyyy"
    ws["E1"] = hotel_name
    if data["kind"] == "breakfast":
        head = ("KAMER", "AANTAL", "OPMERKINGEN")
        widths = (10, 10, 60)
    else:
        head = ("Kamer", "Leave", "Stay", "Check in", "REMARKS/OPMERKINGEN")
        widths = (10, 8, 8, 10, 60)
        if data.get("controle"):
            ws["D1"] = f"Controle: {data['controle']}"
    for col, (text, width) in enumerate(zip(head, widths, strict=True), 1):
        c = ws.cell(row=3, column=col, value=text)
        c.font, c.border = bold, box
        ws.column_dimensions[c.column_letter].width = width
    row = 4
    first = row
    for r in data["rows"]:
        if r.get("sep"):
            row += 1
            continue
        values = ([r["room"], r.get("count") if r.get("count") is not None else ("?" if r.get("check") else None),
                   r.get("remark") or None] if data["kind"] == "breakfast"
                  else [r["room"], "x" if r.get("leave") else None, "x" if r.get("stay") else None,
                        "check in" if r.get("checkin") else None, r.get("remark") or None])
        if str(values[0]).isdigit():
            values[0] = int(values[0])  # kamernummer als getal, zoals in de lijst met de hand
        for col, v in enumerate(values, 1):
            c = ws.cell(row=row, column=col, value=v)
            c.border = box
            c.alignment = Alignment(vertical="top", wrap_text=col == len(values))
            if r.get("check"):
                c.fill = yellow
        row += 1
    last = row - 1
    row += 1
    ws.cell(row=row, column=1, value="TOTAAL").font = bold
    if data["kind"] == "breakfast":
        ws.cell(row=row, column=2, value=f"=SUM(B{first}:B{last})").font = bold
    else:
        for col, letter, text in ((2, "B", "x"), (3, "C", "x"), (4, "D", "check in")):
            ws.cell(row=row, column=col, value=f'=COUNTIF({letter}{first}:{letter}{last},"{text}")').font = bold
        for extra in data.get("extra_rows") or []:
            row += 2
            ws.cell(row=row, column=1, value=extra).font = bold
    ws.print_options.gridLines = True
    ws.page_setup.fitToWidth = 1
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ---------------------------------------------------------------- HTML (mail en monitor)

_TD = "padding:4px 8px;border:1px solid #ccc;vertical-align:top;"
_TH = "padding:4px 8px;border:1px solid #ccc;text-align:left;background:#F4F5F8;"


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""))


def table_html(data: dict) -> str:
    """Alleen de tabel (ook voor de monitor)."""
    if data["kind"] == "breakfast":
        head = ("Kamer", "Aantal", "Opmerkingen")
    else:
        head = ("Kamer", "Leave", "Stay", "Check in", "Opmerkingen")
    body = ""
    for r in data["rows"]:
        if r.get("sep"):
            body += f'<tr><td colspan="{len(head)}" style="padding:2px;border:0;"></td></tr>'
            continue
        bg = "#FFF2A8" if r.get("check") else "#FFFFFF"
        if data["kind"] == "breakfast":
            count = r.get("count") if r.get("count") is not None else ("?" if r.get("check") else "")
            cells = [r["room"], count, r.get("remark")]
        else:
            cells = [r["room"], "x" if r.get("leave") else "", "x" if r.get("stay") else "",
                     "check in" if r.get("checkin") else "", r.get("remark")]
        body += f'<tr style="background:{bg};">' + "".join(
            f'<td style="{_TD}{"font-weight:bold;" if i == 0 else ""}">{_e(v)}</td>' for i, v in enumerate(cells)) + "</tr>"
    if data["kind"] == "breakfast":
        foot = [("Totaal", data.get("total", 0), "")]
    else:
        tot = data.get("totals", {})
        foot = [("Totaal", tot.get("leave", 0), tot.get("stay", 0), tot.get("checkin", 0), "")]
    body += "".join('<tr style="font-weight:bold;">' + "".join(f'<td style="{_TD}">{_e(v)}</td>' for v in f) + "</tr>"
                    for f in foot)
    for extra in data.get("extra_rows") or []:
        body += f'<tr><td colspan="{len(head)}" style="{_TD}font-weight:bold;">{_e(extra)}</td></tr>'
    return ('<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px;">'
            "<tr>" + "".join(f'<th style="{_TH}">{h}</th>' for h in head) + "</tr>" + body + "</table>")


def mail_html(data: dict, hotel_name: str, notes: list[str]) -> str:
    """Mail met de lijst als tabel (leesbaar op de gsm); de Excel zit als bijlage bij."""
    title = f"{'Ontbijtlijst' if data['kind'] == 'breakfast' else 'Kuislijst'} {day_text(data['day'])}"
    parts = [f'<h2 style="font-family:Arial,sans-serif;font-size:18px;">{_e(hotel_name)}: {_e(title)}</h2>']
    if data["kind"] == "cleaning" and data.get("controle"):
        parts.append(f'<p style="font-family:Arial,sans-serif;font-size:14px;">Controle: {_e(data["controle"])}</p>')
    parts += [f'<p style="font-family:Arial,sans-serif;font-size:14px;">{_e(n)}</p>' for n in notes]
    parts.append(table_html(data))
    parts.append('<p style="font-family:Arial,sans-serif;font-size:12px;color:#8A90A0;margin-top:16px;">'
                 f"Gemaakt op {_e(data.get('generated_at', '')[:16].replace('T', ' '))}. Geel = nakijken in Lighthouse. "
                 "De Excel staat in de bijlage.</p>")
    return "\n".join(parts)


# ---------------------------------------------------------------- korte tekst (WhatsApp, sms)


def summary(data: dict) -> str:
    """Eén regel (WhatsApp-sjablonen laten geen nieuwe regels toe in een variabele)."""
    rows = [r for r in data["rows"] if not r.get("sep")]
    if data["kind"] == "breakfast":
        items = [f"{r['room']}: {r['count'] if r.get('count') is not None else '?'}"
                 + (f" ({r['remark']})" if r.get("remark") else "") for r in rows]
        return f"{data.get('total', 0)} personen. " + ("; ".join(items) if items else "geen ontbijt")
    parts = []
    for key, label in (("leave", "vertrek"), ("stay", "blijvers"), ("checkin", "check in")):
        rooms = [r["room"] for r in rows if r.get(key)]
        parts.append(f"{label} {len(rooms)}" + (f" ({', '.join(rooms)})" if rooms else ""))
    notes = [f"{r['room']}: {r['remark']}" for r in rows if r.get("remark")]
    return ", ".join(parts) + (". Opmerkingen: " + "; ".join(notes) if notes else "")


def text(data: dict, hotel_name: str) -> str:
    """Volledige lijst als tekst met een regel per kamer (sms)."""
    what = "Ontbijtlijst" if data["kind"] == "breakfast" else "Kuislijst"
    lines = [f"{hotel_name} {what.lower()} {day_text(data['day'])}"]
    for r in data["rows"]:
        if r.get("sep"):
            continue
        if data["kind"] == "breakfast":
            lines.append(f"{r['room']}: {r['count'] if r.get('count') is not None else '?'}"
                         + (f" {r['remark']}" if r.get("remark") else ""))
        else:
            what = [w for k, w in (("leave", "vertrek"), ("stay", "blijft"), ("checkin", "check in")) if r.get(k)]
            if what or r.get("remark"):
                lines.append(f"{r['room']}: {', '.join(what)}" + (f" ({r['remark']})" if r.get("remark") else ""))
    if data["kind"] == "breakfast":
        lines.append(f"Totaal: {data.get('total', 0)}")
    else:
        tot = data.get("totals", {})
        lines.append(f"Vertrek {tot.get('leave', 0)}, blijvers {tot.get('stay', 0)}, check in {tot.get('checkin', 0)}")
    return "\n".join(lines)
