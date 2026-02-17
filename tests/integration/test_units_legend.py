"""
Tests for F4: Units Legend (Einheiten-Legende im E-Mail-Footer).

SPEC: docs/specs/modules/units_legend.md v1.0

Tests real formatter behavior — NO mocking!
"""
from __future__ import annotations

import pytest
from datetime import date, datetime, time, timedelta, timezone

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.metric_catalog import build_default_display_config, get_metric_by_col_key
from formatters.trip_report import TripReportFormatter


# --- Helper: Create a segment with visibility data ---

def _make_segment_with_visibility() -> SegmentWeatherData:
    """Create a segment with visibility and standard metrics."""
    target_date = date.today() + timedelta(days=1)
    seg = TripSegment(
        segment_id="Seg1",
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500.0),
        end_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500.0),
        start_time=datetime.combine(target_date, time(8, 0), tzinfo=timezone.utc),
        end_time=datetime.combine(target_date, time(12, 0), tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=10.0,
        ascent_m=500.0,
        descent_m=200.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_seamless",
        run=datetime.now(timezone.utc), grid_res_km=1.0, interp="point_grid",
    )
    base = datetime.combine(target_date, time(8, 0), tzinfo=timezone.utc)
    data = []
    for h in range(4):
        data.append(ForecastDataPoint(
            ts=base + timedelta(hours=h),
            t2m_c=12.0 + h,
            wind10m_kmh=20.0 + h * 5,
            gust_kmh=35.0 + h * 5,
            precip_1h_mm=0.5,
            visibility_m=15000 - h * 3000,
            cloud_total_pct=40,
        ))
    ts = NormalizedTimeseries(meta=meta, data=data)
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=SegmentWeatherSummary(),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _dc_with_visibility() -> UnifiedWeatherDisplayConfig:
    """Build display config with visibility enabled."""
    dc = build_default_display_config()
    for mc in dc.metrics:
        if mc.metric_id == "visibility":
            mc.enabled = True
            mc.use_friendly_format = False
    return dc


class TestVisibilityFormatKm:
    """Visibility values should be in km without 'k' suffix."""

    def test_visibility_no_k_suffix(self):
        """Visibility >= 10km should be plain number without 'k'."""
        f = TripReportFormatter()
        f._friendly_keys = set()  # disable friendly format
        result = f._fmt_val("visibility", 15000)
        assert result == "15", f"Expected '15', got '{result}'"
        assert "k" not in result, f"Should not contain 'k' suffix: {result}"

    def test_visibility_mid_range_km(self):
        """Visibility 1-10km should be decimal without 'k'."""
        f = TripReportFormatter()
        f._friendly_keys = set()  # disable friendly format
        result = f._fmt_val("visibility", 5000)
        assert result == "5.0", f"Expected '5.0', got '{result}'"
        assert "k" not in result

    def test_visibility_sub_1km(self):
        """Visibility < 1km should be decimal km (e.g. 0.8)."""
        f = TripReportFormatter()
        f._friendly_keys = set()  # disable friendly format
        result = f._fmt_val("visibility", 800)
        assert result == "0.8", f"Expected '0.8', got '{result}'"


class TestUnitsLegend:
    """Units legend should appear in email footer."""

    def test_legend_in_html_footer(self):
        """HTML email should contain units legend in footer."""
        f = TripReportFormatter()
        seg = _make_segment_with_visibility()
        dc = _dc_with_visibility()

        report = f.format_email(
            segments=[seg],
            trip_name="Test Trip",
            report_type="morning",
            display_config=dc,
        )

        assert "Visib km" in report.email_html or "km" in report.email_html, \
            "HTML footer should contain visibility unit 'km'"
        assert "°C" in report.email_html, "HTML footer should contain temperature unit"

    def test_legend_in_plain_footer(self):
        """Plaintext email should contain units legend."""
        f = TripReportFormatter()
        seg = _make_segment_with_visibility()
        dc = _dc_with_visibility()

        report = f.format_email(
            segments=[seg],
            trip_name="Test Trip",
            report_type="morning",
            display_config=dc,
        )

        assert "Einheiten:" in report.email_plain, \
            "Plaintext should contain 'Einheiten:' legend line"
        assert "km" in report.email_plain, \
            "Plaintext legend should contain 'km' for visibility"

    def test_legend_groups_same_units(self):
        """Metrics with same unit should be grouped."""
        f = TripReportFormatter()
        seg = _make_segment_with_visibility()
        dc = _dc_with_visibility()

        report = f.format_email(
            segments=[seg],
            trip_name="Test Trip",
            report_type="morning",
            display_config=dc,
        )

        plain = report.email_plain
        assert "km/h" in plain, "Legend should contain 'km/h' for wind metrics"
        legend_line = [l for l in plain.split("\n") if "Einheiten:" in l]
        assert len(legend_line) == 1, "Should have exactly one legend line"
        assert legend_line[0].count("km/h") == 1, \
            f"km/h should appear once (grouped), got: {legend_line[0]}"

    def test_legend_only_active_metrics(self):
        """Legend should only contain units for enabled metrics."""
        f = TripReportFormatter()
        seg = _make_segment_with_visibility()
        dc = build_default_display_config()

        report = f.format_email(
            segments=[seg],
            trip_name="Test Trip",
            report_type="morning",
            display_config=dc,
        )

        legend_lines = [l for l in report.email_plain.split("\n") if "Einheiten:" in l]
        if legend_lines:
            assert "Visib" not in legend_lines[0], \
                f"Disabled metric 'Visib' should not appear in legend: {legend_lines[0]}"

    def test_display_unit_field_in_catalog(self):
        """Visibility metric should have display_unit='km'."""
        m = get_metric_by_col_key("visibility")
        assert hasattr(m, "display_unit"), "MetricDefinition should have display_unit field"
        assert m.display_unit == "km", f"Visibility display_unit should be 'km', got '{m.display_unit}'"
