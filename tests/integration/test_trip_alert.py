"""
Integration tests for TripAlertService.

Feature 3.4: Alert bei Änderungen
Tests weather change detection and alert email sending.

SPEC: docs/specs/modules/trip_alert.md v1.0
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pytest

from app.models import (
    ChangeSeverity,
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
    WeatherChange,
)
from app.trip import Stage, TimeWindow, Trip, Waypoint


class TestFilterSignificantChanges:
    """Test filtering of significant changes."""

    def test_filter_keeps_moderate_and_major(self) -> None:
        """MODERATE and MAJOR severity should be kept."""
        from services.trip_alert import TripAlertService

        service = TripAlertService()

        changes = [
            _create_change("temp_max_c", ChangeSeverity.MINOR),
            _create_change("wind_max_kmh", ChangeSeverity.MODERATE),
            _create_change("precip_sum_mm", ChangeSeverity.MAJOR),
        ]

        filtered = service._filter_significant_changes(changes)

        assert len(filtered) == 2
        assert all(c.severity in [ChangeSeverity.MODERATE, ChangeSeverity.MAJOR] for c in filtered)

    def test_filter_removes_minor(self) -> None:
        """MINOR severity should be filtered out."""
        from services.trip_alert import TripAlertService

        service = TripAlertService()

        changes = [
            _create_change("temp_max_c", ChangeSeverity.MINOR),
            _create_change("wind_max_kmh", ChangeSeverity.MINOR),
        ]

        filtered = service._filter_significant_changes(changes)

        assert len(filtered) == 0

    def test_filter_empty_list(self) -> None:
        """Empty list should return empty."""
        from services.trip_alert import TripAlertService

        service = TripAlertService()
        filtered = service._filter_significant_changes([])

        assert filtered == []


class TestThrottling:
    """Test alert throttling."""

    def test_first_alert_not_throttled(self) -> None:
        """First alert should not be throttled."""
        from services.trip_alert import TripAlertService

        service = TripAlertService(throttle_hours=2)

        assert service._is_throttled("trip-1") is False

    def test_second_alert_within_window_is_throttled(self) -> None:
        """Alert within throttle window should be blocked."""
        from services.trip_alert import TripAlertService

        service = TripAlertService(throttle_hours=2)

        # Simulate first alert
        service._last_alert_times["trip-1"] = datetime.now(timezone.utc)

        assert service._is_throttled("trip-1") is True

    def test_alert_after_window_not_throttled(self) -> None:
        """Alert after throttle window should be allowed."""
        from services.trip_alert import TripAlertService

        service = TripAlertService(throttle_hours=2)

        # Simulate alert 3 hours ago
        service._last_alert_times["trip-1"] = datetime.now(timezone.utc) - timedelta(hours=3)

        assert service._is_throttled("trip-1") is False

    def test_clear_throttle(self) -> None:
        """Clear throttle should allow immediate alert."""
        from services.trip_alert import TripAlertService

        service = TripAlertService(throttle_hours=2)

        # Simulate recent alert
        service._last_alert_times["trip-1"] = datetime.now(timezone.utc)
        assert service._is_throttled("trip-1") is True

        # Clear throttle
        service.clear_throttle("trip-1")
        assert service._is_throttled("trip-1") is False

    def test_get_time_until_next_alert(self) -> None:
        """Should return remaining throttle time."""
        from services.trip_alert import TripAlertService

        service = TripAlertService(throttle_hours=2)

        # Simulate alert 1 hour ago
        service._last_alert_times["trip-1"] = datetime.now(timezone.utc) - timedelta(hours=1)

        remaining = service.get_time_until_next_alert("trip-1")
        assert remaining is not None
        assert 50 * 60 < remaining.total_seconds() < 70 * 60  # ~1 hour remaining

    def test_get_time_until_next_alert_not_throttled(self) -> None:
        """Should return None if not throttled."""
        from services.trip_alert import TripAlertService

        service = TripAlertService(throttle_hours=2)

        remaining = service.get_time_until_next_alert("trip-1")
        assert remaining is None


class TestDetectAllChanges:
    """Test change detection across segments."""

    def test_detect_changes_matching_segments(self) -> None:
        """Should detect changes between matching segments."""
        from services.trip_alert import TripAlertService

        service = TripAlertService()

        # Create cached and fresh with different temps
        cached = [_create_segment_weather(segment_id=1, temp_max=15.0)]
        fresh = [_create_segment_weather(segment_id=1, temp_max=25.0)]  # +10°C

        changes = service._detect_all_changes(cached, fresh)

        # Should detect temp change (threshold 5°C, delta 10°C)
        temp_changes = [c for c in changes if "temp" in c.metric]
        assert len(temp_changes) > 0

    def test_no_changes_when_similar(self) -> None:
        """Should return empty when no significant changes."""
        from services.trip_alert import TripAlertService

        service = TripAlertService()

        # Create cached and fresh with similar temps
        cached = [_create_segment_weather(segment_id=1, temp_max=15.0)]
        fresh = [_create_segment_weather(segment_id=1, temp_max=16.0)]  # +1°C

        changes = service._detect_all_changes(cached, fresh)

        # Small change should not exceed threshold
        temp_changes = [c for c in changes if "temp" in c.metric]
        assert len(temp_changes) == 0


# --- Test Helpers ---

def _create_change(metric: str, severity: ChangeSeverity) -> WeatherChange:
    """Create a test WeatherChange."""
    return WeatherChange(
        metric=metric,
        old_value=10.0,
        new_value=20.0,
        delta=10.0,
        threshold=5.0,
        severity=severity,
        direction="increase",
    )


def _create_segment_weather(
    segment_id: int = 1,
    temp_max: float = 20.0,
    wind_max: float = 15.0,
) -> SegmentWeatherData:
    """Create test SegmentWeatherData."""
    now = datetime.now(timezone.utc)

    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1200.0),
        start_time=now,
        end_time=now + timedelta(hours=2),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=200.0,
        descent_m=0.0,
    )

    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=now,
        grid_res_km=1.0,
        interp="point_grid",
    )

    timeseries = NormalizedTimeseries(
        meta=meta,
        data=[
            ForecastDataPoint(
                ts=now,
                t2m_c=temp_max,
                wind10m_kmh=wind_max,
            )
        ],
    )

    summary = SegmentWeatherSummary(
        temp_min_c=temp_max - 5,
        temp_max_c=temp_max,
        temp_avg_c=temp_max - 2.5,
        wind_max_kmh=wind_max,
        precip_sum_mm=0.0,
    )

    return SegmentWeatherData(
        segment=segment,
        timeseries=timeseries,
        aggregated=summary,
        fetched_at=now,
        provider="openmeteo",
    )
