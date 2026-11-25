"""WhatsApp-sjablonen beheren in de monitor (instellingen, WhatsApp): teksten wijzigen, indienen bij Meta (via
Twilio) en de goedgekeurde versie gebruiken.

Waar alles staat:
- standaardteksten per hotel: config/whatsapp/<hotel_id>.toml
- in de monitor gewijzigde teksten, de versies en hun status: database (HotelConfig, document whatsapp_templates),
  per omgeving apart (TST en PRD hebben elk hun eigen sjablonen, want het adres van de knop verschilt)

Per sjabloon en taal:
- text: de tekst zoals ze nu in de monitor staat (ontbreekt = de actieve tekst, anders de standaard)
- active: de goedgekeurde versie die verstuurd wordt (SID, naam, versie, tekst)
- pending: de ingediende versie die nog niet goedgekeurd is (of afgekeurd, met de reden van Meta)

Een goedgekeurd sjabloon kan niet meer gewijzigd worden: een nieuwe tekst wordt een nieuwe versie (_v2, _v3, ...)
die opnieuw ingediend wordt. Tot Meta ze goedkeurt, blijft de vorige versie gebruikt worden. De status wordt alleen
gevraagd voor versies die nog wachten (check); wat goedgekeurd of afgekeurd is, wordt niet meer opgevraagd.
"""

from __future__ import annotations

import logging
import os
import re
import tomllib
from datetime import UTC, datetime, timedelta

from hotel_checkin.core import hotels
from hotel_checkin.core.safety import environment
from hotel_checkin.messaging import content_templates as twilio

DOC = "whatsapp_templates"
SHARED_DOC = "whatsapp_templates_prd"  # buiten PRD: de goedgekeurde PRD-sjablonen die deze omgeving gebruikt
SOURCE_ENV = "prd"  # TST (en dev) gebruiken de sjablonen van PRD: niets apart indienen. De knop van een PRD-sjabloon
# wijst naar het PRD-formulier; daarom zet templates.checkin_suffix in TST "&env=tst" achter de link, en stuurt het
# PRD-formulier de gast door naar het TST-formulier (web/checkin/app.js).

# Per bericht: de plaatsen in de tekst ({{1}}, {{2}}, ...) in volgorde, en of er een knop naar het check-in-formulier
# (link) of een pdf bovenaan (media) bij hoort. De laatste plaats is dan het variabele einde van dat adres.
# Nieuwe plaatsen komen altijd achteraan in vars: een oudere goedgekeurde versie gebruikt dan de eerste plaatsen
# (var_names). Elke versie bewaart welke plaatsen ze heeft; daarmee worden de waarden ingevuld bij het versturen.
# De pincode zelf: Meta keurt die eerst af als "Category mismatch" (moet Verificatie zijn, 21/11/2026), maar na bezwaar
# werd een sjabloon met de pincode goedgekeurd (lucca_test_access_nl_v1, 25/11/2026). Daarom staat ze in access_code;
# tot die versie goedgekeurd is, blijft de vorige (zonder pincode) in gebruik.
TEMPLATES: dict[str, dict] = {
    "confirmation": {"vars": ("voornaam",), "button": "checkin_suffix", "langs": ("nl", "fr", "en", "de")},
    "reminder": {"vars": ("voornaam",), "button": "checkin_suffix", "langs": ("nl", "fr", "en", "de")},
    "access_code": {"vars": ("kamer_kort", "pincode"), "button": "checkin_suffix", "langs": ("nl", "fr", "en", "de")},
    "room_change": {"vars": ("kamer_kort",), "button": "checkin_suffix", "langs": ("nl", "fr", "en", "de")},
    # Lijsten voor het personeel: in het Engels, zoals de lijsten zelf (dag en samenvatting komen Engels uit
    # daily_lists: lists.day_text en describe). De voorbeeld-pdf moet echt bestaan: Meta haalt ze op.
    "breakfast_list": {"vars": ("dag", "samenvatting"), "media": "pdf_pad", "langs": ("en",),
                       "samples": {"samenvatting": "12 persons in 6 rooms"}},
    "cleaning_list": {"vars": ("dag", "samenvatting"), "media": "pdf_pad", "langs": ("en",),
                      "samples": {"samenvatting": "3 leave, 5 stay, 2 check in"}},
}
# Voorbeeldwaarden: Meta vraagt ze bij het goedkeuren (en de monitor toont er een voorbeeld mee)
SAMPLES = {"voornaam": "Jan", "checkin_suffix": "a1b2c3d4&lang=nl", "kamer_kort": "16 verdiep 1", "pincode": "3453",
           "dag": "Friday 13/11/2026", "samenvatting": "12 persons in 6 rooms"}
