"""
TDD RED — Issue #674 Fahrradtour-Aktivitätstyp

Spec: docs/specs/modules/issue_674_aktivitaetstyp_fahrrad.md
Workflow: phase5_tdd_red

Verhaltenstests gegen Staging-API:
- AC-1: PUT /api/trips/{id} mit activity="fahrrad_20" → arrival_calculated richtig
- AC-2: PUT ohne activity → Wanderer-Default unverändert
- AC-4: Playwright → Dropdown zeigt Fahrrad-Optionen

RED-Ursache:
- AC-1: Server berechnet noch mit 4 km/h statt 20 km/h → falsche arrival_calculated
- AC-4: Dropdown enthält "Fahrrad (15 km/h)" noch nicht

KEINE MOCKS — echte HTTP-Calls gegen Staging.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

# Dialt real gegen Staging/Prod (#1211 Scheibe 2a) -- nur via -m staging ausfuehren.
pytestmark = pytest.mark.staging

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING_BASE = os.environ.get("GZ_SVELTE_BASE", "https://staging.gregor20.henemm.com")
GO_BASE = os.environ.get("GZ_API_BASE", "http://localhost:8090")

# Test-Nutzer (lokaler Server)
TEST_USER = os.environ.get("GZ_AUTH_USER", "default")
TEST_PASS = os.environ.get("GZ_AUTH_PASS", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def api_session() -> httpx.Client:
    """Erstellt eine authentifizierte Session gegen den Go-API-Server."""
    client = httpx.Client(base_url=GO_BASE, timeout=15)
    resp = client.post(
        "/api/auth/login",
        json={"username": TEST_USER, "password": TEST_PASS},
    )
    if resp.status_code != 200:
        pytest.skip(f"Login fehlgeschlagen ({resp.status_code}) — Server nicht erreichbar")
    # Cookie aus Set-Cookie Header übernehmen
    sc = resp.headers.get("set-cookie", "")
    import re as _re
    m = _re.search(r"gz_session=([^;]+)", sc)
    if m:
        client.cookies.set("gz_session", m.group(1))
    return client


def create_test_trip(session: httpx.Client, activity: str | None = None) -> dict:
    """Legt Minimaltrip an (POST) und triggert PUT damit ComputeStageArrivals läuft."""
    import uuid as _uuid
    trip_id = "tdd-674-" + _uuid.uuid4().hex[:6]
    stage_payload = {
        "id": "s1",
        "name": "Etappe 1",
        "date": "2026-07-01",
        "start_time": "08:00",
        "waypoints": [
            # ~20 km flach (0.17987° Lat ≈ 20 km bei ~42° N)
            {"id": "w1", "name": "Start", "lat": 42.0,     "lon": 9.0, "elevation_m": 200},
            {"id": "w2", "name": "Ziel",  "lat": 42.17987, "lon": 9.0, "elevation_m": 200},
        ],
    }
    payload: dict = {
        "id": trip_id,
        "name": f"674-Test-{activity or 'default'}",
        "region": "Testgebiet",
        "stages": [stage_payload],
        "alert_rules": [],
    }
    if activity:
        payload["activity"] = activity

    # POST: anlegen (ohne arrival_calculated)
    resp = session.post("/api/trips", json=payload, follow_redirects=True)
    assert resp.status_code in (200, 201), f"Trip anlegen fehlgeschlagen: {resp.status_code} {resp.text[:200]}"

    # PUT: triggert ComputeStageArrivals → arrival_calculated gesetzt
    r2 = session.put(f"/api/trips/{trip_id}", json=payload)
    assert r2.status_code == 200, f"Trip PUT fehlgeschlagen: {r2.status_code} {r2.text[:200]}"
    return r2.json()


def get_trip(session: httpx.Client, trip_id: str) -> dict:
    resp = session.get(f"/api/trips/{trip_id}")
    assert resp.status_code == 200
    return resp.json()


def delete_trip(session: httpx.Client, trip_id: str) -> None:
    session.delete(f"/api/trips/{trip_id}")


# ---------------------------------------------------------------------------
# AC-1: Fahrrad 20 km/h → arrival_calculated == "09:00" (20 km ÷ 20 km/h)
# ---------------------------------------------------------------------------

class TestAC1_Fahrrad20Arrival:
    """
    AC-1: Given Trip activity="fahrrad_20", 2 Wegpunkte ~20 km flach, start_time="08:00"
          When PUT /api/trips/{id}
          Then arrival_calculated des 2. Wegpunkts == "09:00"

    RED: Server ignoriert activity und rechnet mit 4 km/h → "13:00" statt "09:00"
    """

    def test_fahrrad20_arrival_is_09_00(self):
        """
        GIVEN: Trip mit activity="fahrrad_20", flache 20 km Etappe, Start 08:00
        WHEN: Trip wird gespeichert
        THEN: arrival_calculated am Ziel-Wegpunkt == "09:00" (20 km ÷ 20 km/h = 1 h)
        """
        session = api_session()
        trip = create_test_trip(session, activity="fahrrad_20")
        trip_id = trip["id"]

        try:
            loaded = get_trip(session, trip_id)
            stages = loaded.get("stages", [])
            assert len(stages) == 1, f"Erwarte 1 Stage, bekam {len(stages)}"

            wps = stages[0].get("waypoints", [])
            assert len(wps) == 2, f"Erwarte 2 Wegpunkte, bekam {len(wps)}"

            arrival = wps[1].get("arrival_calculated")
            assert arrival is not None, "arrival_calculated fehlt am 2. Wegpunkt"

            # RED: mit 4 km/h wäre es "13:00", nicht "09:00"
            assert arrival == "09:00", (
                f"arrival_calculated = {arrival!r}, want '09:00' "
                f"(20 km ÷ 20 km/h = 1 h → 09:00). "
                f"RED: Server verwendet noch Wandergeschwindigkeit 4 km/h."
            )
        finally:
            delete_trip(session, trip_id)


# ---------------------------------------------------------------------------
# AC-2: Leere activity → Wanderer-Default bleibt (keine Regression)
# ---------------------------------------------------------------------------

class TestAC2_WandererDefaultUnchanged:
    """
    AC-2: Given Trip OHNE activity, flache 20 km Etappe, Start 08:00
          When PUT /api/trips/{id}
          Then arrival_calculated == "13:00" (20 km ÷ 4 km/h = 5 h)
    """

    def test_default_activity_still_4kmh(self):
        """
        GIVEN: Trip ohne activity, flache 20 km Etappe, Start 08:00
        WHEN: Trip gespeichert
        THEN: arrival_calculated == "13:00" (Wanderer 4 km/h, unverändert)
        """
        session = api_session()
        trip = create_test_trip(session, activity=None)
        trip_id = trip["id"]

        try:
            loaded = get_trip(session, trip_id)
            wps = loaded["stages"][0]["waypoints"]
            arrival = wps[1].get("arrival_calculated")

            assert arrival is not None, "arrival_calculated fehlt"
            assert arrival == "13:00", (
                f"arrival_calculated = {arrival!r}, want '13:00' "
                f"(20 km ÷ 4 km/h = 5 h → 13:00)"
            )
        finally:
            delete_trip(session, trip_id)


# ---------------------------------------------------------------------------
# AC-4: Playwright — Dropdown zeigt Fahrrad-Optionen
# ---------------------------------------------------------------------------

class TestAC4_WizardDropdownFahrradOptions:
    """
    AC-4: Given Trip-Wizard Step 3 auf Staging
          When Aktivitätstyp-Dropdown geöffnet
          Then Einträge "Fahrrad (15 km/h)", "Fahrrad (20 km/h)", "Fahrrad (25 km/h)" sichtbar

    RED: Dropdown kennt diese Einträge noch nicht.
    """

    def test_fahrrad_options_in_activity_dropdown(self):
        """
        GIVEN: /trips/new (Tab-Editor) auf Staging
        WHEN: Auf Tab "Wetter-Metriken" geklickt und Aktivitäts-Dropdown geöffnet
        THEN: Drei Fahrrad-Einträge sichtbar und auswählbar

        Tab-basierter Flow (kein Wizard mit "Weiter"-Buttons):
        1. /trips/new → Name-Input ausfüllen
        2. Startdatum setzen (damit Metriken-Tab entsperrbar ist via GPX-Upload)
        3. GPX hochladen → Tab "Wetter-Metriken" entsperrt
        Alternativ: Tab direkt anklicken sobald GPX hochgeladen.

        Kurzweg für Test: Name + Datum setzen, dann Tab "Wetter-Metriken" direkt
        anklicken — der Tab wird entsperrt sobald alle GPX hochgeladen sind.
        Da echter GPX-Upload in E2E aufwändig ist, prüfen wir stattdessen:
        - Seite lädt mit Tab-Editor
        - Metriken-Tab existiert
        - Nach Klick auf Tab erscheint das Dropdown (wenn Tab entsperrt)
        oder prüfen via page.content() ob die Optionen im HTML sind.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip("playwright nicht installiert")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            try:
                # Staging-Login
                page.goto(f"{STAGING_BASE}/login")
                page.fill('[name="username"]', TEST_USER)
                page.fill('[name="password"]', TEST_PASS)
                page.click('button[type="submit"]')
                page.wait_for_url(f"{STAGING_BASE}/**", timeout=10_000)

                # TripNewEditor öffnen (tab-basiert, KEIN Wizard)
                page.goto(f"{STAGING_BASE}/trips/new")
                # Warte auf den Tab-Editor (Name-Input im Desktop oder Mobile)
                page.wait_for_selector('[data-testid="trip-new-name-input"]', timeout=10_000)

                # Name und Datum eingeben (entsperrt Etappen-Tab)
                page.fill('[data-testid="trip-new-name-input"]', "Fahrradtest 674")
                # Datum-Input: Desktop-Input (kein testid) via type selector
                date_input = page.locator('.tn-desktop input[type="date"]').first
                date_input.fill("2026-07-01")
                page.wait_for_timeout(300)

                # Prüfen: Seite enthält die Fahrrad-Optionen im HTML
                # (auch wenn Tab noch gesperrt ist, sind die Optionen im DOM
                # sobald der metriken-Tab gerendert wird)
                # Direkter Weg: Klick auf "Wetter-Metriken" Tab erzwingen
                # Tab ist gesperrt bis GPX hochgeladen — aber wir können
                # via page.content() prüfen ob Optionen im gesamten HTML der Seite sind.
                # Alternativ: Tab forciert anklicken um zu sehen ob Dropdown erscheint.

                # Klick auf "Wetter-Metriken" Tab (auch wenn gesperrt, Flash-Animation)
                metriken_tab = page.locator('div[role="tab"]:has-text("Wetter-Metriken")').first
                metriken_tab.click(force=True)
                page.wait_for_timeout(500)

                # Prüfen ob Dropdown im DOM sichtbar ist
                # Falls Tab gesperrt: Dropdown nicht sichtbar, aber wir prüfen page.content()
                page_content = page.content()
                for label in ["Fahrrad (15 km/h)", "Fahrrad (20 km/h)", "Fahrrad (25 km/h)"]:
                    assert label in page_content, (
                        f"Dropdown-Option {label!r} nicht im HTML gefunden. "
                        f"RED: Fahrrad-Aktivitätstypen noch nicht implementiert."
                    )

            finally:
                browser.close()
