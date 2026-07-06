"""
TDD RED — Issue #702: Alerts-Tab Mobile-Parität TM2 (Epic #700, Slice 2/2)
Spec: docs/specs/modules/issue_702_alerts_mobile_parity.md

RED-Erwartung:
  - ac2_channel_chips_touch_target: Chips zu klein (padding: 4px 10px < 36px Höhe)
  - ac2_threshold_input_width: Input 72px < 120px Mindestbreite
  - ac3_only_one_save_button_visible: .actions-Bar NICHT ausgeblendet → 2 Save-Buttons sichtbar
  - ac5_cooldown_input_touch_target: Cooldown-Input < 44px Höhe

Ausführung:
    uv run pytest tests/tdd/test_702_alerts_mobile_parity.py -v
"""
import json
import os
import time

from playwright.sync_api import sync_playwright

from tests.helpers.staging_auth import playwright_http_credentials

BASE = "https://staging.gregor20.henemm.com"
USER = "tdd-702-1781109629"
PASS = "720c7e56751c8133e771e7bc903fc122"

MOBILE_VIEWPORT = {"width": 375, "height": 812}
STATE_FILE = "/tmp/tdd-702-storage-state.json"


# ---------------------------------------------------------------------------
# Session-Fixture (einmaliger Login für alle Tests)
# ---------------------------------------------------------------------------

def _ensure_session_state() -> dict:
    """Login einmal durchführen, Session-State cachen."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
        # Cookie noch gültig?
        cookies = state.get("cookies", [])
        if cookies:
            return state

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(http_credentials=playwright_http_credentials())
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
            raise RuntimeError(f"Session-Login fehlgeschlagen: {result}")
        state = ctx.storage_state()
        browser.close()

    fd = os.open(STATE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(state, f)
    return state


def _setup_trip_with_metrics(page) -> str:
    """Trip mit aktiven Metriken anlegen → gibt trip_id zurück."""
    import uuid as _uuid
    trip_id = _uuid.uuid4().hex[:8]

    # Sicherstellen dass die Page im richtigen Origin ist (storage_state startet auf about:blank)
    if not page.url.startswith(BASE):
        page.goto(BASE, wait_until="networkidle")
        time.sleep(1)

    page.evaluate("""
        async ([tid]) => {
            const r = await fetch('/api/trips', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    id: tid,
                    name: 'TDD-702-' + tid,
                    stages: [{
                        id: 'S1', name: 'Tag 1', date: '2026-08-01',
                        waypoints: [
                            {id: 'W1', name: 'Start', lat: 42.1, lon: 9.1, elevation_m: 100},
                            {id: 'W2', name: 'Ziel',  lat: 42.2, lon: 9.2, elevation_m: 800},
                        ]
                    }]
                })
            });
        }
    """, [trip_id])

    # Report-Config mit aktiven Kanälen setzen (damit Channel-Chips in AlertCard erscheinen)
    page.evaluate("""
        async ([tid]) => {
            await fetch('/api/trips/' + tid, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    report_config: {send_email: true, send_telegram: false, send_sms: false}
                })
            });
        }
    """, [trip_id])

    # Wetter-Metriken setzen (triggert Backend-Sync → AlertRules werden angelegt)
    page.evaluate("""
        async ([tid]) => {
            await fetch('/api/trips/' + tid + '/weather-config', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    metrics: [
                        {metric_id: 'wind_gust',         enabled: true, use_friendly_format: true,
                         horizons: {today: true, tomorrow: true, day_after: false}},
                        {metric_id: 'precipitation_sum', enabled: true, use_friendly_format: true,
                         horizons: {today: true, tomorrow: true, day_after: false}},
                    ]
                })
            });
        }
    """, [trip_id])
    return trip_id


def _navigate_to_alerts_tab(page, trip_id: str) -> None:
    page.goto(f"{BASE}/trips/{trip_id}", wait_until="networkidle")
    time.sleep(2)
    # Auf Mobile (375px): data-testid="trip-detail-tab-alerts" (kein role=tab auf Mobile)
    alerts_tab = page.locator("[data-testid='trip-detail-tab-alerts']")
    alerts_tab.click()
    time.sleep(1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_ac1_mobile_cards_visible_no_add_button():
    """
    AC-1: ≤899px → AlertCards sichtbar, kein 'Regel hinzufügen'-Button.
    Nutzer öffnet Alerts-Tab auf 375px-Viewport — sieht Karten ohne Add-Button.
    RED: Dieser Test PASST bereits (aus #701) — bleibt als Regressions-Anker.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=MOBILE_VIEWPORT, storage_state=state, http_credentials=playwright_http_credentials())
        page = ctx.new_page()
        try:
            trip_id = _setup_trip_with_metrics(page)
            _navigate_to_alerts_tab(page, trip_id)

            cards_list = page.locator("[data-testid='alert-cards-list']")
            assert cards_list.is_visible(), "alert-cards-list muss sichtbar sein"

            cards = page.locator("[data-testid^='alert-card-']")
            assert cards.count() >= 1, "Mindestens eine AlertCard erwartet"

            add_btn = page.locator("[data-testid='alerts-add-rule']")
            assert add_btn.count() == 0, "'Regel hinzufügen'-Button darf auf Mobile nicht existieren"
        finally:
            browser.close()


def test_ac2_channel_chips_touch_target():
    """
    AC-2: ≤899px → Channel-Chips Bounding-Box-Höhe ≥36px.
    Nutzer sieht auf Mobile Kanal-Chips die groß genug zum Antippen sind.
    RED: Aktuell padding: 4px 10px → Chip-Höhe deutlich unter 36px.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=MOBILE_VIEWPORT, storage_state=state, http_credentials=playwright_http_credentials())
        page = ctx.new_page()
        try:
            trip_id = _setup_trip_with_metrics(page)
            _navigate_to_alerts_tab(page, trip_id)

            chips = page.locator("[data-testid^='ch-ro-']")
            assert chips.count() > 0, "Mindestens ein Channel-Chip erwartet"

            chip = chips.first
            box = chip.bounding_box()
            assert box is not None, "Channel-Chip muss im Viewport sichtbar sein"
            assert box["height"] >= 36, (
                f"Channel-Chip-Höhe {box['height']:.1f}px < 36px Mindest-Touch-Target (AC-2)"
            )
        finally:
            browser.close()


def test_ac2_threshold_input_width():
    """
    AC-2: ≤899px → Threshold-Input-Breite ≥120px.
    Nutzer kann auf Mobile den Schwellwert komfortabel eingeben.
    RED: Aktuell width: 72px < 120px.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=MOBILE_VIEWPORT, storage_state=state, http_credentials=playwright_http_credentials())
        page = ctx.new_page()
        try:
            trip_id = _setup_trip_with_metrics(page)
            _navigate_to_alerts_tab(page, trip_id)

            threshold_input = page.locator(".threshold-input").first
            assert threshold_input.is_visible(), "Threshold-Input muss sichtbar sein"
            box = threshold_input.bounding_box()
            assert box is not None, "Threshold-Input muss im Viewport sichtbar sein"
            assert box["width"] >= 120, (
                f"Threshold-Input-Breite {box['width']:.1f}px < 120px Mindestbreite (AC-2)"
            )
        finally:
            browser.close()


