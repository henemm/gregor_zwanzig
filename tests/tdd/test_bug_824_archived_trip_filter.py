"""
TDD RED — Bug #824: Archivierte Trips filtern + Stage-ID-Roundtrip

Spec: docs/specs/modules/bug_824_archived_trip_filter.md
Workflow: epic-825-stable-identity

RED-Ursache vor Fix:
- AC-1: load_all_trips() filtert archived_at nicht → archivierter Trip in Ergebnis
- AC-6: load_all_trips(user_id, include_archived=True) → TypeError (kein solcher Parameter)
- AC-2: _find_active_trip() ignoriert archived_at → gibt archivierten Trip zurück
- AC-3: load_all_trips() Basis für Scheduler gibt archived mit → archived in Ergebnis
- AC-4: load_all_trips() Basis für Alert gibt archived mit → archived verarbeitet
- AC-5: Stage-IDs nach load→save Roundtrip erhalten (wird durch TypeError bei
        include_archived=True blockiert, da save_trip auf load_all_trips aufbaut)

KEINE MOCKS — echte File-I/O via tmp_path + monkeypatch.chdir.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trip_json(trip_id: str, stage_date: str, archived_at: str | None = None) -> dict:
    data: dict = {
        "id": trip_id,
        "name": f"Trip {trip_id}",
        "stages": [
            {
                "id": f"stage-{trip_id}-1",
                "name": "Etappe 1",
                "date": stage_date,
                "waypoints": [
                    {
                        "id": f"wp-{trip_id}-1",
                        "name": "Start",
                        "lat": 42.0,
                        "lon": 9.0,
                        "elevation_m": 800,
                    }
                ],
            }
        ],
    }
    if archived_at is not None:
        data["archived_at"] = archived_at
    return data


@pytest.fixture()
def two_trip_env(tmp_path, monkeypatch):
    """Aktiver Trip: stage=MORGEN (future-Fallback).
    Archivierter Trip: stage=HEUTE (date-overlap → ohne Filter zwingend zuerst gefunden).

    _find_active_trip: prüft date-overlap zuerst → findet archived (heute).
    Nach Fix: archived gefiltert → active via future-Fallback.

    load_all_trips: gibt beide zurück (kein Filter).
    Nach Fix: gibt nur active zurück.
    """
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    trips_dir = tmp_path / "data" / "users" / "tdd-824" / "trips"
    trips_dir.mkdir(parents=True)

    active = _make_trip_json("active-824", stage_date=tomorrow, archived_at=None)
    archived = _make_trip_json("archived-824", stage_date=today, archived_at="2026-01-15T10:00:00Z")

    (trips_dir / "active-824.json").write_text(json.dumps(active), encoding="utf-8")
    (trips_dir / "archived-824.json").write_text(json.dumps(archived), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    return "tdd-824"


@pytest.fixture()
def two_trip_env_today(tmp_path, monkeypatch):
    """Beide Trips haben stage=HEUTE — Scheduler-Test (get_stage_for_date(today)).

    Ohne archived_at-Filter gibt load_all_trips beide zurück.
    """
    today = date.today().isoformat()
    trips_dir = tmp_path / "data" / "users" / "tdd-824-sched" / "trips"
    trips_dir.mkdir(parents=True)

    active = _make_trip_json("active-sched-824", stage_date=today, archived_at=None)
    archived = _make_trip_json("archived-sched-824", stage_date=today, archived_at="2026-01-15T10:00:00Z")

    (trips_dir / "active-sched-824.json").write_text(json.dumps(active), encoding="utf-8")
    (trips_dir / "archived-sched-824.json").write_text(json.dumps(archived), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    return "tdd-824-sched"


# ---------------------------------------------------------------------------
# AC-1: load_all_trips() ohne Parameter liefert NUR nicht-archivierte Trips
# ---------------------------------------------------------------------------

class TestAC1LoadAllTripsExcludesArchived:
    """AC-1: load_all_trips(user_id) ohne include_archived liefert nur aktive Trips."""

    def test_archived_trip_not_returned_by_default(self, two_trip_env):
        """GIVEN: 2 Trips (aktiv + archiviert) / WHEN: load_all_trips() ohne Param
        / THEN: nur aktiver Trip zurück — archivierter NICHT enthalten."""
        from app.loader import load_all_trips

        trips = load_all_trips(two_trip_env)

        assert len(trips) == 1, (
            f"load_all_trips() soll nur 1 aktiven Trip liefern, "
            f"lieferte aber {len(trips)}: {[t.id for t in trips]}"
        )
        assert trips[0].id == "active-824"

    def test_archived_trip_id_not_in_result(self, two_trip_env):
        """Archivierter Trip darf nicht in Ergebnisliste erscheinen."""
        from app.loader import load_all_trips

        trip_ids = {t.id for t in load_all_trips(two_trip_env)}
        assert "archived-824" not in trip_ids, (
            "Archivierter Trip 'archived-824' darf nicht von load_all_trips() "
            "zurückgegeben werden"
        )


# ---------------------------------------------------------------------------
# AC-6: load_all_trips(user_id, include_archived=True) enthält beide Trips
# ---------------------------------------------------------------------------

class TestAC6IncludeArchivedParam:
    """AC-6: include_archived=True gibt alle Trips zurück inkl. archivierter."""

    def test_include_archived_true_returns_all(self, two_trip_env):
        """GIVEN: 2 Trips / WHEN: load_all_trips(user_id, include_archived=True)
        / THEN: beide Trips im Ergebnis."""
        from app.loader import load_all_trips

        trips = load_all_trips(two_trip_env, include_archived=True)

        assert len(trips) == 2, (
            f"load_all_trips(include_archived=True) soll 2 Trips liefern, "
            f"lieferte {len(trips)}"
        )
        trip_ids = {t.id for t in trips}
        assert "active-824" in trip_ids
        assert "archived-824" in trip_ids

    def test_include_archived_false_matches_default(self, two_trip_env):
        """include_archived=False und kein Argument sollen identisch sein."""
        from app.loader import load_all_trips

        default_result = load_all_trips(two_trip_env)
        explicit_false = load_all_trips(two_trip_env, include_archived=False)

        assert {t.id for t in default_result} == {t.id for t in explicit_false}


# ---------------------------------------------------------------------------
# AC-2: _find_active_trip() ignoriert archivierte Trips
# ---------------------------------------------------------------------------

class TestAC2FindActiveTripSkipsArchived:
    """AC-2: _find_active_trip(user_id) gibt nur aktiven Trip zurück.

    Fixture: archivierter Trip hat stage=HEUTE (date-overlap) → ohne Filter zuerst gefunden.
    Aktiver Trip hat stage=MORGEN → nur via future-Fallback erreichbar.
    Nach Fix: archived gefiltert → active via future-Fallback zurückgegeben.
    """

    def test_find_active_trip_skips_archived(self, two_trip_env):
        """GIVEN: archived Trip mit stage=heute, aktiver Trip mit stage=morgen
        / WHEN: _find_active_trip()
        / THEN: aktiver Trip zurückgegeben (via future-Fallback), archivierter ignoriert."""
        from services.inbound_telegram_reader import InboundTelegramReader

        reader = InboundTelegramReader.__new__(InboundTelegramReader)
        trip = reader._find_active_trip(two_trip_env)

        assert trip is not None, "_find_active_trip() soll aktiven Trip finden"
        assert trip.archived_at is None, (
            f"_find_active_trip() darf keinen archivierten Trip zurückgeben, "
            f"gab aber Trip mit archived_at='{trip.archived_at}' zurück (id={trip.id})"
        )
        assert trip.id == "active-824", (
            f"_find_active_trip() soll 'active-824' zurückgeben, gab '{trip.id}' zurück"
        )


# ---------------------------------------------------------------------------
# AC-3: load_all_trips() Basis für Scheduler — archivierte ausgeschlossen
# ---------------------------------------------------------------------------

class TestAC3SchedulerBasisSkipsArchived:
    """AC-3: load_all_trips() (Basis für _get_active_trips) filtert archivierte Trips."""

    def test_load_all_trips_basis_excludes_archived(self, two_trip_env_today):
        """GIVEN: Nutzer mit aktivem + archiviertem Trip (beide Datum=heute)
        / WHEN: load_all_trips() — Basis für Scheduler
        / THEN: archivierter Trip nicht in Ergebnis."""
        from app.loader import load_all_trips

        trips = load_all_trips(two_trip_env_today)
        trip_ids = [t.id for t in trips]

        assert "archived-sched-824" not in trip_ids, (
            f"load_all_trips() (Basis für _get_active_trips) darf archivierten Trip "
            f"nicht liefern, erhielt aber: {trip_ids}"
        )

    def test_load_all_trips_basis_includes_active(self, two_trip_env_today):
        """load_all_trips() soll aktiven Trip mit heutigem Datum enthalten."""
        from app.loader import load_all_trips

        trips = load_all_trips(two_trip_env_today)
        trip_ids = [t.id for t in trips]

        assert "active-sched-824" in trip_ids, (
            f"load_all_trips() soll 'active-sched-824' enthalten, hat aber: {trip_ids}"
        )


# ---------------------------------------------------------------------------
# AC-4: load_all_trips() Basis für Alert — archivierte ausgeschlossen
# ---------------------------------------------------------------------------

class TestAC4AlertBasisSkipsArchived:
    """AC-4: load_all_trips() (Basis für check_all) enthält keine archivierten Trips."""

    def test_alert_basis_excludes_archived(self, two_trip_env):
        """GIVEN: Nutzer mit aktivem + archiviertem Trip
        / WHEN: load_all_trips(user_id) — Basis für check_all()
        / THEN: keine archivierten Trips in Ergebnis."""
        from app.loader import load_all_trips

        trips = load_all_trips(two_trip_env)
        archived_trips = [t for t in trips if t.archived_at is not None]

        assert len(archived_trips) == 0, (
            f"load_all_trips() (Basis für check_all) darf keine archivierten Trips "
            f"zurückgeben, lieferte aber: {[t.id for t in archived_trips]}"
        )


# ---------------------------------------------------------------------------
# AC-5: Stage-ID-Roundtrip bleibt stabil (load → save → load)
# ---------------------------------------------------------------------------

class TestAC5StageIdRoundtrip:
    """AC-5: Stage-IDs bleiben nach load→save Roundtrip identisch."""

    def test_stage_ids_preserved_after_roundtrip(self, tmp_path, monkeypatch):
        """GIVEN: Trip mit Stage-IDs gespeichert / WHEN: laden, speichern, wieder laden
        / THEN: Stage-IDs identisch — kein neues ensureStageIDs-Vergeben."""
        monkeypatch.chdir(tmp_path)
        trips_dir = tmp_path / "data" / "users" / "tdd-824-rt" / "trips"
        trips_dir.mkdir(parents=True)

        original_stage_ids = ["stage-rt-1", "stage-rt-2"]
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        trip_data = {
            "id": "roundtrip-824",
            "name": "Roundtrip Test",
            "stages": [
                {
                    "id": original_stage_ids[0],
                    "name": "Etappe 1",
                    "date": today,
                    "waypoints": [
                        {"id": "wp-rt-1", "name": "A", "lat": 42.0, "lon": 9.0, "elevation_m": 500}
                    ],
                },
                {
                    "id": original_stage_ids[1],
                    "name": "Etappe 2",
                    "date": tomorrow,
                    "waypoints": [
                        {"id": "wp-rt-2", "name": "B", "lat": 42.1, "lon": 9.1, "elevation_m": 600}
                    ],
                },
            ],
        }
        (trips_dir / "roundtrip-824.json").write_text(json.dumps(trip_data), encoding="utf-8")

        from app.loader import load_all_trips, save_trip

        # Laden — include_archived=True weil der Trip kein archived_at hat aber der
        # Parameter-Test selbst ist der RED-Beweis wenn TypeError kommt
        trips = load_all_trips("tdd-824-rt", include_archived=True)
        assert len(trips) == 1
        loaded_trip = trips[0]

        loaded_stage_ids = [s.id for s in loaded_trip.stages]
        assert loaded_stage_ids == original_stage_ids, (
            f"Stage-IDs nach Laden verändert: {loaded_stage_ids} != {original_stage_ids}"
        )

        # Speichern ohne Änderung
        save_trip(loaded_trip, user_id="tdd-824-rt")

        # Wieder laden
        reloaded = load_all_trips("tdd-824-rt", include_archived=True)
        assert len(reloaded) == 1
        reloaded_stage_ids = [s.id for s in reloaded[0].stages]

        assert reloaded_stage_ids == original_stage_ids, (
            f"Stage-IDs nach save_trip verändert: {reloaded_stage_ids} != {original_stage_ids}"
        )
