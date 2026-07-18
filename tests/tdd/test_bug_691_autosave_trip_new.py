"""
TDD RED — Bug #691: Trip-New Auto-Save bei Navigation weg

Spec: docs/specs/modules/bug_691_autosave_trip_new.md
Workflow: bug-691-autosave-trip-new

Verhaltenstests gegen Staging (einmaliger Login via shared browser context):
- AC-7: Playwright → Button heißt "Trip speichern" (nicht "Tour speichern")
- AC-1: Playwright → Navigation weg → Trip wird auto-gespeichert (erscheint in Liste)
- AC-4: Playwright → Abbrechen löst keinen Auto-Save aus

RED-Ursache:
- AC-7: Button-Text ist "Tour speichern" statt "Trip speichern"
- AC-1: beforeNavigate-Hook fehlt → kein Auto-Save → Trip erscheint NICHT in Liste
- AC-4: tbd nach AC-1-Fix (aktuell: kein Auto-Save beim Cancel ebenfalls nicht)

KEINE MOCKS — Playwright gegen Staging, einmaliger Login via Session-Fixture.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import httpx
import pytest

# Dialt real gegen Staging/Prod (#1211 Scheibe 2a) -- nur via -m staging ausfuehren.
pytestmark = pytest.mark.staging

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING_BASE = os.environ.get("GZ_SVELTE_BASE", "https://staging.gregor20.henemm.com")
GO_STAGING_BASE = os.environ.get("GZ_API_STAGING_BASE", "http://localhost:8091")
GPX_FIXTURE = REPO_ROOT / "frontend/e2e/fixtures/test-trip.gpx"

# Dedizierter Staging-Testnutzer für #691 (erstellt auf Staging per Register-API)
TEST_USER = os.environ.get("GZ_TEST_691_USER", "tdd-691-test")
TEST_PASS = os.environ.get("GZ_TEST_691_PASS", "tdd691pass!")


# ---------------------------------------------------------------------------
# Module-scoped Playwright-Fixture (einmaliger Login)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pw_session():
    """
    Startet einmalig Playwright mit cookie-injizierter Session (kein Login-Form-Aufruf).

    Strategie: httpx holt Session-Cookie von der Staging-API direkt (1 Token).
    Playwright injiziert den Cookie in den Browser-Kontext → keine zweite Login-Anfrage.
    Damit wird der Rate-Limit-Token nur einmal verbraucht.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright nicht installiert")

    # Cookie per direkter API-Anfrage holen (umgeht nginx → eigener Rate-Limit-Bucket)
    # Alternativ: Umgebungsvariable GZ_TEST_691_COOKIE vorab setzen
    cookie_value = os.environ.get("GZ_TEST_691_COOKIE", "")
    if not cookie_value:
        try:
            resp = httpx.post(
                f"{GO_STAGING_BASE}/api/auth/login",
                json={"username": TEST_USER, "password": TEST_PASS},
                timeout=10,
            )
            if resp.status_code == 429:
                pytest.skip("Rate-Limit — bitte 2 Minuten warten und erneut ausführen.")
            if resp.status_code != 200:
                pytest.skip(f"Login fehlgeschlagen ({resp.status_code})")
            sc = resp.headers.get("set-cookie", "")
            m = re.search(r"gz_session=([^;]+)", sc)
            if not m:
                pytest.skip("Kein gz_session-Cookie in Login-Antwort")
            cookie_value = m.group(1)
        except Exception as e:
            pytest.skip(f"Staging-API nicht erreichbar: {e}")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            base_url=STAGING_BASE,
        )
        # Cookie direkt injizieren — kein Login-Form nötig
        context.add_cookies([{
            "name": "gz_session",
            "value": cookie_value,
            "domain": STAGING_BASE.replace("https://", ""),
            "path": "/",
            "httpOnly": True,
            "secure": True,
        }])
        page = context.new_page()

        # Prüfen ob Cookie gültig ist
        page.goto(f"{STAGING_BASE}/trips/new")
        if "/login" in page.url:
            pytest.skip("Cookie ungültig oder abgelaufen.")

        yield page


