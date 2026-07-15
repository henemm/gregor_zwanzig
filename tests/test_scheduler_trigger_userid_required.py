"""Kern-Schicht: Scheduler-Trigger-Endpoints erzwingen Pflicht-``user_id`` (#1181).

Spec: docs/specs/fast/harden-1181-scheduler-userid.md

Vier interne Scheduler-Trigger-Endpoints erbten einen stillen Default
``user_id: str = "default"``. Ohne ``user_id`` verarbeiteten sie kommentarlos
den ``default``-Nutzer — ein latentes Cross-User-Datenleck.

Bug-Nachweis (rot vor Fix): Ein POST OHNE ``user_id`` lieferte 200 (stiller
``default``-Lauf). Nach der Härtung (``user_id: str = Query(...)``) liefert
FastAPI 422 (fehlender Pflicht-Query-Parameter).

Keine Mocks: echter ``scheduler.router`` in einer FastAPI-App via ``TestClient``.
Der 200-Nachweis läuft gegen den echten ``default``-Nutzer aus ``data/users/``;
dessen einziger Trip ist abgelaufen (Etappen Feb 2026), wird also übersprungen —
kein Netz, keine Mail, deterministisch ``count=0``.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import scheduler


@pytest.fixture
def client():
    """FastAPI TestClient für den echten scheduler-Router."""
    app = FastAPI()
    app.include_router(scheduler.router)
    return TestClient(app)


# Alle vier gehärteten Routen. hour bleibt optional; user_id ist jetzt Pflicht.
REQUIRED_USER_ID_ROUTES = [
    "/api/scheduler/trip-reports",
    "/api/scheduler/alert-checks",
    "/api/scheduler/compare-alert-checks",
    "/api/scheduler/compare-presets-daily",
]


@pytest.mark.parametrize("route", REQUIRED_USER_ID_ROUTES)
def test_missing_user_id_returns_422(client, route):
    """POST ohne ``user_id``-Query → 422 (vorher: stiller 200-``default``-Lauf)."""
    resp = client.post(route)
    assert resp.status_code == 422, (
        f"{route} ohne user_id muss 422 liefern (Pflicht-Query-Parameter), "
        f"bekam {resp.status_code}: {resp.text[:200]}"
    )


def test_alert_checks_with_user_id_returns_200(client):
    """POST /alert-checks?user_id=default → 200 (Pflicht-Param akzeptiert Wert weiterhin).

    Läuft gegen den echten ``default``-Nutzer; dessen einziger Trip ist abgelaufen
    → übersprungen → deterministisch ``count=0``, kein Netz, keine Mail.
    """
    resp = client.post("/api/scheduler/alert-checks", params={"user_id": "default"})
    assert resp.status_code == 200, f"Body: {resp.text[:200]}"
    data = resp.json()
    assert "status" in data, f"Response ohne 'status': {data}"
