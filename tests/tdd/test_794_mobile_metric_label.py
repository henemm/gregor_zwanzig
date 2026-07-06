"""
TDD RED — Issue #794: Mobile Metrik-Label Truncation Fix

Spec ACs:
  AC-1: Mobiler Viewport (<900px) → Metrik-Namen vollständig sichtbar (white-space: normal, kein nowrap)
  AC-2: Mobiler Viewport (<900px) → .controls flexDirection='column' (kein horizontaler Overflow)
  AC-3: Desktop-Viewport (≥900px) → Metrik-Namen einzeilig mit Ellipsis (white-space: nowrap bleibt)

RED-Erwartung:
  AC-1 FAIL: .metric-label hat aktuell white-space: nowrap → getComputedStyle liefert 'nowrap', nicht 'normal'
  AC-2 FAIL: .controls hat aktuell flex-direction: row → 'row', nicht 'column'
  AC-3 PASS: .metric-label auf Desktop hat white-space: nowrap → existierendes Verhalten bestätigt

Ausführung:
    uv run pytest tests/tdd/test_794_mobile_metric_label.py -v
"""
import json
import os
import time

from playwright.sync_api import sync_playwright

BASE = "https://staging.gregor20.henemm.com"

# Credentials: laden aus .claude/validator.env (gleiche Quelle wie design_fidelity_diff.py).
# Fallback auf den bekannten tdd-702-User (hat Trips mit Metriken, ideal für CSS-Test).
def _load_credentials() -> tuple[str, str]:
    env_file = Path("/home/hem/gregor_zwanzig/.claude/validator.env")
    user = os.environ.get("GZ_VALIDATOR_USER", "")
    pw = os.environ.get("GZ_VALIDATOR_PASS", "")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k == "GZ_VALIDATOR_USER" and not user:
                user = v
            if k == "GZ_VALIDATOR_PASS" and not pw:
                pw = v
    # Fallback: tdd-702-User ist auf Staging bekannt und hat bereits Metriken
    if not user:
        user = "tdd-702-1781109629"
    if not pw:
        pw = "720c7e56751c8133e771e7bc903fc122"
    return user, pw

from pathlib import Path
_USER, _PASS = _load_credentials()

MOBILE_VIEWPORT = {"width": 390, "height": 844}
DESKTOP_VIEWPORT = {"width": 1280, "height": 800}
# Reihenfolge: eigene Session-Datei → tdd-702-Session (gleicher Nutzer, pre-gecacht)
STATE_FILE = "/tmp/tdd-794-storage-state.json"
STATE_FILE_FALLBACK = "/tmp/tdd-702-storage-state.json"


# ---------------------------------------------------------------------------
# Session-Fixture (einmaliger Login für alle Tests)
# ---------------------------------------------------------------------------

