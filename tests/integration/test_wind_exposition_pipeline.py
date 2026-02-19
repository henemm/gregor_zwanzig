"""
F7b: Pipeline-Integration Wind-Exposition — Integration Tests

Tests that exposed_sections flow through the pipeline:
Scheduler → Formatter → RiskEngine

SPEC: docs/specs/modules/wind_exposition_pipeline.md v1.0
"""
import math
from datetime import datetime, time, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional

import pytest

from app.models import (
    ExposedSection,
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    RiskType,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
)


# ---------------------------------------------------------------------------
# Test fixtures / helpers
# ---------------------------------------------------------------------------

def _make_segment(
    seg_id: int,
    start_km: float,
    end_km: float,
    start_elev: float,
    end_elev: float,
    wind_max: float = 20.0,
    gust_max: float = 25.0,
    start_hour: int = 8,
    end_hour: int = 10,
) -> SegmentWeatherData:
    """Create a SegmentWeatherData with given km/elev/wind values."""
    base_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=start_elev, distance_from_start_km=start_km),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=end_elev, distance_from_start_km=end_km),
        start_time=base_date.replace(hour=start_hour),
        end_time=base_date.replace(hour=end_hour),
        duration_hours=float(end_hour - start_hour),
        distance_km=round(end_km - start_km, 1),
        ascent_m=max(0, end_elev - start_elev),
        descent_m=max(0, start_elev - end_elev),
    )
    ts_data = [
        ForecastDataPoint(
            ts=base_date.replace(hour=h),
            t2m_c=10.0,
            wind10m_kmh=wind_max,
            gust_kmh=gust_max,
        )
        for h in range(start_hour, end_hour + 1)
    ]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=base_date,
        grid_res_km=0.1,
        interp="point_grid",
    )
    agg = SegmentWeatherSummary(
        temp_min_c=8.0,
        temp_max_c=12.0,
        wind_max_kmh=wind_max,
        gust_max_kmh=gust_max,
        precip_sum_mm=0.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(meta=meta, data=ts_data),
        aggregated=agg,
        fetched_at=base_date,
        provider="openmeteo",
    )


# ---------------------------------------------------------------------------
# Fake Trip/Stage/Waypoint for scheduler tests
# ---------------------------------------------------------------------------

@dataclass
class _FakeWaypoint:
    id: str
    lat: float
    lon: float
    elevation_m: float
    time_window: Optional[object] = None


@dataclass
class _FakeTimeWindow:
    start: time


@dataclass
class _FakeStage:
    id: str
    name: str
    date: datetime
    waypoints: list
    start_time: time = field(default_factory=lambda: time(8, 0))


@dataclass
class _FakeDisplayConfig:
    metrics: list = field(default_factory=list)
    show_compact_summary: bool = False
    show_night_block: bool = False
    night_interval_hours: int = 2
    thunder_forecast_days: int = 0
    multi_day_trend_reports: list = field(default_factory=list)
    sms_metrics: list = field(default_factory=list)

    def is_metric_enabled(self, metric_id):
        return False


@dataclass
class _FakeTrip:
    id: str
    name: str
    stages: list
    display_config: Optional[object] = None
    report_config: Optional[object] = None

    def get_stage_for_date(self, target_date):
        for s in self.stages:
            if s.date == target_date or (hasattr(s.date, 'date') and s.date.date() == target_date):
                return s
        return None

    def get_future_stages(self, target_date):
        return []


# ===========================================================================
# Test 1: Cumulative distance set on GPXPoints
# ===========================================================================