REV = 2  # rev 2: pincode uit de sjablonen; afgekeurde versies van daarvoor worden eenmalig weggegooid (_migrate)

BODY_MAX, BODY_MAX_BUTTON, BUTTON_MAX, FOOTER_MAX, HEADER_MAX = 1024, 640, 20, 60, 60
CHECK_EVERY = timedelta(minutes=10)  # status van een wachtende versie hoogstens zo vaak opvragen (timer)
CHECK_EVERY_MONITOR = timedelta(seconds=60)  # bij het openen van de monitor
# Afgekeurd: na een bezwaar in Business Support Home kan Meta de versie alsnog goedkeuren. Daarom ook afgekeurde
# versies blijven opvragen, minder vaak, tot 30 dagen na het indienen.
CHECK_REJECTED_EVERY = timedelta(hours=1)
CHECK_REJECTED_DAYS = timedelta(days=30)
FIELDS = ("header", "body", "button", "footer")
# Content Template Builder in de Twilio Console (lijst met zoekvak; een link per sjabloon is niet gedocumenteerd)
CONSOLE_URL = "https://console.twilio.com/us1/develop/sms/content-template-builder"


def samples_of(step: str, hotel_id: str = "lucca") -> dict[str, str]:
    """Voorbeeldwaarden voor dit bericht (eigen waarden van het bericht gaan voor). De pdf: een echte voorbeeldlink."""
    out = SAMPLES | TEMPLATES[step].get("samples", {})
    if TEMPLATES[step].get("media"):
        from hotel_checkin.processes import daily_lists

        out["pdf_pad"] = daily_lists.sample_pdf_path(hotel_id, step.removesuffix("_list"))
    return out


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- opslag


def _load(hotel_id: str) -> dict:
    """Alle sjablonen. Per bericht een eigen rij (whatsapp_templates_<bericht>): alles samen werd groter dan Azure in
    één veld toelaat (64 KB). De rij whatsapp_templates zelf bewaart alleen de versie van de opslag (_rev); in een
    oudere opslag staat daar nog alles samen (wordt bij het volgende bewaren gesplitst)."""
    from hotel_checkin.guests import repository

    base = (repository.get_config_doc(hotel_id, DOC) or {}).get("value") or {}
    if base.get("_split"):
        data = {"_rev": base.get("_rev")}
        for step in TEMPLATES:
            doc = repository.get_config_doc(hotel_id, f"{DOC}_{step}")
            if doc and doc.get("value"):
                data[step] = doc["value"]
    else:
        data = base
    return _migrate(data)


def _save(hotel_id: str, data: dict, user: str) -> None:
    from hotel_checkin.guests import repository

    for step in TEMPLATES:
        if isinstance(data.get(step), dict):
            repository.set_config_doc(hotel_id, f"{DOC}_{step}", data[step], user)
    repository.set_config_doc(hotel_id, DOC, {"_rev": data.get("_rev", REV), "_split": True}, user)


def _migrate(data: dict) -> dict:
    """Eenmalig per omgeving: afgekeurde of mislukte versies van voor REV weggooien, zodat de nieuwe standaardtekst
    getoond wordt (goedgekeurde en wachtende versies blijven). Wordt bewaard bij de volgende wijziging."""
    if int(data.get("_rev") or 0) >= REV:
        return data
    for per in data.values():
        if isinstance(per, dict):
            for e in per.values():
                if isinstance(e, dict) and e.get("pending", {}).get("status") in ("rejected", "error"):
                    e.pop("pending")
    data["_rev"] = REV
    return data


def _entry(data: dict, step: str, lang: str) -> dict:
    return data.setdefault(step, {}).setdefault(lang, {})


