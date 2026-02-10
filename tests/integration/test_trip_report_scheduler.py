"""
Integration tests for TripReportSchedulerService.

Feature 3.3: Report-Scheduler
Tests the trip report scheduling and email delivery.

SPEC: docs/specs/modules/trip_report_scheduler.md v1.0
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.models import GPXPoint, TripSegment
from app.trip import Stage, TimeWindow, Trip, Waypoint


class TestTripToSegmentConversion:
    """Test conversion of Trip waypoints to TripSegment DTOs."""

    def test_convert_two_waypoints_to_one_segment(self) -> None:
        """Two waypoints should create one segment between them."""
        from services.trip_report_scheduler import TripReportSchedulerService

        today = date.today()
        trip = _create_test_trip(today, num_waypoints=2)

        service = TripReportSchedulerService()
        segments = service._convert_trip_to_segments(trip, today)

        assert len(segments) == 1
        assert segments[0].segment_id == 1
        assert segments[0].start_point.lat == 47.0
        assert segments[0].end_point.lat == 47.1

    def test_convert_three_waypoints_to_two_segments(self) -> None:
        """Three waypoints should create two segments."""
        from services.trip_report_scheduler import TripReportSchedulerService

        today = date.today()
        trip = _create_test_trip(today, num_waypoints=3)

        service = TripReportSchedulerService()
        segments = service._convert_trip_to_segments(trip, today)

        assert len(segments) == 2
        assert segments[0].segment_id == 1
        assert segments[1].segment_id == 2

    def test_no_segments_for_wrong_date(self) -> None:
        """Trip should return no segments for a date without a stage."""
        from services.trip_report_scheduler import TripReportSchedulerService

        today = date.today()
        tomorrow = today + timedelta(days=1)
        trip = _create_test_trip(today, num_waypoints=3)

        service = TripReportSchedulerService()
        segments = service._convert_trip_to_segments(trip, tomorrow)

        assert len(segments) == 0

    def test_segment_times_are_utc(self) -> None:
        """Segment start/end times should be UTC."""
        from services.trip_report_scheduler import TripReportSchedulerService

        today = date.today()
        trip = _create_test_trip(today, num_waypoints=2)

        service = TripReportSchedulerService()
        segments = service._convert_trip_to_segments(trip, today)

        assert segments[0].start_time.tzinfo == timezone.utc
        assert segments[0].end_time.tzinfo == timezone.utc

    def test_segment_duration_calculated(self) -> None:
        """Segment duration should be calculated from time windows."""
        from services.trip_report_scheduler import TripReportSchedulerService

        today = date.today()
        trip = _create_test_trip(today, num_waypoints=2)

        service = TripReportSchedulerService()
        segments = service._convert_trip_to_segments(trip, today)

        # 08:00 to 10:00 = 2 hours
        assert segments[0].duration_hours == 2.0

    def test_segment_ascent_descent(self) -> None:
        """Segment should calculate ascent/descent from elevation."""
        from services.trip_report_scheduler import TripReportSchedulerService

        today = date.today()
        # Waypoints: 1000m -> 1500m (ascent 500m)
        trip = _create_test_trip(today, num_waypoints=2, elevations=[1000, 1500])

        service = TripReportSchedulerService()
        segments = service._convert_trip_to_segments(trip, today)

        assert segments[0].ascent_m == 500.0
        assert segments[0].descent_m == 0.0


class TestActiveTripFilter:
    """Test filtering of active trips."""

    def test_morning_returns_today_trips(self) -> None:
        """Morning report should return trips with today's stage."""
        from services.trip_report_scheduler import TripReportSchedulerService

        service = TripReportSchedulerService()
        target_date = service._get_target_date("morning")

        assert target_date == date.today()

    def test_evening_returns_tomorrow_trips(self) -> None:
        """Evening report should return trips with tomorrow's stage."""
        from services.trip_report_scheduler import TripReportSchedulerService

        service = TripReportSchedulerService()
        target_date = service._get_target_date("evening")

        assert target_date == date.today() + timedelta(days=1)


class TestSchedulerIntegration:
    """Test scheduler integration."""

    def test_scheduler_has_trip_report_jobs(self) -> None:
        """Scheduler should have trip report jobs registered."""
        from web.scheduler import (
            init_scheduler,
            get_scheduler_status,
            shutdown_scheduler,
        )

        # Initialize scheduler
        init_scheduler()

        try:
            status = get_scheduler_status()
            job_ids = [job["id"] for job in status["jobs"]]

            assert "morning_trip_reports" in job_ids
            assert "evening_trip_reports" in job_ids
        finally:
            shutdown_scheduler()

    def test_scheduler_job_names(self) -> None:
        """Scheduler jobs should have descriptive names."""
        from web.scheduler import (
            init_scheduler,
            get_scheduler_status,
            shutdown_scheduler,
        )

        init_scheduler()

        try:
            status = get_scheduler_status()
            jobs_by_id = {job["id"]: job for job in status["jobs"]}

            assert "Morning Trip Reports" in jobs_by_id["morning_trip_reports"]["name"]
            assert "Evening Trip Reports" in jobs_by_id["evening_trip_reports"]["name"]
        finally:
            shutdown_scheduler()


# --- Test Helpers ---

def _create_test_trip(
    stage_date: date,
    num_waypoints: int = 3,
    elevations: list[int] | None = None,
) -> Trip:
    """
    Create a test trip with the specified number of waypoints.

    Args:
        stage_date: Date for the stage
        num_waypoints: Number of waypoints (default 3)
        elevations: Optional list of elevations (default: 1000, 1200, 1400, ...)

    Returns:
        Trip object for testing
    """
    if elevations is None:
        elevations = [1000 + i * 200 for i in range(num_waypoints)]

    # Create waypoints with 2-hour gaps
    waypoints = []
    for i in range(num_waypoints):
        start_hour = 8 + i * 2
        end_hour = start_hour + 2

        wp = Waypoint(
            id=f"G{i+1}",
            name=f"Waypoint {i+1}",
            lat=47.0 + i * 0.1,
            lon=11.0 + i * 0.1,
            elevation_m=elevations[i],
            time_window=TimeWindow(
                start=time(start_hour, 0),
                end=time(end_hour, 0),
            ),
        )
        waypoints.append(wp)

    stage = Stage(
        id="T1",
        name="Test Stage",
        date=stage_date,
        waypoints=waypoints,
    )

    return Trip(
        id="test-trip",
        name="Test Trip",
        stages=[stage],
    )
