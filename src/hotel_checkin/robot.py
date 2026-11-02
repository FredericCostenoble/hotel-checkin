"""De Lighthouse-robot als los programma (container in Azure Container Apps).

Draait op schema (standaard elk uur, als vangnet) en op vraag via de knop "Robot nu draaien" op de
opvolgpagina. Leest Lighthouse alleen; schrijft niets in Lighthouse.

    python -m hotel_checkin.robot                  # alle hotels, sinds de nieuwste opgeslagen boeking
    python -m hotel_checkin.robot --hotel lucca --hours 48

Schema van de job per omgeving: GitHub-variabele ROBOT_SCHEDULE (cron, UTC), standaard elk
uur. Nieuwe boekingen komen normaal meteen binnen via de meldingsmail (processes/mail_trigger.py);
het schema vangt op wat geen mail kreeg. Per hotel kan het trager: [robot] check_minutes in het hotelbestand, per omgeving te
overschrijven met Key Vault-geheim <hotel>-robot-check-minutes. Op vraag (knop in de monitor,
ROBOT_MANUAL=1) worden alle hotels gelezen.

Elke run zoekt nieuwe reservaties (en leest van nieuwe meteen de contactgegevens). Om de zoveel
uur ([robot] contact_refresh_hours in het hotelbestand, standaard 2) leest hij ook de
contactgegevens opnieuw van reservaties die binnenkort aankomen en nog geen e-mailadres hebben.

Zonder --hours leest de robot alles sinds de nieuwste boeking die al opgeslagen is (min 1 uur
marge), of de laatste 30 dagen als er nog niets opgeslagen is. Had de vorige run een fout of
overgeslagen rijen, dan leest hij dezelfde periode opnieuw.
"""

from __future__ import annotations

import time

PROCESS_STARTED = time.time()  # zo vroeg mogelijk: begin van de container (vóór de zware imports)

import argparse
import logging
import os
import sys
from datetime import UTC, datetime, timedelta

from hotel_checkin.core.config import hotel_setting
from hotel_checkin.core.hotels import list_hotels
from hotel_checkin.guests import repository as guests
from hotel_checkin.processes import maintenance, new_reservation, refresh_contacts


def _since(hotel_id: str, hours: int | None) -> datetime:
    """Vanaf welke boekdatum lezen.

    - Met --hours: een vast aantal uren terug.
    - Had de vorige run een fout of overgeslagen rijen: opnieuw vanaf dezelfde datum, zodat die
      rijen nog eens geprobeerd worden (bestaande reservaties worden gewoon bijgewerkt).
    - Anders: de nieuwste opgeslagen boeking (min 1 uur marge), of 30 dagen als er nog niets is.
    """
    now = datetime.now(UTC)
    if hours:
        return now - timedelta(hours=hours)
    runs = guests.robot_runs(hotel_id, limit=1, task=new_reservation.TASK)
    if runs and runs[0].get("since") and (not runs[0].get("ok") or int(runs[0].get("skipped") or 0)):
        return datetime.fromisoformat(runs[0]["since"])
    booked = [r.booked_at for r in guests.list_reservations(hotel_id) if r.booked_at]
    if booked:
        return max(booked) - timedelta(hours=1)
    return now - timedelta(days=30)


SESSION_KEY = "lighthouse_session"  # vroeger in RobotState; nu in de sessiekluis (core/session_vault.py)


def _session_secret(hotel_id: str) -> str:
    return f"{hotel_id}-lighthouse-session"


def _restore_session(hotel_id: str) -> None:
    """De container begint altijd leeg: de sessiecookies van Lighthouse van de vorige run terugzetten,
    zodat de robot niet bij elke run opnieuw aanmeldt (ongeveer 25 seconden per run). Is de sessie
    verlopen, dan meldt de robot gewoon opnieuw aan. Bewaard in de aparte sessiekluis (Key Vault)."""
    from hotel_checkin.core import session_vault
    from hotel_checkin.pms.lighthouse_browser import state_file

    if not session_vault.available():
        return  # codespace: het bestand blijft gewoon staan
    try:
        data = session_vault.get(_session_secret(hotel_id))
        path = state_file(hotel_id)
        if data and not path.exists():
            path.write_text(data)
    except Exception:
        logging.warning("%s: sessie van Lighthouse niet teruggezet", hotel_id, exc_info=True)


