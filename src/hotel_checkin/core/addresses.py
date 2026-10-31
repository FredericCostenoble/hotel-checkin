"""E-mailadressen van gasten: eigen adres of doorstuuradres van een boekingsplatform.

Booking.com, Expedia, ... geven vaak een doorstuuradres (bv. ...@guest.booking.com). Mails daarheen
komen bij de gast aan (als het hotel de afzender en links goedkeurde in het extranet), maar het is
niet het eigen adres van de gast. Het eigen adres (check-in-formulier) gaat altijd voor.
"""

from __future__ import annotations

RELAY_DOMAINS = {
    "guest.booking.com": "Booking.com",
    "expediapartnercentral.com": "Expedia",
    "m.expediapartnercentral.com": "Expedia",
    "agoda-messaging.com": "Agoda",
    "guest.airbnb.com": "Airbnb",
    "messaging.trip.com": "Trip.com",
    "hotels.com": "Hotels.com",
}


def relay_platform(email: str | None) -> str | None:
    """Naam van het platform als dit een doorstuuradres is, anders None."""
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[1].lower()
    for d, name in RELAY_DOMAINS.items():
        if domain == d or domain.endswith("." + d):
            return name
    return None


def is_own_email(email: str | None) -> bool:
    """Een echt adres van de gast (geen doorstuuradres van een boekingsplatform)."""
    return bool(email and "@" in email) and relay_platform(email) is None
