"""
RISK-04: Configurable Display & Risk Thresholds
TDD RED - Tests for catalog-driven thresholds in MetricCatalog + TripReportFormatter.

All tests use REAL MetricCatalog and TripReportFormatter instances (no mocks!).
"""

import pytest
from app.metric_catalog import get_metric, MetricDefinition


# =====================================================================
# Part 1: MetricCatalog threshold fields exist
# =====================================================================


class TestMetricDefinitionFields:
    """MetricDefinition must have three new threshold fields."""

    def test_display_thresholds_field_exists(self) -> None:
        """MetricDefinition must have a display_thresholds dict field."""
        md = get_metric("gust")
        assert hasattr(md, "display_thresholds"), "display_thresholds field missing"
        assert isinstance(md.display_thresholds, dict)

    def test_highlight_threshold_field_exists(self) -> None:
        """MetricDefinition must have a highlight_threshold Optional[float] field."""
        md = get_metric("gust")
        assert hasattr(md, "highlight_threshold"), "highlight_threshold field missing"

    def test_risk_thresholds_field_exists(self) -> None:
        """MetricDefinition must have a risk_thresholds dict field."""
        md = get_metric("gust")
        assert hasattr(md, "risk_thresholds"), "risk_thresholds field missing"
        assert isinstance(md.risk_thresholds, dict)


# =====================================================================
# Part 2: Catalog populated with correct threshold values
# =====================================================================


class TestCatalogPopulation:
    """Threshold values must match previously hardcoded values exactly."""

    def test_gust_display_thresholds(self) -> None:
        """Gust: yellow >= 50, red >= 80."""
        md = get_metric("gust")
        assert md.display_thresholds == {"yellow": 50.0, "red": 80.0}

    def test_gust_highlight_threshold(self) -> None:
        """Gust highlight at > 60 km/h."""
        md = get_metric("gust")
        assert md.highlight_threshold == 60.0

    def test_gust_risk_thresholds(self) -> None:
        """Gust risk: medium > 50, high > 70."""
        md = get_metric("gust")
        assert md.risk_thresholds == {"medium": 50.0, "high": 70.0}

    def test_wind_highlight_threshold(self) -> None:
        """Wind highlight at > 50 km/h."""
        md = get_metric("wind")
        assert md.highlight_threshold == 50.0

    def test_wind_risk_thresholds(self) -> None:
        """Wind risk: medium > 50, high > 70."""
        md = get_metric("wind")
        assert md.risk_thresholds == {"medium": 50.0, "high": 70.0}

    def test_precipitation_display_thresholds(self) -> None:
        """Precipitation: blue >= 5 mm."""
        md = get_metric("precipitation")
        assert md.display_thresholds == {"blue": 5.0}

    def test_precipitation_risk_thresholds(self) -> None:
        """Precipitation risk: medium > 20 mm."""
        md = get_metric("precipitation")
        assert md.risk_thresholds == {"medium": 20.0}

    def test_rain_probability_display_thresholds(self) -> None:
        """Rain probability: blue >= 80%."""
        md = get_metric("rain_probability")
        assert md.display_thresholds == {"blue": 80.0}

    def test_rain_probability_highlight(self) -> None:
        """Rain probability highlight at >= 80%."""
        md = get_metric("rain_probability")
        assert md.highlight_threshold == 80.0

    def test_cape_display_thresholds(self) -> None:
        """CAPE: yellow >= 1000 J/kg."""
        md = get_metric("cape")
        assert md.display_thresholds == {"yellow": 1000.0}

    def test_cape_risk_thresholds(self) -> None:
        """CAPE risk: medium >= 1000, high >= 2000."""
        md = get_metric("cape")
        assert md.risk_thresholds == {"medium": 1000.0, "high": 2000.0}

    def test_visibility_display_thresholds(self) -> None:
        """Visibility: orange if < 500m (less-than condition)."""
        md = get_metric("visibility")
        assert md.display_thresholds == {"orange_lt": 500.0}

    def test_visibility_risk_thresholds(self) -> None:
        """Visibility risk: high if < 100m."""
        md = get_metric("visibility")
        assert md.risk_thresholds == {"high_lt": 100.0}

    def test_wind_chill_risk_thresholds(self) -> None:
        """Wind chill risk: high if < -20 C."""
        md = get_metric("wind_chill")
        assert md.risk_thresholds == {"high_lt": -20.0}

    def test_metrics_without_thresholds_have_empty_dicts(self) -> None:
        """Metrics not in threshold list should have empty defaults."""
        md = get_metric("temperature")
        assert md.display_thresholds == {}
        assert md.risk_thresholds == {}
        assert md.highlight_threshold is None


# =====================================================================
# Part 3: _fmt_val() backward compatibility (same output as before)
# =====================================================================


class TestFmtValCatalogThresholds:
    """_fmt_val() must produce same output as before (thresholds from catalog now)."""

    def _get_formatter(self):
        from formatters.trip_report import TripReportFormatter
        return TripReportFormatter()

    def test_gust_yellow_background(self) -> None:
        """Gust 55 km/h -> yellow background in HTML."""
        fmt = self._get_formatter()
        result = fmt._fmt_val("gust", 55.0, html=True)
        assert "background:#fff9c4" in result

    def test_gust_red_background(self) -> None:
        """Gust 85 km/h -> red background in HTML."""
        fmt = self._get_formatter()
        result = fmt._fmt_val("gust", 85.0, html=True)
        assert "background:#ffebee" in result

    def test_gust_no_highlight_below_threshold(self) -> None:
        """Gust 40 km/h -> no background color."""
        fmt = self._get_formatter()
        result = fmt._fmt_val("gust", 40.0, html=True)
        assert "background" not in result
        assert result == "40"

    def test_precip_blue_background(self) -> None:
        """Precip 6 mm -> blue background."""
        fmt = self._get_formatter()
        result = fmt._fmt_val("precip", 6.0, html=True)
        assert "background:#e3f2fd" in result

    def test_pop_blue_background(self) -> None:
        """POP 85% -> blue background."""
        fmt = self._get_formatter()
        result = fmt._fmt_val("pop", 85.0, html=True)
        assert "background:#e3f2fd" in result

    def test_cape_yellow_background_numeric(self) -> None:
        """CAPE 1500 J/kg numeric -> yellow background."""
        fmt = self._get_formatter()
        fmt._friendly_keys = set()
        result = fmt._fmt_val("cape", 1500.0, html=True)
        assert "background:#fff9c4" in result

    def test_visibility_orange_background(self) -> None:
        """Visibility 450m -> orange background."""
        fmt = self._get_formatter()
        fmt._friendly_keys = set()
        result = fmt._fmt_val("visibility", 450.0, html=True)
        assert "background:#fff3e0" in result

    def test_cape_emoji_hardcoded(self) -> None:
        """CAPE 1500 friendly -> orange emoji (stays hardcoded)."""
        fmt = self._get_formatter()
        fmt._friendly_keys = {"cape"}
        result = fmt._fmt_val("cape", 1500.0, html=False)
        assert result == "\U0001f7e0"

    def test_cloud_emoji_hardcoded(self) -> None:
        """Cloud 35% friendly -> partly cloudy emoji (stays hardcoded)."""
        fmt = self._get_formatter()
        fmt._friendly_keys = {"cloud"}
        result = fmt._fmt_val("cloud", 35.0, html=False)
        assert result == "\u26c5"