def defaults(hotel_id: str) -> dict:
    """Standaardteksten uit config/whatsapp/<hotel_id>.toml ({} als het bestand er niet is)."""
    path = hotels.hotels_dir().parent / "whatsapp" / f"{hotel_id}.toml"
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _clean(text: dict | None) -> dict:
    t = {k: str((text or {}).get(k) or "").replace("\r\n", "\n").strip() for k in FIELDS}
    return {k: v for k, v in t.items() if v}


def current_text(hotel_id: str, step: str, lang: str, data: dict | None = None) -> dict:
    """De tekst zoals ze nu in de monitor staat: gewijzigd, anders de ingediende versie (ook afgekeurd, om ze te
    verbeteren), anders de actieve versie, anders de standaard."""
    e = (data if data is not None else _load(hotel_id)).get(step, {}).get(lang, {})
    if "text" in e:
        return _clean(e["text"])
    if e.get("pending"):
        return _clean(e["pending"].get("text"))
    if e.get("active"):
        return _clean(e["active"].get("text"))
    return _clean(defaults(hotel_id).get(step, {}).get(lang))


# ---------------------------------------------------------------- regels van Meta


def validate(step: str, text: dict) -> list[str]:
    """Wat Meta zou weigeren of Twilio niet aanvaardt. Lege lijst = in orde."""
    spec = TEMPLATES[step]
    n = len(spec["vars"])
    body, button, footer = text.get("body", ""), text.get("button", ""), text.get("footer", "")
    header = text.get("header", "")
    errors: list[str] = []
    if not body:
        return ["De tekst is leeg."]
    limit = BODY_MAX_BUTTON if spec.get("button") else BODY_MAX
    if len(body) > limit:
        errors.append(f"De tekst is te lang ({len(body)} tekens, hoogstens {limit}).")
    found = re.findall(r"\{\{\s*([^}]*?)\s*\}\}", body)
    wanted = [str(i) for i in range(1, n + 1)]
    for x in found:
        if x not in wanted:
            errors.append(f"Onbekende plaats {{{{{x}}}}}: deze tekst kent alleen {', '.join('{{' + w + '}}' for w in wanted)}.")
    for w in wanted:
        if found.count(w) == 0:
            errors.append(f"Plaats {{{{{w}}}}} ({spec['vars'][int(w) - 1]}) ontbreekt.")
        elif found.count(w) > 1:
            errors.append(f"Plaats {{{{{w}}}}} staat er meer dan een keer in.")
    if re.match(r"\{\{", body):
        errors.append("De tekst mag niet beginnen met een plaats ({{...}}).")
    if re.search(r"\}\}$", body):
        errors.append("De tekst mag niet eindigen met een plaats ({{...}}).")
    if re.search(r"\}\}\s*\{\{", body):
        errors.append("Twee plaatsen na elkaar: zet er tekst tussen.")
    if re.search(r"\n\s*\n\s*\n", body):
        errors.append("Hoogstens een lege regel na elkaar.")
    if spec.get("button"):
        if not button:
            errors.append("De knoptekst ontbreekt.")
        elif len(button) > BUTTON_MAX:
            errors.append(f"De knoptekst is te lang ({len(button)} tekens, hoogstens {BUTTON_MAX}).")
    elif button:
        errors.append("Dit bericht heeft geen knop.")
    if "{{" in button or "{{" in footer or "{{" in header:
        errors.append("Geen plaatsen ({{...}}) in de titel, de knop of de voettekst.")
    if len(header) > HEADER_MAX:
        errors.append(f"De titel is te lang ({len(header)} tekens, hoogstens {HEADER_MAX}).")
    if header and spec.get("media"):
        errors.append("Een bericht met pdf heeft geen titel (de pdf staat bovenaan).")
    if len(footer) > FOOTER_MAX:
        errors.append(f"De voettekst is te lang ({len(footer)} tekens, hoogstens {FOOTER_MAX}).")
    if footer and spec.get("media"):
        errors.append("Een bericht met pdf heeft geen voettekst.")
    return errors


# ---------------------------------------------------------------- adressen (knop en pdf)


def button_prefix(hotel_id: str) -> str:
    """Vast begin van de knop naar het check-in-formulier in deze omgeving (bv. https://checkin.hotellucca.be/?r=)."""
    from hotel_checkin.messaging import templates

    return templates._form_url(hotel_id).split("{token}", 1)[0]


