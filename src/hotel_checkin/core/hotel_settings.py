"""Instellingen van een hotel bekijken en wijzigen in de monitor (instellingen, tabblad Hotel).

De standaard staat in config/hotels/<hotel_id>.toml. Wat in de monitor gewijzigd wordt, komt in
de database (tabel HotelConfig, document hotel_settings) en gaat voor op het bestand
(core/hotels.load_hotel). Alleen gewijzigde waarden worden bewaard; "terug naar standaard" wist ze.
Per omgeving apart (TST en PRD hebben elk hun eigen database).

Geheimen (wachtwoorden, sleutels) staan nooit hier maar in Key Vault. Een waarde die per omgeving in
Key Vault of als instelling van de Function App staat, gaat voor op deze pagina; dat wordt getoond.
De workflow (flows, workflow_parameters) heeft een eigen tabblad.
"""

from __future__ import annotations

import os
import re

from hotel_checkin.core import hotels

META_DOC = "hotel_settings_meta"  # per sectie: wie en wanneer gewijzigd in de monitor

EXCLUDED = ("flows",)  # tabblad Workflow
# Instellingen met een vaste keuzelijst
CHOICES = {("workflow_parameters", "city_tax_unit"): ("person_night", "person_stay"),
           ("schakelaars", "berichten"): ("uit", "aan", "selectie"),
           ("kamers", "verdieping_regel"): ("eerste_cijfer", "geen")}
# Oude waarden die in de monitor bewaard zijn, getoond als de nieuwe keuze
LEGACY = {("schakelaars", "berichten"): {True: "aan", False: "uit", "true": "aan", "false": "uit"}}


def _legacy(section: str, key: str, value):
    m = LEGACY.get((section, key), {})
    try:
        return m.get(value, value)
    except TypeError:
        return value
LIST_TIMES = (("ontbijtlijst", "uur"), ("kuislijst", "uur"))  # keuze uit de vaste uren van de robot


def _choices(hotel_id: str, section: str, key: str, changes: dict | None = None) -> tuple:
    """Vaste keuzelijst, of voor het uur van de lijsten: de vaste uren van het vangnet van de robot
    (processes/robot_schedule.py), zodat de lijst geen extra robotrun vraagt."""
    if (section, key) in LIST_TIMES:
        from hotel_checkin.processes import robot_schedule

        every = (changes or {}).get("robot", {}).get("check_minutes")
        return tuple(robot_schedule.slots(float(every) if every not in (None, "") else robot_schedule.minutes(hotel_id),
                                          hotel_id))
    return CHOICES.get((section, key), ())


def _comments(hotel_id: str) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """Uitleg uit het hotelbestand: commentaar onder een sectiekop (sectie) en commentaar op of
    net boven een sleutel (veld)."""
    path = hotels.hotels_dir() / f"{hotel_id}.toml"
    section_help: dict[str, str] = {}
    field_help: dict[tuple[str, str], str] = {}
    section, pending, seen_key = "", [], False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        head = re.fullmatch(r"\[\[?([\w.]+)\]\]?", line)
        if head:
            section, pending, seen_key = head.group(1), [], False
            continue
        if line.startswith("#"):
            text = line.lstrip("#").strip()
            if re.match(r"[\w]+\s*=", text):  # uitgeschakelde sleutel als voorbeeld, geen uitleg
                continue
            pending.append(text)
            continue
        key = re.match(r"([\w\"]+)\s*=", line)
        if not key or not section:
            if not line:
                if not seen_key and pending:
                    section_help[section] = " ".join(pending)
                pending = [] if seen_key else pending
            continue
        name = key.group(1).strip('"')
        if not seen_key and pending:
            section_help[section] = " ".join(pending)
            pending = []
        inline = raw.split("#", 1)[1].strip() if "#" in raw and not raw.split("#", 1)[0].count('"') % 2 else ""
        field_help[(section, name)] = " ".join(pending + ([inline] if inline else []))
        pending, seen_key = [], True
    return section_help, field_help


