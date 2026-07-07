"""
TDD RED — Issue #1068: Nutzerlevel-Datenmodell + Anzeige im Account

Spec: docs/specs/modules/issue_1068_tier_model_display.md (Slice 1 aus Epic #1067)

AC-1: Neuer Nutzer ohne tier-Feld -> Profile-API liefert "tier": "free"
AC-2: Nutzer mit explizit gesetztem tier: standard -> Profile-API liefert
      "standard" unveraendert (Zwei-Nutzer-Test gegen Cross-User-Datenleck)
AC-3: Account-Seite zeigt das aktuelle Level sichtbar an
AC-4: GET auf einen Nutzer ohne tier-Feld schreibt dessen user.json NICHT
      nachtraeglich um (Read-Modify-Write-Grundsatz, byteidentisch)

RED-Ursache:
- internal/model/user.go hat kein Tier-Feld
- internal/handler/auth.go (profileResponse/toProfileResponse) gibt kein
  "tier" in der Profile-Response aus, kein Default-Fallback auf "free"
- frontend/src/routes/account/+page.svelte rendert kein Level-Badge

KEINE MOCKS. Echte HTTP-Calls gegen Staging + Playwright-Browser fuer AC-3.
Direkte Dateimanipulation der user.json (AC-2-Fixture) simuliert exakt den in
der Spec dokumentierten PO-Handbetrieb (kein API-Endpoint fuer Tier-Aenderung
in diesem Slice) — sie ist Test-Vorbereitung, nicht die Pruefung selbst.

Die per-Nutzer-Verzeichnisse unter data/users/<id>/ gehoeren dem Service-Account
"claude-gregor" (0750/2750), nicht dem Test-ausfuehrenden Unix-User — Lesen/
Schreiben laeuft daher ueber passwortloses sudo (gleicher Mechanismus, den ein
PO beim manuellen Setzen von tier in Produktion braeuchte).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

import httpx
import pytest

from tests.helpers.staging_auth import httpx_auth, playwright_http_credentials

STAGING = os.environ.get("GZ_SVELTE_BASE", "https://staging.gregor20.henemm.com")
API = STAGING  # Go-API laeuft hinter SvelteKit-Proxy auf /api/
STAGING_DATA_DIR = Path("/home/hem/gregor_zwanzig_staging/data")


def _sudo_read_bytes(path: Path) -> bytes | None:
    """Liest eine Datei per sudo cat (Service-Account-Dateien sind fuer den
    Testnutzer nicht direkt lesbar). None wenn nicht lesbar/nicht vorhanden."""
    result = subprocess.run(
        ["sudo", "-n", "cat", str(path)], capture_output=True, timeout=10
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _sudo_write_bytes(path: Path, data: bytes) -> None:
    """Schreibt eine Datei per sudo tee (root behaelt Owner/Group der Datei bei)."""
    result = subprocess.run(
        ["sudo", "-n", "tee", str(path)], input=data, capture_output=True, timeout=10
    )
    assert result.returncode == 0, (
        f"sudo tee auf {path} fehlgeschlagen: {result.stderr.decode(errors='replace')}"
    )

# Feste Test-User (idempotent angelegt) — der Register-Endpoint ist IP-weit auf
# 5 Requests/Stunde limitiert (internal/router/router.go:43); zufaellige
# Uuid-Nutzernamen pro Testlauf wuerden das Kontingent bei jedem RE-Run neu
# verbrauchen. Bestehen die Nutzer schon (409), ist das idempotent gewollt.
TEST_PASS = "tdd1068testpass"
USER_FREE = "tdd-1068-free"
USER_STANDARD = "tdd-1068-std"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_user(username: str, password: str) -> None:
    """Legt den Testnutzer auf Staging an (idempotent, ignoriert 409)."""
    resp = httpx.post(
        f"{API}/api/auth/register",
        json={"username": username, "password": password},
        auth=httpx_auth(),
        timeout=15,
    )
    assert resp.status_code in (201, 409, 429), (
        f"Register {username!r} fehlgeschlagen: {resp.status_code} {resp.text[:200]}"
    )


def _login(username: str, password: str) -> httpx.Client:
    """Gibt einen authentifizierten httpx-Client zurueck."""
    client = httpx.Client(
        base_url=API, timeout=15, follow_redirects=True, auth=httpx_auth()
    )
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        pytest.skip(f"Login {username!r} fehlgeschlagen ({resp.status_code}) — Staging nicht erreichbar")
    sc = resp.headers.get("set-cookie", "")
    m = re.search(r"gz_session=([^;]+)", sc)
    if m:
        client.cookies.set("gz_session", m.group(1))
    return client


def _login_playwright(page, username: str, password: str) -> None:
    """Login ueber Playwright-Browser auf Staging."""
    page.goto(f"{STAGING}/login", wait_until="networkidle")
    time.sleep(1)
    page.fill("input[name='username']", username)
    page.fill("input[type='password']", password)
    page.click("button[type='submit']")
    page.wait_for_url(
        re.compile(rf"^{re.escape(STAGING)}(?!/login)"),
        timeout=20_000,
    )


def _user_json_path(username: str) -> Path:
    return STAGING_DATA_DIR / "users" / username / "user.json"


def _set_tier_on_disk(username: str, tier: str) -> None:
    """Simuliert den in der Spec dokumentierten PO-Handbetrieb: Tier direkt in
    user.json setzen. Es gibt in diesem Slice bewusst keinen API-Endpoint dafuer."""
    path = _user_json_path(username)
    raw = _sudo_read_bytes(path)
    assert raw is not None, f"user.json fuer {username} nicht lesbar (auch nicht per sudo): {path}"
    data = json.loads(raw)
    data["tier"] = tier
    _sudo_write_bytes(path, json.dumps(data, indent=2).encode())


# ---------------------------------------------------------------------------
# Setup: Testnutzer anlegen (einmalig fuer Session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def ensure_test_users():
    """Legt beide Testnutzer idempotent an; USER_STANDARD bekommt explizit tier=standard."""
    try:
        _ensure_user(USER_FREE, TEST_PASS)
        _ensure_user(USER_STANDARD, TEST_PASS)
    except httpx.ConnectError:
        pytest.skip("Staging nicht erreichbar — Tests uebersprungen")

    if _sudo_read_bytes(_user_json_path(USER_STANDARD)) is None:
        pytest.skip(
            f"user.json fuer {USER_STANDARD} nicht lesbar (auch nicht per sudo) — "
            "Dateisystemzugriff auf Staging-Daten fehlt, Tests uebersprungen."
        )
    _set_tier_on_disk(USER_STANDARD, "standard")


# ---------------------------------------------------------------------------
# AC-1: Neuer Nutzer ohne tier-Feld -> Default "free"
# ---------------------------------------------------------------------------

class TestAC1DefaultTierFree:
    """
    GIVEN: Neuer Nutzer, dessen user.json kein tier-Feld enthaelt
    WHEN:  GET /api/auth/profile wird fuer diesen Nutzer aufgerufen
    THEN:  Die JSON-Antwort enthaelt "tier": "free"
    """

    def test_new_user_without_tier_field_gets_free(self) -> None:
        client = _login(USER_FREE, TEST_PASS)
        resp = client.get("/api/auth/profile")
        assert resp.status_code == 200, (
            f"Profile-Abruf fehlgeschlagen: {resp.status_code} {resp.text[:200]}"
        )
        body = resp.json()
        assert body.get("tier") == "free", (
            f"RED: erwartet tier=='free' fuer neuen Nutzer ohne tier-Feld, "
            f"bekommen: {body.get('tier')!r}. internal/handler/auth.go: "
            "toProfileResponse() muss Default-Fallback auf 'free' liefern."
        )


# ---------------------------------------------------------------------------
# AC-2: Expliziter Tier bleibt unveraendert, kein Cross-User-Leak
# ---------------------------------------------------------------------------

class TestAC2ExplicitTierPassesThroughNoLeak:
    """
    GIVEN: Zwei Nutzer — einer ohne tier-Feld (Default "free"), einer mit
           explizit gesetztem "tier": "standard" in seiner user.json
    WHEN:  Beide rufen GET /api/auth/profile auf
    THEN:  Jeder sieht ausschliesslich seinen eigenen, korrekten Tier-Wert
    """

    def test_explicit_tier_unchanged_and_no_cross_user_leak(self) -> None:
        client_free = _login(USER_FREE, TEST_PASS)
        client_std = _login(USER_STANDARD, TEST_PASS)

        resp_free = client_free.get("/api/auth/profile")
        resp_std = client_std.get("/api/auth/profile")

        assert resp_free.status_code == 200, f"{USER_FREE}: {resp_free.status_code} {resp_free.text[:200]}"
        assert resp_std.status_code == 200, f"{USER_STANDARD}: {resp_std.status_code} {resp_std.text[:200]}"

        tier_free = resp_free.json().get("tier")
        tier_std = resp_std.json().get("tier")

        assert tier_free == "free", f"RED: {USER_FREE} erwartet 'free', bekommen {tier_free!r}"
        assert tier_std == "standard", (
            f"RED: {USER_STANDARD} hat explizit tier='standard' in user.json, "
            f"Profile-API liefert aber {tier_std!r} zurueck "
            "(Feld fehlt in profileResponse oder Cross-User-Leak)."
        )


# ---------------------------------------------------------------------------
# AC-3: Tier-Badge sichtbar im Account-Bereich
# ---------------------------------------------------------------------------

class TestAC3TierBadgeVisibleOnAccountPage:
    """
    GIVEN: Eingeloggter Nutzer oeffnet die Account-Seite (/account)
    WHEN:  Die Seite vollstaendig geladen ist
    THEN:  Ein sichtbares Element im Account-Bereich zeigt seinen Level
           ("Free"/"Standard"/"Premium") an
    """

    def test_tier_badge_visible_in_account_section(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            pytest.skip("playwright nicht installiert")

        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                http_credentials=playwright_http_credentials(),
            )
            page = ctx.new_page()
            try:
                _login_playwright(page, USER_FREE, TEST_PASS)

                page.goto(f"{STAGING}/account", wait_until="networkidle")
                time.sleep(1)

                account_section = page.locator('[data-testid="account-section"]')
                account_section.wait_for(timeout=10_000)

                badge = account_section.get_by_text("Free", exact=False)
                assert badge.count() > 0 and badge.first.is_visible(), (
                    "RED: kein sichtbares 'Free'-Element im Account-Bereich gefunden. "
                    "frontend/src/routes/account/+page.svelte muss ein Level-Badge rendern."
                )
            finally:
                browser.close()


# ---------------------------------------------------------------------------
# AC-4: Kein Zwangs-Rewrite der user.json bei fehlendem tier-Feld
# ---------------------------------------------------------------------------

class TestAC4NoRewriteOnMissingTier:
    """
    GIVEN: Nutzer ohne tier-Feld in seiner user.json
    WHEN:  GET /api/auth/profile liefert tier=="free" zurueck
    THEN:  Die zugrunde liegende user.json-Datei bleibt byteidentisch
           (kein Feld wird nachtraeglich in die Datei geschrieben)
    """

    def test_get_profile_does_not_rewrite_user_json(self) -> None:
        path = _user_json_path(USER_FREE)
        before = _sudo_read_bytes(path)
        if before is None:
            pytest.skip("user.json nicht lesbar (auch nicht per sudo) — Dateisystemzugriff auf Staging-Daten fehlt")

        client = _login(USER_FREE, TEST_PASS)
        resp = client.get("/api/auth/profile")
        assert resp.status_code == 200

        after = _sudo_read_bytes(path)
        assert before == after, (
            "RED-Absicherung: GET /api/auth/profile darf user.json NICHT veraendern "
            "(Read-Modify-Write-Grundsatz, kein Zwangs-Rewrite von Bestandsdateien). "
            f"before={before!r} after={after!r}"
        )
