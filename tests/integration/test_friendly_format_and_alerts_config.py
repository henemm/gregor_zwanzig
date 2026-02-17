"""
Integration tests: use_friendly_format and alert_enabled config settings.

Verifies that:
1. _fmt_val() respects use_friendly_format=True/False for ALL friendly metrics
2. _build_friendly_keys() correctly builds the friendly key set
3. alert_enabled config controls which metrics are included in change detection

NO MOCKS — uses real TripReportFormatter, MetricCatalog, and WeatherChangeDetectionService.
"""

import pytest
from app.metric_catalog import get_metric, build_default_display_config
from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from formatters.trip_report import TripReportFormatter


# =====================================================================
# Helper: build display_config with specific friendly settings
# =====================================================================

def _make_display_config(friendly_overrides: dict[str, bool]) -> UnifiedWeatherDisplayConfig:
    """Build a display_config with specific use_friendly_format overrides.

    Args:
        friendly_overrides: {metric_id: use_friendly_format} for metrics to override.
                            All other metrics keep default (True).
    """
    dc = build_default_display_config()
    new_metrics = []
    for mc in dc.metrics:
        if mc.metric_id in friendly_overrides:
            new_metrics.append(MetricConfig(
                metric_id=mc.metric_id,
                enabled=True,
                aggregations=mc.aggregations,
                use_friendly_format=friendly_overrides[mc.metric_id],
                alert_enabled=mc.alert_enabled,
                alert_threshold=mc.alert_threshold,
            ))
        else:
            new_metrics.append(mc)
    return UnifiedWeatherDisplayConfig(
        trip_id="test", metrics=new_metrics,
        show_night_block=dc.show_night_block,
        night_interval_hours=dc.night_interval_hours,
        thunder_forecast_days=dc.thunder_forecast_days,
    )


def _make_formatter(dc: UnifiedWeatherDisplayConfig) -> TripReportFormatter:
    """Create a formatter with _friendly_keys built from the given config."""
    fmt = TripReportFormatter()
    fmt._friendly_keys = fmt._build_friendly_keys(dc)
    return fmt


# =====================================================================
# Part 1: _build_friendly_keys() correctness
# =====================================================================


class TestBuildFriendlyKeys:
    """_build_friendly_keys() must include only metrics with use_friendly=True."""

    def test_all_friendly_enabled(self) -> None:
        """Default config: all friendly metrics are in the set."""
        dc = build_default_display_config()
        fmt = TripReportFormatter()
        keys = fmt._build_friendly_keys(dc)
        # All metrics with has_friendly_format and default use_friendly=True
        assert "cloud" in keys
        assert "cape" in keys
        assert "thunder" in keys

    def test_visibility_disabled(self) -> None:
        """Visibility friendly=False: 'visibility' not in set."""
        dc = _make_display_config({"visibility": False})
        fmt = TripReportFormatter()
        keys = fmt._build_friendly_keys(dc)
        assert "visibility" not in keys

    def test_cape_disabled(self) -> None:
        """Cape friendly=False: 'cape' not in set."""
        dc = _make_display_config({"cape": False})
        fmt = TripReportFormatter()
        keys = fmt._build_friendly_keys(dc)
        assert "cape" not in keys

    def test_cloud_disabled(self) -> None:
        """Cloud friendly=False: 'cloud' not in set."""
        dc = _make_display_config({"cloud_total": False})
        fmt = TripReportFormatter()
        keys = fmt._build_friendly_keys(dc)
        assert "cloud" not in keys

    def test_all_friendly_disabled(self) -> None:
        """All friendly formats disabled: empty set."""
        overrides = {
            "thunder": False, "cape": False, "cloud_total": False,
            "cloud_low": False, "cloud_mid": False, "cloud_high": False,
            "visibility": False,
        }
        dc = _make_display_config(overrides)
        fmt = TripReportFormatter()
        keys = fmt._build_friendly_keys(dc)
        assert keys == set()


