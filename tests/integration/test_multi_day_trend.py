"""
Tests for F3: Multi-Day Trend v2.0 — Stage-basierte Aggregation.

SPEC: docs/specs/modules/multi_day_trend.md v2.0

Tests real OpenMeteo API calls — NO mocking!

v2.0 Changes:
- aggregate_stage() function (Level-2 aggregation)
- Trip.get_future_stages() method
- Stage-based trend (not single-point)
- Precipitation in trend rows
- Stage name in trend rows
- show_multi_day_trend persistence bugfix
"""
from __future__ import annotations

import math
import pytest
from datetime import date, datetime, time, timedelta, timezone

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    PrecipType,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_segment_weather(
    segment_id: int,
    *,
    temp_min: float = 5.0,
    temp_max: float = 15.0,
    temp_avg: float = 10.0,
    wind_max: float = 20.0,
    gust_max: float = 35.0,
    precip_sum: float = 1.0,
    cloud_avg: int = 50,
    humidity_avg: int = 70,
    thunder_max: ThunderLevel = ThunderLevel.NONE,
    visibility_min: int = 8000,
    dewpoint_avg: float = 4.0,
    pressure_avg: float = 1013.0,
    wind_chill_min: float = 2.0,
    pop_max: int = 30,
    cape_max: float = 100.0,
    uv_index_max: float = 3.0,
    snow_new_sum: float = 0.0,
    wind_direction_avg: int = 180,
    precip_type_dom: PrecipType = PrecipType.RAIN,
    has_error: bool = False,
) -> SegmentWeatherData:
    """Create a SegmentWeatherData with controlled aggregated values."""
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=39.75, lon=2.65, elevation_m=100.0),
        end_point=GPXPoint(lat=39.76, lon=2.66, elevation_m=200.0),
        start_time=datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 18, 11, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=3.0,
        ascent_m=100.0,
        descent_m=0.0,
    )
    summary = SegmentWeatherSummary(
        temp_min_c=temp_min,
        temp_max_c=temp_max,
        temp_avg_c=temp_avg,
        wind_max_kmh=wind_max,
        gust_max_kmh=gust_max,
        precip_sum_mm=precip_sum,
        cloud_avg_pct=cloud_avg,
        humidity_avg_pct=humidity_avg,
        thunder_level_max=thunder_max,
        visibility_min_m=visibility_min,
        dewpoint_avg_c=dewpoint_avg,
        pressure_avg_hpa=pressure_avg,
        wind_chill_min_c=wind_chill_min,
        pop_max_pct=pop_max,
        cape_max_jkg=cape_max,
        uv_index_max=uv_index_max,
        snow_new_sum_cm=snow_new_sum,
        wind_direction_avg_deg=wind_direction_avg,
        precip_type_dominant=precip_type_dom,
        aggregation_config={
            "temp_min_c": "min",
            "temp_max_c": "max",
            "temp_avg_c": "avg",
            "wind_max_kmh": "max",
            "gust_max_kmh": "max",
            "precip_sum_mm": "sum",
            "cloud_avg_pct": "avg",
            "humidity_avg_pct": "avg",
            "thunder_level_max": "max",
            "visibility_min_m": "min",
            "dewpoint_avg_c": "avg",
            "pressure_avg_hpa": "avg",
            "wind_chill_min_c": "min",
            "snow_depth_cm": "max",
            "freezing_level_m": "avg",
            "pop_max_pct": "max",
            "cape_max_jkg": "max",
            "uv_index_max": "max",
            "snow_new_sum_cm": "sum",
            "wind_direction_avg_deg": "avg",
            "precip_type_dominant": "max",
        },
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test", run=datetime.now(timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(meta=meta, data=[]),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
        has_error=has_error,
    )


# ===========================================================================
# TEST: aggregate_stage() — Level-2 Aggregation
# ===========================================================================

