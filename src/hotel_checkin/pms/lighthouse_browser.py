"""Browsersessie voor Lighthouse (Reservation Manager), per hotel.

Aanmelden met een eigen robotgebruiker per hotel (zonder MFA):
    gebruikersnaam: instelling <HOTEL>_LIGHTHOUSE_USERNAME  (Key Vault: <hotel>-lighthouse-username)
    wachtwoord:     instelling <HOTEL>_LIGHTHOUSE_PASSWORD  (Key Vault: <hotel>-lighthouse-password)
    adres:          config/hotels/<hotel_id>.toml, [lighthouse] base_url

Afspraken:
- Pagina's altijd volledig laten laden (folio en transacties laden asynchroon).
- Sessiecookies worden bewaard tussen runs, zodat niet elke keer opnieuw aangemeld wordt.
- Dit bestand leest alleen. Schrijven in Lighthouse gebeurt enkel in PRD (zie lighthouse.py).
"""

from __future__ import annotations

import os
from pathlib import Path

from hotel_checkin.core.config import hotel_setting

DEFAULT_BASE_URL = "https://reservationmanager.mylighthouse.com"
TIMEOUT_MS = 60_000


def _state_dir() -> Path:
    d = Path(os.environ.get("LIGHTHOUSE_STATE_DIR", Path.home() / ".hotel-checkin"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def credentials(hotel_id: str) -> tuple[str, str]:
    """Altijd de eigen robotgebruiker van het hotel, nooit een gedeelde waarde."""
    return (
        hotel_setting(hotel_id, "LIGHTHOUSE_USERNAME", shared=False),
        hotel_setting(hotel_id, "LIGHTHOUSE_PASSWORD", shared=False),
    )


def base_url(hotel_id: str) -> str:
    return hotel_setting(hotel_id, "LIGHTHOUSE_BASE_URL", default=DEFAULT_BASE_URL).rstrip("/")


class LighthouseSession:
    """Gebruik:
        with LighthouseSession("lucca") as lh:
            page = lh.goto("/Customer/Dashboard")
    """

    def __init__(self, hotel_id: str, headless: bool = True, debug_dir: Path | None = None):
        self.hotel_id = hotel_id
        self.base = base_url(hotel_id)
        self.headless = headless
        self.debug_dir = debug_dir
        self.state_file = _state_dir() / f"lighthouse-{hotel_id}.json"
        self._pw = self._browser = self._context = self.page = None

    def __enter__(self) -> "LighthouseSession":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        state = str(self.state_file) if self.state_file.exists() else None
        self._context = self._browser.new_context(
            storage_state=state, locale="nl-BE", viewport={"width": 1600, "height": 1000}
        )
        self._context.set_default_timeout(TIMEOUT_MS)
        self.page = self._context.new_page()
        self.login()
        return self

    def __exit__(self, *exc) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _snap(self, name: str) -> None:
        if self.debug_dir:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(self.debug_dir / f"{name}.png"), full_page=True)

    def _wait_loaded(self) -> None:
        self.page.wait_for_load_state("load")
        try:
            self.page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception:  # noqa: BLE001 - sommige pagina's blijven pollen
            pass

    def _on_login_page(self) -> bool:
        return self.page.locator("input[type=password]").count() > 0 or "/Customer/" not in self.page.url

    def login(self) -> None:
        """Meld aan als de bewaarde sessie niet meer geldig is."""
        page = self.page
        page.goto(self.base + "/Customer/Dashboard")
        self._wait_loaded()
        if not self._on_login_page():
            return
        self._snap("01-login")
        user, password = credentials(self.hotel_id)

        user_field = page.locator(
            "input[type=email], input[name*=user i], input[name*=email i], input[id*=user i], input[id*=email i]"
        ).first
        user_field.fill(user)
        password_field = page.locator("input[type=password]").first
        if not password_field.is_visible():
            # Login in twee stappen: eerst gebruikersnaam, dan wachtwoord
            page.keyboard.press("Enter")
            password_field.wait_for(state="visible")
            self._snap("02-wachtwoord")
        password_field.fill(password)
        page.keyboard.press("Enter")

        page.wait_for_url("**/Customer/**")
        self._wait_loaded()
        self._snap("03-aangemeld")
        self._context.storage_state(path=str(self.state_file))

    def goto(self, path: str):
        """Open een pagina en wacht tot ze volledig geladen is."""
        self.page.goto(self.base + path)
        self._wait_loaded()
        if self._on_login_page():
            self.login()
            self.page.goto(self.base + path)
            self._wait_loaded()
        return self.page
