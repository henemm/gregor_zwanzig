"""
TDD RED — Issue #675 Startzeiten je Etappe editieren
Spec: docs/specs/modules/issue_675_stage_start_time_edit.md

RED-Erwartung: data-testid="stage-start-time-field" existiert noch nicht auf Staging.
Alle Tests schlagen mit TimeoutError fehl — weil das Eingabe-Widget fehlt.

Ausführung:
    uv run pytest tests/tdd/test_issue_675_stage_start_time.py -v
"""
import json
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


def _make_trip_payload(prefix: str, with_pause: bool = False) -> tuple[dict, str, str]:
    """Gibt (payload, trip_id, normal_stage_id) zurück."""
    trip_id = uuid.uuid4().hex[:8]
    normal_stage_id = uuid.uuid4().hex[:8]
    stages = [
        {
            "id": normal_stage_id,
            "name": "Wandertag",
            "date": "2026-08-01",
            "waypoints": [
                {"id": uuid.uuid4().hex[:8], "name": "Start",
                 "lat": 42.1, "lon": 9.1, "elevation_m": 100},
                {"id": uuid.uuid4().hex[:8], "name": "Ziel",
                 "lat": 42.2, "lon": 9.2, "elevation_m": 800},
            ],
        }
    ]
    if with_pause:
        stages.append({
            "id": uuid.uuid4().hex[:8],
            "name": "Pausentag",
            "date": "2026-08-02",
            "waypoints": [],
        })
    payload = {
        "id": trip_id,
        "name": f"TDD-675-{prefix}-{trip_id}",
        "stages": stages,
    }
    return payload, trip_id, normal_stage_id