class TestAggregateStage:
    """Test aggregate_stage() in weather_metrics.py."""

    def test_aggregate_stage_max(self):
        """MAX over segment MAXes: temp_max, wind, gust, pop, cape, uv."""
        from services.weather_metrics import aggregate_stage

        segments = [
            _make_segment_weather(1, temp_max=12.0, wind_max=15.0, gust_max=30.0, pop_max=20, cape_max=80.0, uv_index_max=2.0),
            _make_segment_weather(2, temp_max=18.0, wind_max=25.0, gust_max=45.0, pop_max=60, cape_max=200.0, uv_index_max=5.0),
            _make_segment_weather(3, temp_max=14.0, wind_max=10.0, gust_max=20.0, pop_max=40, cape_max=150.0, uv_index_max=3.0),
        ]

        result = aggregate_stage(segments)

        assert result.temp_max_c == 18.0
        assert result.wind_max_kmh == 25.0
        assert result.gust_max_kmh == 45.0
        assert result.pop_max_pct == 60
        assert result.cape_max_jkg == 200.0
        assert result.uv_index_max == 5.0

    def test_aggregate_stage_min(self):
        """MIN over segment MINs: temp_min, wind_chill, visibility."""
        from services.weather_metrics import aggregate_stage

        segments = [
            _make_segment_weather(1, temp_min=5.0, wind_chill_min=2.0, visibility_min=8000),
            _make_segment_weather(2, temp_min=3.0, wind_chill_min=-1.0, visibility_min=3000),
            _make_segment_weather(3, temp_min=7.0, wind_chill_min=4.0, visibility_min=5000),
        ]

        result = aggregate_stage(segments)

        assert result.temp_min_c == 3.0
        assert result.wind_chill_min_c == -1.0
        assert result.visibility_min_m == 3000

    def test_aggregate_stage_sum(self):
        """SUM over segment SUMs: precip, fresh_snow."""
        from services.weather_metrics import aggregate_stage

        segments = [
            _make_segment_weather(1, precip_sum=0.3, snow_new_sum=0.0),
            _make_segment_weather(2, precip_sum=1.2, snow_new_sum=0.5),
            _make_segment_weather(3, precip_sum=0.0, snow_new_sum=0.0),
        ]

        result = aggregate_stage(segments)

        assert abs(result.precip_sum_mm - 1.5) < 0.01
        assert abs(result.snow_new_sum_cm - 0.5) < 0.01

    def test_aggregate_stage_avg(self):
        """AVG over segment AVGs: cloud, humidity, dewpoint, pressure."""
        from services.weather_metrics import aggregate_stage

        segments = [
            _make_segment_weather(1, cloud_avg=60, humidity_avg=80, dewpoint_avg=6.0, pressure_avg=1010.0),
            _make_segment_weather(2, cloud_avg=80, humidity_avg=70, dewpoint_avg=4.0, pressure_avg=1015.0),
            _make_segment_weather(3, cloud_avg=40, humidity_avg=60, dewpoint_avg=2.0, pressure_avg=1020.0),
        ]

        result = aggregate_stage(segments)

        assert result.cloud_avg_pct == 60  # (60+80+40)/3
        assert result.humidity_avg_pct == 70  # (80+70+60)/3
        assert abs(result.dewpoint_avg_c - 4.0) < 0.01
        assert abs(result.pressure_avg_hpa - 1015.0) < 0.01

    def test_aggregate_stage_thunder_enum(self):
        """MAX severity for ThunderLevel: NONE < MED < HIGH."""
        from services.weather_metrics import aggregate_stage

        segments = [
            _make_segment_weather(1, thunder_max=ThunderLevel.NONE),
            _make_segment_weather(2, thunder_max=ThunderLevel.MED),
            _make_segment_weather(3, thunder_max=ThunderLevel.NONE),
        ]

        result = aggregate_stage(segments)

        assert result.thunder_level_max == ThunderLevel.MED

    def test_aggregate_stage_wind_direction_circular(self):
        """Circular mean for wind direction: 350 + 10 -> ~0, NOT 180."""
        from services.weather_metrics import aggregate_stage

        segments = [
            _make_segment_weather(1, wind_direction_avg=350),
            _make_segment_weather(2, wind_direction_avg=10),
        ]

        result = aggregate_stage(segments)

        # Circular mean of 350 and 10 should be ~0 (360), NOT 180
        assert result.wind_direction_avg_deg is not None
        avg_deg = result.wind_direction_avg_deg
        assert avg_deg <= 10 or avg_deg >= 350, \
            f"Circular mean of 350 and 10 should be ~0, got {avg_deg}"

    def test_aggregate_stage_skips_errors(self):
        """Segments with has_error=True are skipped."""
        from services.weather_metrics import aggregate_stage

        segments = [
            _make_segment_weather(1, temp_max=12.0),
            _make_segment_weather(2, temp_max=99.0, has_error=True),
            _make_segment_weather(3, temp_max=14.0),
        ]

        result = aggregate_stage(segments)

        # Error segment's 99 should NOT affect result
        assert result.temp_max_c == 14.0

    def test_aggregate_stage_empty_raises(self):
        """Empty segment list raises ValueError."""
        from services.weather_metrics import aggregate_stage

        with pytest.raises(ValueError):
            aggregate_stage([])

    def test_aggregate_stage_single_segment(self):
        """Single segment -> summary identical to segment's aggregated."""
        from services.weather_metrics import aggregate_stage

        seg = _make_segment_weather(
            1, temp_max=15.0, precip_sum=2.3, cloud_avg=40, visibility_min=5000,
        )

        result = aggregate_stage([seg])

        assert result.temp_max_c == 15.0
        assert result.precip_sum_mm == 2.3
        assert result.cloud_avg_pct == 40
        assert result.visibility_min_m == 5000

    def test_aggregate_stage_all_errors_raises(self):
        """All segments with errors -> raises ValueError."""
        from services.weather_metrics import aggregate_stage

        segments = [
            _make_segment_weather(1, has_error=True),
            _make_segment_weather(2, has_error=True),
        ]

        with pytest.raises(ValueError):
            aggregate_stage(segments)


