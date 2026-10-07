"""#2218 Scheibe A (C4-53): Der Trip-Versand-Endpunkt leitet `status`/`count`/`failed`
aus der ZUSTELLUNG ab, nicht aus „kein Fehler".

Echter FastAPI-Router, echter `TripReportSchedulerService`, echter Slot-Speicher;
ersetzt ist ausschließlich die Netz-Naht `_send_trip_report_outcome` (feste Ausgänge
je Nutzer, kein Mock). Geprüft wird am Endpunkt `/api/scheduler/trip-reports`.
Spec: docs/specs/modules/dispatch_orchestrator.md (AC-6 bis AC-9)
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import scheduler
from services.trip_report_scheduler import TripReportSchedulerService
from tests.tdd.test_briefing_slot_idempotenz import (
    KORSIKA, _schreibe, _trip_json, _zeitpunkt, PARIS,
)

TAGE = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
TAG = date(2026, 8, 20)

# Ausgang je Nutzer — wird von der Naht gelesen
_AUSGANG: dict[str, object] = {}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GZ_ENV", "production")
    _AUSGANG.clear()

    def _naht(self, trip, report_type, **kwargs):
        return _AUSGANG[self._user_id]

    monkeypatch.setattr(TripReportSchedulerService, "_send_trip_report_outcome", _naht)
    app = FastAPI()
    app.include_router(scheduler.router)
    return TestClient(app)


def _lauf(client, user: str, ausgang) -> dict:
    _AUSGANG[user] = ausgang
    _schreibe(user, [_trip_json("korsika", *KORSIKA, TAGE, morning="07:00:00")])
    at = _zeitpunkt(PARIS, TAG, 7).isoformat()
    r = client.post("/api/scheduler/trip-reports", params={"user_id": user, "at": at})
    assert r.status_code == 200
    return r.json()


def test_ac6_channels_unreachable_meldet_partial(client):
    assert _lauf(client, "u2218-unreach", "channels_unreachable") == {
        "status": "partial", "count": 0, "failed": 1,
    }


@pytest.mark.parametrize("ausgang", ["no_weather", "weird_new_outcome", None])
def test_ac7_no_weather_und_unbekannt_zaehlen_als_failed(client, ausgang):
    user = f"u2218-ac7-{ausgang}"
    assert _lauf(client, user, ausgang) == {"status": "partial", "count": 0, "failed": 1}


@pytest.mark.parametrize("ausgang", ["no_channels", "no_stage"])
def test_ac8_leerlaeufe_sind_neutral(client, ausgang):
    assert _lauf(client, f"u2218-ac8-{ausgang}", ausgang) == {
        "status": "ok", "count": 0, "failed": 0,
    }


def test_ac9_zwei_nutzer_werden_getrennt_bewertet(client):
    a = _lauf(client, "u2218-nutzer-a", "sent")
    b = _lauf(client, "u2218-nutzer-b", "channels_unreachable")
    assert a == {"status": "ok", "count": 1, "failed": 0}
    assert b == {"status": "partial", "count": 0, "failed": 1}
