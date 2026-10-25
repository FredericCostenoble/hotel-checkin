"""Instellingen per hotel (multi-hotel).

Elk hotel heeft een bestand config/hotels/<hotel_id>.toml. De hotel_id is de bestandsnaam,
bv. "lucca". Alles wat per hotel verschilt (naam, kleuren, uren, privacylinks, afzender) staat daar.
Geheimen per hotel (Lighthouse, Salto, ...) staan in Key Vault als <hotel_id>-<naam>.
"""

from __future__ import annotations

import os
import re
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
def load_hotel(hotel_id: str) -> dict:
    """De instellingen van een hotel. Fout als het hotel niet bestaat."""
    path = hotels_dir() / f"{_check_id(hotel_id)}.toml"
    if not path.is_file():
        raise KeyError(f"Onbekend hotel: {hotel_id}")
    with open(path, "rb") as f:
        return tomllib.load(f)


def list_hotels() -> list[str]:
    return sorted(p.stem for p in hotels_dir().glob("*.toml"))


def secret_name(hotel_id: str, name: str) -> str:
    """Naam van een geheim per hotel in Key Vault, bv. lucca-lighthouse-password."""
    return f"{_check_id(hotel_id)}-{name}"