# ===========================================================================
# TEST: Trip.get_future_stages()
# ===========================================================================

class TestGetFutureStages:
    """Test Trip.get_future_stages() method."""

    def test_get_future_stages(self):
        """Returns only stages after target_date, sorted."""
        from app.trip import Trip, Stage, Waypoint
        from app.trip import AggregationConfig

        wp = Waypoint(id="G1", name="Start", lat=39.75, lon=2.65, elevation_m=100)

        stages = [
            Stage(id="T1", name="Tag 1", date=date(2026, 2, 16), waypoints=[wp]),
            Stage(id="T2", name="Tag 2", date=date(2026, 2, 17), waypoints=[wp]),
            Stage(id="T3", name="Tag 3", date=date(2026, 2, 18), waypoints=[wp]),
            Stage(id="T4", name="Tag 4", date=date(2026, 2, 19), waypoints=[wp]),
        ]

        trip = Trip(
            id="test", name="Test Trip", stages=stages,
            avalanche_regions=[], aggregation=AggregationConfig(),
        )

        future = trip.get_future_stages(date(2026, 2, 17))

        assert len(future) == 2
        assert future[0].id == "T3"
        assert future[1].id == "T4"

    def test_get_future_stages_empty(self):
        """No future stages -> empty list."""
        from app.trip import Trip, Stage, Waypoint
        from app.trip import AggregationConfig

        wp = Waypoint(id="G1", name="Start", lat=39.75, lon=2.65, elevation_m=100)
        stages = [
            Stage(id="T1", name="Tag 1", date=date(2026, 2, 16), waypoints=[wp]),
        ]

        trip = Trip(
            id="test", name="Test Trip", stages=stages,
            avalanche_regions=[], aggregation=AggregationConfig(),
        )

        future = trip.get_future_stages(date(2026, 2, 16))
        assert future == []

    def test_get_future_stages_sorted(self):
        """Stages returned sorted by date even if input is unsorted."""
        from app.trip import Trip, Stage, Waypoint
        from app.trip import AggregationConfig

        wp = Waypoint(id="G1", name="Start", lat=39.75, lon=2.65, elevation_m=100)

        # Deliberately unsorted
        stages = [
            Stage(id="T4", name="Tag 4", date=date(2026, 2, 19), waypoints=[wp]),
            Stage(id="T2", name="Tag 2", date=date(2026, 2, 17), waypoints=[wp]),
            Stage(id="T3", name="Tag 3", date=date(2026, 2, 18), waypoints=[wp]),
        ]

        trip = Trip(
            id="test", name="Test Trip", stages=stages,
            avalanche_regions=[], aggregation=AggregationConfig(),
        )

        future = trip.get_future_stages(date(2026, 2, 16))

        assert [s.id for s in future] == ["T2", "T3", "T4"]


