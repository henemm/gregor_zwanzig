"""TDD-RED: Issue #1948 Scheibe S2 — AC-1/AC-3 Payload-Exklusivitaet am
Preview-Endpoint ``POST /api/trips/{trip_id}/alert-preview``.

SPEC: docs/specs/modules/alarm_testeinspeisung.md

Der 422-Guard wird von einer binaeren (onset XOR changes+segment_times) auf
eine Vier-Wege-Exklusivitaet erweitert (``onset`` | ``changes`` | ``official``
| ``nowcast_frames``). AC-1 verlangt eine 422-Meldung, die ALLE VIER Typen
nennt; AC-3 verlangt bei unbekannter ``segment_id`` eine 422-Meldung, die die
ID selbst nennt.

RED-Grund: ``AlertPreviewBody`` kennt heute weder ``official`` noch
``nowcast_frames`` (Pydantic ignoriert unbekannte Felder), und die
422-Meldung nennt nur 'onset'/'changes'. Manche Kombinationen unten liefern
deshalb HEUTE bereits zufaellig 422 (weil das binaere Alt-Gate zwei bekannte
Felder gleichzeitig sieht), andere HEUTE 200 (weil ``official``/
``nowcast_frames`` unbeachtet verpuffen und nur das Alt-Feld ``changes``
uebrig bleibt) -- in JEDEM Fall schlaegt mindestens eine der beiden
Zusicherungen (Status ODER Meldungstext) heute fehl.

Kein Mock — echter FastAPI-TestClient gegen den echten Router, echte
Trip-Fixtures unter data/users/<uid>/briefings/.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.real_data_root

REQUIRED_TYPE_NAMES = ("onset", "changes", "official", "nowcast_frames")

CHANGE_PAYLOAD = {
    "metric": "gust_max_kmh", "old_value": 25.0, "new_value": 72.0,
    "delta": 47.0, "threshold": 60.0, "severity": "major", "direction": "increase",
    "segment_id": "1",
}
SEGMENT_TIME_PAYLOAD = {"segment_id": "1", "start": "08:00", "end": "10:00"}
ONSET_PAYLOAD = {
    "onset_minutes": 12, "onset_time": "14:35", "km_from": 0.0, "km_to": 5.0,
    "is_convective": False, "intensity_label": "leichter Regen",
    "source_label": "Radar (DWD)",
}
OFFICIAL_PAYLOAD = {
    "source": "geosphere_warn", "hazard": "thunderstorm", "level": 3,
    "label": "Gewitter", "segment_ids": ["1"],
}


def _nowcast_frames_payload() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "source": "radar",
        "frames": [
            {"timestamp": (now + timedelta(minutes=20)).isoformat(),
             "precip_mm_h": 2.5, "is_convective": False},
        ],
        "km_from": 0.0, "km_to": 5.0,
    }


@pytest.fixture
def client():
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.fixture
def stub_trip():
    user_id = f"test_1948s2ac1_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-stub"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "Exklusivitaets-Trip", "stages": [],
    }))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


def _write_real_trip(user_id: str, trip_id: str) -> None:
    """Trip mit EINEM echten Segment ('1') fuer den AC-3-Unbekannt-Test."""
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": trip_id, "name": "AC-3 Trip",
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


def _assert_422_names_all_four(resp) -> None:
    assert resp.status_code == 422, (
        f"Erwartet 422, bekam {resp.status_code}: {resp.text[:300]}"
    )
    detail = resp.json().get("detail", "")
    for name in REQUIRED_TYPE_NAMES:
        assert name in detail, (
            f"AC-1: 422-Meldung muss alle vier Typnamen nennen, "
            f"'{name}' fehlt. Meldung: {detail!r}"
        )


class TestAC1_PayloadExclusivity:
    """AC-1: genau EINER von onset/changes/official/nowcast_frames -- sonst
    422 mit einer Meldung, die alle vier Typen benennt."""

    def test_empty_body_returns_422_naming_all_four_types(self, client, stub_trip):
        user_id, trip_id = stub_trip
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id}, json={},
        )
        _assert_422_names_all_four(resp)

    def test_two_types_simultaneously_returns_422_naming_all_four_types(
        self, client, stub_trip,
    ):
        user_id, trip_id = stub_trip
        body = {
            "changes": [CHANGE_PAYLOAD], "segment_times": [SEGMENT_TIME_PAYLOAD],
            "official": [OFFICIAL_PAYLOAD],
        }
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id}, json=body,
        )
        _assert_422_names_all_four(resp)

    def test_three_types_simultaneously_returns_422_naming_all_four_types(
        self, client, stub_trip,
    ):
        user_id, trip_id = stub_trip
        body = {
            "changes": [CHANGE_PAYLOAD], "segment_times": [SEGMENT_TIME_PAYLOAD],
            "official": [OFFICIAL_PAYLOAD],
            "nowcast_frames": _nowcast_frames_payload(),
        }
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id}, json=body,
        )
        _assert_422_names_all_four(resp)

    def test_all_four_types_simultaneously_returns_422_naming_all_four_types(
        self, client, stub_trip,
    ):
        user_id, trip_id = stub_trip
        body = {
            "onset": ONSET_PAYLOAD,
            "changes": [CHANGE_PAYLOAD], "segment_times": [SEGMENT_TIME_PAYLOAD],
            "official": [OFFICIAL_PAYLOAD],
            "nowcast_frames": _nowcast_frames_payload(),
        }
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id}, json=body,
        )
        _assert_422_names_all_four(resp)


class TestAC3_UnknownSegmentId:
    """AC-3: ``changes`` ohne ``segment_times`` mit einer im Trip nicht
    existenten ``segment_id`` -> 422, Meldung nennt die unbekannte ID."""

    def test_unknown_segment_id_returns_422_naming_the_id(self, client):
        user_id = f"test_1948s2ac3_{uuid.uuid4().hex[:8]}"
        trip_id = "trip-ac3"
        try:
            _write_real_trip(user_id, trip_id)
            bogus_id = "does-not-exist-9876"
            body = {"changes": [{**CHANGE_PAYLOAD, "segment_id": bogus_id}]}
            resp = client.post(
                f"/api/trips/{trip_id}/alert-preview",
                params={"user_id": user_id}, json=body,
            )
            assert resp.status_code == 422, f"Body: {resp.text[:300]}"
            detail = resp.json().get("detail", "")
            assert bogus_id in detail, (
                f"AC-3: 422-Meldung muss die unbekannte segment_id "
                f"{bogus_id!r} nennen. Meldung: {detail!r}"
            )
        finally:
            shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)
