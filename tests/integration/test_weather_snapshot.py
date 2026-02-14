"""
Integration tests for WeatherSnapshotService.

ALERT-01: Weather Snapshot Service
Tests save/load roundtrip, graceful failure, enum serialization, multi-user isolation.

SPEC: docs/specs/modules/weather_snapshot.md v1.0

TDD RED: These tests MUST FAIL because src/services/weather_snapshot.py does not exist yet.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.models import (
    GPXPoint,
    PrecipType,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_segment(segment_id: int, hour_start: int, hour_end: int) -> TripSegment:
    """Create a minimal TripSegment for testing."""
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=39.76, lon=2.65),
        end_point=GPXPoint(lat=39.80, lon=2.70),
        start_time=datetime(2026, 2, 14, hour_start, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 14, hour_end, 0, tzinfo=timezone.utc),
        duration_hours=float(hour_end - hour_start),
        distance_km=5.0,
        ascent_m=300.0,
        descent_m=100.0,
    )


def _make_summary(**overrides) -> SegmentWeatherSummary:
    """Create a SegmentWeatherSummary with sensible defaults + overrides."""
    defaults = dict(
        temp_min_c=5.2,
        temp_max_c=9.8,
        temp_avg_c=7.5,
        wind_max_kmh=35.0,
        gust_max_kmh=52.0,
        precip_sum_mm=0.2,
        cloud_avg_pct=65,
        humidity_avg_pct=78,
    )
    defaults.update(overrides)
    return SegmentWeatherSummary(**defaults)


def _make_segment_weather(
    segment_id: int = 1,
    hour_start: int = 8,
    hour_end: int = 10,
    summary_overrides: dict | None = None,
) -> SegmentWeatherData:
    """Create a SegmentWeatherData with aggregated summary for testing."""
    segment = _make_segment(segment_id, hour_start, hour_end)
    summary = _make_summary(**(summary_overrides or {}))
    return SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=summary,
        fetched_at=datetime(2026, 2, 14, 7, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


# ---------------------------------------------------------------------------
# Test 1: Save and Load Roundtrip
# ---------------------------------------------------------------------------

class TestSaveAndLoadRoundtrip:
    """SPEC Test 1: Save then load — data must match."""

    def test_roundtrip_two_segments(self, tmp_path: Path) -> None:
        """
        GIVEN: Two SegmentWeatherData with filled aggregated summaries
        WHEN: save() then load()
        THEN: Loaded data matches (segment_id, times, aggregated values)
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService(user_id="default")
        service._snapshots_dir = tmp_path

        seg1 = _make_segment_weather(segment_id=1, hour_start=8, hour_end=10)
        seg2 = _make_segment_weather(
            segment_id=2, hour_start=10, hour_end=12,
            summary_overrides={"temp_max_c": 12.5, "wind_max_kmh": 28.0},
        )

        service.save("test-trip", [seg1, seg2], date(2026, 2, 14))

        loaded = service.load("test-trip")

        assert loaded is not None
        assert len(loaded) == 2

        # Segment IDs match
        assert loaded[0].segment.segment_id == 1
        assert loaded[1].segment.segment_id == 2

        # Times match
        assert loaded[0].segment.start_time == seg1.segment.start_time
        assert loaded[0].segment.end_time == seg1.segment.end_time

        # Aggregated values match
        assert loaded[0].aggregated.temp_max_c == 9.8
        assert loaded[0].aggregated.wind_max_kmh == 35.0
        assert loaded[1].aggregated.temp_max_c == 12.5
        assert loaded[1].aggregated.wind_max_kmh == 28.0

        # Provider preserved
        assert loaded[0].provider == "openmeteo"

        # Timeseries is None (not stored in snapshot)
        assert loaded[0].timeseries is None

    def test_roundtrip_preserves_all_numeric_fields(self, tmp_path: Path) -> None:
        """
        GIVEN: SegmentWeatherSummary with ALL numeric fields set
        WHEN: save() then load()
        THEN: Every field value is preserved
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        full_summary = SegmentWeatherSummary(
            temp_min_c=-2.5,
            temp_max_c=15.3,
            temp_avg_c=6.4,
            wind_max_kmh=45.0,
            gust_max_kmh=68.0,
            precip_sum_mm=12.5,
            cloud_avg_pct=85,
            humidity_avg_pct=92,
            visibility_min_m=3000,
            dewpoint_avg_c=4.2,
            pressure_avg_hpa=1013.25,
            wind_chill_min_c=-8.1,
            snow_depth_cm=25.0,
            freezing_level_m=1800,
            pop_max_pct=90,
            cape_max_jkg=150.0,
            uv_index_max=3.5,
            snow_new_sum_cm=5.0,
            wind_direction_avg_deg=270,
        )

        seg = _make_segment_weather()
        seg.aggregated = full_summary

        service.save("full-trip", [seg], date(2026, 2, 14))
        loaded = service.load("full-trip")

        assert loaded is not None
        s = loaded[0].aggregated

        assert s.temp_min_c == -2.5
        assert s.temp_max_c == 15.3
        assert s.temp_avg_c == 6.4
        assert s.wind_max_kmh == 45.0
        assert s.gust_max_kmh == 68.0
        assert s.precip_sum_mm == 12.5
        assert s.cloud_avg_pct == 85
        assert s.humidity_avg_pct == 92
        assert s.visibility_min_m == 3000
        assert s.dewpoint_avg_c == 4.2
        assert s.pressure_avg_hpa == 1013.25
        assert s.wind_chill_min_c == -8.1
        assert s.snow_depth_cm == 25.0
        assert s.freezing_level_m == 1800
        assert s.pop_max_pct == 90
        assert s.cape_max_jkg == 150.0
        assert s.uv_index_max == 3.5
        assert s.snow_new_sum_cm == 5.0
        assert s.wind_direction_avg_deg == 270


# ---------------------------------------------------------------------------
# Test 2: Load Missing File
# ---------------------------------------------------------------------------

class TestLoadMissingFile:
    """SPEC Test 2: Load non-existent snapshot returns None."""

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        """
        GIVEN: No snapshot file for trip_id
        WHEN: load(trip_id)
        THEN: Returns None, no exception
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        result = service.load("nonexistent-trip")
        assert result is None


