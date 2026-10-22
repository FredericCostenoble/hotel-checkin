"""Bouwblok sjablonen en vertaling: maakt van een berichttype, een taal en gastgegevens
een kant-en-klaar bericht (onderwerp, HTML-mail, tekstversie en SMS/WhatsApp-tekst).

- Teksten: src/hotel_checkin/messaging/texts/<taal>.toml (nl, fr, en, de).
- Hotelgegevens, uren en kleuren: config/hotel.toml (velden zoals {hotel_naam}, {receptie_van}).
- Ontbreekt een taal, dan valt het terug op Engels.
- Een veld zonder waarde blijft zichtbaar als {veldnaam}, zodat een fout opvalt.

Berichttypes: bevestiging, herinnering, info_pincode, aan_de_deur (alleen SMS/WhatsApp).

Testmails sturen in de codespace (alle mails, alle talen, met voorbeeldgegevens):
    python -m hotel_checkin.messaging.templates jouw@adres.be
    python -m hotel_checkin.messaging.templates jouw@adres.be nl,fr
"""

from __future__ import annotations

import html
import os
import sys
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TEXTS_DIR = Path(__file__).parent / "texts"
# config/hotel.toml naast src/ (repo, codespace) of naast het pakket (Azure-deployment in api/)
_CONFIG_CANDIDATES = [
    Path(__file__).resolve().parents[3] / "config" / "hotel.toml",
    Path(__file__).resolve().parents[2] / "config" / "hotel.toml",
]
DEFAULT_CONFIG = next((p for p in _CONFIG_CANDIDATES if p.exists()), _CONFIG_CANDIDATES[0])
LANGUAGES = ("nl", "fr", "en", "de")
FALLBACK_LANGUAGE = "en"
EMAIL_MESSAGES = ("bevestiging", "herinnering", "info_pincode")


@dataclass
class RenderedMessage:
    subject: str | None
    html: str | None
    text: str | None
    sms: str


