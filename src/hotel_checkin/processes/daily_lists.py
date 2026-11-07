"""Proces: elke dag de ontbijtlijst en de schoonmaaklijst maken en versturen.

Hoofdschakelaars [schakelaars] ontbijtlijst en kuislijst (per omgeving, standaard uit). Aan = de lijst wordt elke
dag om [ontbijtlijst] uur / [kuislijst] uur gemaakt voor de dag [..] dag later (1 = morgen) en verstuurd per mail
(met de Excel als bijlage) en per WhatsApp (met sms als terugval). In de monitor (tabbladen Ontbijt en Schoonmaak) kan
een lijst altijd opnieuw gemaakt en verstuurd worden, ook met de schakelaar uit. Alleen de laatste KEEP lijsten
per soort blijven bewaard. Er staan geen gastnamen op, alleen kamers, aantallen en opmerkingen.

Ontbijtlijst voor dag D (ontbijt 's ochtends): wie de nacht ervoor sliep (aankomst voor D, vertrek op of na D) en
ontbijt heeft. Zelfde regel als het label ONTBIJT (processes/breakfast_labels.py): tarief met ontbijt, of ontbijt in
de folio voor alle personen en nachten, of het label werd door de robot gezet. Ontbijt als extra in de folio: de robot
leest per ontbijtregel de dagen en het aantal per dag (venster "Bewerken" achter de 3 puntjes), zodat ook één
bijgeboekte dag juist op de lijst komt. Kon hij de dagen niet lezen en is het ontbijt maar voor een deel van het
verblijf: de kamer komt in het geel, "nakijken". Meer kamers in één reservatie: de personen verdeeld over de kamers, met "samen met ...".

Schoonmaaklijst voor dag D, per kamer: Leave (vertrek op D), Stay (aankomst voor D, vertrek na D), Check in (aankomst op D).
Opmerkingen: zinnen uit de opmerking van de reservatie of lijnen van de folio met een van de woorden uit de
instellingen ([kuislijst] woorden, bv. babybed, romantisch), en het aantal personen bij een check in.

Planbord: de robot leest bij elke gevraagde lijst het planbord van Lighthouse voor die dag (alleen lezen). Daarop is
elke kamer een eigen blok met eigen aankomst, vertrek, aantal personen en labels, ook bij een groep met kamers op
verschillende data, en ook reservaties die de robot nog niet kent. Beide lijsten volgen de kamers en data van het
planbord; tarief, folio en opmerking komen uit de reservatie. Labels uit [kuislijst] labels (bv. BABY BED) komen bij
de opmerkingen. Kon de robot het planbord niet lezen, dan de kamers en data van de reservaties (staat bij de lijst).

Vers: een lijst wordt altijd gemaakt met wat de robot net in Lighthouse las. Lijst maken (monitor) of het uur van de
automatische lijst start de robot, die de reservaties van die dag leest (kamer, data, folio, opmerking); daarna maakt
de timer de lijst en verstuurt ze. De automatische lijst wordt gevraagd op het uur uit de instellingen; dat is een vast
uur van de robot (keuzelijst), zodat de lijst de robotrun van dat uur gebruikt en er geen extra run nodig is. Lukt het
nalezen niet binnen MAX_WAIT_MINUTES, dan toch, met de gegevens die er zijn (staat in het robotlog). Zonder robot in de cloud (codespace) meteen met wat er is.
Kamers: nummer en omschrijving zoals Lighthouse ze toont (bv. 11, Superior double room), onthouden over de reservaties
heen (RobotState room_catalog), zodat ook lege kamers hun omschrijving hebben.
Lijsten maken en versturen gebeurt in de Function App (timer van de meldingen, elke minuut). Buiten PRD gaan de berichten naar het testadres.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, date, datetime, timedelta

from hotel_checkin.core import clock
from hotel_checkin.core.hotels import load_hotel
from hotel_checkin.core.models import Reservation, ReservationStatus
from hotel_checkin.guests import repository as guests
from hotel_checkin.messaging import lists

KINDS = ("breakfast", "cleaning")
SECTION = {"breakfast": "ontbijtlijst", "cleaning": "kuislijst"}  # sectie in het hotelbestand, ook de schakelaar
TASK = SECTION  # taak in het robotlog
KEEP = 15  # zoveel lijsten per soort bewaren, oudere worden gewist
MAX_WAIT_MINUTES = 30  # hoogstens zo lang wachten op dat nalezen, daarna toch maken met wat er is
ROBOT_RETRY_MINUTES = 6  # de robot opnieuw starten als hij intussen niet nalas en niet meer draait
REQUEST_STATE = "daily_lists_requests"  # RobotState: gevraagde lijsten (schrijft alleen de Function App)
MADE_STATE = "daily_lists_made"  # RobotState: wanneer de robot de gevraagde lijst maakte (schrijft alleen de robot)
CATALOG_STATE = "room_catalog"  # RobotState: kamer -> omschrijving in Lighthouse
PLANBOARD_STATE = "planboard:{day}"  # RobotState: wie verblijft in welke kamer op die dag, zoals de robot het planbord las
CLEANING_LABELS = ("BABY BED", "DOUBLE OPMAKEN", "SPECIAAL VERZOEK", "LATE ARRIVAL")  # standaard voor [kuislijst] labels
SEPARATOR = "-"  # in [kamers] lijst_volgorde: lege rij (nieuwe verdieping)


def switch(hotel_id: str, kind: str) -> bool:
    """Hoofdschakelaar van deze lijst (soort breakfast of cleaning), of een andere bij naam (bv. reservaties)."""
    from hotel_checkin.processes.send_messages import switch as main_switch

    return main_switch(hotel_id, SECTION.get(kind, kind))


def _list(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return [str(x).strip() for x in (value or []) if str(x).strip()]


def settings(hotel_id: str, kind: str) -> dict:
    cfg = load_hotel(hotel_id).get(SECTION[kind], {})
    return {"time": str(cfg.get("uur") or "18:00"), "days": int(cfg.get("dag", 1) or 0),
            "email": _list(cfg.get("email")), "whatsapp": _list(cfg.get("whatsapp")),
            "words": _list(cfg.get("woorden")), "controle": str(cfg.get("controle") or ""),
            "extra_rows": _list(cfg.get("extra_rijen")),
            "labels": _list(cfg["labels"] if "labels" in cfg else (list(CLEANING_LABELS) if kind == "cleaning" else []))}


def _time(value: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d{1,2})[:.h](\d{2})\s*", value or "")
    return (int(m.group(1)), int(m.group(2))) if m else (18, 0)


def send_moment(hotel_id: str, kind: str, today: date) -> datetime:
    hour, minute = _time(settings(hotel_id, kind)["time"])
    return datetime(today.year, today.month, today.day, hour, minute, tzinfo=clock.tz(hotel_id))


def next_day(hotel_id: str, kind: str, now: datetime | None = None) -> date:
    """Dag van de volgende lijst die automatisch gemaakt wordt (voor de monitor): vandaag + dag zolang het uur
    nog niet voorbij is, anders morgen + dag."""
    now = now or datetime.now(clock.tz(hotel_id))
    today = now.astimezone(clock.tz(hotel_id)).date()
    base = today if now < send_moment(hotel_id, kind, today) else today + timedelta(days=1)
    return base + timedelta(days=settings(hotel_id, kind)["days"])


# ---------------------------------------------------------------- kamers


def room_order(hotel_id: str) -> list[str]:
    """Kamers op de lijst in volgorde, met SEPARATOR voor een lege rij ([kamers] lijst_volgorde)."""
    return _list(load_hotel(hotel_id).get("kamers", {}).get("lijst_volgorde"))


def room_name(hotel_id: str, room: str) -> str:
    """Naam op de lijst ([kamers.<nummer>] lijst, bv. App voor het appartement), anders het nummer."""
    rooms = load_hotel(hotel_id).get("kamers", {})
    sub = rooms.get(room) if isinstance(rooms.get(room), dict) else {}
    return str(sub.get("lijst") or room)


def room_catalog(hotel_id: str, reservations: list[Reservation]) -> dict[str, str]:
    """Omschrijving per kamer uit Lighthouse, aangevuld met wat in de reservaties staat en bewaard (ook lege kamers
    houden zo hun omschrijving, ook als de reservaties opgeruimd zijn)."""
    try:
        known = dict(json.loads(guests.get_state(hotel_id, CATALOG_STATE) or "{}"))
    except ValueError:
        known = {}
    merged = dict(known)
    for r in sorted(reservations, key=lambda x: x.arrival):  # de nieuwste omschrijving wint
        merged.update({k: v for k, v in r.room_names.items() if v})
    if merged != known:
        guests.set_state(hotel_id, CATALOG_STATE, json.dumps(merged))
    return merged


def describe_room(text: str) -> str:
    """'SUPERIOR DOUBLE ROOM' -> 'Superior double room' (alleen de eerste regel, niet het tarief)."""
    text = (text or "").strip().splitlines()[0].strip() if (text or "").strip() else ""
    return text.capitalize() if text.isupper() else text


def _layout(hotel_id: str, rooms_used: list[str]) -> list[str]:
    """Kamers in de volgorde van de instellingen; kamers die daar niet in staan, erachter (gesorteerd)."""
    order = room_order(hotel_id)
    known = {r for r in order if r != SEPARATOR}
    extra = sorted((r for r in rooms_used if r not in known), key=lambda x: (len(x), x))
    if not order:
        return extra
    return order + ([SEPARATOR, *extra] if extra else [])


def _rows(hotel_id: str, layout: list[str], per_room: dict[str, dict], empty: dict,
          catalog: dict[str, str] | None = None) -> list[dict]:
    out: list[dict] = []
    for room in layout:
        if room == SEPARATOR:
            if out and not out[-1].get("sep"):
                out.append({"sep": True})
            continue
        out.append({"room": room_name(hotel_id, room), "desc": describe_room((catalog or {}).get(room, "")),
                    **(per_room.get(room) or dict(empty))})
    if out and out[-1].get("sep"):
        out.pop()
    return out


# ---------------------------------------------------------------- opmerkingen


# Standaardzinnen van de boekingssites, geen wens van de gast: "U heeft geen kinderbedjes toegevoegd.", "Kinderen en
# extra bedden: Kinderen van alle leeftijden zijn toegestaan.", "No cots added", ...
_NOISE = re.compile(r"\b(geen|no|not|none|pas de|aucun|keine?n?|kein)\b|toegestaan|allowed|accepted|autoris|erlaubt|"
                    r"kinderen en extra bedden|children and extra beds|enfants et lits", re.IGNORECASE)


def notes(texts: list[str | None], words: list[str]) -> list[str]:
    """Zinnen of lijnen met een van de woorden (begin van een woord, hoofdletters maken niet uit)."""
    from hotel_checkin.pms.lighthouse_parse import DOOR_CODE_PREFIX

    pats = [re.compile(r"(?<!\w)" + re.escape(w), re.IGNORECASE) for w in words if w]
    out: list[str] = []
    for text in texts:
        for part in re.split(r"\n|\s\|\s|(?<=[.!?])\s+", text or ""):
            p = " ".join(part.split()).strip(" -;,|")
            if not p or p.startswith(DOOR_CODE_PREFIX) or not any(x.search(p) for x in pats) or _NOISE.search(p):
                continue
            p = p if len(p) <= 120 else p[:117] + "..."
            if p.lower() not in (o.lower() for o in out):
                out.append(p)
    return out


def _texts(r: Reservation) -> list[str | None]:
    return [r.remarks, *(x.get("label") for x in r.folio)]


def _active(r: Reservation) -> bool:
    return r.status != ReservationStatus.CANCELLED


# ---------------------------------------------------------------- lijsten opmaken


def _persons(stay: dict, r: Reservation | None, stays_of_r: list[dict]) -> int | None:
    """Personen in deze kamer: het getal op het planbord, anders dat van de reservatie als ze maar één kamer heeft."""
    if stay.get("persons"):
        return stay["persons"]
    return r.guest_count if r and len(stays_of_r) == 1 else None


def _add(per_room: dict, room: str, count: int | None, remark: list[str], check: bool) -> None:
    cur = per_room.get(room)
    if cur:  # twee reservaties in dezelfde kamer (bv. wissel op die dag)
        cur["count"] = (cur["count"] or 0) + (count or 0) if (cur["count"] is not None or count is not None) else None
        cur["remark"] = "; ".join(x for x in (cur["remark"], *remark) if x)
        cur["check"] = cur["check"] or check
    else:
        per_room[room] = {"count": count, "remark": "; ".join(remark), "check": check}


def _labeled(per_room: dict, room: str, persons: int | None) -> None:
    """Kamer met het label ONTBIJT: ontbijt voor wie in de kamer is."""
    _add(per_room, room, persons, [] if persons else ["aantal personen niet gekend"], not persons)


def _by_reservation(stays: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for st in sorted(stays, key=lambda x: (len(x.get("room") or "999"), x.get("room") or "")):
        out.setdefault(st["reservation"], []).append(st)
    return out


def build_breakfast(hotel_id: str, day: date, reservations: list[Reservation], words: list[str],
                    stays: list[dict] | None = None) -> dict:
    """stays = het planbord (robot): wie in welke kamer sliep, per kamer met eigen data, personen en labels. Zonder
    planbord: de kamers en data van de reservaties."""
    from dataclasses import replace

    from hotel_checkin.pms.lighthouse_parse import BREAKFAST_LABEL, rate_plans_from
    from hotel_checkin.processes.breakfast_labels import breakfast

    per_room: dict[str, dict] = {}
    undated = dated_lines = 0  # ontbijtregels zonder / met de dagen uit Lighthouse (om te zien of de robot ze las)
    label = breakfast_label(hotel_id)
    plan = None if stays is None else _by_reservation(
        [x for x in stays if x["arrival"] < day.isoformat() <= x["departure"]])
    known = {r.reservation_id.lower() for r in reservations}
    room_persons: dict[str, int | None] = {}
    for rid, st in (plan or {}).items():
        if rid in known:
            continue
        # Op het planbord, maar de robot kent de reservatie (nog) niet: met het label is het zeker, anders nakijken
        for x in st:
            room = x.get("room") or "?"
            if label in x["labels"]:
                _labeled(per_room, room, x.get("persons"))
            else:
                _add(per_room, room, None, ["reservatie nog niet gelezen door de robot: nakijken of er ontbijt is"], True)
    for r in reservations:
        if not _active(r):
            continue
        judged = None
        if plan is not None:
            st = plan.get(r.reservation_id.lower())
            if not st:
                continue  # die nacht niet in het hotel volgens het planbord
            for x in st:  # label ONTBIJT op deze kamer: ontbijt elke dag voor wie in de kamer is
                if label in x["labels"]:
                    _labeled(per_room, x.get("room") or "?", _persons(x, r, st))
            rest = [x for x in st if label not in x["labels"]]
            if not rest:
                continue
            judged = breakfast(r)  # tarief en folio gelden voor de hele reservatie
            room_persons = {x.get("room") or "?": _persons(x, r, st) for x in rest}
            known_persons = [p for p in room_persons.values() if p]
            r = replace(r, rooms=list(room_persons), pms_labels=[], breakfast_labeled_at=None,
                        guest_count=sum(known_persons) if len(known_persons) == len(rest) else
                        (r.guest_count if len(rest) == len(st) else None))
        elif not (r.arrival < day <= r.departure):
            continue
        else:
            room_persons = {}
        yes, why = judged or breakfast(r)
        # Label ONTBIJT op het planbord (Lighthouse): ontbijt elke dag, voor iedereen (tarief of bijgeboekt)
        if label in r.pms_labels:
            yes, why = True, f"label {label}"
        rate_incl = yes and why.startswith(("tarief", "label"))
        # Ontbijt als extra met de dagen uit Lighthouse (venster "Bewerken" in de folio): precies per dag en kamer
        lines = [x for x in r.folio if BREAKFAST_LABEL.search(x["label"]) and not rate_plans_from(x["label"])]
        dated = {}
        if not rate_incl and lines:
            undated += sum(1 for x in lines if not x.get("days"))
            dated_lines += sum(1 for x in lines if x.get("days"))
        if not rate_incl and lines and all(x.get("days") for x in lines):
            for x in lines:
                n = int(x["days"].get(day.isoformat()) or 0)
                room = x.get("room") or (r.rooms[0] if r.rooms else "?")
                if n and (plan is None or room in r.rooms):
                    dated[room] = dated.get(room, 0) + n
            if not dated:
                continue  # ontbijt geboekt, maar niet voor deze dag
        yes = yes or bool(r.breakfast_labeled_at)
        partial = not dated and not yes and why.startswith("maar ")
        unread = not dated and not yes and not r.folio
        if not (dated or yes or partial or unread):
            continue
        persons = r.guest_count
        if dated:
            rooms = list(dated)
            split = [dated[x] for x in rooms]
        elif room_persons and all(room_persons.values()):
            rooms = list(room_persons)
            split = [room_persons[x] for x in rooms]
        else:
            rooms = r.rooms or ["?"]
            split = ([persons // len(rooms) + (1 if i < persons % len(rooms) else 0) for i in range(len(rooms))]
                     if persons else [None] * len(rooms))
        found = notes(_texts(r), words)
        for i, room in enumerate(rooms):
            remark: list[str] = []
            check = False
            if partial:
                errors = sorted({x["days_error"] for x in lines if x.get("days_error")})
                remark.append(f"ontbijt bijgeboekt, {why[5:]}, maar de dagen werden "
                              + (f"niet gelezen ({'; '.join(errors)})" if errors else "nog niet gelezen in Lighthouse")
                              + f": nakijken ({r.booking_number or ''})")
                check = True
            elif unread:
                remark.append(f"folio nog niet gelezen: nakijken of er ontbijt is ({r.booking_number or ''})")
                check = True
            elif persons is None and not dated:
                remark.append("aantal personen niet gekend")
                check = True
            if room == "?":
                remark.append(f"nog geen kamer toegewezen ({r.booking_number or ''})")
                check = True
            if len(rooms) > 1 and i == 0 and not dated and not (room_persons and all(room_persons.values())):
                remark.append(f"samen met {', '.join(room_name(hotel_id, x) for x in rooms[1:])}"
                              + (f" ({persons} pers.)" if persons else ""))
            if i == 0:
                remark += found
            _add(per_room, room, None if (partial or unread) else split[i], remark, check)
    rows = _rows(hotel_id, _layout(hotel_id, list(per_room)), per_room, {"count": None, "remark": "", "check": False},
                 room_catalog(hotel_id, reservations))
    total = sum(r.get("count") or 0 for r in rows if not r.get("sep"))
    return {"kind": "breakfast", "day": day.isoformat(), "rows": rows, "total": total,
            "breakfast_lines": {"with_days": dated_lines, "without_days": undated},
            "check": sum(1 for r in rows if r.get("check"))}


def _cleaning_plan(day: date, reservations: list[Reservation], words: list[str], labels: list[str],
                   stays: list[dict], per_room: dict) -> None:
    """Schoonmaaklijst uit het planbord: elke kamer met haar eigen aankomst en vertrek."""
    d = day.isoformat()
    by_id = {r.reservation_id.lower(): r for r in reservations}
    wanted = {x.upper() for x in labels}
    for rid, st in _by_reservation([x for x in stays if x["arrival"] <= d <= x["departure"]]).items():
        r = by_id.get(rid)
        if r is not None and not _active(r):
            continue
        found_done = False
        for x in st:
            room = x.get("room") or "?"
            leave, checkin = x["departure"] == d, x["arrival"] == d
            stay = x["arrival"] < d < x["departure"]
            cur = per_room.setdefault(room, {"leave": False, "stay": False, "checkin": False, "remark": "",
                                             "check": False})
            cur["leave"] = cur["leave"] or leave
            cur["stay"] = cur["stay"] or stay
            cur["checkin"] = cur["checkin"] or checkin
            if not (stay or checkin):
                continue  # wensen van wie vertrekt, gelden niet meer
            remark = []
            persons = _persons(x, r, st)
            if checkin and persons:
                remark.append(f"{persons} pers.")
            remark += [lab.capitalize() for lab in x["labels"] if lab.upper() in wanted]
            if room == "?":
                remark.append("nog geen kamer toegewezen" + (f" ({r.booking_number})" if r and r.booking_number else ""))
                cur["check"] = True
            if r is not None and not found_done:  # opmerkingen van de reservatie: bij de eerste kamer
                remark += notes(_texts(r), words)
                found_done = True
            cur["remark"] = "; ".join(x for x in (cur["remark"], *remark) if x)


def build_cleaning(hotel_id: str, day: date, reservations: list[Reservation], words: list[str],
                   stays: list[dict] | None = None, labels: list[str] | None = None) -> dict:
    """stays = het planbord (robot), zie build_breakfast. labels = labels op het planbord die als opmerking komen."""
    per_room: dict[str, dict] = {}
    if stays is not None:
        _cleaning_plan(day, reservations, words, labels or [], stays, per_room)
    for r in reservations if stays is None else []:
        if not _active(r) or not (r.arrival <= day <= r.departure):
            continue
        leave, checkin = r.departure == day, r.arrival == day
        stay = r.arrival < day < r.departure
        found = notes(_texts(r), words) if (stay or checkin) else []
        for room in r.rooms or ["?"]:
            cur = per_room.setdefault(room, {"leave": False, "stay": False, "checkin": False, "remark": "",
                                             "check": False})
            cur["leave"] = cur["leave"] or leave
            cur["stay"] = cur["stay"] or stay
            cur["checkin"] = cur["checkin"] or checkin
            remark = []
            if checkin and r.guest_count:
                remark.append(f"{r.guest_count} pers.")
            if room == "?":
                remark.append(f"nog geen kamer toegewezen ({r.booking_number or ''})")
                cur["check"] = True
            remark += found
            cur["remark"] = "; ".join(x for x in (cur["remark"], *remark) if x)
    rows = _rows(hotel_id, _layout(hotel_id, list(per_room)), per_room,
                 {"leave": False, "stay": False, "checkin": False, "remark": "", "check": False},
                 room_catalog(hotel_id, reservations))
    real = [r for r in rows if not r.get("sep")]
    totals = {k: sum(1 for r in real if r.get(k)) for k in ("leave", "stay", "checkin")}
    return {"kind": "cleaning", "day": day.isoformat(), "rows": rows, "totals": totals}


def build(hotel_id: str, kind: str, day: date) -> dict:
    cfg = settings(hotel_id, kind)
    reservations = guests.list_reservations(hotel_id)
    plan = planboard(hotel_id, day)
    stays = plan["stays"] if plan else None
    if kind == "breakfast":
        data = build_breakfast(hotel_id, day, reservations, cfg["words"], stays)
    else:
        data = build_cleaning(hotel_id, day, reservations, cfg["words"], stays, cfg.get("labels") or [])
        data["controle"], data["extra_rows"] = cfg["controle"], cfg["extra_rows"]
    data["source"] = f"planbord van {plan['read_at'][11:16]}" if plan else "reservaties (planbord niet gelezen)"
    return data


def planboard(hotel_id: str, day: date) -> dict | None:
    """Wat de robot op het planbord las voor die dag: {"read_at", "stays"}, of None."""
    try:
        data = json.loads(guests.get_state(hotel_id, PLANBOARD_STATE.format(day=day.isoformat())) or "null")
    except ValueError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get("stays"), list) else None


def save_planboard(hotel_id: str, day: date, parsed: dict, read_at: datetime) -> int:
    """Het planbord voor die dag bewaren (alleen wie er die dag of de nacht ervoor is) en de kamers onthouden."""
    d, before = day.isoformat(), (day - timedelta(days=1)).isoformat()
    keep = [{k: x[k] for k in ("reservation", "room", "arrival", "departure", "persons", "labels")}
            for x in parsed["stays"] if x["arrival"] <= d and x["departure"] >= before]
    guests.set_state(hotel_id, PLANBOARD_STATE.format(day=d),
                     json.dumps({"read_at": read_at.isoformat(timespec="minutes"), "stays": keep}))
    try:
        known = dict(json.loads(guests.get_state(hotel_id, CATALOG_STATE) or "{}"))
    except ValueError:
        known = {}
    merged = known | {u["room"]: u["name"] for u in parsed["units"].values() if u.get("room") and u.get("name")}
    if merged != known:
        guests.set_state(hotel_id, CATALOG_STATE, json.dumps(merged))
    return len(keep)


def describe(data: dict) -> str:
    """Inhoud in een paar woorden (robotlog, monitor)."""
    source = f", volgens {data['source']}" if data.get("source") else ""
    if data["kind"] == "breakfast":
        rooms = sum(1 for r in data["rows"] if not r.get("sep") and (r.get("count") or r.get("check")))
        missing = (data.get("breakfast_lines") or {}).get("without_days", 0)
        return (f"{data.get('total', 0)} personen in {rooms} kamers"
                + (f", {data['check']} na te kijken" if data.get("check") else "")
                + (f", van {missing} ontbijtregel(s) de dagen niet gelezen" if missing else "") + source)
    t = data.get("totals", {})
    return f"{t.get('leave', 0)} vertrek, {t.get('stay', 0)} blijvers, {t.get('checkin', 0)} check in" + source


# ---------------------------------------------------------------- versturen


def _send_phone(hotel_id: str, data: dict, to: str, hotel_name: str) -> dict:
    """WhatsApp met het goedgekeurde sjabloon ([whatsapp] template_breakfast_list_nl / template_cleaning_list_nl:
    {{1}} titel, {{2}} de lijst op één regel), anders of als dat mislukt per sms met de hele lijst."""
    from hotel_checkin.checkin.service import normalize_phone
    from hotel_checkin.messaging import sms, whatsapp
    from hotel_checkin.processes import send_messages

    if not send_messages.phone_enabled(hotel_id):
        return {"channel": "whatsapp", "to": to, "ok": False, "skipped": True,
                "error": "niet verstuurd: WhatsApp en sms staan uit (instellingen, Berichten)"}
    number = normalize_phone(to)
    if not number:
        return {"channel": "whatsapp", "to": to, "ok": False, "error": "ongeldig gsm-nummer"}
    template = send_messages.whatsapp_template(hotel_id, f"{data['kind']}_list", "nl")
    if template:
        title = lists.subject(data, hotel_name)
        res = whatsapp.send_whatsapp_template(hotel_id, number, template,
                                              {"1": title, "2": lists.summary(data)[:900]})
        if res.ok:
            return {"channel": "whatsapp", "to": to, "ok": True}
        logging.warning("%s: %s per WhatsApp naar %s mislukt (%s), nu per sms", hotel_id, data["kind"], to, res.error)
    res = sms.send_sms(hotel_id, number, lists.text(data, hotel_name))
    return {"channel": "sms", "to": to, "ok": res.ok, "error": res.error or ""}


def send(hotel_id: str, data: dict) -> list[dict]:
    """Naar alle ontvangers uit de instellingen. Geeft per ontvanger het resultaat."""
    from hotel_checkin.messaging import email

    cfg = settings(hotel_id, data["kind"])
    hotel = load_hotel(hotel_id)
    name = hotel["hotel"]["naam"]
    sender = hotel.get("verzending", {}).get("mail_afzender")
    now = datetime.now(UTC).isoformat()
    out: list[dict] = []
    if cfg["email"]:
        body = lists.mail_html(data, name, [describe(data)[:1].upper() + describe(data)[1:] + "."])
        attachment = (lists.file_name(data, name), lists.xlsx(data, name))
        for to in cfg["email"]:
            res = email.send_email(to=to, subject=lists.subject(data, name), html_body=body, attachments=[attachment],
                                   sender=sender, hotel_id=hotel_id)
            out.append({"channel": "email", "to": to, "ok": res.ok, "error": res.error or "", "at": now})
    for to in cfg["whatsapp"]:
        try:
            out.append(_send_phone(hotel_id, data, to, name) | {"at": now})
        except Exception as exc:  # noqa: BLE001 - de andere ontvangers gaan gewoon door
            out.append({"channel": "whatsapp", "to": to, "ok": False, "error": f"{type(exc).__name__}: {exc}", "at": now})
    return out


def _sent_text(sent: list[dict]) -> str:
    if not sent:
        return "niet verstuurd: geen ontvangers in de instellingen"
    names = {"email": "mail", "whatsapp": "WhatsApp", "sms": "sms"}
    return ", ".join(f"{names.get(s['channel'], s['channel'])} naar {s['to']} "
                     + ("gelukt" if s["ok"] else f"({s.get('error') or 'mislukt'})"[:160]) for s in sent)


def prune(hotel_id: str, kind: str, keep: int = KEEP) -> int:
    old = guests.daily_lists(hotel_id, kind)[keep:]
    for d in old:
        guests.delete_daily_list(hotel_id, kind, d["day"])
    return len(old)


def generate(hotel_id: str, kind: str, day: date, by: str = "", send_now: bool = False, auto: bool = False,
             fresh: str = "") -> dict:
    """Lijst (opnieuw) maken voor die dag, bewaren en eventueel versturen. Eigen regel in het robotlog."""
    if kind not in KINDS:
        raise ValueError(kind)
    started = datetime.now(UTC)
    data = build(hotel_id, kind, day)
    old = guests.get_daily_list(hotel_id, kind, day.isoformat()) or {}
    data |= {"generated_at": datetime.now(clock.tz(hotel_id)).isoformat(timespec="minutes"),
             "generated_by": by or "automatisch", "auto": auto or bool(old.get("auto")),
             "sent": old.get("sent", []), "sent_at": old.get("sent_at", "")}
    sent: list[dict] = []
    if send_now:
        sent = send(hotel_id, data)
        data["sent"], data["sent_at"] = sent, data["generated_at"]
    guests.save_daily_list(hotel_id, kind, day.isoformat(), data)
    prune(hotel_id, kind)
    note = (f"lijst voor {lists.day_text(day.isoformat())} {'automatisch gemaakt' if auto else 'gemaakt door ' + (by or '?')}: "
            f"{describe(data)}" + (f" ({fresh})" if fresh else "")
            + (f". {_sent_text(sent)}" if send_now else ", niet verstuurd"))
    ok = all(s["ok"] or s.get("skipped") for s in sent)
    guests.log_robot_run(hotel_id, TASK[kind], started, ok, 1, 1 if send_now and sent and ok else 0, note,
                         skipped=sum(1 for s in sent if not s["ok"]))
    return data


def _robot_busy(hotel_id: str) -> bool:
    """Draait de robot nu echt (of is hij net gestart)? Alleen dan staan de knoppen in de monitor even uit."""
    from hotel_checkin.admin import cloud_robot

    if not cloud_robot.available():
        return False
    try:
        return cloud_robot.running()
    except Exception:  # noqa: BLE001 - niet te weten: de knoppen niet blokkeren
        return False


def view(hotel_id: str, kind: str) -> dict:
    """Voor de monitor: de bewaarde lijsten (nieuwste eerst, met de tabel), en wanneer de volgende komt."""
    cfg = settings(hotel_id, kind)
    records = [d | {"html": lists.table_html(d), "summary": describe(d)} for d in guests.daily_lists(hotel_id, kind)]
    pending = sorted(({"day": k.split(":", 1)[1], "at": r.get("at", ""), "send": bool(r.get("send")),
                       "made": bool(_made_at(hotel_id, k, r))}
                      for k, r in requests(hotel_id).items() if k.startswith(kind + ":")), key=lambda x: x["day"])
    return {"kind": kind, "switch": switch(hotel_id, kind), "next_day": next_day(hotel_id, kind).isoformat(),
            "pending": pending, "robot_busy": bool(pending) and _robot_busy(hotel_id),
            "time": cfg["time"], "days": cfg["days"], "email": cfg["email"], "whatsapp": cfg["whatsapp"],
            "keep": KEEP, "records": records}


# ---------------------------------------------------------------- aanvragen: de robot maakt de lijst
# De robot maakt de lijst, met wat hij net in Lighthouse las (folio, opmerking, kamer). Wie een lijst vraagt (knop in
# de monitor of het uur van de automatische lijst), maakt een aanvraag en start de robot. De robot leest de
# reservaties van die dag (Reservaties bijwerken), maakt de lijst (eigen taak in zijn run) en noteert dat (MADE_STATE);
# de lijst staat dan meteen in de monitor. Versturen (mail, WhatsApp) doet de timer van de Function App daarna: de robot
# heeft geen rechten op de mailbox. "Lijst maken" verstuurt nooit, alleen "Maken en versturen" en de automatische lijst.
# Twee toestanden met elk één schrijver, zodat ze elkaar niet overschrijven: REQUEST_STATE (Function App) en
# MADE_STATE (robot).


def _state(hotel_id: str, key: str) -> dict:
    try:
        value = json.loads(guests.get_state(hotel_id, key) or "{}")
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def _save(hotel_id: str, key: str, value: dict, today: date) -> None:
    """Bewaren, zonder de lijsten van meer dan 3 dagen geleden."""
    oldest = (today - timedelta(days=3)).isoformat()
    guests.set_state(hotel_id, key, json.dumps({k: v for k, v in value.items() if k.split(":", 1)[1] >= oldest}))


def _now(now: datetime | None, hotel_id: str) -> datetime:
    return (now or datetime.now(UTC)).astimezone(clock.tz(hotel_id))


def requests(hotel_id: str) -> dict:
    """Openstaande aanvragen: {"soort:dag": {"send", "auto", "by", "at", "robot_at"}}."""
    return _state(hotel_id, REQUEST_STATE)


def _made_at(hotel_id: str, key: str, req: dict) -> datetime | None:
    """Wanneer de robot de lijst voor deze aanvraag maakte (na de aanvraag), of None."""
    value = _state(hotel_id, MADE_STATE).get(key)
    if value and value >= req["at"]:
        return datetime.fromisoformat(value)
    return None


def _start_robot(hotel_id: str, req: dict, now: datetime) -> str:
    """De robot starten om de lijst te maken, als hij niet al draait en niet net gestart werd."""
    from hotel_checkin.admin import cloud_robot

    last = req.get("robot_at")
    if last and now - datetime.fromisoformat(last) < timedelta(minutes=ROBOT_RETRY_MINUTES):
        return ""
    if cloud_robot.running():
        return "robot is al bezig"
    req["robot_at"] = now.isoformat()
    if cloud_robot.start():
        return "robot gestart"
    what = f"robot niet gestart: {cloud_robot.LAST_ERROR}"
    guests.log_robot_run(hotel_id, "robot", datetime.now(UTC), False, 0, 0,
                         f"voor de gevraagde ontbijt- of schoonmaaklijst: {what}. Opnieuw over {ROBOT_RETRY_MINUTES} minuten; "
                         f"na {MAX_WAIT_MINUTES} minuten wordt de lijst gemaakt met de gegevens die er zijn")
    return what


def request(hotel_id: str, kind: str, day: date, by: str = "", send_now: bool = False, auto: bool = False,
            now: datetime | None = None) -> dict:
    """Een lijst vragen: de robot leest de reservaties van die dag en maakt de lijst; versturen alleen als gevraagd.
    Een nieuwe vraag voor dezelfde lijst vervangt de vorige (ook of ze verstuurd moet worden).
    Zonder robot in de cloud (codespace, tests) of als hij niet leest: meteen maken met wat er is."""
    from hotel_checkin.admin import cloud_robot

    if kind not in KINDS:
        raise ValueError(kind)
    now = _now(now, hotel_id)
    if not cloud_robot.available() or not switch(hotel_id, "reservaties"):  # geen robot, of hij leest niet
        data = generate(hotel_id, kind, day, by=by, send_now=send_now, auto=auto)
        return {"requested": False, "day": data["day"], "sent": data["sent"] if send_now else []}
    reqs = requests(hotel_id)
    key = f"{kind}:{day.isoformat()}"
    old = reqs.get(key, {})
    req = {"send": send_now or (auto and bool(old.get("send"))), "auto": auto, "by": by or "automatisch",
           "at": now.isoformat(), "robot_at": None}  # een nieuwe vraag probeert de robot meteen te starten
    what = _start_robot(hotel_id, req, now)
    reqs[key] = req
    _save(hotel_id, REQUEST_STATE, reqs, now.date())
    return {"requested": True, "day": day.isoformat(), "robot": what}


def pending_reads(hotel_id: str) -> list[str]:
    """Voor de robot: gevraagde lijsten die hij nog moet maken ("soort:dag")."""
    return [k for k, r in requests(hotel_id).items() if not _made_at(hotel_id, k, r)]


def refresh_due(hotel_id: str) -> list[Reservation]:
    """Voor de robot: reservaties om nu te lezen voor de gevraagde lijsten (wie op die dag in het hotel is,
    aankomt of vertrekt)."""
    days = {date.fromisoformat(k.split(":", 1)[1]) for k in pending_reads(hotel_id)}
    if not days:
        return []
    return sorted((r for r in guests.list_reservations(hotel_id)
                   if _active(r) and any(r.arrival <= d <= r.departure for d in days)), key=lambda r: r.arrival)


def robot_read_labels(hotel_id: str, keys: list[str], lh) -> str:
    """Voor de robot: de labels op het planbord van de nacht voor elke gevraagde dag, bij de reservaties bewaren.
    Geeft een korte notitie voor het robotlog."""
    from hotel_checkin.pms import lighthouse

    days = sorted({date.fromisoformat(k.split(":", 1)[1]) for k in keys})
    found: dict[str, list[str]] = {}
    stays = 0
    for d in days:
        parsed = lighthouse.planboard_stays(hotel_id, d - timedelta(days=1), d, lh)
        stays += save_planboard(hotel_id, d, parsed, datetime.now(clock.tz(hotel_id)))
        for x in parsed["stays"]:
            found[x["reservation"]] = sorted(set(found.get(x["reservation"], [])) | set(x["labels"]))
    changed = 0
    for r in guests.list_reservations(hotel_id):
        rid = r.reservation_id.lower()
        if rid in found and r.pms_labels != found[rid]:
            r.pms_labels = found[rid]
            guests.save_reservation(r, fields=guests.PMS_LABEL_FIELDS)
            changed += 1
    name = breakfast_label(hotel_id)
    with_label = sum(1 for labels in found.values() if name in labels)
    return f"planbord gelezen ({stays} kamers bezet): {with_label} reservaties met label {name}"


def breakfast_label(hotel_id: str) -> str:
    from hotel_checkin.processes.breakfast_labels import label_name

    return label_name(hotel_id)


def robot_make(hotel_id: str, keys: list[str], now: datetime | None = None) -> list[str]:
    """Voor de robot, na het nalezen: de gevraagde lijsten maken (eigen taak in zijn run, zonder versturen) en
    noteren dat ze klaar zijn. Geeft terug welke gemaakt werden."""
    now = _now(now, hotel_id)
    reqs = requests(hotel_id)
    made = _state(hotel_id, MADE_STATE)
    done = []
    for key in keys:
        req = reqs.get(key)
        if not req:
            continue
        kind, day_iso = key.split(":", 1)
        try:
            generate(hotel_id, kind, date.fromisoformat(day_iso), by=req.get("by", ""), auto=bool(req.get("auto")),
                     fresh=f"reservaties van die dag nagelezen om {now:%H:%M}"
                           + (", wordt nu verstuurd" if req.get("send") else ""))
        except Exception as exc:
            logging.exception("%s: %s niet gemaakt", hotel_id, key)
            guests.log_robot_run(hotel_id, TASK[kind], datetime.now(UTC), False, 1, 0,
                                 f"lijst voor {day_iso} niet gemaakt: {type(exc).__name__}: {exc}")
            continue
        made[key] = now.isoformat()
        done.append(key)
    if done:
        _save(hotel_id, MADE_STATE, made, now.date())
    return done


def send_stored(hotel_id: str, kind: str, day: date, auto: bool = False) -> list[dict]:
    """De bewaarde lijst versturen (Function App). Eigen regel in het robotlog."""
    started = datetime.now(UTC)
    data = guests.get_daily_list(hotel_id, kind, day.isoformat())
    if not data:
        raise RuntimeError("lijst niet gevonden")
    sent = send(hotel_id, data)
    data["sent"], data["sent_at"] = sent, datetime.now(clock.tz(hotel_id)).isoformat(timespec="minutes")
    data["auto"] = data.get("auto") or auto
    guests.save_daily_list(hotel_id, kind, day.isoformat(), data)
    ok = all(s["ok"] or s.get("skipped") for s in sent)
    guests.log_robot_run(hotel_id, TASK[kind], started, ok, 1, 1 if sent and ok else 0,
                         f"lijst voor {lists.day_text(day.isoformat())} verstuurd: {_sent_text(sent)}",
                         skipped=sum(1 for s in sent if not s["ok"]))
    return sent


def run(hotel_id: str, now: datetime | None = None) -> list[str]:
    """Timer van de Function App (elke minuut).
    - Automatische lijst: op het uur een aanvraag (de robot maakt de lijst in de run van dat vaste uur).
    - Lijst gemaakt door de robot: versturen als dat gevraagd was (een automatische pas vanaf het uur).
    - Na MAX_WAIT_MINUTES zonder robot: toch maken (en versturen) met de bewaarde gegevens (staat in het robotlog).
    - Draait de robot niet terwijl er nog een lijst te maken is: opnieuw starten.
    Geeft terug wat er gebeurde."""

    now = _now(now, hotel_id)
    done: list[str] = []
    reqs = requests(hotel_id)
    lead = timedelta(0)  # op het uur zelf: dat is een vast uur van de robot, de lijst gebruikt die run
    for kind in KINDS:
        if not switch(hotel_id, kind):
            continue
        at = send_moment(hotel_id, kind, now.date())
        day = now.date() + timedelta(days=settings(hotel_id, kind)["days"])
        key = f"{kind}:{day.isoformat()}"
        if now >= at - lead and key not in reqs \
                and not (guests.get_daily_list(hotel_id, kind, day.isoformat()) or {}).get("auto"):
            result = request(hotel_id, kind, day, send_now=True, auto=True, now=now)
            reqs = requests(hotel_id)
            if not result["requested"]:
                done.append(f"{kind} {day.isoformat()}")
            else:
                done.append(f"{key}: aangevraagd, {result['robot'] or 'robot start straks'}")
    changed = False
    for key, req in list(reqs.items()):
        kind, day_iso = key.split(":", 1)
        day = date.fromisoformat(day_iso)
        made = _made_at(hotel_id, key, req)
        if made is None and now - datetime.fromisoformat(req["at"]) < timedelta(minutes=MAX_WAIT_MINUTES):
            what = _start_robot(hotel_id, req, now)
            if what:
                changed = True
                done.append(f"{key}: {what}")
            continue
        if req.get("send") and req.get("auto") and \
                now < send_moment(hotel_id, kind, day - timedelta(days=settings(hotel_id, kind)["days"])):
            continue  # gemaakt, maar automatisch pas op het uur versturen
        try:
            if made is None:  # geen robot: met de bewaarde gegevens
                generate(hotel_id, kind, day, by=req.get("by", ""), send_now=bool(req.get("send")),
                         auto=bool(req.get("auto")),
                         fresh=f"de robot maakte de lijst niet binnen {MAX_WAIT_MINUTES} minuten: gemaakt met de "
                               "gegevens die er waren")
            elif req.get("send"):
                send_stored(hotel_id, kind, day, auto=bool(req.get("auto")))
            done.append(f"{kind} {day_iso}")
        except Exception as exc:
            logging.exception("%s: %s niet gemaakt of verstuurd", hotel_id, key)
            guests.log_robot_run(hotel_id, TASK[kind], datetime.now(UTC), False, 1, 0,
                                 f"lijst voor {day:%d/%m} niet gemaakt of verstuurd: {type(exc).__name__}: {exc}")
        reqs.pop(key)
        changed = True
    if changed:
        _save(hotel_id, REQUEST_STATE, reqs, now.date())
    return done
