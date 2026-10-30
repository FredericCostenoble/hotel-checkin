"""Meldingen van Cubilis herkennen, met verzonnen voorbeelden in de opmaak van Cubilis."""

from datetime import date

from hotel_checkin.pms.cubilis_mail import parse_notice

BODY = """Reserveringsnummer: 12345678,

Gemaakt door Jan Voorbeeld op 30 oktober 2026 11:16.

Jan Voorbeeld

Teststraat 1

Aankomst:

maandag 2 november 2026

Vertrek:

dinsdag 3 november 2026

Inchecken:

15:45
"""


def test_new_reservation_direct():
    n = parse_notice("no-reply@cubilis.eu", "Nieuwe reservering bij Lucca Hotel - Brugge (12345678)", BODY)
    assert (n.kind, n.number) == ("new", "12345678")
    assert (n.arrival, n.departure) == (date(2026, 11, 2), date(2026, 11, 3))


def test_forwarded_by_hand():
    text = ("____\nFrom: Cubilis reservations <x@cubilis.eu>\nSent: Friday\nSubject: Nieuwe reservering bij "
            "Lucca Hotel - Brugge (12345678)\n\n" + BODY)
    n = parse_notice("info@hotellucca.be", "Fw: Nieuwe reservering bij Lucca Hotel - Brugge (12345678)", text)
    assert n.kind == "new" and n.number == "12345678" and n.arrival == date(2026, 11, 2)


def test_english_cancellation():
    text = "Reservation number: 87654321\n\nArrival:\n\nMonday 2 November 2026\n\nDeparture:\n\nTuesday 3 November 2026"
    n = parse_notice("noreply@cubilis.com", "Cancelled reservation via Booking.com (87654321)", text)
    assert (n.kind, n.number, n.channel) == ("cancelled", "87654321", "Booking.com")
    assert n.departure == date(2026, 11, 3)


def test_other_mail_ignored():
    assert parse_notice("support@mylighthouse.com", "Activate your Lighthouse account!", "Hi") is None
    assert parse_notice("noreply@cubilis.com", "Your monthly invoice", "Invoice") is None
