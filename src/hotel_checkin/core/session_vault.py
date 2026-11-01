"""Bouwblok: sessies van de robot bewaren in een aparte Key Vault (kv-session-<omgeving>-...).

Alleen voor wat de robot zelf moet kunnen schrijven, zoals de sessiecookies van Lighthouse. Daarom
een eigen kluis: de robot heeft hier schrijfrechten (Key Vault Secrets Officer), maar in de gewone
kluis met de wachtwoorden (Lighthouse, Salto, Twilio) alleen leesrechten. De Function App kan hier niet bij.

Instelling SESSION_VAULT_URL (zie infra/main.bicep). Leeg (bv. in de codespace): niet beschikbaar,
de robot houdt de sessie dan gewoon in een bestand.
"""

from __future__ import annotations

import os
from functools import lru_cache

MAX_CHARS = 24_000  # een geheim in Key Vault mag max. 25 KB zijn


def available() -> bool:
    return bool(os.environ.get("SESSION_VAULT_URL"))


@lru_cache
def _client():
    from azure.keyvault.secrets import SecretClient

    from hotel_checkin.core.clients import azure_credential

    return SecretClient(vault_url=os.environ["SESSION_VAULT_URL"], credential=azure_credential())


def _name(name: str) -> str:
    return name.replace("_", "-").lower()


def get(name: str) -> str | None:
    from azure.core.exceptions import ResourceNotFoundError

    try:
        return _client().get_secret(_name(name)).value
    except ResourceNotFoundError:
        return None


def put(name: str, value: str) -> bool:
    """Bewaar (nieuwe versie). False als de waarde te groot is."""
    if len(value) > MAX_CHARS:
        return False
    _client().set_secret(_name(name), value, content_type="application/json")
    return True
