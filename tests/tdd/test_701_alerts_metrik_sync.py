"""
TDD RED — Issue #701: Alerts-Tab metrik-gekoppelt (Backend Auto-Sync + Desktop TE2)
Spec: docs/specs/modules/issue_701_alerts_metrik_sync.md

RED-Erwartung:
  - ac1_backend_sync_via_http: alert_rules leer nach WeatherConfig-PUT (Backend-Sync fehlt)
  - ac2_no_add_rule_button: data-testid="alerts-add-rule" existiert noch (disabled)
  - ac5_channel_chips_readonly: Kanal-Chips sind noch als interaktive Buttons implementiert

Ausführung:
    uv run pytest tests/tdd/test_701_alerts_metrik_sync.py -v
"""
import re
import time
import uuid

import pytest
from playwright.sync_api import sync_playwright

BASE = "https://staging.gregor20.henemm.com"
USER = "validator-issue110"
PASS = "457442e8830f5ee3afe9afe2d5f0d923"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    time.sleep(2)
    inp = (
        page.query_selector("input[name='username']")
        or page.query_selector("input[type='text']")
    )
    inp.click()
    page.keyboard.type(USER)
    pw = page.query_selector("input[type='password']")
    pw.click()
    page.keyboard.type(PASS)
    page.click("button[type='submit']")
    page.wait_for_url(
        re.compile(r"^https://staging\.gregor20\.henemm\.com(?!/login)"),
        timeout=30000,
    )


def _navigate_to_alerts_tab(page, trip_id: str) -> None:
    page.goto(f"{BASE}/trips/{trip_id}", wait_until="networkidle")
    time.sleep(2)
    alerts_tab = page.locator("[data-testid='tab-alerts']")
    if not alerts_tab.is_visible():
        alerts_tab = page.get_by_role("tab", name=re.compile("alerts", re.IGNORECASE))
    alerts_tab.click()
    time.sleep(1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_ac1_backend_sync_via_http():
    """
    AC-1 + AC-3: Nach PUT /api/trips/{id}/weather-config enthält trip.alert_rules
    genau eine absolute Regel pro aktiver alert-fähiger Metrik.
    RED: Backend-Sync nicht implementiert → alert_rules bleibt leer nach WeatherConfig-Update.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        try:
            _login(page)

            trip_id = uuid.uuid4().hex[:8]
            # Trip anlegen
            page.evaluate("""
                async ([tripId]) => {
                    const res = await fetch('/api/trips', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            id: tripId,
                            name: 'TDD-701-AC1-' + tripId,
                            stages: [{
                                id: 'S1', name: 'Tag 1', date: '2026-08-01',
                                waypoints: [
                                    {id: 'W1', name: 'Start', lat: 42.1, lon: 9.1, elevation_m: 100},
                                    {id: 'W2', name: 'Ziel', lat: 42.2, lon: 9.2, elevation_m: 800},
                                ]
                            }]
                        })
                    });
                    return await res.json();
                }
            """, [trip_id])

            # WeatherConfig mit wind_gust + snow_line aktiv, thunder_level = delta-only → kein Alert
            page.evaluate("""
                async ([tripId]) => {
                    await fetch(`/api/trips/${tripId}/weather-config`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            metrics: [
                                {metric_id: 'wind_gust', enabled: true, use_friendly_format: true,
                                 horizons: {today: true, tomorrow: true, day_after: true}},
                                {metric_id: 'snow_line', enabled: true, use_friendly_format: false,
                                 horizons: {today: true, tomorrow: true, day_after: true}},
                                {metric_id: 'thunder_level', enabled: true, use_friendly_format: false,
                                 horizons: {today: true, tomorrow: true, day_after: true}},
                            ]
                        })
                    });
                }
            """, [trip_id])

            # Trip nachladen und alert_rules prüfen
            trip_data = page.evaluate("""
                async ([tripId]) => {
                    const res = await fetch(`/api/trips/${tripId}`);
                    return await res.json();
                }
            """, [trip_id])

            alert_rules = trip_data.get("alert_rules", [])
            metrics_in_rules = [r["metric"] for r in alert_rules]

            # AC-1: genau 2 Regeln (wind_gust + snow_line), NICHT thunder_level
            assert len(alert_rules) == 2, (
                f"AC-1 FAIL: want 2 alert_rules (wind_gust+snow_line), "
                f"got {len(alert_rules)}: {metrics_in_rules}"
            )
            assert "wind_gust" in metrics_in_rules, "AC-1: want wind_gust rule"
            assert "snow_line" in metrics_in_rules, "AC-1: want snow_line rule"
            assert "thunder_level" not in metrics_in_rules, (
                "AC-2 FAIL: thunder_level must NOT get a rule (delta-only)"
            )
            # Alle Regeln müssen absolute sein
            for r in alert_rules:
                assert r.get("kind") == "absolute", (
                    f"AC-2 FAIL: rule {r['metric']} has kind={r.get('kind')}, want absolute"
                )
        finally:
            browser.close()


def test_ac2_no_add_rule_button():
    """
    AC-2: In der Alerts-Tab gibt es keinen 'Neuen Alert hinzufügen'-Button mehr.
    RED: data-testid="alerts-add-rule" existiert noch im DOM (disabled) → Test schlägt fehl.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        try:
            _login(page)
            trip_id = uuid.uuid4().hex[:8]
            page.evaluate("""
                async ([tripId]) => {
                    await fetch('/api/trips', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            id: tripId, name: 'TDD-701-AC2-' + tripId,
                            stages: [{id: 'S1', name: 'D1', date: '2026-08-01',
                                waypoints: [
                                    {id: 'W1', name: 'P1', lat: 42.1, lon: 9.1, elevation_m: 100},
                                    {id: 'W2', name: 'P2', lat: 42.2, lon: 9.2, elevation_m: 800},
                                ]}]
                        })
                    });
                }
            """, [trip_id])

            _navigate_to_alerts_tab(page, trip_id)

            # AC-2: Button soll NICHT im DOM existieren
            add_btn = page.locator("[data-testid='alerts-add-rule']")
            count = add_btn.count()
            assert count == 0, (
                f"AC-2 FAIL: 'alerts-add-rule' Button existiert noch im DOM (count={count}). "
                f"Nach Implementierung muss er komplett entfernt sein."
            )
        finally:
            browser.close()


