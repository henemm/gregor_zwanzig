"""
TDD RED tests for weather-metrics-ux feature.

SPEC: docs/specs/modules/weather_metrics_ux.md v1.0

Tests verify:
1. col_label values updated in MetricCatalog (13 changes)
2. _fmt_val() level-based formatting for cloud/cape/visibility
3. Config UI shows col_label next to German label (checked via get_col_defs)
"""
import pytest

from app.metric_catalog import get_metric, get_col_defs


# ============================================================
# Change 1: col_label updates (13 metrics)
# ============================================================

class TestColLabelUpdates:
    """Verify all 13 col_label values have been updated."""

    def test_wind_chill_label_feels(self):
        m = get_metric("wind_chill")
        assert m.col_label == "Feels", f"Expected 'Feels', got '{m.col_label}'"

    def test_thunder_label_thunder(self):
        m = get_metric("thunder")
        assert m.col_label == "Thunder", f"Expected 'Thunder', got '{m.col_label}'"

    def test_snowfall_limit_label_snowl(self):
        m = get_metric("snowfall_limit")
        assert m.col_label == "SnowL", f"Expected 'SnowL', got '{m.col_label}'"

    def test_cloud_total_label_cloud(self):
        m = get_metric("cloud_total")
        assert m.col_label == "Cloud", f"Expected 'Cloud', got '{m.col_label}'"

    def test_cloud_low_label_cldlow(self):
        m = get_metric("cloud_low")
        assert m.col_label == "CldLow", f"Expected 'CldLow', got '{m.col_label}'"

    def test_cloud_mid_label_cldmid(self):
        m = get_metric("cloud_mid")
        assert m.col_label == "CldMid", f"Expected 'CldMid', got '{m.col_label}'"

    def test_cloud_high_label_cldhi(self):
        m = get_metric("cloud_high")
        assert m.col_label == "CldHi", f"Expected 'CldHi', got '{m.col_label}'"

    def test_dewpoint_label_cond(self):
        m = get_metric("dewpoint")
        assert m.col_label == "Cond°", f"Expected 'Cond°', got '{m.col_label}'"

    def test_visibility_label_visib(self):
        m = get_metric("visibility")
        assert m.col_label == "Visib", f"Expected 'Visib', got '{m.col_label}'"

    def test_rain_probability_label_rain_pct(self):
        m = get_metric("rain_probability")
        assert m.col_label == "Rain%", f"Expected 'Rain%', got '{m.col_label}'"

    def test_cape_label_thndr_pct(self):
        m = get_metric("cape")
        assert m.col_label == "Thndr%", f"Expected 'Thndr%', got '{m.col_label}'"

    def test_freezing_level_label_zeroline(self):
        m = get_metric("freezing_level")
        assert m.col_label == "0°Line", f"Expected '0°Line', got '{m.col_label}'"

    def test_snow_depth_label_snowh(self):
        m = get_metric("snow_depth")
        assert m.col_label == "SnowH", f"Expected 'SnowH', got '{m.col_label}'"

    def test_unchanged_labels_still_correct(self):
        """Verify unchanged labels haven't been accidentally modified."""
        assert get_metric("temperature").col_label == "Temp"
        assert get_metric("wind").col_label == "Wind"
        assert get_metric("gust").col_label == "Gust"
        assert get_metric("precipitation").col_label == "Rain"
        assert get_metric("humidity").col_label == "Humid"
        assert get_metric("pressure").col_label == "hPa"

    def test_col_defs_contain_new_labels(self):
        """get_col_defs() should return the new labels."""
        col_defs = get_col_defs()
        labels = {cd[0]: cd[1] for cd in col_defs}
        assert labels["felt"] == "Feels"
        assert labels["thunder"] == "Thunder"
        assert labels["cloud"] == "Cloud"
        assert labels["pop"] == "Rain%"
        assert labels["cape"] == "Thndr%"
        assert labels["freeze_lvl"] == "0°Line"


# ============================================================
# Change 2: Level-based formatting in _fmt_val()
# ============================================================

