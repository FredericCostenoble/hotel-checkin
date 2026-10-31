"""Bouwblok sjablonen en vertaling: maakt van een berichttype, een taal en gastgegevens
een kant-en-klaar bericht (onderwerp, HTML-mail, tekstversie en SMS/WhatsApp-tekst).

- Multi-hotel: elk bericht hoort bij een hotel (hotel_id, bv. "lucca").
- Teksten: src/hotel_checkin/messaging/texts/<taal>.toml (nl, fr, en, de). Een hotel kan eigen
  teksten hebben in config/hotels/<hotel_id>/texts/<taal>.toml; die hebben dan voorrang.
- Hotelgegevens, uren en kleuren: config/hotels/<hotel_id>.toml (velden zoals {hotel_naam}).
- Ontbreekt een taal, dan valt het terug op Engels.
- Een veld zonder waarde blijft zichtbaar als {veldnaam}, zodat een fout opvalt.

Berichttypes: confirmation, reminder, access_code, at_the_door (alleen SMS/WhatsApp).

Testmails sturen in de codespace (alle mails, alle talen, met voorbeeldgegevens):
    python -m hotel_checkin.messaging.templates jouw@adres.be
    python -m hotel_checkin.messaging.templates jouw@adres.be nl,fr
    python -m hotel_checkin.messaging.templates jouw@adres.be nl --hotel lucca
Buiten productie gaan de mails naar TEST_EMAIL (zie core/safety.py).
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
LANGUAGES = ("nl", "fr", "en", "de")
FALLBACK_LANGUAGE = "en"
EMAIL_MESSAGES = ("confirmation", "reminder", "access_code", "thank_you", "payment_request")


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


def load_hotel_config(hotel_id: str) -> dict:
    from hotel_checkin.core.hotels import load_hotel

    return load_hotel(hotel_id)


@lru_cache
def load_texts(hotel_id: str, language: str) -> dict:
    from hotel_checkin.core.hotels import hotels_dir

    own = hotels_dir() / hotel_id / "texts"
    file = next(
        (d / f"{lang}.toml" for lang in (language, FALLBACK_LANGUAGE) for d in (own, TEXTS_DIR)
         if (d / f"{lang}.toml").exists()),
    )
    with open(file, "rb") as f:
        return tomllib.load(f)


def _config_fields(config: dict) -> dict[str, str]:
    fields: dict[str, str] = {}
    for section, values in config.items():
        if not isinstance(values, dict) or section in ("flows", "workflow_parameters"):
            continue  # workflow: geen velden voor teksten
        for key, value in values.items():
            fields[f"{section}_{key}"] = str(value)
    return fields


def _fill(text: str, fields: dict) -> str:
    return text.format_map(fields)


def checkin_link(hotel_id: str, token: str, language: str | None = None) -> str:
    """Link naar het check-in-formulier. In TST naar het testformulier (instelling CHECKIN_FORM_URL),
    anders naar het formulier van het hotel uit config/hotels/<hotel_id>.toml.
    Met language opent het formulier in de taal van het bericht (&lang=fr)."""
    url = os.environ.get("CHECKIN_FORM_URL") or load_hotel_config(hotel_id)["checkin"]["formulier_url"]
    url = url.replace("{token}", token)
    if language:
        url += ("&" if "?" in url else "?") + "lang=" + language
    return url


MODULES = ("code", "reservation", "checkin_form", "checkin_form_done", "pay", "practical_info")  # volgorde in de mail: pincode altijd bovenaan


def compose_blocks(texts: dict, message: str, content: dict | None, pay: str = "none") -> list[dict]:
    """De blokken van een mail, volgens de gekozen inhoud (tabblad Workflow).

    content: {"reservation": bool, "checkin_form": bool, "code": bool, "practical_info": bool}.
    Zonder content: de tekst van het berichttype zoals ze is. Blokken met module = ... horen bij
    een bouwsteen; ontbreekt een gekozen bouwsteen in de eigen tekst, dan komt hij uit [modules].
    Volgorde: inleiding, code, reservatie, check-in-formulier, betalen, praktische info, slot.
    """
    blocks = texts[message].get("blokken", [])  # at_the_door: alleen sms
    if content is None and pay == "none":
        return blocks
    content = content or {}
    first_tagged = next((i for i, b in enumerate(blocks) if b.get("module")), len(blocks))
    intro = [b for b in blocks[:first_tagged] if not b.get("module")]
    closing = [b for b in blocks[first_tagged:] if not b.get("module")]
    shared = texts.get("modules", {})
    middle: list[dict] = []
    for mod in MODULES:
        if mod == "pay":
            if pay and pay != "none":
                middle += shared.get(f"pay_{pay}", [])
            continue
        if not content.get(mod, any(b.get("module") == mod for b in blocks)):
            continue
        own = [b for b in blocks if b.get("module") == mod]
        middle += own or shared.get(mod, [])
    return intro + middle + closing


def render(hotel_id: str, message: str, language: str, data: dict[str, str],
           content: dict | None = None, pay: str = "none") -> RenderedMessage:
    """Stel een bericht samen. `data` bevat de gastgegevens, bv. voornaam, aankomst, pincode.
    content en pay: welke bouwstenen in de mail komen (zie compose_blocks)."""
    from hotel_checkin.core.models import normalize_language

    language = normalize_language(language)
    config = load_hotel_config(hotel_id)
    texts = load_texts(hotel_id, language)
    fields = _Fields({**_config_fields(config), **data})
    rooms = data.get("_rooms") or []
    if len(rooms) > 1:  # het kamertype is dat van de eerste kamer: bij meer kamers het aantal en de nummers
        fields["kamertype"] = texts["algemeen"]["meerdere_kamers"].format(aantal=len(rooms), kamers=", ".join(rooms))
    if "token" in data and "checkin_link" not in data:
        fields["checkin_link"] = checkin_link(hotel_id, data["token"], language)
    # Website in de taal van het bericht als het hotelbestand die kent ([hotel] website_fr = ...)
    fields["hotel_website"] = config.get("hotel", {}).get(f"website_{language}") or fields.get("hotel_website", "")

    t = {**texts[message], "blokken": compose_blocks(texts, message, content, pay)}
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
    lines = ([f["_test_note"], ""] if f.get("_test_note") else []) + [_fill(t["aanhef"], f), ""]
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
        elif kind == "prices":
            lines += [f"{label}: {amount}" for label, amount in _price_rows(block, f)]
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

    parts: list[str] = []
    if f.get("_test_note"):  # alleen buiten PRD: wat in deze testmail nog niet echt is
        parts.append(f'<p style="margin:0 0 16px 0;padding:10px 12px;background:#FDF0E1;border:1px solid #E59A3C;'
                     f'font-family:{FONT};font-size:13px;color:#7A4510;">{_e(f["_test_note"])}</p>')
    parts.append(f'<p style="{p_style}">{_e(_fill(t["aanhef"], f))}</p>')
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
        elif kind == "prices":
            rows = _price_rows(block, f)
            if rows:
                cell = f"padding:6px 12px;font-family:{FONT};font-size:14px;color:{c['tekst']};border-bottom:1px solid #E3E6ED;"
                last = len(rows) - 1
                body = "".join(
                    f'<tr><td style="{cell}{"font-weight:bold;" if i == last else ""}">{_e(label)}</td>'
                    f'<td align="right" style="{cell}white-space:nowrap;{"font-weight:bold;" if i == last else ""}">{_e(amount)}</td></tr>'
                    for i, (label, amount) in enumerate(rows)
                )
                parts.append(
                    f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                    f'style="border-collapse:collapse;background:{c["achtergrond"]};margin:0 0 6px 0;">{body}</table>'
                    f"{_gap(10)}"
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


def _price_rows(block: dict, f: dict) -> list[tuple[str, str]]:
    """Prijzen boven de betaalknop: de lijnen van de folio, het totaal, wat al betaald is en wat
    nog open staat (laatste rij, vet). Leeg als de folio niet gekend is."""
    lines = list(f.get("_folio") or [])
    if not lines:
        return []
    if f.get("_total"):
        lines.append((block.get("totaal", "Totaal"), f["_total"]))
    if f.get("_paid"):
        lines.append((block.get("betaald", "Betaald"), "- " + f["_paid"]))
    if f.get("_open"):
        lines.append((block.get("open", "Open"), f["_open"]))
    return lines


def sample_data(language: str) -> dict[str, str]:
    return {
        "voornaam": "Anna", "achternaam": "Peeters", "reservatienummer": "LUC-12345",
        "kamernummer": "14", "pincode": "482916", "token": "voorbeeld", "openstaand_bedrag": "€ 245,00",
        **SAMPLE.get(language, SAMPLE["en"]),
    }


if __name__ == "__main__":
    from hotel_checkin.messaging.email import send_email

    args = sys.argv[1:]
    hotel = "lucca"
    if "--hotel" in args:
        i = args.index("--hotel")
        hotel = args[i + 1]
        del args[i : i + 2]
    if len(args) not in (1, 2):
        sys.exit("Gebruik: python -m hotel_checkin.messaging.templates <ontvanger> [nl,fr,en,de] [--hotel id]")
    languages = args[1].split(",") if len(args) == 2 else list(LANGUAGES)
    cfg = load_hotel_config(hotel)
    for lang in languages:
        for msg in EMAIL_MESSAGES:
            r = render(hotel, msg, lang, sample_data(lang))
            result = send_email(
                args[0], f"[TEST {lang.upper()}] {r.subject}", r.html,
                sender=cfg["verzending"]["mail_afzender"], reply_to=cfg["hotel"]["email"],
            )
            print(lang, msg, "ok" if result.ok else result.error)
        print(lang, "sms at_the_door:", render(hotel, "at_the_door", lang, sample_data(lang)).sms)


# ---------------------------------------------------------------- datums in de taal van de gast

_DAYS = {
    "nl": ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"],
    "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
}
_MONTHS = {
    "nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september",
           "oktober", "november", "december"],
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
           "octobre", "novembre", "décembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
           "Oktober", "November", "Dezember"],
}


def format_date(d, language: str) -> str:
    """Datum zoals in de voorbeeldteksten: 'vrijdag 14 november 2026', 'Freitag, 14. November 2026'."""
    lang = language if language in _DAYS else FALLBACK_LANGUAGE
    day, month = _DAYS[lang][d.weekday()], _MONTHS[lang][d.month - 1]
    if lang == "de":
        return f"{day}, {d.day}. {month} {d.year}"
    if lang == "en":
        return f"{day} {d.day} {month} {d.year}"
    return f"{day} {d.day} {month} {d.year}"


def format_moment(dt, language: str) -> str:
    """Dag en uur zoals in de code-mail: '14 november, 14:00', '14 novembre, 14h00',
    '14 November, 2 pm', '14. November, 14:00 Uhr'."""
    lang = language if language in _MONTHS else FALLBACK_LANGUAGE
    month = _MONTHS[lang][dt.month - 1]
    if lang == "fr":
        return f"{dt.day} {month}, {dt.hour}h{dt.minute:02d}"
    if lang == "en":
        h = dt.hour % 12 or 12
        return f"{dt.day} {month}, {h}{':%02d' % dt.minute if dt.minute else ''} {'am' if dt.hour < 12 else 'pm'}"
    if lang == "de":
        return f"{dt.day}. {month}, {dt.hour:02d}:{dt.minute:02d} Uhr"
    return f"{dt.day} {month}, {dt.hour:02d}:{dt.minute:02d}"
