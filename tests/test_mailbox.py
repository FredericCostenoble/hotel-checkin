"""Bouwblok mailbox: lezen via Graph (nagebootst) en maskeren van gastgegevens."""

from datetime import datetime, timezone

import httpx

from hotel_checkin.messaging import mailbox


def test_list_messages_reads_and_follows_paging():
    pages = {
        "first": {"value": [{"id": "1", "receivedDateTime": "2026-10-30T10:00:00Z",
                             "from": {"emailAddress": {"address": "NoReply@Cubilis.com"}},
                             "subject": "New reservation via Booking.com", "body": {"content": "tekst"}}],
                  "@odata.nextLink": "https://graph.microsoft.com/next"},
        "next": {"value": [{"id": "2", "receivedDateTime": "2026-10-30T11:00:00Z", "from": None,
                            "subject": None, "body": None}]},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Prefer"] == 'outlook.body-content-type="text"'
        return httpx.Response(200, json=pages["next" if "next" in str(request.url) else "first"])

    msgs = mailbox.list_messages("lucca", datetime(2026, 10, 29, tzinfo=timezone.utc),
                                 client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert [m["id"] for m in msgs] == ["1", "2"]
    assert msgs[0]["sender"] == "noreply@cubilis.com" and msgs[0]["text"] == "tekst"
    assert msgs[1]["subject"] == "" and msgs[1]["sender"] == ""


def test_mask_hides_guest_data_keeps_structure():
    text = ("Reservation number: CPB-4276-002731\nGuest name: Jan Voorbeeld\nEmail: jan@example.com\n"
            "Phone: +32 470 12 34 56\nArrival: 02/11/2026\nDear Voorbeeld, thank you")
    out = mailbox.mask(text, ["Voorbeeld"])
    assert "CPB-4276-002731" in out and "02/11/2026" in out
    assert "Jan" not in out and "Voorbeeld" not in out and "jan@example.com" not in out and "470" not in out
