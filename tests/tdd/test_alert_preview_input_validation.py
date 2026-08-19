"""TDD: fix-1948-s2-preview-eingaben — Eingabevalidierung des Preview-
Endpoints ``POST /api/trips/{trip_id}/alert-preview`` (Nachbesserung zu
#1948 S2, schliesst zugleich #1965 mit).

SPEC: docs/specs/fast/fix-1948-s2-preview-eingaben.md

Bug A: ``changes[].metric`` wird nicht gegen den Metrik-Katalog geprueft --
eine unbekannte Metrik crasht (KeyError in ``_resolve_metric_id``) als 500
statt als 422 mit der Metrik im Fehlertext.

Bug B Teil 1: ``official[].segment_ids`` werden nicht gegen die echten
Trip-Segmente geprueft. Hat der Trip fuer heute ECHTE Segmente, muss eine
unbekannte ID 422 liefern. Hat der Trip KEINE echten Segmente (Stub-/
Test-Trip, wie in allen bestehenden S2-Official-Tests), bleibt die Pruefung
ein No-Op -- deckt sich mit der bestehenden "gesamte Route"-Semantik in
``official_alerts.py`` (Trip ohne echte Zwischen-Segmente akzeptiert jede
uebergebene ID).

Bug B Teil 2 / #1965: ``format_segment_reference()`` crasht bei
nicht-numerischen, nicht-"Ziel"-Segment-IDs (``int()``-ValueError) --
betrifft auch den Produktiv-Versandpfad (``trip_alert.py:1614`` uebergibt
``str(segment_id)``).

Kein Mock — echter FastAPI-TestClient, echte Trip-Fixtures unter
data/users/<uid>/briefings/.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.real_data_root

CHANGE_TEMPLATE = {
    "old_value": 25.0, "new_value": 72.0, "delta": 47.0, "threshold": 60.0,
    "severity": "major", "direction": "increase", "segment_id": "1",
}


@pytest.fixture
def client():
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.fixture
def stub_trip():
    """Trip OHNE echte Segmente (leere stages) -- Muster aus den bestehenden
    S2-Official-Tests (test_alert_preview_official_render.py etc.)."""
    user_id = f"test_fix1948s2_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-stub"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "Eingabevalidierungs-Trip", "stages": [],
    }))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


@pytest.fixture
def real_trip():
    """Trip mit EINEM echten Segment ('1') fuer heute (Muster aus
    test_alert_preview_payload_exclusivity.py::_write_real_trip)."""
    user_id = f"test_fix1948s2real_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-real"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": trip_id, "name": "Echtsegment-Trip",
        "stages": [{
            "id": "T1", "name": "Tag 1", "date": date.today().isoformat(),
            "waypoints": [
                {"id": "G1", "name": "Start", "lat": 47.0, "lon": 11.0,
                 "elevation_m": 1000, "arrival_override": "08:00"},
                {"id": "G2", "name": "Ziel", "lat": 47.05, "lon": 11.05,
                 "elevation_m": 1200, "arrival_override": "10:00"},
            ],
        }],
    }
    (trip_dir / f"{trip_id}.json").write_text(json.dumps(payload))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


class TestBugA_UnknownMetricRejected:
    def test_unknown_metric_in_changes_returns_422_naming_the_metric(
        self, client, stub_trip,
    ):
        user_id, trip_id = stub_trip
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json={"changes": [{**CHANGE_TEMPLATE, "metric": "temperature"}]},
        )
        assert resp.status_code == 422, (
            f"Unbekannte Metrik 'temperature' (kein Katalog-summary_field) "
            f"muss 422 liefern, nicht {resp.status_code}: {resp.text[:300]}"
        )
        assert "temperature" in resp.json().get("detail", ""), (
            f"422-Meldung muss die Metrik nennen: {resp.text[:300]}"
        )


class TestAC2_UnknownChangesSegmentIdRejectedWithExplicitSegmentTimes:
    """AC-2 (Staging-Finding #1): die AC-3-Pruefung sitzt heute nur in
    ``_synthesize_segment_times`` und laeuft NUR, wenn ``segment_times``
    NICHT mitgeliefert wird (``validator.py:304-305`` vor dem Fix). Bei
    explizit mitgeliefertem ``segment_times`` blieb eine unbekannte
    ``segment_id`` bislang komplett ungeprueft (Lueckenschluss)."""

    def test_unknown_segment_id_with_explicit_segment_times_returns_422(
        self, client, real_trip,
    ):
        user_id, trip_id = real_trip
        bogus = {**CHANGE_TEMPLATE, "metric": "gust_max_kmh",
                 "segment_id": "gibt-es-nicht"}
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json={
                "changes": [bogus],
                "segment_times": [
                    {"segment_id": "gibt-es-nicht", "start": "08:00", "end": "10:00"},
                ],
            },
        )
        assert resp.status_code == 422, (
            f"Unbekannte segment_id MUSS auch bei explizitem segment_times "
            f"422 liefern, nicht {resp.status_code}: {resp.text[:300]}"
        )
        assert "gibt-es-nicht" in resp.json().get("detail", ""), (
            f"422-Meldung muss die ID nennen: {resp.text[:300]}"
        )


class TestBugB1_UnknownOfficialSegmentIdRejected:
    def test_unknown_segment_id_on_real_trip_returns_422_naming_the_id(
        self, client, real_trip,
    ):
        user_id, trip_id = real_trip
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id},
            json={"official": [{
                "source": "geosphere_warn", "hazard": "thunderstorm",
                "level": 3, "label": "Gewitter",
                "segment_ids": ["gibt-es-nicht"],
            }]},
        )
        assert resp.status_code == 422, (
            f"Unbekannte segment_id auf einem Trip mit echten Segmenten "
            f"muss 422 liefern, nicht {resp.status_code}: {resp.text[:300]}"
        )
        assert "gibt-es-nicht" in resp.json().get("detail", ""), (
            f"422-Meldung muss die ID nennen: {resp.text[:300]}"
        )


class TestBugB2_FormatSegmentReferenceHandlesStringIds:
    """Direkt-Test an der Funktion (#1965) -- am Wirkort, ohne HTTP-Umweg.

    Deviation von der Mini-Spec-Formulierung ("official mit gueltiger
    String-Segment-ID ueber den Endpoint"): eine Endpoint-Reproduktion ist
    nicht konstruierbar, ohne Bug B Teil 1 (422 bei unbekannter ID) zu
    widersprechen -- ``convert_trip_to_segments`` liefert fuer JEDEN echten
    Trip ausschliesslich `i+1` (int) oder "Ziel" (`trip_segments.py:223/305`,
    `app/models.py:399` dokumentiert dasselbe). Ein Trip, dessen ECHTES
    Segment "stage1" heisst, existiert damit nicht -- Bug B Teil 1 wuerde
    "stage1" also stets als unbekannt ablehnen (422), nie 200 liefern; ein
    Trip OHNE echte Segmente wiederum laesst ``official_alerts.py``s
    ``is_full``-Kollaps (Trip <=1 echtes Segment -> immer "gesamte Route")
    ``format_segment_reference()`` gar nicht erst erreichen -- ein Endpoint-
    Test mit Stub-Trip ist schon HEUTE gruen (kein Rot-Beweis moeglich,
    verifiziert vor dem Fix). Issue #1965 selbst trennt die beiden Bugs
    explizit ("Abgrenzung": 422-Validierung = Preview-Endpoint-Eingabe,
    Renderer-Robustheit = Versandpfad) -- dieser Test deckt exakt den
    Versandpfad-Teil an der Stelle ab, an der die Zusicherung wirkt."""

    def test_non_numeric_id_appended_ziel_stays_separate(self):
        from output.renderers.alert.segments import format_segment_reference

        result = format_segment_reference(["stage1", "Ziel"])
        assert result == "Segment stage1, 🏁 Ziel", (
            f"Nicht-numerische ID muss crashfrei aufgezaehlt werden, "
            f"'Ziel' bleibt separat am Ende: {result!r}"
        )

    def test_numeric_case_stays_byte_identical(self):
        """Gegenprobe: der Bestandsfall (rein numerisch, zusammenhaengend)
        darf durch die Erweiterung nicht veraendert werden."""
        from output.renderers.alert.segments import format_segment_reference

        assert format_segment_reference(["3", "4", "5"]) == "Segment 3–5"
