"""Diagnose van de gastprofielen (alleen lezen). Geen namen of adressen in de uitvoer: alleen
tellingen, datums, kanalen en een korte hash van de naam, om dubbele profielen te verklaren.

Gebruik: python -m hotel_checkin.admin.guest_diag lucca
"""

from __future__ import annotations

import hashlib
import sys
from collections import Counter

from hotel_checkin.guests import profiles
from hotel_checkin.guests import repository as repo
from hotel_checkin.processes import guest_profiles as gp


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:6]


def main(hotel_id: str) -> None:
    ps = profiles.list_profiles(hotel_id)
    rs = repo.list_reservations(hotel_id)
    by_res = {r.reservation_id: r for r in rs}
    res_by_guest: dict[str, list] = {}
    for r in rs:
        if r.guest_id:
            res_by_guest.setdefault(r.guest_id, []).append(r)
    print(f"profielen: {len(ps)}, reservaties: {len(rs)}, zonder guest_id: {sum(1 for r in rs if not r.guest_id)}")
    print("profielen aangemaakt per dag:", sorted(Counter(p.created_at.date().isoformat() for p in ps if p.created_at).items())[-15:])
    print("zonder meegeteld verblijf:", sum(1 for p in ps if not p.stays), " zonder gekoppelde reservatie (guest_id):",
          sum(1 for p in ps if p.guest_id not in res_by_guest))
    ids = {p.guest_id for p in ps}
    print("reservaties met guest_id dat niet bestaat:", sum(1 for r in rs if r.guest_id and r.guest_id not in ids))
    m = gp.possible_matches(hotel_id, limit=500)
    print("voorstellen:", Counter(x["reason"] for x in m))
    pmap = {p.guest_id: p for p in ps}
    groups: dict[str, list] = {}
    for p in ps:
        if p.first_name or p.last_name:
            groups.setdefault(" ".join(sorted(gp.name_tokens(p.first_name, p.last_name))), []).append(p)
    dup = [g for g in groups.values() if len(g) > 1]
    print(f"namen met meer dan één profiel: {len(dup)}")
    for g in sorted(dup, key=len, reverse=True)[:25]:
        print(f"-- naam {_h(' '.join(sorted(gp.name_tokens(g[0].first_name, g[0].last_name))))}: {len(g)} profielen")
        for p in g:
            linked = res_by_guest.get(p.guest_id, [])
            listed = [by_res.get(i) for i in p.reservation_ids]
            desc = ", ".join(f"{r.source or '?'} {'…' + r.booking_number[-3:] if r.booking_number else ''} {r.arrival}>{r.departure} "
                             f"{r.status.value if hasattr(r.status, 'value') else r.status} kamers={len(r.rooms)} "
                             f"mail={'eigen' if r.guest.email and gp.is_own_email(r.guest.email) else ('relay' if r.guest.email else '-')} "
                             f"tel={'ja' if r.guest.phone else '-'}"
                             for r in linked)
            print(f"   prof {p.guest_id[:6]} gemaakt {p.created_at:%Y-%m-%d %H:%M} stays={p.stays} ids={len(p.reservation_ids)} "
                  f"(waarvan bestaand {sum(1 for x in listed if x)}) gekoppeld={len(linked)} | {desc}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "lucca")
