"""Browsersessie voor Lighthouse (Reservation Manager), per hotel.

Aanmelden met een eigen robotgebruiker per hotel (zonder MFA):
    gebruikersnaam: instelling <HOTEL>_LIGHTHOUSE_USERNAME  (Key Vault: <hotel>-lighthouse-username)
    wachtwoord:     instelling <HOTEL>_LIGHTHOUSE_PASSWORD  (Key Vault: <hotel>-lighthouse-password)
    adres:          config/hotels/<hotel_id>.toml, [lighthouse] base_url

Afspraken:
- Pagina's altijd volledig laten laden (folio en transacties laden asynchroon). Niet wachten op
  "netwerk stil": Lighthouse blijft op de achtergrond verversen, dus dat wordt nooit stil en kost
  telkens de volle wachttijd. Wel nagaan of wat we nodig hebben er staat (wachtwoordveld, aangemelde
  pagina, rijen in de lijst, ingevulde transacties): goto(path, ready=<voorwaarde in JavaScript>).
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


def state_file(hotel_id: str) -> Path:
    """Bestand met de sessiecookies van dit hotel (Playwright storage_state)."""
    return _state_dir() / f"lighthouse-{hotel_id}.json"


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
        self.state_file = state_file(hotel_id)
        self._pw = self._browser = self._context = self.page = None
        # Gemeten duur (seconden) voor de monitor: browser starten, aanmelden, sessie hergebruikt (1) of niet (0)
        self.timings: dict[str, float] = {}

    def __enter__(self) -> LighthouseSession:
        import time

        from playwright.sync_api import sync_playwright

        t0 = time.monotonic()
        self._pw = sync_playwright().start()
        # In een container is /dev/shm klein (64 MB): zonder deze vlag crasht het tabblad na veel pagina's
        self._browser = self._pw.chromium.launch(headless=self.headless,
                                                 args=["--disable-dev-shm-usage", "--disable-gpu"])
        state = str(self.state_file) if self.state_file.exists() else None
        self._context = self._browser.new_context(
            storage_state=state, locale="nl-BE", viewport={"width": 1600, "height": 1000}
        )
        self._context.set_default_timeout(TIMEOUT_MS)
        self.page = self._context.new_page()
        self.timings["browser"] = round(time.monotonic() - t0, 1)
        t0 = time.monotonic()
        self.login()
        self.timings["login"] = round(time.monotonic() - t0, 1)
        return self

    def __exit__(self, *exc) -> None:
        if self._context:
            try:  # vernieuwde cookies bewaren voor de volgende run
                self._context.storage_state(path=str(self.state_file))
            except Exception:  # noqa: BLE001 - dan meldt de volgende run opnieuw aan
                pass
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _snap(self, name: str) -> None:
        if self.debug_dir:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(self.debug_dir / f"{name}.png"), full_page=True)

    def _wait_loaded(self, ready: str | None = None, timeout: int = 20_000, arg=None) -> bool:
        """Wacht tot de pagina geladen is. Met ready (JavaScript-voorwaarde): tot die waar is, dus tot wat
        we nodig hebben er echt staat. Zonder: tot het netwerk stil is (max. timeout), als vangnet voor
        pagina's zonder gekende voorwaarde. False als de voorwaarde niet binnen de tijd waar werd."""
        self.page.wait_for_load_state("load")
        try:
            if ready:
                self.page.wait_for_function(ready, arg=arg, timeout=timeout)
            else:
                self.page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except Exception:  # noqa: BLE001 - dan verder met wat er is
            return False

    def _on_login_page(self) -> bool:
        return self.page.locator("input[type=password]").count() > 0 or "/Customer/" not in self.page.url

    def login(self) -> None:
        """Meld aan als de bewaarde sessie niet meer geldig is."""
        page = self.page
        page.goto(self.base + "/Customer/Dashboard")  # wacht tot "load": daarna is meteen duidelijk waar we zijn
        if not self._on_login_page():
            self.timings["session"] = 1  # bewaarde sessie nog geldig
            return
        self.timings["session"] = 0
        self._snap("01-login")
        try:
            self._fill_login()
        except Exception:
            self._snap("99-fout")
            raise
        self._snap("04-aangemeld")
        self._context.storage_state(path=str(self.state_file))

    def _fill_login(self) -> None:
        page = self.page
        user, password = credentials(self.hotel_id)

        # Stardekk-pagina: eerst doorklikken naar de login van Lighthouse
        sso = page.locator("a.lighthouse-login-flow, a:has-text('Lighthouse account')").first
        if sso.count():
            sso.click()
            page.wait_for_load_state("load")  # het veld hieronder wacht zelf tot het zichtbaar is
            self._snap("02-lighthouse-login")

        user_field = page.locator(
            "input[type=email]:visible, input[autocomplete=username]:visible, "
            "input[name*=user i]:visible, input[name*=email i]:visible, "
            "input[id*=user i]:visible, input[id*=email i]:visible, input[type=text]:visible"
        ).first
        user_field.fill(user)
        password_field = page.locator("input[type=password]").first
        if not password_field.is_visible():
            # Login in twee stappen: eerst gebruikersnaam, dan wachtwoord
            page.keyboard.press("Enter")
            password_field.wait_for(state="visible")
            self._snap("03-wachtwoord")
        password_field.fill(password)
        page.keyboard.press("Enter")

        page.wait_for_url("**/Customer/**")  # aangemeld zodra Lighthouse de klantpagina geladen heeft

    def close_popups(self) -> None:
        """Sluit pop-ups die Lighthouse vanzelf opent (bv. de interne memo). Wijzigt niets."""
        page = self.page
        for _ in range(3):
            modal = page.locator(".modal.in, .modal.show").first
            if not modal.count() or not modal.is_visible():
                return
            close = modal.locator("button.close, [data-dismiss='modal'], button:has-text('Sluiten'), button:has-text('Close')").first
            if close.count():
                close.click()
            else:
                page.keyboard.press("Escape")
            page.wait_for_timeout(500)

    RECYCLE_AFTER = 40  # na zoveel pagina's een vers tabblad (geheugen blijft laag)

    def _fresh_page(self) -> None:
        """Nieuw tabblad in dezelfde sessie (cookies blijven): na een crash, of om de zoveel pagina's."""
        old = self.page
        self.page = self._context.new_page()
        self._pages = 0
        try:
            old.close()
        except Exception:  # noqa: BLE001 - al gecrasht of gesloten
            pass

    def goto(self, path: str, ready: str | None = None, timeout: int = 20_000):
        """Open een pagina en wacht tot ze geladen is (ready: zie _wait_loaded). Crasht het tabblad, dan
        één keer opnieuw in een vers tabblad; om de RECYCLE_AFTER pagina's sowieso een vers tabblad."""
        self._pages = getattr(self, "_pages", 0) + 1
        if self._pages > self.RECYCLE_AFTER or self.page.is_closed():
            self._fresh_page()
        try:
            self.page.goto(self.base + path)
        except Exception as exc:
            if "crash" not in str(exc).lower() and "closed" not in str(exc).lower():
                raise
            self._fresh_page()
            self.page.goto(self.base + path)
        if self._on_login_page():
            self.login()
            self.page.goto(self.base + path)
        self._wait_loaded(ready, timeout)
        return self.page