# =====================================================================
# Part 2: _fmt_val() respects friendly format per metric
# =====================================================================


class TestFmtValFriendlyVisibility:
    """Visibility: friendly='good/fair/poor/fog', numeric='Xk' or 'X'."""

    def test_friendly_enabled_good(self) -> None:
        fmt = _make_formatter(_make_display_config({"visibility": True}))
        assert fmt._fmt_val("visibility", 15000) == "good"

    def test_friendly_enabled_fair(self) -> None:
        fmt = _make_formatter(_make_display_config({"visibility": True}))
        assert fmt._fmt_val("visibility", 5000) == "fair"

    def test_friendly_enabled_poor(self) -> None:
        fmt = _make_formatter(_make_display_config({"visibility": True}))
        assert fmt._fmt_val("visibility", 2000) == "poor"

    def test_friendly_enabled_fog(self) -> None:
        fmt = _make_formatter(_make_display_config({"visibility": True}))
        result = fmt._fmt_val("visibility", 500)
        assert "fog" in result

    def test_friendly_disabled_large(self) -> None:
        fmt = _make_formatter(_make_display_config({"visibility": False}))
        assert fmt._fmt_val("visibility", 15000) == "15"

    def test_friendly_disabled_medium(self) -> None:
        fmt = _make_formatter(_make_display_config({"visibility": False}))
        assert fmt._fmt_val("visibility", 5000) == "5.0"

    def test_friendly_disabled_small(self) -> None:
        fmt = _make_formatter(_make_display_config({"visibility": False}))
        assert fmt._fmt_val("visibility", 800) == "0.8"

    def test_friendly_disabled_small_html_orange(self) -> None:
        fmt = _make_formatter(_make_display_config({"visibility": False}))
        result = fmt._fmt_val("visibility", 300, html=True)
        assert "background:#fff3e0" in result


class TestFmtValFriendlyCape:
    """Cape: friendly=emoji, numeric=number."""

    def test_friendly_enabled_green(self) -> None:
        fmt = _make_formatter(_make_display_config({"cape": True}))
        assert fmt._fmt_val("cape", 200) == "\U0001f7e2"

    def test_friendly_enabled_yellow(self) -> None:
        fmt = _make_formatter(_make_display_config({"cape": True}))
        assert fmt._fmt_val("cape", 800) == "\U0001f7e1"

    def test_friendly_enabled_orange(self) -> None:
        fmt = _make_formatter(_make_display_config({"cape": True}))
        assert fmt._fmt_val("cape", 1500) == "\U0001f7e0"

    def test_friendly_enabled_red(self) -> None:
        fmt = _make_formatter(_make_display_config({"cape": True}))
        assert fmt._fmt_val("cape", 2500) == "\U0001f534"

    def test_friendly_disabled_numeric(self) -> None:
        fmt = _make_formatter(_make_display_config({"cape": False}))
        assert fmt._fmt_val("cape", 1500) == "1500"

    def test_friendly_disabled_html_yellow(self) -> None:
        fmt = _make_formatter(_make_display_config({"cape": False}))
        result = fmt._fmt_val("cape", 1500, html=True)
        assert "background:#fff9c4" in result


class TestFmtValFriendlyCloud:
    """Cloud: friendly=emoji, numeric=number."""

    def test_friendly_enabled_sun(self) -> None:
        fmt = _make_formatter(_make_display_config({"cloud_total": True}))
        assert "☀" in fmt._fmt_val("cloud", 5)

    def test_friendly_enabled_partly(self) -> None:
        fmt = _make_formatter(_make_display_config({"cloud_total": True}))
        assert fmt._fmt_val("cloud", 50) == "⛅"

    def test_friendly_enabled_overcast(self) -> None:
        fmt = _make_formatter(_make_display_config({"cloud_total": True}))
        assert "☁" in fmt._fmt_val("cloud", 95)

    def test_friendly_disabled_numeric(self) -> None:
        fmt = _make_formatter(_make_display_config({"cloud_total": False}))
        assert fmt._fmt_val("cloud", 50) == "50"

    def test_friendly_disabled_numeric_low(self) -> None:
        fmt = _make_formatter(_make_display_config({"cloud_total": False}))
        assert fmt._fmt_val("cloud", 5) == "5"


