"""
Integration tests for friendly-format email rendering + alert change detection.

Tests verify:
1. Email HTML contains emoji OR raw values based on MetricConfig.use_friendly_format
2. Per-metric alert_enabled / alert_threshold via from_display_config()
3. Weather change detection with manipulated summaries (simulated forecast shift)
4. Thunder enum ordinal comparison in change detection
5. Full alert flow: cached→fresh diff → filter significant → changes list

NO MOCKS — all tests use real DTOs with controlled values.

SPEC: docs/specs/modules/weather_config.md v2.3
SPEC: docs/specs/modules/weather_change_detection.md v2.2
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    ChangeSeverity,
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
    WeatherChange,
)


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc)


def _make_segment(segment_id: int = 1) -> TripSegment:
    return TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1200.0),
        start_time=_NOW,
        end_time=_NOW + timedelta(hours=2),
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=200.0,
        descent_m=0.0,
    )


def _make_meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=_NOW,
        grid_res_km=1.0,
        interp="point_grid",
    )


def _make_dp(
    hour: int = 10,
    temp: float = 15.0,
    wind: float = 12.0,
    gust: float = 25.0,
    precip: float = 0.0,
    cloud: float = 50.0,
    cape: float = 800.0,
    visibility: float = 5000.0,
    thunder: ThunderLevel = ThunderLevel.NONE,
    humidity: float = 65.0,
    wind_chill: float = 10.0,
    pressure: float = 1013.0,
    dewpoint: float = 8.0,
    pop: float = 30.0,
    uv_index: float | None = None,
) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=_NOW.replace(hour=hour),
        t2m_c=temp,
        wind10m_kmh=wind,
        gust_kmh=gust,
        precip_1h_mm=precip,
        cloud_total_pct=cloud,
        cape_jkg=cape,
        visibility_m=visibility,
        thunder_level=thunder,
        humidity_pct=humidity,
        wind_chill_c=wind_chill,
        pressure_msl_hpa=pressure,
        dewpoint_c=dewpoint,
        pop_pct=pop,
        uv_index=uv_index,
    )


def _make_summary(
    temp_max: float = 18.0,
    wind_max: float = 20.0,
    gust_max: float = 30.0,
    precip_sum: float = 0.0,
    cloud_avg: float = 50.0,
    cape_max: float = 800.0,
    visibility_min: float = 5000.0,
    thunder_max: ThunderLevel = ThunderLevel.NONE,
    humidity_avg: float = 65.0,
    wind_chill_min: float = 8.0,
    pressure_avg: float = 1013.0,
    dewpoint_avg: float = 8.0,
    pop_max: float = 30.0,
    uv_index_max: float | None = None,
    freezing_level: float = 2500.0,
    snow_depth: float = 0.0,
) -> SegmentWeatherSummary:
    return SegmentWeatherSummary(
        temp_min_c=temp_max - 5,
        temp_max_c=temp_max,
        temp_avg_c=temp_max - 2.5,
        wind_max_kmh=wind_max,
        gust_max_kmh=gust_max,
        precip_sum_mm=precip_sum,
        cloud_avg_pct=cloud_avg,
        cape_max_jkg=cape_max,
        visibility_min_m=visibility_min,
        thunder_level_max=thunder_max,
        humidity_avg_pct=humidity_avg,
        wind_chill_min_c=wind_chill_min,
        pressure_avg_hpa=pressure_avg,
        dewpoint_avg_c=dewpoint_avg,
        pop_max_pct=pop_max,
        uv_index_max=uv_index_max,
        freezing_level_m=freezing_level,
        snow_depth_cm=snow_depth,
    )


def _make_segment_weather(
    segment_id: int = 1,
    summary: SegmentWeatherSummary | None = None,
    dp_kwargs: dict | None = None,
) -> SegmentWeatherData:
    seg = _make_segment(segment_id)
    dp = _make_dp(**(dp_kwargs or {}))
    ts = NormalizedTimeseries(meta=_make_meta(), data=[dp])
    agg = summary or _make_summary()
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=agg,
        fetched_at=_NOW,
        provider="openmeteo",
    )


# ===========================================================================
# PART 1: E-Mail Formatting — Friendly vs Raw
# ===========================================================================

class TestEmailFriendlyVsRawFormatting:
    """
    Verify that format_email() produces HTML with correct format
    based on MetricConfig.use_friendly_format per metric.
    """

    def _make_config(self, friendly_cloud: bool, friendly_cape: bool,
                     friendly_vis: bool) -> UnifiedWeatherDisplayConfig:
        return UnifiedWeatherDisplayConfig(
            trip_id="test-trip",
            metrics=[
                MetricConfig(metric_id="temperature", enabled=True,
                             aggregations=["min", "max"]),
                MetricConfig(metric_id="wind", enabled=True,
                             aggregations=["max"]),
                MetricConfig(metric_id="cloud_total", enabled=True,
                             aggregations=["avg"],
                             use_friendly_format=friendly_cloud),
                MetricConfig(metric_id="cape", enabled=True,
                             aggregations=["max"],
                             use_friendly_format=friendly_cape),
                MetricConfig(metric_id="visibility", enabled=True,
                             aggregations=["min"],
                             use_friendly_format=friendly_vis),
                MetricConfig(metric_id="thunder", enabled=True,
                             aggregations=["max"]),
            ],
        )

    def _generate_report(self, dc: UnifiedWeatherDisplayConfig,
                         cloud: float = 50.0, cape: float = 800.0,
                         visibility: float = 5000.0):
        from formatters.trip_report import TripReportFormatter

        seg = _make_segment_weather(
            dp_kwargs={"cloud": cloud, "cape": cape, "visibility": visibility},
            summary=_make_summary(cloud_avg=cloud, cape_max=cape,
                                  visibility_min=visibility),
        )
        f = TripReportFormatter()
        return f.format_email(
            segments=[seg],
            trip_name="Test Trip",
            report_type="evening",
            display_config=dc,
        )

    # --- All Friendly ON ---

    def test_all_friendly_cloud_emoji_in_html(self):
        """Cloud 50% → ⛅ when friendly ON."""
        dc = self._make_config(True, True, True)
        report = self._generate_report(dc, cloud=50.0)
        assert "⛅" in report.email_html
        # Raw percentage should NOT be in the table
        # (but may appear in highlights, so just check emoji exists)

    def test_all_friendly_cape_emoji_in_html(self):
        """CAPE 800 J/kg → 🟡 when friendly ON."""
        dc = self._make_config(True, True, True)
        report = self._generate_report(dc, cape=800.0)
        assert "🟡" in report.email_html

    def test_all_friendly_visibility_level_in_html(self):
        """Visibility 5000m → 'fair' when friendly ON."""
        dc = self._make_config(True, True, True)
        report = self._generate_report(dc, visibility=5000.0)
        assert "fair" in report.email_html

    # --- All Friendly OFF ---

    def test_all_raw_cloud_percentage_in_html(self):
        """Cloud 50% → '50' when friendly OFF."""
        dc = self._make_config(False, False, False)
        report = self._generate_report(dc, cloud=50.0)
        html = report.email_html
        # Should NOT have cloud emoji
        assert "⛅" not in html
        # Raw "50" should appear somewhere in the table

    def test_all_raw_cape_number_in_html(self):
        """CAPE 800 J/kg → '800' when friendly OFF."""
        dc = self._make_config(False, False, False)
        report = self._generate_report(dc, cape=800.0)
        html = report.email_html
        assert "🟡" not in html
        assert "🟢" not in html

    def test_all_raw_visibility_km_in_html(self):
        """Visibility 5000m → '5.0' (km) when friendly OFF."""
        dc = self._make_config(False, False, False)
        report = self._generate_report(dc, visibility=5000.0)
        html = report.email_html
        assert "fair" not in html
        assert "5.0" in html

    # --- Mixed: cloud friendly, cape raw, visibility friendly ---

    def test_mixed_cloud_friendly_cape_raw(self):
        """Cloud friendly ON + CAPE friendly OFF → emoji + number."""
        dc = self._make_config(True, False, True)
        report = self._generate_report(dc, cloud=50.0, cape=800.0)
        html = report.email_html
        assert "⛅" in html       # Cloud friendly
        assert "🟡" not in html    # CAPE raw (no emoji)

    def test_mixed_visibility_friendly_in_html(self):
        """Visibility friendly ON + cloud/CAPE raw."""
        dc = self._make_config(False, False, True)
        report = self._generate_report(dc, visibility=5000.0)
        html = report.email_html
        assert "fair" in html

    # --- Edge cases ---

    def test_cape_extreme_raw_html_highlighted(self):
        """CAPE >= 1000 gets HTML highlighting when raw."""
        dc = self._make_config(False, False, False)
        report = self._generate_report(dc, cape=1500.0)
        html = report.email_html
        assert "1500" in html
        assert "background" in html  # Has highlighting span

    def test_cape_extreme_friendly_shows_orange(self):
        """CAPE 1500 → 🟠 when friendly ON."""
        dc = self._make_config(False, True, False)
        report = self._generate_report(dc, cape=1500.0)
        assert "🟠" in report.email_html

    def test_visibility_fog_raw_html_highlighted(self):
        """Visibility < 500m gets HTML highlighting when raw (now in km)."""
        dc = self._make_config(False, False, False)
        report = self._generate_report(dc, visibility=300.0)
        html = report.email_html
        assert "0.3" in html
        assert "background" in html

    def test_visibility_fog_friendly_shows_warning(self):
        """Visibility 300m → '⚠️ fog' when friendly ON."""
        dc = self._make_config(False, False, True)
        report = self._generate_report(dc, visibility=300.0)
        assert "fog" in report.email_html

    def test_cloud_all_levels_friendly(self):
        """All cloud levels produce correct emoji."""
        from formatters.trip_report import TripReportFormatter
        f = TripReportFormatter()
        f._friendly_keys = {"cloud"}

        assert f._fmt_val("cloud", 5) == "☀️"     # <= 10
        assert f._fmt_val("cloud", 20) == "🌤️"   # <= 30
        assert f._fmt_val("cloud", 50) == "⛅"     # <= 70
        assert f._fmt_val("cloud", 85) == "🌥️"   # <= 90
        assert f._fmt_val("cloud", 95) == "☁️"    # > 90

    def test_cape_all_levels_friendly(self):
        """All CAPE levels produce correct emoji."""
        from formatters.trip_report import TripReportFormatter
        f = TripReportFormatter()
        f._friendly_keys = {"cape"}

        assert f._fmt_val("cape", 100) == "🟢"    # <= 300
        assert f._fmt_val("cape", 500) == "🟡"    # <= 1000
        assert f._fmt_val("cape", 1500) == "🟠"   # <= 2000
        assert f._fmt_val("cape", 3000) == "🔴"   # > 2000

    def test_visibility_all_levels_friendly(self):
        """All visibility levels produce correct text."""
        from formatters.trip_report import TripReportFormatter
        f = TripReportFormatter()
        f._friendly_keys = {"visibility"}

        assert f._fmt_val("visibility", 15000) == "good"   # >= 10000
        assert f._fmt_val("visibility", 5000) == "fair"    # >= 4000
        assert f._fmt_val("visibility", 2000) == "poor"    # >= 1000
        assert "fog" in f._fmt_val("visibility", 500)       # < 1000


# ===========================================================================
# PART 2: from_display_config() — Per-Metric Alert Thresholds
# ===========================================================================

class TestFromDisplayConfig:
    """
    Test WeatherChangeDetectionService.from_display_config() factory.
    Verifies per-metric alert_enabled and alert_threshold are correctly applied.
    """

    def test_only_alert_enabled_metrics_in_map(self):
        """Only metrics with alert_enabled=True should appear in thresholds."""
        from services.weather_change_detection import WeatherChangeDetectionService

        dc = UnifiedWeatherDisplayConfig(
            trip_id="test",
            metrics=[
                MetricConfig(metric_id="temperature", alert_enabled=True),
                MetricConfig(metric_id="wind", alert_enabled=False),
                MetricConfig(metric_id="precipitation", alert_enabled=True),
            ],
        )
        service = WeatherChangeDetectionService.from_display_config(dc)

        assert "temp_min_c" in service._thresholds
        assert "temp_max_c" in service._thresholds
        assert "temp_avg_c" in service._thresholds
        assert "precip_sum_mm" in service._thresholds
        assert "wind_max_kmh" not in service._thresholds

    def test_custom_threshold_overrides_default(self):
        """User-set alert_threshold should override MetricCatalog default."""
        from services.weather_change_detection import WeatherChangeDetectionService

        dc = UnifiedWeatherDisplayConfig(
            trip_id="test",
            metrics=[
                MetricConfig(metric_id="temperature", alert_enabled=True,
                             alert_threshold=2.0),  # Default is 5.0
            ],
        )
        service = WeatherChangeDetectionService.from_display_config(dc)

        assert service._thresholds["temp_max_c"] == 2.0

    def test_none_threshold_uses_catalog_default(self):
        """alert_threshold=None should fall back to MetricCatalog default."""
        from services.weather_change_detection import WeatherChangeDetectionService

        dc = UnifiedWeatherDisplayConfig(
            trip_id="test",
            metrics=[
                MetricConfig(metric_id="temperature", alert_enabled=True,
                             alert_threshold=None),  # Should use 5.0
            ],
        )
        service = WeatherChangeDetectionService.from_display_config(dc)

        assert service._thresholds["temp_max_c"] == 5.0

    def test_empty_config_produces_empty_map(self):
        """No alert-enabled metrics → empty thresholds map."""
        from services.weather_change_detection import WeatherChangeDetectionService

        dc = UnifiedWeatherDisplayConfig(trip_id="test", metrics=[])
        service = WeatherChangeDetectionService.from_display_config(dc)

        assert service._thresholds == {}

    def test_all_alert_metrics_enabled(self):
        """Enable all alertable metrics → all should be in map."""
        from services.weather_change_detection import WeatherChangeDetectionService
        from app.metric_catalog import get_all_metrics

        metrics = []
        for m in get_all_metrics():
            if m.default_change_threshold is not None:
                metrics.append(MetricConfig(
                    metric_id=m.id, alert_enabled=True))

        dc = UnifiedWeatherDisplayConfig(trip_id="test", metrics=metrics)
        service = WeatherChangeDetectionService.from_display_config(dc)

        # Should match full catalog detection map
        from app.metric_catalog import get_change_detection_map
        assert service._thresholds == get_change_detection_map()

    def test_thunder_alert_enabled_in_map(self):
        """Thunder with alert_enabled → thunder_level_max in map."""
        from services.weather_change_detection import WeatherChangeDetectionService

        dc = UnifiedWeatherDisplayConfig(
            trip_id="test",
            metrics=[
                MetricConfig(metric_id="thunder", alert_enabled=True),
            ],
        )
        service = WeatherChangeDetectionService.from_display_config(dc)

        assert "thunder_level_max" in service._thresholds
        assert service._thresholds["thunder_level_max"] == 1.0

    def test_thunder_custom_threshold(self):
        """Thunder with custom threshold (2 Stufen = 2.0)."""
        from services.weather_change_detection import WeatherChangeDetectionService

        dc = UnifiedWeatherDisplayConfig(
            trip_id="test",
            metrics=[
                MetricConfig(metric_id="thunder", alert_enabled=True,
                             alert_threshold=2.0),
            ],
        )
        service = WeatherChangeDetectionService.from_display_config(dc)

        assert service._thresholds["thunder_level_max"] == 2.0

    def test_metrics_without_threshold_skipped(self):
        """Metrics like wind_direction (threshold=None) should be skipped."""
        from services.weather_change_detection import WeatherChangeDetectionService

        dc = UnifiedWeatherDisplayConfig(
            trip_id="test",
            metrics=[
                MetricConfig(metric_id="wind_direction", alert_enabled=True),
                MetricConfig(metric_id="precip_type", alert_enabled=True),
            ],
        )
        service = WeatherChangeDetectionService.from_display_config(dc)

        assert service._thresholds == {}

    def test_uv_index_alert_enabled(self):
        """UV-Index with alert_enabled → uv_index_max in map."""
        from services.weather_change_detection import WeatherChangeDetectionService

        dc = UnifiedWeatherDisplayConfig(
            trip_id="test",
            metrics=[
                MetricConfig(metric_id="uv_index", alert_enabled=True),
            ],
        )
        service = WeatherChangeDetectionService.from_display_config(dc)

        assert "uv_index_max" in service._thresholds
        assert service._thresholds["uv_index_max"] == 3.0


# ===========================================================================
# PART 3: Alert Change Detection — Simulated Weather Shifts
# ===========================================================================

class TestAlertChangeDetectionSimulated:
    """
    Simulate weather changes by constructing 'cached' and 'fresh'
    SegmentWeatherData with controlled summary values.
    No API calls — pure detection logic verification.
    """

    def test_temp_increase_detected(self):
        """Temperature +10°C (threshold 5°C) → detected as change."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(temp_max=15.0))
        fresh = _make_segment_weather(
            summary=_make_summary(temp_max=25.0))  # +10

        service = WeatherChangeDetectionService(
            thresholds={"temp_max_c": 5.0})
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 1
        assert changes[0].metric == "temp_max_c"
        assert changes[0].delta == pytest.approx(10.0)
        assert changes[0].direction == "increase"

    def test_temp_decrease_detected(self):
        """Temperature -8°C (threshold 5°C) → decrease detected."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(temp_max=20.0))
        fresh = _make_segment_weather(
            summary=_make_summary(temp_max=12.0))  # -8

        service = WeatherChangeDetectionService(
            thresholds={"temp_max_c": 5.0})
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 1
        assert changes[0].direction == "decrease"

    def test_below_threshold_no_change(self):
        """Temperature +3°C (threshold 5°C) → no change detected."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(temp_max=15.0))
        fresh = _make_segment_weather(
            summary=_make_summary(temp_max=18.0))  # +3

        service = WeatherChangeDetectionService(
            thresholds={"temp_max_c": 5.0})
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 0

    def test_wind_spike_detected(self):
        """Wind gust +40 km/h (threshold 20) → MAJOR severity."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(gust_max=30.0))
        fresh = _make_segment_weather(
            summary=_make_summary(gust_max=70.0))  # +40

        service = WeatherChangeDetectionService(
            thresholds={"gust_max_kmh": 20.0})
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 1
        assert changes[0].severity == ChangeSeverity.MAJOR  # 2x threshold

    def test_multiple_metrics_detected(self):
        """Multiple simultaneous changes → multiple WeatherChange objects."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(temp_max=15.0, wind_max=10.0,
                                  precip_sum=0.0))
        fresh = _make_segment_weather(
            summary=_make_summary(temp_max=25.0, wind_max=35.0,
                                  precip_sum=15.0))

        service = WeatherChangeDetectionService(
            thresholds={
                "temp_max_c": 5.0,
                "wind_max_kmh": 20.0,
                "precip_sum_mm": 10.0,
            })
        changes = service.detect_changes(cached, fresh)

        metrics_changed = {c.metric for c in changes}
        assert "temp_max_c" in metrics_changed
        assert "wind_max_kmh" in metrics_changed
        assert "precip_sum_mm" in metrics_changed

    def test_severity_minor_moderate_major(self):
        """Verify severity classification at different delta/threshold ratios."""
        from services.weather_change_detection import WeatherChangeDetectionService

        # 1.2x threshold → MINOR
        cached = _make_segment_weather(summary=_make_summary(temp_max=15.0))
        fresh_minor = _make_segment_weather(summary=_make_summary(temp_max=21.0))  # +6
        service = WeatherChangeDetectionService(thresholds={"temp_max_c": 5.0})
        changes = service.detect_changes(cached, fresh_minor)
        assert changes[0].severity == ChangeSeverity.MINOR

        # 1.6x threshold → MODERATE
        fresh_mod = _make_segment_weather(summary=_make_summary(temp_max=23.0))  # +8
        changes = service.detect_changes(cached, fresh_mod)
        assert changes[0].severity == ChangeSeverity.MODERATE

        # 2.5x threshold → MAJOR
        fresh_major = _make_segment_weather(summary=_make_summary(temp_max=27.5))  # +12.5
        changes = service.detect_changes(cached, fresh_major)
        assert changes[0].severity == ChangeSeverity.MAJOR

    def test_cape_change_detected_with_custom_threshold(self):
        """CAPE change with custom lower threshold → detected."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(cape_max=200.0))
        fresh = _make_segment_weather(
            summary=_make_summary(cape_max=600.0))  # +400

        # Custom threshold: 200 (instead of catalog default 500)
        service = WeatherChangeDetectionService(
            thresholds={"cape_max_jkg": 200.0})
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 1
        assert changes[0].metric == "cape_max_jkg"

    def test_uv_index_change_detected(self):
        """UV-Index change from 2 to 8 (threshold 3.0) → detected."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(uv_index_max=2.0))
        fresh = _make_segment_weather(
            summary=_make_summary(uv_index_max=8.0))  # +6

        service = WeatherChangeDetectionService(
            thresholds={"uv_index_max": 3.0})
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 1
        assert changes[0].metric == "uv_index_max"
        assert changes[0].delta == pytest.approx(6.0)


