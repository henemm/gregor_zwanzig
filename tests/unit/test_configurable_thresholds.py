"""
RISK-04: Configurable Display & Risk Thresholds
TDD RED - Tests for catalog-driven thresholds in MetricCatalog + TripReportFormatter.

All tests use REAL MetricCatalog and TripReportFormatter instances (no mocks!).
"""

from app.metric_catalog import get_metric


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
        """Gust: yellow >= 50, orange >= 65, red >= 80 (4-stufige Ampel seit #759)."""
        md = get_metric("gust")
        assert md.display_thresholds == {"yellow": 50.0, "orange": 65.0, "red": 80.0}

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
        """Precipitation: yellow >= 1, orange >= 5, red >= 10 (4-stufige Ampel seit #759)."""
        md = get_metric("precipitation")
        assert md.display_thresholds == {"yellow": 1.0, "orange": 5.0, "red": 10.0}

    def test_precipitation_risk_thresholds(self) -> None:
        """Precipitation risk: medium > 20 mm."""
        md = get_metric("precipitation")
        assert md.risk_thresholds == {"medium": 20.0}

    def test_rain_probability_display_thresholds(self) -> None:
        """Rain probability: yellow >= 30, orange >= 60, red >= 80 (4-stufige Ampel seit #759)."""
        md = get_metric("rain_probability")
        assert md.display_thresholds == {"yellow": 30.0, "orange": 60.0, "red": 80.0}

    def test_rain_probability_highlight(self) -> None:
        """Rain probability highlight at >= 80%."""
        md = get_metric("rain_probability")
        assert md.highlight_threshold == 80.0

    def test_cape_display_thresholds(self) -> None:
        """CAPE: 4-stufige Ampel yellow/orange/red — Berg-Kalibrierung (Workflow
        fix-briefing-grid-and-summary): Berg-Gewitter triggern orographisch bei
        deutlich niedrigerem CAPE als die vormalige Flachland-Konvektionsskala
        (yellow:1000/orange:2500/red:3500, Issue #814 AC-4), die deshalb im
        Gebirgs-Kontext dauergrün zeigte."""
        md = get_metric("cape")
        assert md.display_thresholds == {"yellow": 300.0, "orange": 800.0, "red": 1500.0}

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
# Part 3: fmt_val() backward compatibility (same output as before)
#
# Issue #1214 Scheibe 4 (#778): TestFmtValCatalogThresholds testete
# ausschliesslich TripReportFormatter._fmt_val (tot). Triage:
# - Gust/Precip/Pop-Highlight aus Katalog-Schwellen: Duplikat \u2014 bereits
#   vollstaendig gegen den lebendigen 4-stufigen CSS-Dot-Pfad getestet in
#   tests/tdd/test_issue_759_email_ampel.py (u.a. gust 40/55/70/85 \u2192
#   green/yellow/orange/red, precip 0/1/5/10, pop 0/30/60/80).
# - CAPE-/Visibility-Roh-HTML-Hintergrund: dead-only 2-Stufen-Highlight,
#   vom lebendigen Pfad widerlegt (tests/tdd/test_issue_811_mode_matrix.py
#   ::test_cape_roh_html_no_yellow_span / ::test_visibility_roh_html_no_inline_style
#   zeigen explizit KEIN Highlight im Roh-Modus, #814 AC-5).
# - CAPE-Friendly-Emoji "\U0001f7e0": bereits VOR #1222 veraltet (die tote
#   Kopie liefert seit #1222 einen CSS-Dot, keinen Kreis-Emoji mehr) \u2014
#   dead-only und schon vor dieser Scheibe strukturell falsch.
# - Cloud-Friendly-Emoji: Duplikat \u2014 bereits gegen helpers.fmt_val portiert
#   in tests/unit/test_weather_metrics_ux.py::TestCloudEmojiFormatting.
# Kein Aequivalent zu portieren.
# =====================================================================
