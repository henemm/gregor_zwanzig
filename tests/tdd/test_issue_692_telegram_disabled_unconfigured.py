"""
TDD RED — Issue #692: Telegram/SMS auswählbar ohne Konfiguration

Spec: docs/specs/modules/issue_692_telegram_disabled_unconfigured.md

Verhaltenstests via Playwright gegen Staging:
- AC-1: Nutzer ohne telegram_chat_id öffnet WeatherMetricsTab "04 — Kanäle"
        → data-testid="channel-telegram-hint" sichtbar, Toggle-Button disabled
- AC-2: Nutzer MIT telegram_chat_id → kein Hint, Toggle funktioniert
- AC-4: Nutzer ohne jegliche Kanal-Konfiguration → alle drei Hints sichtbar
- AC-5: Gespeicherte channels-Werte überleben einen Roundtrip (Persistenz)

RED-Ursache:
- WeatherV2Kanaele.svelte hat kein availability-Prop → keine Hints, kein disabled
- WeatherMetricsTab.svelte lädt kein Profil → kann availability nicht berechnen

Staging-URL: https://staging.gregor20.henemm.com (GZ_SVELTE_BASE)
API (inkl. Auth): über dieselbe Staging-URL (SvelteKit-Proxy auf Go-API)

KEINE MOCKS. Echte HTTP-Calls gegen Staging + Playwright-Browser.
"""

from __future__ import annotations

import os
import re
import time
import uuid

import httpx
import pytest

from tests.helpers.staging_auth import (  # Bündel H #987: Staging-Basic-Auth
    httpx_auth,
    playwright_http_credentials,
)

# Dialt real gegen Staging/Prod (#1211 Scheibe 2a) -- nur via -m staging ausfuehren.
pytestmark = pytest.mark.staging

STAGING = os.environ.get("GZ_SVELTE_BASE", "https://staging.gregor20.henemm.com")
API = STAGING  # Go-API läuft hinter SvelteKit-Proxy auf /api/

# Feste Test-User für dieses Issue (idempotent anlegen)
USER_NO_TG = "tdd-692-notelegram"
USER_WITH_TG = "tdd-692-withtelegram"
TEST_PASS = "tdd692testpass"
FAKE_TG_CHAT_ID = "999888777"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_user(username: str, password: str) -> None:
    """Legt den Testnutzer auf Staging an (idempotent, ignoriert 409)."""
    resp = httpx.post(
        f"{API}/api/auth/register",
        json={"username": username, "password": password},
        auth=httpx_auth(),
        timeout=15,
    )
    assert resp.status_code in (201, 409, 429), (
        f"Register {username!r} fehlgeschlagen: {resp.status_code} {resp.text[:200]}"
    )


def _login(username: str, password: str) -> httpx.Client:
    """Gibt einen authentifizierten httpx-Client zurück."""
    client = httpx.Client(
        base_url=API, timeout=15, follow_redirects=True, auth=httpx_auth()
    )
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        pytest.skip(f"Login {username!r} fehlgeschlagen ({resp.status_code}) — Staging nicht erreichbar")
    sc = resp.headers.get("set-cookie", "")
    m = re.search(r"gz_session=([^;]+)", sc)
    if m:
        client.cookies.set("gz_session", m.group(1))
    return client


def _set_telegram(client: httpx.Client, chat_id: str | None) -> None:
    """Setzt oder löscht telegram_chat_id im Profil."""
    payload: dict = {"telegram_chat_id": chat_id if chat_id else ""}
    resp = client.put("/api/auth/profile", json=payload)
    assert resp.status_code == 200, f"Profil-Update fehlgeschlagen: {resp.status_code} {resp.text[:200]}"


