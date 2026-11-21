"""Bouwblok: WhatsApp-sjablonen bij Twilio (Content API) aanmaken, laten goedkeuren door Meta en de status opvragen.

Alleen de aanroepen naar Twilio; welke tekst, wanneer indienen en welke versie actief is, beslist
processes/whatsapp_templates.py. Een sjabloon bij Twilio kan na het indienen niet meer gewijzigd worden:
een nieuwe tekst is altijd een nieuw sjabloon (nieuwe SID) dat opnieuw goedgekeurd moet worden.

Twilio-account: zelfde instellingen als sms en WhatsApp (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN).
"""

from __future__ import annotations

import httpx

from hotel_checkin.core import clients
from hotel_checkin.core.config import hotel_setting

CONTENT_API = "https://content.twilio.com/v1/Content"

# Statussen van Meta (via Twilio) waarbij het wachten is; de andere zijn definitief
# (approved, rejected) of vragen een tussenkomst (paused, disabled).
WAITING = ("received", "pending", "submitted", "unsubmitted", "")


class TemplateError(Exception):
    """Twilio weigerde de aanvraag (tekst met de reden van Twilio)."""


def build_types(body: str, button_title: str | None = None, button_url: str | None = None,
                footer: str | None = None, media_url: str | None = None) -> dict:
    """De inhoud van het sjabloon in de vorm van Twilio.
    - met pdf of foto bovenaan: twilio/media
    - met knop en voettekst: twilio/card (de voettekst is bij WhatsApp de subtitle)
    - met knop: twilio/call-to-action
    - alleen tekst: twilio/text (met voettekst: twilio/card zonder knop)"""
    actions = [{"type": "URL", "title": button_title, "url": button_url}] if button_title and button_url else []
    if media_url:
        return {"twilio/media": {"body": body, "media": [media_url]}}
    if footer:
        card = {"title": body, "subtitle": footer}
        if actions:
            card["actions"] = actions
        return {"twilio/card": card}
    if actions:
        return {"twilio/call-to-action": {"body": body, "actions": actions}}
    return {"twilio/text": {"body": body}}


def _auth(hotel_id: str) -> tuple[str, str]:
    return (hotel_setting(hotel_id, "TWILIO_ACCOUNT_SID"), hotel_setting(hotel_id, "TWILIO_AUTH_TOKEN"))


def _error(response: httpx.Response) -> TemplateError:
    try:
        d = response.json()
        return TemplateError(f"Twilio {response.status_code}, code {d.get('code')}: {d.get('message')}")
    except ValueError:
        return TemplateError(f"Twilio {response.status_code}: {response.text[:300]}")


def create(hotel_id: str, friendly_name: str, language: str, samples: dict[str, str], types: dict,
           client: httpx.Client | None = None) -> str:
    """Nieuw sjabloon bij Twilio. samples: voorbeeldwaarden per plaats ({"1": "Jan"}), Meta vraagt ze bij het
    goedkeuren. Geeft de SID (HX...)."""
    http = client or clients.http()
    r = http.post(CONTENT_API, json={"friendly_name": friendly_name, "language": language,
                                     "variables": samples, "types": types}, auth=_auth(hotel_id))
    if r.status_code not in (200, 201):
        raise _error(r)
    return r.json()["sid"]


def submit_whatsapp(hotel_id: str, sid: str, name: str, category: str = "UTILITY",
                    client: httpx.Client | None = None) -> dict:
    """Ter goedkeuring bij Meta indienen. name: kleine letters, cijfers en _ (uniek in het WhatsApp-account).
    Geeft {"status": ..., "reason": ...}."""
    http = client or clients.http()
    r = http.post(f"{CONTENT_API}/{sid}/ApprovalRequests/whatsapp", json={"name": name, "category": category},
                  auth=_auth(hotel_id))
    if r.status_code not in (200, 201):
        raise _error(r)
    d = r.json()
    return {"status": str(d.get("status") or "received").lower(), "reason": d.get("rejection_reason") or ""}


def approval_status(hotel_id: str, sid: str, client: httpx.Client | None = None) -> dict:
    """Status bij Meta: {"status": approved|received|pending|rejected|paused|disabled|..., "reason": ...}."""
    http = client or clients.http()
    r = http.get(f"{CONTENT_API}/{sid}/ApprovalRequests", auth=_auth(hotel_id))
    if r.status_code != 200:
        raise _error(r)
    wa = r.json().get("whatsapp") or {}
    return {"status": str(wa.get("status") or "").lower(), "reason": wa.get("rejection_reason") or ""}


def delete(hotel_id: str, sid: str, client: httpx.Client | None = None) -> None:
    """Sjabloon bij Twilio verwijderen (een vervangen versie die nog niet goedgekeurd was)."""
    http = client or clients.http()
    r = http.delete(f"{CONTENT_API}/{sid}", auth=_auth(hotel_id))
    if r.status_code not in (200, 204, 404):
        raise _error(r)