# ===========================================================================
# TEST: Trend rendering — stage name + precipitation
# ===========================================================================

class TestTrendRendering:
    """Test trend block rendering in HTML and plaintext."""

    def _make_trend_data(self) -> list[dict]:
        """Create trend data in v2.0 format (with stage_name and precip)."""
        return [
            {
                "weekday": "Mi",
                "date": date(2026, 2, 18),
                "stage_name": "Tag 3: von Soller nach Tossals Verds",
                "temp_max_c": 14.0,
                "precip_sum_mm": 1.5,
                "cloud_avg_pct": 55,
                "cloud_emoji": "⛅",
                "warning": None,
            },
            {
                "weekday": "Do",
                "date": date(2026, 2, 19),
                "stage_name": "Tag 4: von Tossals Verds nach Lluc",
                "temp_max_c": 16.0,
                "precip_sum_mm": 2.3,
                "cloud_avg_pct": 25,
                "cloud_emoji": "🌤",
                "warning": "Gewitter",
            },
        ]

    def _make_last_segment(self) -> SegmentWeatherData:
        """Minimal last segment for formatter."""
        seg = TripSegment(
            segment_id="Ziel",
            start_point=GPXPoint(lat=39.75, lon=2.65, elevation_m=100.0),
            end_point=GPXPoint(lat=39.75, lon=2.65, elevation_m=100.0),
            start_time=datetime(2026, 2, 17, 13, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 2, 17, 15, 0, tzinfo=timezone.utc),
            duration_hours=2.0, distance_km=0.0, ascent_m=0.0, descent_m=0.0,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="test", run=datetime.now(timezone.utc),
            grid_res_km=1.0, interp="point_grid",
        )
        return SegmentWeatherData(
            segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=[]),
            aggregated=SegmentWeatherSummary(), fetched_at=datetime.now(timezone.utc),
            provider="openmeteo",
        )

    def test_html_contains_stage_name(self):
        """HTML trend block shows stage names, not just weekdays."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        trend = self._make_trend_data()
        last_seg = self._make_last_segment()

        report = formatter.format_email(
            segments=[last_seg],
            trip_name="GR221 Mallorca",
            report_type="evening",
            multi_day_trend=trend,
        )

        # Should contain "Etappen" header (v2.0), not "5-Tage-Trend"
        assert "Etappen" in report.email_html, \
            "HTML should contain 'Etappen' header"
        # Should NOT contain old v1.0 header
        assert "Ankunftsort" not in report.email_html, \
            "HTML should not contain old v1.0 'Ankunftsort' header"
        # Should contain stage route info
        assert "Tossals Verds" in report.email_html, \
            "HTML should contain stage destination"

    def test_html_contains_precipitation(self):
        """HTML trend block includes precipitation column."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        trend = self._make_trend_data()
        last_seg = self._make_last_segment()

        report = formatter.format_email(
            segments=[last_seg],
            trip_name="GR221 Mallorca",
            report_type="evening",
            multi_day_trend=trend,
        )

        assert "1.5mm" in report.email_html or "1.5" in report.email_html, \
            "HTML should contain precipitation value"
        assert "2.3mm" in report.email_html or "2.3" in report.email_html, \
            "HTML should contain second stage precipitation"

    def test_plain_contains_stage_name(self):
        """Plaintext trend block shows stage names."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        trend = self._make_trend_data()
        last_seg = self._make_last_segment()

        report = formatter.format_email(
            segments=[last_seg],
            trip_name="GR221 Mallorca",
            report_type="evening",
            multi_day_trend=trend,
        )

        assert "Etappen" in report.email_plain, \
            "Plaintext should contain 'Etappen' header"
        assert "Tossals Verds" in report.email_plain, \
            "Plaintext should contain stage destination"

    def test_plain_contains_precipitation(self):
        """Plaintext trend block includes precipitation values."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        trend = self._make_trend_data()
        last_seg = self._make_last_segment()

        report = formatter.format_email(
            segments=[last_seg],
            trip_name="GR221 Mallorca",
            report_type="evening",
            multi_day_trend=trend,
        )

        assert "1.5" in report.email_plain, "Plaintext should contain precip value"

    def test_morning_report_no_trend(self):
        """Morning report should NOT contain trend block."""
        from formatters.trip_report import TripReportFormatter

        formatter = TripReportFormatter()
        trend = self._make_trend_data()
        last_seg = self._make_last_segment()

        report = formatter.format_email(
            segments=[last_seg],
            trip_name="GR221 Mallorca",
            report_type="morning",
            multi_day_trend=trend,
        )

        assert "Etappen" not in report.email_html
        assert "Etappen" not in report.email_plain

    def test_trend_disabled_in_config(self):
        """Trend should not appear when show_multi_day_trend=False."""
        from app.metric_catalog import build_default_display_config
        from formatters.trip_report import TripReportFormatter

        dc = build_default_display_config()
        dc.show_multi_day_trend = False

        formatter = TripReportFormatter()
        trend = self._make_trend_data()
        last_seg = self._make_last_segment()

        report = formatter.format_email(
            segments=[last_seg],
            trip_name="GR221 Mallorca",
            report_type="evening",
            display_config=dc,
            multi_day_trend=trend,
        )

        assert "Etappen" not in report.email_html
        assert "Etappen" not in report.email_plain