def media_prefix() -> str | None:
    """Vast begin van het adres van de pdf (de Function App van deze omgeving); None buiten Azure."""
    host = os.environ.get("WEBSITE_HOSTNAME")
    return f"https://{host}/api/lists/" if host else None


def spec_of(hotel_id: str, step: str, text: dict) -> dict:
    """Alles wat het sjabloon bepaalt: de tekst en de vaste adressen. Een ander adres (bv. ander formulier in deze
    omgeving) vraagt ook een nieuwe versie."""
    spec = TEMPLATES[step]
    out = dict(text)
    if spec.get("button"):
        out["url"] = button_prefix(hotel_id)
    if spec.get("media"):
        out["media"] = media_prefix() or ""
    return out


def var_names(step: str, count: int | None = None, body: str | None = None) -> tuple[str, ...]:
    """Welke waarden in welke plaats van een versie van dit bericht: de eerste plaatsen van vars, dan de knop of pdf.
    count = aantal plaatsen van die versie (Twilio), of body = haar tekst. Niets gekend: de huidige plaatsen."""
    spec = TEMPLATES[step]
    extra = spec.get("button") or spec.get("media")
    if count is not None:
        n = count - (1 if extra else 0)
    elif body is not None:
        n = len(set(re.findall(r"\{\{\s*(\d+)\s*\}\}", body)))
    else:
        n = len(spec["vars"])
    n = max(0, min(n, len(spec["vars"])))
    return tuple(spec["vars"][:n]) + ((extra,) if extra else ())


def template_name(hotel_id: str, step: str, lang: str, version: int) -> str:
    """Naam bij Meta: uniek per WhatsApp-account (hotel, omgeving, bericht, taal, versie)."""
    raw = f"{hotel_id}_{environment()}_{step}_{lang}_v{version}".lower()
    return re.sub(r"[^a-z0-9_]", "_", raw)


# ---------------------------------------------------------------- toestand


def state(hotel_id: str, step: str, lang: str, data: dict) -> str:
    """approved: de getoonde tekst is goedgekeurd en actief; waiting: ingediend, Meta beslist nog; rejected: afgekeurd;
    changed: gewijzigd, nog niet ingediend (de vorige versie blijft actief); new: nog nooit ingediend."""
    e = data.get(step, {}).get(lang, {})
    spec = spec_of(hotel_id, step, current_text(hotel_id, step, lang, data))
    pending, active = e.get("pending"), e.get("active")
    if pending and pending.get("spec") == spec:
        if pending.get("status") == "rejected":
            return "rejected"
        if pending.get("status") in twilio.WAITING:
            return "waiting"
        if pending.get("status") == "error":
            return "error"
    if active and active.get("spec") == spec:
        return "approved"
    return "changed" if active else "new"


def shared() -> bool:
    """Gebruikt deze omgeving de sjablonen van een andere (PRD)?"""
    return environment() != SOURCE_ENV


def _load_shared(hotel_id: str) -> dict:
    from hotel_checkin.guests import repository

    doc = repository.get_config_doc(hotel_id, SHARED_DOC)
    return (doc or {}).get("value") or {}


def sync_shared(hotel_id: str, client=None, min_age: timedelta = CHECK_EVERY) -> list[str]:
    """Buiten PRD: de nieuwste goedgekeurde PRD-versie per bericht en taal opvragen bij Twilio (zelfde account) en
    bewaren. Hoogstens om de min_age. Geeft wat veranderde."""
    import re as _re

    if not shared():
        return []
    data = _load_shared(hotel_id)
    checked = data.get("_checked_at")
    # Versies van voor het bewaren van het aantal plaatsen: meteen opnieuw ophalen
    complete = all("variables" in v for per in data.values() if isinstance(per, dict) for v in per.values()
                   if isinstance(v, dict))
    if checked and complete and _now() - datetime.fromisoformat(checked) < min_age:
        return []
    found = twilio.approved(hotel_id, client=client)
    pat = _re.compile(rf"^{_re.escape(hotel_id.lower())}_{SOURCE_ENV}_(.+)_([a-z]{{2}})_v(\d+)$")
    best: dict = {}
    for name, info in found.items():
        sid = info["sid"]
        m = pat.match(name)
        if not m or m.group(1) not in TEMPLATES or m.group(2) not in TEMPLATES[m.group(1)]["langs"]:
            continue
        step, lang, version = m.group(1), m.group(2), int(m.group(3))
        cur = best.get(step, {}).get(lang)
        if not cur or version > cur["version"]:
            best.setdefault(step, {})[lang] = {"sid": sid, "name": name, "version": version,
                                               "variables": info.get("variables")}
    changes = [f"{v['name']} in gebruik" for step, per in best.items() for lang, v in per.items()
               if (data.get(step, {}).get(lang) or {}).get("sid") != v["sid"]]
    from hotel_checkin.guests import repository

    repository.set_config_doc(hotel_id, SHARED_DOC, best | {"_checked_at": _now().isoformat()}, "Twilio (PRD-sjablonen)")
    return changes


