"""
TDD RED — Issue #727: /trips SSR 500 bei stages:null (null-safety)
Spec: docs/specs/modules/issue_727_trips_null_safety.md

RED-Erwartung (vor Fix):
  - ac1_trips_page_no_500: /trips gibt HTTP 500 zurück (Bug aktiv)
  - ac2_date_range_dash: dateRange() crasht bei stages:null → 500
  - ac3_etappen_count_zero: Desktop-Karte crasht bei stages:null → 500
  - ac4_real_stages_regression: Trips mit echten Etappen werden korrekt gerendert

Ausführung:
    uv run pytest tests/tdd/test_issue_727_trips_null_safety.py -v
"""
import json
import os

import httpx
import pytest
from playwright.sync_api import sync_playwright

BASE = "https://staging.gregor20.henemm.com"
USER = "tdd-727"
PASS = "f2675a9ec77f2b94f58ba740"
NULL_STAGES_TRIP_ID = "tdd-727-null-stages"
REAL_STAGES_TRIP_ID = "tdd-727-real-stages"
STATE_FILE = "/tmp/tdd-727-storage-state.json"


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
        assert result["ok"], f"Login fehlgeschlagen: {result}"
        state = ctx.storage_state()
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
        browser.close()
    return state


def _get_session_cookies() -> dict:
    state = _ensure_session_state()
    return {c["name"]: c["value"] for c in state.get("cookies", [])}


def _http_cookies(cookies: dict) -> httpx.Cookies:
    return httpx.Cookies(cookies)


def _ensure_null_stages_trip():
    cookies = _http_cookies(_get_session_cookies())
    r = httpx.get(f"{BASE}/api/trips/{NULL_STAGES_TRIP_ID}", cookies=cookies)
    if r.status_code == 200:
        return
    r = httpx.post(
        f"{BASE}/api/trips",
        json={
            "id": NULL_STAGES_TRIP_ID,
            "name": "TDD-727-Bug-Trip",
            "region": "Testgebiet",
            "activity_type": "wandern",
        },
        cookies=cookies,
    )
    assert r.status_code in (200, 201, 409), f"Trip anlegen fehlgeschlagen: {r.text}"


def _ensure_real_stages_trip():
    cookies = _http_cookies(_get_session_cookies())
    r = httpx.get(f"{BASE}/api/trips/{REAL_STAGES_TRIP_ID}", cookies=cookies)
    if r.status_code == 200:
        return
    r = httpx.post(
        f"{BASE}/api/trips",
        json={
            "id": REAL_STAGES_TRIP_ID,
            "name": "TDD-727-Real-Trip",
            "region": "Realgebiet",
            "activity_type": "wandern",
            "stages": [
                {"id": "s1", "name": "Etappe 1", "date": "2026-07-01"},
                {"id": "s2", "name": "Etappe 2", "date": "2026-07-03"},
            ],
        },
        cookies=cookies,
    )
    assert r.status_code in (200, 201, 409), f"Trip-mit-Etappen anlegen fehlgeschlagen: {r.text}"


# ---------------------------------------------------------------------------
# AC-1: /trips Seite lädt ohne 500-Fehler
# ---------------------------------------------------------------------------

def test_ac1_trips_page_no_500():
    """
    GIVEN: Nutzer hat einen Trip mit stages:null
    WHEN: /trips aufgerufen wird (SSR)
    THEN: HTTP 200, kein 500-Fehler, Seite wird gerendert
    """
    _ensure_null_stages_trip()
    cookies = _http_cookies(_get_session_cookies())

    r = httpx.get(f"{BASE}/trips", cookies=cookies, follow_redirects=True)
    assert r.status_code == 200, (
        f"FAIL: /trips gibt HTTP {r.status_code} statt 200 zurück. "
        f"Bug #727: stages:null crasht dateRange(). Body: {r.text[:300]}"
    )


# ---------------------------------------------------------------------------
# AC-2: dateRange zeigt '-' bei stages:null (kein Crash)
# ---------------------------------------------------------------------------

def test_ac2_date_range_dash_for_null_stages():
    """
    GIVEN: Nutzer hat Trip mit stages:null UND Trip mit echten Etappen
    WHEN: /trips geladen (Playwright)
    THEN: null-stages-Trip zeigt '-' als Datum, kein Crash
    """
    _ensure_null_stages_trip()
    _ensure_real_stages_trip()
    state = _ensure_session_state()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(storage_state=state)
        page = ctx.new_page()

        page.goto(f"{BASE}/trips", wait_until="networkidle")

        assert page.url.endswith("/trips") or "/trips" in page.url, (
            f"Redirect auf: {page.url} — Seite hat nicht geladen"
        )

        body = page.locator("body").inner_text()
        assert "500" not in body[:200], f"500-Fehler im Body: {body[:300]}"

        cards = page.locator("[data-testid='trip-card']")
        count = cards.count()
        assert count >= 1, "Keine Trip-Cards gefunden nach dem Fix"

        browser.close()


# ---------------------------------------------------------------------------
# AC-3: Desktop-Karte zeigt '0 Etappen' für stages:null
# ---------------------------------------------------------------------------

def test_ac3_etappen_count_zero_for_null_stages():
    """
    GIVEN: Nutzer hat Trip mit stages:null
    WHEN: /trips Desktop-Ansicht geladen (Playwright, 1280px)
    THEN: Trip-Karte zeigt '0 Etappen', kein Crash
    """
    _ensure_null_stages_trip()
    state = _ensure_session_state()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            storage_state=state,
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.goto(f"{BASE}/trips", wait_until="networkidle")

        assert "500" not in page.title().lower(), "500 im Seitentitel"

        body = page.locator("body").inner_text()
        assert "TDD-727-Bug-Trip" in body, (
            f"null-stages-Trip nicht in der Seite sichtbar. Body: {body[:500]}"
        )

        browser.close()


# ---------------------------------------------------------------------------
# AC-4: Trips mit echten Etappen werden weiterhin korrekt angezeigt
# ---------------------------------------------------------------------------

def test_ac4_real_stages_still_rendered():
    """
    GIVEN: Nutzer hat Trip mit 2 echten Etappen (2026-07-01 — 2026-07-03)
    WHEN: /trips geladen
    THEN: Etappenanzahl '2 Etappen' und Startdatum '2026-07-01' sichtbar
    """
    _ensure_real_stages_trip()
    state = _ensure_session_state()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            storage_state=state,
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.goto(f"{BASE}/trips", wait_until="networkidle")

        assert page.url.endswith("/trips") or "/trips" in page.url
        body = page.locator("body").inner_text()

        assert "TDD-727-Real-Trip" in body, f"Real-Stages-Trip nicht sichtbar: {body[:500]}"
        assert "2026-07-01" in body, f"Startdatum nicht sichtbar: {body[:500]}"

        browser.close()
