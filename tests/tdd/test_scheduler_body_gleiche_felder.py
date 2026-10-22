"""TDD RED — Issue #2286 AC-8: gleiche Feldmenge beider Versand-Sub-Jobs im Python-Body.

SPEC: docs/specs/modules/fix_2286_compare_betrieb_health.md (Implementierungsdetail 6, AC-8)

Der Go-Scheduler liest je Nutzer den Body von `POST /api/scheduler/trip-reports`
und dem Compare-Pendant `POST /api/scheduler/compare-presets-daily`. Der
Trip-Body traegt `{status, count, failed, duration_s}`, der Compare-Body heute
nur `{status, count, failed}` -- `duration_s` fehlt.

Kern-Schicht: FastAPI-TestClient gegen die echte App, isolierter Daten-Root
(autouse `_isolate_data_root`), Nutzer ohne faellige Briefings (kein Versand,
kein Netz).
"""
from __future__ import annotations

import uuid

import pytest

PFLICHTFELDER = {"status", "count", "failed", "duration_s"}

ENDPOINTS = {
    "trip_reports_hourly": "/api/scheduler/trip-reports?user_id={uid}",
    "compare_presets_daily": "/api/scheduler/compare-presets-daily?user_id={uid}&hour=6",
}


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from api.main import app

    return TestClient(app)


@pytest.mark.parametrize("job", sorted(ENDPOINTS))
def test_body_has_status_count_failed_duration(client, job):
    """Given ein Nutzer ohne faellige Briefings / When der Sub-Job-Endpoint
    aufgerufen wird / Then enthaelt der Body `status`, `count`, `failed` und
    `duration_s` (Zahl >= 0).

    RED nur fuer `compare_presets_daily` (`duration_s` fehlt); der Trip-Fall
    ist der gruene Waechter."""
    uid = f"tdd-2286-body-{uuid.uuid4().hex[:8]}"
    resp = client.post(ENDPOINTS[job].format(uid=uid))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    fehlend = PFLICHTFELDER - set(body)
    assert not fehlend, (
        f"AC-8: {job} muss {sorted(PFLICHTFELDER)} liefern, fehlt {sorted(fehlend)}: {body!r}"
    )
    assert isinstance(body["duration_s"], (int, float)) and body["duration_s"] >= 0


def test_both_bodies_share_the_same_core_fields(client):
    """AC-8: beide Sub-Jobs liefern dieselbe Kern-Feldmenge -- kein
    Pflichtfeld, das nur einer der beiden kennt."""
    uid = f"tdd-2286-body-{uuid.uuid4().hex[:8]}"
    keys = {
        job: set(client.post(url.format(uid=uid)).json()) & PFLICHTFELDER
        for job, url in ENDPOINTS.items()
    }
    assert keys["trip_reports_hourly"] == keys["compare_presets_daily"] == PFLICHTFELDER, keys