def active(hotel_id: str, step: str, lang: str) -> tuple[str, tuple[str, ...]] | None:
    """De goedgekeurde versie (wat verstuurd wordt): (SID, waarden per plaats), of None. Buiten PRD: die van PRD."""
    try:
        if shared():
            a = _load_shared(hotel_id).get(step, {}).get(lang) or {}
        else:
            a = _load(hotel_id).get(step, {}).get(lang, {}).get("active") or {}
    except Exception:  # noqa: BLE001 - geen opslag: dan de SID uit de instellingen (send_messages)
        return None
    if not a.get("sid"):
        return None
    if a.get("vars"):
        names = tuple(a["vars"])
    elif a.get("variables") is not None or shared():
        names = var_names(step, count=a.get("variables"))
    else:  # versie van voor de bewaarde plaatsen: afleiden uit haar tekst
        names = var_names(step, body=((a.get("text") or {}).get("body")))
    return a["sid"], names


def active_sid(hotel_id: str, step: str, lang: str) -> str | None:
    """SID van de goedgekeurde versie, of None."""
    a = active(hotel_id, step, lang)
    return a[0] if a else None


def view(hotel_id: str, refresh: bool = True) -> dict:
    """Alle sjablonen voor de monitor, met per taal de tekst, de toestand, de actieve en de ingediende versie.
    refresh: eerst de status vragen van versies die nog wachten (hoogstens een keer per minuut)."""
    if shared():
        return _view_shared(hotel_id, refresh)
    if refresh:
        try:
            check(hotel_id, min_age=CHECK_EVERY_MONITOR)
        except Exception:  # Twilio niet bereikbaar: de bewaarde status tonen
            logging.exception("%s: status van de WhatsApp-sjablonen niet opgevraagd", hotel_id)
    from hotel_checkin.core.config import hotel_setting

    data = _load(hotel_id)
    base = defaults(hotel_id)
    out = []
    for step, spec in TEMPLATES.items():
        langs = []
        for lang in spec["langs"]:
            e = data.get(step, {}).get(lang, {})
            text = current_text(hotel_id, step, lang, data)
            manual = hotel_setting(hotel_id, f"WHATSAPP_TEMPLATE_{step.upper()}_{lang.upper()}",
                                   required=False, shared=False)
            langs.append({
                "lang": lang, "text": text, "default": _clean(base.get(step, {}).get(lang)),
                "edited": "text" in e, "state": state(hotel_id, step, lang, data), "errors": validate(step, text),
                "active": _public(e.get("active")), "pending": _public(e.get("pending")),
                "manual_sid": manual if manual and not e.get("active") else "",
            })
        out.append({"step": step, "vars": list(spec["vars"]), "button": bool(spec.get("button")),
                    "media": bool(spec.get("media")), "samples": [samples_of(step, hotel_id)[v] for v in spec["vars"]],
                    "media_sample": samples_of(step, hotel_id)[spec["media"]].rsplit("/", 1)[-1] if spec.get("media") else "",
                    "langs": langs})
    newer = sum(default_differs(hotel_id, st, lg, data) for st, sp in TEMPLATES.items() for lg in sp["langs"])
    return {"templates": out, "newer_defaults": newer, "console_url": CONSOLE_URL, "button_prefix": button_prefix(hotel_id), "media_prefix": media_prefix() or "",
            "env": environment(), "limits": {"body": BODY_MAX, "body_button": BODY_MAX_BUTTON,
                                             "button": BUTTON_MAX, "footer": FOOTER_MAX, "header": HEADER_MAX}}