def _kind(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "list"
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return "color"
    return "text"


def _sections(data: dict, prefix: str = "") -> dict[str, dict]:
    """Alle secties (ook geneste, bv. salto.rooms) met hun eenvoudige waarden."""
    out: dict[str, dict] = {}
    for name, value in data.items():
        if not isinstance(value, dict) or (not prefix and name in EXCLUDED):
            continue
        full = f"{prefix}{name}"
        out[full] = {k: v for k, v in value.items() if not isinstance(v, dict)}
        out.update(_sections(value, full + "."))
    return out


def _env_names() -> set[str]:
    """Namen die per omgeving een waarde hebben: instellingen van de Function App en geheimen in
    Key Vault (alleen de namen, nooit de waarden)."""
    from hotel_checkin.core.config import _key_vault_client

    names = {k.upper() for k, v in os.environ.items() if v}
    try:
        client = _key_vault_client()
        if client is not None:
            names |= {p.name.replace("-", "_").upper() for p in client.list_properties_of_secrets() if p.enabled}
    except Exception:  # noqa: BLE001 - Key Vault niet bereikbaar: alleen de omgeving
        pass
    return names


def _env_override(hotel_id: str, section: str, key: str, names: set[str]) -> bool:
    """Staat deze instelling per omgeving in Key Vault of in de Function App? Dan gaat die voor."""
    if "." in section:
        return False
    return f"{hotel_id.upper().replace('-', '_')}_{section.upper()}_{key.upper()}" in names


def _with_current(options: tuple, current) -> list:
    """De huidige waarde blijft kiesbaar, ook als ze niet (meer) in de lijst staat."""
    out = list(options)
    if out and current not in (None, "") and str(current) not in out:
        out = sorted([*out, str(current)])
    return out


ROOM_BASE = (("verdieping", "text"), ("lijst", "text"), ("twin", "bool"))
ROOM_TEXTS = ("naam", "kort", "toegang")
ROOM_LANGS = ("nl", "fr", "en", "de")


def _room_template(file_rooms: dict[str, dict]) -> list[dict]:
    """Vaste velden voor elke uitzondering per kamer: verdieping, naam op de lijsten, twin, en per taal
    naam, kort en toegang. Talen en extra sleutels die in het hotelbestand staan, komen erbij."""
    seen = [k for v in file_rooms.values() for k in v]
    langs = list(dict.fromkeys([*ROOM_LANGS, *(k.rsplit("_", 1)[1] for k in seen
                                                if "_" in k and k.rsplit("_", 1)[0] in ROOM_TEXTS)]))
    keys = [(k, kind) for k, kind in ROOM_BASE] + [(f"{t}_{lg}", "text") for lg in langs for t in ROOM_TEXTS]
    known = {k for k, _ in keys}
    keys += [(k, _kind(v)) for room in file_rooms.values() for k, v in room.items() if k not in known]
    return [{"key": k, "type": kind} for k, kind in dict.fromkeys(keys)]


def _room_section(hotel_id: str, field_help: dict, changed: dict, per: dict, doc: dict | None) -> dict:
    file_rooms = hotels.room_exceptions(hotels.load_hotel_file(hotel_id))
    now = hotels.room_exceptions(hotels.load_hotel(hotel_id))
    template = _room_template(file_rooms | now)
    help_ = {f["key"]: next((field_help[(f"kamers.{r}", f["key"])] for r in file_rooms
                             if field_help.get((f"kamers.{r}", f["key"]))), "") for f in template}
    for f in template:
        f["help"] = help_[f["key"]]
    m = per.get(hotels.ROOM_EXCEPTIONS) if hotels.ROOM_EXCEPTIONS in changed else None
    return {"section": hotels.ROOM_EXCEPTIONS, "rooms": True, "free": False, "help": "", "fields": [],
            "template": template,
            "items": [{"room": r, "values": v} for r, v in now.items()],
            "default_items": [{"room": r, "values": v} for r, v in file_rooms.items()],
            "meta": {"updated_by": m["by"], "updated_at": m["at"]} if m else (
                {"updated_by": doc["updated_by"], "updated_at": doc["updated_at"]}
                if doc and any(k.startswith("kamers.") for k in changed) else {})}


def view(hotel_id: str) -> dict:
    """Alle instellingen met type, standaard, huidige waarde en uitleg, per sectie."""
    from hotel_checkin.guests import repository

    default = _sections(hotels.load_hotel_file(hotel_id))
    current = _sections(hotels.load_hotel(hotel_id))
    section_help, field_help = _comments(hotel_id)
    names = _env_names()
    sections = []
    for name, values in default.items():
        if name.startswith("kamers."):
            continue  # uitzonderingen per kamer: één sectie, zie _room_section
        if name == "whatsapp":
            continue  # sjablonen: tabblad WhatsApp (processes/whatsapp_templates.py), niet meer met de hand
        free = name in hotels.FREE_SECTIONS
        now = current.get(name, {})
        keys = list(dict.fromkeys(list(values) + (list(now) if free else [])))
        sections.append({
            "section": name, "free": free, "help": section_help.get(name, ""),
            "fields": [{
                "key": k, "type": "choice" if _choices(hotel_id, name, k) else _kind(values.get(k, now.get(k, ""))),
                "choices": _with_current(_choices(hotel_id, name, k), _legacy(name, k, now.get(k, values.get(k)))),
                "default": values.get(k),
                "value": _legacy(name, k, now.get(k, values.get(k))), "help": field_help.get((name, k), ""),
                "env": _env_override(hotel_id, name, k, names),
            } for k in keys],
        })
    doc = repository.get_config_doc(hotel_id, hotels.SETTINGS_DOC)
    changed = (doc or {}).get("value") or {}
    per = (repository.get_config_doc(hotel_id, META_DOC) or {}).get("value") or {}
    for sec in sections:
        # Wie deze sectie laatst wijzigde (monitor); niets = standaard uit het hotelbestand
        m = per.get(sec["section"]) if sec["section"] in changed else None
        sec["meta"] = {"updated_by": m["by"], "updated_at": m["at"]} if m else (
            {"updated_by": doc["updated_by"], "updated_at": doc["updated_at"]} if doc and sec["section"] in changed else {})
    rooms = _room_section(hotel_id, field_help, changed, per, doc)
    at = next((n + 1 for n, x in enumerate(sections) if x["section"] == "kamers"), len(sections))
    sections.insert(at, rooms)
    return {"sections": sections, "meta": {"source": "monitor" if doc else "file",
                                           "updated_by": doc["updated_by"] if doc else "",
                                           "updated_at": doc["updated_at"] if doc else ""}}


def _coerce(kind: str, value, where: str):
    if kind == "bool":
        return value in (True, "true", "True", 1, "1", "on")
    if kind in ("int", "float"):
        try:
            return int(value) if kind == "int" else float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{where}: geen getal") from None
    if kind == "list":
        if isinstance(value, str):
            value = [x.strip() for x in value.split(",")]
        return [str(x).strip() for x in value if str(x).strip()]
    if kind == "color" and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(value or "")):
        raise ValueError(f"{where}: kleur als #RRGGBB")
    return str(value if value is not None else "")


