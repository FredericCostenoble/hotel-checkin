"""Diagnose (alleen lezen): is de index van de lijsten opgebouwd en klopt hij met de tabellen?"""

import sys

from hotel_checkin.guests import index, profiles
from hotel_checkin.guests import repository as repo


def main(hotel_id: str) -> None:
    print("versie:", repo.get_state(hotel_id, "list_index_version"), "verwacht:", index.VERSION)
    pk = f"PartitionKey eq '{hotel_id}'"
    res_idx = {e["RowKey"] for e in repo._table(index.T_RES_INDEX).query_entities(pk, select=["RowKey"])}
    gst_idx = {e["RowKey"] for e in repo._table(index.T_GUEST_INDEX).query_entities(pk, select=["RowKey"])}
    res = {repo._key(r.reservation_id) for r in repo.list_reservations(hotel_id)}
    gst = {g.guest_id for g in profiles.list_profiles(hotel_id)}
    print(f"reservaties: {len(res)}, in index: {len(res_idx)}, ontbreken: {len(res - res_idx)}, te veel: {len(res_idx - res)}")
    print(f"gasten: {len(gst)}, in index: {len(gst_idx)}, ontbreken: {len(gst - gst_idx)}, te veel: {len(gst_idx - gst)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "lucca")
