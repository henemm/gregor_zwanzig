"""
TDD RED — Issue #846: Alert-Rework Slice 3 — Preset-Dropdown (Epic #813, Slice 3)
Spec: docs/specs/modules/issue_846_alert_preset.md

Geprüft werden hier NUR die E2E/Playwright-ACs (Frontend, eingeloggter Nutzer
gegen Staging). Die reinen Backend-ACs (AC-3/AC-4/AC-6/AC-7/AC-8 sowie der
Python-Teil von AC-2) sind echte Python-Unittests in einer separaten Datei.

RED-Erwartung (Feature existiert noch NICHT — Preset-Dropdown ist nicht gebaut):
  - AC-1: Es gibt noch KEIN Preset-Dropdown im Alerts-Tab; stattdessen sind
          Zahlen-Inputs (`<input type="number">`) sichtbar → Test schlägt fehl.
  - AC-2: "Sensibel" lässt sich nicht im Dropdown wählen (kein Dropdown vorhanden)
          → Test schlägt fehl.
  - AC-5: Es gibt noch kein Info-Icon (ℹ) mit Schwellen-Popover → Test schlägt fehl.

KEINE MOCKS. Echter Browser (Playwright) gegen Staging.

Ausführung:
    uv run pytest tests/tdd/test_issue_846_alert_preset_e2e.py -v
"""
import json
import os
import time
import uuid

import pytest
from playwright.sync_api import sync_playwright

from tests.helpers.staging_auth import (  # Bündel H #987: Staging-Basic-Auth
    playwright_http_credentials,
)

BASE = "https://staging.gregor20.henemm.com"

# Bekannter, auf Staging verifizierter Test-Nutzer (mandantenisoliert).
USER = os.environ.get("GZ_TEST_USER", "tdd-702-1781109629")
PASS = os.environ.get("GZ_TEST_PASS", "720c7e56751c8133e771e7bc903fc122")

STATE_FILE = "/tmp/tdd-846-storage-state.json"


# ---------------------------------------------------------------------------
# Session-Fixture (einmaliger Login für alle Tests)
# ---------------------------------------------------------------------------

