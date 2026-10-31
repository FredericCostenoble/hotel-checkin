"""Instellingen per hotel (multi-hotel).

Elk hotel heeft een bestand config/hotels/<hotel_id>.toml. De hotel_id is de bestandsnaam,
bv. "lucca". Alles wat per hotel verschilt (naam, kleuren, uren, privacylinks, afzender) staat daar.
Geheimen per hotel (Lighthouse, Salto, ...) staan in Key Vault als <hotel_id>-<naam>.
"""

from __future__ import annotations

import copy
import os
import re
import time
import tomllib
from functools import lru_cache
from pathlib import Path

_HERE = Path(__file__).resolve()
# config/ naast src/ (repo, codespace) of naast het pakket (Azure-deployment in api/)
_CANDIDATES = [_HERE.parents[3] / "config" / "hotels", _HERE.parents[2] / "config" / "hotels"]


def hotels_dir() -> Path:
    env = os.environ.get("HOTELS_CONFIG_DIR")
    if env:
        return Path(env)
    return next((p for p in _CANDIDATES if p.is_dir()), _CANDIDATES[0])


def _check_id(hotel_id: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,30}", hotel_id or ""):
        raise ValueError(f"Ongeldige hotel_id: {hotel_id!r}")
    return hotel_id


@lru_cache
def load_hotel_file(hotel_id: str) -> dict:
    """De standaardinstellingen uit config/hotels/<hotel_id>.toml. Fout als het hotel niet bestaat."""
    path = hotels_dir() / f"{_check_id(hotel_id)}.toml"
    if not path.is_file():
        raise KeyError(f"Onbekend hotel: {hotel_id}")
    with open(path, "rb") as f:
        return tomllib.load(f)


_OVERRIDES: dict[str, tuple[float, dict]] = {}  # hotel -> (gelezen op, wijzigingen uit de monitor)
OVERRIDES_SECONDS = 60


def overrides(hotel_id: str) -> dict:
    """In de monitor gewijzigde instellingen ({sectie: {sleutel: waarde}}), een minuut bewaard.
    Zonder opslag (bv. tests zonder database): geen wijzigingen."""
    cached = _OVERRIDES.get(hotel_id)
    if cached and time.monotonic() - cached[0] < OVERRIDES_SECONDS:
        return cached[1]
    try:
        from hotel_checkin.guests import repository

        doc = repository.get_config_doc(hotel_id, SETTINGS_DOC)
        value = doc["value"] if doc else {}
    except Exception:  # noqa: BLE001 - geen opslag: standaard uit het bestand
        value = {}
    _OVERRIDES[hotel_id] = (time.monotonic(), value)
    return value


def forget_overrides(hotel_id: str | None = None) -> None:
    """Na bewaren of terugzetten: meteen opnieuw lezen."""
    if hotel_id is None:
        _OVERRIDES.clear()
    else:
        _OVERRIDES.pop(hotel_id, None)


SETTINGS_DOC = "hotel_settings"


def load_hotel(hotel_id: str) -> dict:
    """De instellingen van een hotel: het hotelbestand, met de wijzigingen uit de monitor
    (instellingen, tabblad Hotel) erover. Geheimen staan in Key Vault, niet hier."""
    base = load_hotel_file(hotel_id)
    changes = overrides(hotel_id)
    if not changes:
        return base
    merged = copy.deepcopy(base)
    for section, values in changes.items():
        target = merged
        for part in section.split("."):  # bv. "salto.rooms"
            target = target.setdefault(part, {})
        if isinstance(values, dict) and section in FREE_SECTIONS:
            target.clear()  # vrije lijst (kamers, sjablonen): de bewaarde versie vervangt alles
        target.update(values)
    return merged


# Secties zonder vaste sleutels: kamer -> Salto-deur, WhatsApp-sjablonen per bericht en taal
FREE_SECTIONS = ("salto.rooms", "whatsapp")


def list_hotels() -> list[str]:
    return sorted(p.stem for p in hotels_dir().glob("*.toml"))


def secret_name(hotel_id: str, name: str) -> str:
    """Naam van een geheim per hotel in Key Vault, bv. lucca-lighthouse-password."""
    return f"{_check_id(hotel_id)}-{name}"