class _Fields(dict):
    """Ontbrekende velden blijven staan als {naam}."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@lru_cache
def load_hotel_config(path: str | None = None) -> dict:
    with open(path or os.environ.get("HOTEL_CONFIG", DEFAULT_CONFIG), "rb") as f:
        return tomllib.load(f)


@lru_cache
def load_texts(language: str) -> dict:
    file = TEXTS_DIR / f"{language}.toml"
    if not file.exists():
        file = TEXTS_DIR / f"{FALLBACK_LANGUAGE}.toml"
    with open(file, "rb") as f:
        return tomllib.load(f)


def _config_fields(config: dict) -> dict[str, str]:
    fields: dict[str, str] = {}
    for section, values in config.items():
        for key, value in values.items():
            fields[f"{section}_{key}"] = str(value)
    return fields


def _fill(text: str, fields: dict) -> str:
    return text.format_map(fields)


def render(message: str, language: str, data: dict[str, str]) -> RenderedMessage:
    """Stel een bericht samen. `data` bevat de gastgegevens, bv. voornaam, aankomst, pincode."""
    config = load_hotel_config()
    texts = load_texts(language)
    fields = _Fields({**_config_fields(config), **data})
    if "token" in data and "checkin_link" not in data:
        fields["checkin_link"] = _fill(config["checkin"]["formulier_url"], fields)

    t = texts[message]
    sms = _fill(t["sms"], fields)
    if message not in EMAIL_MESSAGES:
        return RenderedMessage(subject=None, html=None, text=None, sms=sms)

    subject = _fill(t["onderwerp"], fields)
    return RenderedMessage(
        subject=subject,
        html=_render_html(t, texts["algemeen"], fields, config, language),
        text=_render_text(t, texts["algemeen"], fields),
        sms=sms,
    )


# ---------------------------------------------------------------- tekstversie


def _render_text(t: dict, common: dict, f: dict) -> str:
    lines = [_fill(t["aanhef"], f), ""]
    for block in t["blokken"]:
        if block.get("titel"):
            lines.append(_fill(block["titel"], f).upper())
        kind = block["type"]
        if kind == "text":
            lines += [_fill(p, f) for p in block["alineas"]]
        elif kind == "details":
            lines += [f"{_fill(k, f)}: {_fill(v, f)}" for k, v in block["rijen"]]
        elif kind == "highlight":
            lines.append(_fill(block["waarde"], f))
            lines += [_fill(p, f) for p in block.get("alineas", [])]
        elif kind == "list":
            lines += [f"- {_fill(i, f)}" for i in block["items"]]
        elif kind == "button":
            lines.append(f"{_fill(block['tekst'], f)}: {_fill(block['link'], f)}")
        lines.append("")
    lines += [
        _fill(t["afsluiting"], f),
        "",
        _fill(common["team"], f),
        f["hotel_adres"],
        f"{f['hotel_telefoon']} | {f['hotel_email']}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- HTML-versie
# Opmaak met tabellen en inline stijlen: dat werkt in Outlook, Gmail en op gsm.

FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def _e(text: str) -> str:
    return html.escape(text, quote=True)


def _gap(height: int) -> str:
    """Verticale witruimte die ook Outlook respecteert (vaste regelhoogte)."""
    return (
        f'<div style="height:{height}px;line-height:{height}px;font-size:{height}px;'
        f'mso-line-height-rule:exactly;">&nbsp;</div>'
    )


def _render_html(t: dict, common: dict, f: dict, config: dict, language: str) -> str:
    c = config["kleuren"]
    p_style = f"margin:0 0 14px 0;font-family:{FONT};font-size:15px;line-height:1.6;color:{c['tekst']};"
    h_style = (
        f"margin:24px 0 10px 0;font-family:{FONT};font-size:12px;letter-spacing:2px;"
        f"text-transform:uppercase;font-weight:bold;color:{c['accent_donker']};"
    )

    parts: list[str] = [f'<p style="{p_style}">{_e(_fill(t["aanhef"], f))}</p>']
    for block in t["blokken"]:
        if block.get("titel") and block["type"] != "highlight":
            parts.append(f'<p style="{h_style}">{_e(_fill(block["titel"], f))}</p>')
        kind = block["type"]
        if kind == "text":
            parts += [f'<p style="{p_style}">{_e(_fill(p, f))}</p>' for p in block["alineas"]]
        elif kind == "details":
            rows = "".join(
                f'<tr><td style="padding:8px 12px;font-family:{FONT};font-size:14px;color:{c["accent_donker"]};'
                f'border-bottom:1px solid #E3E6ED;width:45%;">{_e(_fill(k, f))}</td>'
                f'<td style="padding:8px 12px;font-family:{FONT};font-size:14px;color:{c["tekst"]};'
                f'border-bottom:1px solid #E3E6ED;font-weight:bold;">{_e(_fill(v, f))}</td></tr>'
                for k, v in block["rijen"]
            )
            parts.append(
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                f'style="border-collapse:collapse;background:{c["achtergrond"]};">{rows}</table>'
                f"{_gap(18)}"
            )
        elif kind == "highlight":
            extra = "".join(
                f'<p style="margin:6px 0 0 0;font-family:{FONT};font-size:14px;color:{c["tekst"]};">{_e(_fill(p, f))}</p>'
                for p in block.get("alineas", [])
            )
            parts.append(
                f"{_gap(8)}"
                f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
                f'<tr><td align="center" style="padding:22px 16px;background:{c["achtergrond"]};'
                f'border:2px solid {c["accent"]};">'
                f'<p style="margin:0 0 8px 0;font-family:{FONT};font-size:12px;letter-spacing:2px;'
                f'text-transform:uppercase;color:{c["accent_donker"]};">{_e(_fill(block["titel"], f))}</p>'
                f'<p style="margin:0 0 8px 0;font-family:{FONT};font-size:36px;letter-spacing:8px;'
                f'font-weight:bold;color:{c["tekst"]};">{_e(_fill(block["waarde"], f))}</p>'
                f"{extra}</td></tr></table>{_gap(22)}"
            )
        elif kind == "list":
            items = "".join(
                f'<li style="margin:0 0 8px 0;font-family:{FONT};font-size:15px;line-height:1.6;'
                f'color:{c["tekst"]};">{_e(_fill(i, f))}</li>'
                for i in block["items"]
            )
            parts.append(f'<ul style="margin:0 0 14px 0;padding-left:20px;">{items}</ul>')
        elif kind == "button":
            # "Bulletproof button": Outlook (Word-weergave) krijgt een VML-knop, andere
            # mailprogramma's een gewone HTML-knop. Breedte geschat op basis van de tekstlengte.
            bg = c["accent_donker"]
            text = _e(_fill(block["tekst"], f))
            link = _e(_fill(block["link"], f))
            width = len(text) * 9 + 64
            parts.append(
                f"{_gap(8)}<div>"
                f'<!--[if mso]><v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" '
                f'xmlns:w="urn:schemas-microsoft-com:office:word" href="{link}" '
                f'style="height:48px;v-text-anchor:middle;width:{width}px;" arcsize="6%" '
                f'strokecolor="{bg}" fillcolor="{bg}"><w:anchorlock/>'
                f'<center style="color:#FFFFFF;font-family:Arial,sans-serif;font-size:14px;'
                f'font-weight:bold;">{text}</center></v:roundrect><![endif]-->'
                f'<!--[if !mso]><!-- --><a href="{link}" style="display:inline-block;background:{bg};'
                f"border-radius:3px;padding:15px 32px;font-family:{FONT};font-size:14px;"
                f'font-weight:bold;color:#FFFFFF;text-decoration:none;">{text}</a><!--<![endif]-->'
                f"</div>{_gap(26)}"
            )
    parts.append(f'<p style="{p_style}margin-top:24px;">{_e(_fill(t["afsluiting"], f))}</p>')
    parts.append(f'<p style="{p_style}font-weight:bold;">{_e(_fill(common["team"], f))}</p>')
    body = "\n".join(parts)

    return f"""<!DOCTYPE html>
