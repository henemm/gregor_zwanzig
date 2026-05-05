"""
TDD-Tests fuer Issue #126 — UI-Begriff "Tour"/"Touren" durch "Trip"/"Trips" ersetzen.

Spec: docs/specs/tests/trips_naming_tests.md
Bug-Spec: docs/specs/bugfix/trips_naming_sidebar_homepage.md

Tests laufen gegen den deployed SvelteKit-Frontend-Server (Default: Staging,
ueber Env-Var `GZ_TEST_BASE_URL` ueberschreibbar). KEINE MOCKS — echte
HTTP-Requests gegen den laufenden Frontend-Server (siehe CLAUDE.md
"KEINE MOCKED TESTS").

Sidebar und Startseite werden nur fuer eingeloggte User korrekt gerendert,
deshalb wird via `/api/auth/login` authentifiziert. Credentials kommen aus
`GZ_TEST_USER` / `GZ_TEST_PASS` Env-Vars.

Vor dem Fix: beide Tests schlagen fehl (RED).
Nach dem Fix: beide Tests gruen (GREEN).
"""
from __future__ import annotations

import os
from contextlib import closing

import httpx
import pytest

BASE_URL = os.getenv("GZ_TEST_BASE_URL", "https://staging.gregor20.henemm.com").rstrip("/")
TIMEOUT = 10.0
USER = os.getenv("GZ_TEST_USER", "default")
PASS = os.getenv("GZ_TEST_PASS")


def _login_session() -> httpx.Client:
    if not PASS:
        pytest.fail(
            "GZ_TEST_PASS env var required — Tests benoetigen eingeloggten User. "
            "Beispiel: GZ_TEST_PASS='...' uv run pytest tests/tdd/test_trips_naming.py"
        )
    client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT, follow_redirects=True)
    r = client.post("/api/auth/login", json={"username": USER, "password": PASS})
    if r.status_code != 200:
        client.close()
        pytest.fail(f"Login failed: HTTP {r.status_code}, body={r.text!r}")
    return client


def test_sidebar_uses_trips_label() -> None:
    """
    GIVEN: Authentifizierte Session gegen deployed Frontend
    WHEN:  GET / und Lesen des HTML
    THEN:  Sidebar enthaelt 'Meine Trips', nicht 'Meine Touren'
    """
    with closing(_login_session()) as client:
        r = client.get("/")
        assert r.status_code == 200
        html = r.text
        assert "Meine Trips" in html, (
            "Sidebar-Label 'Meine Trips' fehlt im HTML — kanonischer Begriff ist Trip "
            "(siehe API-Vertrag, URL /trips)."
        )
        assert "Meine Touren" not in html, (
            "Altes Sidebar-Label 'Meine Touren' noch im HTML — Issue #126 nicht behoben."
        )


def test_homepage_uses_trip_terminology() -> None:
    """
    GIVEN: Authentifizierte Session gegen deployed Frontend
    WHEN:  GET / und Lesen des HTML
    THEN:  Keine Tour/Touren-Vorkommen mehr; Trip-Bezeichnungen stattdessen
    """
    with closing(_login_session()) as client:
        r = client.get("/")
        assert r.status_code == 200
        html = r.text

        forbidden = ("Erste Tour anlegen", "Neue Tour", "deine erste Tour")
        for token in forbidden:
            assert token not in html, (
                f"Veraltetes Wording {token!r} noch im Startseiten-HTML — "
                f"Issue #126 fordert Vereinheitlichung auf 'Trip'."
            )

        new_tokens = ("Ersten Trip anlegen", "Neuer Trip", "Meine Trips")
        assert any(t in html for t in new_tokens), (
            f"Keine der neuen Trip-Bezeichnungen {new_tokens!r} im HTML — "
            f"je nach Empty-State sollte mindestens einer sichtbar sein."
        )
