"""
Unit tests for WEATHER-05b: Model-Metric-Fallback.

Tests that:
1. ForecastMeta has fallback tracking fields
2. _find_fallback_model selects correct fallback
3. _merge_fallback fills None fields without overwriting
4. fetch_forecast integrates fallback when cache available
5. Footer renders fallback info

SPEC: docs/specs/modules/model_metric_fallback.md v1.0
TDD RED: All tests MUST FAIL before implementation.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_meta(model: str = "meteofrance_arome") -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model=model,
        run=datetime(2026, 2, 16, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
        interp="grid_point",
    )


def _make_dp(hour: int, cape: float | None = None, visibility: float | None = None) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 2, 17, hour, 0, tzinfo=timezone.utc),
        t2m_c=10.0,
        wind10m_kmh=15.0,
        gust_kmh=25.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        humidity_pct=60,
        cape_jkg=cape,
        visibility_m=visibility,
    )


def _make_timeseries(model: str = "meteofrance_arome", cape: float | None = None, visibility: float | None = None) -> NormalizedTimeseries:
    meta = _make_meta(model)
    data = [_make_dp(h, cape=cape, visibility=visibility) for h in range(8, 11)]
    return NormalizedTimeseries(meta=meta, data=data)


# ---------------------------------------------------------------------------
# Test 1: ForecastMeta fallback fields
# ---------------------------------------------------------------------------

class TestForecastMetaFallbackFields:
    """ForecastMeta must have fallback tracking fields."""

    def test_fallback_model_field_exists(self) -> None:
        meta = _make_meta()
        assert hasattr(meta, 'fallback_model')
        assert meta.fallback_model is None

    def test_fallback_metrics_field_exists(self) -> None:
        meta = _make_meta()
        assert hasattr(meta, 'fallback_metrics')
        assert meta.fallback_metrics == []

    def test_fallback_fields_settable(self) -> None:
        meta = _make_meta()
        meta.fallback_model = "icon_eu"
        meta.fallback_metrics = ["cape", "visibility"]
        assert meta.fallback_model == "icon_eu"
        assert len(meta.fallback_metrics) == 2


# ---------------------------------------------------------------------------
# Test 2: _find_fallback_model
# ---------------------------------------------------------------------------

class TestFindFallbackModel:
    """_find_fallback_model must select the right fallback."""

    def test_finds_fallback_for_arome_coords(self) -> None:
        """AROME at Mallorca should fall back to ICON-EU or ECMWF."""
        from providers.openmeteo import OpenMeteoProvider, AVAILABILITY_CACHE_PATH

        # Write a fake cache with AROME missing cape, icon_eu having it
        cache = {
            "probe_date": date.today().isoformat(),
            "models": {
                "meteofrance_arome": {"available": ["temperature_2m"], "unavailable": ["cape", "visibility"]},
                "icon_eu": {"available": ["temperature_2m", "cape", "visibility"], "unavailable": []},
                "ecmwf_ifs04": {"available": ["temperature_2m", "cape"], "unavailable": ["visibility"]},
            }
        }
        AVAILABILITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        AVAILABILITY_CACHE_PATH.write_text(json.dumps(cache))

        provider = OpenMeteoProvider()
        result = provider._find_fallback_model("meteofrance_arome", 39.7, 2.6, ["cape", "visibility"])

        assert result is not None
        fb_model_id, fb_grid_res_km, fb_endpoint = result
        # Should pick icon_eu (has both cape AND visibility, lower priority than ecmwf)
        assert fb_model_id == "icon_eu"

    def test_returns_none_without_cache(self) -> None:
        """No cache → no fallback."""
        from providers.openmeteo import OpenMeteoProvider, AVAILABILITY_CACHE_PATH

        # Remove cache if exists
        if AVAILABILITY_CACHE_PATH.exists():
            AVAILABILITY_CACHE_PATH.unlink()

        provider = OpenMeteoProvider()
        result = provider._find_fallback_model("meteofrance_arome", 39.7, 2.6, ["cape"])

        assert result is None


# ---------------------------------------------------------------------------
# Test 3: _merge_fallback
# ---------------------------------------------------------------------------

class TestMergeFallback:
    """_merge_fallback must fill None fields without overwriting."""

    def test_fills_none_fields(self) -> None:
        from providers.openmeteo import OpenMeteoProvider

        primary = _make_timeseries(cape=None, visibility=None)
        fallback = _make_timeseries(model="icon_eu", cape=500.0, visibility=10000.0)

        provider = OpenMeteoProvider()
        filled = provider._merge_fallback(primary, fallback, ["cape", "visibility"])

        assert "cape" in filled
        assert primary.data[0].cape_jkg == 500.0

    def test_does_not_overwrite_existing(self) -> None:
        from providers.openmeteo import OpenMeteoProvider

        primary = _make_timeseries(cape=200.0, visibility=None)
        fallback = _make_timeseries(model="icon_eu", cape=500.0, visibility=10000.0)

        provider = OpenMeteoProvider()
        provider._merge_fallback(primary, fallback, ["cape", "visibility"])

        # cape was 200 in primary — must NOT be overwritten
        assert primary.data[0].cape_jkg == 200.0
        # visibility was None — must be filled
        assert primary.data[0].visibility_m == 10000.0


# ---------------------------------------------------------------------------
# Test 4: Footer rendering
# ---------------------------------------------------------------------------

class TestFooterFallbackInfo:
    """Footer must show fallback info when present."""

    def _make_segment_data(self, fallback_model=None, fallback_metrics=None):
        """Helper to create a SegmentWeatherData with fallback meta."""
        from app.models import SegmentWeatherData, SegmentWeatherSummary, TripSegment, GPXPoint

        today = date.today()
        meta = _make_meta()
        meta.fallback_model = fallback_model
        meta.fallback_metrics = fallback_metrics or []

        ts = NormalizedTimeseries(meta=meta, data=[_make_dp(8)])
        seg = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=39.7, lon=2.6, elevation_m=100.0),
            end_point=GPXPoint(lat=39.8, lon=2.7, elevation_m=200.0),
            start_time=datetime(today.year, today.month, today.day, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(today.year, today.month, today.day, 10, 0, tzinfo=timezone.utc),
            duration_hours=2.0,
            distance_km=5.0,
            ascent_m=100.0,
            descent_m=0.0,
        )
        return SegmentWeatherData(
            segment=seg,
            timeseries=ts,
            aggregated=SegmentWeatherSummary(
                temp_min_c=10.0, temp_max_c=12.0, wind_max_kmh=15.0,
                gust_max_kmh=25.0, precip_sum_mm=0.0, cloud_avg_pct=50,
            ),
            fetched_at=datetime.now(timezone.utc),
            provider="openmeteo",
        )

    def test_html_footer_shows_fallback(self) -> None:
        from formatters.trip_report import TripReportFormatter

        seg = self._make_segment_data(fallback_model="icon_eu", fallback_metrics=["cape", "visibility"])
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test Trip", "morning")

        assert "fallback" in report.email_html.lower()
        assert "icon_eu" in report.email_html

    def test_plain_footer_shows_fallback(self) -> None:
        from formatters.trip_report import TripReportFormatter

        seg = self._make_segment_data(fallback_model="icon_eu", fallback_metrics=["cape", "visibility"])
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test Trip", "morning")

        assert "fallback" in report.email_plain.lower()
        assert "icon_eu" in report.email_plain
