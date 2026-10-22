"""Tests voor het bouwblok mail, zonder echte Graph-aanroep."""

import json

import httpx

from hotel_checkin.messaging.email import send_email


def _client(status: int, captured: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(status, headers={"request-id": "abc"}, text="fout" if status != 202 else "")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_send_ok():
    captured: dict = {}
    result = send_email(
        to="gast@example.com",
        subject="Test",
        html_body="<p>Hallo</p>",
        attachments=[("info.txt", b"abc")],
        sender="checkin@hotellucca.be",
        client=_client(202, captured),
    )
    assert result.ok and result.provider_id == "abc"
    assert captured["url"].endswith("/users/checkin@hotellucca.be/sendMail")
    msg = captured["body"]["message"]
    assert msg["toRecipients"][0]["emailAddress"]["address"] == "gast@example.com"
    assert msg["attachments"][0]["contentBytes"] == "YWJj"
    assert msg["replyTo"][0]["emailAddress"]["address"] == "info@hotellucca.be"


def test_send_error_is_returned_not_raised():
    result = send_email(
        to="gast@example.com",
        subject="Test",
        html_body="x",
        sender="checkin@hotellucca.be",
        client=_client(403, {}),
    )
    assert not result.ok and "403" in result.error
