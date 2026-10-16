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


# -- Test 5: user_id "default" sendet keine Testmail --
# Abgeloest durch #2521 S2 / ADR-0091: vorher sendete dieser Test (Marker
# ``email``) eine ECHTE Mail unter ``user_id="default"`` und erwartete
# ``status: ok``. Neu sperrt der Dienst ``"default"`` -- es wird nicht mehr
# gewaehlt, deshalb laeuft der Test ohne Marker im Kern, mit Aufzeichner am
# SMTP-Rand und hermetischer Umgebung (keine Projekt-``.env``).

def test_notify_test_email_mit_default_kennung_sendet_nichts(monkeypatch):
    """
    GIVEN: Ein vollstaendiges, bestaetigtes Profil unter ``default`` und eine
           globale Betreiber-Adresse
    WHEN: POST /api/notify/test mit channel=email und user_id=default
    THEN: Response enthaelt {"error": ...}, keine SMTP-Verbindung
    """
    import json

    from app.config import Settings
    from app.loader import get_data_dir
    from output.channels import email as email_mod

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key, wert in {
        "GZ_ENV": "production",
        "GZ_IS_TEST_MODE": "false",
        "GZ_SMTP_HOST": "versandkette-pruefung.henemm.com",
        "GZ_SMTP_USER": "versandkette",
        "GZ_SMTP_PASS": "kein-echtes-passwort",
        "GZ_MAIL_FROM": "gregor_zwanzig@henemm.com",
        "GZ_MAIL_TO": "betreiber-rueckfall@henemm.com",
        "GZ_TEST_SMTP_HOST": "stalwart-pruefung.henemm.com",
        "GZ_TEST_SMTP_USER": "gregor-test",
        "GZ_TEST_SMTP_PASS": "kein-echtes-passwort",
    }.items():
        monkeypatch.setenv(key, wert)

    verbindungen: list[str] = []

    class _SmtpAufzeichner:
        def __init__(self, host, port, timeout=None):
            verbindungen.append(host)

            class _Sock:
                def settimeout(self, t):
                    pass

            self.sock = _Sock()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, user, password):
            pass

        def sendmail(self, from_addr, to_addrs, msg):
            pass

    monkeypatch.setattr(email_mod.smtplib, "SMTP", _SmtpAufzeichner)
    monkeypatch.setattr(email_mod, "running_origin", lambda module_file: "production")

    ordner = get_data_dir("default")
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": "default", "mail_to": "default-profil@henemm.com",
        "email_verified_at": "2026-10-01T08:00:00Z",
    }))

    from api.main import app
    client = TestClient(app)
    resp = client.post(
        "/api/notify/test",
        json={"channel": "email"},
        params={"user_id": "default"},
    )
    data = resp.json()
    assert "error" in data and "status" not in data, (
        f"Erwarte {{'error': ...}} fuer user_id=default, bekam: {data}"
    )
    assert verbindungen == [], f"user_id=default darf nicht waehlen, gesehen {verbindungen!r}"


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