# =====================================================================
# Part 3: alert_enabled controls change detection
# =====================================================================


class TestAlertEnabledConfig:
    """alert_enabled must control which metrics are in change detection."""

    def test_default_alert_metrics(self) -> None:
        """Default config has 5 alert-enabled metrics."""
        dc = build_default_display_config()
        alert_metrics = dc.get_alert_enabled_metrics()
        alert_ids = {mc.metric_id for mc in alert_metrics}
        assert "temperature" in alert_ids
        assert "wind" in alert_ids
        assert "gust" in alert_ids
        assert "precipitation" in alert_ids
        assert "wind_chill" in alert_ids

    def test_cape_not_alert_by_default(self) -> None:
        """Cape is NOT alert-enabled by default."""
        dc = build_default_display_config()
        alert_ids = {mc.metric_id for mc in dc.get_alert_enabled_metrics()}
        assert "cape" not in alert_ids

    def test_custom_alert_config(self) -> None:
        """Custom config with cape alert enabled, wind disabled."""
        dc = build_default_display_config()
        new_metrics = []
        for mc in dc.metrics:
            if mc.metric_id == "cape":
                new_metrics.append(MetricConfig(
                    metric_id="cape", enabled=True,
                    aggregations=mc.aggregations,
                    alert_enabled=True, alert_threshold=500.0,
                ))
            elif mc.metric_id == "wind":
                new_metrics.append(MetricConfig(
                    metric_id="wind", enabled=True,
                    aggregations=mc.aggregations,
                    alert_enabled=False,
                ))
            else:
                new_metrics.append(mc)
        dc_custom = UnifiedWeatherDisplayConfig(
            trip_id="test", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )
        alert_ids = {mc.metric_id for mc in dc_custom.get_alert_enabled_metrics()}
        assert "cape" in alert_ids
        assert "wind" not in alert_ids

    def test_change_detection_uses_alert_config(self) -> None:
        """WeatherChangeDetectionService.from_display_config() respects alert_enabled."""
        from services.weather_change_detection import WeatherChangeDetectionService

        dc = build_default_display_config()
        service = WeatherChangeDetectionService.from_display_config(dc)
        # Default: temperature, wind, gust, precipitation, wind_chill
        # Thresholds use summary field names (e.g. temp_min_c, wind_max_kmh)
        assert len(service._thresholds) >= 5
        # Verify some expected summary fields are present
        threshold_keys = set(service._thresholds.keys())
        assert any("temp" in k for k in threshold_keys)
        assert any("wind" in k for k in threshold_keys)
        assert any("gust" in k for k in threshold_keys)

    def test_no_alerts_means_empty_thresholds(self) -> None:
        """If all alert_enabled=False, change detection has no thresholds."""
        from services.weather_change_detection import WeatherChangeDetectionService

        dc = build_default_display_config()
        new_metrics = [
            MetricConfig(
                metric_id=mc.metric_id, enabled=mc.enabled,
                aggregations=mc.aggregations,
                alert_enabled=False,
            )
            for mc in dc.metrics
        ]
        dc_no_alerts = UnifiedWeatherDisplayConfig(
            trip_id="test", metrics=new_metrics,
            show_night_block=dc.show_night_block,
            night_interval_hours=dc.night_interval_hours,
            thunder_forecast_days=dc.thunder_forecast_days,
        )
        service = WeatherChangeDetectionService.from_display_config(dc_no_alerts)
        assert len(service._thresholds) == 0