def _ensure_session_state() -> dict:
    """Login einmal durchführen, Session-State cachen."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            if state.get("cookies"):
                return state
        except (json.JSONDecodeError, OSError):
            pass

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(http_credentials=playwright_http_credentials())
        page = ctx.new_page()
        page.goto(BASE, wait_until="networkidle")
        result = page.evaluate(
            """
            async ([u, p]) => {
                const r = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p}),
                    credentials: 'include',
                });
                return {status: r.status, ok: r.ok};
            }
            """,
            [USER, PASS],
        )
        if not result.get("ok"):
            pytest.skip(f"Staging-Login fehlgeschlagen ({result}) — Infrastruktur, kein Feature-Defekt")
        state = ctx.storage_state()
        browser.close()

    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    return state


def _create_legacy_trip(page) -> str:
    """
    Trip mit Legacy-`alert_rules`-Array anlegen (KEIN `display_config.alert_preset`).
    Repräsentiert eine alte Config aus Slice 1/2. Gibt trip_id zurück.
    """
    trip_id = "tdd846-" + uuid.uuid4().hex[:6]

    if not page.url.startswith(BASE):
        page.goto(BASE, wait_until="networkidle")
        time.sleep(1)

    res = page.evaluate(
        """
        async ([tid]) => {
            const r = await fetch('/api/trips', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    id: tid,
                    name: 'TDD-846-' + tid,
                    stages: [{
                        id: 'S1', name: 'Tag 1', date: '2026-08-01',
                        waypoints: [
                            {id: 'W1', name: 'Start', lat: 42.1, lon: 9.1, elevation_m: 100},
                            {id: 'W2', name: 'Ziel',  lat: 42.2, lon: 9.2, elevation_m: 800}
                        ]
                    }],
                    report_config: {send_email: true, send_telegram: false, send_sms: false},
                    alert_rules: [
                        {id: 'legacy-r1', kind: 'delta', metric: 'wind_gust',
                         threshold: 35, unit: 'km/h', enabled: true},
                        {id: 'legacy-r2', kind: 'delta', metric: 'precipitation_sum',
                         threshold: 15, unit: 'mm', enabled: true}
                    ]
                })
            });
            return {status: r.status, ok: r.ok};
        }
        """,
        [trip_id],
    )
    if not res.get("ok"):
        pytest.skip(f"Trip-Anlage auf Staging fehlgeschlagen ({res}) — Infrastruktur")
    return trip_id


def _navigate_to_alerts_tab(page, trip_id: str) -> None:
    page.goto(f"{BASE}/trips/{trip_id}", wait_until="networkidle")
    time.sleep(2)
    alerts_tab = page.locator("[data-testid='trip-detail-tab-alerts']")
    alerts_tab.first.click()
    time.sleep(1)


# ---------------------------------------------------------------------------
# AC-1 — Preset-Dropdown statt Zahlen-Inputs (Legacy-Config ohne alert_preset)
# ---------------------------------------------------------------------------

def test_ac1_preset_dropdown_standard_no_number_inputs():
    """
    AC-1: Trip mit Legacy-`alert_rules` (kein `alert_preset`) → Alerts-Tab zeigt
    ein Preset-Dropdown mit Wert "Standard"; KEIN `<input type="number">` im DOM
    des Alerts-Tab, keine Einzel-Toggles.

    RED: Es existiert noch kein Preset-Selector; der Alerts-Tab enthält weiterhin
    Zahlen-Inputs / Karten-Modell → Test schlägt fehl.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            storage_state=state,
            http_credentials=playwright_http_credentials(),
        )
        page = ctx.new_page()
        try:
            trip_id = _create_legacy_trip(page)
            _navigate_to_alerts_tab(page, trip_id)

            # 1) Preset-Dropdown muss existieren und "Standard" anzeigen.
            preset = page.locator("[data-testid='alert-preset-select']")
            assert preset.count() == 1, (
                "AC-1 FAIL: Es gibt kein Preset-Dropdown "
                "(data-testid='alert-preset-select') im Alerts-Tab."
            )
            assert preset.first.is_visible(), "AC-1: Preset-Dropdown muss sichtbar sein"

            # Ausgewählter Wert / Anzeigetext muss "Standard" sein (Default bei Legacy).
            value = (preset.first.input_value() if preset.first.evaluate(
                "el => el.tagName.toLowerCase() === 'select'"
            ) else preset.first.inner_text()).strip().lower()
            assert "standard" in value, (
                f"AC-1 FAIL: Preset-Dropdown zeigt nicht 'Standard', sondern '{value}'."
            )

            # 2) KEIN Schwellwert-Zahlen-Input im Alerts-Tab.
            # Das Cooldown-Input (data-testid='alert-cooldown-input') ist legitim und bleibt.
            alerts_tab = page.locator("[data-testid='alerts-tab']")
            threshold_inputs = alerts_tab.locator(
                "input[type='number']:not([data-testid='alert-cooldown-input'])"
            )
            assert threshold_inputs.count() == 0, (
                f"AC-1 FAIL: {threshold_inputs.count()} Schwellwert-Zahlen-Inputs im Alerts-Tab — "
                "das Preset-Modell darf keine manuellen Threshold-Inputs mehr zeigen."
            )
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# AC-2 — "Sensibel" wählen + speichern → nach Reload "Sensibel"
# ---------------------------------------------------------------------------

