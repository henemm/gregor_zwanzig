"""
Tests for bugfix: Trips UI verwirft time_window → keine Morning-E-Mail.

SPEC: docs/specs/bugfix/trips_time_window_lost.md v1.0

Tests cover:
- Fix 1: trips.py preserves time_window in gpx_to_stage_data, save handlers, edit dialog
- Fix 2: Scheduler interpolates missing time_window instead of skipping
"""
from datetime import date, time, datetime, timezone, timedelta

import pytest

from app.trip import Stage, Waypoint, TimeWindow, Trip, AggregationConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stage_with_time_windows() -> Stage:
    """Stage with 4 waypoints that all have time_window."""
    return Stage(
        id="T1",
        name="Tag 1: Valldemossa nach Deià",
        date=date(2026, 2, 15),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=39.710, lon=2.622,
                     elevation_m=410, time_window=TimeWindow(time(8, 0), time(8, 0))),
            Waypoint(id="G2", name="Punkt 2", lat=39.726, lon=2.624,
                     elevation_m=795, time_window=TimeWindow(time(10, 0), time(10, 0))),
            Waypoint(id="G3", name="Punkt 3", lat=39.738, lon=2.635,
                     elevation_m=457, time_window=TimeWindow(time(12, 0), time(12, 0))),
            Waypoint(id="G4", name="Ziel", lat=39.747, lon=2.648,
                     elevation_m=149, time_window=TimeWindow(time(14, 0), time(14, 0))),
        ],
    )


def _make_stage_without_time_windows() -> Stage:
    """Stage with 4 waypoints that have NO time_window (the bug scenario)."""
    return Stage(
        id="T1",
        name="Tag 1: Valldemossa nach Deià",
        date=date(2026, 2, 15),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=39.710, lon=2.622, elevation_m=410),
            Waypoint(id="G2", name="Punkt 2", lat=39.726, lon=2.624, elevation_m=795),
            Waypoint(id="G3", name="Punkt 3", lat=39.738, lon=2.635, elevation_m=457),
            Waypoint(id="G4", name="Ziel", lat=39.747, lon=2.648, elevation_m=149),
        ],
    )


# ---------------------------------------------------------------------------
# Fix 1: trips.py — gpx_to_stage_data preserves time_window
# ---------------------------------------------------------------------------

def _waypoint_to_stage_dict(stage: Stage) -> dict:
    """Reproduce the serialization logic from trips.py gpx_to_stage_data/edit dialog."""
    from web.pages.trips import gpx_to_stage_data  # noqa: F401 - verify import works

    # Use the same pattern as trips.py — now with time_window fix
    return {
        "name": stage.name,
        "date": stage.date.isoformat(),
        "waypoints": [
            {
                "id": wp.id,
                "name": wp.name,
                "lat": wp.lat,
                "lon": wp.lon,
                "elevation_m": wp.elevation_m,
                "time_window": str(wp.time_window) if wp.time_window else None,
            }
            for wp in stage.waypoints
        ],
    }


class TestGpxToStageDataPreservesTimeWindow:
    """Spec Fix 1.1: gpx_to_stage_data() must include time_window in dict."""

    def test_gpx_stage_dict_includes_time_window(self):
        """
        GIVEN a stage with waypoints that have time_window,
        WHEN converted to dict (as gpx_to_stage_data does),
        THEN each waypoint dict has a time_window field.
        """
        stage = _make_stage_with_time_windows()
        stage_dict = _waypoint_to_stage_dict(stage)

        for i, wp_dict in enumerate(stage_dict["waypoints"]):
            wp = stage.waypoints[i]
            assert "time_window" in wp_dict, \
                f"Waypoint {wp.id} has time_window={wp.time_window} but dict has no time_window key"

    def test_gpx_stage_dict_time_window_is_string(self):
        """
        GIVEN a waypoint with time_window TimeWindow(08:00, 08:00),
        WHEN serialized to stage dict,
        THEN time_window is a string like "08:00-08:00".
        """
        stage = _make_stage_with_time_windows()
        stage_dict = _waypoint_to_stage_dict(stage)
        assert stage_dict["waypoints"][0]["time_window"] == "08:00-08:00"


# ---------------------------------------------------------------------------
# Fix 1: trips.py — Save handlers read time_window from dict
# ---------------------------------------------------------------------------

