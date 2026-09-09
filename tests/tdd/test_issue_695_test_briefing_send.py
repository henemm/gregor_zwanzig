"""
TDD GREEN — Issue #695: Test-Briefing senden Button

Spec: docs/specs/modules/issue_695_test_briefing_send.md
Workflow: issue-695-test-briefing-send

Drei Verhaltenstests — KEINE Mocks:

  AC-4 (Python): POST /api/scheduler/trips/{id}/send?user_id=...
    - existiert als FastAPI-Endpoint
    - unbekannte trip_id → 404

  AC-5 (Go-Proxy): POST /api/trips/{id}/send via Go (localhost:8090)
    - existiert als Route
    - unbekannte trip_id → 404 (propagiert vom Python-Upstream)

  AC-6 (Frontend): +page.svelte enthält Feedback-Spans mit data-testid
    - data-testid="test-briefing-success"
    - data-testid="test-briefing-error"

KEINE MOCKS — FastAPI TestClient ist ein echter ASGI-Aufruf.
Go-Test via echter HTTP-Call gegen localhost:8090.
Frontend-Test prüft Svelte-Quelltext (doc-compliance-test).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


# Issue #1196 Klasse B: kein modulweites `load_dotenv()` mehr (lief beim
# COLLECT statt beim Testlauf und kontaminierte os.environ ohne Teardown fuer
# den Rest des Prozesses). GO_BASE/TEST_USER/TEST_PASS wurden dafuer von
# Modul-Konstanten zu Funktionen -- sie werden ausschliesslich innerhalb von
# Testkoerpern gelesen (nie in einem skipif), sodass die untenstehende
# autouse-Fixture `_dotenv` (fordert die geteilte `dotenv_env`-Fixture aus
# tests/conftest.py an) laengst gelaufen ist, bevor der jeweilige Wert
# gebraucht wird.
def _go_base() -> str:
    return os.environ.get("GZ_API_BASE", "http://localhost:8090")


def _test_user() -> str:
    return os.environ.get("GZ_AUTH_USER", "default")


def _test_pass() -> str:
    return os.environ.get("GZ_AUTH_PASS", "")


@pytest.fixture(autouse=True)
def _dotenv(dotenv_env):
    yield


# ---------------------------------------------------------------------------
# AC-4: Python-Endpoint
# ---------------------------------------------------------------------------

class TestPythonEndpointExists:
    """AC-4 — POST /api/scheduler/trips/{id}/send existiert und liefert 404 für
    unbekannte trip_id."""

    @pytest.fixture
    def client(self):
        from api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_endpoint_returns_404_for_unknown_trip(self, client):
        """
        GIVEN: FastAPI app läuft
        WHEN: POST /api/scheduler/trips/nonexistent-trip-xyz-695/send
        THEN: HTTP 404 mit detail-Feld
        """
        resp = client.post(
            "/api/scheduler/trips/nonexistent-trip-xyz-695/send",
            params={"user_id": "default"},
        )
        assert resp.status_code == 404, (
            f"Erwartet 404 für unbekannte trip_id, erhalten: {resp.status_code} "
            f"body={resp.text}"
        )
        data = resp.json()
        assert "detail" in data, f"Antwort muss 'detail'-Feld enthalten: {data}"


# ---------------------------------------------------------------------------
# AC-5: Go-Proxy
# ---------------------------------------------------------------------------

class TestGoProxyRoute:
    """AC-5 — POST /api/trips/{id}/send via Go-Proxy existiert und leitet an
    Python-Upstream weiter."""

    def _login(self):
        """Authentifizierte Session gegen localhost:8090."""
        import httpx
        client = httpx.Client(base_url=_go_base(), timeout=15)
        resp = client.post(
            "/api/auth/login",
            json={"username": _test_user(), "password": _test_pass()},
        )
        if resp.status_code != 200:
            pytest.skip(
                f"Login fehlgeschlagen ({resp.status_code}) — "
                "Go-API nicht erreichbar oder Credentials fehlen"
            )
        sc = resp.headers.get("set-cookie", "")
        m = re.search(r"gz_session=([^;]+)", sc)
        if m:
            client.cookies.set("gz_session", m.group(1))
        return client

    # #1196 Klasse C Teil 4: braucht einen echten Go-Server auf localhost:8090
    # (`_login()` wirft ohne laufenden Server eine ungefangene httpx.ConnectError,
    # kein Skip) -- auf dem CI-Runner strukturell nicht gegeben, kein Settings-
    # Fix moeglich. Nachbar-Test derselben Klasse existiert nicht; Datei bleibt
    # sonst deterministisch.
    @pytest.mark.live
    def test_go_proxy_returns_404_for_unknown_trip(self):
        """
        GIVEN: Go-API läuft auf localhost:8090, Python-Staging auf Port 8001
        WHEN: POST /api/trips/nonexistent-trip-xyz-695/send (authentifiziert)
        THEN: HTTP 404 (vom Python-Upstream propagiert)
        """
        client = self._login()
        resp = client.post("/api/trips/nonexistent-trip-xyz-695/send")
        assert resp.status_code == 404, (
            f"Erwartet 404 für unbekannte trip_id via Go-Proxy, "
            f"erhalten: {resp.status_code} body={resp.text}"
        )


# ---------------------------------------------------------------------------
# AC-6: Frontend (doc-compliance-test)
# ---------------------------------------------------------------------------

class TestFrontendFeedback:
    """AC-6 — Svelte-Seite enthält Feedback-Spans mit data-testid.

    # doc-compliance-test
    """

    def _svelte_source(self) -> str:
        path = (
            REPO_ROOT
            / "frontend"
            / "src"
            / "routes"
            / "trips"
            / "[id]"
            / "+page.svelte"
        )
        return path.read_text(encoding="utf-8")

    def test_success_span_has_testid(self):
        """
        GIVEN: +page.svelte im Frontend
        WHEN: Quelltext lesen
        THEN: data-testid="test-briefing-success" vorhanden
        """
        src = self._svelte_source()
        assert 'data-testid="test-briefing-success"' in src, (
            "Erwartet data-testid=\"test-briefing-success\" in +page.svelte"
        )

    def test_error_span_has_testid(self):
        """
        GIVEN: +page.svelte im Frontend
        WHEN: Quelltext lesen
        THEN: data-testid="test-briefing-error" vorhanden
        """
        src = self._svelte_source()
        assert 'data-testid="test-briefing-error"' in src, (
            "Erwartet data-testid=\"test-briefing-error\" in +page.svelte"
        )
