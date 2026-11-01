"""TDD RED — Issue #2163 Scheibe 2: ungueltige Nutzerkennung an den Routern.

Spec: docs/specs/modules/auth_haertung_python_2163.md (AC-7 GPX-Teil, AC-9..11).

Echte App ueber ``TestClient`` (Core-Geheimnis setzt ``tests/conftest.py``
zentral fuer jeden TestClient, #2142). Datenwurzel ist ``tmp_path``; Bob hat
echte Dateien, die Angriffskennung ``../users/bob`` zeigt heute genau dorthin.
Kein Netz: Sockets gesperrt, Bob ohne ``mail_to``, kein Kanal-Opt-in.

Ausfuehren: uv run pytest tests/unit/test_user_id_haertung_router.py -v
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

ANGRIFF = "../users/bob"
TRIP_ID = "gr20-etappe"
PRESET_ID = "vergleich-a"


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app import loader

    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    for name in ("GZ_SMTP_HOST", "GZ_SMTP_USER", "GZ_SMTP_PASS", "GZ_MAIL_TO"):
        monkeypatch.delenv(name, raising=False)
    bob = tmp_path / "users" / "bob"
    (bob / "briefings").mkdir(parents=True)
    (bob / "user.json").write_text(json.dumps({"id": "bob", "tier": "premium"}))
    (bob / "briefings" / f"{TRIP_ID}.json").write_text(json.dumps({
        "id": TRIP_ID, "name": "Bobs Trip", "kind": "route", "alert_rules": [],
        "official_alerts_enabled": False,
        "report_config": {"send_email": False, "send_telegram": False, "send_sms": False},
        "stages": [{"id": "s1", "name": "Etappe", "date": date.today().isoformat(),
                    "waypoints": [{"id": "w1", "name": "Innsbruck", "lat": 47.27,
                                   "lon": 11.40, "elevation_m": 574}]}],
    }))
    (bob / "briefings" / f"{PRESET_ID}.json").write_text(json.dumps({
        "id": PRESET_ID, "name": "Bobs Vergleich", "kind": "vergleich",
        "location_ids": [], "schedule": "daily", "empfaenger": [],
        "send_telegram": False, "send_sms": False, "send_premium_sms": False,
    }))
    from api.main import app

    import socket

    import pytest_socket

    vorher = socket.socket
    # Netz sperren, Unix-Sockets (Event-Loop des TestClient) erlaubt.
    pytest_socket.disable_socket(allow_unix_socket=True)
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        socket.socket = vorher


def _assert_not_found_ohne_kennung(resp) -> None:
    text = resp.text
    assert resp.status_code == 404, f"{resp.status_code}: {text}"
    assert resp.json().get("code") == "not_found", text
    for verraeter in ("bob", "users", ANGRIFF):
        assert verraeter not in text, f"Kennung gespiegelt: {text}"


@pytest.mark.parametrize("pfad,params", [
    (f"/api/briefings/{PRESET_ID}/send", {"kind": "vergleich"}),
    (f"/api/briefings/{TRIP_ID}/send", {"kind": "route"}),
], ids=["vergleich", "trip"])
def test_handversand_mit_ungueltiger_kennung_ist_not_found(client, pfad, params):
    """GIVEN Bob hat Trip und Vergleich, die Query traegt ``../users/bob``
    WHEN der Handversand-Endpoint aufgerufen wird
    THEN 404 ``not_found`` ohne Kennung im Text, kein 500/invalid_preset (AC-9)."""
    resp = client.post(pfad, params={**params, "user_id": ANGRIFF})
    _assert_not_found_ohne_kennung(resp)


@pytest.mark.parametrize("pfad", [
    f"/api/scheduler/trips/{TRIP_ID}/send",
    f"/api/scheduler/compare-presets/{PRESET_ID}/send",
], ids=["alt-trip", "alt-vergleich"])
def test_alt_routen_mit_ungueltiger_kennung_wie_neuer_endpoint(client, pfad):
    """GIVEN die Alt-Routen in scheduler.py mit ``../users/bob`` in der Query
    WHEN sie aufgerufen werden
    THEN dasselbe Bild wie AC-9: 404 ``not_found`` ohne Kennung (AC-10)."""
    _assert_not_found_ohne_kennung(client.post(pfad, params={"user_id": ANGRIFF}))


@pytest.mark.parametrize("methode,pfad,kwargs", [
    ("get", f"/api/preview/{TRIP_ID}/sms", {"params": {"user_id": ANGRIFF}}),
    ("post", "/api/_internal/sms/verification-code",
     {"json": {"user_id": ANGRIFF, "to": "+491511234567", "code": "123456"}}),
    ("post", "/api/scheduler/alert-checks", {"params": {"user_id": ANGRIFF}}),
], ids=["preview-sms", "sms-verifikation", "scheduler-alert-checks"])
def test_zentraler_handler_meldet_ungueltige_kennung_als_not_found(client, methode, pfad, kwargs):
    """GIVEN ein Router reicht die Kennung an ``with_user_profile``/Loader
    WHEN die Kennung ``../users/bob`` ist
    THEN zentraler Handler: 404 ``not_found`` ohne Kennung statt 500 (AC-11)."""
    resp = getattr(client, methode)(pfad, **kwargs)
    _assert_not_found_ohne_kennung(resp)
    assert "not_found" in resp.text


_GPX = b'<?xml version="1.0"?><gpx version="1.1" creator="t"><trk><trkseg>' \
       b'<trkpt lat="47.27" lon="11.40"><ele>574</ele></trkpt>' \
       b'<trkpt lat="47.31" lon="11.38"><ele>2269</ele></trkpt></trkseg></trk></gpx>'


@pytest.mark.parametrize("kennung", ["alice\n", ANGRIFF], ids=["zeilenumbruch", "pfad"])
def test_gpx_upload_lehnt_ungueltige_kennung_mit_400_ab(client, kennung):
    """GIVEN eine Kennung mit Zeilenumbruch am Ende bzw. ``../users/bob``
    WHEN eine GPX-Datei hochgeladen wird
    THEN genau 400 ``invalid_user_id`` (AC-7; der Pfad-Fall ist Regressionsschutz)."""
    resp = client.post("/api/gpx/parse", params={"user_id": kennung},
                       files={"file": ("t.gpx", _GPX, "application/gpx+xml")})
    assert resp.status_code == 400, f"{resp.status_code}: {resp.text}"
    assert resp.json().get("detail") == "invalid_user_id", resp.text