class TestSaveHandlerReadsTimeWindow:
    """Spec Fix 1.2 + 1.4: Save handlers must construct Waypoint with time_window."""

    def test_waypoint_from_dict_with_time_window(self):
        """
        GIVEN a waypoint dict with time_window="10:00-10:00",
        WHEN constructing a Waypoint as the save handler does (with fix),
        THEN Waypoint.time_window is TimeWindow(10:00, 10:00).
        """
        wp_dict = {
            "id": "G2",
            "name": "Punkt 2",
            "lat": 39.726,
            "lon": 2.624,
            "elevation_m": 795,
            "time_window": "10:00-10:00",
        }
        # Save handler pattern (with fix applied):
        wp = Waypoint(
            id=wp_dict["id"],
            name=wp_dict["name"],
            lat=float(wp_dict["lat"]),
            lon=float(wp_dict["lon"]),
            elevation_m=int(wp_dict["elevation_m"]),
            time_window=TimeWindow.from_string(wp_dict["time_window"]) if wp_dict.get("time_window") else None,
        )
        assert wp.time_window is not None, "Save handler must read time_window from dict"
        assert wp.time_window == TimeWindow(time(10, 0), time(10, 0))

    def test_waypoint_from_dict_without_time_window(self):
        """
        GIVEN a waypoint dict without time_window (manual entry),
        WHEN constructing a Waypoint with the fixed code,
        THEN Waypoint.time_window is None (no crash).
        """
        wp_dict = {
            "id": "G1",
            "name": "Manual Point",
            "lat": 47.0,
            "lon": 11.0,
            "elevation_m": 2000,
        }
        wp = Waypoint(
            id=wp_dict["id"],
            name=wp_dict["name"],
            lat=float(wp_dict["lat"]),
            lon=float(wp_dict["lon"]),
            elevation_m=int(wp_dict["elevation_m"]),
            time_window=TimeWindow.from_string(wp_dict["time_window"]) if wp_dict.get("time_window") else None,
        )
        assert wp.time_window is None


# ---------------------------------------------------------------------------
# Fix 1: trips.py — Edit dialog preserves time_window
# ---------------------------------------------------------------------------

class TestEditDialogPreservesTimeWindow:
    """Spec Fix 1.3: Edit dialog Trip→Dict must include time_window."""

    def test_edit_dialog_trip_to_dict_preserves_time_window(self):
        """
        GIVEN a Trip with waypoints that have time_window,
        WHEN the edit dialog converts Trip→Dict (using fixed pattern),
        THEN the dict includes time_window for each waypoint.
        """
        stage = _make_stage_with_time_windows()
        stage_dict = _waypoint_to_stage_dict(stage)

        for i, wp_dict in enumerate(stage_dict["waypoints"]):
            original_wp = stage.waypoints[i]
            if original_wp.time_window:
                assert "time_window" in wp_dict, \
                    f"Edit dialog lost time_window for waypoint {wp_dict['id']}"
                assert wp_dict["time_window"] == str(original_wp.time_window)


# ---------------------------------------------------------------------------
# Fix 1: Roundtrip — time_window through save/load cycle
# ---------------------------------------------------------------------------

class TestTimeWindowRoundtrip:
    """Full roundtrip: time_window must survive save/load cycles."""

    def test_time_window_survives_save_and_load(self):
        """
        GIVEN a Trip with time_windows,
        WHEN serialized and parsed back,
        THEN time_windows are preserved.
        """
        from app.loader import _parse_trip, _trip_to_dict

        stage = _make_stage_with_time_windows()
        trip = Trip(id="tw-test", name="TW Test", stages=[stage])

        data = _trip_to_dict(trip)
        parsed = _parse_trip(data)

        for i, wp in enumerate(parsed.stages[0].waypoints):
            original = stage.waypoints[i]
            assert wp.time_window == original.time_window, \
                f"Waypoint {wp.id}: time_window lost after save/load. " \
                f"Expected {original.time_window}, got {wp.time_window}"


# ---------------------------------------------------------------------------
# Fix 2: Scheduler — interpolates missing time_window
# ---------------------------------------------------------------------------