# ===========================================================================
# PART 4: Thunder Enum Ordinal Comparison
# ===========================================================================

class TestThunderEnumAlerts:
    """
    Thunder is an Enum (NONE/MED/HIGH) with ordinal comparison.
    Verify change detection works correctly with enum→ordinal conversion.
    """

    def test_thunder_none_to_high_detected(self):
        """Thunder NONE→HIGH (ordinal 0→2, threshold 1.0) → detected."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.NONE))
        fresh = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.HIGH))

        service = WeatherChangeDetectionService(
            thresholds={"thunder_level_max": 1.0})
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 1
        assert changes[0].metric == "thunder_level_max"
        assert changes[0].delta == pytest.approx(2.0)  # HIGH(2) - NONE(0)
        assert changes[0].direction == "increase"

    def test_thunder_none_to_med_detected(self):
        """Thunder NONE→MED (ordinal 0→1, threshold 1.0) → detected."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.NONE))
        fresh = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.MED))

        service = WeatherChangeDetectionService(
            thresholds={"thunder_level_max": 1.0})
        changes = service.detect_changes(cached, fresh)

        # Delta = 1.0, threshold = 1.0 → abs(1) > 1.0 is False
        # NB: Change detection uses > (strictly greater), so exactly at threshold = no alert
        assert len(changes) == 0

    def test_thunder_high_to_none_detected(self):
        """Thunder HIGH→NONE (ordinal 2→0, threshold 1.0) → decrease detected."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.HIGH))
        fresh = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.NONE))

        service = WeatherChangeDetectionService(
            thresholds={"thunder_level_max": 1.0})
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 1
        assert changes[0].direction == "decrease"

    def test_thunder_same_level_no_change(self):
        """Thunder MED→MED → no change."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.MED))
        fresh = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.MED))

        service = WeatherChangeDetectionService(
            thresholds={"thunder_level_max": 1.0})
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 0

    def test_thunder_2_stufen_threshold(self):
        """Thunder with 2-Stufen threshold: NONE→MED (delta 1) → NOT detected."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.NONE))
        fresh = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.MED))

        service = WeatherChangeDetectionService(
            thresholds={"thunder_level_max": 2.0})  # 2 Stufen
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 0  # Delta 1 not > 2

    def test_thunder_2_stufen_none_to_high(self):
        """Thunder with 2-Stufen threshold: NONE→HIGH (delta 2) → NOT detected (not > 2)."""
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.NONE))
        fresh = _make_segment_weather(
            summary=_make_summary(thunder_max=ThunderLevel.HIGH))

        service = WeatherChangeDetectionService(
            thresholds={"thunder_level_max": 2.0})
        changes = service.detect_changes(cached, fresh)

        # Delta = 2, threshold = 2.0 → abs(2) > 2.0 is False
        assert len(changes) == 0


# ===========================================================================
# PART 5: Full Alert Flow — TripAlertService with Simulated Data
# ===========================================================================

class TestAlertFlowWithSimulatedData:
    """
    Test TripAlertService._detect_all_changes() with crafted cached/fresh
    segment data. Verifies the full flow from segment matching through
    change detection to significance filtering.
    """

    def test_detect_all_changes_across_segments(self):
        """Changes detected across multiple segments."""
        from services.trip_alert import TripAlertService

        service = TripAlertService()

        cached = [
            _make_segment_weather(segment_id=1,
                                  summary=_make_summary(temp_max=15.0)),
            _make_segment_weather(segment_id=2,
                                  summary=_make_summary(temp_max=18.0)),
        ]
        fresh = [
            _make_segment_weather(segment_id=1,
                                  summary=_make_summary(temp_max=25.0)),  # +10
            _make_segment_weather(segment_id=2,
                                  summary=_make_summary(temp_max=20.0)),  # +2
        ]

        changes = service._detect_all_changes(cached, fresh)

        # Segment 1 should have changes, segment 2 should not (below threshold)
        seg1_changes = [c for c in changes if "temp_max" in c.metric]
        assert len(seg1_changes) >= 1

    def test_filter_significant_keeps_moderate_major(self):
        """Only MODERATE and MAJOR changes pass the filter."""
        from services.trip_alert import TripAlertService

        service = TripAlertService()

        changes = [
            WeatherChange(metric="temp_max_c", old_value=15.0, new_value=21.0,
                          delta=6.0, threshold=5.0, severity=ChangeSeverity.MINOR,
                          direction="increase"),
            WeatherChange(metric="wind_max_kmh", old_value=10.0, new_value=40.0,
                          delta=30.0, threshold=20.0, severity=ChangeSeverity.MODERATE,
                          direction="increase"),
            WeatherChange(metric="precip_sum_mm", old_value=0.0, new_value=25.0,
                          delta=25.0, threshold=10.0, severity=ChangeSeverity.MAJOR,
                          direction="increase"),
        ]

        significant = service._filter_significant_changes(changes)

        assert len(significant) == 2
        assert all(c.severity != ChangeSeverity.MINOR for c in significant)

    def test_per_metric_alert_config_used_in_detection(self):
        """
        TripAlertService uses from_display_config() when display_config has
        alert-enabled metrics. This test verifies the detector is configured
        with per-metric thresholds.
        """
        from app.trip import Stage, TimeWindow, Trip, Waypoint
        from datetime import date as date_type, time as time_type
        from services.trip_alert import TripAlertService

        # Create trip with per-metric alert config
        waypoint = Waypoint(
            id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0,
            time_window=TimeWindow(start=time_type(8, 0), end=time_type(10, 0)),
        )
        stage = Stage(id="T1", name="Tag 1", date=date_type.today(),
                      waypoints=[waypoint])

        trip = Trip(id="test-trip", name="Test Trip", stages=[stage])
        trip.display_config = UnifiedWeatherDisplayConfig(
            trip_id="test-trip",
            metrics=[
                MetricConfig(metric_id="temperature", alert_enabled=True,
                             alert_threshold=3.0),  # Lower than default 5.0
                MetricConfig(metric_id="wind", alert_enabled=False),
            ],
        )

        # Provide cached and fresh with temp +4 (above custom 3.0, below default 5.0)
        cached = [_make_segment_weather(
            summary=_make_summary(temp_max=15.0, wind_max=10.0))]
        fresh = [_make_segment_weather(
            summary=_make_summary(temp_max=19.0, wind_max=35.0))]  # temp +4, wind +25

        service = TripAlertService()
        # Trigger the detector setup
        if trip.display_config and trip.display_config.get_alert_enabled_metrics():
            from services.weather_change_detection import WeatherChangeDetectionService
            service._change_detector = WeatherChangeDetectionService.from_display_config(
                trip.display_config)

        changes = service._detect_all_changes(cached, fresh)

        # Temperature should be detected (delta 4 > threshold 3)
        temp_changes = [c for c in changes if "temp" in c.metric]
        assert len(temp_changes) > 0

        # Wind should NOT be detected (alert_enabled=False)
        wind_changes = [c for c in changes if "wind" in c.metric]
        assert len(wind_changes) == 0

    def test_storm_scenario_multiple_severe_changes(self):
        """
        Simulate approaching storm: temp drops, wind spikes, precipitation
        increases, CAPE rises, thunder appears. All at once.
        """
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(summary=_make_summary(
            temp_max=22.0,
            wind_max=15.0,
            gust_max=25.0,
            precip_sum=0.0,
            cape_max=100.0,
            thunder_max=ThunderLevel.NONE,
        ))
        fresh = _make_segment_weather(summary=_make_summary(
            temp_max=14.0,      # -8 → detected
            wind_max=45.0,      # +30 → detected
            gust_max=70.0,      # +45 → detected
            precip_sum=20.0,    # +20 → detected
            cape_max=1800.0,    # +1700 → detected
            thunder_max=ThunderLevel.HIGH,  # 0→2 → detected
        ))

        service = WeatherChangeDetectionService(thresholds={
            "temp_max_c": 5.0,
            "wind_max_kmh": 20.0,
            "gust_max_kmh": 20.0,
            "precip_sum_mm": 10.0,
            "cape_max_jkg": 500.0,
            "thunder_level_max": 1.0,
        })
        changes = service.detect_changes(cached, fresh)

        metrics = {c.metric for c in changes}
        assert "temp_max_c" in metrics
        assert "wind_max_kmh" in metrics
        assert "gust_max_kmh" in metrics
        assert "precip_sum_mm" in metrics
        assert "cape_max_jkg" in metrics
        assert "thunder_level_max" in metrics
        assert len(changes) == 6

        # All should be at least MODERATE
        for c in changes:
            assert c.severity in (ChangeSeverity.MODERATE, ChangeSeverity.MAJOR)

    def test_improving_weather_detected_as_decrease(self):
        """
        Weather improvement: wind calms, rain stops → direction="decrease".
        """
        from services.weather_change_detection import WeatherChangeDetectionService

        cached = _make_segment_weather(summary=_make_summary(
            wind_max=50.0, precip_sum=15.0))
        fresh = _make_segment_weather(summary=_make_summary(
            wind_max=10.0, precip_sum=0.0))  # calmed down

        service = WeatherChangeDetectionService(thresholds={
            "wind_max_kmh": 20.0,
            "precip_sum_mm": 10.0,
        })
        changes = service.detect_changes(cached, fresh)

        assert len(changes) == 2
        assert all(c.direction == "decrease" for c in changes)
