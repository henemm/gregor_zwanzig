"""TDD RED — Reports pro Typ Phase A: Per-Report-Type Metric Filtering.

Tests for:
1. get_metrics_for_report_type() on UnifiedWeatherDisplayConfig
2. Serialization roundtrip of morning_enabled/evening_enabled
3. Formatter uses per-report-type filtering
"""

from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helper: Build a minimal display config with per-type flags
# ---------------------------------------------------------------------------

def _build_dc(metric_configs):
    """Build UnifiedWeatherDisplayConfig from a list of (id, enabled, morning, evening) tuples."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    metrics = []
    for mc_tuple in metric_configs:
        metric_id, enabled, morning, evening = mc_tuple
        metrics.append(MetricConfig(
            metric_id=metric_id,
            enabled=enabled,
            morning_enabled=morning,
            evening_enabled=evening,
            aggregations=["min", "max"],
        ))
    return UnifiedWeatherDisplayConfig(
        trip_id="test",
        metrics=metrics,
        updated_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# 1. get_metrics_for_report_type()
# ---------------------------------------------------------------------------


class TestGetMetricsForReportType:
    """UnifiedWeatherDisplayConfig.get_metrics_for_report_type() method."""

    def test_method_exists(self):
        """GIVEN UnifiedWeatherDisplayConfig
        WHEN calling get_metrics_for_report_type
        THEN it should exist and be callable."""
        dc = _build_dc([("temperature", True, None, None)])
        result = dc.get_metrics_for_report_type("morning")
        assert isinstance(result, list)

    def test_none_inherits_global_enabled_true(self):
        """GIVEN metric with enabled=True, morning_enabled=None
        WHEN getting metrics for morning
        THEN metric is included (inherits global)."""
        dc = _build_dc([("temperature", True, None, None)])
        ids = [mc.metric_id for mc in dc.get_metrics_for_report_type("morning")]
        assert "temperature" in ids

    def test_none_inherits_global_enabled_false(self):
        """GIVEN metric with enabled=False, morning_enabled=None
        WHEN getting metrics for morning
        THEN metric is excluded (inherits global)."""
        dc = _build_dc([("temperature", False, None, None)])
        ids = [mc.metric_id for mc in dc.get_metrics_for_report_type("morning")]
        assert "temperature" not in ids

    def test_morning_false_overrides_global_true(self):
        """GIVEN metric with enabled=True, morning_enabled=False
        WHEN getting metrics for morning
        THEN metric is excluded (override)."""
        dc = _build_dc([("wind", True, False, None)])
        ids = [mc.metric_id for mc in dc.get_metrics_for_report_type("morning")]
        assert "wind" not in ids

    def test_morning_true_overrides_global_false(self):
        """GIVEN metric with enabled=False, morning_enabled=True
        WHEN getting metrics for morning
        THEN metric is included (override)."""
        dc = _build_dc([("uv_index", False, True, None)])
        ids = [mc.metric_id for mc in dc.get_metrics_for_report_type("morning")]
        assert "uv_index" in ids

    def test_evening_false_overrides_global_true(self):
        """GIVEN metric with enabled=True, evening_enabled=False
        WHEN getting metrics for evening
        THEN metric is excluded."""
        dc = _build_dc([("wind", True, None, False)])
        ids = [mc.metric_id for mc in dc.get_metrics_for_report_type("evening")]
        assert "wind" not in ids

    def test_evening_true_overrides_global_false(self):
        """GIVEN metric with enabled=False, evening_enabled=True
        WHEN getting metrics for evening
        THEN metric is included."""
        dc = _build_dc([("freezing_level", False, None, True)])
        ids = [mc.metric_id for mc in dc.get_metrics_for_report_type("evening")]
        assert "freezing_level" in ids

    def test_different_sets_morning_vs_evening(self):
        """GIVEN metrics configured differently for morning vs evening
        WHEN getting metrics for each type
        THEN different sets are returned."""
        dc = _build_dc([
            # temp: both (global enabled)
            ("temperature", True, None, None),
            # uv: morning only
            ("uv_index", True, True, False),
            # freezing_level: evening only
            ("freezing_level", True, False, True),
        ])
        morning_ids = {mc.metric_id for mc in dc.get_metrics_for_report_type("morning")}
        evening_ids = {mc.metric_id for mc in dc.get_metrics_for_report_type("evening")}

        assert "temperature" in morning_ids
        assert "temperature" in evening_ids
        assert "uv_index" in morning_ids
        assert "uv_index" not in evening_ids
        assert "freezing_level" not in morning_ids
        assert "freezing_level" in evening_ids

    def test_alert_type_uses_global_only(self):
        """GIVEN metric with morning_enabled=False but enabled=True
        WHEN getting metrics for 'alert'
        THEN it uses global enabled (ignores morning/evening flags)."""
        dc = _build_dc([("wind", True, False, False)])
        ids = [mc.metric_id for mc in dc.get_metrics_for_report_type("alert")]
        assert "wind" in ids

    def test_all_none_returns_same_as_enabled(self):
        """GIVEN all morning_enabled/evening_enabled are None
        WHEN getting metrics for morning
        THEN result matches global enabled set (regression protection)."""
        dc = _build_dc([
            ("temperature", True, None, None),
            ("wind", True, None, None),
            ("snow_depth", False, None, None),
        ])
        morning_ids = {mc.metric_id for mc in dc.get_metrics_for_report_type("morning")}
        global_ids = {mc.metric_id for mc in dc.metrics if mc.enabled}
        assert morning_ids == global_ids


# ---------------------------------------------------------------------------
# 2. Serialization roundtrip
# ---------------------------------------------------------------------------


class TestSerializationRoundtrip:
    """morning_enabled/evening_enabled survive save→load cycle."""

    def test_trip_save_includes_morning_evening(self):
        """GIVEN a trip with morning_enabled/evening_enabled set on MetricConfig
        WHEN saving to JSON and loading back
        THEN morning_enabled/evening_enabled are preserved."""
        from app.loader import _parse_display_config

        dc = _build_dc([
            ("temperature", True, True, False),
            ("wind", True, False, True),
            ("precipitation", True, None, None),
        ])

        # Serialize
        trip_dict = {"display_config": {
            "trip_id": "test",
            "metrics": [],
            "updated_at": dc.updated_at.isoformat(),
        }}
        # Use _trip_to_dict serialization path for metrics
        for mc in dc.metrics:
            trip_dict["display_config"]["metrics"].append({
                "metric_id": mc.metric_id,
                "enabled": mc.enabled,
                "morning_enabled": mc.morning_enabled,
                "evening_enabled": mc.evening_enabled,
                "aggregations": mc.aggregations,
                "use_friendly_format": mc.use_friendly_format,
                "alert_enabled": mc.alert_enabled,
                "alert_threshold": mc.alert_threshold,
            })

        # Deserialize
        loaded_dc = _parse_display_config(trip_dict["display_config"])

        # Verify roundtrip
        temp = next(mc for mc in loaded_dc.metrics if mc.metric_id == "temperature")
        assert temp.morning_enabled is True
        assert temp.evening_enabled is False

        wind = next(mc for mc in loaded_dc.metrics if mc.metric_id == "wind")
        assert wind.morning_enabled is False
        assert wind.evening_enabled is True

        precip = next(mc for mc in loaded_dc.metrics if mc.metric_id == "precipitation")
        assert precip.morning_enabled is None
        assert precip.evening_enabled is None

    def test_trip_to_dict_includes_morning_evening(self):
        """GIVEN a Trip with per-type metric flags
        WHEN calling _trip_to_dict()
        THEN the output dict contains morning_enabled/evening_enabled."""
        from app.loader import _trip_to_dict
        from app.trip import Trip, Stage, Waypoint
        from datetime import date, time as dtime

        dc = _build_dc([
            ("temperature", True, True, False),
        ])

        trip = Trip(
            id="test-rpt",
            name="Test Trip",
            stages=[Stage(
                id="S1", name="Stage 1", date=date(2026, 5, 1),
                waypoints=[
                    Waypoint(id="W1", name="Start", lat=47.0, lon=11.0, elevation_m=500),
                    Waypoint(id="W2", name="End", lat=47.1, lon=11.1, elevation_m=800),
                ],
                start_time=dtime(9, 0),
            )],
            display_config=dc,
        )
        result = _trip_to_dict(trip)

        # Check that morning_enabled is in the serialized metrics
        metrics_list = result.get("display_config", {}).get("metrics", [])
        assert len(metrics_list) > 0
        temp_dict = metrics_list[0]
        assert "morning_enabled" in temp_dict, (
            "_trip_to_dict must serialize morning_enabled"
        )
        assert temp_dict["morning_enabled"] is True
        assert "evening_enabled" in temp_dict, (
            "_trip_to_dict must serialize evening_enabled"
        )
        assert temp_dict["evening_enabled"] is False


# ---------------------------------------------------------------------------
# 3. Formatter uses per-report-type filtering
# ---------------------------------------------------------------------------


class TestFormatterPerTypeFiltering:
    """TripReportFormatter.format_email() ACTUALLY renders different columns per report type."""

    def _make_segment_data(self):
        """Build minimal real SegmentWeatherData with a few hours of forecast."""
        from app.models import (
            ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
            Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
        )

        now = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
        points = []
        for h in range(6):
            points.append(ForecastDataPoint(
                ts=datetime(2026, 5, 1, 9 + h, 0, tzinfo=timezone.utc),
                t2m_c=15.0 + h,
                wind10m_kmh=10.0,
                freezing_level_m=2800,
                uv_index=5.0,
            ))

        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="icon_d2",
            run=now,
            grid_res_km=2.0,
            interp="nearest",
        )
        ts = NormalizedTimeseries(meta=meta, data=points)
        segment = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
            end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=2000),
            start_time=now,
            end_time=datetime(2026, 5, 1, 15, 0, tzinfo=timezone.utc),
            duration_hours=6.0,
            distance_km=12.0,
            ascent_m=500,
            descent_m=0,
        )
        return SegmentWeatherData(
            segment=segment,
            timeseries=ts,
            aggregated=SegmentWeatherSummary(),
            fetched_at=now,
            provider="openmeteo",
        )

    def test_morning_report_excludes_evening_only_metric(self):
        """GIVEN freezing_level configured as evening-only
        WHEN calling format_email with report_type='morning'
        THEN freezing_level does NOT appear in email_plain output."""
        from formatters.trip_report import TripReportFormatter

        dc = _build_dc([
            ("temperature", True, None, None),
            ("freezing_level", True, False, True),  # evening only
        ])
        segment = self._make_segment_data()
        formatter = TripReportFormatter()
        report = formatter.format_email(
            segments=[segment],
            trip_name="Test Trip",
            report_type="morning",
            display_config=dc,
        )
        # freezing_level column header should NOT be in output
        assert "Frostgr" not in report.email_plain
        assert "FrzLvl" not in report.email_plain
        # temperature SHOULD be present
        assert "Temp" in report.email_plain or "°C" in report.email_plain

    def test_evening_report_includes_evening_only_metric(self):
        """GIVEN freezing_level configured as evening-only
        WHEN calling format_email with report_type='evening'
        THEN freezing_level DOES appear in email_plain output."""
        from formatters.trip_report import TripReportFormatter

        dc = _build_dc([
            ("temperature", True, None, None),
            ("freezing_level", True, False, True),  # evening only
        ])
        segment = self._make_segment_data()
        formatter = TripReportFormatter()
        report = formatter.format_email(
            segments=[segment],
            trip_name="Test Trip",
            report_type="evening",
            display_config=dc,
        )
        # freezing_level SHOULD appear (col_key or label)
        plain = report.email_plain.lower()
        assert "frostgr" in plain or "frzlvl" in plain or "freezing" in plain or "2800" in plain

    def test_morning_true_override_disabled_global_appears_in_output(self):
        """CRITICAL: enabled=False + morning_enabled=True must still render.
        This is the exact bug F001 caught — the formatter must not skip it."""
        from formatters.trip_report import TripReportFormatter

        dc = _build_dc([
            ("temperature", True, None, None),
            # uv_index: globally disabled, but forced for morning
            ("uv_index", False, True, None),
        ])
        segment = self._make_segment_data()
        formatter = TripReportFormatter()
        report = formatter.format_email(
            segments=[segment],
            trip_name="Test Trip",
            report_type="morning",
            display_config=dc,
        )
        # uv_index MUST appear despite enabled=False
        plain = report.email_plain.lower()
        assert "uv" in plain or "5.0" in plain, (
            f"uv_index (enabled=False, morning_enabled=True) must appear in morning report. "
            f"Got: {report.email_plain[:500]}"
        )