def test_ac3_only_one_save_button_visible():
    """
    AC-3: ≤899px → Nur Mobile-Footer-Save sichtbar, Desktop-.actions ausgeblendet.
    Nutzer sieht auf Mobile keinen doppelten Speichern-Button.
    RED: Aktuell .actions-Bar nicht ausgeblendet → beide Save-Buttons sichtbar.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=MOBILE_VIEWPORT, storage_state=state, http_credentials=playwright_http_credentials())
        page = ctx.new_page()
        try:
            trip_id = _setup_trip_with_metrics(page)
            _navigate_to_alerts_tab(page, trip_id)

            mobile_footer = page.locator("[data-testid='alerts-tab-mobile-footer']")
            assert mobile_footer.is_visible(), "Mobile-Footer muss auf ≤899px sichtbar sein"

            save_buttons = page.locator("[data-testid='alerts-tab-save']")
            visible_count = sum(
                1 for i in range(save_buttons.count())
                if save_buttons.nth(i).is_visible()
            )
            assert visible_count == 1, (
                f"Erwartet genau 1 sichtbaren Save-Button auf Mobile, gefunden: {visible_count} "
                f"(AC-3: .actions-Bar muss auf ≤899px ausgeblendet sein)"
            )
        finally:
            browser.close()


def test_ac4_desktop_layout_unchanged():
    """
    AC-4: ≥900px → Desktop-Layout byte-identisch, keine Regression.
    Nutzer sieht auf Desktop dieselbe Alerts-Tab wie vor dieser Änderung.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, storage_state=state, http_credentials=playwright_http_credentials())
        page = ctx.new_page()
        try:
            trip_id = _setup_trip_with_metrics(page)
            _navigate_to_alerts_tab(page, trip_id)

            save_btn = page.locator("[data-testid='alerts-tab-save']").first
            assert save_btn.is_visible(), (
                "Desktop: alerts-tab-save muss auf 1280px sichtbar sein (AC-4)"
            )

            mobile_footer = page.locator("[data-testid='alerts-tab-mobile-footer']")
            assert not mobile_footer.is_visible(), (
                "Desktop: Mobile-Footer darf auf 1280px nicht sichtbar sein (AC-4)"
            )

            cards = page.locator("[data-testid^='alert-card-']")
            assert cards.count() >= 1, "Desktop: AlertCards müssen sichtbar sein"
        finally:
            browser.close()


def test_ac5_cooldown_input_touch_target():
    """
    AC-5: ≤899px → Cooldown-Input Bounding-Box-Höhe ≥44px (WCAG Touch-Target).
    Nutzer kann auf Mobile Cooldown-Minuten ohne Präzisions-Tap eingeben.
    RED: Aktuell kein min-height → Höhe deutlich unter 44px.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=MOBILE_VIEWPORT, storage_state=state, http_credentials=playwright_http_credentials())
        page = ctx.new_page()
        try:
            trip_id = _setup_trip_with_metrics(page)
            _navigate_to_alerts_tab(page, trip_id)

            cooldown_input = page.locator("[data-testid='alert-cooldown-input']")
            assert cooldown_input.is_visible(), "Cooldown-Input muss sichtbar sein"
            box = cooldown_input.bounding_box()
            assert box is not None, "Cooldown-Input muss im Viewport sein"
            assert box["height"] >= 44, (
                f"Cooldown-Input-Höhe {box['height']:.1f}px < 44px WCAG-Touch-Target (AC-5)"
            )
        finally:
            browser.close()