<html lang="{language}" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(_fill(t["onderwerp"], f))}</title></head>
<body style="margin:0;padding:0;background:{c['achtergrond']};">
<div style="display:none;max-height:0;overflow:hidden;">{_e(_fill(t["voorvertoning"], f))}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{c['achtergrond']};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#FFFFFF;">
<tr><td align="center" style="background:{c['accent']};padding:28px 24px;">
<a href="{_e(f['hotel_website'])}"><img src="{_e(f['hotel_logo_url'])}" alt="{_e(f['hotel_naam'])}" width="220"
 style="display:block;width:220px;max-width:70%;height:auto;border:0;"></a>
</td></tr>
<tr><td style="padding:32px 32px 16px 32px;">
{body}
</td></tr>
<tr><td style="padding:20px 32px;background:{c['accent']};font-family:{FONT};font-size:13px;line-height:1.6;color:{c['tekst']};" align="center">
<strong>{_e(f['hotel_naam'])}</strong><br>{_e(f['hotel_adres'])}<br>
<a href="tel:{_e(f['hotel_telefoon'].replace(' ', ''))}" style="color:{c['tekst']};">{_e(f['hotel_telefoon'])}</a> |
<a href="mailto:{_e(f['hotel_email'])}" style="color:{c['tekst']};">{_e(f['hotel_email'])}</a> |
<a href="{_e(f['hotel_website'])}" style="color:{c['tekst']};">{_e(f['hotel_website'].replace('https://', ''))}</a>
</td></tr>
</table>
<p style="margin:14px 0 0 0;font-family:{FONT};font-size:11px;color:#8A90A0;">{_e(_fill(common['voettekst'], f))}</p>
</td></tr></table>
</body></html>"""


# ---------------------------------------------------------------- testmails

SAMPLE = {
    "nl": {"aankomst": "vrijdag 14 november 2026", "vertrek": "zondag 16 november 2026",
           "kamertype": "Superior Double", "code_geldig_van": "14 november, 14:00",
           "code_geldig_tot": "16 november, 11:00"},
    "fr": {"aankomst": "vendredi 14 novembre 2026", "vertrek": "dimanche 16 novembre 2026",
           "kamertype": "Superior Double", "code_geldig_van": "14 novembre, 14h00",
           "code_geldig_tot": "16 novembre, 11h00"},
    "en": {"aankomst": "Friday 14 November 2026", "vertrek": "Sunday 16 November 2026",
           "kamertype": "Superior Double", "code_geldig_van": "14 November, 2 pm",
           "code_geldig_tot": "16 November, 11 am"},
    "de": {"aankomst": "Freitag, 14. November 2026", "vertrek": "Sonntag, 16. November 2026",
           "kamertype": "Superior Double", "code_geldig_van": "14. November, 14:00 Uhr",
           "code_geldig_tot": "16. November, 11:00 Uhr"},
}


def sample_data(language: str) -> dict[str, str]:
    return {
        "voornaam": "Anna", "achternaam": "Peeters", "reservatienummer": "LUC-12345",
        "kamernummer": "14", "pincode": "482916", "token": "voorbeeld",
        **SAMPLE.get(language, SAMPLE["en"]),
    }


if __name__ == "__main__":
    from hotel_checkin.messaging.email import send_email

    if len(sys.argv) not in (2, 3):
        sys.exit("Gebruik: python -m hotel_checkin.messaging.templates <ontvanger> [nl,fr,en,de]")
    languages = sys.argv[2].split(",") if len(sys.argv) == 3 else list(LANGUAGES)
    for lang in languages:
        for msg in EMAIL_MESSAGES:
            r = render(msg, lang, sample_data(lang))
            result = send_email(sys.argv[1], f"[TEST {lang.upper()}] {r.subject}", r.html)
            print(lang, msg, "ok" if result.ok else result.error)
        print(lang, "sms aan_de_deur:", render("aan_de_deur", lang, sample_data(lang)).sms)
