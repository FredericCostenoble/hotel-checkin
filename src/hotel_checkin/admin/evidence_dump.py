"""Het bewijs van de zelftest uit de opslag halen, voor de herstelrobot (.github/workflows/repair.yml).

    python -m hotel_checkin.admin.evidence_dump lucca --out lighthouse-explore/repair

Schrijft per onderdeel dat niet klopte de pagina (HTML) en een overzicht (health.json): wat de robot niet meer
vond en sinds wanneer. Alleen lezen. Nodig: STORAGE_TABLE_ENDPOINT en toegang tot de opslag (Azure-aanmelding).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hotel_checkin.guests import repository as guests
from hotel_checkin.processes import pms_health


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("hotel_id")
    p.add_argument("--out", default="lighthouse-explore/repair")
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    health = pms_health.state(args.hotel_id)
    (out / "health.json").write_text(json.dumps(health, indent=2, ensure_ascii=False), encoding="utf-8")
    keys = [f["evidence"] for f in health.get("failures", []) if f.get("evidence")]
    for e in guests.evidence_list(args.hotel_id):
        if keys and e["key"] not in keys:
            continue
        content = guests.get_evidence(args.hotel_id, e["key"]) or ""
        (out / f"{e['part']}.html").write_text(content, encoding="utf-8")
        print(f"{e['part']}: {e.get('why', '')} ({len(content)} tekens)")
    print(f"Klaar: {out}")


if __name__ == "__main__":
    main()