def test_ac5_channel_chips_readonly():
    """
    AC-5: Kanal-Chips in AlertCard sind read-only (keine interaktiven Buttons mehr).
    RED: Kanal-Chips sind noch als <button> mit onclick=toggleChannel implementiert.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        try:
            _login(page)
            trip_id = uuid.uuid4().hex[:8]
            # Trip mit wind_gust-Regel direkt anlegen (ohne Backend-Sync)
            page.evaluate("""
                async ([tripId]) => {
                    await fetch('/api/trips', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            id: tripId, name: 'TDD-701-AC5-' + tripId,
                            stages: [{id: 'S1', name: 'D1', date: '2026-08-01',
                                waypoints: [
                                    {id: 'W1', name: 'P1', lat: 42.1, lon: 9.1, elevation_m: 100},
                                    {id: 'W2', name: 'P2', lat: 42.2, lon: 9.2, elevation_m: 800},
                                ]}],
                            alert_rules: [{
                                id: 'test-rule-701', kind: 'absolute',
                                metric: 'wind_gust', threshold: 50,
                                unit: 'km/h', severity: 'warning', enabled: true
                            }],
                            report_config: {send_email: true}
                        })
                    });
                }
            """, [trip_id])

            _navigate_to_alerts_tab(page, trip_id)

            cards = page.locator("[data-testid^='alert-card-']")
            if cards.count() == 0:
                pytest.skip("Keine Alert-Karten vorhanden")

            first_card = cards.first

            # AC-5: Kanal-Chip-Buttons dürfen NICHT als klickbare <button>-Elemente existieren.
            # Nach Implementierung: read-only <span> statt <button>.
            channel_buttons = first_card.locator("[data-testid^='channel-chip-']")
            count = channel_buttons.count()
            assert count == 0, (
                f"AC-5 FAIL: Kanal-Chips sind noch als interaktive Buttons implementiert "
                f"(count={count}). Nach Implementierung müssen sie read-only (span/div) sein."
            )
        finally:
            browser.close()