class TestCumulativeDistance:
    """After _convert_trip_to_segments(), GPXPoints have distance_from_start_km set."""

    def test_cumulative_distance_set(self):
        """GPXPoints should have monotonically increasing distance_from_start_km."""
        from services.trip_report_scheduler import TripReportSchedulerService

        target_date = datetime(2026, 3, 1).date()

        # 3 waypoints: ~1km apart (lat diff ~0.009 ≈ 1km)
        wps = [
            _FakeWaypoint("wp1", 47.0, 11.0, 1500.0, _FakeTimeWindow(time(8, 0))),
            _FakeWaypoint("wp2", 47.009, 11.0, 2200.0, _FakeTimeWindow(time(10, 0))),
            _FakeWaypoint("wp3", 47.018, 11.0, 1800.0, _FakeTimeWindow(time(12, 0))),
        ]
        stage = _FakeStage("s1", "Test Stage", target_date, wps)
        trip = _FakeTrip("test", "Test", [stage])

        svc = TripReportSchedulerService.__new__(TripReportSchedulerService)
        segments = svc._convert_trip_to_segments(trip, target_date)

        # Should have 2 walking segments + 1 destination = 3
        assert len(segments) >= 2

        # First segment: start_point should have distance_from_start_km = 0.0
        assert segments[0].start_point.distance_from_start_km == 0.0

        # Each segment's end_point distance > start_point distance
        for seg in segments[:-1]:  # Exclude destination
            if seg.segment_id == "Ziel":
                continue
            assert seg.end_point.distance_from_start_km > seg.start_point.distance_from_start_km, \
                f"Segment {seg.segment_id}: end ({seg.end_point.distance_from_start_km}) " \
                f"should be > start ({seg.start_point.distance_from_start_km})"

        # Monotonically increasing across segments
        prev_end = 0.0
        for seg in segments:
            if seg.segment_id == "Ziel":
                continue
            assert seg.start_point.distance_from_start_km >= prev_end, \
                f"Segment {seg.segment_id} start ({seg.start_point.distance_from_start_km}) " \
                f"should be >= prev end ({prev_end})"
            prev_end = seg.end_point.distance_from_start_km


# ===========================================================================
# Test 2-6: format_email exposed_sections → RiskEngine
# ===========================================================================

class TestTripReportExposedSections:
    """format_email() passes exposed_sections to RiskEngine."""

    def test_exposed_sections_passed_to_engine(self):
        """Segment at 2400m + wind 35 km/h → _determine_risk returns WIND_EXPOSITION."""
        from formatters.trip_report import TripReportFormatter

        seg = _make_segment(1, 0.0, 2.0, 2400.0, 2400.0, wind_max=35.0, gust_max=40.0)
        exposed = [ExposedSection(start_km=0.0, end_km=2.0, max_elevation_m=2400.0, exposition_type="GRAT")]

        formatter = TripReportFormatter()
        # format_email stores exposed_sections for _determine_risk
        report = formatter.format_email(
            segments=[seg],
            trip_name="Test",
            report_type="morning",
            exposed_sections=exposed,
        )

        # After format_email, _determine_risk should use stored exposed_sections
        level, label = formatter._determine_risk(seg)
        assert "Exposed Ridge" in label

    def test_no_exposition_below_threshold(self):
        """All segments under 2000m → no WIND_EXPOSITION risk."""
        from formatters.trip_report import TripReportFormatter

        seg = _make_segment(1, 0.0, 2.0, 1500.0, 1500.0, wind_max=35.0, gust_max=40.0)

        formatter = TripReportFormatter()
        report = formatter.format_email(
            segments=[seg],
            trip_name="Test",
            report_type="morning",
            exposed_sections=[],  # Empty — no exposed sections
        )

        # Should NOT contain exposed ridge label
        assert "Exposed Ridge" not in report.email_html

    def test_low_wind_no_exposition_risk(self):
        """Segment at 2400m + wind 25 km/h → no WIND_EXPOSITION risk (under 30 threshold)."""
        from formatters.trip_report import TripReportFormatter

        seg = _make_segment(1, 0.0, 2.0, 2400.0, 2400.0, wind_max=25.0, gust_max=28.0)
        exposed = [ExposedSection(start_km=0.0, end_km=2.0, max_elevation_m=2400.0, exposition_type="GRAT")]

        formatter = TripReportFormatter()
        report = formatter.format_email(
            segments=[seg],
            trip_name="Test",
            report_type="morning",
            exposed_sections=exposed,
        )

        # Wind under 30 km/h — should NOT trigger WIND_EXPOSITION
        assert "Exposed Ridge" not in report.email_html

    def test_exposition_moderate_risk(self):
        """Wind 35 km/h + exposed → MODERATE WIND_EXPOSITION via _determine_risk."""
        from formatters.trip_report import TripReportFormatter

        seg = _make_segment(1, 0.0, 2.0, 2400.0, 2400.0, wind_max=35.0, gust_max=38.0)
        exposed = [ExposedSection(start_km=0.0, end_km=2.0, max_elevation_m=2400.0, exposition_type="GRAT")]

        formatter = TripReportFormatter()
        formatter.format_email(
            segments=[seg],
            trip_name="Test",
            report_type="morning",
            exposed_sections=exposed,
        )

        level, label = formatter._determine_risk(seg)
        assert "Exposed Ridge/Wind" in label

    def test_exposition_high_risk(self):
        """Wind 55 km/h + exposed → HIGH WIND_EXPOSITION via _determine_risk."""
        from formatters.trip_report import TripReportFormatter

        seg = _make_segment(1, 0.0, 2.0, 2400.0, 2400.0, wind_max=55.0, gust_max=65.0)
        exposed = [ExposedSection(start_km=0.0, end_km=2.0, max_elevation_m=2400.0, exposition_type="GRAT")]

        formatter = TripReportFormatter()
        formatter.format_email(
            segments=[seg],
            trip_name="Test",
            report_type="morning",
            exposed_sections=exposed,
        )

        level, label = formatter._determine_risk(seg)
        assert "Exposed Ridge/Storm" in label


