"""
Integration test: Real OpenMeteo snapshot for Mallorca — plausibility checks.

Regression target: visibility_min_m must NOT be None after WEATHER-05b fallback.
Uses real API calls (no mocks) per CLAUDE.md.
SPEC: docs/specs/bugfix/snapshot_plausibility_and_cache_isolation.md
"""
from __future__ import annotations

import sys
from datetime import date, datetime, time, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

MALLORCA_LAT = 39.77
MALLORCA_LON = 2.71


@pytest.fixture(scope="module")
def mallorca_summary():
    """Fetch real weather for Mallorca once per test module."""
    from app.models import TripSegment, GPXPoint
    from providers.base import get_provider
    from services.segment_weather import SegmentWeatherService

    provider = get_provider("openmeteo")
    today = date.today()
    start = datetime.combine(today, time(8, 0), tzinfo=timezone.utc)
    end = datetime.combine(today, time(18, 0), tzinfo=timezone.utc)

    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=MALLORCA_LAT, lon=MALLORCA_LON, elevation_m=100.0),
        end_point=GPXPoint(lat=MALLORCA_LAT, lon=MALLORCA_LON, elevation_m=100.0),
        start_time=start,
        end_time=end,
        duration_hours=10.0,
        distance_km=20.0,
        ascent_m=500.0,
        descent_m=500.0,
    )

    service = SegmentWeatherService(provider)
    return service.fetch_segment_weather(segment)


class TestCoreMetricsNotNone:
    """Core metrics must always be present — no fallback needed."""

    def test_temp_min_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.temp_min_c is not None

    def test_temp_max_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.temp_max_c is not None

    def test_wind_max_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.wind_max_kmh is not None

    def test_gust_max_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.gust_max_kmh is not None

    def test_precip_sum_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.precip_sum_mm is not None

    def test_cloud_avg_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.cloud_avg_pct is not None

    def test_humidity_avg_not_none(self, mallorca_summary):
        assert mallorca_summary.aggregated.humidity_avg_pct is not None


class TestFallbackMetricsNotNone:
    """Fallback metrics (WEATHER-05b) must be filled via ICON-EU for AROME at Mallorca."""

    def test_visibility_min_not_none(self, mallorca_summary):
        """REGRESSION TARGET: visibility must not be None after fallback."""
        assert mallorca_summary.aggregated.visibility_min_m is not None, (
            "visibility_min_m is None — WEATHER-05b fallback broken or cache deleted by tests"
        )


class TestValueRanges:
    """All metric values must be within physically plausible ranges."""

    def test_temp_range(self, mallorca_summary):
        agg = mallorca_summary.aggregated
        assert -50 <= agg.temp_min_c <= 50
        assert -50 <= agg.temp_max_c <= 50

    def test_wind_range(self, mallorca_summary):
        agg = mallorca_summary.aggregated
        assert 0 <= agg.wind_max_kmh <= 300
        assert 0 <= agg.gust_max_kmh <= 300

    def test_precip_range(self, mallorca_summary):
        assert 0 <= mallorca_summary.aggregated.precip_sum_mm <= 500

    def test_cloud_humidity_range(self, mallorca_summary):
        agg = mallorca_summary.aggregated
        assert 0 <= agg.cloud_avg_pct <= 100
        assert 0 <= agg.humidity_avg_pct <= 100

    def test_visibility_range(self, mallorca_summary):
        vis = mallorca_summary.aggregated.visibility_min_m
        if vis is not None:
            assert 0 <= vis <= 100_000

    def test_pressure_range_if_present(self, mallorca_summary):
        p = mallorca_summary.aggregated.pressure_avg_hpa
        if p is not None:
            assert 800 <= p <= 1100

    def test_uv_range_if_present(self, mallorca_summary):
        uv = mallorca_summary.aggregated.uv_index_max
        if uv is not None:
            assert 0 <= uv <= 15

    def test_cape_range_if_present(self, mallorca_summary):
        cape = mallorca_summary.aggregated.cape_max_jkg
        if cape is not None:
            assert 0 <= cape <= 5000


class TestCrossMetricConsistency:
    """Aggregated metrics must be mutually consistent."""

    def test_gust_gte_wind(self, mallorca_summary):
        agg = mallorca_summary.aggregated
        assert agg.gust_max_kmh >= agg.wind_max_kmh, (
            f"gust_max ({agg.gust_max_kmh}) must be >= wind_max ({agg.wind_max_kmh})"
        )

    def test_temp_max_gte_avg_gte_min(self, mallorca_summary):
        agg = mallorca_summary.aggregated
        if agg.temp_avg_c is not None:
            assert agg.temp_max_c >= agg.temp_avg_c >= agg.temp_min_c, (
                f"temp order violated: max={agg.temp_max_c} avg={agg.temp_avg_c} min={agg.temp_min_c}"
            )


class TestFallbackMechanismActive:
    """For AROME at Mallorca coordinates, fallback_model must be set."""

    def test_fallback_model_is_set(self, mallorca_summary):
        """AROME does not provide visibility — fallback must kick in."""
        meta = mallorca_summary.timeseries.meta
        assert meta.fallback_model is not None, (
            "fallback_model is None — WEATHER-05b did not activate for AROME/Mallorca"
        )
