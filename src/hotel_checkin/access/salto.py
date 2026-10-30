"""Bouwblok 6: Salto KS via de KS Connect API. Alleen praten met Salto, geen beslissingen.

Per boeking (zie processes/grant_access.py, dat deze functies combineert):
  1. gebruiker aanmaken                      create_user
  2. access group met deuren en periode      create_access_group, add_locks, add_time_schedule
  3. gebruiker in de group, pincode          add_user_to_group, create_pin
Opruimen na vertrek of bij annulering: delete_user, delete_access_group.

Instellingen per hotel (core/config.py, hotel_setting):
  Key Vault: <hotel>-salto-client-id, -client-secret, -username, -password (systeemgebruiker)
  Hotelbestand [salto]: identity_url, api_url, site_id, guest_role_id (leeg = eerste rol met
  "guest"/"gast" in de naam), lock_ids van gemeenschappelijke deuren en per kamer in [salto.rooms].
Documentatie en links: projectnotitie claude/salto-ks-connect.md.

Setup in de codespace (toont deuren en rollen om de kamers te koppelen):
    python -m hotel_checkin.access.salto lucca
"""

from __future__ import annotations

import sys
import time
from datetime import datetime

import httpx

from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.hotels import load_hotel
from hotel_checkin.core.models import AccessCode

DEFAULT_IDENTITY_URL = "https://identity-acc.eu.my-clay.com"  # test (accept); productie: https://identity.eu.my-clay.com
DEFAULT_API_URL = "https://clp-accept-user.my-clay.com"  # test (accept)

_tokens: dict[str, tuple[str, float]] = {}  # hotel -> (token, vervalt op)


class SaltoError(RuntimeError):
    pass


def configured(hotel_id: str) -> bool:
    """Is Salto ingesteld voor dit hotel (site en aanmeldgegevens)?"""
    return bool(hotel_setting(hotel_id, "SALTO_SITE_ID", required=False, shared=False)
                and hotel_setting(hotel_id, "SALTO_USERNAME", required=False, shared=False))


def _setting(hotel_id: str, name: str, default: str | None = None) -> str:
    return hotel_setting(hotel_id, name, default=default, shared=False)


def _token(hotel_id: str, client: httpx.Client) -> str:
    cached = _tokens.get(hotel_id)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    url = _setting(hotel_id, "SALTO_IDENTITY_URL", DEFAULT_IDENTITY_URL).rstrip("/") + "/connect/token"
    r = client.post(url, data={
        "grant_type": "password", "scope": "user_api.full_access",
        "username": _setting(hotel_id, "SALTO_USERNAME"), "password": _setting(hotel_id, "SALTO_PASSWORD"),
    }, auth=(_setting(hotel_id, "SALTO_CLIENT_ID"), _setting(hotel_id, "SALTO_CLIENT_SECRET")))
    if r.status_code != 200:
        raise SaltoError(f"Aanmelden bij Salto mislukt: {r.status_code} {r.text[:300]}")
    data = r.json()
    _tokens[hotel_id] = (data["access_token"], time.time() + int(data.get("expires_in", 3600)))
    return data["access_token"]


def _call(hotel_id: str, method: str, path: str, json: dict | None = None,
          client: httpx.Client | None = None):
    """Oproep naar de API van de site. path zonder site, bv. "/v1.2/sites/{site}/users"."""
    http = client or httpx.Client(timeout=30)
    base = _setting(hotel_id, "SALTO_API_URL", DEFAULT_API_URL).rstrip("/")
    url = base + path.replace("{site}", _setting(hotel_id, "SALTO_SITE_ID"))
    r = http.request(method, url, json=json, headers={"Authorization": f"Bearer {_token(hotel_id, http)}"})
    if r.status_code >= 400:
        raise SaltoError(f"Salto {method} {path}: {r.status_code} {r.text[:300]}")
    if not r.content:
        return None
    try:
        return r.json()
    except ValueError:
        return r.text.strip().strip('"')


# ---------------------------------------------------------------- gebruikers en pincodes


def guest_role_id(hotel_id: str, client: httpx.Client | None = None) -> str:
    """Rol voor gasten: [salto] guest_role_id, anders de eerste rol met guest/gast in de naam."""
    own = hotel_setting(hotel_id, "SALTO_GUEST_ROLE_ID", required=False, shared=False)
    if own:
        return own
    roles = _call(hotel_id, "GET", "/v1.2/sites/{site}/roles", client=client)
    for role in (roles or {}).get("items", roles if isinstance(roles, list) else []):
        if any(w in str(role.get("name", "")).lower() for w in ("guest", "gast")):
            return role["id"]
    raise SaltoError("Geen gastenrol gevonden: vul [salto] guest_role_id in")


