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
from datetime import date, datetime, timezone

from hotel_checkin.core.models import GuestProfile, Reservation, ReservationStatus
from hotel_checkin.guests import profiles
from hotel_checkin.guests import repository as guests

# Doorstuuradressen van boekingsplatformen: per boeking anders en niet bruikbaar voor marketing
RELAY_DOMAINS = ("guest.booking.com", "expediapartnercentral.com", "m.expediapartnercentral.com",
                 "agoda-messaging.com", "guest.airbnb.com", "messaging.trip.com", "hotels.com")


def is_own_email(email: str | None) -> bool:
    if not email or "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].lower()
    return not any(domain == d or domain.endswith("." + d) for d in RELAY_DOMAINS)


def name_key(first: str, last: str) -> str:
    """'DE VOORBEELD Maria' en 'Maria de Voorbeeld' geven dezelfde sleutel."""
    text = unicodedata.normalize("NFKD", f"{first} {last}").encode("ascii", "ignore").decode().lower()
    return " ".join(sorted(re.findall(r"[a-z]+", text)))


def channel_of(r: Reservation) -> str:
    return r.source or "onbekend"


# ---------------------------------------------------------------- koppelen


def _strong_match(r: Reservation, candidates: list[GuestProfile]) -> GuestProfile | None:
    email = (r.guest.email or "").lower()
    for g in candidates:
        if is_own_email(email) and g.email and g.email.lower() == email:
            return g
        if r.guest.phone and g.phone and g.phone == r.guest.phone:
            return g
    return None


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
        guests.save_reservation(r)
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
    today = today or date.today()
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
    r.stay_counted_at = datetime.now(timezone.utc)
    guests.save_reservation(r)
    return True


def count_cancellation(r: Reservation, today: date | None = None) -> bool:
    """Tel een geannuleerde reservatie één keer mee in het profiel."""
    if r.cancel_counted_at or not r.guest_id or r.status != ReservationStatus.CANCELLED:
        return False
    g = profiles.get_profile(r.hotel_id, r.guest_id)
    if g is None:
        return False
    g.cancellations += 1
    g.last_cancelled = today or date.today()
    profiles.save_profile(g)
    r.cancel_counted_at = datetime.now(timezone.utc)
    guests.save_reservation(r)
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
            guests.save_reservation(r)
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
    keep.phone = keep.phone or other.phone
    keep.country = keep.country or other.country
    keep.from_checkin_form = keep.from_checkin_form or other.from_checkin_form
    keep.reservation_ids = list(dict.fromkeys(keep.reservation_ids + other.reservation_ids))
    for rid in other.reservation_ids:
        r = guests.get_reservation(hotel_id, rid)
        if r is not None and r.guest_id != keep.guest_id:
            r.guest_id = keep.guest_id
            guests.save_reservation(r)
    profiles.save_profile(keep)
    profiles.delete_profile(hotel_id, other.guest_id)
    return keep


def possible_matches(hotel_id: str, limit: int = 50) -> list[dict]:
    """Paren die misschien dezelfde gast zijn, voor de monitor. Nooit automatisch samengevoegd."""
    pool = [g for g in profiles.list_profiles(hotel_id) if g.first_name or g.last_name]
    different = profiles.different_pairs(hotel_id)
    by_token: dict[str, list[GuestProfile]] = {}
    for g in pool:
        for token in set(name_key(g.first_name, g.last_name).split()):
            if len(token) > 2:
                by_token.setdefault(token, []).append(g)
    seen, out = set(), []
    for group in by_token.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                pair = tuple(sorted((a.guest_id, b.guest_id)))
                if pair in seen or profiles.is_marked_different(different, *pair):
                    continue
                seen.add(pair)
                if a.country and b.country and a.country != b.country:
                    continue
                ka, kb = name_key(a.first_name, a.last_name), name_key(b.first_name, b.last_name)
                if ka == kb:
                    reason = "same_name"
                elif difflib.SequenceMatcher(None, ka, kb).ratio() >= 0.9:
                    reason = "similar_name"
                else:
                    continue
                out.append({"a": a.guest_id, "b": b.guest_id, "reason": reason})
                if len(out) >= limit:
                    return out
    return out
