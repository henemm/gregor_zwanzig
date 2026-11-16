"""Geteilte Test-Umgebung der Vorschau-/Alarm-Vorschau-Tests (Issue #2283).

Herkunft: die Fixtures standen in ``tests/integration/test_briefing_preview_bundle.py``,
das mit dem Rueckbau der kind-neutralen Briefing-Vorschau (#1743) entfallen
ist. Die Alarm-Vorschau-Tests nutzen sie weiter.

- ``env``: isolierter Daten-Root ueber beide Loader-Zugriffsformen, echte
  Nutzerkennung (niemals ``"default"``).
- ``seed_trip`` / ``seed_compare``: legen einen Trip bzw. einen Ortsvergleich
  samt Orten im Daten-Root dieses Nutzers an.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import pytest

from app.loader import get_briefings_dir, get_data_dir, save_location
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

TRIP_DATE = (date.today() + timedelta(days=1)).isoformat()


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolierter Daten-Root ueber beide Zugriffsformen (Muster
    test_compare_preview_service.py::compare_env); echte Nutzerkennung,
    niemals 'default'."""
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    try:
        from src.app import loader as src_loader

        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(data_root))
    except ImportError:  # pragma: no cover
        pass
    return f"tdd-2283-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def mittagsuhr():
    """Gestellte Uhr (#3047), heute 12:00 UTC statt Wanduhr.

    Die Trip-Anker der Vorschau-Tests decken HEUTE 00:00-23:59 ab. Ab 23:59 UTC
    liegt das Segment in der Vergangenheit, der Frisch-Abruf entfaellt zu Recht
    und der Test wird rot (CI-Lauf 2026-11-15 23:59). Muster:
    ``frozen_active_window()`` (#2050).

    ``pydantic.v1`` wird VOR dem Einfrieren geladen: FastAPI importiert es beim
    ersten Router-Aufbau nach, und unter freezegun scheitert dessen
    ``datetime``-Unterklasse mit einem Metaklassen-Konflikt.

    Gestellt wird NUR die Kalenderuhr: ``time.monotonic``/``perf_counter``
    bleiben echt. Die Vorschau ruft frisch in einem Hilfsfaden mit
    monotoner Frist ab (``alert_preview_hours._within``,
    ``parallel_fetch.fetch_ordered``); freezegun beantwortet ``monotonic()``
    dort je nach Aufrufstapel mal echt, mal gestellt, und die Frist liefe
    sofort ab -- ein Messartefakt, kein Produktverhalten."""
    import time

    import pydantic.v1.types  # noqa: F401
    from freezegun import api as freezegun_api

    from tests.helpers.nowcast_gate_fixtures import frozen_active_window

    with frozen_active_window() as anker:
        time.monotonic = freezegun_api.real_monotonic
        time.perf_counter = freezegun_api.real_perf_counter
        yield anker


def seed_trip(user_id: str, trip_id: str, name: str) -> None:
    trips_dir = get_briefings_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": trip_id,
        "name": name,
        "stages": [
            {
                "id": "T1", "name": "Etappe 1", "date": TRIP_DATE,
                "waypoints": [
                    {"id": "G1", "name": "Start", "lat": 47.2692, "lon": 11.4041,
                     "elevation_m": 600},
                    {"id": "G2", "name": "Ziel", "lat": 47.3010, "lon": 11.4500,
                     "elevation_m": 1200},
                ],
            }
        ],
    }
    (trips_dir / f"{trip_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def seed_compare(user_id: str, preset_id: str, locations: list[SavedLocation]) -> None:
    for loc in locations:
        save_location(loc, user_id=user_id)
    write_compare_briefings(
        get_data_dir(user_id),
        [{
            "id": preset_id,
            "name": "Urlaubsorte 2283",
            "user_id": user_id,
            "location_ids": [loc.id for loc in locations],
            "schedule": "daily",
            "profil": "ALLGEMEIN",
            "hour_from": 9,
            "hour_to": 16,
            "forecast_hours": 48,
            "empfaenger": ["a@example.invalid"],
            "created_at": "2026-07-01T00:00:00Z",
        }],
    )