def create_user(hotel_id: str, first_name: str, last_name: str, alias: str,
                client: httpx.Client | None = None) -> str:
    """Nieuwe gebruiker op de site (zonder e-mail: Salto stuurt dan geen uitnodiging). Geeft het id."""
    body = {"first_name": first_name or "-", "last_name": last_name or "-", "alias": alias,
            "role_ids": [guest_role_id(hotel_id, client)], "use_pin": True}
    return _call(hotel_id, "POST", "/v1.2/sites/{site}/users", body, client)["id"]


def create_pin(hotel_id: str, user_id: str, expiry: datetime | None, client: httpx.Client | None = None) -> str:
    """Laat Salto een pincode maken voor deze gebruiker; geeft de pincode terug."""
    body = {"expiry_date": expiry.strftime("%Y-%m-%dT%H:%M:%S") if expiry else None}
    pin = _call(hotel_id, "PUT", f"/v1.2/sites/{{site}}/users/{user_id}/pin", body, client)
    if isinstance(pin, dict):  # voor het geval Salto een object teruggeeft
        pin = pin.get("pin") or pin.get("value") or ""
    if not pin:
        raise SaltoError("Salto gaf geen pincode terug")
    return str(pin)


def delete_user(hotel_id: str, user_id: str, client: httpx.Client | None = None) -> None:
    _call(hotel_id, "DELETE", f"/v1.2/sites/{{site}}/users/{user_id}", client=client)


# ---------------------------------------------------------------- access groups


def create_access_group(hotel_id: str, name: str, client: httpx.Client | None = None) -> str:
    return _call(hotel_id, "POST", "/v1.2/sites/{site}/access_groups", {"customer_reference": name}, client)["id"]


def add_locks(hotel_id: str, group_id: str, lock_ids: list[str], client: httpx.Client | None = None) -> None:
    for lock_id in lock_ids:
        _call(hotel_id, "POST", f"/v1.2/sites/{{site}}/access_groups/{group_id}/locks", {"lock_id": lock_id}, client)


def add_time_schedule(hotel_id: str, group_id: str, valid_from: datetime, valid_until: datetime,
                      client: httpx.Client | None = None) -> None:
    """Elke dag, de hele dag, tussen check-in en check-out (datum met uur)."""
    body = {d: True for d in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}
    body |= {"start_time": "00:00", "end_time": "23:59",
             "start_date": valid_from.strftime("%Y-%m-%dT%H:%M:%S"), "end_date": valid_until.strftime("%Y-%m-%dT%H:%M:%S")}
    _call(hotel_id, "POST", f"/v1.1/sites/{{site}}/access_groups/{group_id}/time_schedules", body, client)


def add_user_to_group(hotel_id: str, group_id: str, user_id: str, client: httpx.Client | None = None) -> None:
    _call(hotel_id, "POST", f"/v1.2/sites/{{site}}/access_groups/{group_id}/users", {"user_id": user_id}, client)


def delete_access_group(hotel_id: str, group_id: str, client: httpx.Client | None = None) -> None:
    _call(hotel_id, "DELETE", f"/v1.2/sites/{{site}}/access_groups/{group_id}", client=client)


# ---------------------------------------------------------------- deuren


def list_locks(hotel_id: str, client: httpx.Client | None = None) -> list[dict]:
    data = _call(hotel_id, "GET", "/v1.2/sites/{site}/locks", client=client)
    return (data or {}).get("items", data if isinstance(data, list) else [])


def lock_ids_for(hotel_id: str, rooms: list[str]) -> list[str]:
    """Deuren voor deze kamers: gemeenschappelijke deuren ([salto] common_lock_ids) plus per kamer
    ([salto.rooms] "12" = "lock-id"). Fout als een kamer niet gekoppeld is."""
    cfg = load_hotel(hotel_id).get("salto", {})
    rooms_map = {str(k): v for k, v in cfg.get("rooms", {}).items()}
    missing = [r for r in rooms if r not in rooms_map]
    if missing:
        raise SaltoError(f"Kamer(s) {', '.join(missing)} niet gekoppeld aan een Salto-deur ([salto.rooms])")
    ids = list(cfg.get("common_lock_ids", []))
    for r in rooms:
        v = rooms_map[r]
        ids += v if isinstance(v, list) else [v]
    return list(dict.fromkeys(ids))


# ---------------------------------------------------------------- oude functies (send_access_code)


def reserve_code(reservation_id: str, room: str, valid_from: datetime, valid_until: datetime,
                 guest_name: str) -> AccessCode:
    raise NotImplementedError("Gebruik processes/grant_access.py")


def cancel_code(code: AccessCode) -> None:
    raise NotImplementedError("Gebruik processes/grant_access.revoke")


if __name__ == "__main__":
    hotel = sys.argv[1] if len(sys.argv) > 1 else "lucca"
    for lock in list_locks(hotel):
        print(f"{lock.get('id')}  {lock.get('customer_reference') or lock.get('name')}")
    roles = _call(hotel, "GET", "/v1.2/sites/{site}/roles")
    for role in (roles or {}).get("items", []):
        print(f"rol {role.get('id')}  {role.get('name')}")
