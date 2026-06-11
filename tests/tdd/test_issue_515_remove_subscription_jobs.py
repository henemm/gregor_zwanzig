"""
Tests für Issue #515 — Entfernung obsoleter Subscription-Jobs.

Verhaltensnachweis (kein Mock, kein Quelltext-Read): die entfernten
Python-Funktionen sind nicht mehr importierbar (echter ImportError), und die
entfernten FastAPI-Endpoints antworten über die reale App mit 404.

#765-Hinweis: Die früheren Go-Quelltext-Greps (scheduler.go/config.go) und der
Test-Datei-Klassen-Grep wurden entfernt (Datei-Inhalt-Anti-Pattern, CLAUDE.md).
Go-seitige Streichungen lassen sich nicht über Python-Quelltext-Analyse
beweisen; die Python-Streichungen sind über Import- und HTTP-Verhalten echt
abgedeckt.

KEINE MOCKS — Projektkonvention (CLAUDE.md).
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# AC-2: Python-Funktionen entfernt (echter Import → ImportError)
# ---------------------------------------------------------------------------

class TestPythonFunctionsRemoved:
    """_run_subscriptions_by_schedule und _run_weekly_subscriptions dürfen nicht existieren."""

    def test_run_subscriptions_by_schedule_not_importable(self):
        """GIVEN api.routers.scheduler, WHEN Import, THEN ImportError."""
        with pytest.raises(ImportError):
            from api.routers.scheduler import _run_subscriptions_by_schedule  # noqa: F401

    def test_run_weekly_subscriptions_not_importable(self):
        """GIVEN api.routers.scheduler, WHEN Import, THEN ImportError."""
        with pytest.raises(ImportError):
            from api.routers.scheduler import _run_weekly_subscriptions  # noqa: F401


# ---------------------------------------------------------------------------
# AC-2/AC-3: Python-Endpoints entfernt (reale App → 404)
# ---------------------------------------------------------------------------

class TestPythonEndpointsRemoved:
    """Die entfernten Subscription-Endpoints existieren nicht mehr in der App."""

    def _client(self):
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_morning_subscriptions_endpoint_404(self):
        """GIVEN reale FastAPI-App, WHEN /api/scheduler/morning-subscriptions
        aufgerufen, THEN 404 — der Endpoint (und damit der Doppelversand-Guard)
        ist entfernt."""
        client = self._client()
        assert client.post("/api/scheduler/morning-subscriptions").status_code == 404
        assert client.get("/api/scheduler/morning-subscriptions").status_code == 404

    def test_evening_subscriptions_endpoint_404(self):
        """GIVEN reale FastAPI-App, WHEN /api/scheduler/evening-subscriptions
        aufgerufen, THEN 404."""
        client = self._client()
        assert client.post("/api/scheduler/evening-subscriptions").status_code == 404
        assert client.get("/api/scheduler/evening-subscriptions").status_code == 404