def validate(hotel_id: str, changes: dict) -> dict:
    """Alleen gekende secties en sleutels, met het type van het hotelbestand. Vrije secties
    (kamers, sjablonen) als tekst. Geeft enkel wat verschilt van het bestand."""
    default = _sections(hotels.load_hotel_file(hotel_id))
    out: dict[str, dict] = {}
    for section, values in (changes or {}).items():
        if section == hotels.ROOM_EXCEPTIONS:
            rooms = _validate_rooms(hotel_id, values)
            if rooms is not None:
                out[section] = rooms
            continue
        if section.startswith("kamers.") and section in default:
            continue  # oude vorm (één sectie per kamer): vervangen door de lijst hierboven
        if section not in default or not isinstance(values, dict):
            raise ValueError(f"Onbekende sectie: {section}")
        base = default[section]
        if section in hotels.FREE_SECTIONS:
            clean = {}
            for k, v in values.items():
                if not re.fullmatch(r"[\w.-]{1,60}", str(k)):
                    raise ValueError(f"{section}: ongeldige naam {k!r}")
                if str(v).strip():
                    clean[str(k)] = str(v).strip()
            if clean != base:
                out[section] = clean
            continue
        diff = {}
        for k, v in values.items():
            if k not in base:
                raise ValueError(f"{section}: onbekende instelling {k}")
            value = _coerce(_kind(base[k]), v, f"{section}.{k}")
            options = _choices(hotel_id, section, k, changes)
            if options and value not in options and value != base[k]:
                raise ValueError(f"{section}.{k}: kies uit {', '.join(options)}")
            if value != base[k]:
                diff[k] = value
        if diff:
            out[section] = diff
    return out


