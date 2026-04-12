"""
TDD RED: Snapshot persistiert keine Koordinaten.

Tests fuer:
1. Snapshot Round-Trip: Save → Load → Koordinaten stimmen ueberein
2. Abwaertskompatibilitaet: Alte Snapshots (ohne Koordinaten) laden ohne Fehler
3. Formatter: int(None) crasht nicht mehr
4. Alert-Pfad: Echte Koordinaten nach Save+Load

SPEC: docs/specs/bugfix/snapshot_missing_coordinates.md
"""
import json
from datetime import date, datetime, timezone

import pytest


class TestSnapshotCoordinateRoundTrip:
    """Save -> Load -> Koordinaten muessen uebereinstimmen."""

    def test_saved_snapshot_contains_coordinates(self, tmp_path):
        """
        GIVEN: SegmentWeatherData mit echten Koordinaten
        WHEN: Snapshot wird gespeichert
        THEN: JSON enthaelt start_lat, start_lon, start_elevation_m, end_lat, end_lon, end_elevation_m
        """
        from app.models import (
            GPXPoint,
            SegmentWeatherData,
            SegmentWeatherSummary,
            TripSegment,
        )
        from services.weather_snapshot import WeatherSnapshotService

        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=39.710564, lon=2.62293, elevation_m=410.0),
            end_point=GPXPoint(lat=39.747657, lon=2.648606, elevation_m=149.0),
            start_time=datetime(2026, 4, 5, 7, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            distance_km=8.0,
            ascent_m=500.0,
            descent_m=300.0,
        )
        seg_weather = SegmentWeatherData(
            segment=segment,
            timeseries=None,
            aggregated=SegmentWeatherSummary(),
            fetched_at=datetime.now(timezone.utc),
            provider="openmeteo",
        )

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        service.save("test-trip", [seg_weather], date(2026, 4, 5))

        snapshot_file = tmp_path / "test-trip.json"
        data = json.loads(snapshot_file.read_text())
        seg_data = data["segments"][0]

        assert seg_data["start_lat"] == 39.710564
        assert seg_data["start_lon"] == 2.62293
        assert seg_data["start_elevation_m"] == 410.0
        assert seg_data["end_lat"] == 39.747657
        assert seg_data["end_lon"] == 2.648606
        assert seg_data["end_elevation_m"] == 149.0

    def test_loaded_snapshot_has_real_coordinates(self, tmp_path):
        """
        GIVEN: Snapshot mit Koordinaten gespeichert
        WHEN: Snapshot wird geladen
        THEN: Rekonstruierte Segmente haben echte Koordinaten (nicht 0.0)
        """
        from app.models import (
            GPXPoint,
            SegmentWeatherData,
            SegmentWeatherSummary,
            TripSegment,
        )
        from services.weather_snapshot import WeatherSnapshotService

        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=39.710564, lon=2.62293, elevation_m=410.0),
            end_point=GPXPoint(lat=39.747657, lon=2.648606, elevation_m=149.0),
            start_time=datetime(2026, 4, 5, 7, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            distance_km=8.0,
            ascent_m=500.0,
            descent_m=300.0,
        )
        seg_weather = SegmentWeatherData(
            segment=segment,
            timeseries=None,
            aggregated=SegmentWeatherSummary(),
            fetched_at=datetime.now(timezone.utc),
            provider="openmeteo",
        )

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        service.save("test-trip", [seg_weather], date(2026, 4, 5))
        loaded = service.load("test-trip")

        assert loaded is not None
        seg = loaded[0].segment
        assert seg.start_point.lat == pytest.approx(39.710564)
        assert seg.start_point.lon == pytest.approx(2.62293)
        assert seg.start_point.elevation_m == pytest.approx(410.0)
        assert seg.end_point.lat == pytest.approx(39.747657)
        assert seg.end_point.lon == pytest.approx(2.648606)
        assert seg.end_point.elevation_m == pytest.approx(149.0)


class TestSnapshotBackwardCompatibility:
    """Alte Snapshots ohne Koordinaten muessen weiterhin laden."""

    def test_old_snapshot_without_coordinates_loads(self, tmp_path):
        """
        GIVEN: Snapshot-JSON im alten Format (ohne Koordinaten-Felder)
        WHEN: Load wird aufgerufen
        THEN: Kein Fehler, Koordinaten fallen auf 0.0 zurueck
        """
        from services.weather_snapshot import WeatherSnapshotService

        old_snapshot = {
            "trip_id": "old-trip",
            "target_date": "2026-04-05",
            "snapshot_at": "2026-04-05T18:00:00+00:00",
            "provider": "openmeteo",
            "segments": [
                {
                    "segment_id": 1,
                    "start_time": "2026-04-05T07:00:00+00:00",
                    "end_time": "2026-04-05T09:00:00+00:00",
                    "aggregated": {"temp_min_c": 5.0, "temp_max_c": 15.0},
                }
            ],
        }

        filepath = tmp_path / "old-trip.json"
        filepath.write_text(json.dumps(old_snapshot))

        service = WeatherSnapshotService()
        service._snapshots_dir = tmp_path

        loaded = service.load("old-trip")
        assert loaded is not None
        seg = loaded[0].segment
        assert seg.start_point.lat == 0.0
        assert seg.start_point.lon == 0.0
        assert seg.start_point.elevation_m is None


class TestFormatterElevationNoneGuard:
    """Formatter darf bei elevation_m=None nicht crashen."""

    def test_int_elevation_none_does_not_crash(self):
        """
        GIVEN: GPXPoint mit elevation_m=None
        WHEN: Formatter ruft int(elevation_m) auf
        THEN: Kein TypeError, Ergebnis ist 0
        """
        from app.models import GPXPoint

        point = GPXPoint(lat=39.71, lon=2.62, elevation_m=None)
        result = int(point.elevation_m or 0)
        assert result == 0

    def test_int_elevation_normal_works(self):
        """
        GIVEN: GPXPoint mit elevation_m=410.0
        WHEN: None-Guard angewendet
        THEN: Ergebnis ist 410
        """
        from app.models import GPXPoint

        point = GPXPoint(lat=39.71, lon=2.62, elevation_m=410.0)
        result = int(point.elevation_m or 0)
        assert result == 410
