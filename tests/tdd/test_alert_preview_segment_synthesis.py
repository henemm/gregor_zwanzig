"""TDD-RED: Issue #1948 Scheibe S2 — AC-2 Zweig-a-Replay ohne ``segment_times``.

SPEC: docs/specs/modules/alarm_testeinspeisung.md

Fehlt ``segment_times``, werden die Segment-Zeiten der in ``changes``
genannten ``segment_id``s aus dem bereits geladenen Trip synthetisiert
(``trip_local_today`` + ``convert_trip_to_segments``). Damit ist eine S1-
Mitschnittdatei (die nie ``segment_times`` enthaelt) ohne Transformation
einspeisbar.

RED-Grund: ``AlertPreviewBody.segment_times`` ist heute PFLICHT (der
422-Guard verlangt ``changes`` UND ``segment_times``) -- ein Request nur mit
``changes`` liefert heute 422 statt 200.

Kein Mock — echter FastAPI-TestClient, echte Trip-Fixture, die erwarteten
expliziten ``segment_times`` werden ueber DIESELBE Produktions-Segmentierung
(``convert_trip_to_segments``) gewonnen, nicht handgerechnet (vermeidet
Zeitzonen-Fehlrechnung und Wanduhr-Kippkanten).
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.real_data_root

CHANGE_TEMPLATE = {
    "metric": "gust_max_kmh", "old_value": 25.0, "new_value": 72.0,
    "delta": 47.0, "threshold": 60.0, "severity": "major", "direction": "increase",
}


@pytest.fixture
def client():
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.fixture
def real_trip():
    """Trip mit drei Wegpunkten (= zwei echten Segmenten '1'/'2') fuer HEUTE
    (``date.today()``), feste ``arrival_override``-Zeiten -- deterministisch,
    unabhaengig von Naismith-Berechnung."""
    user_id = f"test_1948s2ac2_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-ac2"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": trip_id, "name": "AC-2 Trip",
        "stages": [{
            "id": "T1", "name": "Tag 1", "date": date.today().isoformat(),
            "waypoints": [
                {"id": "G1", "name": "Start", "lat": 47.0, "lon": 11.0,
                 "elevation_m": 1000, "arrival_override": "08:00"},
                {"id": "G2", "name": "Mitte", "lat": 47.05, "lon": 11.05,
                 "elevation_m": 1200, "arrival_override": "10:00"},
                {"id": "G3", "name": "Ziel", "lat": 47.1, "lon": 11.1,
                 "elevation_m": 900, "arrival_override": "12:00"},
            ],
        }],
    }
    (trip_dir / f"{trip_id}.json").write_text(json.dumps(payload))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


def _real_segment_times(user_id: str, trip_id: str) -> list[dict]:
    """Baut die 'richtigen' expliziten segment_times ueber denselben
    Produktions-Segmentierungsweg, den die Synthese im GREEN-Stand nutzen
    MUSS -- kein Handrechnen von Zeitzonen-Offsets."""
    from api.routers.validator import _load_trip_for_validator
    from services.trip_day import trip_local_today
    from services.trip_segments import convert_trip_to_segments

    trip_obj = _load_trip_for_validator(user_id, trip_id)
    today = trip_local_today(trip_obj, datetime.now(timezone.utc))
    segments = convert_trip_to_segments(trip_obj, today)
    return [
        {"segment_id": str(s.segment_id),
         "start": s.start_time.strftime("%H:%M"),
         "end": s.end_time.strftime("%H:%M")}
        for s in segments
    ]


class TestAC2_SegmentTimesSynthesizedFromTrip:
    def test_synthesized_segment_times_match_explicit_equivalent_byte_identical(
        self, client, real_trip,
    ):
        user_id, trip_id = real_trip
        real_times = _real_segment_times(user_id, trip_id)
        assert real_times, (
            "Fixtur-Schutz: der Trip muss reale Segmente fuer heute liefern, "
            f"sonst testet AC-2 nichts. Bekam: {real_times!r}"
        )
        used_ids = [seg["segment_id"] for seg in real_times[:2]]
        changes = [{**CHANGE_TEMPLATE, "segment_id": sid} for sid in used_ids]
        explicit_times = [seg for seg in real_times if seg["segment_id"] in used_ids]

        resp_synth = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json={"changes": changes},
        )
        resp_explicit = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json={"changes": changes, "segment_times": explicit_times},
        )

        assert resp_synth.status_code == 200, (
            f"AC-2: Request ohne segment_times muss 200 liefern (Segment-"
            f"Zeiten werden aus dem Trip synthetisiert), war "
            f"{resp_synth.status_code}: {resp_synth.text[:300]}"
        )
        assert resp_explicit.status_code == 200, f"Body: {resp_explicit.text[:300]}"
        assert resp_synth.json() == resp_explicit.json(), (
            "AC-2: synthetisierte und explizit gleichwertige segment_times "
            "muessen byte-identische Antworten liefern.\n"
            f"Synth: {resp_synth.text[:500]}\nExplizit: {resp_explicit.text[:500]}"
        )
