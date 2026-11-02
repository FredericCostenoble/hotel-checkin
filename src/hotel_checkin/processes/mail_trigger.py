"""Proces: meldingen van Lighthouse/Cubilis in de mailbox starten de robot meteen.

Elke minuut (Function App, timer): nieuwe mails in de mailbox van het hotel lezen (bouwblok
mailbox), meldingen herkennen (bouwblok cubilis_mail) en bij een melding de robot starten
(bouwblok cloud_robot), zonder te wachten op het schema. Het schema van de robot blijft als vangnet.

Aan per hotel met [robot] mail_trigger = true. Tot waar gelezen werd, staat in RobotState.

Ook: betaalverzoeken van Lighthouse ("Betaal uw openstaande saldo", naar checkin@). De betaallink wordt
bij de reservatie bewaard (betaalknop in onze mail) en de mail gaat naar de map Betaalverzoeken.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from hotel_checkin.admin import cloud_robot
from hotel_checkin.core.config import hotel_setting
from hotel_checkin.guests import repository as guests
from hotel_checkin.messaging import mailbox
from hotel_checkin.pms.cubilis_mail import parse_notice
from hotel_checkin.pms.lighthouse_mail import parse_payment_mail

TASK = "meldingen"
PAYMENT_FOLDER = "Betaalverzoeken"
STATE_KEY = "mail_trigger_since"
ERROR_LOG_MINUTES = 60  # een fout hoogstens eens per uur in het logboek (draait elke minuut)


def enabled(hotel_id: str) -> bool:
    return str(hotel_setting(hotel_id, "ROBOT_MAIL_TRIGGER", default="false", shared=False)).lower() == "true"


def run(hotel_id: str) -> int:
    """Geeft het aantal gevonden meldingen terug. Logt alleen als er meldingen waren (of een fout)."""
    started = datetime.now(UTC)
    since_text = guests.get_state(hotel_id, STATE_KEY)
    since = datetime.fromisoformat(since_text) if since_text else started - timedelta(minutes=10)
    try:
        messages = mailbox.list_messages(hotel_id, since)
    except Exception as exc:  # noqa: BLE001 - bv. nog geen rechten op de mailbox
        _log_error(hotel_id, started, f"Mailbox niet gelezen: {type(exc).__name__}: {str(exc)[:300]}")
        return 0
    _payment_links(hotel_id, messages)
    notices = [n for m in messages if (n := parse_notice(m["sender"], m["subject"], m["text"]))]
    newest = max((m["received_at"] for m in messages), default=None)
    # Gewijzigd of geannuleerd: de lijst van nieuwe boekingen toont dat niet; de robot leest de
    # reservaties van die dagen opnieuw (ook als hij nu al bezig is: bij de volgende run)
    from hotel_checkin.processes import refresh_requests

    refresh_requests.request(hotel_id, [d for n in notices if n.kind in ("modified", "cancelled")
                                        for d in (n.arrival, n.departure)])
    if not notices:
        if newest:
            guests.set_state(hotel_id, STATE_KEY, (newest + timedelta(seconds=1)).isoformat())
        return 0
    if cloud_robot.available() and cloud_robot.running():
        logging.info("%s: %s meldingen, robot is al bezig; volgende minuut opnieuw", hotel_id, len(notices))
        return len(notices)  # leesgrens niet verzetten, zodat dit na de lopende run opnieuw gebeurt
    started_robot = cloud_robot.start() if cloud_robot.available() else False
    kinds = {"new": "nieuw", "modified": "gewijzigd", "cancelled": "geannuleerd"}
    note = ", ".join(f"{kinds.get(n.kind, n.kind)} {n.number or '?'}" for n in notices)
    note += ". Robot gestart." if started_robot else ". Robot NIET gestart."
    guests.log_robot_run(hotel_id, TASK, started, started_robot, len(notices), 0, note)
    if started_robot and newest:
        guests.set_state(hotel_id, STATE_KEY, (newest + timedelta(seconds=1)).isoformat())
    return len(notices)


def _payment_links(hotel_id: str, messages: list[dict]) -> int:
    """Betaallinks uit betaalverzoeken van Lighthouse bij de reservatie bewaren. Geeft het aantal terug."""
    found = [(m, p) for m in messages if (p := parse_payment_mail(m["subject"], m["text"]))]
    if not found:
        return 0
    by_number = {r.booking_number: r for r in guests.list_reservations(hotel_id) if r.booking_number}
    saved = 0
    for m, p in found:
        r = by_number.get(p.booking_number)
        if r is None:
            logging.warning("%s: betaallink voor onbekende reservatie %s", hotel_id, p.booking_number)
            continue
        if r.pay_link != p.link:
            r.pay_link = p.link
            guests.save_reservation(r, fields=guests.PAY_LINK_FIELDS)
            saved += 1
        mailbox.move_message(hotel_id, m["id"], PAYMENT_FOLDER)  # lukt niet zonder Mail.ReadWrite: dan blijft ze staan
    if saved:
        guests.log_robot_run(hotel_id, TASK, datetime.now(UTC), True, len(found), saved,
                             "Betaallink bewaard: " + ", ".join(p.booking_number for _, p in found))
    return saved


def _log_error(hotel_id: str, started: datetime, error: str) -> None:
    logging.warning("%s: %s", hotel_id, error)
    last = [r for r in guests.robot_runs(hotel_id, limit=50, task=TASK) if not r.get("ok")]
    if last and started - datetime.fromisoformat(last[0]["started_at"]) < timedelta(minutes=ERROR_LOG_MINUTES):
        return
    guests.log_robot_run(hotel_id, TASK, started, False, 0, 0, error)