# ---------------------------------------------------------------------------
# Test 3: Load Corrupt File
# ---------------------------------------------------------------------------

class TestLoadCorruptFile:
    """SPEC Test 3: Corrupt JSON returns None gracefully."""

    def test_invalid_json_returns_none(self, tmp_path: Path) -> None:
        """
        GIVEN: Snapshot file with invalid JSON
        WHEN: load(trip_id)
        THEN: Returns None, no exception
        """
        from services.weather_snapshot import WeatherSnapshotService

        corrupt_file = tmp_path / "broken-trip.json"
        corrupt_file.write_text("{invalid json content!!!")

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        result = service.load("broken-trip")
        assert result is None

    def test_missing_segments_key_returns_none(self, tmp_path: Path) -> None:
        """
        GIVEN: Snapshot file with valid JSON but missing 'segments' key
        WHEN: load(trip_id)
        THEN: Returns None
        """
        from services.weather_snapshot import WeatherSnapshotService

        bad_file = tmp_path / "bad-structure.json"
        bad_file.write_text(json.dumps({"trip_id": "bad-structure"}))

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        result = service.load("bad-structure")
        assert result is None


# ---------------------------------------------------------------------------
# Test 4: Save Failure (Graceful)
# ---------------------------------------------------------------------------

class TestSaveFailure:
    """SPEC Test 4: Save failure logs warning, does not raise."""

    def test_save_to_readonly_dir_does_not_raise(self, tmp_path: Path) -> None:
        """
        GIVEN: Snapshots directory is not writable
        WHEN: save()
        THEN: No exception raised (graceful failure)
        """
        from services.weather_snapshot import WeatherSnapshotService

        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        service = WeatherSnapshotService()
        service._snapshots_dir = readonly_dir

        seg = _make_segment_weather()

        # Must NOT raise
        service.save("test-trip", [seg], date(2026, 2, 14))

        # Cleanup permissions for tmp_path cleanup
        readonly_dir.chmod(0o755)