def _store_session(hotel_id: str) -> None:
    """Alleen de cookies bewaren (geen localStorage), zodat het in één geheim past. Alleen als ze
    veranderden (elke wijziging is een nieuwe versie van het geheim)."""
    import json

    from hotel_checkin.core import session_vault
    from hotel_checkin.pms.lighthouse_browser import state_file

    if not session_vault.available():
        return
    try:
        if guests.get_state(hotel_id, SESSION_KEY):  # eenmalig: oude kopie uit de tabel wissen
            guests.delete_state(hotel_id, SESSION_KEY)
        path = state_file(hotel_id)
        if not path.exists():
            return
        data = json.dumps({"cookies": json.loads(path.read_text()).get("cookies", []), "origins": []})
        if data != session_vault.get(_session_secret(hotel_id)) and not session_vault.put(_session_secret(hotel_id), data):
            logging.warning("%s: sessie van Lighthouse te groot om te bewaren", hotel_id)
    except Exception:
        logging.warning("%s: sessie van Lighthouse niet bewaard", hotel_id, exc_info=True)


def _check_due(hotel_id: str) -> str | None:
    """Is het tijd om opnieuw naar nieuwe reservaties te kijken voor dit hotel? None = ja, anders de reden
    waarom niet (voor het robotlog)."""
    if os.environ.get("ROBOT_MANUAL"):
        return None
    minutes = float(hotel_setting(hotel_id, "ROBOT_CHECK_MINUTES", default="60", shared=False))
    runs = [r for r in guests.robot_runs(hotel_id, task=new_reservation.TASK) if r.get("ok")]
    if not runs:
        return None
    last = datetime.fromisoformat(runs[0]["started_at"])
    # 2 minuten marge: een run op schema start nooit precies op dezelfde seconde
    if datetime.now(UTC) - last >= timedelta(minutes=minutes) - timedelta(minutes=2):
        return None
    from hotel_checkin.core import clock

    tz = clock.tz(hotel_id)
    nxt = last + timedelta(minutes=minutes) - timedelta(minutes=2)
    return (f"run op schema overgeslagen: vorige run om {last.astimezone(tz):%H:%M}, de robot kijkt om de "
            f"{minutes:g} minuten (instelling Robot: hoe vaak), volgende vanaf {nxt.astimezone(tz):%H:%M}")


SKIP_TASK = "robot"  # regel in het robotlog als een run niets doet (overgeslagen of al een andere bezig)
LOCK_KEY = "robot_running"
LOCK_MINUTES = 20  # een run duurt hoogstens 15 minuten (time-out van de job); ouder = vastgelopen


def _other_run(hotel_id: str, me: str) -> str | None:
    """Is er voor dit hotel al een andere run bezig? Geeft de uitleg terug, anders None (en dan is deze run
    nu de lopende)."""
    import json

    raw = guests.get_state(hotel_id, LOCK_KEY)
    if raw:
        try:
            other = json.loads(raw)
            started = datetime.fromisoformat(other["started"])
        except Exception:  # noqa: BLE001 - onleesbaar: negeren
            other, started = None, None
        if other and other.get("run") != me and datetime.now(UTC) - started < timedelta(minutes=LOCK_MINUTES):
            from hotel_checkin.core import clock

            return (f"run overgeslagen: een andere run ({other.get('run') or 'zonder naam'}) is nog bezig sinds "
                    f"{started.astimezone(clock.tz(hotel_id)):%H:%M}; die doet het werk")
    guests.set_state(hotel_id, LOCK_KEY, json.dumps({"run": me, "started": datetime.now(UTC).isoformat()}))
    return None


