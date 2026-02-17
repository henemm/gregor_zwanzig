"""
Regression tests: Config persistence and metric visibility.

BUG-03: Config-Reset — Ensures user metric settings survive save/load cycles.
BUG-04: Trip-Edit preserves configs.

Tests real loader, formatter, and config objects — NO mocking!
"""
from __future__ import annotations

import json
import tempfile
from copy import deepcopy
from datetime import date, datetime, time, timezone
from pathlib import Path

import pytest

from app.loader import load_trip, save_trip, _trip_to_dict, _parse_display_config
from app.metric_catalog import build_default_display_config, get_metric
from app.models import (
    ForecastDataPoint,
    MetricConfig,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint
from formatters.trip_report import TripReportFormatter


# =====================================================================
# Helpers
# =====================================================================

def _make_trip(display_config: UnifiedWeatherDisplayConfig | None = None) -> Trip:
    """Create minimal trip for testing."""
    return Trip(
        id="test-trip",
        name="Test Trip",
        stages=[
            Stage(
                id="T1",
                name="Stage 1",
                date=date(2026, 3, 1),
                waypoints=[
                    Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000),
                    Waypoint(id="G2", name="End", lat=47.1, lon=11.1, elevation_m=1500),
                ],
                start_time=time(9, 0),
            )
        ],
        display_config=display_config,
    )


def _make_dp(hour: int = 10) -> ForecastDataPoint:
    """Create a data point with all metrics populated."""
    return ForecastDataPoint(
        ts=datetime(2026, 3, 1, hour, 0, tzinfo=timezone.utc),
        t2m_c=10.0,
        wind10m_kmh=20.0,
        gust_kmh=30.0,
        precip_1h_mm=0.5,
        visibility_m=15000,
        uv_index=5.0,
        snowfall_limit_m=2000,
        cloud_total_pct=50,
        humidity_pct=60,
        cape_jkg=500,
    )


# =====================================================================
# Part 1: Save/Load roundtrip preserves ALL config values
# =====================================================================


class TestConfigRoundtrip:
    """Save → Load must preserve every MetricConfig field."""

    def test_roundtrip_preserves_enabled_false(self, tmp_path: Path) -> None:
        """enabled=False survives save/load."""
        dc = build_default_display_config("test-trip")
        # Set visibility to disabled
        new_metrics = []
        for mc in dc.metrics:
            if mc.metric_id == "visibility":
                new_metrics.append(MetricConfig(
                    metric_id="visibility", enabled=False,
                    aggregations=mc.aggregations,
                    use_friendly_format=True,
                ))
            else:
                new_metrics.append(mc)
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test-trip", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )

        trip = _make_trip(dc)
        # Save
        trips_dir = tmp_path / "trips"
        trips_dir.mkdir()
        data = _trip_to_dict(trip)
        path = trips_dir / "test-trip.json"
        path.write_text(json.dumps(data, indent=2))
        # Load
        loaded = load_trip(path)
        vis_mc = next(mc for mc in loaded.display_config.metrics if mc.metric_id == "visibility")
        assert vis_mc.enabled is False

    def test_roundtrip_preserves_friendly_false(self, tmp_path: Path) -> None:
        """use_friendly_format=False survives save/load."""
        dc = build_default_display_config("test-trip")
        new_metrics = []
        for mc in dc.metrics:
            if mc.metric_id == "visibility":
                new_metrics.append(MetricConfig(
                    metric_id="visibility", enabled=True,
                    aggregations=mc.aggregations,
                    use_friendly_format=False,
                ))
            else:
                new_metrics.append(mc)
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test-trip", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )

        trip = _make_trip(dc)
        data = _trip_to_dict(trip)
        path = tmp_path / "test-trip.json"
        path.write_text(json.dumps(data, indent=2))
        loaded = load_trip(path)
        vis_mc = next(mc for mc in loaded.display_config.metrics if mc.metric_id == "visibility")
        assert vis_mc.use_friendly_format is False

    def test_roundtrip_preserves_alert_enabled(self, tmp_path: Path) -> None:
        """alert_enabled=True with threshold survives save/load."""
        dc = build_default_display_config("test-trip")
        new_metrics = []
        for mc in dc.metrics:
            if mc.metric_id == "cape":
                new_metrics.append(MetricConfig(
                    metric_id="cape", enabled=True,
                    aggregations=mc.aggregations,
                    alert_enabled=True, alert_threshold=500.0,
                ))
            else:
                new_metrics.append(mc)
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test-trip", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )

        trip = _make_trip(dc)
        data = _trip_to_dict(trip)
        path = tmp_path / "test-trip.json"
        path.write_text(json.dumps(data, indent=2))
        loaded = load_trip(path)
        cape_mc = next(mc for mc in loaded.display_config.metrics if mc.metric_id == "cape")
        assert cape_mc.alert_enabled is True
        assert cape_mc.alert_threshold == 500.0

    def test_roundtrip_all_metrics_count(self, tmp_path: Path) -> None:
        """All metrics survive roundtrip (none lost, none added)."""
        dc = build_default_display_config("test-trip")
        trip = _make_trip(dc)
        original_count = len(dc.metrics)
        data = _trip_to_dict(trip)
        path = tmp_path / "test-trip.json"
        path.write_text(json.dumps(data, indent=2))
        loaded = load_trip(path)
        assert len(loaded.display_config.metrics) == original_count


