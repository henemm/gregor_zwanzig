"""
TDD RED — Kanal-Test-Button (F76 Konto erweitern)

Tests fuer den POST /api/notify/test Endpoint, der eine echte
Testnachricht ueber den gewaehlten Kanal sendet.

ALLE Tests muessen FEHLSCHLAGEN, weil:
- api/routers/notify.py existiert noch nicht
- Der Endpoint POST /api/notify/test existiert noch nicht
"""
import pytest
from fastapi.testclient import TestClient


# -- Test 1: Router-Modul existiert --

def test_notify_router_module_exists():
    """
    GIVEN: Die Codebase
    WHEN: api.routers.notify wird importiert
    THEN: Das Modul existiert und hat einen router
    """
    from api.routers import notify
    assert hasattr(notify, "router")


# -- Test 2: Router ist in main.py registriert --

def test_notify_router_registered_in_app():
    """
    GIVEN: Die FastAPI-App
    WHEN: POST /api/notify/test aufgerufen wird
    THEN: Die Route existiert (nicht 404)
    """
    from api.main import app
    client = TestClient(app)
    resp = client.post("/api/notify/test", params={"user_id": "default"})
    assert resp.status_code != 404, (
        f"Route /api/notify/test nicht registriert (404). Status: {resp.status_code}"
    )


# -- Test 3: Endpoint erwartet channel im Body --

def test_notify_test_requires_channel():
    """
    GIVEN: Die FastAPI-App mit registriertem notify-Router
    WHEN: POST /api/notify/test ohne Body aufgerufen wird
    THEN: 422 Validation Error (channel fehlt)
    """
    from api.main import app
    client = TestClient(app)
    resp = client.post("/api/notify/test", params={"user_id": "default"})
    assert resp.status_code == 422, (
        f"Erwarte 422 bei fehlendem Body, bekam {resp.status_code}"
    )


# -- Test 4: Unbekannter Kanal gibt Fehler zurueck --

def test_notify_test_unknown_channel_returns_error():
    """
    GIVEN: Der Endpoint existiert
    WHEN: Ein unbekannter Kanal gesendet wird
    THEN: Response enthaelt {"error": "..."}
    """
    from api.main import app
    client = TestClient(app)
    resp = client.post(
        "/api/notify/test",
        json={"channel": "fax"},
        params={"user_id": "default"},
    )
    data = resp.json()
    assert "error" in data, f"Erwarte error-Key bei unbekanntem Kanal, bekam: {data}"


# -- Test 5: Gueltiger Kanal gibt status ok zurueck --

def test_notify_test_email_returns_ok():
    """
    GIVEN: Ein User mit konfigurierter E-Mail
    WHEN: POST /api/notify/test mit channel=email
    THEN: Response enthaelt {"status": "ok"}

    Hinweis: Dieser Test sendet eine ECHTE E-Mail.
    Der Default-User muss mail_to konfiguriert haben.
    """
    from api.main import app
    client = TestClient(app)
    resp = client.post(
        "/api/notify/test",
        json={"channel": "email"},
        params={"user_id": "default"},
    )
    data = resp.json()
    assert data.get("status") == "ok", (
        f"Erwarte {{'status': 'ok'}}, bekam: {data}"
    )


# -- Test 6: Fehlender user_id Parameter --

def test_notify_test_requires_user_id():
    """
    GIVEN: Der Endpoint existiert
    WHEN: POST ohne user_id Query-Parameter
    THEN: 422 Validation Error
    """
    from api.main import app
    client = TestClient(app)
    resp = client.post(
        "/api/notify/test",
        json={"channel": "email"},
    )
    assert resp.status_code == 422, (
        f"Erwarte 422 bei fehlendem user_id, bekam {resp.status_code}"
    )
