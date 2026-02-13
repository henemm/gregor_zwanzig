"""
Tests for Stage start_time and test report functionality.

SPEC: docs/specs/modules/trips_test_reports_start_times.md v1.0
"""
from datetime import date, time

import pytest

from app.trip import Stage, Waypoint, TimeWindow, Trip, AggregationConfig
from app.loader import _parse_trip, _trip_to_dict


# ---------------------------------------------------------------------------
# Feature 1: Stage Start Time
# ---------------------------------------------------------------------------

class TestStageStartTime:
    """Spec: Stage has optional start_time field."""

    def test_stage_with_start_time(self):
        """GIVEN a Stage with start_time=09:00, THEN start_time is accessible."""
        stage = Stage(
            id="T1", name="Test", date=date(2026, 3, 1),
            waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000)],
            start_time=time(9, 0),
        )
        assert stage.start_time == time(9, 0)

    def test_stage_without_start_time(self):
        """GIVEN a Stage without start_time, THEN start_time is None."""
        stage = Stage(
            id="T1", name="Test", date=date(2026, 3, 1),
            waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000)],
        )
        assert stage.start_time is None


class TestStartTimeSerialization:
    """Spec: start_time serialized/deserialized in JSON."""

    def test_roundtrip_with_start_time(self):
        """GIVEN Trip with stage.start_time=09:00,
        WHEN serialized and parsed back,
        THEN start_time is preserved."""
        stage = Stage(
            id="T1", name="Tag 1", date=date(2026, 3, 1),
            waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000)],
            start_time=time(9, 0),
        )
        trip = Trip(id="test", name="Test", stages=[stage])
        data = _trip_to_dict(trip)
        parsed = _parse_trip(data)
        assert parsed.stages[0].start_time == time(9, 0)

    def test_roundtrip_without_start_time(self):
        """GIVEN Trip without start_time,
        WHEN serialized and parsed back,
        THEN start_time is None (backward compat)."""
        stage = Stage(
            id="T1", name="Tag 1", date=date(2026, 3, 1),
            waypoints=[Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000)],
        )
        trip = Trip(id="test", name="Test", stages=[stage])
        data = _trip_to_dict(trip)
        # Ensure no start_time key if None
        assert "start_time" not in data["stages"][0]
        parsed = _parse_trip(data)
        assert parsed.stages[0].start_time is None

    def test_parse_legacy_json_without_start_time(self):
        """GIVEN old JSON format without start_time field,
        WHEN parsed,
        THEN stage.start_time is None (backward compat)."""
        data = {
            "id": "legacy",
            "name": "Legacy Trip",
            "stages": [{
                "id": "T1",
                "name": "Tag 1",
                "date": "2026-03-01",
                "waypoints": [{
                    "id": "G1", "name": "Start",
                    "lat": 47.0, "lon": 11.0, "elevation_m": 1000,
                }],
            }],
        }
        trip = _parse_trip(data)
        assert trip.stages[0].start_time is None


# ---------------------------------------------------------------------------
# Feature 2: Test Report Public API
# ---------------------------------------------------------------------------

class TestSendTestReportAPI:
    """Spec: TripReportSchedulerService has public send_test_report method."""

    def test_send_test_report_method_exists(self):
        """GIVEN TripReportSchedulerService,
        THEN send_test_report() method exists."""
        from services.trip_report_scheduler import TripReportSchedulerService
        service = TripReportSchedulerService()
        assert hasattr(service, "send_test_report")
        assert callable(service.send_test_report)

    def test_send_test_report_invalid_type(self):
        """GIVEN invalid report_type,
        WHEN send_test_report() called,
        THEN raises ValueError."""
        from services.trip_report_scheduler import TripReportSchedulerService
        service = TripReportSchedulerService()
        stage = Stage(
            id="T1", name="Test", date=date(2026, 3, 1),
            waypoints=[Waypoint(id="G1", name="S", lat=47.0, lon=11.0, elevation_m=1000)],
        )
        trip = Trip(id="test", name="Test", stages=[stage])
        with pytest.raises(ValueError, match="Invalid report_type"):
            service.send_test_report(trip, "invalid")
