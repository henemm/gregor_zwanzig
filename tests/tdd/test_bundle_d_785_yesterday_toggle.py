"""
TDD RED — Bundle D: Issues #785 + #709
show_yesterday_comparison Checkbox in EditReportConfigSection.svelte

Spec: docs/specs/modules/bundle_d_mail_ui_schalter.md

RED-Erwartung:
  - AC-1: data-testid="report-show-yesterday-comparison" fehlt → TimeoutError
  - AC-2: Checkbox-Abwahl nicht möglich → API-Feld bleibt true
  - AC-4: Legacy-Trip ohne Feld → kein Checkbox-Element sichtbar → TimeoutError
  - AC-5: Kompakt-Modus → kein disabled-Attribut (Element fehlt) → TimeoutError

Ausführung:
    uv run pytest tests/tdd/test_bundle_d_785_yesterday_toggle.py -v
"""
import json
import os

import httpx
import pytest
from playwright.sync_api import sync_playwright

BASE = "https://staging.gregor20.henemm.com"
USER = "tdd-785-ac"
PASS = "tdd785testpass"
TRIP_ID_OFF = "tdd-785-trip1"     # show_yesterday_comparison = false
TRIP_ID_LEGACY = "tdd-785-legacy"  # kein Feld im report_config (Altdaten)
STATE_FILE = "/tmp/tdd-785-storage-state.json"


# ---------------------------------------------------------------------------
# Session-Fixture
# ---------------------------------------------------------------------------

