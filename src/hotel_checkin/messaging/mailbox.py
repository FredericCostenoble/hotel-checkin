"""Bouwblok: mails lezen uit de mailbox van een hotel (Microsoft Graph), en een gelezen mail naar
een map verplaatsen (bv. de betaalverzoeken van Lighthouse naar "Betaalverzoeken").

Doet één ding: berichten ophalen (afzender, onderwerp, tijdstip, tekst) of verplaatsen. Wat ermee gebeurt
(bv. een melding van Lighthouse/Cubilis herkennen) zit in een ander bouwblok; wanneer de robot
start, beslist een proces.

Mailbox per hotel: config/hotels/<hotel_id>.toml, [verzending] mail_afzender (checkin@...).
Rechten (Exchange RBAC for Applications, alleen voor die mailbox):
    New-ManagementRoleAssignment -App <client-id hotel-checkin> -Role "Application Mail.Read" `
      -CustomResourceScope "hotel-checkin-mailbox"
Verplaatsen vraagt ook "Application Mail.ReadWrite" (zelfde commando, andere rol). Zonder dat recht
blijft de mail gewoon in de inbox staan; de rest werkt.

Verkennen in de codespace (schrijft naar mail-explore/, niet in git, gastgegevens gemaskeerd):
    python -m hotel_checkin.messaging.mailbox lucca --days 3
"""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from hotel_checkin.core import clients
from hotel_checkin.core.config import hotel_setting
from hotel_checkin.messaging.email import GRAPH_URL, _get_token


def mailbox_address(hotel_id: str) -> str:
    return hotel_setting(hotel_id, "VERZENDING_MAIL_AFZENDER", shared=False)