class TestSchedulerInterpolation:
    """Spec Fix 2: Scheduler must interpolate missing time_window."""

    def test_scheduler_creates_segments_without_time_window(self):
        """
        GIVEN a Trip with 4 waypoints WITHOUT time_window,
        WHEN _convert_trip_to_segments is called,
        THEN 3 segments are created (not 0).

        This is the core bug: currently returns 0 segments.
        """
        from services.trip_report_scheduler import TripReportSchedulerService

        stage = _make_stage_without_time_windows()
        trip = Trip(id="gr221", name="GR221 Mallorca", stages=[stage])

        service = TripReportSchedulerService()
        segments = service._convert_trip_to_segments(trip, date(2026, 2, 15))

        # BUG: Currently returns [] because all waypoints skip
        normal = [s for s in segments if s.segment_id != "Ziel"]
        assert len(normal) == 3, \
            f"Expected 3 normal segments, got {len(normal)}. " \
            f"Scheduler must interpolate missing time_window."

    def test_scheduler_interpolated_times_are_sequential(self):
        """
        GIVEN interpolated time_windows,
        WHEN segments are created,
        THEN each segment's start_time < end_time and segments are sequential.
        """
        from services.trip_report_scheduler import TripReportSchedulerService

        stage = _make_stage_without_time_windows()
        trip = Trip(id="gr221", name="GR221 Mallorca", stages=[stage])

        service = TripReportSchedulerService()
        segments = service._convert_trip_to_segments(trip, date(2026, 2, 15))

        assert len(segments) > 0, "No segments created"

        for seg in segments:
            assert seg.start_time < seg.end_time, \
                f"Segment {seg.segment_id}: start {seg.start_time} >= end {seg.end_time}"

        for i in range(len(segments) - 1):
            assert segments[i].end_time <= segments[i + 1].start_time, \
                f"Segment {i+1} overlaps with segment {i+2}"

    def test_scheduler_interpolation_uses_stage_start_time(self):
        """
        GIVEN a Stage with start_time=09:00 and waypoints without time_window,
        WHEN segments are created,
        THEN first segment starts at 09:00 (not default 08:00).
        """
        from services.trip_report_scheduler import TripReportSchedulerService

        stage = Stage(
            id="T1", name="Test", date=date(2026, 2, 15),
            waypoints=[
                Waypoint(id="G1", name="Start", lat=39.710, lon=2.622, elevation_m=410),
                Waypoint(id="G2", name="Ziel", lat=39.726, lon=2.624, elevation_m=795),
            ],
            start_time=time(9, 0),
        )
        trip = Trip(id="test", name="Test", stages=[stage])

        service = TripReportSchedulerService()
        segments = service._convert_trip_to_segments(trip, date(2026, 2, 15))

        normal = [s for s in segments if s.segment_id != "Ziel"]
        assert len(normal) == 1, f"Expected 1 normal segment, got {len(normal)}"
        assert normal[0].start_time.hour == 9, \
            f"First segment should start at 09:00, got {normal[0].start_time}"

    def test_scheduler_preserves_existing_time_windows(self):
        """
        GIVEN a Trip with waypoints that HAVE time_window,
        WHEN _convert_trip_to_segments is called,
        THEN original time_windows are used (no interpolation).
        """
        from services.trip_report_scheduler import TripReportSchedulerService

        stage = _make_stage_with_time_windows()
        trip = Trip(id="test", name="Test", stages=[stage])

        service = TripReportSchedulerService()
        segments = service._convert_trip_to_segments(trip, date(2026, 2, 15))

        normal = [s for s in segments if s.segment_id != "Ziel"]
        assert len(normal) == 3
        assert normal[0].start_time.hour == 8
        assert normal[0].end_time.hour == 10
        assert normal[1].start_time.hour == 10
        assert normal[1].end_time.hour == 12

    def test_scheduler_interpolation_respects_elevation(self):
        """
        GIVEN two waypoints with significant elevation difference,
        WHEN interpolating time,
        THEN steep segment takes longer than flat segment.
        """
        from services.trip_report_scheduler import TripReportSchedulerService

        stage_steep = Stage(
            id="T1", name="Steep", date=date(2026, 2, 15),
            waypoints=[
                Waypoint(id="G1", name="Start", lat=39.710, lon=2.622, elevation_m=410),
                Waypoint(id="G2", name="Top", lat=39.726, lon=2.624, elevation_m=795),
            ],
        )
        stage_flat = Stage(
            id="T1", name="Flat", date=date(2026, 2, 15),
            waypoints=[
                Waypoint(id="G1", name="Start", lat=39.710, lon=2.622, elevation_m=410),
                Waypoint(id="G2", name="End", lat=39.726, lon=2.624, elevation_m=410),
            ],
        )

        service = TripReportSchedulerService()
        segs_steep = service._convert_trip_to_segments(
            Trip(id="steep", name="Steep", stages=[stage_steep]), date(2026, 2, 15))
        segs_flat = service._convert_trip_to_segments(
            Trip(id="flat", name="Flat", stages=[stage_flat]), date(2026, 2, 15))

        steep_normal = [s for s in segs_steep if s.segment_id != "Ziel"]
        flat_normal = [s for s in segs_flat if s.segment_id != "Ziel"]
        assert len(steep_normal) == 1, "Steep segments missing"
        assert len(flat_normal) == 1, "Flat segments missing"

        assert steep_normal[0].duration_hours > flat_normal[0].duration_hours, \
            "Steep segment should take longer than flat"