# =====================================================================
# Part 2: Trip-Edit preserves configs (BUG-04 regression)
# =====================================================================


class TestTripEditPreservesConfig:
    """Editing trip name/stages must NOT destroy display_config."""

    def test_trip_to_dict_includes_display_config(self) -> None:
        """_trip_to_dict serializes display_config when present."""
        dc = build_default_display_config("test-trip")
        trip = _make_trip(dc)
        data = _trip_to_dict(trip)
        assert "display_config" in data
        assert len(data["display_config"]["metrics"]) > 0

    def test_trip_without_display_config_omits_key(self) -> None:
        """_trip_to_dict omits display_config when None (existing bug scenario)."""
        trip = _make_trip(display_config=None)
        data = _trip_to_dict(trip)
        assert "display_config" not in data

    def test_edit_trip_preserves_display_config(self, tmp_path: Path) -> None:
        """Simulates trip edit: change name, keep display_config."""
        dc = build_default_display_config("test-trip")
        # Customize a metric
        for mc in dc.metrics:
            if mc.metric_id == "visibility":
                mc.enabled = False
                mc.use_friendly_format = True

        trip = _make_trip(dc)
        # Save original
        data = _trip_to_dict(trip)
        path = tmp_path / "test-trip.json"
        path.write_text(json.dumps(data, indent=2))

        # Simulate edit: load, change name, preserve configs, save
        loaded = load_trip(path)
        edited = Trip(
            id=loaded.id,
            name="Renamed Trip",
            stages=loaded.stages,
            avalanche_regions=loaded.avalanche_regions,
            display_config=loaded.display_config,
            weather_config=loaded.weather_config,
            report_config=loaded.report_config,
        )
        data2 = _trip_to_dict(edited)
        path.write_text(json.dumps(data2, indent=2))

        # Verify config survived
        reloaded = load_trip(path)
        assert reloaded.name == "Renamed Trip"
        assert reloaded.display_config is not None
        vis_mc = next(mc for mc in reloaded.display_config.metrics if mc.metric_id == "visibility")
        assert vis_mc.enabled is False
        assert vis_mc.use_friendly_format is True


# =====================================================================
# Part 3: Disabled metrics do NOT appear in report rows
# =====================================================================