def _ensure_session_state() -> dict:
    """Login via Formular einmal durchführen, Session-State cachen.
    Versucht STATE_FILE, dann STATE_FILE_FALLBACK (tdd-702 Session), dann frischen Login.
    """
    for sf in [STATE_FILE, STATE_FILE_FALLBACK]:
        if os.path.exists(sf):
            with open(sf) as f:
                state = json.load(f)
            cookies = state.get("cookies", [])
            if cookies:
                return state

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context()
        page = ctx.new_page()

        try:
            page.goto(f"{BASE}/login", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)
            page.fill("input[name='username']", _USER)
            page.fill("input[name='password']", _PASS)
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception as e:
            # Fallback: API-Login direkt versuchen
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
            """, [_USER, _PASS])
            if not result.get("ok"):
                raise RuntimeError(f"Session-Login fehlgeschlagen (user={_USER}): {result}") from e

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
                    name: 'TDD-794-' + tid,
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

    # Wetter-Metriken mit mehreren Einträgen setzen (damit Reihenfolge-Abschnitt befüllt ist)
    page.evaluate("""
        async ([tid]) => {
            await fetch('/api/trips/' + tid + '/weather-config', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    metrics: [
                        {metric_id: 'wind_gust',          enabled: true, use_friendly_format: true,
                         horizons: {today: true, tomorrow: true, day_after: false}},
                        {metric_id: 'precipitation_sum',  enabled: true, use_friendly_format: true,
                         horizons: {today: true, tomorrow: true, day_after: false}},
                        {metric_id: 'temperature_max',    enabled: true, use_friendly_format: false,
                         horizons: {today: true, tomorrow: true, day_after: false}},
                    ]
                })
            });
        }
    """, [trip_id])
    return trip_id


def _navigate_to_weather_tab(page, trip_id: str) -> None:
    """Trip-Detail öffnen und auf den Inhalt/Wetter-Tab navigieren."""
    page.goto(f"{BASE}/trips/{trip_id}?tab=weather", wait_until="networkidle")
    time.sleep(2)
    # Fallback: Tab-Button klicken falls URL-Parameter nicht greift
    weather_tab = page.locator("[data-testid='trip-detail-tab-weather']")
    if weather_tab.count() > 0:
        weather_tab.click()
        time.sleep(1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_ac1_mobile_metric_label_white_space_normal():
    """
    AC-1: Mobiler Viewport (390px) → .metric-label white-space = 'normal'.
    Nutzer sieht auf Mobile alle Metrik-Namen vollständig, kein Abschneiden.
    RED: Aktuell white-space: nowrap → getComputedStyle liefert 'nowrap', nicht 'normal'.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=MOBILE_VIEWPORT, storage_state=state)
        page = ctx.new_page()
        try:
            trip_id = _setup_trip_with_metrics(page)
            _navigate_to_weather_tab(page, trip_id)

            # Warte auf das Reihenfolge-Section (state='attached' reicht: CSS-Test braucht kein visible)
            page.wait_for_selector(".metric-label", state="attached", timeout=15000)
            # Scroll to element to ensure it's in view
            first_el = page.locator(".metric-label").first
            first_el.scroll_into_view_if_needed()

            labels = page.locator(".metric-label")
            assert labels.count() > 0, "Mindestens ein .metric-label muss im Reihenfolge-Abschnitt sichtbar sein"

            first_label = labels.first
            white_space = page.evaluate(
                "(el) => window.getComputedStyle(el).whiteSpace",
                first_label.element_handle()
            )
            assert white_space == "normal", (
                f"AC-1 FAIL: .metric-label white-space ist '{white_space}', "
                f"erwartet 'normal' auf mobilem Viewport (390px). "
                f"Aktuell ist 'nowrap' gesetzt — Metrik-Namen werden abgekürzt statt umgebrochen."
            )
        finally:
            browser.close()


def test_ac2_mobile_controls_flex_direction_column():
    """
    AC-2: Mobiler Viewport (390px) → .controls flex-direction = 'column'.
    Nutzer sieht auf Mobile Steuerelemente vertikal gestapelt, kein horizontaler Overflow.
    RED: Aktuell flex-direction: row → 'row', nicht 'column'.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=MOBILE_VIEWPORT, storage_state=state)
        page = ctx.new_page()
        try:
            trip_id = _setup_trip_with_metrics(page)
            _navigate_to_weather_tab(page, trip_id)

            page.wait_for_selector(".controls", state="attached", timeout=15000)
            # Scroll to ensure in view
            page.locator(".controls").first.scroll_into_view_if_needed()

            controls = page.locator(".controls")
            assert controls.count() > 0, "Mindestens ein .controls-Element muss sichtbar sein"

            first_controls = controls.first
            flex_direction = page.evaluate(
                "(el) => window.getComputedStyle(el).flexDirection",
                first_controls.element_handle()
            )
            assert flex_direction == "column", (
                f"AC-2 FAIL: .controls flex-direction ist '{flex_direction}', "
                f"erwartet 'column' auf mobilem Viewport (390px). "
                f"Aktuell keine mobile Stapelung — horizontaler Overflow möglich."
            )
        finally:
            browser.close()


def test_ac3_desktop_metric_label_white_space_nowrap():
    """
    AC-3: Desktop-Viewport (1280px) → .metric-label white-space = 'nowrap'.
    Nutzer sieht auf Desktop Metrik-Namen einzeilig mit Ellipsis — existierendes Verhalten bleibt erhalten.
    PASS: Dieser Test bestätigt existierendes Verhalten und darf nicht nach der Implementierung brechen.
    """
    state = _ensure_session_state()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=DESKTOP_VIEWPORT, storage_state=state)
        page = ctx.new_page()
        try:
            trip_id = _setup_trip_with_metrics(page)
            _navigate_to_weather_tab(page, trip_id)

            page.wait_for_selector(".metric-label", state="attached", timeout=15000)

            labels = page.locator(".metric-label")
            assert labels.count() > 0, "Mindestens ein .metric-label muss auf Desktop sichtbar sein"

            first_label = labels.first
            white_space = page.evaluate(
                "(el) => window.getComputedStyle(el).whiteSpace",
                first_label.element_handle()
            )
            assert white_space == "nowrap", (
                f"AC-3 REGRESSION: .metric-label white-space ist '{white_space}', "
                f"erwartet 'nowrap' auf Desktop-Viewport (1280px). "
                f"Desktop-Verhalten darf durch Mobile-Fix nicht verändert werden."
            )
        finally:
            browser.close()
