"""
TDD-Tests fuer Issue #128 — Etappen-Reihenfolge per Pfeil-Buttons aendern.

Spec: docs/specs/tests/stage_reorder_tests.md
Feature-Spec: docs/specs/feature/stage_reorder.md

Tests laufen gegen den deployed SvelteKit-Frontend-Server + Go-Backend
(Default: Staging, ueberschreibbar per GZ_TEST_BASE_URL). KEINE MOCKS.

Tests legen pro Lauf einen frischen Test-Trip via API an, manipulieren
ihn ueber die echte UI mit Playwright und loeschen den Trip im finally.
Bestandsdaten bleiben unangetastet.

Vor dem Fix: beide Tests schlagen fehl (Buttons / Selektoren existieren
nicht). Nach dem Fix: beide gruen.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import httpx
import pytest
from playwright.async_api import async_playwright

BASE_URL = os.getenv("GZ_TEST_BASE_URL", "https://staging.gregor20.henemm.com").rstrip("/")
USER = os.getenv("GZ_TEST_USER", "default")
PASS = os.getenv("GZ_TEST_PASS")
TIMEOUT = 10.0

# Issue #355: echte Live-Server-/Login-Tests (httpx + Playwright gegen Staging).
# Vom Default-Offline-Lauf (addopts = -m 'not email and not live') ausgeschlossen;
# explizit ausfuehrbar mit `-m live` + GZ_TEST_PASS gegen Staging.
pytestmark = pytest.mark.live


def _login(client: httpx.Client) -> None:
    if not PASS:
        pytest.fail(
            "GZ_TEST_PASS env var required. "
            "Beispiel: GZ_TEST_PASS='...' uv run pytest tests/tdd/test_stage_reorder.py"
        )
    r = client.post("/api/auth/login", json={"username": USER, "password": PASS})
    if r.status_code != 200:
        pytest.fail(f"Login failed: HTTP {r.status_code}, body={r.text!r}")


def _create_test_trip(client: httpx.Client) -> str:
    """Legt einen Test-Trip mit 3 Etappen an, gibt Trip-ID zurueck."""
    trip_id = uuid.uuid4().hex[:8]
    trip: dict[str, Any] = {
        "id": trip_id,
        "name": f"stage-reorder-test-{trip_id}",
        "stages": [
            {
                "id": "a",
                "name": "Alpha",
                "date": "2026-06-01",
                "waypoints": [
                    {"id": "p1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 1000},
                ],
            },
            {
                "id": "b",
                "name": "Bravo",
                "date": "2026-06-02",
                "waypoints": [
                    {"id": "p2", "name": "Start", "lat": 47.1, "lon": 11.1, "elevation_m": 1100},
                ],
            },
            {
                "id": "c",
                "name": "Charlie",
                "date": "2026-06-03",
                "waypoints": [
                    {"id": "p3", "name": "Start", "lat": 47.2, "lon": 11.2, "elevation_m": 1200},
                ],
            },
        ],
    }
    r = client.post("/api/trips", json=trip)
    if r.status_code not in (200, 201):
        pytest.fail(f"Trip create failed: HTTP {r.status_code} body={r.text!r}")
    return r.json()["id"]


def _delete_trip(client: httpx.Client, trip_id: str) -> None:
    try:
        client.delete(f"/api/trips/{trip_id}")
    except Exception:
        pass


async def _run_move_down_persists() -> None:
    """
    GIVEN: Trip mit 3 Etappen [Alpha, Bravo, Charlie] im Edit-Dialog
    WHEN:  User klickt 'runter' bei Alpha (idx 0), dann Speichern
    THEN:  Direkte DOM-Reihenfolge: [Bravo, Alpha, Charlie]
           Nach API-Reload: persistente Reihenfolge [Bravo, Alpha, Charlie]
           Wegpunkt-IDs aller Etappen unveraendert
    """
    client = httpx.Client(base_url=BASE_URL, follow_redirects=True, timeout=TIMEOUT)
    _login(client)
    trip_id = _create_test_trip(client)
    cookie = client.cookies.get("gz_session")
    assert cookie, "Session-Cookie fehlt nach Login"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            from urllib.parse import urlparse
            host = urlparse(BASE_URL).hostname or "localhost"
            await ctx.add_cookies([{
                "name": "gz_session",
                "value": cookie,
                "domain": host,
                "path": "/",
            }])
            page = await ctx.new_page()
            await page.goto(f"{BASE_URL}/trips/{trip_id}/edit")
            await page.wait_for_load_state("networkidle")

            # Initiale Reihenfolge
            initial = await page.eval_on_selector_all(
                'input[placeholder="Etappenname"]',
                "els => els.map(e => e.value)",
            )
            assert initial == ["Alpha", "Bravo", "Charlie"], (
                f"Initiale Reihenfolge unerwartet: {initial}"
            )

            # Klick 'runter' bei Etappe 0
            await page.click('[data-testid="stage-move-down-0"]', timeout=5000)

            # DOM-Reihenfolge nach Klick
            after = await page.eval_on_selector_all(
                'input[placeholder="Etappenname"]',
                "els => els.map(e => e.value)",
            )
            assert after == ["Bravo", "Alpha", "Charlie"], (
                f"Reihenfolge nach Klick falsch: {after}"
            )

            # Speichern
            await page.click('button:has-text("Speichern")', timeout=5000)
            # Nach Speichern wechselt Edit-Dialog typisch zu /trips
            await page.wait_for_url(f"{BASE_URL}/trips", timeout=8000)
            await browser.close()

        # Persistenz-Check via API
        r = client.get(f"/api/trips/{trip_id}")
        assert r.status_code == 200
        data = r.json()
        names = [s["name"] for s in data["stages"]]
        assert names == ["Bravo", "Alpha", "Charlie"], (
            f"Persistierte Reihenfolge falsch: {names}"
        )

        # Wegpunkt-IDs unveraendert (keine Datenverluste)
        wps = {s["name"]: [w["id"] for w in s["waypoints"]] for s in data["stages"]}
        assert wps["Alpha"] == ["p1"], f"Alpha Wegpunkte: {wps['Alpha']}"
        assert wps["Bravo"] == ["p2"], f"Bravo Wegpunkte: {wps['Bravo']}"
        assert wps["Charlie"] == ["p3"], f"Charlie Wegpunkte: {wps['Charlie']}"
    finally:
        _delete_trip(client, trip_id)
        client.close()


async def _run_disabled_at_edges() -> None:
    """
    GIVEN: Trip mit 3 Etappen
    WHEN:  Edit-Seite gerendert
    THEN:  Erster 'hoch'-Button und letzter 'runter'-Button disabled
    """
    client = httpx.Client(base_url=BASE_URL, follow_redirects=True, timeout=TIMEOUT)
    _login(client)
    trip_id = _create_test_trip(client)
    cookie = client.cookies.get("gz_session")
    assert cookie, "Session-Cookie fehlt nach Login"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            from urllib.parse import urlparse
            host = urlparse(BASE_URL).hostname or "localhost"
            await ctx.add_cookies([{
                "name": "gz_session",
                "value": cookie,
                "domain": host,
                "path": "/",
            }])
            page = await ctx.new_page()
            await page.goto(f"{BASE_URL}/trips/{trip_id}/edit")
            await page.wait_for_load_state("networkidle")

            up0 = await page.locator('[data-testid="stage-move-up-0"]').is_disabled()
            assert up0, "Erster 'hoch'-Button muss disabled sein"

            down_last = await page.locator('[data-testid="stage-move-down-2"]').is_disabled()
            assert down_last, "Letzter 'runter'-Button muss disabled sein"

            await browser.close()
    finally:
        _delete_trip(client, trip_id)
        client.close()


def test_stage_reorder_move_down_persists() -> None:
    asyncio.run(_run_move_down_persists())


def test_stage_reorder_disabled_at_edges() -> None:
    asyncio.run(_run_disabled_at_edges())