def list_messages(
    hotel_id: str, since: datetime, client: httpx.Client | None = None, limit: int = 100,
) -> list[dict]:
    """Berichten in de inbox sinds `since`, oudste eerst: id, received_at, sender, subject, text."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    http = client or clients.http()
    url = f"{GRAPH_URL}/users/{mailbox_address(hotel_id)}/mailFolders/inbox/messages"
    params = {
        "$filter": f"receivedDateTime ge {since.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}",
        "$orderby": "receivedDateTime asc",
        "$select": "id,receivedDateTime,from,subject,body",
        "$top": str(min(limit, 50)),
    }
    headers = {
        "Authorization": f"Bearer {_get_token() if client is None else 'test'}",
        "Prefer": 'outlook.body-content-type="text"',  # tekst in plaats van HTML
    }
    out: list[dict] = []
    while url and len(out) < limit:
        r = http.get(url, params=params, headers=headers)
        r.raise_for_status()
        data = r.json()
        for m in data.get("value", []):
            out.append({
                "id": m["id"],
                "received_at": datetime.fromisoformat(m["receivedDateTime"]),
                "sender": ((m.get("from") or {}).get("emailAddress") or {}).get("address", "").lower(),
                "subject": m.get("subject") or "",
                "text": (m.get("body") or {}).get("content") or "",
            })
        url, params = data.get("@odata.nextLink"), None
    return out[:limit]


_folders: dict[tuple[str, str], str] = {}  # (mailbox, mapnaam) -> id


def _folder_id(http: httpx.Client, box: str, name: str, headers: dict) -> str:
    """Id van de map onder de inbox met deze naam; bestaat ze nog niet, dan maken."""
    key = (box, name)
    if key in _folders:
        return _folders[key]
    base = f"{GRAPH_URL}/users/{box}/mailFolders/inbox/childFolders"
    r = http.get(base, params={"$filter": f"displayName eq '{name}'"}, headers=headers)
    r.raise_for_status()
    found = r.json().get("value", [])
    if found:
        _folders[key] = found[0]["id"]
    else:
        r = http.post(base, json={"displayName": name}, headers=headers)
        r.raise_for_status()
        _folders[key] = r.json()["id"]
    return _folders[key]


def move_message(hotel_id: str, message_id: str, folder: str, client: httpx.Client | None = None) -> bool:
    """Verplaats een mail naar een map onder de inbox. False als het niet lukt (bv. geen recht
    Mail.ReadWrite): de mail blijft dan staan, er gaat niets verloren."""
    http = client or clients.http()
    box = mailbox_address(hotel_id)
    headers = {"Authorization": f"Bearer {_get_token() if client is None else 'test'}"}
    try:
        target = _folder_id(http, box, folder, headers)
        r = http.post(f"{GRAPH_URL}/users/{box}/messages/{message_id}/move", json={"destinationId": target},
                      headers=headers)
        return r.status_code in (200, 201)
    except Exception:  # noqa: BLE001 - verplaatsen is netjes, niet nodig
        return False


# ---------------------------------------------------------------- verkennen (alleen lezen)

OUT = Path("mail-explore")
_NAME_LABELS = ("naam", "name", "nom", "gast", "guest", "client", "klant", "contact", "booker", "voornaam",
                "achternaam", "first", "last", "prénom", "adres", "address", "adresse", "straat", "street")


def mask(text: str, names: list[str]) -> str:
    """Gastgegevens weglaten: gekende namen, e-mail, telefoon, waarden bij naam- en adresvelden,
    lange vrije tekst. Labels, datums, bedragen en reservatienummers blijven staan."""
    out = []
    in_guest_block = False
    for line in [x.rstrip() for x in text.splitlines()]:
        # Cubilis: "Gemaakt door <naam> op <datum>", daarna naam en adres op losse regels tot "Aankomst:"
        if re.match(r"\s*(Gemaakt door|Made by|Created by|Créée? par|Erstellt von)\b", line, re.IGNORECASE):
            line = re.sub(r"\b(door|by|par|von)\b.*?\b(op|on|le|am)\b", r"\1 <naam> \2", line, count=1, flags=re.IGNORECASE)
            out.append(line)
            in_guest_block = True
            continue
        if in_guest_block:
            if re.match(r"\s*(Aankomst|Arrival|Arrivée|Anreise)\b", line, re.IGNORECASE):
                in_guest_block = False
            elif line.strip():
                out.append("<gastgegevens>")
                continue
        line = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "<email>", line)
        # telefoon: begint met +, 00 of 0, alleen spaties/punten als scheiding, minstens 9 cijfers
        line = re.sub(r"(?<![\w/-])(?:\+|0)\d[\d .]{7,}\d(?![\w/-])",
                      lambda m: "<tel>" if len(re.sub(r"\D", "", m.group(0))) >= 9 else m.group(0), line)
        for n in names:
            if len(n) > 2:
                line = re.sub(rf"\b{re.escape(n)}\b", "<naam>", line, flags=re.IGNORECASE)
        label, sep, value = line.partition(":")
        if sep and value.strip() and any(w in label.lower() for w in _NAME_LABELS):
            line = f"{label}: <waarde>"
        if len(line) > 100:
            line = f"<tekst {len(line)} tekens>"
        out.append(line)
    return "\n".join(out)


def _known_names(hotel_id: str) -> list[str]:
    try:
        from hotel_checkin.guests import repository as guests

        names = set()
        for r in guests.list_reservations(hotel_id):
            names.update(w for w in f"{r.guest.first_name} {r.guest.last_name}".split() if len(w) > 2)
        return sorted(names, key=len, reverse=True)
    except Exception:  # noqa: BLE001 - zonder opslag: alleen de andere regels
        return []


def main() -> None:
    p = argparse.ArgumentParser(description="Mails in de mailbox van het hotel tonen, gemaskeerd (alleen lezen)")
    p.add_argument("hotel_id")
    p.add_argument("--days", type=int, default=3)
    args = p.parse_args()
    since = datetime.now(UTC) - timedelta(days=args.days)
    messages = list_messages(args.hotel_id, since)
    names = _known_names(args.hotel_id)
    report = [f"# Mailbox {mailbox_address(args.hotel_id)} sinds {since:%d/%m %H:%M} UTC: {len(messages)} berichten", ""]
    for m in messages:
        report += [f"## {m['received_at']:%d/%m %H:%M} van {m['sender']}",
                   f"Onderwerp: {mask(m['subject'], names)}", "", mask(m["text"], names), ""]
    OUT.mkdir(exist_ok=True)
    (OUT / "mails.md").write_text("\n".join(report), encoding="utf-8")
    print(f"{len(messages)} berichten. Klaar: {OUT}/mails.md (gemaskeerd; kijk het na voor je het deelt).")


if __name__ == "__main__":
    main()
