"""Proces: elke dag de ontbijtlijst en de kuislijst maken en versturen.

Hoofdschakelaars [schakelaars] ontbijtlijst en kuislijst (per omgeving, standaard uit). Aan = de lijst wordt elke
dag om [ontbijtlijst] uur / [kuislijst] uur gemaakt voor de dag [..] dag later (1 = morgen) en verstuurd per mail
(met de Excel als bijlage) en per WhatsApp (met sms als terugval). In de monitor (tabbladen Ontbijt en Kuis) kan
een lijst altijd opnieuw gemaakt en verstuurd worden, ook met de schakelaar uit. Alleen de laatste KEEP lijsten
per soort blijven bewaard. Er staan geen gastnamen op, alleen kamers, aantallen en opmerkingen.

Ontbijtlijst voor dag D (ontbijt 's ochtends): wie de nacht ervoor sliep (aankomst voor D, vertrek op of na D) en
ontbijt heeft. Zelfde regel als het label ONTBIJT (processes/breakfast_labels.py): tarief met ontbijt, of ontbijt in
de folio voor alle personen en nachten, of het label werd door de robot gezet. Ontbijt in de folio voor maar een
deel van het verblijf (bv. één dag bijgeboekt): de kamer komt in het geel op de lijst, "nakijken": de folio zegt
niet voor welke dag. Meer kamers in één reservatie: de personen verdeeld over de kamers, met "samen met ...".

Kuislijst voor dag D, per kamer: Leave (vertrek op D), Stay (aankomst voor D, vertrek na D), Check in (aankomst op D).
Opmerkingen: zinnen uit de opmerking van de reservatie of lijnen van de folio met een van de woorden uit de
instellingen ([kuislijst] woorden, bv. babybed, romantisch), en het aantal personen bij een check in.

Vers: in de 3 uur voor een lijst automatisch verstuurd wordt, leest de robot de reservaties van die dag nog eens in
Lighthouse (Reservaties bijwerken, processes/refresh_contacts.py): kamer, data, folio en opmerking.
Draait in de Function App (timer), los van de robot. Buiten PRD gaan de berichten naar het testadres.
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
REFRESH_HOURS = 3  # zoveel uur voor het versturen leest de robot de reservaties van die dag opnieuw
REFRESH_STATE = "daily_lists_refreshed"  # RobotState: voor welke lijsten de robot al nalas
SEPARATOR = "-"  # in [kamers] lijst_volgorde: lege rij (nieuwe verdieping)


def switch(hotel_id: str, kind: str) -> bool:
    from hotel_checkin.processes.send_messages import switch as main_switch

    return main_switch(hotel_id, SECTION[kind])


def _list(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    return [str(x).strip() for x in (value or []) if str(x).strip()]


def settings(hotel_id: str, kind: str) -> dict:
    cfg = load_hotel(hotel_id).get(SECTION[kind], {})
    return {"time": str(cfg.get("uur") or "18:00"), "days": int(cfg.get("dag", 1) or 0),
            "email": _list(cfg.get("email")), "whatsapp": _list(cfg.get("whatsapp")),
            "words": _list(cfg.get("woorden")), "controle": str(cfg.get("controle") or ""),
            "extra_rows": _list(cfg.get("extra_rijen"))}


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


def _layout(hotel_id: str, rooms_used: list[str]) -> list[str]:
    """Kamers in de volgorde van de instellingen; kamers die daar niet in staan, erachter (gesorteerd)."""
    order = room_order(hotel_id)
    known = {r for r in order if r != SEPARATOR}
    extra = sorted((r for r in rooms_used if r not in known), key=lambda x: (len(x), x))
    if not order:
        return extra
    return order + ([SEPARATOR, *extra] if extra else [])


def _rows(hotel_id: str, layout: list[str], per_room: dict[str, dict], empty: dict) -> list[dict]:
    out: list[dict] = []
    for room in layout:
        if room == SEPARATOR:
            if out and not out[-1].get("sep"):
                out.append({"sep": True})
            continue
        out.append({"room": room_name(hotel_id, room), **(per_room.get(room) or dict(empty))})
    if out and out[-1].get("sep"):
        out.pop()
    return out


# ---------------------------------------------------------------- opmerkingen


def notes(texts: list[str | None], words: list[str]) -> list[str]:
    """Zinnen of lijnen met een van de woorden (begin van een woord, hoofdletters maken niet uit)."""
    from hotel_checkin.pms.lighthouse_parse import DOOR_CODE_PREFIX

    pats = [re.compile(r"(?<!\w)" + re.escape(w), re.IGNORECASE) for w in words if w]
    out: list[str] = []
    for text in texts:
        for part in re.split(r"\n|\s\|\s|(?<=[.!?])\s+", text or ""):
            p = " ".join(part.split()).strip(" -;,|")
            if not p or p.startswith(DOOR_CODE_PREFIX) or not any(x.search(p) for x in pats):
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


def build_breakfast(hotel_id: str, day: date, reservations: list[Reservation], words: list[str]) -> dict:
    from hotel_checkin.processes.breakfast_labels import breakfast

    per_room: dict[str, dict] = {}
    for r in reservations:
        if not _active(r) or not (r.arrival < day <= r.departure):
            continue
        yes, why = breakfast(r)
        yes = yes or bool(r.breakfast_labeled_at)
        partial = not yes and why.startswith("maar ")
        unread = not yes and not r.folio
        if not (yes or partial or unread):
            continue
        rooms = r.rooms or ["?"]
        persons = r.guest_count
        split = ([persons // len(rooms) + (1 if i < persons % len(rooms) else 0) for i in range(len(rooms))]
                 if persons else [None] * len(rooms))
        found = notes(_texts(r), words)
        for i, room in enumerate(rooms):
            remark: list[str] = []
            check = False
            if partial:
                remark.append(f"ontbijt bijgeboekt, {why[5:]}: nakijken voor welke dag")
                check = True
            elif unread:
                remark.append("folio nog niet gelezen: nakijken of er ontbijt is")
                check = True
            elif persons is None:
                remark.append("aantal personen niet gekend")
                check = True
            if room == "?":
                remark.append(f"nog geen kamer toegewezen ({r.booking_number or ''})")
                check = True
            if len(rooms) > 1 and i == 0:
                remark.append(f"samen met {', '.join(room_name(hotel_id, x) for x in rooms[1:])}"
                              + (f" ({persons} pers.)" if persons else ""))
            if i == 0:
                remark += found
            count = None if (partial or unread) else split[i]
            cur = per_room.get(room)
            if cur:  # twee reservaties in dezelfde kamer (bv. wissel op die dag)
                cur["count"] = (cur["count"] or 0) + (count or 0) if (cur["count"] is not None or count is not None) else None
                cur["remark"] = "; ".join(x for x in (cur["remark"], *remark) if x)
                cur["check"] = cur["check"] or check
            else:
                per_room[room] = {"count": count, "remark": "; ".join(remark), "check": check}
    rows = _rows(hotel_id, _layout(hotel_id, list(per_room)), per_room, {"count": None, "remark": "", "check": False})
    total = sum(r.get("count") or 0 for r in rows if not r.get("sep"))
    return {"kind": "breakfast", "day": day.isoformat(), "rows": rows, "total": total,
            "check": sum(1 for r in rows if r.get("check"))}


def build_cleaning(hotel_id: str, day: date, reservations: list[Reservation], words: list[str]) -> dict:
    per_room: dict[str, dict] = {}
    for r in reservations:
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
                 {"leave": False, "stay": False, "checkin": False, "remark": "", "check": False})
    real = [r for r in rows if not r.get("sep")]
    totals = {k: sum(1 for r in real if r.get(k)) for k in ("leave", "stay", "checkin")}
    return {"kind": "cleaning", "day": day.isoformat(), "rows": rows, "totals": totals}


def build(hotel_id: str, kind: str, day: date) -> dict:
    cfg = settings(hotel_id, kind)
    reservations = guests.list_reservations(hotel_id)
    if kind == "breakfast":
        data = build_breakfast(hotel_id, day, reservations, cfg["words"])
    else:
        data = build_cleaning(hotel_id, day, reservations, cfg["words"])
        data["controle"], data["extra_rows"] = cfg["controle"], cfg["extra_rows"]
    return data


def describe(data: dict) -> str:
    """Inhoud in een paar woorden (robotlog, monitor)."""
    if data["kind"] == "breakfast":
        rooms = sum(1 for r in data["rows"] if not r.get("sep") and (r.get("count") or r.get("check")))
        return (f"{data.get('total', 0)} personen in {rooms} kamers"
                + (f", {data['check']} na te kijken" if data.get("check") else ""))
    t = data.get("totals", {})
    return f"{t.get('leave', 0)} vertrek, {t.get('stay', 0)} blijvers, {t.get('checkin', 0)} check in"


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


def generate(hotel_id: str, kind: str, day: date, by: str = "", send_now: bool = False, auto: bool = False) -> dict:
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
            f"{describe(data)}" + (f". {_sent_text(sent)}" if send_now else ", niet verstuurd"))
    ok = all(s["ok"] or s.get("skipped") for s in sent)
    guests.log_robot_run(hotel_id, TASK[kind], started, ok, 1, 1 if send_now and sent and ok else 0, note,
                         skipped=sum(1 for s in sent if not s["ok"]))
    return data


def view(hotel_id: str, kind: str) -> dict:
    """Voor de monitor: de bewaarde lijsten (nieuwste eerst, met de tabel), en wanneer de volgende komt."""
    cfg = settings(hotel_id, kind)
    records = [d | {"html": lists.table_html(d), "summary": describe(d)} for d in guests.daily_lists(hotel_id, kind)]
    return {"kind": kind, "switch": switch(hotel_id, kind), "next_day": next_day(hotel_id, kind).isoformat(),
            "time": cfg["time"], "days": cfg["days"], "email": cfg["email"], "whatsapp": cfg["whatsapp"],
            "keep": KEEP, "records": records}


# ---------------------------------------------------------------- timer en robot


def run(hotel_id: str, now: datetime | None = None) -> list[str]:
    """Aangeroepen door de timer (elke 5 minuten): lijsten waarvan het uur voorbij is en die vandaag nog niet
    automatisch gemaakt werden. Geeft terug wat er gemaakt werd."""
    now = (now or datetime.now(clock.tz(hotel_id))).astimezone(clock.tz(hotel_id))
    done = []
    for kind in KINDS:
        if not switch(hotel_id, kind) or now < send_moment(hotel_id, kind, now.date()):
            continue
        day = now.date() + timedelta(days=settings(hotel_id, kind)["days"])
        if (guests.get_daily_list(hotel_id, kind, day.isoformat()) or {}).get("auto"):
            continue
        try:
            generate(hotel_id, kind, day, send_now=True, auto=True)
            done.append(f"{kind} {day.isoformat()}")
        except Exception as exc:
            logging.exception("%s: %s niet gemaakt", hotel_id, kind)
            guests.log_robot_run(hotel_id, TASK[kind], datetime.now(UTC), False, 1, 0,
                                 f"lijst voor {day:%d/%m} niet gemaakt: {type(exc).__name__}: {exc}")
    return done


def _windows(hotel_id: str, now: datetime) -> list[str]:
    """Lijsten die binnen REFRESH_HOURS automatisch verstuurd worden ("soort:dag")."""
    now = now.astimezone(clock.tz(hotel_id))
    out = []
    for kind in KINDS:
        if not switch(hotel_id, kind):
            continue
        at = send_moment(hotel_id, kind, now.date())
        if at - timedelta(hours=REFRESH_HOURS) <= now < at:
            out.append(f"{kind}:{(now.date() + timedelta(days=settings(hotel_id, kind)['days'])).isoformat()}")
    return out


def _refreshed(hotel_id: str) -> list[str]:
    try:
        return list(json.loads(guests.get_state(hotel_id, REFRESH_STATE) or "[]"))
    except ValueError:
        return []


def refresh_due(hotel_id: str, now: datetime | None = None) -> list[Reservation]:
    """Reservaties die de robot nu opnieuw moet lezen voor een lijst die binnenkort verstuurd wordt (één keer per
    lijst): wie op die dag in het hotel is, aankomt of vertrekt."""
    now = now or datetime.now(UTC)
    todo = [w for w in _windows(hotel_id, now) if w not in _refreshed(hotel_id)]
    days = {date.fromisoformat(w.split(":", 1)[1]) for w in todo}
    if not days:
        return []
    return sorted((r for r in guests.list_reservations(hotel_id)
                   if _active(r) and any(r.arrival <= d <= r.departure for d in days)), key=lambda r: r.arrival)


def refresh_done(hotel_id: str, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    keep = [w for w in _refreshed(hotel_id) if w.split(":", 1)[1] >= (now.date() - timedelta(days=3)).isoformat()]
    guests.set_state(hotel_id, REFRESH_STATE, json.dumps(sorted(set(keep) | set(_windows(hotel_id, now)))))