# ---------------------------------------------------------------------------
# Test 5: Enum Serialization
# ---------------------------------------------------------------------------

class TestEnumSerialization:
    """SPEC Test 5: Enums roundtrip correctly."""

    def test_thunder_level_roundtrip(self, tmp_path: Path) -> None:
        """
        GIVEN: SegmentWeatherSummary with thunder_level_max=ThunderLevel.HIGH
        WHEN: save() then load()
        THEN: Loaded value is ThunderLevel.HIGH (enum, not string)
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        seg = _make_segment_weather(
            summary_overrides={"thunder_level_max": ThunderLevel.HIGH}
        )

        service.save("thunder-trip", [seg], date(2026, 2, 14))
        loaded = service.load("thunder-trip")

        assert loaded is not None
        assert loaded[0].aggregated.thunder_level_max == ThunderLevel.HIGH
        assert isinstance(loaded[0].aggregated.thunder_level_max, ThunderLevel)

    def test_thunder_level_stored_as_string_in_json(self, tmp_path: Path) -> None:
        """
        GIVEN: Saved snapshot with ThunderLevel enum
        WHEN: Read raw JSON
        THEN: Value is string "MED", not enum
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        seg = _make_segment_weather(
            summary_overrides={"thunder_level_max": ThunderLevel.MED}
        )

        service.save("thunder-json", [seg], date(2026, 2, 14))

        raw = json.loads((tmp_path / "thunder-json.json").read_text())
        assert raw["segments"][0]["aggregated"]["thunder_level_max"] == "MED"

    def test_precip_type_roundtrip(self, tmp_path: Path) -> None:
        """
        GIVEN: SegmentWeatherSummary with precip_type_dominant=PrecipType.SNOW
        WHEN: save() then load()
        THEN: Loaded value is PrecipType.SNOW (enum, not string)
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        seg = _make_segment_weather(
            summary_overrides={"precip_type_dominant": PrecipType.SNOW}
        )

        service.save("precip-trip", [seg], date(2026, 2, 14))
        loaded = service.load("precip-trip")

        assert loaded is not None
        assert loaded[0].aggregated.precip_type_dominant == PrecipType.SNOW
        assert isinstance(loaded[0].aggregated.precip_type_dominant, PrecipType)


# ---------------------------------------------------------------------------
# Test 6: None Field Handling
# ---------------------------------------------------------------------------

class TestNoneFieldHandling:
    """SPEC Test 6: None fields omitted from JSON, restored as None."""

    def test_none_fields_omitted_from_json(self, tmp_path: Path) -> None:
        """
        GIVEN: SegmentWeatherSummary with visibility_min_m=None
        WHEN: save()
        THEN: JSON does NOT contain "visibility_min_m" key
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        seg = _make_segment_weather(
            summary_overrides={"visibility_min_m": None}
        )

        service.save("none-trip", [seg], date(2026, 2, 14))

        raw = json.loads((tmp_path / "none-trip.json").read_text())
        aggregated = raw["segments"][0]["aggregated"]
        assert "visibility_min_m" not in aggregated

    def test_none_fields_restored_as_none(self, tmp_path: Path) -> None:
        """
        GIVEN: Snapshot JSON without "visibility_min_m" key
        WHEN: load()
        THEN: Loaded summary has visibility_min_m=None
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        seg = _make_segment_weather()
        service.save("none-restore", [seg], date(2026, 2, 14))
        loaded = service.load("none-restore")

        assert loaded is not None
        assert loaded[0].aggregated.visibility_min_m is None


# ---------------------------------------------------------------------------
# Test 7: Multi-User Isolation
# ---------------------------------------------------------------------------

class TestMultiUserIsolation:
    """SPEC Test 7: Users see only their own snapshots."""

    def test_user_isolation(self, tmp_path: Path) -> None:
        """
        GIVEN: Snapshots for user "alice" and user "bob"
        WHEN: alice loads trip_id
        THEN: Gets alice's data, not bob's
        """
        from services.weather_snapshot import WeatherSnapshotService

        alice_dir = tmp_path / "alice"
        bob_dir = tmp_path / "bob"

        alice_service = WeatherSnapshotService(user_id="alice")
        alice_service._snapshots_dir = alice_dir

        bob_service = WeatherSnapshotService(user_id="bob")
        bob_service._snapshots_dir = bob_dir

        seg_alice = _make_segment_weather(
            summary_overrides={"temp_max_c": 20.0}
        )
        seg_bob = _make_segment_weather(
            summary_overrides={"temp_max_c": -5.0}
        )

        alice_service.save("shared-trip", [seg_alice], date(2026, 2, 14))
        bob_service.save("shared-trip", [seg_bob], date(2026, 2, 14))

        alice_data = alice_service.load("shared-trip")
        bob_data = bob_service.load("shared-trip")

        assert alice_data is not None
        assert bob_data is not None
        assert alice_data[0].aggregated.temp_max_c == 20.0
        assert bob_data[0].aggregated.temp_max_c == -5.0


# ---------------------------------------------------------------------------
# Test: JSON file structure
# ---------------------------------------------------------------------------

class TestJsonStructure:
    """Verify the JSON snapshot format matches the spec."""

    def test_snapshot_has_required_top_level_keys(self, tmp_path: Path) -> None:
        """
        GIVEN: Saved snapshot
        WHEN: Read raw JSON
        THEN: Has trip_id, target_date, snapshot_at, provider, segments
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        seg = _make_segment_weather()
        service.save("structure-trip", [seg], date(2026, 2, 14))

        raw = json.loads((tmp_path / "structure-trip.json").read_text())

        assert raw["trip_id"] == "structure-trip"
        assert raw["target_date"] == "2026-02-14"
        assert "snapshot_at" in raw
        assert raw["provider"] == "openmeteo"
        assert len(raw["segments"]) == 1

    def test_segment_has_required_keys(self, tmp_path: Path) -> None:
        """
        GIVEN: Saved snapshot
        WHEN: Read raw JSON segment
        THEN: Has segment_id, start_time, end_time, aggregated
        """
        from services.weather_snapshot import WeatherSnapshotService

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        seg = _make_segment_weather()
        service.save("keys-trip", [seg], date(2026, 2, 14))

        raw = json.loads((tmp_path / "keys-trip.json").read_text())
        seg_json = raw["segments"][0]

        assert seg_json["segment_id"] == 1
        assert "start_time" in seg_json
        assert "end_time" in seg_json
        assert "aggregated" in seg_json


# ---------------------------------------------------------------------------
# Test: Loader helper
# ---------------------------------------------------------------------------

class TestLoaderHelper:
    """Verify get_snapshots_dir() exists and follows pattern."""

    def test_get_snapshots_dir_default(self) -> None:
        """
        GIVEN: Default user_id
        WHEN: get_snapshots_dir()
        THEN: Returns Path("data/users/default/weather_snapshots")
        """
        from app.loader import get_snapshots_dir

        result = get_snapshots_dir()
        assert result == Path("data/users/default/weather_snapshots")

    def test_get_snapshots_dir_custom_user(self) -> None:
        """
        GIVEN: Custom user_id "alice"
        WHEN: get_snapshots_dir("alice")
        THEN: Returns Path("data/users/alice/weather_snapshots")
        """
        from app.loader import get_snapshots_dir

        result = get_snapshots_dir("alice")
        assert result == Path("data/users/alice/weather_snapshots")