class TestCloudEmojiFormatting:
    """Cloud metrics should show emoji based on percentage."""

    @pytest.fixture()
    def formatter(self):
        from formatters.trip_report import TripReportFormatter
        return TripReportFormatter()

    # --- Plain text: emoji only ---

    def test_cloud_clear_plain(self, formatter):
        """0-10% → ☀️"""
        result = formatter._fmt_val("cloud", 5, html=False)
        assert "☀️" in result

    def test_cloud_partly_plain(self, formatter):
        """11-30% → 🌤️"""
        result = formatter._fmt_val("cloud", 25, html=False)
        assert "🌤️" in result

    def test_cloud_half_plain(self, formatter):
        """31-70% → ⛅"""
        result = formatter._fmt_val("cloud", 50, html=False)
        assert "⛅" in result

    def test_cloud_mostly_plain(self, formatter):
        """71-90% → 🌥️"""
        result = formatter._fmt_val("cloud", 85, html=False)
        assert "🌥️" in result

    def test_cloud_overcast_plain(self, formatter):
        """91-100% → ☁️"""
        result = formatter._fmt_val("cloud", 95, html=False)
        assert "☁️" in result

    # --- HTML: emoji + percentage ---

    def test_cloud_html_has_emoji_and_value(self, formatter):
        """HTML should show emoji AND percentage."""
        result = formatter._fmt_val("cloud", 25, html=True)
        assert "🌤️" in result
        assert "25" in result

    # --- Boundary values ---

    def test_cloud_boundary_10_is_clear(self, formatter):
        result = formatter._fmt_val("cloud", 10, html=False)
        assert "☀️" in result

    def test_cloud_boundary_11_is_partly(self, formatter):
        result = formatter._fmt_val("cloud", 11, html=False)
        assert "🌤️" in result

    def test_cloud_boundary_70_is_half(self, formatter):
        result = formatter._fmt_val("cloud", 70, html=False)
        assert "⛅" in result

    def test_cloud_boundary_91_is_overcast(self, formatter):
        result = formatter._fmt_val("cloud", 91, html=False)
        assert "☁️" in result

    # --- Cloud sub-types also work ---

    def test_cloud_low_emoji(self, formatter):
        result = formatter._fmt_val("cloud_low", 50, html=False)
        assert "⛅" in result

    def test_cloud_mid_emoji(self, formatter):
        result = formatter._fmt_val("cloud_mid", 5, html=False)
        assert "☀️" in result

    def test_cloud_high_emoji(self, formatter):
        result = formatter._fmt_val("cloud_high", 95, html=False)
        assert "☁️" in result

    def test_cloud_none_returns_dash(self, formatter):
        result = formatter._fmt_val("cloud", None, html=False)
        assert result == "–"


class TestCapeEmojiFormatting:
    """CAPE should show level emoji based on J/kg value."""

    @pytest.fixture()
    def formatter(self):
        from formatters.trip_report import TripReportFormatter
        return TripReportFormatter()

    # --- Plain text: emoji only ---

    def test_cape_low_plain(self, formatter):
        """0-300 J/kg → 🟢"""
        result = formatter._fmt_val("cape", 200, html=False)
        assert "🟢" in result

    def test_cape_moderate_plain(self, formatter):
        """301-1000 J/kg → 🟡"""
        result = formatter._fmt_val("cape", 800, html=False)
        assert "🟡" in result

    def test_cape_high_plain(self, formatter):
        """1001-2000 J/kg → 🟠"""
        result = formatter._fmt_val("cape", 1500, html=False)
        assert "🟠" in result

    def test_cape_extreme_plain(self, formatter):
        """>2000 J/kg → 🔴"""
        result = formatter._fmt_val("cape", 2500, html=False)
        assert "🔴" in result

    # --- HTML: emoji + value ---

    def test_cape_html_has_emoji_and_value(self, formatter):
        result = formatter._fmt_val("cape", 800, html=True)
        assert "🟡" in result
        assert "800" in result

    # --- Boundary values ---

    def test_cape_boundary_300_is_low(self, formatter):
        """Exactly 300 → 🟢 (spec says 0-300)"""
        result = formatter._fmt_val("cape", 300, html=False)
        assert "🟢" in result

    def test_cape_boundary_301_is_moderate(self, formatter):
        result = formatter._fmt_val("cape", 301, html=False)
        assert "🟡" in result

    def test_cape_none_returns_dash(self, formatter):
        result = formatter._fmt_val("cape", None, html=False)
        assert result == "–"


class TestVisibilityLevelFormatting:
    """Visibility should show text levels instead of raw values."""

    @pytest.fixture()
    def formatter(self):
        from formatters.trip_report import TripReportFormatter
        return TripReportFormatter()

    def test_visibility_good(self, formatter):
        """>10km → good"""
        result = formatter._fmt_val("visibility", 12000, html=False)
        assert result == "good"

    def test_visibility_fair(self, formatter):
        """4-10km → fair"""
        result = formatter._fmt_val("visibility", 5000, html=False)
        assert result == "fair"

    def test_visibility_poor(self, formatter):
        """1-4km → poor"""
        result = formatter._fmt_val("visibility", 2000, html=False)
        assert result == "poor"

    def test_visibility_fog(self, formatter):
        """<1km → ⚠️ fog"""
        result = formatter._fmt_val("visibility", 500, html=False)
        assert "fog" in result

    def test_visibility_html_same_as_plain(self, formatter):
        """HTML and plain-text should be the same for visibility levels."""
        plain = formatter._fmt_val("visibility", 5000, html=False)
        html = formatter._fmt_val("visibility", 5000, html=True)
        assert plain == html

    # --- Boundary values ---

    def test_visibility_boundary_10000_is_good(self, formatter):
        result = formatter._fmt_val("visibility", 10000, html=False)
        assert result == "good"

    def test_visibility_boundary_4000_is_fair(self, formatter):
        result = formatter._fmt_val("visibility", 4000, html=False)
        assert result == "fair"

    def test_visibility_boundary_1000_is_poor(self, formatter):
        result = formatter._fmt_val("visibility", 1000, html=False)
        assert result == "poor"

    def test_visibility_none_returns_dash(self, formatter):
        result = formatter._fmt_val("visibility", None, html=False)
        assert result == "–"