def _ensure_session_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
        if state.get("cookies"):
            return state

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(BASE, wait_until="networkidle")
        result = page.evaluate("""
            async ([u, p]) => {
                const r = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p}),
                    credentials: 'include',
                });
                return {status: r.status, ok: r.ok};
            }
        """, [USER, PASS])
        if not result.get("ok"):
            raise RuntimeError(f"Login fehlgeschlagen: {result}")
        state = ctx.storage_state()
        fd = os.open(STATE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        browser.close()
    return state


@pytest.fixture(scope="module")
def session_state():
    return _ensure_session_state()


@pytest.fixture(scope="module")
def api_cookie(session_state):
    for c in session_state.get("cookies", []):
        if c.get("name") == "gz_session":
            return c["value"]
    raise RuntimeError("gz_session Cookie nicht gefunden")


# ---------------------------------------------------------------------------
# AC-1: Trip mit show_yesterday_comparison=false → Checkbox unchecked
# ---------------------------------------------------------------------------

class TestAC1CheckboxReflectsStoredFalse:
    """
    AC-1: Given Trip mit show_yesterday_comparison=false in DB /
    When E-Mail-Inhalt-Tab öffnen /
    Then Checkbox 'Vortag-Vergleich' ist unchecked.
    """

    def test_ac1_checkbox_exists_and_is_unchecked(self, session_state, api_cookie):
        # Sicherstellen: Trip hat show_yesterday_comparison=false als Ausgangszustand
        resp = httpx.put(
            f"https://staging.gregor20.henemm.com/api/trips/{TRIP_ID_OFF}",
            json={
                "id": TRIP_ID_OFF,
                "name": "TDD-785 Vortag-Toggle",
                "activity_type": "wandern",
                "stages": [],
                "report_config": {
                    "show_yesterday_comparison": False,
                    "show_stage_stats": True,
                    "show_metrics_summary": False,
                    "show_outlook": True,
                    "email_format": "full",
                },
            },
            cookies={"gz_session": api_cookie},
        )
        assert resp.status_code == 200, f"Setup PUT fehlgeschlagen: {resp.text}"

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(storage_state=session_state)
            page = ctx.new_page()
            page.goto(f"{BASE}/trips/{TRIP_ID_OFF}", wait_until="networkidle")

            # Reports-Tab öffnen
            # Wetter-Tab enthält die E-Mail-Inhalt-Card (showMailContent=true)
            page.locator('[data-testid="trip-detail-tab-weather"]').click()

            # Checkbox muss existieren — schlägt fehl wenn Element fehlt (RED)
            checkbox = page.locator('[data-testid="report-show-yesterday-comparison"]')
            checkbox.wait_for(timeout=5000)

            # Zustand: unchecked
            input_el = checkbox.locator('input[type="checkbox"]')
            assert not input_el.is_checked(), (
                "Checkbox 'Vortag-Vergleich' sollte unchecked sein (show_yesterday_comparison=false)"
            )
            browser.close()


# ---------------------------------------------------------------------------
# AC-2: Abwählen + Speichern → API gibt false zurück
# ---------------------------------------------------------------------------

class TestAC2SavePersistsToAPI:
    """
    AC-2: Given Checkbox angehakt /
    When abwählen + speichern /
    Then GET /api/trips/<id> liefert show_yesterday_comparison=false.
    """

    def test_ac2_uncheck_and_save_reflects_in_api(self, session_state, api_cookie):
        # Sicherstellen: Trip hat show_yesterday_comparison=true als Ausgangszustand
        resp = httpx.put(
            f"https://staging.gregor20.henemm.com/api/trips/{TRIP_ID_OFF}",
            json={
                "id": TRIP_ID_OFF,
                "name": "TDD-785 Vortag-Toggle",
                "activity_type": "wandern",
                "stages": [],
                "report_config": {
                    "show_yesterday_comparison": True,
                    "show_stage_stats": True,
                    "show_metrics_summary": False,
                    "show_outlook": True,
                    "email_format": "full",
                },
            },
            cookies={"gz_session": api_cookie},
        )
        assert resp.status_code == 200, f"Vorbereitung PUT fehlgeschlagen: {resp.text}"

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(storage_state=session_state)
            page = ctx.new_page()
            page.goto(f"{BASE}/trips/{TRIP_ID_OFF}", wait_until="networkidle")

            # Wetter-Tab enthält die E-Mail-Inhalt-Card (showMailContent=true)
            page.locator('[data-testid="trip-detail-tab-weather"]').click()

            # Checkbox muss existieren (RED: fehlt → TimeoutError)
            checkbox = page.locator('[data-testid="report-show-yesterday-comparison"]')
            checkbox.wait_for(timeout=5000)
            input_el = checkbox.locator('input[type="checkbox"]')

            # Angehakt → abwählen
            assert input_el.is_checked(), "Checkbox sollte initial angehakt sein (true)"
            input_el.uncheck()

            # Speichern (Auto-Save oder Save-Button)
            save_btn = page.locator('[data-testid="save-report-config"], button:has-text("Speichern")').first
            if save_btn.count() > 0:
                save_btn.click()
            page.wait_for_timeout(1500)

            browser.close()

        # API verifizieren
        get_resp = httpx.get(
            f"https://staging.gregor20.henemm.com/api/trips/{TRIP_ID_OFF}",
            cookies={"gz_session": api_cookie},
        )
        assert get_resp.status_code == 200
        rc = get_resp.json().get("report_config", {})
        assert rc.get("show_yesterday_comparison") is False, (
            f"API soll show_yesterday_comparison=false liefern, got: {rc}"
        )


# ---------------------------------------------------------------------------
# AC-4: Altdaten ohne Feld → Checkbox angehakt (Default=true)
# ---------------------------------------------------------------------------

class TestAC4LegacyTripShowsChecked:
    """
    AC-4: Given Trip ohne show_yesterday_comparison im report_config /
    When E-Mail-Inhalt-Tab öffnen /
    Then Checkbox 'Vortag-Vergleich' ist angehakt (Default=true).
    """

    def test_ac4_legacy_trip_checkbox_defaults_to_true(self, session_state):
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(storage_state=session_state)
            page = ctx.new_page()
            page.goto(f"{BASE}/trips/{TRIP_ID_LEGACY}", wait_until="networkidle")

            # Wetter-Tab enthält die E-Mail-Inhalt-Card (showMailContent=true)
            page.locator('[data-testid="trip-detail-tab-weather"]').click()

            # Checkbox muss existieren (RED: fehlt → TimeoutError)
            checkbox = page.locator('[data-testid="report-show-yesterday-comparison"]')
            checkbox.wait_for(timeout=5000)
            input_el = checkbox.locator('input[type="checkbox"]')

            assert input_el.is_checked(), (
                "Checkbox 'Vortag-Vergleich' soll bei Altdaten (kein Feld) angehakt sein (Default=true)"
            )
            browser.close()


# ---------------------------------------------------------------------------
# AC-5: Kompakt-Format → Checkbox disabled
# ---------------------------------------------------------------------------

class TestAC5CompactFormatDisablesCheckbox:
    """
    AC-5: Given E-Mail im Format 'Kompakt (Nur-Text)' /
    When E-Mail-Inhalt-Tab öffnen /
    Then Checkbox 'Vortag-Vergleich' ist disabled (analog anderen 3 Bausteinen).
    """

    def test_ac5_compact_format_disables_yesterday_checkbox(self, session_state, api_cookie):
        # Trip auf Kompakt-Format setzen
        resp = httpx.put(
            f"https://staging.gregor20.henemm.com/api/trips/{TRIP_ID_OFF}",
            json={
                "id": TRIP_ID_OFF,
                "name": "TDD-785 Vortag-Toggle",
                "activity_type": "wandern",
                "stages": [],
                "report_config": {
                    "show_yesterday_comparison": True,
                    "show_stage_stats": True,
                    "show_metrics_summary": False,
                    "show_outlook": True,
                    "email_format": "compact",
                },
            },
            cookies={"gz_session": api_cookie},
        )
        assert resp.status_code == 200

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            ctx = browser.new_context(storage_state=session_state)
            page = ctx.new_page()
            page.goto(f"{BASE}/trips/{TRIP_ID_OFF}", wait_until="networkidle")

            # Wetter-Tab enthält die E-Mail-Inhalt-Card (showMailContent=true)
            page.locator('[data-testid="trip-detail-tab-weather"]').click()

            # Checkbox muss existieren (RED: fehlt → TimeoutError)
            checkbox = page.locator('[data-testid="report-show-yesterday-comparison"]')
            checkbox.wait_for(timeout=5000)
            input_el = checkbox.locator('input[type="checkbox"]')

            assert input_el.is_disabled(), (
                "Checkbox 'Vortag-Vergleich' muss im Kompakt-Modus disabled sein"
            )
            browser.close()
