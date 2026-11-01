"""Gedeelde verbindingen, één keer gemaakt per proces.

- http(): één httpx-client voor Graph, Twilio en Salto. Hergebruikt verbindingen (keep-alive) en laat
  geen open verbindingen achter, wat wel gebeurde met een nieuwe client per oproep.
- azure_credential(): één DefaultAzureCredential. Die houdt de tokens zelf in het geheugen bij; een
  nieuwe per oproep vroeg telkens een nieuw token aan (managed identity, Key Vault, Graph, ARM).
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache
def http():
    import httpx

    return httpx.Client(timeout=30)


@lru_cache
def azure_credential():
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()
