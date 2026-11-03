"""Bouwblok: het overzicht van de aankomsten en de waarschuwingen als HTML-mail opmaken (voor het hotel,
in het Nederlands). Alleen opmaak: wat erin staat, beslist het proces (processes/oversight.py)."""

from __future__ import annotations

import html

_OK, _BAD, _NA = "#1E6B3A", "#A33A3A", "#8A90A0"


def _cell(value, key: str = "") -> str:
    if value is False and key == "betaald":  # nog niet betaald is geen fout
        return f'<td style="color:{_NA};padding:4px 8px;">nee</td>'
    if value is True:
        return f'<td style="color:{_OK};padding:4px 8px;">ja</td>'
    if value is False:
        return f'<td style="color:{_BAD};padding:4px 8px;font-weight:bold;">nee</td>'
    return f'<td style="color:{_NA};padding:4px 8px;">{html.escape(str(value or "-"))}</td>'


COLUMNS = (("kamer", "Kamer"), ("gast", "Gast"), ("via", "Via"), ("contact", "Contact"), ("betaald", "Kamer betaald"),
           ("code", "Code"), ("code_mail", "Code-mail"), ("lighthouse", "Code in Lighthouse"))


def overview_html(title: str, intro: list[str], sections: list[tuple[str, list[dict]]], monitor_url: str) -> str:
    """sections: (titel, rijen); een rij: kolommen hierboven plus "problemen" (lijst, rood bovenaan), "info"
    (lijst, grijs: goed om te weten, geen fout) en "nummer"."""
    parts = [f'<h2 style="font-family:Arial,sans-serif;font-size:18px;">{html.escape(title)}</h2>']
    parts += [f'<p style="font-family:Arial,sans-serif;font-size:14px;">{html.escape(p)}</p>' for p in intro]
    for name, rows in sections:
        parts.append(f'<h3 style="font-family:Arial,sans-serif;font-size:15px;margin-top:20px;">{html.escape(name)} '
                     f'({len(rows)})</h3>')
        if not rows:
            parts.append('<p style="font-family:Arial,sans-serif;font-size:13px;color:#8A90A0;">Geen aankomsten.</p>')
            continue
        head = "".join(f'<th style="text-align:left;padding:4px 8px;border-bottom:1px solid #ccc;">{t}</th>'
                       for _, t in COLUMNS)
        body = ""
        for r in sorted(rows, key=lambda x: (not x["problemen"], str(x.get("kamer")))):
            bg = "#FDECEC" if r["problemen"] else "#FFFFFF"
            cells = "".join(_cell(r.get(k), k) if k in ("betaald", "code", "code_mail", "lighthouse")
                            else f'<td style="padding:4px 8px;">{html.escape(str(r.get(k) or ""))}</td>' for k, _ in COLUMNS)
            body += f'<tr style="background:{bg};">{cells}</tr>'
            if r["problemen"]:
                body += (f'<tr style="background:{bg};"><td></td><td colspan="{len(COLUMNS) - 1}" '
                         f'style="padding:0 8px 6px;color:{_BAD};font-size:13px;">'
                         + html.escape(f"{r.get('nummer', '')}: " + "; ".join(r["problemen"])) + "</td></tr>")
            elif r.get("info"):
                body += (f'<tr style="background:{bg};"><td></td><td colspan="{len(COLUMNS) - 1}" '
                         f'style="padding:0 8px 6px;color:{_NA};font-size:13px;">'
                         + html.escape(f"{r.get('nummer', '')}: " + "; ".join(r["info"])) + "</td></tr>")
        parts.append(f'<table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;">'
                     f"<tr>{head}</tr>{body}</table>")
    parts.append(f'<p style="font-family:Arial,sans-serif;font-size:13px;margin-top:20px;">Opvolgen en opnieuw '
                 f'versturen: <a href="{html.escape(monitor_url)}">{html.escape(monitor_url)}</a></p>')
    return "\n".join(parts)
