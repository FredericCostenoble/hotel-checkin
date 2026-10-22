"""Lokale testserver voor het check-in-formulier, zonder Azure.

Start in de codespace:
    python -m hotel_checkin.checkin.devserver

Open daarna de link die verschijnt (Codespaces stuurt poort 8080 door).
De opslag zit in het geheugen met twee voorbeeldreservaties; alles verdwijnt bij het stoppen.
Wil je tegen de echte opslag testen: start met --azure (gebruikt STORAGE_TABLE_ENDPOINT).
"""

from __future__ import annotations

import json
import mimetypes
import sys
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from hotel_checkin.checkin import service
from hotel_checkin.core.models import Guest, Reservation, ReservationStatus
from hotel_checkin.guests import repository as repo

WEB = Path(__file__).resolve().parents[3] / "web" / "checkin"
PORT = 8080


def seed() -> None:
    today = date.today()
    repo.save_reservation(Reservation(
        reservation_id="DEMO-1", token="demo",
        guest=Guest("Anna", "Peeters", "anna@example.com", None, "nl"),
        arrival=today + timedelta(days=14), departure=today + timedelta(days=16),
        room_type="Superior Double", source="Booking.com"))
    repo.save_reservation(Reservation(
        reservation_id="DEMO-2", token="annule", status=ReservationStatus.CANCELLED,
        guest=Guest("Pierre", "Dubois", "pierre@example.com", None, "fr"),
        arrival=today + timedelta(days=3), departure=today + timedelta(days=5)))


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj) -> None:
        self._send(status, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/checkin/"):
            data = service.form_data(path.rsplit("/", 1)[1])
            return self._json(200, data) if data else self._json(404, {"error": "not_found"})
        file = WEB / ("index.html" if path in ("", "/") else path.lstrip("/"))
        if not file.resolve().is_relative_to(WEB) or not file.is_file():
            return self._send(404, b"Not found", "text/plain")
        self._send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")

    def do_POST(self):
        path = self.path.split("?")[0]
        if not path.startswith("/api/checkin/"):
            return self._send(404, b"Not found", "text/plain")
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self._json(400, {"ok": False, "errors": {"body": "invalid"}})
        ok, errors = service.submit(
            path.rsplit("/", 1)[1], str(payload.get("email", "")), str(payload.get("phone", "")),
            str(payload.get("language", "")), bool(payload.get("no_marketing", False)))
        self._json(200 if ok else 400, {"ok": ok, "errors": errors})


if __name__ == "__main__":
    if "--azure" not in sys.argv:
        repo.use_memory_store()
        seed()
    print(f"Check-in-formulier: http://localhost:{PORT}/?r=demo")
    print(f"Geannuleerde reservatie: http://localhost:{PORT}/?r=annule")
    print(f"Ongeldige link: http://localhost:{PORT}/?r=fout")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
