"""Bouwblok: de geheimen in Key Vault bekijken en wijzigen vanuit de monitor (pagina Technisch).

Wie wat mag, beslist Azure zelf: de aangemelde gebruiker (object-id uit de ingebouwde login) moet op de Key Vault
een rol hebben. Key Vault Secrets User = bekijken; Key Vault Secrets Officer of Key Vault Administrator = bekijken
en wijzigen. Zonder rol toont de monitor de geheimen niet. De Function App leest de rollen (Reader op de Key Vault)
en schrijft met haar eigen identiteit (Key Vault Secrets Officer, infra/main.bicep).

Per hotel alleen de gedeelde geheimen en die van dat hotel (<hotel_id>-<naam>), niet die van andere hotels.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from hotel_checkin.core.hotels import list_hotels

ROLES = {
    "4633458b-17de-408a-b874-0445c86b69e6": "read",   # Key Vault Secrets User
    "b86a8fe4-44ce-4948-aee5-eccb2c155cd7": "write",  # Key Vault Secrets Officer
    "00482a5a-887f-4fb3-b363-3b7fe8e74483": "write",  # Key Vault Administrator
}
ACCESS_SECONDS = 120
_access: dict[str, tuple[str, float]] = {}


def _vault():
    from hotel_checkin.core.config import _key_vault_client

    return _key_vault_client()


def access(user_oid: str) -> str:
    """"write", "read" of "" voor deze gebruiker, volgens zijn rollen op de Key Vault (ook geërfd)."""
    vault_id = os.environ.get("KEY_VAULT_ID", "")
    if not user_oid or not vault_id:
        return ""
    hit = _access.get(user_oid)
    if hit and hit[1] > time.monotonic():
        return hit[0]
    from hotel_checkin.core.clients import azure_credential, http

    token = azure_credential().get_token("https://management.azure.com/.default").token
    url = (f"https://management.azure.com{vault_id}/providers/Microsoft.Authorization/roleAssignments"
           f"?api-version=2022-04-01&$filter=assignedTo('{user_oid}')")
    with http() as client:
        response = client.get(url, headers={"Authorization": f"Bearer {token}"})
    level = ""
    if response.status_code == 200:
        found = {ROLES.get(a["properties"]["roleDefinitionId"].rsplit("/", 1)[-1], "")
                 for a in response.json().get("value", [])}
        level = "write" if "write" in found else "read" if "read" in found else ""
    _access[user_oid] = (level, time.monotonic() + ACCESS_SECONDS)
    return level


def _allowed(hotel_id: str, name: str) -> bool:
    others = [h for h in list_hotels() if h != hotel_id]
    return not any(name.startswith(f"{h}-") for h in others)


def list_secrets(hotel_id: str) -> list[dict]:
    """Namen (zonder waarde), wanneer gewijzigd en door wie (tag updated_by)."""
    vault = _vault()
    if vault is None:
        return []
    out = []
    for p in vault.list_properties_of_secrets():
        if not p.enabled or not _allowed(hotel_id, p.name):
            continue
        out.append({"name": p.name, "updated": p.updated_on.astimezone(UTC).isoformat() if p.updated_on else "",
                    "updated_by": (p.tags or {}).get("updated_by", ""),
                    "hotel": p.name.startswith(f"{hotel_id}-"), "portal": portal_link(p.name)})
    return sorted(out, key=lambda s: (not s["hotel"], s["name"]))


def portal_link(name: str) -> str:
    """Link naar het geheim in de Azure Portal (daar is de werkelijke waarde en de geschiedenis te zien)."""
    url = os.environ.get("KEY_VAULT_URL", "").rstrip("/")
    return f"https://portal.azure.com/#asset/Microsoft_Azure_KeyVault/Secret/{url}/secrets/{name}" if url else ""


def reveal(hotel_id: str, name: str) -> str | None:
    vault = _vault()
    if vault is None or not _allowed(hotel_id, name):
        return None
    return vault.get_secret(name).value


def save(hotel_id: str, name: str, value: str, user: str) -> bool:
    """Nieuwe versie van een bestaand geheim. De Function App gebruikt ze binnen enkele minuten."""
    vault = _vault()
    if vault is None or not _allowed(hotel_id, name) or not value.strip():
        return False
    if name not in {s["name"] for s in list_secrets(hotel_id)}:
        return False
    vault.set_secret(name, value.strip(), tags={"updated_by": user,
                                                "updated_at": datetime.now(UTC).isoformat(timespec="seconds")})
    from hotel_checkin.core.config import clear_cache

    clear_cache()
    return True
