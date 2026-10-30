"""Lokale testserver voor het check-in-formulier en de opvolgpagina, zonder Azure.

Start in de codespace:
    python -m hotel_checkin.checkin.devserver

Open daarna de link die verschijnt (Codespaces stuurt poort 8080 door).
Opvolgpagina: /monitor/ (lokaal zonder login; de knop "Robot nu draaien" leest Lighthouse, alleen lezen).
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

from hotel_checkin.admin import service as admin
from hotel_checkin.checkin import service
from hotel_checkin.core.models import Guest, Reservation, ReservationStatus
from hotel_checkin.guests import repository as repo

ROOT_WEB = Path(__file__).resolve().parents[3] / "web"
WEB = ROOT_WEB / "checkin"
ADMIN_WEB = ROOT_WEB / "admin"
PORT = 8080


def seed() -> None:
    today = date.today()
    repo.save_reservation(Reservation(
        hotel_id="lucca", reservation_id="DEMO-1", token="demo",
        guest=Guest("Anna", "Peeters", "anna@example.com", None, "nl", country="BE"),
        arrival=today + timedelta(days=14), departure=today + timedelta(days=16),
        room_type="Superior Double", source="Booking.com"))
    repo.save_reservation(Reservation(
        hotel_id="lucca", reservation_id="DEMO-3", token="nieuw",
        guest=Guest("Klaus", "Becker", None, None, "de", country="DE"),
        arrival=today + timedelta(days=30), departure=today + timedelta(days=33),
        room_type="Historical Suite", source="Expedia"))
    repo.save_reservation(Reservation(
        hotel_id="lucca", reservation_id="DEMO-2", token="annule", status=ReservationStatus.CANCELLED,
        guest=Guest("Pierre", "Dubois", "pierre@example.com", None, "fr", country="FR"),
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

    def _admin_api(self, method: str, path: str) -> bool:
        parts = path.strip("/").split("/")  # api monitor <hotel> <wat>
        if parts[:2] != ["api", "monitor"]:
            return False
        if method == "GET" and parts[2:] == ["hotels"]:
            self._json(200, admin.hotels())
        elif method == "GET" and len(parts) == 4 and parts[3] == "reservations":
            self._json(200, admin.reservations(parts[2]))
        elif method == "GET" and len(parts) == 4 and parts[3] == "runs":
            self._json(200, admin.runs(parts[2]) | {"can_run": True})
        elif method == "POST" and len(parts) == 4 and parts[3] == "run":
            hours = int((self.path.split("hours=") + ["48"])[1].split("&")[0] or 48)
            self._json(200, {"started": admin.start_robot(parts[2], hours)})
        elif method == "DELETE" and len(parts) == 4 and parts[3] == "runs":
            run_id = (self.path.split("id=") + [""])[1].split("&")[0]
            self._json(200, {"deleted": admin.delete_run(parts[2], run_id)})
        else:
            self._send(404, b"Not found", "text/plain")
        return True

    def _file(self, base: Path, rel: str) -> None:
        file = base / (rel or "index.html")
        if not file.resolve().is_relative_to(base) or not file.is_file():
            return self._send(404, b"Not found", "text/plain")
        self._send(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")

    def do_GET(self):
        path = self.path.split("?")[0]
        if self._admin_api("GET", path):
            return None
        if path == "/monitor":
            self.send_response(302)
            self.send_header("Location", "/monitor/")
            self.end_headers()
            return None
        if path.startswith("/monitor/"):
            return self._file(ADMIN_WEB, path[len("/monitor/"):])
        if path.startswith("/api/checkin/"):
            data = service.form_data(path.rsplit("/", 1)[1])
            return self._json(200, data) if data else self._json(404, {"error": "not_found"})
        return self._file(WEB, path.lstrip("/"))

    def do_DELETE(self):
        if not self._admin_api("DELETE", self.path.split("?")[0]):
            self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        path = self.path.split("?")[0]
        if self._admin_api("POST", path):
            return None
        if not path.startswith("/api/checkin/"):
            return self._send(404, b"Not found", "text/plain")
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self._json(400, {"ok": False, "errors": {"body": "invalid"}})
        if not isinstance(payload, dict):
            return self._json(400, {"ok": False, "errors": {"body": "invalid"}})
        ok, errors = service.submit(path.rsplit("/", 1)[1], payload)
        self._json(200 if ok else 400, {"ok": ok, "errors": errors})


if __name__ == "__main__":
    if "--azure" not in sys.argv:
        repo.use_memory_store()
        seed()
    print(f"Check-in-formulier: http://localhost:{PORT}/?r=demo")
    print(f"Gast zonder gekende contactgegevens: http://localhost:{PORT}/?r=nieuw")
    print(f"Geannuleerde reservatie: http://localhost:{PORT}/?r=annule")
    print(f"Ongeldige link: http://localhost:{PORT}/?r=fout")
    print(f"Opvolgpagina: http://localhost:{PORT}/monitor/")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
