"""TDD-RED: Issue #1948 Scheibe S2 — AC-6/AC-7 Zweig-c-Replay
(``nowcast_frames``) am Preview-Endpoint.

SPEC: docs/specs/modules/alarm_testeinspeisung.md

AC-6: Frames mit Regen-Onset im Nowcast-Horizont -> dieselbe
``_derive_result``-Ableitung wie der Live-Radar-Pfad, volles Preview mit
``onset_detected: true``.
AC-7: Frames ohne Onset -> HTTP 200, ``onset_detected: false``, alle
Render-Felder ``null`` -- statt Exception/HTTP 500.

RED-Grund: ``AlertPreviewBody`` kennt heute kein ``nowcast_frames``-Feld
(Pydantic ignoriert es); mit leerem ``changes``/``onset`` liefert der
Endpunkt 422 statt 200.

Wanduhr-Ratsche (#1940): alle Frame-Zeitstempel sind relativ zu einem
``request_now``, der UNMITTELBAR vor dem Request erfasst wird -- keine
festen Uhrzeiten, kein Hour-Tipping.

Kein Mock — echter FastAPI-TestClient, echte Trip-Fixture.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.real_data_root


@pytest.fixture
def client():
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.fixture
def stub_trip():
    user_id = f"test_1948s2ac6_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-ac6"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "AC-6 Trip", "stages": [],
    }))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


def _wet_frames(now: datetime) -> list[dict]:
    """Erster nasser Frame nach 20 Minuten, 2.5 mm/h (>= "Maessiger Regen",
    < 4.0 mm/h Schwelle "Starker Regen")."""
    return [
        {"timestamp": (now + timedelta(minutes=5)).isoformat(),
         "precip_mm_h": 0.0, "is_convective": False},
        {"timestamp": (now + timedelta(minutes=20)).isoformat(),
         "precip_mm_h": 2.5, "is_convective": False},
        {"timestamp": (now + timedelta(minutes=40)).isoformat(),
         "precip_mm_h": 3.0, "is_convective": False},
    ]


def _dry_frames(now: datetime) -> list[dict]:
    """Alle Raten unter der Trockenschwelle (0.1 mm/h) -- kein Onset."""
    return [
        {"timestamp": (now + timedelta(minutes=m)).isoformat(),
         "precip_mm_h": 0.0, "is_convective": False}
        for m in (10, 30, 60)
    ]


class TestAC6_OnsetReplayDetectsOnset:
    def test_wet_frames_yield_onset_detected_true_with_derived_minutes(
        self, client, stub_trip,
    ):
        user_id, trip_id = stub_trip
        request_now = datetime.now(timezone.utc)
        body = {"nowcast_frames": {
            "source": "radar", "frames": _wet_frames(request_now),
            "km_from": 2.0, "km_to": 6.0,
        }}
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id}, json=body,
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        data = resp.json()
        assert data.get("onset_detected") is True, (
            f"AC-6: onset_detected muss True sein: {data!r}"
        )
        for field in ("subject", "email_html", "email_plain", "telegram", "sms"):
            assert data.get(field), (
                f"AC-6: '{field}' darf bei erkanntem Onset nicht leer sein: {data!r}"
            )

        match = re.search(r"R!(\d+)", data["sms"])
        assert match, (
            f"AC-6: SMS muss ein nicht-konvektives 'R!<Minuten>'-Token "
            f"tragen: {data['sms']!r}"
        )
        actual_minutes = int(match.group(1))
        assert abs(actual_minutes - 20) <= 1, (
            f"AC-6: onset_minutes muss aus derselben _derive_result-"
            f"Ableitung stammen wie der Live-Radar-Pfad (erster nasser "
            f"Frame bei ~20 Min), bekam R!{actual_minutes}"
        )
        assert (
            "Mäßiger Regen" in data["email_plain"]
            or "Mäßiger Regen" in data["telegram"]
        ), (
            f"AC-6: Intensitaets-Label 'Mäßiger Regen' (2.5 mm/h) muss "
            f"reflektiert werden.\nplain={data['email_plain']!r}\n"
            f"telegram={data['telegram']!r}"
        )


class TestAC7_NoOnsetReturns200WithNullFields:
    def test_dry_frames_yield_200_onset_false_and_null_render_fields(
        self, client, stub_trip,
    ):
        user_id, trip_id = stub_trip
        request_now = datetime.now(timezone.utc)
        body = {"nowcast_frames": {
            "source": "radar", "frames": _dry_frames(request_now),
        }}
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id}, json=body,
        )
        assert resp.status_code == 200, (
            f"AC-7: trockene Frames muessen 200 liefern, keine Exception "
            f"oder HTTP 500. War {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        assert data.get("onset_detected") is False, (
            f"AC-7: onset_detected muss False sein: {data!r}"
        )
        for field in ("subject", "email_html", "email_plain", "telegram", "sms"):
            assert data.get(field) is None, (
                f"AC-7: '{field}' muss null sein, wenn kein Onset erkannt "
                f"wurde: {data!r}"
            )