def _view_shared(hotel_id: str, refresh: bool) -> dict:
    """Buiten PRD: alleen tonen welke PRD-versie gebruikt wordt (niets wijzigen of indienen)."""
    if refresh:
        try:
            sync_shared(hotel_id, min_age=CHECK_EVERY_MONITOR)
        except Exception:  # Twilio niet bereikbaar: de bewaarde toestand tonen
            logging.exception("%s: PRD-sjablonen niet opgevraagd", hotel_id)
    data = _load_shared(hotel_id)
    base = defaults(hotel_id)
    out = []
    for step, spec in TEMPLATES.items():
        langs = []
        for lang in spec["langs"]:
            a = data.get(step, {}).get(lang)
            text = _clean(base.get(step, {}).get(lang))
            langs.append({"lang": lang, "text": text, "default": text, "edited": False,
                          "state": "approved" if a else "new", "errors": [], "pending": None, "manual_sid": "",
                          "active": a and {"sid": a["sid"], "name": a["name"], "version": a["version"], "text": text}})
        out.append({"step": step, "vars": list(spec["vars"]), "button": bool(spec.get("button")),
                    "media": bool(spec.get("media")), "samples": [samples_of(step, hotel_id)[v] for v in spec["vars"]],
                    "media_sample": samples_of(step, hotel_id)[spec["media"]].rsplit("/", 1)[-1] if spec.get("media") else "",
                    "langs": langs})
    return {"templates": out, "shared_from": SOURCE_ENV, "checked_at": data.get("_checked_at", ""), "newer_defaults": 0,
            "console_url": CONSOLE_URL, "button_prefix": button_prefix(hotel_id), "media_prefix": media_prefix() or "",
            "env": environment(), "limits": {"body": BODY_MAX, "body_button": BODY_MAX_BUTTON, "button": BUTTON_MAX,
                                             "footer": FOOTER_MAX, "header": HEADER_MAX}}


def _public(v: dict | None) -> dict | None:
    if not v:
        return None
    return {k: v.get(k) for k in ("sid", "name", "version", "status", "reason", "submitted_at", "submitted_by",
                                  "approved_at", "checked_at", "error") if v.get(k) not in (None, "")} | {
        "text": _clean(v.get("text"))}


def _known(step: str, lang: str) -> None:
    if step not in TEMPLATES or lang not in TEMPLATES[step]["langs"]:
        raise ValueError(f"onbekend sjabloon {step}/{lang}")


# ---------------------------------------------------------------- wijzigen en indienen


def _not_shared() -> None:
    if shared():
        raise ValueError("Deze omgeving gebruikt de sjablonen van PRD: wijzigen en indienen gebeurt in PRD")


def save_text(hotel_id: str, step: str, lang: str, text: dict, user: str) -> None:
    """Tekst bewaren (nog niet indienen). Gelijk aan de actieve of de standaardtekst: niets apart bewaren."""
    _not_shared()
    _known(step, lang)
    data = _load(hotel_id)
    e = _entry(data, step, lang)
    new = _clean(text)
    e.pop("text", None)
    if new != current_text(hotel_id, step, lang, data):
        e["text"] = new
    _save(hotel_id, data, user)


def reset_text(hotel_id: str, step: str, lang: str, user: str) -> None:
    """Wijziging weggooien: terug naar de actieve tekst, of de standaard als er nog geen is (ook als er een versie met
    een andere tekst wacht bij Meta; indienen vervangt die dan). Een afgekeurde of mislukte versie verdwijnt."""
    _known(step, lang)
    data = _load(hotel_id)
    e = _entry(data, step, lang)
    e.pop("text", None)
    if e.get("pending") and e["pending"].get("status") not in twilio.WAITING:
        e.pop("pending")
    elif e.get("pending") and not e.get("active"):
        # Wacht nog bij Meta, nog niets goedgekeurd: terug naar de standaardtekst (indienen vervangt de wachtende)
        default = _clean(defaults(hotel_id).get(step, {}).get(lang))
        if default != _clean(e["pending"].get("text")):
            e["text"] = default
    _save(hotel_id, data, user)


