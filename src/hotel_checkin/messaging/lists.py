"""Bouwblok: de ontbijtlijst en de schoonmaaklijst opmaken als Excel, als HTML (mail en monitor) en als korte tekst
(WhatsApp of sms). Alleen opmaak: wat erop staat, beslist het proces (processes/daily_lists.py).

Alle teksten op de lijsten in het Engels (de ploeg in de keuken en de schoonmaakploeg spreekt geen Nederlands).
Zelfde opbouw als de lijsten die het hotel met de hand maakte: per kamer een rij, een lege rij tussen de
verdiepingen, opmerkingen achteraan. Een lijst (dict):
- soort "breakfast": rows = [{"room", "desc", "count", "remark", "check"}] (check = nakijken in Lighthouse), total;
- soort "cleaning": rows = [{"room", "desc", "leave", "stay", "checkin", "remark"}], totals {"leave", "stay", "checkin"},
  controle (naam), extra_rows (vaste rijen onderaan, bv. TOILETTEN).
Een rij {"sep": True} is een lege rij (nieuwe verdieping).
"""

from __future__ import annotations

import html
import io
from datetime import date

TITLES = {"breakfast": "BREAKFAST LIST", "cleaning": "CLEANING LIST"}
NAMES = {"breakfast": "Breakfast list", "cleaning": "Cleaning list"}
DAYS = {"en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
        "nl": ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")}


def day_text(day: str, lang: str = "en") -> str:
    """Dag zoals op de lijst (Engels); lang="nl" voor het robotlogboek."""
    d = date.fromisoformat(day)
    return f"{DAYS[lang][d.weekday()]} {d:%d/%m/%Y}"


def file_name(data: dict, hotel_name: str) -> str:
    return f"{NAMES[data['kind']]} {hotel_name} {data['day']}.xlsx"


def subject(data: dict, hotel_name: str) -> str:
    return f"{hotel_name}: {NAMES[data['kind']].lower()} {day_text(data['day'])}"


# ---------------------------------------------------------------- Excel


def xlsx(data: dict, hotel_name: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    bold, big = Font(bold=True), Font(bold=True, size=14)
    thin = Side(style="thin", color="999999")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    yellow = PatternFill("solid", fgColor="FFF2A8")  # nakijken
    todo = PatternFill("solid", fgColor="FFFF00")  # opmerking voor de schoonmaakploeg (zoals in de lijst van het hotel)
    ws["A1"], ws["B1"], ws["C1"] = TITLES[data["kind"]], "Date:", date.fromisoformat(data["day"])
    ws["A1"].font, ws["C1"].font = big, bold
    ws["C1"].number_format = "[$-809]ddd dd/mm/yyyy"  # Engelse dagnaam (Sun 08/11/2026), ook in een Nederlandse Excel
    ws.merge_cells("C1:D1")  # anders te smal voor de datum (#####)
    ws["G1" if data["kind"] == "cleaning" else "E1"] = hotel_name
    if data["kind"] == "breakfast":
        head = ("ROOM", "TYPE", "PERSONS", "REMARKS")
        widths = (8, 24, 10, 60)
    else:
        head = ("Room", "Type", "Leave", "Stay", "Check in", "REMARKS")
        widths = (8, 24, 8, 8, 10, 60)
        if data.get("controle"):
            ws["E1"] = f"Checked by: {data['controle']}"
    center = {3, 4, 5} if data["kind"] == "cleaning" else {3}  # x, check in en aantal: gecentreerd
    for col, (text, width) in enumerate(zip(head, widths, strict=True), 1):
        c = ws.cell(row=3, column=col, value=text)
        c.font, c.border = bold, box
        c.alignment = Alignment(horizontal="center" if col in center or col == len(head) else None)
        ws.column_dimensions[c.column_letter].width = width
    row = 4
    first = row
    for r in data["rows"]:
        if r.get("sep"):
            row += 1
            continue
        values = ([r["room"], r.get("desc") or None,
                   r.get("count") if r.get("count") is not None else ("?" if r.get("check") else None),
                   r.get("remark") or None] if data["kind"] == "breakfast"
                  else [r["room"], r.get("desc") or None, "x" if r.get("leave") else None,
                        "x" if r.get("stay") else None, "check in" if r.get("checkin") else None,
                        r.get("remark") or None])
        if str(values[0]).isdigit():
            values[0] = int(values[0])  # kamernummer als getal, zoals in de lijst met de hand
        for col, v in enumerate(values, 1):
            c = ws.cell(row=row, column=col, value=v)
            c.border = box
            c.alignment = Alignment(vertical="top", wrap_text=col == len(values),
                                    horizontal="center" if col in center else None)
            if r.get("check"):
                c.fill = yellow
            elif data["kind"] == "cleaning" and col == len(values) and v:
                c.fill, c.font = todo, bold  # iets te doen voor de schoonmaakploeg: in het geel en vet
        row += 1
    last = row - 1
    row += 1
    ws.cell(row=row, column=1, value="TOTAL").font = bold
    if data["kind"] == "breakfast":
        c = ws.cell(row=row, column=3, value=f"=SUM(C{first}:C{last})")
        c.font, c.alignment = bold, Alignment(horizontal="center")
    else:
        for col, letter, text in ((3, "C", "x"), (4, "D", "x"), (5, "E", "check in")):
            c = ws.cell(row=row, column=col, value=f'=COUNTIF({letter}{first}:{letter}{last},"{text}")')
            c.font, c.alignment = bold, Alignment(horizontal="center")
        for extra in data.get("extra_rows") or []:
            row += 2
            ws.cell(row=row, column=1, value=extra).font = bold
    ws.print_options.gridLines = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True  # afdrukken op één pagina breed (opmerkingen niet op een 2e blad)
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ---------------------------------------------------------------- pdf (WhatsApp naar het personeel)


def pdf_name(data: dict) -> str:
    """Bestandsnaam van de pdf (zo staat ze in WhatsApp), zonder spaties: ze komt ook in de link."""
    return f"{data['kind']}-list-{data['day']}.pdf"


def _latin(value) -> str:
    """De standaardletters van een pdf kennen alleen Latin-1: andere tekens (emoji, ...) worden een vraagteken."""
    return str(value if value is not None else "").encode("latin-1", "replace").decode("latin-1")


def pdf(data: dict, hotel_name: str) -> bytes:
    """Zelfde lijst als de Excel, als pdf op A4: opent met één tik op een gsm en is zo af te drukken."""
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    breakfast = data["kind"] == "breakfast"
    doc = FPDF(orientation="P", unit="mm", format="A4")
    doc.set_auto_page_break(auto=True, margin=12)
    doc.set_margins(10, 10, 10)
    doc.add_page()
    doc.set_font("Helvetica", "B", 16)
    doc.cell(0, 8, _latin(f"{TITLES[data['kind']]}  {day_text(data['day'])}"), new_x="LMARGIN", new_y="NEXT")
    doc.set_font("Helvetica", "", 11)
    doc.cell(0, 6, _latin(hotel_name), new_x="LMARGIN", new_y="NEXT")
    if not breakfast and data.get("controle"):
        doc.cell(0, 6, _latin(f"Checked by: {data['controle']}"), new_x="LMARGIN", new_y="NEXT")
    doc.ln(3)
    if breakfast:
        head = ("Room", "Type", "Persons", "Remarks")
        widths = (16, 52, 18, 104)
        mid = {2}
    else:
        head = ("Room", "Type", "Leave", "Stay", "Check in", "Remarks")
        widths = (16, 46, 14, 14, 18, 82)
        mid = {2, 3, 4}
    check = FontFace(fill_color=(255, 242, 168))  # nakijken in Lighthouse
    todo = FontFace(emphasis="BOLD", fill_color=(255, 255, 0))  # iets te doen voor de schoonmaakploeg
    bold = FontFace(emphasis="BOLD")
    doc.set_font("Helvetica", "", 10)
    with doc.table(col_widths=widths, line_height=6, first_row_as_headings=True,
                   headings_style=FontFace(emphasis="BOLD", fill_color=(244, 245, 248))) as table:
        row = table.row()
        for h in head:
            row.cell(h)
        for r in data["rows"]:
            if r.get("sep"):
                row = table.row()
                for _ in head:
                    row.cell("")
                continue
            if breakfast:
                count = r.get("count") if r.get("count") is not None else ("?" if r.get("check") else "")
                cells = [r["room"], r.get("desc"), count, r.get("remark")]
            else:
                cells = [r["room"], r.get("desc"), "x" if r.get("leave") else "", "x" if r.get("stay") else "",
                         "check in" if r.get("checkin") else "", r.get("remark")]
            row = table.row()
            for i, v in enumerate(cells):
                style = check if r.get("check") else None
                if not breakfast and i == len(cells) - 1 and v and not r.get("check"):
                    style = todo
                elif i == 0 and not r.get("check"):
                    style = bold
                row.cell(_latin(v), style=style, align="C" if i in mid else "L")
        tot = data.get("totals", {})
        foot = (["Total", "", str(data.get("total", 0)), ""] if breakfast
                else ["Total", "", str(tot.get("leave", 0)), str(tot.get("stay", 0)), str(tot.get("checkin", 0)), ""])
        row = table.row()
        for i, v in enumerate(foot):
            row.cell(v, style=bold, align="C" if i in mid else "L")
    for extra in data.get("extra_rows") or []:
        doc.ln(4)
        doc.set_font("Helvetica", "B", 11)
        doc.cell(0, 6, _latin(extra), new_x="LMARGIN", new_y="NEXT")
    return bytes(doc.output())


# ---------------------------------------------------------------- HTML (mail en monitor)

# Kolommen en totaal per taal: verstuurd wordt altijd Engels; Nederlands alleen om te bekijken in de monitor
HEAD = {"en": {"breakfast": ("Room", "Type", "Persons", "Remarks"),
               "cleaning": ("Room", "Type", "Leave", "Stay", "Check in", "Remarks"), "total": "Total"},
        "nl": {"breakfast": ("Kamer", "Type", "Aantal", "Opmerkingen"),
               "cleaning": ("Kamer", "Type", "Vertrek", "Blijft", "Check in", "Opmerkingen"), "total": "Totaal"}}

_TD = "padding:4px 8px;border:1px solid #ccc;vertical-align:top;"
_TH = "padding:4px 8px;border:1px solid #ccc;text-align:left;background:#F4F5F8;"


def _e(value) -> str:
    return html.escape(str(value if value is not None else ""))


def table_html(data: dict, lang: str = "en") -> str:
    """Alleen de tabel (ook voor de monitor). lang = "nl" alleen om te bekijken; de opmerkingen blijven zoals ze zijn."""
    words = HEAD.get(lang, HEAD["en"])
    head = words[data["kind"]]
    mid = {2, 3, 4} if data["kind"] == "cleaning" else {2}  # aantallen en x: gecentreerd, ook het totaal
    body = ""
    for r in data["rows"]:
        if r.get("sep"):
            body += f'<tr><td colspan="{len(head)}" style="padding:2px;border:0;"></td></tr>'
            continue
        bg = "#FFF2A8" if r.get("check") else "#FFFFFF"
        if data["kind"] == "breakfast":
            count = r.get("count") if r.get("count") is not None else ("?" if r.get("check") else "")
            cells = [r["room"], r.get("desc"), count, r.get("remark")]
        else:
            cells = [r["room"], r.get("desc"), "x" if r.get("leave") else "", "x" if r.get("stay") else "",
                     "check in" if r.get("checkin") else "", r.get("remark")]
        def style(i, v, cells=cells, mid=mid, r=r):
            extra = "font-weight:bold;" if i == 0 else ""
            extra += "text-align:center;" if i in mid else ""
            if data["kind"] == "cleaning" and i == len(cells) - 1 and v and not r.get("check"):
                extra += "background:#FFFF00;font-weight:bold;"  # iets te doen voor de schoonmaakploeg
            return extra

        body += f'<tr style="background:{bg};">' + "".join(
            f'<td style="{_TD}{style(i, v)}">{_e(v)}</td>' for i, v in enumerate(cells)) + "</tr>"
    if data["kind"] == "breakfast":
        foot = [(words["total"], "", data.get("total", 0), "")]
    else:
        tot = data.get("totals", {})
        foot = [(words["total"], "", tot.get("leave", 0), tot.get("stay", 0), tot.get("checkin", 0), "")]
    body += "".join('<tr style="font-weight:bold;">' + "".join(
        f'<td style="{_TD}{"text-align:center;" if i in mid else ""}">{_e(v)}</td>' for i, v in enumerate(f)) + "</tr>"
        for f in foot)
    for extra in data.get("extra_rows") or []:
        body += f'<tr><td colspan="{len(head)}" style="{_TD}font-weight:bold;">{_e(extra)}</td></tr>'
    return ('<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:14px;">'
            "<tr>" + "".join(f'<th style="{_TH}">{h}</th>' for h in head) + "</tr>" + body + "</table>")


def mail_html(data: dict, hotel_name: str, notes: list[str]) -> str:
    """Mail met de lijst als tabel (leesbaar op de gsm); de Excel zit als bijlage bij."""
    title = f"{NAMES[data['kind']]} {day_text(data['day'])}"
    parts = [f'<h2 style="font-family:Arial,sans-serif;font-size:18px;">{_e(hotel_name)}: {_e(title)}</h2>']
    if data["kind"] == "cleaning" and data.get("controle"):
        parts.append(f'<p style="font-family:Arial,sans-serif;font-size:14px;">Checked by: {_e(data["controle"])}</p>')
    parts += [f'<p style="font-family:Arial,sans-serif;font-size:14px;">{_e(n)}</p>' for n in notes]
    parts.append(table_html(data))
    parts.append('<p style="font-family:Arial,sans-serif;font-size:12px;color:#8A90A0;margin-top:16px;">'
                 f"Made on {_e(data.get('generated_at', '')[:16].replace('T', ' '))}. The Excel file is attached.</p>")
    return "\n".join(parts)


# ---------------------------------------------------------------- korte tekst (WhatsApp, sms)


def summary(data: dict) -> str:
    """Eén regel (WhatsApp-sjablonen laten geen nieuwe regels toe in een variabele)."""
    rows = [r for r in data["rows"] if not r.get("sep")]
    if data["kind"] == "breakfast":
        items = [f"{r['room']}: {r['count'] if r.get('count') is not None else '?'}"
                 + (f" ({r['remark']})" if r.get("remark") else "") for r in rows]
        return f"{data.get('total', 0)} persons. " + ("; ".join(items) if items else "no breakfast")
    parts = []
    for key, label in (("leave", "leave"), ("stay", "stay"), ("checkin", "check in")):
        rooms = [r["room"] for r in rows if r.get(key)]
        parts.append(f"{label} {len(rooms)}" + (f" ({', '.join(rooms)})" if rooms else ""))
    notes = [f"{r['room']}: {r['remark']}" for r in rows if r.get("remark")]
    return ", ".join(parts) + (". Remarks: " + "; ".join(notes) if notes else "")


def text(data: dict, hotel_name: str) -> str:
    """Volledige lijst als tekst met een regel per kamer (sms)."""
    lines = [f"{hotel_name} {NAMES[data['kind']].lower()} {day_text(data['day'])}"]
    for r in data["rows"]:
        if r.get("sep"):
            continue
        if data["kind"] == "breakfast":
            # zoals in de pdf: een lege kamer (geen ontbijt) niet vermelden; "?" alleen als het aantal na te kijken is
            count = r.get("count") if r.get("count") is not None else ("?" if r.get("check") else "")
            if count == "" and not r.get("remark"):
                continue
            lines.append(f"{r['room']}: " + " ".join(str(x) for x in (count, r.get("remark")) if x not in ("", None)))
        else:
            what = [w for k, w in (("leave", "leave"), ("stay", "stay"), ("checkin", "check in")) if r.get(k)]
            if what or r.get("remark"):
                lines.append(f"{r['room']}: {', '.join(what)}" + (f" ({r['remark']})" if r.get("remark") else ""))
    if data["kind"] == "breakfast":
        lines.append(f"Total: {data.get('total', 0)}")
    else:
        tot = data.get("totals", {})
        lines.append(f"Leave {tot.get('leave', 0)}, stay {tot.get('stay', 0)}, check in {tot.get('checkin', 0)}")
    return "\n".join(lines)
