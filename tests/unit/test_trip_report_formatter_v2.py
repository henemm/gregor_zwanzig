"""
Tests for TripReportFormatter v2 – hourly segment tables.

SPEC: docs/specs/modules/trip_report_formatter_v2.md
"""
from datetime import datetime, time, timezone

import pytest

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from formatters.trip_report import TripReportFormatter


def _config_with_disabled(*metric_ids: str) -> UnifiedWeatherDisplayConfig:
    """Build default display config with specific metrics disabled."""
    config = build_default_display_config()
    for mc in config.metrics:
        if mc.metric_id in metric_ids:
            mc.enabled = False
    return config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_dp(hour: int, day: int = 11, **overrides) -> ForecastDataPoint:
    """Create a ForecastDataPoint for a given hour."""
    defaults = dict(
        ts=datetime(2026, 2, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0 + hour * 0.3,
        wind10m_kmh=12.0 + hour * 0.5,
        gust_kmh=30.0 + hour * 1.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        wind_chill_c=10.0 + hour * 0.2,
        snowfall_limit_m=None,
        humidity_pct=55,
    )
    defaults.update(overrides)
    return ForecastDataPoint(**defaults)


def _make_timeseries(hours: range, day: int = 11, **dp_overrides) -> NormalizedTimeseries:
    """Create a NormalizedTimeseries spanning given hours."""
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="arome_france",
        run=datetime(2026, 2, day, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
        interp="point_grid",
    )
    data = [_make_dp(h, day=day, **dp_overrides) for h in hours]
    return NormalizedTimeseries(meta=meta, data=data)


def _make_segment(
    seg_id: int,
    start_hour: int,
    end_hour: int,
    day: int = 11,
    start_elev: float = 400.0,
    end_elev: float = 800.0,
) -> TripSegment:
    """Create a TripSegment."""
    return TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=39.71, lon=2.62, elevation_m=start_elev),
        end_point=GPXPoint(lat=39.75, lon=2.65, elevation_m=end_elev),
        start_time=datetime(2026, 2, day, start_hour, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, day, end_hour, 0, tzinfo=timezone.utc),
        duration_hours=float(end_hour - start_hour),
        distance_km=4.2,
        ascent_m=max(0, end_elev - start_elev),
        descent_m=max(0, start_elev - end_elev),
    )


