"""
Tests for F2: Kompakt-Summary — Natural-language weather summary per stage.

SPEC: docs/specs/modules/compact_summary.md v1.1

Tests use constructed SegmentWeatherData with real timeseries data — NO mocking!

Key feature: Temporal qualification (peak times, rain start/end, gust peaks).
"""
from __future__ import annotations

import pytest
from datetime import datetime, time, timedelta, timezone

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
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

def _make_dp(hour: int, **kwargs) -> ForecastDataPoint:
    """Create a ForecastDataPoint for a given hour with defaults."""
    defaults = dict(
        ts=datetime(2026, 2, 18, hour, 0, tzinfo=timezone.utc),
        t2m_c=12.0,
        wind10m_kmh=15.0,
        wind_direction_deg=270,
        gust_kmh=20.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        pop_pct=10,
        humidity_pct=65,
    )
    defaults.update(kwargs)
    return ForecastDataPoint(**defaults)


def _make_segment_weather_with_timeseries(
    segment_id: int,
    hourly: list[ForecastDataPoint],
    *,
    temp_min: float = 8.0,
    temp_max: float = 18.0,
    wind_max: float = 25.0,
    gust_max: float = 35.0,
    precip_sum: float = 4.0,
    cloud_avg: int = 65,
    pop_max: int = 60,
    thunder_max: ThunderLevel = ThunderLevel.NONE,
    wind_direction_avg: int = 315,
    visibility_min: int = 8000,
) -> SegmentWeatherData:
    """Create SegmentWeatherData with both timeseries and aggregated summary."""
    start_hour = hourly[0].ts.hour if hourly else 9
    end_hour = hourly[-1].ts.hour + 1 if hourly else 17

    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=39.75, lon=2.65, elevation_m=100.0),
        end_point=GPXPoint(lat=39.76, lon=2.66, elevation_m=200.0),
        start_time=datetime(2026, 2, 18, start_hour, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 18, end_hour, 0, tzinfo=timezone.utc),
        duration_hours=float(end_hour - start_hour),
        distance_km=5.0,
        ascent_m=200.0,
        descent_m=100.0,
    )
    summary = SegmentWeatherSummary(
        temp_min_c=temp_min, temp_max_c=temp_max, temp_avg_c=(temp_min + temp_max) / 2,
        wind_max_kmh=wind_max, gust_max_kmh=gust_max,
        precip_sum_mm=precip_sum, cloud_avg_pct=cloud_avg,
        humidity_avg_pct=65, thunder_level_max=thunder_max,
        visibility_min_m=visibility_min, dewpoint_avg_c=6.0,
        pressure_avg_hpa=1013.0, wind_chill_min_c=5.0,
        pop_max_pct=pop_max, cape_max_jkg=100.0,
        uv_index_max=3.0, snow_new_sum_cm=0.0,
        wind_direction_avg_deg=wind_direction_avg,
        precip_type_dominant=PrecipType.RAIN,
        aggregation_config={},
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime.now(timezone.utc), grid_res_km=1.0, interp="point_grid",
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(meta=meta, data=hourly),
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _default_dc() -> UnifiedWeatherDisplayConfig:
    """Display config with all relevant metrics enabled + friendly format."""
    return UnifiedWeatherDisplayConfig(
        trip_id="test",
        metrics=[
            MetricConfig(metric_id="temperature", enabled=True, aggregations=["min", "max"], use_friendly_format=True),
            MetricConfig(metric_id="cloud_total", enabled=True, aggregations=["avg"], use_friendly_format=True),
            MetricConfig(metric_id="precipitation", enabled=True, aggregations=["sum"], use_friendly_format=True),
            MetricConfig(metric_id="rain_probability", enabled=True, aggregations=["max"], use_friendly_format=True),
            MetricConfig(metric_id="wind", enabled=True, aggregations=["max"], use_friendly_format=True),
            MetricConfig(metric_id="gust", enabled=True, aggregations=["max"], use_friendly_format=True),
            MetricConfig(metric_id="wind_direction", enabled=True, aggregations=["avg"], use_friendly_format=True),
            MetricConfig(metric_id="thunder", enabled=True, aggregations=["max"], use_friendly_format=True),
        ],
    )


# ===========================================================================
# TEST: Basic summary line
# ===========================================================================

class TestBasicSummary:
    """Test basic format_stage_summary() output."""

    def test_basic_summary_contains_temp_range(self):
        """Summary should contain temperature range."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = [_make_dp(h, t2m_c=8 + h, precip_1h_mm=0.5) for h in range(9, 17)]
        segments = [_make_segment_weather_with_timeseries(1, hourly)]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        assert "8" in result and "18" in result
        assert "°C" in result

    def test_dry_conditions(self):
        """When no precipitation, summary should contain 'trocken'."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = [_make_dp(h, precip_1h_mm=0.0) for h in range(9, 17)]
        segments = [_make_segment_weather_with_timeseries(1, hourly, precip_sum=0.0, pop_max=5)]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        assert "trocken" in result.lower()
        assert "regen" not in result.lower()


# ===========================================================================
# TEST: Temporal qualification — rain patterns
# ===========================================================================

class TestRainTemporal:
    """Test temporal qualification for precipitation."""

    def test_rain_with_peak_time(self):
        """Rain throughout with clear peak should mention peak hour."""
        from formatters.compact_summary import CompactSummaryFormatter

        # Rain in ALL hours, but peak at 11:00 → "peak" pattern
        hourly = []
        for h in range(9, 17):
            precip = 3.0 if h == 11 else 0.5
            hourly.append(_make_dp(h, precip_1h_mm=precip))

        segments = [_make_segment_weather_with_timeseries(1, hourly, precip_sum=6.5, pop_max=80)]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        assert "11:00" in result or "11" in result

    def test_rain_starts_later(self):
        """Dry morning, rain starting later should indicate start time."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = []
        for h in range(9, 17):
            precip = 2.0 if h >= 13 else 0.0
            hourly.append(_make_dp(h, precip_1h_mm=precip))

        segments = [_make_segment_weather_with_timeseries(1, hourly, precip_sum=8.0, pop_max=70)]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        assert "13:00" in result or "13" in result

    def test_rain_ends_early(self):
        """Rain in morning, dry afternoon should indicate when it stops."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = []
        for h in range(9, 17):
            precip = 1.5 if h <= 11 else 0.0
            hourly.append(_make_dp(h, precip_1h_mm=precip))

        segments = [_make_segment_weather_with_timeseries(1, hourly, precip_sum=4.5, pop_max=60)]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        result_lower = result.lower()
        assert "trocken" in result_lower or "12" in result or "11" in result


# ===========================================================================
# TEST: Config-awareness
# ===========================================================================

class TestConfigAwareness:
    """Test that summary respects display_config."""

    def test_disabled_wind_not_shown(self):
        """When wind is disabled in config, no wind info in summary."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = [_make_dp(h) for h in range(9, 17)]
        segments = [_make_segment_weather_with_timeseries(1, hourly)]
        dc = _default_dc()
        for mc in dc.metrics:
            if mc.metric_id in ("wind", "gust", "wind_direction"):
                mc.enabled = False

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        assert "wind" not in result.lower()
        assert "km/h" not in result.lower()

    def test_friendly_vs_raw_clouds(self):
        """When cloud_total.use_friendly_format=False, show percentage not emoji."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = [_make_dp(h, cloud_total_pct=65) for h in range(9, 17)]
        segments = [_make_segment_weather_with_timeseries(1, hourly, cloud_avg=65)]
        dc = _default_dc()
        for mc in dc.metrics:
            if mc.metric_id == "cloud_total":
                mc.use_friendly_format = False

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        assert "65" in result or "%" in result


# ===========================================================================
# TEST: Adjective thresholds
# ===========================================================================

class TestAdjectives:
    """Test precipitation and wind adjective thresholds."""

    def test_heavy_rain_adjective(self):
        """precip_sum > 10mm should say 'starker Regen'."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = [_make_dp(h, precip_1h_mm=2.5) for h in range(9, 17)]
        segments = [_make_segment_weather_with_timeseries(1, hourly, precip_sum=20.0, pop_max=90)]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        assert "stark" in result.lower()

    def test_storm_gusts(self):
        """wind_max > 60 should say 'Sturmboeen' or similar."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = [_make_dp(h, wind10m_kmh=65.0, gust_kmh=80.0) for h in range(9, 17)]
        segments = [_make_segment_weather_with_timeseries(
            1, hourly, wind_max=65.0, gust_max=80.0,
        )]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        result_lower = result.lower()
        assert "sturm" in result_lower or "böen" in result_lower or "boeen" in result_lower


# ===========================================================================
# TEST: Thunder time window
# ===========================================================================

class TestThunder:
    """Test thunder temporal window detection."""

    def test_thunder_with_time_window(self):
        """Thunder in specific hours should show time window."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = []
        for h in range(9, 17):
            tl = ThunderLevel.HIGH if 15 <= h <= 16 else ThunderLevel.NONE
            hourly.append(_make_dp(h, thunder_level=tl))

        segments = [_make_segment_weather_with_timeseries(
            1, hourly, thunder_max=ThunderLevel.HIGH,
        )]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        assert "⚡" in result or "gewitter" in result.lower()
        assert "15" in result


# ===========================================================================
# TEST: Graceful handling of None/missing data
# ===========================================================================

class TestGraceful:
    """Test graceful handling of None values and missing data."""

    def test_none_wind_no_crash(self):
        """Missing wind values should not crash, just omit wind part."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = [_make_dp(h, wind10m_kmh=None, gust_kmh=None) for h in range(9, 17)]
        segments = [_make_segment_weather_with_timeseries(
            1, hourly, wind_max=None, gust_max=None,
        )]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        assert "°C" in result

    def test_empty_timeseries_uses_summary(self):
        """With empty timeseries, fall back to aggregated summary."""
        from formatters.compact_summary import CompactSummaryFormatter

        segments = [_make_segment_weather_with_timeseries(1, [], precip_sum=3.0)]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von A nach B", dc)

        assert "°C" in result


# ===========================================================================
# TEST: Stage name shortening
# ===========================================================================

class TestStageName:
    """Test stage name appears shortened in output."""

    def test_stage_name_shortened(self):
        """Long stage name should be shortened."""
        from formatters.compact_summary import CompactSummaryFormatter

        hourly = [_make_dp(h) for h in range(9, 17)]
        segments = [_make_segment_weather_with_timeseries(1, hourly)]
        dc = _default_dc()

        formatter = CompactSummaryFormatter()
        result = formatter.format_stage_summary(segments, "Tag 1: von Valldemossa nach Deià", dc)

        assert "Valldemossa" in result
        assert "Deià" in result
        assert "Tag 1:" not in result
