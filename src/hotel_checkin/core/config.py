"""Configuratie: eerst omgevingsvariabelen, anders Azure Key Vault.

Secrets komen nooit in de code of in git. In Azure staan ze in Key Vault en leest de
Function App of Container App ze met zijn Managed Identity.
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


def get_setting(name: str, default: str | None = None, required: bool = True) -> str | None:
    """Lees een instelling. Key Vault-namen gebruiken '-' in plaats van '_'."""
    value = os.environ.get(name)
    if value:
        return value
    client = _key_vault_client()
    if client is not None:
        try:
            return client.get_secret(name.replace("_", "-")).value
        except Exception:  # noqa: BLE001 - secret bestaat niet, val terug op default
            pass
    if default is not None or not required:
        return default
    raise KeyError(f"Instelling ontbreekt: {name}")