def _create_trip(client: httpx.Client, trip_id: str) -> str:
    """Legt einen Minimal-Trip an und gibt die trip_id zurück."""
    payload = {
        "id": trip_id,
        "name": f"692-Test-{trip_id[-6:]}",
        "region": "Testgebiet",
        "stages": [
            {
                "id": "s1",
                "name": "Etappe 1",
                "date": "2026-08-01",
                "start_time": "08:00",
                "waypoints": [
                    {"id": "w1", "name": "Start", "lat": 42.0, "lon": 9.0, "elevation_m": 200},
                    {"id": "w2", "name": "Ziel", "lat": 42.1, "lon": 9.0, "elevation_m": 250},
                ],
            }
        ],
        "alert_rules": [],
        "display_config": {
            "channels": {"email": True, "telegram": True, "sms": False},
            "metrics": [],
        },
    }
    resp = client.post("/api/trips", json=payload)
    assert resp.status_code in (200, 201), (
        f"Trip anlegen fehlgeschlagen: {resp.status_code} {resp.text[:200]}"
    )
    return trip_id


def _login_playwright(page, username: str, password: str) -> None:
    """Login über Playwright-Browser auf Staging."""
    page.goto(f"{STAGING}/login", wait_until="networkidle")
    time.sleep(1)
    page.fill("input[name='username']", username)
    page.fill("input[type='password']", password)
    page.click("button[type='submit']")
    page.wait_for_url(
        re.compile(rf"^{re.escape(STAGING)}(?!/login)"),
        timeout=20_000,
    )


# ---------------------------------------------------------------------------
# Setup: Testnutzer anlegen (einmalig für Session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def ensure_test_users():
    """Legt beide Testnutzer idempotent an."""
    try:
        _ensure_user(USER_NO_TG, TEST_PASS)
        _ensure_user(USER_WITH_TG, TEST_PASS)
    except httpx.ConnectError:
        pytest.skip("Staging nicht erreichbar — Tests übersprungen")


@pytest.fixture(scope="module")
def trip_id_no_tg() -> str:
    """Trip-ID für den Nutzer ohne Telegram."""
    client = _login(USER_NO_TG, TEST_PASS)
    # Profil: kein Telegram, keine E-Mail, kein SMS
    _set_telegram(client, None)
    t_id = f"tdd-692-no-{uuid.uuid4().hex[:6]}"
    return _create_trip(client, t_id)


@pytest.fixture(scope="module")
def trip_id_with_tg() -> str:
    """Trip-ID für den Nutzer MIT Telegram."""
    client = _login(USER_WITH_TG, TEST_PASS)
    _set_telegram(client, FAKE_TG_CHAT_ID)
    t_id = f"tdd-692-tg-{uuid.uuid4().hex[:6]}"
    return _create_trip(client, t_id)


# ---------------------------------------------------------------------------
# AC-1: Nutzer OHNE Telegram → Hint sichtbar, Toggle disabled
# ---------------------------------------------------------------------------

class TestAC1TelegramHintForUnconfiguredUser:
    """
    GIVEN: Nutzer hat keine telegram_chat_id in seinem Profil
    WHEN:  Er öffnet einen Trip → Tab "Wetter-Metriken" (04 — Kanäle)
    THEN:  data-testid="channel-telegram-hint" ist sichtbar
           Toggle-Button für Telegram hat disabled-Attribut
    """

    def test_telegram_hint_visible_in_wm2_kanaele(self, trip_id_no_tg: str) -> None:
        """AC-1: channel-telegram-hint muss in WeatherV2Kanaele sichtbar sein."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip("playwright nicht installiert")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                http_credentials=playwright_http_credentials(),
            )
            page = ctx.new_page()
            try:
                _login_playwright(page, USER_NO_TG, TEST_PASS)

                # Navigiere zum Trip, direkt zum Wetter-Tab
                page.goto(f"{STAGING}/trips/{trip_id_no_tg}?tab=weather", wait_until="networkidle")
                time.sleep(2)

                # WeatherV2Kanaele-Container muss vorhanden sein
                kanaele = page.locator('[data-testid="wm2-kanaele"]')
                kanaele.wait_for(timeout=10_000)

                # AC-1: Telegram-Hint muss sichtbar sein
                hint = kanaele.locator('[data-testid="channel-telegram-hint"]')
                assert hint.is_visible(), (
                    "RED: data-testid='channel-telegram-hint' ist NICHT sichtbar in "
                    "wm2-kanaele, obwohl Nutzer keine telegram_chat_id hat. "
                    "WeatherV2Kanaele.svelte muss availability-Prop + Hint implementieren."
                )
            finally:
                browser.close()

    def test_telegram_toggle_is_disabled_for_unconfigured_user(self, trip_id_no_tg: str) -> None:
        """AC-1: Telegram-Toggle-Button muss disabled sein wenn kein Chat-ID konfiguriert."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip("playwright nicht installiert")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                http_credentials=playwright_http_credentials(),
            )
            page = ctx.new_page()
            try:
                _login_playwright(page, USER_NO_TG, TEST_PASS)
                page.goto(f"{STAGING}/trips/{trip_id_no_tg}?tab=weather", wait_until="networkidle")
                time.sleep(2)

                kanaele = page.locator('[data-testid="wm2-kanaele"]')
                kanaele.wait_for(timeout=10_000)

                # Telegram-Karte: button[data-channel="telegram"] muss disabled sein
                tg_btn = kanaele.locator('[data-channel="telegram"] button').first
                assert tg_btn.is_disabled(), (
                    "RED: Telegram-Toggle-Button ist NICHT disabled, obwohl keine "
                    "telegram_chat_id konfiguriert. WeatherV2Kanaele muss disabled="
                    "!(availability?.telegram ?? true) setzen."
                )
            finally:
                browser.close()


