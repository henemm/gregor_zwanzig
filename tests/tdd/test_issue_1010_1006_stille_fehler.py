"""TDD RED — Issues #1010 + #1006: Stille Fehler im Frontend.

#1010: `handleStartTimeChange` (EditStagesPanelNew.svelte:144, Issue #675)
aktualisiert nur den lokalen State — als einziger Änderungs-Handler des
Panels OHNE scheduleSave()/save(). Eine reine Startzeit-Änderung wird nie
gespeichert (PO-Datenverlust 2026-07-04, Logbelege in #1010).

#1006: `api.ts::request()` behandelt 401 (Sitzung nach 24h abgelaufen) nicht —
Aktionen aus offenen Tabs scheitern mit kryptischer Meldung bzw. versanden
still, statt zur Anmeldeseite mit klarem Hinweis zu führen.

RED: AC-1/AC-2 (kein Save-Trigger), AC-3/AC-4 (kein 401-Handling).

Mock-frei: echte Playwright-Läufe gegen Staging als eingeloggter Nutzer
(Nginx-Basic-Auth aus validator.env, App-Accounts via echtem Register/Login),
echte Trips über die echte API.

SPEC: docs/specs/modules/issue_1010_1006_stille_fehler.md
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

# Issue #1210 AC-1 Nebenwirkung: `_ui_login()` retried bis zu 3x mit
# sleep(15) (bis zu 2x pro Test, AC-6) -- legitim >30s, daher deklarierter
# Override statt Kollision mit dem neuen globalen ini-Timeout (30s).
pytestmark = pytest.mark.timeout(180)

_VALIDATOR_ENV = Path("/home/hem/gregor_zwanzig/.claude/validator.env")


def _load_validator_env() -> dict:
    env = {}
    for line in _VALIDATOR_ENV.read_text().splitlines():
        line = line.strip().removeprefix("export ").strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


_ENV = _load_validator_env()
BASE = _ENV.get("GZ_VALIDATION_URL", "https://staging.gregor20.henemm.com")
_HTTP_CREDS = {
    "username": _ENV["GZ_VALIDATOR_USER"],
    "password": _ENV["GZ_VALIDATOR_PASS"],
}
_APP_PASS = "tdd-1010-Pass!"
# Feste, vorab angelegte Staging-Testnutzer (data/users/… mit bcrypt-Hash) —
# das Staging-Register-Limit (5/h/IP, cmd/server/main.go:87) macht
# Frisch-Registrierung pro Testlauf unmöglich.
_USER_A = "tdd1010-usera"
_USER_B = "tdd1010-userb"


def _browser_context(p, viewport=None):
    browser = p.chromium.launch()
    ctx = browser.new_context(
        http_credentials=_HTTP_CREDS,
        viewport=viewport or {"width": 1440, "height": 900},
    )
    return browser, ctx




def _ui_login(page, username: str) -> None:
    """UI-Login mit Retry — Staging drosselt schnelle Login-Folgen (Rate-Limit)."""
    last_err = None
    for attempt in range(4):
        if attempt:
            time.sleep(15)
        try:
            page.goto(f"{BASE}/login", wait_until="networkidle")
            page.fill("input[name='username'], input[type='text']", username)
            page.fill("input[type='password']", _APP_PASS)
            page.click("button[type='submit']")
            page.wait_for_url(
                re.compile(r"^" + re.escape(BASE) + r"(?!/login)"), timeout=20000
            )
            return
        except Exception as e:  # noqa: BLE001 — Retry nur bei Nicht-Navigation
            last_err = e
    raise AssertionError(f"UI-Login für {username!r} nach 4 Versuchen erfolglos: {last_err}")


def _create_trip(ctx, prefix: str) -> str:
    trip_id = f"tdd-{prefix}-{uuid.uuid4().hex[:6]}"
    payload = {
        "id": trip_id,
        "name": f"TDD 1010 {prefix} {trip_id}",
        "stages": [{
            "id": uuid.uuid4().hex[:8],
            "name": "Wandertag",
            "date": "2026-08-10",
            "waypoints": [
                {"id": uuid.uuid4().hex[:8], "name": "Start",
                 "lat": 47.2692, "lon": 11.4041, "elevation_m": 600},
                {"id": uuid.uuid4().hex[:8], "name": "Ziel",
                 "lat": 47.2820, "lon": 11.4230, "elevation_m": 700},
            ],
        }],
    }
    resp = ctx.request.post(
        f"{BASE}/api/trips",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 201, f"Trip-Create: {resp.status} {resp.text()[:200]}"
    return trip_id


def _delete_trip(ctx, trip_id: str) -> None:
    try:
        ctx.request.delete(f"{BASE}/api/trips/{trip_id}")
    except Exception:
        pass


def _time_input(page):
    field = page.locator("[data-testid='stage-start-time-field'] input[type='time']").first
    field.wait_for(state="visible", timeout=20000)
    return field


# ---------------------------------------------------------------------------
# AC-1 + AC-2 — reine Startzeit-Änderung wird gespeichert (sichtbar + persistent)
# ---------------------------------------------------------------------------

def test_ac1_ac2_startzeit_aenderung_speichert_und_persistiert():
    """AC-1: NUR Startzeit ändern → nach Reload persistent.
    AC-2: Save-Indicator durchläuft sichtbar den Gespeichert-Zustand."""
    with sync_playwright() as p:
        browser, ctx = _browser_context(p)
        page = ctx.new_page()
        _ui_login(page, _USER_A)
        trip_id = _create_trip(ctx, "ac1")
        try:
            page.goto(f"{BASE}/trips/{trip_id}?tab=stages", wait_until="networkidle")
            field = _time_input(page)
            field.fill("11:30")
            field.dispatch_event("change")

            # AC-2: sichtbarer Save-Durchlauf (kein stilles Versanden)
            indicator = page.locator("[data-testid='save-indicator']")
            expect(indicator).to_contain_text("Gespeichert", timeout=15000)

            # AC-1: Persistenz über echten Reload
            page.reload(wait_until="networkidle")
            field2 = _time_input(page)
            expect(field2).to_have_value("11:30", timeout=20000)

            # Beleg auch in den API-Daten (Server-Zustand, nicht nur UI)
            resp = ctx.request.get(f"{BASE}/api/trips/{trip_id}")
            data = resp.json()
            assert data["stages"][0].get("start_time", "").startswith("11:30"), (
                f"start_time nicht persistiert: {data['stages'][0].get('start_time')!r}"
            )
        finally:
            _delete_trip(ctx, trip_id)
            browser.close()


# ---------------------------------------------------------------------------
# AC-3 + AC-4 — 401: klare Meldung, Login, Rückkehr zur Ausgangsseite
# ---------------------------------------------------------------------------

def test_ac3_ac4_sitzungsablauf_meldung_login_rueckkehr():
    """AC-3: Aktion mit abgelaufener Sitzung → Anmeldeseite mit Hinweis
    'Sitzung abgelaufen'. AC-4: nach Login zurück zur Ausgangsseite."""
    with sync_playwright() as p:
        browser, ctx = _browser_context(p)
        page = ctx.new_page()
        _ui_login(page, _USER_A)
        trip_id = _create_trip(ctx, "ac3")
        try:
            target_path = f"/trips/{trip_id}?tab=stages"
            page.goto(f"{BASE}{target_path}", wait_until="networkidle")
            field = _time_input(page)

            # Sitzung REAL entwerten: Cookie weg → der Server lehnt mit echtem
            # 401 ab (identisch zum 24h-Ablauf; kein Mock, kein Fake-Server).
            cookies = [c for c in ctx.cookies() if c["name"] != "gz_session"]
            ctx.clear_cookies()
            ctx.add_cookies(cookies)

            # Aktion aus dem offenen Tab (echter Klick-Pfad)
            field.fill("09:45")
            field.dispatch_event("change")

            # AC-3: Anmeldeseite mit klarem Hinweis statt kryptischer Meldung
            page.wait_for_url(re.compile(re.escape(BASE) + r"/login.*"), timeout=15000)
            expect(page.locator("body")).to_contain_text(
                re.compile("Sitzung abgelaufen", re.IGNORECASE), timeout=10000
            )

            # AC-4: Login → zurück zur Ausgangsseite
            page.fill("input[name='username'], input[type='text']", _USER_A)
            page.fill("input[type='password']", _APP_PASS)
            page.click("button[type='submit']")
            page.wait_for_url(
                re.compile(re.escape(BASE) + re.escape(target_path).replace(r"\?", r"\?") + r"$"),
                timeout=30000,
            )
        finally:
            _delete_trip(ctx, trip_id)
            browser.close()


# ---------------------------------------------------------------------------
# AC-6 — Zwei-Nutzer-Isolation
# ---------------------------------------------------------------------------

def test_ac6_zwei_nutzer_isolation():
    """Nutzer A ändert seine Startzeit über die UI — Nutzer Bs Trip bleibt
    unangetastet (eigene Sitzung, eigene Daten)."""
    with sync_playwright() as p:
        browser_a, ctx_a = _browser_context(p)
        page_a = ctx_a.new_page()
        _ui_login(page_a, _USER_A)
        trip_a = _create_trip(ctx_a, "isoA")

        browser_b, ctx_b = _browser_context(p)
        page_b = ctx_b.new_page()
        _ui_login(page_b, _USER_B)
        trip_b = _create_trip(ctx_b, "isoB")
        try:
            page_a.goto(f"{BASE}/trips/{trip_a}?tab=stages", wait_until="networkidle")
            field = _time_input(page_a)
            field.fill("12:15")
            field.dispatch_event("change")
            expect(page_a.locator("[data-testid='save-indicator']")).to_contain_text(
                "Gespeichert", timeout=15000
            )

            resp_a = ctx_a.request.get(f"{BASE}/api/trips/{trip_a}")
            assert resp_a.json()["stages"][0].get("start_time", "").startswith("12:15")

            resp_b = ctx_b.request.get(f"{BASE}/api/trips/{trip_b}")
            b_start = resp_b.json()["stages"][0].get("start_time")
            assert not b_start, f"Cross-User-Leck: Bs Trip hat start_time {b_start!r}"

            # B darf As Trip gar nicht sehen
            resp_cross = ctx_b.request.get(f"{BASE}/api/trips/{trip_a}")
            assert resp_cross.status in (403, 404), (
                f"Isolation verletzt: B liest As Trip mit HTTP {resp_cross.status}"
            )
        finally:
            _delete_trip(ctx_a, trip_a)
            _delete_trip(ctx_b, trip_b)
            browser_a.close()
            browser_b.close()