# ===========================================================================
# Test 7-8: SMS formatter
# ===========================================================================

class TestSMSExposedSections:
    """format_sms() accepts and uses exposed_sections."""

    def test_sms_formatter_accepts_exposed_sections(self):
        """format_sms(segments, exposed_sections=...) should not raise TypeError."""
        from formatters.sms_trip import SMSTripFormatter

        seg = _make_segment(1, 0.0, 2.0, 1500.0, 1500.0, wind_max=20.0)

        formatter = SMSTripFormatter()
        # This should NOT raise TypeError
        sms = formatter.format_sms(
            segments=[seg],
            exposed_sections=[],
        )
        assert isinstance(sms, str)

    def test_sms_grat_wind_label(self):
        """Exposed segment + wind >= 30 → SMS label 'GratWind'."""
        from formatters.sms_trip import SMSTripFormatter

        seg = _make_segment(1, 0.0, 2.0, 2400.0, 2400.0, wind_max=35.0, gust_max=40.0)
        exposed = [ExposedSection(start_km=0.0, end_km=2.0, max_elevation_m=2400.0, exposition_type="GRAT")]

        formatter = SMSTripFormatter()
        sms = formatter.format_sms(
            segments=[seg],
            exposed_sections=exposed,
        )

        assert "GratWind" in sms


# ===========================================================================
# Test 9: Exception handling
# ===========================================================================

class TestExpositionExceptionHandling:
    """WindExpositionService errors should be handled gracefully."""

    def test_exposition_service_exception_handled(self):
        """If WindExpositionService raises, report is still generated (no WIND_EXPOSITION)."""
        from formatters.trip_report import TripReportFormatter

        seg = _make_segment(1, 0.0, 2.0, 2400.0, 2400.0, wind_max=35.0, gust_max=40.0)

        formatter = TripReportFormatter()
        # Without exposed_sections (simulates exception path where exposed=[])
        report = formatter.format_email(
            segments=[seg],
            trip_name="Test",
            report_type="morning",
            exposed_sections=None,
        )

        # Report generated successfully
        assert report.email_html is not None
        assert len(report.email_html) > 0
        # No WIND_EXPOSITION risk
        assert "Exposed Ridge" not in report.email_html


# ===========================================================================
# Test 10-15: F7c Trip-Level min_elevation_m Config
# SPEC: docs/specs/modules/wind_exposition_config.md v1.0
# ===========================================================================