def _refresh_due(hotel_id: str) -> bool:
    """Is het tijd om de contactgegevens opnieuw na te lezen? Altijd als een melding erom vroeg."""
    from hotel_checkin.processes import refresh_requests

    if refresh_requests.requested(hotel_id):
        return True
    from hotel_checkin.core import clock, workflow
    from hotel_checkin.processes import booking_payout

    cfg, today = workflow.config(hotel_id), clock.today(hotel_id)
    from hotel_checkin.processes import pms_sync

    stored = guests.list_reservations(hotel_id)
    if any(booking_payout.candidate(r, cfg, today) or pms_sync.candidate(r) for r in stored):
        return True  # iets te schrijven in Lighthouse (overschrijving, pincode, status): niet wachten
    from hotel_checkin.processes import breakfast_labels

    if breakfast_labels.due(hotel_id, today):
        return True  # label ONTBIJT te zetten
    hours = float(hotel_setting(hotel_id, "ROBOT_CONTACT_REFRESH_HOURS", default="2", shared=False))
    runs = [r for r in guests.robot_runs(hotel_id, task=refresh_contacts.TASK) if r.get("ok")]
    if not runs:
        return True
    last = datetime.fromisoformat(runs[0]["started_at"])
    # 5 minuten marge, zodat een run op schema net na het uur niet een beurt overslaat
    return datetime.now(UTC) - last >= timedelta(hours=hours) - timedelta(minutes=5)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--hotel", default=os.environ.get("ROBOT_HOTEL") or None)
    p.add_argument("--hours", type=int, default=None)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from hotel_checkin.core import run_context

    run_context.start(PROCESS_STARTED, os.environ.get("CONTAINER_APP_JOB_EXECUTION_NAME", ""))
    logging.info("run %s: proces gestart, %.1f s voor de code klaar was",
                 os.environ.get("CONTAINER_APP_JOB_EXECUTION_NAME", "lokaal"), time.time() - PROCESS_STARTED)

    failed = False
    from hotel_checkin.core import progress

    for hotel_id in [args.hotel] if args.hotel else list_hotels():
        progress.step(hotel_id, SKIP_TASK, "robot gestart in Azure, check-in-formulieren nakijken", force=True)
        # Vangnet: ingevulde check-in-formulieren die niet in de reservatie staan, opnieuw toepassen.
        # Normaal gebeurt dat meteen bij het indienen; hier alleen nakijken (bij elke run, ook als vangnet-uur).
        try:
            from hotel_checkin.checkin import service as checkin_service

            fixed = checkin_service.reapply_forms(hotel_id)
            if fixed:
                logging.warning("%s: %d check-in-formulier(en) opnieuw toegepast", hotel_id, fixed)
        except Exception:
            logging.exception("%s: formulieren nakijken mislukt", hotel_id)
        me = os.environ.get("CONTAINER_APP_JOB_EXECUTION_NAME", "") or f"lokaal-{os.getpid()}"
        skip = (None if args.hours else _check_due(hotel_id)) or _other_run(hotel_id, me)
        if skip:
            logging.info("%s: %s", hotel_id, skip)
            guests.log_robot_run(hotel_id, SKIP_TASK, datetime.now(UTC), True, 0, 0, skip)
            if "andere run" not in skip:
                progress.done(hotel_id)  # de andere run houdt zijn eigen live regel
            continue
        progress.step(hotel_id, new_reservation.TASK, "aanmelden bij Lighthouse", force=True)
        since = _since(hotel_id, args.hours)
        _restore_session(hotel_id)
        try:
            new = new_reservation.run(hotel_id, since)
            logging.info("%s: %s nieuwe reservaties", hotel_id, new)
            # Gasten synchroniseren: één keer per dag mee in een run die toch al draait (geen eigen schema)
            if maintenance.due(hotel_id):
                progress.step(hotel_id, maintenance.TASK, "gasten synchroniseren en oude gegevens opruimen")
                maintenance.run(hotel_id)
            if _refresh_due(hotel_id):
                found = refresh_contacts.run(hotel_id)
                logging.info("%s: %s e-mailadressen gevonden bij nalezen", hotel_id, found)
            # Log van de robot opruimen (standaard 30 dagen, instelling ROBOT_LOG_DAYS)
            progress.step(hotel_id, SKIP_TASK, "afronden: robotlog opruimen, sessie van Lighthouse bewaren", force=True)
            guests.prune_robot_runs(hotel_id, int(os.environ.get("ROBOT_LOG_DAYS") or 30))
        except Exception:
            logging.exception("%s: robot mislukt", hotel_id)
            failed = True
        finally:
            _store_session(hotel_id)
            guests.delete_state(hotel_id, LOCK_KEY)  # deze run is klaar
            progress.finish(hotel_id, "klaar met een fout, zie het robotlog; Azure sluit de robot af" if failed
                            else "klaar: alle taken gedaan, Azure sluit de robot af")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
