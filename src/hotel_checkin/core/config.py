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

import logging
import os
import time
from functools import lru_cache


@lru_cache
def _key_vault_client():
    url = os.environ.get("KEY_VAULT_URL")
    if not url:
        return None
    from azure.keyvault.secrets import SecretClient

    from hotel_checkin.core.clients import azure_credential

    return SecretClient(vault_url=url, credential=azure_credential())


# Waarden uit Key Vault even onthouden: niet bij elke oproep naar Key Vault, maar een gewijzigd of
# nieuw geheim (bv. berichten aan of uit) werkt binnen enkele minuten, zonder herstart.
CACHE_SECONDS = 300
_cache: dict[str, tuple[str | None, float]] = {}


def clear_cache() -> None:
    _cache.clear()


def _from_key_vault(name: str) -> str | None:
    client = _key_vault_client()
    if client is None:
        return None
    hit = _cache.get(name)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    from azure.core.exceptions import ResourceNotFoundError

    try:
        value = client.get_secret(name.replace("_", "-").lower()).value
    except ResourceNotFoundError:
        value = None  # bestaat niet: ook onthouden (de meeste namen bestaan niet, bv. per hotel)
    except Exception:
        logging.warning("Key Vault: %s niet gelezen", name, exc_info=True)
        return None
    _cache[name] = (value, time.monotonic() + CACHE_SECONDS)
    return value


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