def submit(hotel_id: str, step: str, lang: str, user: str, client=None) -> dict:
    """De huidige tekst als nieuwe versie bij Twilio aanmaken en bij Meta indienen.
    Geeft {"ok": bool, "message": ...}. Een eerdere versie die nog niet goedgekeurd was, wordt vervangen."""
    _not_shared()
    _known(step, lang)
    data = _load(hotel_id)
    e = _entry(data, step, lang)
    text = current_text(hotel_id, step, lang, data)
    errors = validate(step, text)
    if errors:
        return {"ok": False, "message": " ".join(errors)}
    st = state(hotel_id, step, lang, data)
    if st == "approved":
        return {"ok": True, "message": "Deze tekst is al goedgekeurd."}
    if st == "waiting":
        return {"ok": True, "message": "Deze tekst is al ingediend; Meta beslist nog."}
    tpl = TEMPLATES[step]
    spec = spec_of(hotel_id, step, text)
    if tpl.get("media") and not spec.get("media"):
        return {"ok": False, "message": "Het adres van de pdf is alleen gekend in Azure (TST of PRD)."}
    n = len(tpl["vars"])
    sample = samples_of(step, hotel_id)
    samples = {str(i): sample[v] for i, v in enumerate(tpl["vars"], 1)}
    url = media = None
    if tpl.get("button"):
        url = f"{spec['url']}{{{{{n + 1}}}}}"
        samples[str(n + 1)] = sample[tpl["button"]]
    if tpl.get("media"):
        media = f"{spec['media']}{{{{{n + 1}}}}}"
        samples[str(n + 1)] = sample[tpl["media"]]
    types = twilio.build_types(text["body"], text.get("button"), url, text.get("footer"), media, text.get("header"))
    version = int(e.get("version") or 0) + 1
    name = template_name(hotel_id, step, lang, version)
    old = e.get("pending")
    try:
        sid = twilio.create(hotel_id, name, lang, samples, types, client=client)
    except Exception as exc:  # noqa: BLE001 - de fout van Twilio tonen in de monitor
        e["pending"] = {"spec": spec, "text": text, "version": version, "name": name, "status": "error",
                        "error": str(exc)[:500], "submitted_at": _now().isoformat(), "submitted_by": user}
        e["version"] = version
        _save(hotel_id, data, user)
        return {"ok": False, "message": f"Aanmaken bij Twilio mislukt: {exc}"}
    pending = {"sid": sid, "spec": spec, "text": text, "version": version, "name": name, "status": "received",
               "vars": list(var_names(step)), "submitted_at": _now().isoformat(), "submitted_by": user}
    e["version"] = version
    try:
        res = twilio.submit_whatsapp(hotel_id, sid, name, client=client)
        pending |= {"status": res["status"], "reason": res["reason"], "checked_at": _now().isoformat()}
    except Exception as exc:  # noqa: BLE001
        pending |= {"status": "error", "error": f"Indienen bij Meta mislukt: {exc}"[:500]}
    e["pending"] = pending
    e.pop("text", None)  # de tekst staat nu in de ingediende versie
    _save(hotel_id, data, user)
    if old and old.get("sid") and old.get("sid") != sid and old.get("status") != "approved":
        try:  # vervangen versie die nooit actief werd: bij Twilio opruimen
            twilio.delete(hotel_id, old["sid"], client=client)
        except Exception:  # noqa: BLE001 - blijft gewoon staan bij Twilio
            logging.warning("%s: oude versie %s niet verwijderd bij Twilio", hotel_id, old.get("sid"))
    if pending["status"] == "error":
        return {"ok": False, "message": pending["error"]}
    return {"ok": True, "message": f"Ingediend als {name}. Meta beslist meestal binnen enkele minuten tot een dag."}


def default_differs(hotel_id: str, step: str, lang: str, data: dict) -> bool:
    """De standaardtekst (bestand) verschilt van wat nu getoond wordt, en er is geen eigen wijziging in de monitor.
    Een bewaarde tekst die gelijk is aan de goedgekeurde of ingediende versie is geen eigen wijziging."""
    e = data.get(step, {}).get(lang, {})
    if "text" in e:
        versions = [_clean((e.get(k) or {}).get("text")) for k in ("active", "pending")]
        if _clean(e["text"]) not in [v for v in versions if v]:
            return False
    default = _clean(defaults(hotel_id).get(step, {}).get(lang))
    return bool(default) and default != current_text(hotel_id, step, lang, data)