# ---------------------------------------------------------------------------
# AC-2: Nutzer MIT Telegram → kein Hint, Toggle klickbar
# ---------------------------------------------------------------------------

class TestAC2TelegramActiveForConfiguredUser:
    """
    GIVEN: Nutzer hat telegram_chat_id gesetzt
    WHEN:  Er öffnet den Wetter-Tab → 04 — Kanäle
    THEN:  Kein channel-telegram-hint sichtbar, Toggle funktioniert
    """

    def test_no_telegram_hint_when_configured(self, trip_id_with_tg: str) -> None:
        """AC-2: Kein Hint wenn Telegram konfiguriert ist."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip("playwright nicht installiert")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                http_credentials=playwright_http_credentials(),
            )
            page = ctx.new_page()
            try:
                _login_playwright(page, USER_WITH_TG, TEST_PASS)
                page.goto(f"{STAGING}/trips/{trip_id_with_tg}?tab=weather", wait_until="networkidle")
                time.sleep(2)

                kanaele = page.locator('[data-testid="wm2-kanaele"]')
                kanaele.wait_for(timeout=10_000)

                # Kein Hint sichtbar
                hint_count = kanaele.locator('[data-testid="channel-telegram-hint"]').count()
                assert hint_count == 0, (
                    f"AC-2: channel-telegram-hint sollte NICHT erscheinen bei "
                    f"konfiguriertem Telegram (chat_id={FAKE_TG_CHAT_ID}). "
                    f"Gefunden: {hint_count} Elemente."
                )

                # Toggle-Button nicht disabled
                tg_btn = kanaele.locator('[data-channel="telegram"] button').first
                assert not tg_btn.is_disabled(), (
                    "AC-2: Telegram-Toggle muss für konfigurierten Nutzer klickbar sein."
                )
            finally:
                browser.close()


# ---------------------------------------------------------------------------
# AC-4: Nutzer ohne jede Konfiguration → alle drei Hints sichtbar
# ---------------------------------------------------------------------------

class TestAC4AllChannelsUnconfigured:
    """
    GIVEN: Nutzer hat weder mail_to noch sms_to noch telegram_chat_id
    WHEN:  Er öffnet 04 — Kanäle
    THEN:  Alle drei Hints sichtbar, keine Überlappung mit kurzform-row
    """

    def test_all_three_hints_visible(self, trip_id_no_tg: str) -> None:
        """AC-4: Alle drei channel-{email,telegram,sms}-hint sichtbar."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip("playwright nicht installiert")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                http_credentials=playwright_http_credentials(),
            )
            page = ctx.new_page()
            try:
                _login_playwright(page, USER_NO_TG, TEST_PASS)
                page.goto(f"{STAGING}/trips/{trip_id_no_tg}?tab=weather", wait_until="networkidle")
                time.sleep(2)

                kanaele = page.locator('[data-testid="wm2-kanaele"]')
                kanaele.wait_for(timeout=10_000)

                missing: list[str] = []
                for channel in ("email", "telegram", "sms"):
                    hint = kanaele.locator(f'[data-testid="channel-{channel}-hint"]')
                    if not hint.is_visible():
                        missing.append(channel)

                assert not missing, (
                    f"RED: Hints für {missing} fehlen in wm2-kanaele. "
                    f"Alle drei Kanäle müssen Hints zeigen wenn kein Kanal konfiguriert. "
                    f"WeatherV2Kanaele.svelte muss availability-Prop + bedingte Hints implementieren."
                )
            finally:
                browser.close()

    def test_telegram_kurzform_row_not_shown_when_telegram_disabled(self, trip_id_no_tg: str) -> None:
        """AC-4: Telegram-Kurzform-Row darf nicht erscheinen wenn Telegram disabled."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip("playwright nicht installiert")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                http_credentials=playwright_http_credentials(),
            )
            page = ctx.new_page()
            try:
                _login_playwright(page, USER_NO_TG, TEST_PASS)
                page.goto(f"{STAGING}/trips/{trip_id_no_tg}?tab=weather", wait_until="networkidle")
                time.sleep(2)

                kanaele = page.locator('[data-testid="wm2-kanaele"]')
                kanaele.wait_for(timeout=10_000)

                # .kurzform-row darf nicht im DOM sichtbar sein
                kurzform = kanaele.locator(".kurzform-row")
                assert not kurzform.is_visible(), (
                    "AC-4: .kurzform-row ist sichtbar obwohl Telegram disabled (unconfigured). "
                    "Kurzform-Row darf nur erscheinen wenn Telegram aktiviert UND konfiguriert."
                )
            finally:
                browser.close()


# ---------------------------------------------------------------------------
# AC-5: Channels-Roundtrip (Persistenz-Regression)
# ---------------------------------------------------------------------------

class TestAC5ChannelsPersistenceRoundtrip:
    """
    GIVEN: Trip mit gespeichertem channels={email:true, telegram:true, sms:false}
    WHEN:  Trip neu geladen (GET /api/trips/{id})
    THEN:  channels-Werte byte-identisch erhalten — kein stiller Reset durch das Sperren
    """

    def test_channels_survive_save_load_roundtrip(self) -> None:
        """AC-5: channels.telegram=true bleibt nach GET erhalten (kein Reset durch Darstellung)."""
        try:
            client = _login(USER_NO_TG, TEST_PASS)
        except Exception:
            pytest.skip("Staging nicht erreichbar")

        trip_id = f"tdd-692-rt-{uuid.uuid4().hex[:6]}"
        saved_channels = {"email": True, "telegram": True, "sms": False}

        # Anlegen mit explizitem channels-Wert
        payload = {
            "id": trip_id,
            "name": f"692-Roundtrip-{trip_id[-6:]}",
            "region": "Test",
            "stages": [
                {
                    "id": "s1",
                    "name": "Etappe 1",
                    "date": "2026-08-01",
                    "start_time": "08:00",
                    "waypoints": [
                        {"id": "w1", "name": "A", "lat": 42.0, "lon": 9.0, "elevation_m": 200},
                        {"id": "w2", "name": "B", "lat": 42.1, "lon": 9.0, "elevation_m": 250},
                    ],
                }
            ],
            "alert_rules": [],
            "display_config": {"channels": saved_channels, "metrics": []},
        }
        resp = client.post("/api/trips", json=payload)
        assert resp.status_code in (200, 201), f"Create fehlgeschlagen: {resp.status_code}"

        # PUT (Speichern) mit denselben channels
        put_resp = client.put(f"/api/trips/{trip_id}", json=payload)
        assert put_resp.status_code == 200, f"PUT fehlgeschlagen: {put_resp.status_code}"

        # GET → channels müssen erhalten sein
        get_resp = client.get(f"/api/trips/{trip_id}")
        assert get_resp.status_code == 200
        loaded = get_resp.json()

        loaded_channels = loaded.get("display_config", {}).get("channels", {})
        for ch, expected in saved_channels.items():
            actual = loaded_channels.get(ch)
            assert actual == expected, (
                f"AC-5: channels.{ch} wurde durch Roundtrip von {expected!r} auf {actual!r} "
                f"geändert — stille Mutation beim Speichern/Laden verboten."
            )