def _trip_count_via_api(username: str = TEST_USER, password: str = TEST_PASS) -> int:
    """Anzahl der Trips des Test-Nutzers via Staging Go-API (kein Login-Rate-Limit
    da API direkt auf localhost erreichbar ist)."""
    try:
        client = httpx.Client(base_url=GO_STAGING_BASE, timeout=10)
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        if resp.status_code != 200:
            return -1
        sc = resp.headers.get("set-cookie", "")
        m = re.search(r"gz_session=([^;]+)", sc)
        if not m:
            return -1
        client.cookies.set("gz_session", m.group(1))
        trips_resp = client.get("/api/trips")
        if trips_resp.status_code != 200:
            return -1
        return len(trips_resp.json())
    except Exception:
        return -1


# ---------------------------------------------------------------------------
# AC-7: Desktop-Save-Button heißt "Trip speichern"
# ---------------------------------------------------------------------------

class TestAC7_SaveButtonLabel:
    """
    AC-7: Desktop-Button soll "Trip speichern" heißen (nicht "Tour speichern").

    RED: Button-Text ist aktuell "Tour speichern".
    """

    def test_save_button_heisst_trip_speichern(self, pw_session):
        """
        GIVEN: /trips/new geladen (authentifiziert)
        WHEN: Desktop-Save-Button gerendert (ohne Aktion)
        THEN: Button-Text ist "Trip speichern"

        RED: Schlägt fehl weil Button aktuell "Tour speichern" zeigt.
        """
        page = pw_session
        page.goto(f"{STAGING_BASE}/trips/new")
        page.wait_for_selector('[data-testid="trip-new-save-btn"]', timeout=15_000)

        btn_text = page.locator('[data-testid="trip-new-save-btn"]').inner_text()
        assert btn_text.strip() == "Trip speichern", (
            f"RED — Button-Text ist '{btn_text.strip()}', erwartet 'Trip speichern'. "
            f"Bug #691: Button-Label noch nicht auf 'Trip speichern' umgestellt."
        )


# ---------------------------------------------------------------------------
# AC-1: Auto-Save bei Navigation weg (voller E2E-Flow)
# ---------------------------------------------------------------------------

