"""Configuratie: eerst omgevingsvariabelen, anders Azure Key Vault.

Secrets komen nooit in de code of in git. In Azure staan ze in Key Vault en leest de
Function App of Container App ze met zijn Managed Identity.

Instellingen per hotel (hotel_setting), in deze volgorde:
1. eigen geheim van het hotel: omgevingsvariabele LUCCA_TWILIO_AUTH_TOKEN of Key Vault
   lucca-twilio-auth-token
2. hotelbestand config/hotels/<hotel_id>.toml: naam SECTIE_SLEUTEL, bv. TWILIO_SMS_FROM is
   [twilio] sms_from (alleen voor wat niet geheim is)
3. gedeelde instelling voor alle hotels: TWILIO_AUTH_TOKEN (omgeving of Key Vault)
Zo kan een hotel een eigen waarde krijgen (bv. een eigen Twilio-account) zonder codewijziging.
"""

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache
def _key_vault_client():
    url = os.environ.get("KEY_VAULT_URL")
    if not url:
        return None
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    return SecretClient(vault_url=url, credential=DefaultAzureCredential())


@lru_cache(maxsize=256)
def _from_key_vault(name: str) -> str | None:
    client = _key_vault_client()
    if client is None:
        return None
    try:
        return client.get_secret(name.replace("_", "-").lower()).value
    except Exception:  # noqa: BLE001 - secret bestaat niet
        return None


def _lookup(name: str) -> str | None:
    return os.environ.get(name) or _from_key_vault(name)


def get_setting(name: str, default: str | None = None, required: bool = True) -> str | None:
    """Lees een gedeelde instelling. Key Vault-namen gebruiken '-' in plaats van '_'."""
    value = _lookup(name)
    if value:
        return value
    if default is not None or not required:
        return default
    raise KeyError(f"Instelling ontbreekt: {name}")


def hotel_setting(
    hotel_id: str,
    name: str,
    default: str | None = None,
    required: bool = True,
    shared: bool = True,
) -> str | None:
    """Lees een instelling voor een hotel: eigen geheim, dan hotelbestand, dan gedeeld.

    shared=False: geen gedeelde waarde gebruiken (bv. het Lighthouse-wachtwoord, dat
    altijd van het hotel zelf moet zijn).
    """
    from hotel_checkin.core.hotels import load_hotel

    prefix = hotel_id.upper().replace("-", "_")
    value = _lookup(f"{prefix}_{name}")
    if value:
        return value
    section, _, key = name.lower().partition("_")
    value = load_hotel(hotel_id).get(section, {}).get(key)
    if value:
        return str(value)
    if shared:
        value = _lookup(name)
        if value:
            return value
    if default is not None or not required:
        return default
    raise KeyError(f"Instelling ontbreekt voor hotel {hotel_id}: {name}")