class TestDisabledMetricsExcluded:
    """Disabled metrics must not appear in formatter output."""

    def test_disabled_visibility_not_in_row(self) -> None:
        """visibility.enabled=False → 'visibility' key absent from row."""
        dc = build_default_display_config()
        new_metrics = [
            MetricConfig(
                metric_id=mc.metric_id,
                enabled=False if mc.metric_id == "visibility" else mc.enabled,
                aggregations=mc.aggregations,
            )
            for mc in dc.metrics
        ]
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )

        fmt = TripReportFormatter()
        dp = _make_dp()
        row = fmt._dp_to_row(dp, dc)
        assert "visibility" not in row

    def test_disabled_uv_not_in_row(self) -> None:
        """uv_index.enabled=False → 'uv' key absent from row."""
        dc = build_default_display_config()
        new_metrics = [
            MetricConfig(
                metric_id=mc.metric_id,
                enabled=False if mc.metric_id == "uv_index" else mc.enabled,
                aggregations=mc.aggregations,
            )
            for mc in dc.metrics
        ]
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )

        fmt = TripReportFormatter()
        row = fmt._dp_to_row(_make_dp(), dc)
        assert "uv" not in row

    def test_disabled_snowfall_limit_not_in_row(self) -> None:
        """snowfall_limit.enabled=False → 'snow_limit' key absent from row."""
        dc = build_default_display_config()
        new_metrics = [
            MetricConfig(
                metric_id=mc.metric_id,
                enabled=False if mc.metric_id == "snowfall_limit" else mc.enabled,
                aggregations=mc.aggregations,
            )
            for mc in dc.metrics
        ]
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )
        fmt = TripReportFormatter()
        row = fmt._dp_to_row(_make_dp(), dc)
        assert "snow_limit" not in row

    def test_enabled_metrics_present_in_row(self) -> None:
        """Enabled metrics DO appear in rows."""
        dc = build_default_display_config()
        fmt = TripReportFormatter()
        row = fmt._dp_to_row(_make_dp(), dc)
        # temperature, wind, gust, precipitation are enabled by default
        assert "temp" in row
        assert "wind" in row
        assert "gust" in row
        assert "precip" in row


# =====================================================================
# Part 4: Friendly format respects per-metric config
# =====================================================================


class TestFriendlyFormatRespectsConfig:
    """use_friendly_format=False → numeric output, True → emoji/label."""

    def test_visibility_friendly_off_shows_numeric(self) -> None:
        """visibility.use_friendly_format=False → '15' not 'good'."""
        dc = build_default_display_config()
        new_metrics = [
            MetricConfig(
                metric_id=mc.metric_id, enabled=True,
                aggregations=mc.aggregations,
                use_friendly_format=False if mc.metric_id == "visibility" else mc.use_friendly_format,
            )
            for mc in dc.metrics
        ]
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )
        fmt = TripReportFormatter()
        fmt._friendly_keys = fmt._build_friendly_keys(dc)
        result = fmt._fmt_val("visibility", 15000)
        assert result == "15"
        assert result != "good"

    def test_visibility_friendly_on_shows_label(self) -> None:
        """visibility.use_friendly_format=True → 'good'."""
        dc = build_default_display_config()
        new_metrics = [
            MetricConfig(
                metric_id=mc.metric_id, enabled=True,
                aggregations=mc.aggregations,
                use_friendly_format=True if mc.metric_id == "visibility" else mc.use_friendly_format,
            )
            for mc in dc.metrics
        ]
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )
        fmt = TripReportFormatter()
        fmt._friendly_keys = fmt._build_friendly_keys(dc)
        result = fmt._fmt_val("visibility", 15000)
        assert result == "good"

    def test_cloud_friendly_off_shows_numeric(self) -> None:
        """cloud_total.use_friendly_format=False → '50' not emoji."""
        dc = build_default_display_config()
        new_metrics = [
            MetricConfig(
                metric_id=mc.metric_id, enabled=True,
                aggregations=mc.aggregations,
                use_friendly_format=False if mc.metric_id == "cloud_total" else mc.use_friendly_format,
            )
            for mc in dc.metrics
        ]
        dc = UnifiedWeatherDisplayConfig(
            trip_id="test", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )
        fmt = TripReportFormatter()
        fmt._friendly_keys = fmt._build_friendly_keys(dc)
        result = fmt._fmt_val("cloud", 50)
        assert result == "50"