def _make_segment_weather(
    seg_id: int = 1,
    start_hour: int = 8,
    end_hour: int = 10,
    day: int = 11,
    thunder: ThunderLevel = ThunderLevel.NONE,
    gust_max: float = 40.0,
    precip_total: float = 0.0,
) -> SegmentWeatherData:
    """Create full SegmentWeatherData with timeseries."""
    seg = _make_segment(seg_id, start_hour, end_hour, day=day)
    ts = _make_timeseries(range(0, 24), day=day, thunder_level=thunder)
    agg = SegmentWeatherSummary(
        temp_min_c=14.0,
        temp_max_c=19.0,
        temp_avg_c=16.5,
        wind_max_kmh=25.0,
        gust_max_kmh=gust_max,
        precip_sum_mm=precip_total,
        cloud_avg_pct=60,
        humidity_avg_pct=55,
        thunder_level_max=thunder,
        wind_chill_min_c=8.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=agg,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHourlyRows:
    """Spec: Each segment table has one row per hour within time window."""

    def test_hourly_rows_per_segment(self):
        """GIVEN 2 segments (08-10 and 10-12), WHEN formatted,
        THEN each segment section has rows for its hours only."""
        seg1 = _make_segment_weather(1, start_hour=8, end_hour=10)
        seg2 = _make_segment_weather(2, start_hour=10, end_hour=12)
        formatter = TripReportFormatter()
        report = formatter.format_email(
            [seg1, seg2], "GR221 Test", "morning",
        )
        html = report.email_html

        # Segment 1 should show hours 08, 09, 10 (hour-only format)
        assert ">08<" in html or "08</td>" in html
        assert ">09<" in html or "09</td>" in html
        # Segment 2 should show hours 10, 11, 12
        assert ">11<" in html or "11</td>" in html
        assert ">12<" in html or "12</td>" in html

    def test_hourly_temp_values_in_table(self):
        """GIVEN segment with timeseries, WHEN formatted,
        THEN individual hourly temp values appear (not just min-max range)."""
        seg = _make_segment_weather(1, start_hour=8, end_hour=10)
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test", "morning")

        # Check that individual hourly temp values appear
        # _make_dp(8) gives t2m_c = 15.0 + 8*0.3 = 17.4
        assert "17.4" in report.email_html
        # _make_dp(9) gives t2m_c = 15.0 + 9*0.3 = 17.7
        assert "17.7" in report.email_html


class TestDisplayConfig:
    """Spec: Hidden columns don't appear in output."""

    def test_columns_match_display_config(self):
        """GIVEN display_config with show_clouds=False and show_wind=False,
        WHEN formatted, THEN Wind and Wolken columns absent."""
        seg = _make_segment_weather()
        config = _config_with_disabled("wind", "cloud_total")
        formatter = TripReportFormatter()
        report = formatter.format_email(
            [seg], "Test", "morning", display_config=config,
        )
        html = report.email_html.lower()
        # Wind column header should not appear
        assert ">wind<" not in html
        # Clouds should also not appear (default off anyway)
        assert ">wolken<" not in html

    def test_temp_felt_hidden_when_disabled(self):
        """GIVEN show_temp_felt=False, THEN 'Gefühlt' column absent."""
        seg = _make_segment_weather()
        config = _config_with_disabled("wind_chill")
        formatter = TripReportFormatter()
        report = formatter.format_email(
            [seg], "Test", "morning", display_config=config,
        )
        assert "Gefühlt" not in report.email_html
        assert "Gefühlt" not in report.email_plain

    def test_default_display_config(self):
        """GIVEN no display_config, THEN sensible defaults applied
        (temp, wind, gusts, precip, thunder, snowfall_limit shown)."""
        seg = _make_segment_weather()
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test", "morning")
        html = report.email_html.lower()
        assert ">temp<" in html
        assert ">wind<" in html
        assert ">gust<" in html


class TestNightBlock:
    """Spec: Night block present in evening, absent in morning."""

    def test_night_block_evening_only(self):
        """GIVEN night_weather provided, WHEN report_type=evening,
        THEN night block appears. WHEN morning, THEN absent."""
        seg = _make_segment_weather()
        night_ts = _make_timeseries(range(14, 24), day=11)
        # Also add next morning hours (day=12, 0-6)
        night_morning = _make_timeseries(range(0, 7), day=12)
        # Combine: just use evening data for simplicity
        formatter = TripReportFormatter()

        evening = formatter.format_email(
            [seg], "Test", "evening", night_weather=night_ts,
        )
        morning = formatter.format_email(
            [seg], "Test", "morning", night_weather=night_ts,
        )
        assert "Nacht" in evening.email_html
        assert "Nacht" not in morning.email_html

    def test_night_block_2hourly(self):
        """GIVEN night_weather, THEN rows appear at 2h intervals."""
        seg = _make_segment_weather(1, start_hour=8, end_hour=14)
        night_ts = _make_timeseries(range(0, 24), day=11)
        formatter = TripReportFormatter()
        report = formatter.format_email(
            [seg], "Test", "evening", night_weather=night_ts,
        )
        plain = report.email_plain
        # Should have 2-hourly: 14, 16, 18, 20, 22 (hour-only format)
        # Night block rows use hour-only format like segment tables
        assert "14" in plain
        assert "16" in plain
        assert "18" in plain
        assert "20" in plain
        assert "22" in plain


class TestThunderForecast:
    """Spec: Thunder forecast +1/+2 days shown when provided."""

    def test_thunder_forecast_shown(self):
        """GIVEN thunder_forecast dict, THEN appears in output."""
        seg = _make_segment_weather()
        thunder_fc = {
            "+1": {"date": "12.02.2026", "level": ThunderLevel.NONE, "text": "Kein Gewitter erwartet"},
            "+2": {"date": "13.02.2026", "level": ThunderLevel.MED, "text": "Gewitter wahrscheinlich nachmittags"},
        }
        formatter = TripReportFormatter()
        report = formatter.format_email(
            [seg], "Test", "morning", thunder_forecast=thunder_fc,
        )
        assert "Gewitter-Vorschau" in report.email_html
        assert "12.02.2026" in report.email_html
        assert "13.02.2026" in report.email_html

    def test_no_thunder_forecast_when_none(self):
        """GIVEN no thunder_forecast, THEN section absent."""
        seg = _make_segment_weather()
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test", "morning")
        assert "Gewitter-Vorschau" not in report.email_html


class TestHTMLColorCoding:
    """Spec: High-risk cells have colored background."""

    def test_html_has_color_coding_for_high_gusts(self):
        """GIVEN segment with gust >= 80 km/h in hourly data,
        THEN HTML contains risk color styling."""
        seg = _make_segment_weather(1, start_hour=8, end_hour=10, gust_max=95.0)
        # Override timeseries to have high gusts at 09:00
        for dp in seg.timeseries.data:
            if dp.ts.hour == 9:
                dp.gust_kmh = 95.0
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test", "morning")
        # Should have some red/danger styling
        assert "c62828" in report.email_html or "ffebee" in report.email_html

    def test_html_has_thunder_icon(self):
        """GIVEN thunder_level=MED, THEN ⚡ emoji in HTML output."""
        seg = _make_segment_weather(1, thunder=ThunderLevel.MED)
        for dp in seg.timeseries.data:
            if 8 <= dp.ts.hour <= 10:
                dp.thunder_level = ThunderLevel.MED
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test", "morning")
        assert "⚡" in report.email_html


class TestPlainTextParity:
    """Spec: Plain-text contains same numeric values as HTML."""

    def test_plain_text_same_data(self):
        """GIVEN formatted report, THEN plain-text has same temp values as HTML."""
        seg = _make_segment_weather(1, start_hour=8, end_hour=10)
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test", "morning")
        # Both should contain the 08:00 temp value (17.4)
        assert "17.4" in report.email_html
        assert "17.4" in report.email_plain

    def test_plain_text_has_segment_tables(self):
        """Plain text should have structured segment tables, not just summary."""
        seg = _make_segment_weather(1, start_hour=8, end_hour=10)
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test", "morning")
        # Hour-only format in plain text tables
        assert "08" in report.email_plain
        assert "09" in report.email_plain


class TestSummary:
    """Spec: Summary shows only relevant highlights."""

    def test_summary_highlights_only(self):
        """GIVEN segment with high gusts, THEN summary mentions gusts.
        No generic 'Recommendations' section."""
        seg = _make_segment_weather(1, gust_max=95.0)
        formatter = TripReportFormatter()
        report = formatter.format_email([seg], "Test", "morning")
        plain = report.email_plain
        assert "Zusammenfassung" in plain or "Summary" in plain
        assert "Empfehlung" not in plain
        assert "Recommendation" not in plain


class TestSegmentHeaders:
    """Spec: Segment headers show elevation, distance, time range."""

    def test_segment_header_info(self):
        """GIVEN segment with known start/end elevation,
        THEN header shows elevation info and time range."""
        seg = _make_segment_weather(1, start_hour=8, end_hour=10)
        # start_elev=400, end_elev=800 (from _make_segment defaults)
        formatter = TripReportFormatter()
        report = formatter.format_email(
            [seg], "Test", "morning",
            stage_name="Tag 1: Valldemossa nach Deià",
        )
        html = report.email_html
        # Should contain elevation info
        assert "400" in html  # start elevation
        assert "800" in html  # end elevation
        # Should contain time range
        assert "08:00" in html
        assert "10:00" in html
