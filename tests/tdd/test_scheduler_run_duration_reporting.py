"""TDD RED -- Feature #1539 (S0), AC-6: Laufdauer in Antwort und Log der
Scheduler-Routen /compare-alert-checks, /compare-official-alert-checks und
/trip-reports.

SPEC: docs/specs/modules/feat_1539_s0_s1a_beobachtbarkeit_atomare_schreiber.md
(Abschnitt B, AC-6)

Heute liefern die drei Routen nur ``status``/``count``/``failed``; es gibt
weder ``duration_s`` noch (bei den beiden Compare-Routen) ``checked``, und das
Log hat keine Zeile "Lauf beendet nach" mit der user_id. Der Aufbau (Antwort
200, ``status``/``count``/``failed`` vorhanden) funktioniert heute -- nur das
NEUE Verhalten fehlt.

Echter FastAPI-Router, echte Dienste, echte Dateien im isolierten Daten-Root
(conftest ``_isolate_data_root``), Wetter ueber den offline ``FixtureProvider``
(conftest, ``GZ_TEST_FIXTURE_DIR``). Kein Mock/patch, kein Netz. Versand ist
ausgeschlossen: Alarmkanaele des Presets aus, Trip-Lauf zu einem Zeitpunkt
ohne faellige Briefings.

Offene Auslegung (steht so in der Spec nur als "zusaetzlich ``checked``"):
``checked`` = Anzahl der geprueften Presets; der Nutzer hat hier genau eines.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import app
from app.loader import get_data_root, save_location
from app.user import SavedLocation
from tests.helpers.compare_briefings import write_compare_briefings
from tests.tdd.test_briefing_slot_idempotenz import (
    KORSIKA,
    PARIS,
    _schreibe,
    _trip_json,
    _zeitpunkt,
)

TAG = date(2026, 8, 20)
_ALLE_KANAELE_AUS = {"email": False, "telegram": False, "sms": False, "premium_sms": False}


@pytest.fixture
def client(monkeypatch):
    # Platzhalter statt Host-.env: kein Lauf kann an ein echtes Konto gehen.
    monkeypatch.setenv("GZ_SMTP_HOST", "dummy.invalid")
    monkeypatch.setenv("GZ_SMTP_USER", "dummy")
    monkeypatch.setenv("GZ_SMTP_PASS", "dummy")
    monkeypatch.setenv("GZ_MAIL_TO", "dummy@example.invalid")
    return TestClient(app)


def _nutzer_mit_preset(prefix: str) -> str:
    """Nutzer mit einem Ort und einem Vergleichs-Preset (Alarmkanaele aus)."""
    uid = f"tdd-1539-{prefix}-{uuid.uuid4().hex[:6]}"
    loc_id = f"loc-{uuid.uuid4().hex[:6]}"
    save_location(
        SavedLocation(id=loc_id, name="Innsbruck", lat=47.2692, lon=11.4041, elevation_m=600),
        user_id=uid,
    )
    preset = {
        "id": f"preset-{uuid.uuid4().hex[:6]}", "name": "Dauer-Preset", "user_id": uid,
        "location_ids": [loc_id], "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16, "empfaenger": [],
        "created_at": "2026-09-09T00:00:00Z", "alert_channels": dict(_ALLE_KANAELE_AUS),
    }
    write_compare_briefings(get_data_root() / "users" / uid, [preset])
    return uid


def _nutzer_mit_trip(prefix: str) -> tuple[str, str]:
    uid = f"tdd-1539-{prefix}-{uuid.uuid4().hex[:6]}"
    _schreibe(uid, [_trip_json("korsika", *KORSIKA, [TAG], morning="07:00:00")])
    # 03:00 Ortszeit: kein Briefing faellig, es wird nichts versendet.
    return uid, _zeitpunkt(PARIS, TAG, 3).isoformat()


def _laufzeilen(caplog, uid: str) -> list[str]:
    return [
        r.getMessage() for r in caplog.records
        if "Lauf beendet nach" in r.getMessage() and uid in r.getMessage()
    ]


def _pruefe_dauer(data: dict) -> None:
    assert "duration_s" in data, f"Antwort ohne duration_s: {data!r}"
    assert isinstance(data["duration_s"], (int, float)) and not isinstance(data["duration_s"], bool)
    assert data["duration_s"] >= 0


@pytest.mark.parametrize(
    "route", ["/api/scheduler/compare-alert-checks", "/api/scheduler/compare-official-alert-checks"],
)
def test_compare_alarmlauf_meldet_dauer_checked_und_loggt_einmal(client, caplog, route):
    """AC-6: Given ein Nutzer mit einem Vergleichs-Preset / When die Compare-
    Alarm-Route aufgerufen wird / Then enthaelt die Antwort ``duration_s``
    (>= 0) und ``checked``, ``status``/``count``/``failed`` bleiben, und das
    Log traegt genau eine Zeile "Lauf beendet nach" mit der user_id.

    RED (heute): die Antwort hat nur status/count/failed; das Log hat keine
    Laufzeile.
    """
    uid = _nutzer_mit_preset("cmp")
    with caplog.at_level(logging.INFO):
        resp = client.post(route, params={"user_id": uid})
    assert resp.status_code == 200
    data = resp.json()
    assert {"status", "count", "failed"} <= set(data), f"Bestandsfelder fehlen: {data!r}"
    assert data["status"] == "ok" and data["failed"] == 0
    _pruefe_dauer(data)
    assert data.get("checked") == 1, f"Erwartet checked=1 (ein Preset), erhalten: {data!r}"
    zeilen = _laufzeilen(caplog, uid)
    assert len(zeilen) == 1, f"Erwartet genau eine Laufzeile fuer {uid}, gefunden: {zeilen!r}"


def test_trip_briefing_lauf_meldet_dauer_und_loggt_einmal(client, caplog):
    """AC-6: Given ein Nutzer mit einem Trip, zu dem kein Briefing faellig ist /
    When /trip-reports aufgerufen wird / Then enthaelt die Antwort
    ``duration_s`` (>= 0), ``status``/``count``/``failed`` bleiben, und das Log
    traegt genau eine Zeile "Lauf beendet nach" mit der user_id.

    RED (heute): kein ``duration_s`` in der Antwort, keine Laufzeile im Log.
    """
    uid, at = _nutzer_mit_trip("rep")
    with caplog.at_level(logging.INFO):
        resp = client.post("/api/scheduler/trip-reports", params={"user_id": uid, "at": at})
    assert resp.status_code == 200
    data = resp.json()
    assert {"status", "count", "failed"} <= set(data), f"Bestandsfelder fehlen: {data!r}"
    assert (data["status"], data["count"], data["failed"]) == ("ok", 0, 0)
    _pruefe_dauer(data)
    zeilen = _laufzeilen(caplog, uid)
    assert len(zeilen) == 1, f"Erwartet genau eine Laufzeile fuer {uid}, gefunden: {zeilen!r}"


@pytest.mark.parametrize(
    "route, dienst",
    [("/api/scheduler/radar-alert-checks", "radar_alert"),
     ("/api/scheduler/compare-radar-alert-checks", "compare_radar_alert")],
)
def test_radar_lauf_loggt_genau_eine_laufzeile_mit_user_id(client, caplog, route, dienst):
    """AC-6 (Adversary F004): die Radar-Routen schreiben je Lauf genau eine
    Zeile "<dienst>: Lauf beendet nach ... user_id=<uid>" und liefern duration_s."""
    uid = f"tdd-1539-radar-{uuid.uuid4().hex[:6]}"  # Nutzer ohne Daten: nichts zu pruefen
    with caplog.at_level(logging.INFO):
        resp = client.post(route, params={"user_id": uid})
    assert resp.status_code == 200
    _pruefe_dauer(resp.json())
    zeilen = _laufzeilen(caplog, uid)
    assert len(zeilen) == 1, f"Erwartet genau eine Laufzeile fuer {uid}, gefunden: {zeilen!r}"
    assert zeilen[0].startswith(f"{dienst}: Lauf beendet nach")