def use_defaults(hotel_id: str, user: str) -> int:
    """De nieuwe standaardteksten overnemen waar de monitor nog een oudere tekst toont (niet waar zelf iets gewijzigd
    is). Daarna gewoon indienen; tot Meta de nieuwe versie goedkeurt blijft de goedgekeurde verstuurd. Geeft het
    aantal."""
    _not_shared()
    data = _load(hotel_id)
    n = 0
    for step, spec in TEMPLATES.items():
        for lang in spec["langs"]:
            if default_differs(hotel_id, step, lang, data):
                _entry(data, step, lang)["text"] = _clean(defaults(hotel_id)[step][lang])
                n += 1
    if n:
        _save(hotel_id, data, user)
    return n


def submit_all(hotel_id: str, user: str, client=None) -> dict:
    """Alle nieuwe en gewijzigde teksten indienen (niet wat afgekeurd is en niet veranderde: dat wordt opnieuw
    afgekeurd). Geeft per sjabloon het resultaat."""
    _not_shared()
    data = _load(hotel_id)
    results = []
    for step, spec in TEMPLATES.items():
        for lang in spec["langs"]:
            if state(hotel_id, step, lang, data) in ("new", "changed", "error"):
                results.append({"step": step, "lang": lang} | submit(hotel_id, step, lang, user, client=client))
    return {"ok": all(r["ok"] for r in results), "results": results}


def check(hotel_id: str, client=None, min_age: timedelta = CHECK_EVERY) -> list[str]:
    """Status opvragen bij Meta, alleen voor versies die nog wachten (of afgekeurd zijn, voor een bezwaar) en niet
    recent nagekeken werden. Goedgekeurd: die versie wordt actief. Geeft wat veranderde (voor het log).
    Buiten PRD: de PRD-sjablonen ophalen."""
    if shared():
        return sync_shared(hotel_id, client=client, min_age=min_age)
    data = _load(hotel_id)
    now = _now()

    def due(p: dict) -> bool:
        if not p.get("sid"):
            return False
        age = now - datetime.fromisoformat(p["checked_at"]) if p.get("checked_at") else None
        if p.get("status") in twilio.WAITING:
            return age is None or age >= min_age
        if p.get("status") == "rejected":
            sent = p.get("submitted_at")
            recent = not sent or now - datetime.fromisoformat(sent) < CHECK_REJECTED_DAYS
            return recent and (age is None or age >= max(min_age, CHECK_REJECTED_EVERY))
        return False

    todo = [(step, lang, e["pending"]) for step, per in data.items() if isinstance(per, dict)
            for lang, e in per.items() if isinstance(e, dict) and e.get("pending") and due(e["pending"])]
    if not todo:
        return []
    changes = []
    results = {}
    for step, lang, p in todo:
        try:
            results[(step, lang, p["sid"])] = twilio.approval_status(hotel_id, p["sid"], client=client)
        except Exception as exc:  # noqa: BLE001 - volgende keer opnieuw
            logging.warning("%s: status van %s niet opgevraagd: %s", hotel_id, p.get("name"), exc)
    data = _load(hotel_id)  # opnieuw lezen: intussen kan in de monitor iets gewijzigd zijn
    for (step, lang, sid), res in results.items():
        e = data.get(step, {}).get(lang, {})
        p = e.get("pending")
        if not p or p.get("sid") != sid:
            continue  # intussen vervangen
        before = p.get("status")
        p |= {"status": res["status"] or p.get("status"), "reason": res["reason"], "checked_at": now.isoformat()}
        if res["status"] == "approved":
            e["active"] = {k: p.get(k) for k in ("sid", "name", "version", "spec", "text", "vars",
                                                  "submitted_at", "submitted_by")} | {"approved_at": now.isoformat()}
            e.pop("pending", None)
            changes.append(f"{p['name']} goedgekeurd")
        elif res["status"] not in twilio.WAITING and res["status"] != before:
            changes.append(f"{p['name']}: {res['status']}" + (f" ({res['reason']})" if res["reason"] else ""))
    _save(hotel_id, data, "Meta (status)")
    return changes