class TestAC1_AutoSaveOnNavigation:
    """
    AC-1: Wenn Nutzer alle Pflicht-Tabs durchläuft und dann auf "im Account einrichten"
    klickt, muss der Trip automatisch gespeichert werden.

    RED: beforeNavigate-Hook fehlt → Trip wird NICHT gespeichert.
    """

    def test_autosave_wenn_weg_navigiert(self, pw_session):
        """
        GIVEN: Nutzer füllt /trips/new vollständig aus (Route + Etappen GPX +
               Metriken + Zeitplan besucht → ready=true)
        WHEN:  Klick auf Link "im Account einrichten" (navigiert zu /account)
        THEN:  Trip erscheint in der Trip-Liste (wurde auto-gespeichert)

        RED: Schlägt fehl weil kein beforeNavigate → Trip-Liste wächst nicht.
        """
        if not GPX_FIXTURE.exists():
            pytest.skip(f"GPX-Fixture fehlt: {GPX_FIXTURE}")

        page = pw_session
        trip_name = f"691-autosave-test-{int(time.time())}"

        # Trip-Anzahl vor dem Test
        count_before = _trip_count_via_api()

        # 1. /trips/new öffnen
        page.goto(f"{STAGING_BASE}/trips/new")
        page.wait_for_selector('[data-testid="trip-new-name-input"]', timeout=15_000)

        # 2. Route-Tab: Name + Startdatum
        page.fill('[data-testid="trip-new-name-input"]', trip_name)
        page.locator('.tn-desktop input[type="date"]').first.fill("2026-07-15")
        page.wait_for_timeout(300)

        # 3. Etappen-Tab: GPX hochladen
        etappen_tab = page.locator('div[role="tab"]:has-text("Etappen")').first
        etappen_tab.click()
        page.wait_for_timeout(500)

        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(str(GPX_FIXTURE))
        page.wait_for_timeout(2_000)

        # 4. Metriken-Tab besuchen (setzt wtVisited=true)
        metriken_tab = page.locator('div[role="tab"]:has-text("Wetter-Metriken")').first
        metriken_tab.wait_for(state="visible", timeout=5_000)
        metriken_tab.click()
        page.wait_for_timeout(500)

        # 5. Zeitplan-Tab besuchen (setzt ztVisited=true → ready=true)
        zeitplan_tab = page.locator('div[role="tab"]:has-text("Briefing-Zeitplan")').first
        zeitplan_tab.wait_for(state="visible", timeout=5_000)
        zeitplan_tab.click()
        page.wait_for_timeout(500)

        # 6. "im Account einrichten"-Link klicken (navigiert zu /account)
        account_link = page.locator('a[href="/account"]:has-text("im Account einrichten")').first
        account_link.wait_for(state="visible", timeout=5_000)
        account_link.click()

        # Warte auf Navigation
        page.wait_for_timeout(3_000)

        # 7. Trip-Anzahl nach Wegnavigieren prüfen
        count_after = _trip_count_via_api()
        if count_before < 0 or count_after < 0:
            pytest.skip("Staging-API nicht erreichbar für Trip-Count-Prüfung")

        assert count_after > count_before, (
            f"RED — Trip wurde NICHT auto-gespeichert. "
            f"Trip-Anzahl vorher: {count_before}, nachher: {count_after}. "
            f"Bug #691: beforeNavigate-Hook fehlt → Trip geht beim Wegnavigieren verloren."
        )


# ---------------------------------------------------------------------------
# AC-4: Abbrechen löst keinen Auto-Save aus
# ---------------------------------------------------------------------------

class TestAC4_CancelKeinAutoSave:
    """
    AC-4: Klick auf "Abbrechen" soll keinen Auto-Save auslösen.
    Nach AC-1-Fix: intentionalCancel-Flag verhindert Auto-Save beim Cancel.
    """

    def test_abbrechen_loest_keinen_autosave_aus(self, pw_session):
        """
        GIVEN: Nutzer füllt Route-Tab aus (Name + Datum)
        WHEN:  Klick auf "Abbrechen"-Button
        THEN:  Kein neuer Trip wird angelegt (Trip-Anzahl unverändert)

        RED: Aktuell kein Auto-Save vorhanden → Test PASST (Trip-Anzahl unverändert).
        GRÜN nach Fix: intentionalCancel verhindert Auto-Save beim Cancel.
        (Test ist ein Sicherheitsnetz — verhindert Regression nach Implementation.)
        """
        page = pw_session
        count_before = _trip_count_via_api()

        page.goto(f"{STAGING_BASE}/trips/new")
        page.wait_for_selector('[data-testid="trip-new-name-input"]', timeout=15_000)

        # Route-Tab teilweise ausfüllen
        page.fill('[data-testid="trip-new-name-input"]', f"691-cancel-test-{int(time.time())}")
        page.locator('.tn-desktop input[type="date"]').first.fill("2026-07-15")
        page.wait_for_timeout(300)

        # Abbrechen klicken
        page.locator('button:has-text("Abbrechen")').first.click()
        page.wait_for_url(f"{STAGING_BASE}/trips", timeout=10_000)
        page.wait_for_timeout(1_000)

        count_after = _trip_count_via_api()
        if count_before < 0 or count_after < 0:
            pytest.skip("Staging-API nicht erreichbar")

        assert count_after == count_before, (
            f"REGRESSION — Cancel hat einen Trip angelegt! "
            f"Vorher: {count_before}, nachher: {count_after}. "
            f"Abbrechen darf keinen Auto-Save auslösen (AC-4)."
        )