def _create_trip(page, prefix: str, with_pause: bool = False) -> tuple[str, str]:
    """Legt Test-Trip an und gibt (trip_id, normal_stage_id) zurück."""
    payload, trip_id, stage_id = _make_trip_payload(prefix, with_pause)
    resp = page.request.post(
        f"{BASE}/api/trips",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 201, f"Trip-Create fehlgeschlagen: {resp.status} — {resp.text()}"
    return trip_id, stage_id


def _delete_trip(page, trip_id: str) -> None:
    try:
        page.request.delete(f"{BASE}/api/trips/{trip_id}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# AC-1: Startzeit-Feld sichtbar im Desktop-Editor (1440px)
# ---------------------------------------------------------------------------

class TestAC1StartTimeFieldDesktop:
    """
    AC-1: GIVEN Etappe mit Wegpunkten im Editor / WHEN Desktop (1440px) /
    THEN data-testid="stage-start-time-field" sichtbar.
    RED: Widget existiert noch nicht → TimeoutError.
    """

    def test_start_time_field_visible_desktop(self):
        """Playwright-E2E: Startzeit-Feld im Desktop-Etappen-Editor sichtbar."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            trip_id = None
            try:
                _login(page)
                trip_id, _ = _create_trip(page, "ac1")
                page.goto(f"{BASE}/trips/{trip_id}/edit", wait_until="networkidle")
                time.sleep(2)
                # RED: Widget data-testid="stage-start-time-field" existiert noch nicht
                page.locator('[data-testid="stage-start-time-field"]').wait_for(
                    state="visible", timeout=5000
                )
            finally:
                if trip_id:
                    _delete_trip(page, trip_id)
                browser.close()


# ---------------------------------------------------------------------------
# AC-2: Startzeit persistiert nach Save + Reload
# ---------------------------------------------------------------------------

class TestAC2StartTimePersists:
    """
    AC-2: GIVEN Startzeit auf 15:00 gesetzt + gespeichert /
    WHEN Seite neu geladen / THEN Feld zeigt 15:00.
    RED: Feld existiert noch nicht → TimeoutError.
    """

    def test_start_time_persists_after_save_reload(self):
        """Playwright-E2E: start_time 15:00 überlebt Save + Reload."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            trip_id = None
            try:
                _login(page)
                trip_id, _ = _create_trip(page, "ac2")
                page.goto(f"{BASE}/trips/{trip_id}/edit", wait_until="networkidle")
                time.sleep(2)
                # RED: Feld nicht vorhanden → TimeoutError
                time_input = page.locator('[data-testid="stage-start-time-field"] input[type="time"]')
                time_input.wait_for(state="visible", timeout=5000)
                time_input.fill("15:00")
                # Speichern
                page.get_by_role("button", name="Etappen speichern").click()
                time.sleep(1)
                # Reload
                page.reload(wait_until="networkidle")
                time.sleep(2)
                loaded = page.locator('[data-testid="stage-start-time-field"] input[type="time"]')
                loaded.wait_for(state="visible", timeout=5000)
                assert loaded.input_value() == "15:00", (
                    f"start_time nicht persistiert: {loaded.input_value()}"
                )
            finally:
                if trip_id:
                    _delete_trip(page, trip_id)
                browser.close()


# ---------------------------------------------------------------------------
# AC-3: Startzeit bei Neu-Anlegen (/trips/new) persistieren
# ---------------------------------------------------------------------------

class TestAC3CreateFlowStartTime:
    """
    AC-3: GIVEN /trips/new Wegpunkte-Tab / WHEN start_time=15:00 gesetzt + Tour angelegt /
    THEN nach Laden: start_time=15:00 erhalten.
    RED: Feld im /trips/new Wegpunkte-Tab fehlt → TimeoutError.
    """

    def test_start_time_preserved_via_create_flow(self):
        """Playwright-E2E: start_time im Anlege-Wizard überlebt POST."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            try:
                _login(page)
                page.goto(f"{BASE}/trips/new", wait_until="networkidle")
                time.sleep(2)
                # Route-Tab: Name + Startdatum
                name_val = f"TDD-675-create-{uuid.uuid4().hex[:6]}"
                name_inp = page.locator("input[name='name']").or_(
                    page.locator("input[placeholder*='name' i]").first
                )
                name_inp.fill(name_val)
                page.locator("input[type='date']").first.fill("2026-08-01")
                # Wegpunkte-Tab aktivieren
                wp_tab = page.get_by_role("tab", name="Wegpunkte")
                wp_tab.click()
                time.sleep(1)
                # RED: stage-start-time-field im /trips/new fehlt → TimeoutError
                time_input = page.locator('[data-testid="stage-start-time-field"] input[type="time"]')
                time_input.wait_for(state="visible", timeout=5000)
                time_input.fill("15:00")
                # Tour anlegen
                page.get_by_role("button", name="Tour anlegen").click()
                page.wait_for_url(re.compile(r"/trips/"), timeout=15000)
                time.sleep(2)
                # Feld nach Anlegen: 15:00 erhalten?
                loaded = page.locator('[data-testid="stage-start-time-field"] input[type="time"]')
                loaded.wait_for(state="visible", timeout=5000)
                assert loaded.input_value() == "15:00", (
                    f"start_time ging im Create-Payload verloren: {loaded.input_value()}"
                )
            finally:
                browser.close()


# ---------------------------------------------------------------------------
# AC-4: Leeres Feld → Default 08:00
# ---------------------------------------------------------------------------

class TestAC4EmptyStartTimeDefault:
    """
    AC-4: GIVEN start_time=15:00 gesetzt / WHEN Feld geleert + gespeichert + Reload /
    THEN erste Ankunftszeit = 08:xx (Default).
    RED: Feld nicht vorhanden → TimeoutError.
    """

    def test_empty_start_time_falls_back_to_default(self):
        """Playwright-E2E: geleerte Startzeit → Ankünfte ab 08:xx."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            trip_id = None
            try:
                _login(page)
                trip_id, stage_id = _create_trip(page, "ac4")
                # start_time vorab via API auf 15:00 setzen
                trip_resp = page.request.get(f"{BASE}/api/trips/{trip_id}")
                trip_data = trip_resp.json()
                trip_data["stages"][0]["start_time"] = "15:00"
                page.request.put(
                    f"{BASE}/api/trips/{trip_id}",
                    data=json.dumps(trip_data),
                    headers={"Content-Type": "application/json"},
                )
                page.goto(f"{BASE}/trips/{trip_id}/edit", wait_until="networkidle")
                time.sleep(2)
                # RED: Feld nicht vorhanden → TimeoutError
                time_input = page.locator('[data-testid="stage-start-time-field"] input[type="time"]')
                time_input.wait_for(state="visible", timeout=5000)
                # Feld leeren und speichern
                time_input.fill("")
                page.get_by_role("button", name="Etappen speichern").click()
                time.sleep(1)
                page.reload(wait_until="networkidle")
                time.sleep(2)
                # Erste Ankunft muss mit "08:" beginnen
                first_arrival = page.locator('[data-testid="wp-arrival-0"]')
                first_arrival.wait_for(state="visible", timeout=5000)
                arrival_text = first_arrival.text_content() or ""
                assert arrival_text.startswith("08:"), (
                    f"Default-Startzeit 08:00 nicht wiederhergestellt, Ankunft: {arrival_text!r}"
                )
            finally:
                if trip_id:
                    _delete_trip(page, trip_id)
                browser.close()


# ---------------------------------------------------------------------------
# AC-5: Mobile-Parität (≤899px, Viewport 375px)
# ---------------------------------------------------------------------------

class TestAC5MobileStartTimeField:
    """
    AC-5: GIVEN Viewport 375px / WHEN Etappe mit WP geöffnet /
    THEN data-testid="stage-start-time-field" sichtbar.
    RED: Widget fehlt im Mobile-Markup → TimeoutError.
    """

    def test_start_time_field_visible_mobile(self):
        """Playwright-E2E 375px: Startzeit-Feld im Mobile-Editor sichtbar."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 375, "height": 812})
            trip_id = None
            try:
                _login(page)
                trip_id, _ = _create_trip(page, "ac5")
                page.goto(f"{BASE}/trips/{trip_id}/edit", wait_until="networkidle")
                time.sleep(2)
                # RED: Widget fehlt im Mobile-Markup → TimeoutError
                page.locator('[data-testid="stage-start-time-field"]').wait_for(
                    state="visible", timeout=5000
                )
            finally:
                if trip_id:
                    _delete_trip(page, trip_id)
                browser.close()


# ---------------------------------------------------------------------------
# AC-6: Kein Start-Zeit-Feld bei Pausentag
# ---------------------------------------------------------------------------

class TestAC6NoPauseStartTime:
    """
    AC-6: GIVEN normaler Wandertag + Pausentag / WHEN normale Etappe aktiv /
    THEN stage-start-time-field sichtbar; WHEN Pausentag aktiv /
    THEN kein stage-start-time-field.
    RED: Bei normaler Etappe fehlt das Feld → TimeoutError.
    """

    def test_no_start_time_field_on_pause_day(self):
        """Playwright-E2E: Startzeit-Feld nur bei normaler Etappe, nicht bei Pausentag."""
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            trip_id = None
            try:
                _login(page)
                trip_id, _ = _create_trip(page, "ac6", with_pause=True)
                page.goto(f"{BASE}/trips/{trip_id}/edit", wait_until="networkidle")
                time.sleep(2)
                # Wandertag (Index 0) muss Feld zeigen [RED: fehlt → TimeoutError]
                page.locator('[data-testid="stage-card-0"]').click()
                time.sleep(1)
                page.locator('[data-testid="stage-start-time-field"]').wait_for(
                    state="visible", timeout=5000
                )
                # Auf Pausentag (Index 1) wechseln: kein Feld erwartet
                page.locator('[data-testid="stage-card-pause-1"]').click()
                time.sleep(1)
                assert not page.locator('[data-testid="stage-start-time-field"]').is_visible(), (
                    "stage-start-time-field darf bei Pausentag nicht sichtbar sein"
                )
            finally:
                if trip_id:
                    _delete_trip(page, trip_id)
                browser.close()
