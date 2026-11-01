"""Proces: reservaties koppelen aan gastprofielen, verblijven meetellen, profielen samenvoegen.

Regels om te beslissen of twee boekingen van dezelfde gast zijn (voorspelbaar, geen gok):
- Automatisch samen (sterk): zelfde eigen e-mailadres (geen doorstuuradres van Booking.com,
  Expedia, ...) of zelfde telefoonnummer (E.164).
- Alleen voorgesteld in de monitor (de gebruiker beslist): zelfde naam (zonder hoofdletters,
  accenten en volgorde van de woorden) in hetzelfde land, of bijna dezelfde naam (tikfout) in
  hetzelfde land. Een keuze "andere persoon" wordt onthouden.

Gegevens van het check-in-formulier (door de gast zelf ingevuld) gaan voor op die uit Lighthouse.
Een verblijf telt mee in het profiel zodra het vertrek voorbij is en het niet geannuleerd werd.
Geannuleerde reservaties tellen meteen mee als annulering (de gast blijft bereikbaar).
Een verblijf is een periode: reservaties van dezelfde gast die in de tijd overlappen (bv. twee
kamers voor dezelfde nachten) vormen samen één verblijf; de nachten tellen één keer.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter
from datetime import UTC, date, datetime

from hotel_checkin.core import clock

# Doorstuuradressen van boekingsplatformen: per boeking anders en niet bruikbaar voor marketing
from hotel_checkin.core.addresses import (  # noqa: F401 - ook hier gebruikt
    RELAY_DOMAINS,
    is_own_email,
)
from hotel_checkin.core.models import GuestProfile, Reservation, ReservationStatus
from hotel_checkin.guests import profiles
from hotel_checkin.guests import repository as guests


def name_key(first: str, last: str) -> str:
    """'DE VOORBEELD Maria' en 'Maria de Voorbeeld' geven dezelfde sleutel."""
    text = unicodedata.normalize("NFKD", f"{first} {last}").encode("ascii", "ignore").decode().lower()
    return " ".join(sorted(re.findall(r"[a-z]+", text)))


def channel_of(r: Reservation) -> str:
    return r.source or "onbekend"


# ---------------------------------------------------------------- koppelen


def own_emails(g: GuestProfile) -> set[str]:
    """Alle eigen adressen van een profiel (huidig en vroeger), geen doorstuuradressen."""
    return {e.lower() for e in [g.email, *g.known_emails] if e and is_own_email(e)}


def phones(g: GuestProfile) -> set[str]:
    return {p for p in [g.phone, *g.known_phones] if p}


def names_fit(first: str, last: str, g: GuestProfile) -> bool:
    """Passen de namen? Minstens een deel van de naam gemeen (of een van beide zonder naam).
    Zo wordt een partner of familielid met hetzelfde adres of nummer niet samengevoegd."""
    a, b = set(name_key(first, last).split()), set(name_key(g.first_name, g.last_name).split())
    return not a or not b or bool(a & b)


def _strong_match(r: Reservation, candidates: list[GuestProfile]) -> GuestProfile | None:
    """Zeker dezelfde gast: hetzelfde eigen e-mailadres of gsm-nummer (huidig of vroeger), en de
    naam past. Doorstuuradressen van Booking.com/Expedia tellen nooit (ze zijn per reservatie)."""
    mine_e = {e.lower() for e in (r.guest.email,) if e and is_own_email(e)}
    mine_p = {p for p in (r.guest.phone,) if p}
    for g in candidates:
        if ((mine_e & own_emails(g)) or (mine_p & phones(g))) and names_fit(r.guest.first_name, r.guest.last_name, g):
            return g
    return None


def _remember(g: GuestProfile, email: str | None, phone: str | None) -> None:
    """Eigen adres en nummer onthouden, ook als ze later vervangen worden (herkennen bij een volgende boeking)."""
    if email and is_own_email(email) and email.lower() not in {e.lower() for e in g.known_emails}:
        g.known_emails.append(email.lower())
    if phone and phone not in g.known_phones:
        g.known_phones.append(phone)


def _update_contact(g: GuestProfile, r: Reservation) -> None:
    """Contact van de reservatie in het profiel. Formulier gaat voor; anders alleen aanvullen
    (of een doorstuuradres vervangen door een eigen adres)."""
    from_form = bool(r.checkin_completed_at)
    if from_form or not (g.first_name or g.last_name):
        g.first_name, g.last_name = r.guest.first_name or g.first_name, r.guest.last_name or g.last_name
    email = (r.guest.email or "").lower() or None
    if email and (from_form or not g.email or (is_own_email(email) and not g.email_own)):
        g.email, g.email_own = email, is_own_email(email)
    if r.guest.phone and (from_form or not g.phone):
        g.phone = r.guest.phone
    _remember(g, r.guest.email, r.guest.phone)
    _remember(g, g.email, g.phone)
    if from_form:  # extra adres en nummer uit het formulier (leeg = door de gast weggehaald)
        g.backup_email = (r.guest.backup_email or "").lower() or None
        g.backup_phone = r.guest.backup_phone or None
    if r.guest.country and (from_form or not g.country):
        g.country = r.guest.country
    if r.guest.language and (from_form or not g.from_checkin_form):
        g.language = r.guest.language
    if from_form and r.guest.channels is not None:
        g.message_channels = list(r.guest.channels)
    g.from_checkin_form = g.from_checkin_form or from_form
    if r.reservation_id not in g.reservation_ids:
        g.reservation_ids.append(r.reservation_id)


def link(r: Reservation, all_profiles: list[GuestProfile] | None = None) -> GuestProfile | None:
    """Koppel de reservatie aan een gastprofiel (bestaand of nieuw) en bewaar beide.

    Zonder naam, e-mail en telefoon: geen profiel. Vindt het een tweede profiel dat sterk
    overeenkomt (bv. nu het formulier een eigen adres gaf), dan worden ze samengevoegd.
    """
    if not (r.guest.first_name or r.guest.last_name or r.guest.email or r.guest.phone):
        return None
    pool = all_profiles if all_profiles is not None else profiles.list_profiles(r.hotel_id)
    g = profiles.get_profile(r.hotel_id, r.guest_id) if r.guest_id else None
    if g is None:
        g = _strong_match(r, pool) or profiles.new_profile(r.hotel_id)
    _update_contact(g, r)
    other = _strong_match(r, [p for p in pool if p.guest_id != g.guest_id])
    if other is not None:
        g = merge(r.hotel_id, g.guest_id, other.guest_id, keep=g, other=other)
    else:
        profiles.save_profile(g)
    if r.guest_id != g.guest_id:
        r.guest_id = g.guest_id
        guests.save_reservation(r, fields=("guest_id",))
    if count_cancellation(r):
        g = profiles.get_profile(r.hotel_id, g.guest_id) or g
    if all_profiles is not None:
        all_profiles[:] = [p for p in all_profiles if p.guest_id != g.guest_id and (other is None or p.guest_id != other.guest_id)] + [g]
    return g


# ---------------------------------------------------------------- verblijven meetellen


def _merge_periods(periods: list[list[str]]) -> list[list[str]]:
    """Overlappende periodes samenvoegen (vertrek = aankomst van de volgende telt niet als overlap)."""
    out: list[list[str]] = []
    for a, d in sorted(periods):
        if out and a < out[-1][1]:
            out[-1][1] = max(out[-1][1], d)
        else:
            out.append([a, d])
    return out


def _apply_periods(g: GuestProfile) -> None:
    g.stay_periods = _merge_periods(g.stay_periods)
    g.stays = len(g.stay_periods)
    g.nights = sum((date.fromisoformat(d) - date.fromisoformat(a)).days for a, d in g.stay_periods)
    g.first_stay = date.fromisoformat(g.stay_periods[0][0]) if g.stay_periods else None
    g.last_stay = date.fromisoformat(g.stay_periods[-1][1]) if g.stay_periods else None


def _overlaps(g: GuestProfile, r: Reservation) -> bool:
    a, d = r.arrival.isoformat(), r.departure.isoformat()
    return any(a < pd and d > pa for pa, pd in g.stay_periods)


def count_stay(r: Reservation, today: date | None = None) -> bool:
    """Tel een voorbij, niet geannuleerd verblijf één keer mee in het profiel.

    Overlapt het met een verblijf dat al meetelt (bv. tweede kamer voor dezelfde nachten), dan
    komt er geen verblijf bij: alleen de kamer en de personen worden toegevoegd.
    """
    today = today or clock.today(r.hotel_id)
    if r.stay_counted_at or not r.guest_id or r.status == ReservationStatus.CANCELLED or r.departure >= today:
        return False
    g = profiles.get_profile(r.hotel_id, r.guest_id)
    if g is None:
        return False
    same_stay = _overlaps(g, r)
    g.stay_periods.append([r.arrival.isoformat(), r.departure.isoformat()])
    _apply_periods(g)
    if r.guest_count:
        g.persons += r.guest_count
        if not same_stay:
            g.persons_stays += 1
    for room in r.rooms:
        g.rooms[room] = g.rooms.get(room, 0) + 1
    if r.room_type:
        g.room_types[r.room_type] = g.room_types.get(r.room_type, 0) + 1
    if not same_stay:
        g.channels[channel_of(r)] = g.channels.get(channel_of(r), 0) + 1
    profiles.save_profile(g)
    r.stay_counted_at = datetime.now(UTC)
    guests.save_reservation(r, fields=("stay_counted_at",))
    return True


def count_cancellation(r: Reservation, today: date | None = None) -> bool:
    """Tel een geannuleerde reservatie één keer mee in het profiel."""
    if r.cancel_counted_at or not r.guest_id or r.status != ReservationStatus.CANCELLED:
        return False
    g = profiles.get_profile(r.hotel_id, r.guest_id)
    if g is None:
        return False
    g.cancellations += 1
    g.last_cancelled = today or clock.today(r.hotel_id)
    profiles.save_profile(g)
    r.cancel_counted_at = datetime.now(UTC)
    guests.save_reservation(r, fields=("cancel_counted_at",))
    return True


def reset_counts(hotel_id: str) -> int:
    """Alle tellingen opnieuw (na een wijziging in de manier van tellen). Geeft het aantal
    reservaties terug dat opnieuw meegeteld kan worden. Reservaties die al opgeruimd zijn, tellen
    dan niet meer mee."""
    for g in profiles.list_profiles(hotel_id):
        g.stays = g.nights = g.persons = g.persons_stays = g.cancellations = 0
        g.last_cancelled = None
        g.stay_periods, g.rooms, g.room_types, g.channels = [], {}, {}, {}
        g.first_stay = g.last_stay = None
        profiles.save_profile(g)
    n = 0
    for r in guests.list_reservations(hotel_id):
        if r.stay_counted_at or r.cancel_counted_at:
            r.stay_counted_at = r.cancel_counted_at = None
            guests.save_reservation(r, fields=("stay_counted_at", "cancel_counted_at"))
            n += 1
    return n


# ---------------------------------------------------------------- samenvoegen en voorstellen


def merge(hotel_id: str, keep_id: str, other_id: str, keep: GuestProfile | None = None,
          other: GuestProfile | None = None) -> GuestProfile:
    """Voeg profiel `other` samen in `keep`: tellers opgeteld, reservaties herkoppeld, `other` verwijderd."""
    keep = keep or profiles.get_profile(hotel_id, keep_id)
    other = other or profiles.get_profile(hotel_id, other_id)
    if keep is None or other is None or keep.guest_id == other.guest_id:
        return keep or other
    keep.last_cancelled = max(filter(None, (keep.last_cancelled, other.last_cancelled)), default=None)
    for k in ("persons", "persons_stays", "cancellations"):
        setattr(keep, k, getattr(keep, k) + getattr(other, k))
    keep.stay_periods = keep.stay_periods + other.stay_periods
    for k in ("rooms", "room_types", "channels"):
        setattr(keep, k, dict(Counter(getattr(keep, k)) + Counter(getattr(other, k))))
    _apply_periods(keep)  # stays, nights, eerste en laatste verblijf uit de periodes
    # Contact: wat de gast zelf bevestigde of een eigen adres gaat voor
    if other.from_checkin_form and not keep.from_checkin_form:
        keep.first_name, keep.last_name = other.first_name or keep.first_name, other.last_name or keep.last_name
        keep.phone, keep.language = other.phone or keep.phone, other.language or keep.language
    if other.email and (not keep.email or (other.email_own and not keep.email_own)
                        or (other.from_checkin_form and not keep.from_checkin_form)):
        keep.email, keep.email_own = other.email, other.email_own
    keep.message_channels = keep.message_channels or other.message_channels
    keep.backup_email = keep.backup_email or other.backup_email
    keep.backup_phone = keep.backup_phone or other.backup_phone
    keep.muted_channels = sorted(set(keep.muted_channels) | set(other.muted_channels))
    for e in [other.email, *other.known_emails]:
        _remember(keep, e, None)
    for ph in [other.phone, *other.known_phones]:
        _remember(keep, None, ph)
    keep.phone = keep.phone or other.phone
    keep.country = keep.country or other.country
    keep.from_checkin_form = keep.from_checkin_form or other.from_checkin_form
    keep.reservation_ids = list(dict.fromkeys(keep.reservation_ids + other.reservation_ids))
    for rid in other.reservation_ids:
        r = guests.get_reservation(hotel_id, rid)
        if r is not None and r.guest_id != keep.guest_id:
            r.guest_id = keep.guest_id
            guests.save_reservation(r, fields=("guest_id",))
    profiles.save_profile(keep)
    profiles.delete_profile(hotel_id, other.guest_id)
    return keep


# Naamdelen die niets zeggen over wie iemand is (Van, De, Der, ...): niet gebruikt om te vergelijken
_PARTICLES = {"van", "von", "der", "den", "del", "della", "des", "het", "ter", "ten", "dos", "das", "les", "mac"}
# Gelijkaardige namen (tikfouten) alleen zoeken binnen groepen tot zoveel profielen met hetzelfde
# naamdeel; anders groeit het kwadratisch (2 jaar gasten). Exact dezelfde naam wordt altijd gevonden.
MAX_GROUP = 200


def possible_matches(hotel_id: str, limit: int = 50) -> list[dict]:
    """Paren die misschien dezelfde gast zijn, voor de monitor. Nooit automatisch samengevoegd.

    Volgorde: zelfde (of extra) adres of nummer, dan exact dezelfde naam, dan een gelijkaardige naam.
    """
    all_profiles = profiles.list_profiles(hotel_id)
    different = profiles.different_pairs(hotel_id)
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []

    def add(a: GuestProfile, b: GuestProfile, reason: str) -> bool:
        """Voeg het paar toe als het nieuw is. True = de limiet is bereikt."""
        pair = tuple(sorted((a.guest_id, b.guest_id)))
        if a.guest_id == b.guest_id or pair in seen or profiles.is_marked_different(different, *pair):
            return False
        seen.add(pair)
        out.append({"a": pair[0], "b": pair[1], "reason": reason})
        return len(out) >= limit

    # extra adres of nummer uit het formulier van de ene gast = adres of nummer van de andere:
    # misschien dezelfde persoon, misschien een partner. Daarom alleen voorstellen.
    # Zelfde eigen adres of nummer maar een andere naam (partner, familie?): ook alleen voorstellen.
    contacts = {g.guest_id: own_emails(g) | phones(g) for g in all_profiles}
    by_contact: dict[str, list[GuestProfile]] = {}
    for g in all_profiles:
        extra = {(g.backup_email or "").lower(), g.backup_phone or ""}
        for v in contacts[g.guest_id] | extra:
            if v and (("@" not in v) or is_own_email(v)):
                by_contact.setdefault(v, []).append(g)
    for value, group in by_contact.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                both_own = value in contacts[a.guest_id] and value in contacts[b.guest_id]
                if add(a, b, "same_contact" if both_own else "extra_contact"):
                    return out

    pool = [g for g in all_profiles if g.first_name or g.last_name]
    keys = {g.guest_id: name_key(g.first_name, g.last_name) for g in pool}

    def other_country(a: GuestProfile, b: GuestProfile) -> bool:
        return bool(a.country and b.country and a.country != b.country)

    by_key: dict[str, list[GuestProfile]] = {}
    for g in pool:
        by_key.setdefault(keys[g.guest_id], []).append(g)
    for group in by_key.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if not other_country(a, b) and add(a, b, "same_name"):
                    return out

    by_token: dict[str, list[GuestProfile]] = {}
    for g in pool:
        for token in set(keys[g.guest_id].split()):
            if len(token) > 2 and token not in _PARTICLES:
                by_token.setdefault(token, []).append(g)
    for group in by_token.values():
        if len(group) > MAX_GROUP:
            continue
        for i, a in enumerate(group):
            ka = keys[a.guest_id]
            for b in group[i + 1:]:
                kb = keys[b.guest_id]
                if ka == kb or other_country(a, b) or abs(len(ka) - len(kb)) > max(len(ka), len(kb)) // 5 + 1:
                    continue
                m = difflib.SequenceMatcher(None, ka, kb)
                if m.quick_ratio() >= 0.9 and m.ratio() >= 0.9 and add(a, b, "similar_name"):
                    return out
    return out
