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

EXCLUDED = ("flows",)  # tabblad Workflow
# Instellingen met een vaste keuzelijst
CHOICES = {("workflow_parameters", "city_tax_unit"): ("person_night", "person_stay")}


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


def _fallback(section: str, key: str) -> str:
    """Waarde die geldt als het veld leeg is: voor het testadres dat van de omgeving."""
    if section == "test" and key in ("email", "phone"):
        from hotel_checkin.core.config import get_setting

        try:
            return get_setting(f"TEST_{key.upper()}", required=False) or ""
        except Exception:  # noqa: BLE001
            return ""
    return ""


def view(hotel_id: str) -> dict:
    """Alle instellingen met type, standaard, huidige waarde en uitleg, per sectie."""
    from hotel_checkin.guests import repository

    default = _sections(hotels.load_hotel_file(hotel_id))
    current = _sections(hotels.load_hotel(hotel_id))
    section_help, field_help = _comments(hotel_id)
    names = _env_names()
    sections = []
    for name, values in default.items():
        free = name in hotels.FREE_SECTIONS
        now = current.get(name, {})
        keys = list(dict.fromkeys(list(values) + (list(now) if free else [])))
        sections.append({
            "section": name, "free": free, "help": section_help.get(name, ""),
            "fields": [{
                "key": k, "type": "choice" if (name, k) in CHOICES else _kind(values.get(k, now.get(k, ""))),
                "choices": list(CHOICES.get((name, k), ())), "default": values.get(k),
                "value": now.get(k, values.get(k)), "help": field_help.get((name, k), ""),
                "env": _env_override(hotel_id, name, k, names),
                "fallback": _fallback(name, k),
            } for k in keys],
        })
    doc = repository.get_config_doc(hotel_id, hotels.SETTINGS_DOC)
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
            if (section, k) in CHOICES and value not in CHOICES[(section, k)]:
                raise ValueError(f"{section}.{k}: kies uit {', '.join(CHOICES[(section, k)])}")
            if value != base[k]:
                diff[k] = value
        if diff:
            out[section] = diff
    return out


def save(hotel_id: str, changes: dict, user: str) -> dict:
    """Bewaar de wijzigingen (fout met uitleg als iets niet klopt)."""
    from hotel_checkin.guests import repository

    clean = validate(hotel_id, changes)
    if clean:
        repository.set_config_doc(hotel_id, hotels.SETTINGS_DOC, clean, user)
    else:
        repository.delete_config_doc(hotel_id, hotels.SETTINGS_DOC)
    hotels.forget_overrides(hotel_id)
    return view(hotel_id)


def reset(hotel_id: str) -> dict:
    """Terug naar het hotelbestand."""
    from hotel_checkin.guests import repository

    repository.delete_config_doc(hotel_id, hotels.SETTINGS_DOC)
    hotels.forget_overrides(hotel_id)
    return view(hotel_id)
