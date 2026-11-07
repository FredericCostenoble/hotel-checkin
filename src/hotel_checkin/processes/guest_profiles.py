"""Proces: reservaties koppelen aan gastprofielen, verblijven meetellen, profielen samenvoegen.

Regels om te beslissen of twee boekingen van dezelfde gast zijn (voorspelbaar, geen gok):
- Automatisch samen (sterk): zelfde eigen e-mailadres (geen doorstuuradres van Booking.com,
  Expedia, ...) of zelfde telefoonnummer (E.164).
- Alleen voorgesteld in de monitor (de gebruiker beslist): zelfde naam (zonder hoofdletters,
  accenten, volgorde van de woorden, en met tussenvoegsels aan elkaar: "Van den Broucke" =
  "Vandenbroucke") in hetzelfde land, of bijna dezelfde naam in hetzelfde land: tikfout, andere
  schrijfwijze die hetzelfde klinkt (Peeters/Peters, Maria/Marie), een initiaal (J. Peeters) of een
  extra voornaam (Anna Maria Peeters). Een keuze "andere persoon" wordt onthouden.

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


# Tussenvoegsels: worden aan het volgende woord vastgemaakt (De Smet = Desmet)
_PARTICLES = {"van", "von", "vom", "der", "den", "de", "del", "della", "dello", "des", "di", "da", "du", "le", "la",
              "les", "het", "ter", "ten", "te", "dos", "das", "do", "mac", "mc", "st", "op", "in", "t"}


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def name_tokens(first: str, last: str) -> list[str]:
    """Woorden van de naam, met tussenvoegsels vast aan het volgende woord:
    'Jan Van den Broucke' -> ['jan', 'vandenbroucke'], 'Jan Vandenbroucke' -> zelfde."""
    out, pending = [], ""
    for word in re.findall(r"[a-z]+", _ascii(f"{first} {last}")):
        if word in _PARTICLES:
            pending += word
            continue
        out.append(pending + word)
        pending = ""
    if pending:
        out.append(pending)
    return out


def canonical_name(first: str, last: str) -> str:
    """Sleutel voor 'zelfde naam': woorden gesorteerd, tussenvoegsels vast."""
    return " ".join(sorted(name_tokens(first, last)))


def sound(word: str) -> str:
    """Hoe een woord ongeveer klinkt: eerste letter plus medeklinkers, met gelijk klinkende letters
    samen (ck/c/q = k, ph = f, ij/y = i, z = s, w = v, d op het einde = t). Peeters en Peters,
    Maria en Marie, Kathy en Cathy klinken zo hetzelfde."""
    w = word
    for a, b in (("ck", "k"), ("ph", "f"), ("ij", "i"), ("y", "i"), ("c", "k"), ("q", "k"), ("z", "s"),
                 ("w", "v"), ("dt", "t")):
        w = w.replace(a, b)
    if len(w) > 1 and w.endswith("d"):
        w = w[:-1] + "t"
    if not w:
        return ""
    return re.sub(r"(.)\1+", r"\1", w[0] + re.sub(r"[aeiouh]", "", w[1:]))


def token_match(a: str, b: str) -> int:
    """2 = zelfde woord, 1 = waarschijnlijk hetzelfde (tikfout, klinkt hetzelfde, initiaal), 0 = anders."""
    if a == b:
        return 2
    if len(a) == 1 or len(b) == 1:
        return 1 if a[0] == b[0] else 0
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return 1 if ratio >= 0.85 or (ratio >= 0.7 and sound(a) == sound(b)) else 0


def names_similar(a: list[str], b: list[str]) -> bool:
    """Bijna dezelfde naam: elk woord van de kortste naam (min. 2 woorden) past bij een ander woord van
    de langste, en minstens één volledig woord (3+ letters) past (niet alleen initialen)."""
    short, long_ = sorted((a, b), key=len)
    if len(short) < 2:
        return False
    used: set[int] = set()
    full = False
    for word in short:
        best = max(((token_match(word, other), i) for i, other in enumerate(long_) if i not in used), default=(0, -1))
        if best[0] == 0:
            return False
        used.add(best[1])
        full = full or (len(word) >= 3 and len(long_[best[1]]) >= 3)
    return full


def channel_of(r: Reservation) -> str:
    return r.source or "onbekend"


# ---------------------------------------------------------------- koppelen


def own_emails(g: GuestProfile) -> set[str]:
    """Alle eigen adressen van een profiel (huidig en vroeger), geen doorstuuradressen."""
    return {e.lower() for e in [g.email, *g.known_emails] if e and is_own_email(e)}


def phones(g: GuestProfile) -> set[str]:
    """Eigen nummers van een profiel, zonder nepnummers van boekingssites (bv. +11111111111111 van Expedia)."""
    from hotel_checkin.checkin.service import placeholder_phone

    return {p for p in [g.phone, *g.known_phones] if p and not placeholder_phone(p)}


def names_fit(first: str, last: str, g: GuestProfile) -> bool:
    """Passen de namen? Minstens een deel van de naam gemeen (of een van beide zonder naam).
    Zo wordt een partner of familielid met hetzelfde adres of nummer niet samengevoegd."""
    a, b = name_tokens(first, last), name_tokens(g.first_name, g.last_name)
    return not a or not b or any(len(x) >= 3 and len(y) >= 3 and token_match(x, y) for x in a for y in b)


def _strong_match(r: Reservation, candidates: list[GuestProfile]) -> GuestProfile | None:
    """Zeker dezelfde gast: hetzelfde eigen e-mailadres of gsm-nummer (huidig of vroeger), en de
    naam past. Doorstuuradressen van Booking.com/Expedia tellen nooit (ze zijn per reservatie)."""
    mine_e = {e.lower() for e in (r.guest.email,) if e and is_own_email(e)}
    from hotel_checkin.checkin.service import placeholder_phone

    mine_p = {p for p in (r.guest.phone,) if p and not placeholder_phone(p)}
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


# Veiligheidsgrens: een blok (zelfde klank van een woord + zelfde beginletter van een ander woord) met
# meer profielen wordt overgeslagen. Normaal zijn blokken klein (familienaam + initiaal voornaam).
MAX_GROUP = 300


def _blocks(tokens: list[str]) -> set[str]:
    """Sleutels om kandidaten te vinden zonder alle paren te vergelijken: klank van een woord plus
    de beginklank van een ander woord, bv. Maria Peeters -> 'ptrs|m' en 'mr|p'."""
    return {f"{sound(t)}|{sound(u)[:1]}" for t in tokens for u in tokens if t is not u and len(t) >= 3 and u}


def possible_matches(hotel_id: str, limit: int = 50) -> list[dict]:
    """Paren die misschien dezelfde gast zijn, voor de monitor. Nooit automatisch samengevoegd.

    Volgorde: zelfde (of extra) adres of nummer, dan dezelfde naam, dan bijna dezelfde naam.
    Nepnummers van boekingssites (bv. +11111111111111 van Expedia) tellen niet.
    """
    from hotel_checkin.checkin.service import placeholder_phone

    all_profiles = profiles.list_profiles(hotel_id)
    different = profiles.different_pairs(hotel_id)
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []

    def add(a: GuestProfile, b: GuestProfile, reason: str, contact: str = "") -> bool:
        """Voeg het paar toe als het nieuw is. True = de limiet is bereikt."""
        pair = tuple(sorted((a.guest_id, b.guest_id)))
        if a.guest_id == b.guest_id or pair in seen or profiles.is_marked_different(different, *pair):
            return False
        seen.add(pair)
        out.append({"a": pair[0], "b": pair[1], "reason": reason, **({"contact": contact} if contact else {})})
        return len(out) >= limit

    # extra adres of nummer uit het formulier van de ene gast = adres of nummer van de andere:
    # misschien dezelfde persoon, misschien een partner. Daarom alleen voorstellen.
    # Zelfde eigen adres of nummer maar een andere naam (partner, familie?): ook alleen voorstellen.
    contacts = {g.guest_id: own_emails(g) | phones(g) for g in all_profiles}
    by_contact: dict[str, list[GuestProfile]] = {}
    for g in all_profiles:
        extra = {(g.backup_email or "").lower(), "" if placeholder_phone(g.backup_phone) else (g.backup_phone or "")}
        for v in contacts[g.guest_id] | extra:
            if v and (("@" not in v) or is_own_email(v)):
                by_contact.setdefault(v, []).append(g)
    for value, group in by_contact.items():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                both_own = value in contacts[a.guest_id] and value in contacts[b.guest_id]
                if add(a, b, "same_contact" if both_own else "extra_contact", value):
                    return out

    pool = [g for g in all_profiles if g.first_name or g.last_name]
    tokens = {g.guest_id: name_tokens(g.first_name, g.last_name) for g in pool}

    def other_country(a: GuestProfile, b: GuestProfile) -> bool:
        return bool(a.country and b.country and a.country != b.country)

    by_name: dict[str, list[GuestProfile]] = {}
    for g in pool:
        by_name.setdefault(" ".join(sorted(tokens[g.guest_id])), []).append(g)
    for group in by_name.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if not other_country(a, b) and add(a, b, "same_name"):
                    return out

    by_block: dict[str, list[GuestProfile]] = {}
    for g in pool:
        for key in _blocks(tokens[g.guest_id]):
            by_block.setdefault(key, []).append(g)
    for group in by_block.values():
        if len(group) > MAX_GROUP:
            continue
        for i, a in enumerate(group):
            ta = tokens[a.guest_id]
            for b in group[i + 1:]:
                tb = tokens[b.guest_id]
                if sorted(ta) == sorted(tb) or other_country(a, b):
                    continue
                if names_similar(ta, tb) and add(a, b, "similar_name"):
                    return out
    return out