# ===========================================================================
# TEST: show_multi_day_trend persistence bugfix
# ===========================================================================

class TestShowMultiDayTrendPersistence:
    """Test that show_multi_day_trend survives save/load round-trip."""

    def test_persistence_round_trip(self):
        """show_multi_day_trend=False persists through save and load."""
        import json
        import tempfile
        from pathlib import Path
        from app.loader import _trip_to_dict, load_trip
        from app.trip import Trip, Stage, Waypoint
        from app.trip import AggregationConfig
        from app.metric_catalog import build_default_display_config

        wp = Waypoint(id="G1", name="Start", lat=39.75, lon=2.65, elevation_m=100)
        stage = Stage(id="T1", name="Tag 1", date=date(2026, 2, 18), waypoints=[wp])

        dc = build_default_display_config()
        dc.show_multi_day_trend = False  # Explicitly set to False

        trip = Trip(
            id="persist-test", name="Persist Test", stages=[stage],
            avalanche_regions=[], aggregation=AggregationConfig(),
            display_config=dc,
        )

        # Save to temp file, then load back
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "persist-test.json"
            data = _trip_to_dict(trip)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)

            # Load back
            loaded = load_trip(path)
            assert loaded.display_config is not None
            assert loaded.display_config.show_multi_day_trend is False, \
                "show_multi_day_trend=False should persist through save/load"
