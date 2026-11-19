"""Gegevens voor de opvolgpagina (web/admin). Alleen lezen, behalve de robot starten.

Bevat gastgegevens: in de cloud alleen achter een Microsoft-login.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, date, datetime, timedelta

from hotel_checkin.core import clock
from hotel_checkin.core.addresses import is_own_email, relay_platform
from hotel_checkin.core.hotels import list_hotels, load_hotel
from hotel_checkin.guests import repository as repo

_robot_lock = threading.Lock()
_robot_state: dict[str, str] = {}  # hotel_id -> "bezig" / laatste fout


def hotels() -> list[dict]:
    """Hotels voor de keuzelijst, met waar berichten in deze omgeving echt naartoe gaan: in PRD naar
    de gast, daarbuiten naar het testadres en testnummer (leeg = er wordt niets verstuurd)."""
    from hotel_checkin.core import safety
    from hotel_checkin.processes import send_messages

    prd = safety.is_production()
    return [{"id": h, "name": load_hotel(h)["hotel"]["naam"], "production": prd,
             "logo_url": load_hotel(h)["hotel"].get("logo_url", ""),  # logo bovenaan de monitor
             "test_email": "" if prd else (safety.test_address("email", h) or ""),
             "test_phone": "" if prd else (safety.test_address("phone", h) or ""),
             "phone_enabled": send_messages.phone_enabled(h),
             # hoofdschakelaars (per omgeving): bovenaan de monitor getoond
             "switches": {"reservaties": send_messages.switch(h, "reservaties"),
                          "overschrijvingen": send_messages.switch(h, "overschrijvingen"),
                          "berichten": send_messages.mode(h),  # uit, aan of selectie
                          "ontbijt_labels": send_messages.switch(h, "ontbijt_labels"),
                          "ontbijtlijst": send_messages.switch(h, "ontbijtlijst"),
                          "kuislijst": send_messages.switch(h, "kuislijst"),
                          "ontgrendelen": send_messages.switch(h, "ontgrendelen")}}
            for h in list_hotels()]


def _app_link(hotel_id: str, r) -> str:
    """Link naar de gast-app van deze reservatie (knop Gast-app bekijken in de monitor)."""
    if not r.token:
        return ""
    try:
        from hotel_checkin.messaging import templates
        return templates.checkin_link(hotel_id, r.token, r.guest.language)
    except Exception:  # noqa: BLE001 - geen formulieradres ingesteld: geen knop
        return ""


def hotel_name(hotel_id: str) -> str:
    return load_hotel(hotel_id)["hotel"]["naam"]


def daily_list(hotel_id: str, kind: str, day: str) -> dict | None:
    """Eén bewaarde ontbijt- of kuislijst (voor de Excel), of None."""
    try:
        date.fromisoformat(day)
    except ValueError:
        return None
    return repo.get_daily_list(hotel_id, kind, day)


def _parallel(fn, items, workers: int = 8) -> list:
    """Dezelfde opvraging voor veel sleutels tegelijk (Table Storage: één punt-opvraging per sleutel)."""
    items = list(items)
    if len(items) <= 1:
        return [fn(x) for x in items]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        return list(pool.map(fn, items))


PAGE = 50
RES_SORT = {"arrival", "departure", "booking_number", "guest", "room", "source", "pms_status", "email", "status"}


def _sort_key(value):
    """Lege waarden altijd onderaan, getallen als getal, tekst zonder hoofdletters."""
    if value in ("", None):
        return (1, 0, "")
    if isinstance(value, (int, float)):
        return (0, value, "")
    return (0, 0, str(value).lower())


def _page(rows: list[dict], sort: str, desc: bool, offset: int, limit: int, value) -> tuple[list[dict], int]:
    filled = [r for r in rows if value(r, sort) not in ("", None)]
    empty = [r for r in rows if value(r, sort) in ("", None)]
    filled.sort(key=lambda r: (_sort_key(value(r, sort)), r.get("id", "")), reverse=desc)
    ordered = filled + empty
    return ordered[offset:offset + limit], len(ordered)


def reservations_page(hotel_id: str, q: str = "", date_from: str = "", date_to: str = "", status: str = "",
                      sort: str = "arrival", desc: bool = False, offset: int = 0, limit: int = PAGE,
                      ids: list[str] | None = None, window: tuple[str, str] | None = None) -> dict:
    """Een pagina reservaties voor de monitor: zoeken, filteren en sorteren gebeurt op de index (guests/index.py),
    de volledige gegevens alleen voor de getoonde rijen.

    ids: precies deze reservaties (detail, gastprofiel, link vanuit Vandaag). window: (van, tot) voor Vandaag:
    alles wat in die periode aankomt, vertrekt of verblijft, zonder paginering."""
    from hotel_checkin.guests import index

    rows = index.reservations(hotel_id)
    if ids is not None:
        want = set(ids)
        rows = [r for r in rows if r["id"] in want]
    elif window is not None:
        a, b = window
        failed = repo.failed_message_reservations(hotel_id)  # Vandaag toont ook mislukte berichten van later
        rows = [r for r in rows if (r["departure"] >= a and r["arrival"] <= b) or (r["id"] in failed and r["departure"] >= a)]
        limit = len(rows)
    else:
        ql = q.lower().strip()
        rows = [r for r in rows if (not date_from or r["departure"] >= date_from) and (not date_to or r["arrival"] <= date_to)
                and (not status or (status == "cancelled") == (r["status"] == "cancelled"))
                and (not ql or ql in r["search"])]
    sort = sort if sort in RES_SORT else "arrival"

    def value(r, k):
        if k == "room":
            return ", ".join(r.get("rooms") or []) or r.get("room_type", "")
        if k == "email":
            return r.get("email") or r.get("phone") or ""
        return r.get(k, "")
    page, total = _page(rows, sort, desc, max(0, offset), max(1, min(limit if ids is None else len(rows) or 1, 500)), value)
    full = _parallel(lambda x: repo.get_reservation(hotel_id, x["id"]), page)
    items = reservations(hotel_id, only=[r for r in full if r])
    return {"items": items, "total": total, "offset": offset, "next": offset + len(page) if offset + len(page) < total else None}


def reservations(hotel_id: str, only: list | None = None, msgs_by_res: dict | None = None) -> list[dict]:
    """Volledige gegevens per reservatie voor de monitor. only: alleen deze reservaties (Reservation-objecten),
    met alleen hun gastprofielen en berichten; None = alle (oude manier, voor tests en het overzicht)."""
    from hotel_checkin.core import workflow
    from hotel_checkin.guests import profiles
    from hotel_checkin.processes import send_messages

    if only is None:
        all_profiles = profiles.list_profiles(hotel_id)
    else:
        ids = {r.guest_id for r in only if r.guest_id}
        all_profiles = [p for p in _parallel(lambda gid: profiles.get_profile(hotel_id, gid), sorted(ids)) if p]
    periods = {g.guest_id: g.stay_periods for g in all_profiles}
    muted = {g.guest_id: set(g.muted_channels) for g in all_profiles}
    own_email = {g.guest_id: g.email for g in all_profiles if g.email_own and g.email}
    # Adressen en nummers uit het gastprofiel (ook van vroegere verblijven), voor de keuzelijst bij versturen
    profile_contacts = {g.guest_id: {"emails": list(dict.fromkeys(e for e in [g.email, g.backup_email, *g.known_emails] if e)),
                                     "phones": list(dict.fromkeys(p for p in [g.phone, g.backup_phone, *g.known_phones] if p))}
                        for g in all_profiles}
    phone = send_messages.phone_enabled(hotel_id)
    from hotel_checkin.pms.lighthouse_browser import base_url
    lighthouse = base_url(hotel_id) + "/Customer/Reservations/Detail/"
    cfg, ready = workflow.config(hotel_id), send_messages.ready_steps(hotel_id)
    begin, on, today = send_messages.start(hotel_id), send_messages.enabled(hotel_id), clock.today(hotel_id)
    chosen = send_messages.selected_ids(hotel_id)

    def earlier_stays(r) -> int:
        """Verblijven van de gast buiten de periode van deze reservatie (terugkerende gast)."""
        a, d = r.arrival.isoformat(), r.departure.isoformat()
        return sum(1 for pa, pd in periods.get(r.guest_id, []) if not (a < pd and d > pa))
    out = []
    if msgs_by_res is not None:
        all_msgs = msgs_by_res
    elif only is None:
        all_msgs = repo.messages_for_hotel(hotel_id)  # één query voor alle berichten, niet één per reservatie
    else:
        all_msgs = dict(zip([r.reservation_id for r in only],
                            _parallel(lambda r: repo.messages_for(hotel_id, r.reservation_id), only), strict=True))
    for r in (repo.list_reservations(hotel_id) if only is None else only):
        msgs = all_msgs.get(r.reservation_id, [])
        out.append({
            "id": r.reservation_id,
            "booking_number": r.booking_number or "",
            "lighthouse_url": lighthouse + r.reservation_id,  # het id is de GUID van Lighthouse
            # Detailpagina van de reservatie (monitor): pincodes, betaling en de gast-app van deze gast
            "access_codes": [{"room": c.get("room", ""), "pin": c.get("pin", ""), "created_at": c.get("created_at", "")} for c in r.access_codes],
            "pms_codes_at": r.pms_codes_at.isoformat() if r.pms_codes_at else "",
            "access_valid_from": r.access_valid_from.isoformat() if r.access_valid_from else "",
            "access_valid_until": r.access_valid_until.isoformat() if r.access_valid_until else "",
            "codes_in_pms": bool(r.pms_codes_line),
            "paid": r.paid, "open_amount": r.open_amount, "folio": r.folio, "folio_total": r.folio_total,
            "payout_registered_at": r.payout_registered_at.isoformat() if r.payout_registered_at else "",
            "pay_requested_at": r.pay_requested_at.isoformat() if r.pay_requested_at else "",
            "pay_link": r.pay_link or "",
            "app_link": _app_link(hotel_id, r),
            "room_moves": r.room_moves,
            # Gebeurtenissen voor de detailpagina (alleen tijdstippen die al bewaard worden)
            "breakfast_labeled_at": r.breakfast_labeled_at.isoformat() if r.breakfast_labeled_at else "",
            "stairs_label_at": r.stairs_label_at.isoformat() if r.stairs_label_at else "",
            "contact_checked_at": r.contact_checked_at.isoformat() if r.contact_checked_at else "",
            "pms_labels": r.pms_labels,
            "arrival": r.arrival.isoformat(),
            "departure": r.departure.isoformat(),
            "guest": f"{r.guest.first_name} {r.guest.last_name}".strip(),
            "email": r.guest.email or "",
            "phone": r.guest.phone or "",
            "backup_email": r.guest.backup_email or "",
            "backup_phone": r.guest.backup_phone or "",
            "relay_email": r.guest.relay_email or "",
            "email_platform": relay_platform(r.guest.email) or "",
            "relay_platform": relay_platform(r.guest.relay_email) or "",
            "profile_emails": profile_contacts.get(r.guest_id or "", {}).get("emails", []),
            "profile_phones": profile_contacts.get(r.guest_id or "", {}).get("phones", []),
            "language": r.guest.language,
            "guests": r.guest_count,
            "room_type": r.room_type or "",
            "rooms": r.rooms,
            "rate_plan": r.rate_plan or "",
            "non_refundable": r.non_refundable,
            "source": r.source or "",
            "flow": workflow.flow_for(hotel_id, r, cfg),  # welke workflow: volgens "Via" (en betaalstatus)
            "pms_status": r.pms_status or "",
            "status": r.status.value,
            "booked_at": r.booked_at.isoformat() if r.booked_at else "",
            "checkin_completed_at": r.checkin_completed_at.isoformat() if r.checkin_completed_at else "",
            "stairs": bool(r.stairs_help),  # formulier: moeilijk ter been
            "messages_on": send_messages.for_reservation(hotel_id, r, chosen),  # krijgt automatische berichten
            "messages_pick": "on" if r.reservation_id in chosen["on"] else "off" if r.reservation_id in chosen["off"] else "",
            "stairs_memo_at": r.stairs_memo_at.isoformat() if r.stairs_memo_at else "",
            "guest_id": r.guest_id or "",
            "guest_stays": earlier_stays(r) if r.guest_id else 0,
            "added_at": r.created_at.isoformat() if r.created_at else "",
            "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            "plan": send_messages.plan(hotel_id, r, msgs, cfg, ready, today, begin, on, phone,
                                       muted.get(r.guest_id or "", set()), own_email.get(r.guest_id or ""), chosen),
            "messages": [
                {"type": m["message_type"], "channel": m["channel"], "ok": m["ok"], "at": m["sent_at"],
                 "to": m.get("recipient", ""), "delivered_to": m.get("delivered_to", ""), "status": m.get("status") or ("sent" if m["ok"] else "failed"),
                 "error": m.get("error", ""), "note": m.get("note", ""), "status_at": m.get("status_at", ""),
                 "problem": message_problem(m) if not m["ok"] else "", "dismissed_at": m.get("dismissed_at", "")}
                for m in msgs
            ],
        })
    return out


def message_problem(m: dict) -> str:
    """Wat er functioneel misliep met een bericht, als code voor de monitor (de technische fout blijft apart)."""
    err, ch = str(m.get("error") or "").lower(), m.get("channel", "")
    if not err and m.get("status") in ("undelivered", "failed"):
        return "not_delivered"
    if "graph 401" in err or "graph 403" in err or "erroraccessdenied" in err or "authorization" in err:
        return "mail_rights" if ch == "email" else "provider_rights"
    if "20003" in err or "authenticate" in err:
        return "provider_rights"
    if any(x in err for x in ("invalidrecipient", "invalid recipient", "21211", "21614", "63003", "not a valid", "not a mobile")):
        return "bad_address"
    if any(x in err for x in ("63016", "outside the allowed window", "template")):
        return "template"
    if m.get("status") in ("undelivered", "failed"):
        return "not_delivered"
    if "timeout" in err or "timed out" in err or "connection" in err or " 5" in err[:12]:
        return "unavailable"
    return "other"


def dismiss_failed(hotel_id: str, reservation_id: str, user: str) -> dict:
    """Negeren op Vandaag: de mislukte berichten van deze reservatie niet meer als aandachtspunt tonen."""
    n = repo.dismiss_failed_messages(hotel_id, reservation_id, user)
    return {"ok": True, "dismissed": n}


def runs(hotel_id: str) -> dict:
    from hotel_checkin.core import progress

    return {"running": _robot_state.get(hotel_id) == "bezig", "progress": progress.current(hotel_id), "runs": [
        {k: e.get(k) for k in ("task", "started_at", "finished_at", "ok", "found", "new", "error", "skipped",
                               "process_started_at", "execution")}
        | {"timings": json.loads(e.get("timings") or "{}"), "id": e.get("RowKey")}
        for e in repo.robot_runs(hotel_id, limit=200)
    ]}


def guests(hotel_id: str, only: list | None = None, with_matches: bool = True) -> dict:
    """Gastprofielen en mogelijke dubbels voor de monitor. only: alleen deze profielen (GuestProfile), met alleen
    hun eigen reservaties; None = alle."""
    from hotel_checkin.guests import profiles
    from hotel_checkin.processes import guest_profiles

    opted_out = {e for e in repo.opted_out_emails(hotel_id)}
    opted_out_by_guest = {e for e in opted_out if repo.opt_out_source(hotel_id, e) not in (None, "monitor")}
    res_by_guest: dict[str, list] = {}
    if only is None:
        for r in repo.list_reservations(hotel_id):
            if r.guest_id:
                res_by_guest.setdefault(r.guest_id, []).append(r)
    else:
        pairs = [(g.guest_id, rid) for g in only for rid in g.reservation_ids]
        for (gid, _), r in zip(pairs, _parallel(lambda p: repo.get_reservation(hotel_id, p[1]), pairs), strict=True):
            if r and r.guest_id == gid:
                res_by_guest.setdefault(gid, []).append(r)
    out = []
    for g in (profiles.list_profiles(hotel_id) if only is None else only):
        channels = sorted(g.channels.items(), key=lambda kv: -kv[1])
        rooms = sorted(g.rooms.items(), key=lambda kv: -kv[1])
        out.append({
            "id": g.guest_id, "name": f"{g.first_name} {g.last_name}".strip(),
            "email": g.email or "", "email_own": g.email_own, "phone": g.phone or "",
            "backup_email": g.backup_email or "", "backup_phone": g.backup_phone or "",
            "known_emails": g.known_emails, "known_phones": g.known_phones,
            "relay_emails": sorted({r.guest.relay_email or r.guest.email for r in res_by_guest.get(g.guest_id, [])
                                    if relay_platform(r.guest.relay_email or r.guest.email)}),
            "language": g.language, "country": g.country or "", "form": g.from_checkin_form,
            "opt_out": bool(g.email and g.email.lower() in opted_out),
            # Wat de robot echt gebruikt (zelfde regels als send_messages.recipients) en waarvoor de gast toestemming gaf:
            # adressen uit het check-in-formulier (marketing volgt de keuze in het formulier), bevestigde gsm-nummers
            "prefs": g.contact_prefs,
            "form_emails": sorted({e.lower() for x in res_by_guest.get(g.guest_id, []) if x.checkin_completed_at
                                   for e in (x.guest.email, x.guest.backup_email) if e and is_own_email(e)}),
            "consent_phones": sorted({p for x in res_by_guest.get(g.guest_id, []) for p in (x.guest.phone_consent or [])}),
            # Marketing per eigen adres: op de blokkeerlijst, en of de gast dat zelf vroeg (dan niet terug aan te zetten)
            "marketing_off": sorted({e.lower() for e in [g.email, g.backup_email, *g.known_emails]
                                     if e and e.lower() in opted_out}),
            "marketing_by_guest": sorted({e.lower() for e in [g.email, g.backup_email, *g.known_emails]
                                          if e and e.lower() in opted_out_by_guest}),
            "first_stay": g.first_stay.isoformat() if g.first_stay else "",
            "last_stay": g.last_stay.isoformat() if g.last_stay else "",
            "stays": g.stays, "nights": g.nights, "cancellations": g.cancellations,
            "last_cancelled": g.last_cancelled.isoformat() if g.last_cancelled else "",
            "avg_nights": round(g.nights / g.stays, 1) if g.stays else None,
            "avg_persons": round(g.persons / g.persons_stays, 1) if g.persons_stays else None,
            "rooms": [k for k, _ in rooms], "room_type": max(g.room_types, key=g.room_types.get) if g.room_types else "",
            "channels": [{"name": k, "count": v} for k, v in channels],
            "preferred_channel": channels[0][0] if channels else "",
            # Nog geen meegeteld verblijf (toekomstige reservatie): kanaal en aankomst van de laatste reservatie
            "booked_source": max(res_by_guest.get(g.guest_id, []), key=lambda r: r.arrival).source or "" if res_by_guest.get(g.guest_id) else "",
            "booked_arrival": max(r.arrival for r in res_by_guest[g.guest_id]).isoformat() if res_by_guest.get(g.guest_id) else "",
            "muted": g.muted_channels,
            "reservations": g.reservation_ids,
            "updated_at": g.updated_at.isoformat() if g.updated_at else "",
        })
    return {"guests": out, "matches": guest_profiles.possible_matches(hotel_id) if with_matches else []}


def list_request(hotel_id: str, what: str, params) -> dict | list:
    """GET reservations/guests van de monitor. Met page=1: per pagina (q, from, to, status, sort, dir, offset,
    limit, ids, window); zonder: de volledige lijst zoals vroeger (oudere pagina's die nog open staan)."""
    p = {k: (params.get(k) or "") for k in ("page", "q", "from", "to", "status", "sort", "dir", "offset", "limit",
                                             "ids", "window")}
    ids = [x for x in p["ids"].split(",") if x] if p["ids"] else None
    num = lambda v, d: int(v) if str(v).isdigit() else d
    if what == "reservations":
        if not p["page"]:
            return reservations(hotel_id)
        window = tuple(p["window"].split(",", 1)) if "," in p["window"] else None
        return reservations_page(hotel_id, p["q"], p["from"], p["to"], p["status"], p["sort"] or "arrival",
                                 p["dir"] == "desc", num(p["offset"], 0), num(p["limit"], PAGE), ids, window)
    if not p["page"]:
        return guests(hotel_id)
    return guests_page(hotel_id, p["q"], p["sort"] or "last_stay", p["dir"] != "asc", num(p["offset"], 0),
                       num(p["limit"], PAGE), ids)


GUEST_SORT = {"name", "country", "stays", "reservations", "last_stay", "first_stay", "preferred_channel"}


def guests_page(hotel_id: str, q: str = "", sort: str = "last_stay", desc: bool = True, offset: int = 0,
                limit: int = PAGE, ids: list[str] | None = None) -> dict:
    """Een pagina gastprofielen: zoeken en sorteren op de index, volledige gegevens alleen voor de getoonde
    rijen. De mogelijke dubbels (Te beslissen) komen mee met de eerste pagina."""
    from hotel_checkin.guests import index, profiles
    from hotel_checkin.processes import guest_profiles

    rows = index.guests(hotel_id)
    if ids is not None:
        want = set(ids)
        rows = [r for r in rows if r["id"] in want]
    else:
        ql = q.lower().strip()
        rows = [r for r in rows if not ql or ql in r["search"]]
    sort = sort if sort in GUEST_SORT else "last_stay"
    page, total = _page(rows, sort, desc, max(0, offset), max(1, min(limit if ids is None else len(rows) or 1, 500)),
                        lambda r, k: r.get(k, ""))
    full = [p for p in _parallel(lambda x: profiles.get_profile(hotel_id, x["id"]), page) if p]
    data = guests(hotel_id, only=full, with_matches=False)
    out = {"guests": data["guests"], "total": total, "offset": offset,
           "next": offset + len(page) if offset + len(page) < total else None}
    if ids is None and offset == 0:
        matches = guest_profiles.possible_matches(hotel_id)
        out["matches"] = matches
        # De gasten uit de voorstellen meesturen, ook als ze niet op deze pagina staan
        need = sorted({x for m in matches for x in (m["a"], m["b"])} - {g["id"] for g in out["guests"]})
        extra = [p for p in _parallel(lambda gid: profiles.get_profile(hotel_id, gid), need) if p]
        out["match_guests"] = guests(hotel_id, only=extra, with_matches=False)["guests"]
    return out


def merge_guests(hotel_id: str, keep: str, other: str) -> bool:
    from hotel_checkin.processes import guest_profiles

    return hotel_id in list_hotels() and guest_profiles.merge(hotel_id, keep, other) is not None


def select_for_messages(hotel_id: str, reservation_id: str, on: bool) -> dict:
    """Automatische berichten voor één reservatie aan of uit (monitor), bovenop de hoofdschakelaar."""
    from hotel_checkin.processes import send_messages

    if hotel_id not in list_hotels() or repo.get_reservation(hotel_id, reservation_id) is None:
        return {"ok": False, "error": "Reservatie niet gevonden"}
    send_messages.set_selected(hotel_id, reservation_id, on)
    return {"ok": True, "on": on, "mode": send_messages.mode(hotel_id)}


def add_contact(hotel_id: str, reservation_id: str, email: str, phone: str) -> dict:
    """Met de hand een e-mailadres of gsm-nummer toevoegen aan een reservatie (monitor), bv. als
    Lighthouse er geen heeft. Komt als hoofdadres als er nog geen is, anders als extra adres.
    Daarna kunnen berichten (met de hand of automatisch) verstuurd worden."""
    from hotel_checkin.checkin.service import EMAIL_RE, normalize_phone
    from hotel_checkin.processes import guest_profiles

    r = repo.get_reservation(hotel_id, reservation_id) if hotel_id in list_hotels() else None
    if r is None:
        return {"ok": False, "error": "Reservatie niet gevonden"}
    email = (email or "").strip().lower()
    if email and not EMAIL_RE.match(email):
        return {"ok": False, "error": "Ongeldig e-mailadres"}
    number = normalize_phone(phone) if (phone or "").strip() else None
    if (phone or "").strip() and number is None:
        return {"ok": False, "error": "Ongeldig gsm-nummer (met landcode, bv. +32...)"}
    if not email and not number:
        return {"ok": False, "error": "Geef een e-mailadres of gsm-nummer"}
    if email:
        if not r.guest.email:
            r.guest.email = email
        elif email != r.guest.email.lower():
            r.guest.backup_email = email
    if number:
        if not r.guest.phone:
            r.guest.phone = number
        elif number != r.guest.phone:
            r.guest.backup_phone = number
    saved = repo.save_reservation(r, fields=("email", "phone", "backup_email", "backup_phone"))
    try:
        guest_profiles.link(saved)
    except Exception:  # noqa: BLE001 - het adres is bewaard; het profiel volgt bij het synchroniseren
        pass
    return {"ok": True}


def resend(hotel_id: str, reservation_id: str, step: str, channel: str, to: str, user: str) -> dict:
    from hotel_checkin.processes import send_messages

    if hotel_id not in list_hotels() or channel not in ("email", "whatsapp", "sms"):
        return {"ok": False, "error": "Onbekend hotel of kanaal"}
    return send_messages.resend(hotel_id, reservation_id, step, channel, to, user)


def set_muted_channels(hotel_id: str, guest_id: str, muted: list[str]) -> bool:
    """Kanalen voor één gast uit- of aanzetten (tabblad Gasten)."""
    from hotel_checkin.guests import profiles

    g = profiles.get_profile(hotel_id, guest_id) if hotel_id in list_hotels() else None
    if g is None:
        return False
    g.muted_channels = sorted({c for c in muted if c in ("email", "whatsapp", "sms")})
    profiles.save_profile(g)
    return True


def detach_reservation(hotel_id: str, reservation_id: str) -> dict:
    """Knop Ontkoppelen in het gastprofiel (processes/guest_profiles.py, detach)."""
    from hotel_checkin.processes import guest_profiles

    if hotel_id not in list_hotels() or not reservation_id:
        return {"ok": False}
    g = guest_profiles.detach(hotel_id, reservation_id)
    return {"ok": g is not None, "guest": g.guest_id if g else ""}


def set_contact_pref(hotel_id: str, guest_id: str, channel: str, address: str, on: bool) -> bool:
    """Vinkje Verblijf bij één adres van een gast (tabblad Gasten): de robot gebruikt dit adres wel of nooit voor
    berichten over het verblijf (send_messages.recipients)."""
    from hotel_checkin.checkin.service import placeholder_phone
    from hotel_checkin.guests import profiles
    from hotel_checkin.processes import send_messages

    g = profiles.get_profile(hotel_id, guest_id) if hotel_id in list_hotels() else None
    if g is None or channel not in ("email", "whatsapp", "sms") or not address:
        return False
    if channel != "email" and placeholder_phone(address):
        return False  # nepnummer van een boekingssite: nooit
    g.contact_prefs[send_messages.pref_key(channel, address)] = bool(on)
    g.muted_channels = [c for c in g.muted_channels if c != channel]  # vanaf nu per adres
    profiles.save_profile(g)
    send_messages._PREFS.pop((hotel_id, guest_id), None)
    return True


def set_marketing(hotel_id: str, email: str, on: bool) -> dict:
    """Vinkje Marketing bij een e-mailadres (tabblad Gasten). Uit: op de blokkeerlijst. Aan: er weer af, maar alleen
    als het hotel het zelf uitzette; vroeg de gast zelf geen marketing (formulier, uitschrijflink), dan blijft het uit."""
    if hotel_id not in list_hotels() or "@" not in (email or ""):
        return {"ok": False}
    source = repo.opt_out_source(hotel_id, email)
    if on:
        if source not in (None, "monitor"):
            return {"ok": False, "error": "De gast vroeg zelf geen marketing; dat kan het hotel niet terug aanzetten."}
        repo.remove_opt_out(hotel_id, email)
    elif source is None:
        repo.add_opt_out(hotel_id, email, "monitor")
    return {"ok": True}


def mark_guests_different(hotel_id: str, a: str, b: str) -> bool:
    from hotel_checkin.guests import profiles

    if hotel_id not in list_hotels() or not a or not b:
        return False
    profiles.mark_different(hotel_id, a, b)
    return True


def delete_run(hotel_id: str, run_id: str) -> bool:
    return hotel_id in list_hotels() and repo.delete_robot_run(hotel_id, run_id)


def delete_runs(hotel_id: str, task: str | None = None) -> int:
    """Alle regels uit het robotlogboek (of alleen die van één taak) verwijderen."""
    return repo.delete_robot_runs(hotel_id, task or None) if hotel_id in list_hotels() else 0


def start_robot(hotel_id: str, hours: int = 48) -> bool:
    """Start de robot (nieuwe reservaties) op de achtergrond. False als hij al loopt."""
    from hotel_checkin.processes import new_reservation

    if hotel_id not in list_hotels() or not _robot_lock.acquire(blocking=False):
        return False

    _robot_state[hotel_id] = "bezig"

    def work():
        try:
            new_reservation.run(hotel_id, datetime.now(UTC) - timedelta(hours=hours))
            _robot_state[hotel_id] = ""
        except Exception as exc:  # noqa: BLE001 - staat ook in het robotlog
            _robot_state[hotel_id] = str(exc)
        finally:
            _robot_lock.release()

    threading.Thread(target=work, daemon=True).start()
    return True


# ---------------------------------------------------------------- workflow (tabblad Workflow)


def workflow_view(hotel_id: str) -> dict:
    """De geldende workflow plus de keuzes voor het scherm."""
    from hotel_checkin.core import workflow
    from hotel_checkin.processes import send_messages

    cfg = workflow.config(hotel_id)
    # Welke waarden van "Via" (Lighthouse) bij welke flow terechtkomen, uit de bewaarde reservaties
    seen: dict[str, dict[str, int]] = {f: {} for f in workflow.FLOWS}
    for r in repo.list_reservations(hotel_id):
        flow, via = workflow.flow_for(hotel_id, r, cfg), r.source or "?"
        seen[flow][via] = seen[flow].get(via, 0) + 1
    return {**cfg, "ready": list(send_messages.ready_steps(hotel_id)),
            "seen_sources": {f: sorted(v.items(), key=lambda kv: -kv[1]) for f, v in seen.items()}, "choices": {
        "flows": list(workflow.FLOWS), "when": list(workflow.WHEN), "channels": list(workflow.CHANNELS),
        "pay": list(workflow.PAY), "conditions": list(workflow.CONDITIONS), "steps": list(workflow.STEP_TYPES),
        "city_tax_units": list(workflow.CITY_TAX_UNITS),
    }}


def settings_view(hotel_id: str) -> dict:
    """Instellingen van het hotel (tabblad Hotel op de instellingenpagina)."""
    from hotel_checkin.core import hotel_settings

    return hotel_settings.view(hotel_id)


def settings_save(hotel_id: str, changes: dict, user: str, only: list[str] | None = None) -> tuple[bool, dict]:
    from hotel_checkin.core import hotel_settings

    try:
        return True, hotel_settings.save(hotel_id, changes, user, only)
    except ValueError as exc:
        return False, {"error": str(exc)}


def settings_reset(hotel_id: str) -> dict:
    from hotel_checkin.core import hotel_settings

    return hotel_settings.reset(hotel_id)


def workflow_save(hotel_id: str, cfg: dict, user: str) -> tuple[bool, dict]:
    """(True, nieuwe workflow) of (False, {"error": uitleg})."""
    from hotel_checkin.core import workflow

    try:
        workflow.save_config(hotel_id, cfg, user)
    except ValueError as exc:
        return False, {"error": str(exc)}
    return True, workflow_view(hotel_id)


def workflow_reset(hotel_id: str) -> dict:
    from hotel_checkin.core import workflow

    workflow.reset_config(hotel_id)
    return workflow_view(hotel_id)


def workflow_preview(hotel_id: str, body: dict) -> dict:
    """Voorbeeldmail voor een stap zoals ze nu op het scherm staat (ook niet bewaard), met
    voorbeeldgegevens. body: {"step": {...}, "flow": "booking", "rate": "nfr", "language": "nl"}."""
    from datetime import timedelta

    from hotel_checkin.core import workflow
    from hotel_checkin.core.models import Guest, Reservation
    from hotel_checkin.messaging import templates
    from hotel_checkin.processes import send_messages

    language = body.get("language") or "nl"
    raw = body.get("step") or {}
    cfg = workflow.config(hotel_id)
    try:
        if body.get("parameters"):
            cfg = {**cfg, "parameters": workflow.validate(hotel_id, {"parameters": body["parameters"], "flows": cfg["flows"]})["parameters"]}
        rate = body.get("rate") if body.get("rate") in workflow.RATES else "standard"
        step = workflow.Step(step=raw["step"], when=raw.get("when", "after_booking"), days=int(raw.get("days", 0) or 0),
                             pay=raw.get("pay", "none"), content={k: bool(v) for k, v in (raw.get("content") or {}).items()},
                             rates={k: dict(v) for k, v in (raw.get("rates") or {}).items() if isinstance(v, dict)}
                             ).for_rate(rate)
    except (KeyError, TypeError, ValueError) as exc:
        return {"error": str(exc)}
    source = {"booking": "Booking.com", "expedia": "Expedia"}.get(body.get("flow", ""), "Website")
    arrival = date.today() + timedelta(days=14)
    sample = Reservation(hotel_id, "voorbeeld", Guest("Anna", "Peeters", language=language), arrival,
                         arrival + timedelta(days=2), guest_count=2, source=source)
    # voorbeeldfolio: kamer voor 2 nachten, toeristenbelasting voor 2 personen, voorschot betaald
    sample.folio = [{"label": "Superior Double Room - Standard rate", "qty": None, "amount": 240.0},
                    {"label": "Citytax", "qty": 4, "amount": 20.0}]
    sample.folio_total, sample.open_amount = 260.0, 245.0
    if rate == "nfr":  # niet annuleerbaar: kamer betaald, alleen de toeristenbelasting staat nog open
        sample.non_refundable, sample.open_amount = True, 20.0
    data = {**templates.sample_data(language), **send_messages.pay_data(hotel_id, sample, cfg),
            "token": "voorbeeld-" + hotel_id,  # werkende link naar het formulier (voorbeeld, niets bewaard)
            "betaal_link": "#betalen"}
    if not step.enabled:
        return {"error": "Niets aangevinkt voor dit tarief: deze mail gaat niet weg."}
    msg = templates.render(hotel_id, step.step, language, data, step.mail_content(), step.pay)
    return {"subject": msg.subject, "html": msg.html}