def test_ac2_select_sensibel_persists_after_reload():
    """
    AC-2 (E2E-Teil): User wählt im Dropdown "Sensibel", speichert, lädt neu —
    das Dropdown zeigt nach Reload weiterhin "Sensibel".

    RED: Kein Preset-Dropdown → Auswahl/Persistenz nicht möglich → Test schlägt fehl.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            storage_state=state,
            http_credentials=playwright_http_credentials(),
        )
        page = ctx.new_page()
        try:
            trip_id = _create_legacy_trip(page)
            _navigate_to_alerts_tab(page, trip_id)

            preset = page.locator("[data-testid='alert-preset-select']")
            assert preset.count() == 1, (
                "AC-2 FAIL: Kein Preset-Dropdown (data-testid='alert-preset-select') vorhanden."
            )

            # "Sensibel" auswählen (HTML-<select> via select_option; sonst Klick-Fallback).
            is_select = preset.first.evaluate("el => el.tagName.toLowerCase() === 'select'")
            if is_select:
                preset.first.select_option(label="Sensibel")
            else:
                preset.first.click()
                page.get_by_text("Sensibel", exact=True).first.click()
            time.sleep(0.5)

            # Speichern.
            save = page.locator("[data-testid='alerts-tab-save']").first
            save.click()
            time.sleep(2)

            # Reload + erneut Alerts-Tab öffnen.
            _navigate_to_alerts_tab(page, trip_id)

            preset_after = page.locator("[data-testid='alert-preset-select']")
            assert preset_after.count() == 1, "AC-2 FAIL: Preset-Dropdown nach Reload verschwunden."
            value = (preset_after.first.input_value() if preset_after.first.evaluate(
                "el => el.tagName.toLowerCase() === 'select'"
            ) else preset_after.first.inner_text()).strip().lower()
            assert "sensibel" in value, (
                f"AC-2 FAIL: Nach Reload zeigt das Dropdown '{value}' statt 'Sensibel' — "
                "Preset wurde nicht persistiert."
            )
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# AC-5 — Info-Icon (ℹ) öffnet/schließt Schwellen-Popover
# ---------------------------------------------------------------------------

def test_ac5_info_icon_toggles_threshold_popover():
    """
    AC-5: Klick auf das Info-Icon (ℹ) neben dem Dropdown öffnet ein Popover mit
    der Schwellen-Tabelle (enthält "Böen" und Standard-Schwelle "20 km/h");
    erneuter Klick / Schließen blendet es wieder aus.

    RED: Kein Info-Icon / kein Popover vorhanden → Test schlägt fehl.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            storage_state=state,
            http_credentials=playwright_http_credentials(),
        )
        page = ctx.new_page()
        try:
            trip_id = _create_legacy_trip(page)
            _navigate_to_alerts_tab(page, trip_id)

            info_icon = page.locator("[data-testid='alert-preset-info']")
            assert info_icon.count() == 1, (
                "AC-5 FAIL: Kein Info-Icon (data-testid='alert-preset-info') neben dem Dropdown."
            )

            popover = page.locator("[data-testid='alert-preset-popover']")
            # Vor Klick: Popover nicht sichtbar.
            assert popover.count() == 0 or not popover.first.is_visible(), (
                "AC-5: Popover darf vor dem Klick nicht sichtbar sein."
            )

            # Öffnen.
            info_icon.first.click()
            time.sleep(0.5)
            assert popover.count() == 1 and popover.first.is_visible(), (
                "AC-5 FAIL: Popover erscheint nach Klick auf Info-Icon nicht."
            )

            popover_text = popover.first.inner_text()
            assert "Böen" in popover_text, (
                f"AC-5 FAIL: Popover enthält 'Böen' nicht. Inhalt: {popover_text!r}"
            )
            assert "20 km/h" in popover_text, (
                f"AC-5 FAIL: Popover enthält die Standard-Böen-Schwelle '20 km/h' nicht. "
                f"Inhalt: {popover_text!r}"
            )

            # Schließen (erneuter Klick aufs Icon oder Schließen-Button).
            close_btn = page.locator("[data-testid='alert-preset-popover-close']")
            if close_btn.count() >= 1 and close_btn.first.is_visible():
                close_btn.first.click()
            else:
                info_icon.first.click()
            time.sleep(0.5)

            popover_after = page.locator("[data-testid='alert-preset-popover']")
            assert popover_after.count() == 0 or not popover_after.first.is_visible(), (
                "AC-5 FAIL: Popover lässt sich nicht wieder schließen."
            )
        finally:
            browser.close()