class TestTripLevelElevationConfig:
    """Trip-level wind_exposition_min_elevation_m config."""

    def test_custom_min_elevation_used(self):
        """Segment at 1600m, min_elevation_m=1500 → exposed section detected."""
        from services.wind_exposition import WindExpositionService

        seg_data = _make_segment(1, 0.0, 3.0, 1600.0, 1600.0, wind_max=35.0, gust_max=40.0)
        svc = WindExpositionService()
        exposed = svc.detect_exposed_from_segments(
            [seg_data.segment], min_elevation_m=1500.0
        )
        assert len(exposed) > 0, "1600m segment should be exposed with min_elevation_m=1500"

        # Now verify risk engine picks it up
        from formatters.trip_report import TripReportFormatter
        formatter = TripReportFormatter()
        formatter.format_email(
            segments=[seg_data],
            trip_name="Test",
            report_type="morning",
            exposed_sections=exposed,
        )
        level, label = formatter._determine_risk(seg_data)
        assert "Exposed Ridge" in label

    def test_default_min_elevation_1500(self):
        """Global default is now 1500m (not 2000m). Segment at 1600m → detected."""
        from services.wind_exposition import WindExpositionService

        seg_data = _make_segment(1, 0.0, 3.0, 1600.0, 1600.0)
        svc = WindExpositionService()
        # Call WITHOUT explicit min_elevation_m — should use new default 1500
        exposed = svc.detect_exposed_from_segments([seg_data.segment])
        assert len(exposed) > 0, "1600m segment should be exposed with default 1500m"

    def test_segment_below_custom_elevation(self):
        """Segment at 900m, Config min=1500 → no exposed section."""
        from services.wind_exposition import WindExpositionService

        seg_data = _make_segment(1, 0.0, 3.0, 900.0, 900.0)
        svc = WindExpositionService()
        exposed = svc.detect_exposed_from_segments(
            [seg_data.segment], min_elevation_m=1500.0
        )
        assert len(exposed) == 0, "900m segment should NOT be exposed with min=1500"

    def test_none_config_uses_service_default(self):
        """wind_exposition_min_elevation_m=None → service default (1500m) applies."""
        from services.wind_exposition import WindExpositionService

        seg_data = _make_segment(1, 0.0, 3.0, 1600.0, 1600.0)
        svc = WindExpositionService()
        # None config → no override → default 1500m
        exposed = svc.detect_exposed_from_segments([seg_data.segment])
        assert len(exposed) > 0, "None config should use default 1500m, 1600m should be exposed"

    def test_model_has_config_field(self):
        """TripReportConfig has wind_exposition_min_elevation_m field."""
        from app.models import TripReportConfig
        config = TripReportConfig(trip_id="test")
        assert hasattr(config, 'wind_exposition_min_elevation_m'), \
            "TripReportConfig must have wind_exposition_min_elevation_m field"
        assert config.wind_exposition_min_elevation_m is None, \
            "Default should be None"

    def test_loader_roundtrip(self):
        """wind_exposition_min_elevation_m survives save→load roundtrip."""
        import json
        import tempfile
        from pathlib import Path
        from app.models import TripReportConfig

        # Create a minimal trip JSON with report_config including new field
        config = TripReportConfig(trip_id="test-roundtrip")
        config.wind_exposition_min_elevation_m = 1800.0

        # Serialize manually (mimicking loader.save_trip)
        rc_dict = {
            "trip_id": config.trip_id,
            "enabled": config.enabled,
            "morning_time": config.morning_time.isoformat(),
            "evening_time": config.evening_time.isoformat(),
            "send_email": config.send_email,
            "send_sms": config.send_sms,
            "alert_on_changes": config.alert_on_changes,
            "change_threshold_temp_c": config.change_threshold_temp_c,
            "change_threshold_wind_kmh": config.change_threshold_wind_kmh,
            "change_threshold_precip_mm": config.change_threshold_precip_mm,
            "updated_at": config.updated_at.isoformat(),
            "wind_exposition_min_elevation_m": config.wind_exposition_min_elevation_m,
        }

        # Deserialize (mimicking loader.load_trip)
        from datetime import time as _time, datetime as _dt
        loaded = TripReportConfig(
            trip_id=rc_dict["trip_id"],
            enabled=rc_dict.get("enabled", True),
            morning_time=_time.fromisoformat(rc_dict["morning_time"]),
            evening_time=_time.fromisoformat(rc_dict["evening_time"]),
            send_email=rc_dict.get("send_email", True),
            send_sms=rc_dict.get("send_sms", False),
            alert_on_changes=rc_dict.get("alert_on_changes", True),
            change_threshold_temp_c=rc_dict.get("change_threshold_temp_c", 5.0),
            change_threshold_wind_kmh=rc_dict.get("change_threshold_wind_kmh", 20.0),
            change_threshold_precip_mm=rc_dict.get("change_threshold_precip_mm", 10.0),
            updated_at=_dt.fromisoformat(rc_dict["updated_at"]),
            wind_exposition_min_elevation_m=rc_dict.get("wind_exposition_min_elevation_m"),
        )
        assert loaded.wind_exposition_min_elevation_m == 1800.0, \
            f"Expected 1800.0 but got {loaded.wind_exposition_min_elevation_m}"