def _validate_rooms(hotel_id: str, values) -> dict | None:
    """Uitzonderingen per kamer: {kamernummer: {veld: waarde}}. Lege velden vallen weg. None = gelijk aan het bestand."""
    if not isinstance(values, dict):
        raise ValueError("Uitzonderingen per kamer: verkeerde vorm")  # noqa: TRY004 - getoond in de monitor
    file_rooms = hotels.room_exceptions(hotels.load_hotel_file(hotel_id))
    kinds = {f["key"]: f["type"] for f in _room_template(file_rooms)}
    out: dict[str, dict] = {}
    for room, fields in values.items():
        room = str(room).strip()
        if not re.fullmatch(r"[\w-]{1,20}", room):
            raise ValueError(f"Uitzonderingen per kamer: ongeldig kamernummer {room!r}")
        if room in out:
            raise ValueError(f"Uitzonderingen per kamer: kamer {room} staat er twee keer")
        if not isinstance(fields, dict):
            raise ValueError(f"Kamer {room}: verkeerde vorm")  # noqa: TRY004 - getoond in de monitor
        clean = {}
        for k, v in fields.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", str(k)):
                raise ValueError(f"Kamer {room}: ongeldige naam {k!r}")
            kind = kinds.get(k, "text")
            value = _coerce(kind, v, f"kamer {room}.{k}")
            if kind == "bool":
                if value or k in file_rooms.get(room, {}):
                    clean[k] = value
            elif str(value).strip() or (k in file_rooms.get(room, {}) and value == file_rooms[room][k]):
                clean[k] = str(value).strip()
        out[room] = clean
    return None if out == file_rooms else out


def save(hotel_id: str, changes: dict, user: str, only: list[str] | None = None) -> dict:
    """Bewaar de wijzigingen (fout met uitleg als iets niet klopt). Met only: alleen die secties (knop Bewaren of
    Terug naar standaard van één sectie); de andere secties blijven zoals ze bewaard waren."""
    from datetime import UTC, datetime

    from hotel_checkin.guests import repository

    doc = repository.get_config_doc(hotel_id, hotels.SETTINGS_DOC)
    before = dict((doc or {}).get("value") or {})
    if only:
        clean = validate(hotel_id, {k: v for k, v in (changes or {}).items() if k in only})
        drop = set(only) | ({k for k in before if k.startswith("kamers.")} if hotels.ROOM_EXCEPTIONS in only else set())
        merged = {k: v for k, v in before.items() if k not in drop} | clean
    else:
        merged = validate(hotel_id, changes)
    if merged:
        repository.set_config_doc(hotel_id, hotels.SETTINGS_DOC, merged, user)
    else:
        repository.delete_config_doc(hotel_id, hotels.SETTINGS_DOC)
    # Per sectie: wie wijzigde wat en wanneer (alleen secties waarvan de bewaarde waarde veranderde)
    per = dict((repository.get_config_doc(hotel_id, META_DOC) or {}).get("value") or {})
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for sec in set(before) | set(merged):
        if before.get(sec) != merged.get(sec):
            if sec in merged:
                per[sec] = {"by": user or "", "at": now}
            else:
                per.pop(sec, None)
    per = {k: v for k, v in per.items() if k in merged}
    if per:
        repository.set_config_doc(hotel_id, META_DOC, per, user)
    else:
        repository.delete_config_doc(hotel_id, META_DOC)
    hotels.forget_overrides(hotel_id)
    return view(hotel_id)


def reset(hotel_id: str) -> dict:
    """Terug naar het hotelbestand."""
    from hotel_checkin.guests import repository

    repository.delete_config_doc(hotel_id, hotels.SETTINGS_DOC)
    repository.delete_config_doc(hotel_id, META_DOC)
    hotels.forget_overrides(hotel_id)
    return view(hotel_id)
