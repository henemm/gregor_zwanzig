"""
Spec Tests for WeatherMetricsService.

These tests verify that the implementation matches the spec.
SPEC: docs/specs/modules/weather_metrics.md
SPEC: docs/specs/compare_email.md (Wolkenlage rules)

Run with: uv run pytest tests/spec/test_weather_metrics_spec.py -v
"""
import pytest

from services.weather_metrics import CloudStatus, WeatherMetricsService


class TestCloudStatusSpec:
    """
    Tests against docs/specs/compare_email.md Zeile 212-216.

    Wolkenlage-Werte:
    - elevation >= 2500m AND cloud_low > 30% AND sunny >= 5h: "ueber Wolken"
    - sunny >= 75% of time_window: "klar"
    - sunny >= 25% of time_window: "leicht"
    - Otherwise: "in Wolken"
    """

    def test_above_clouds_high_elevation_with_low_clouds(self):
        """High elevation (3000m) above low clouds (50%) with good sunshine (6h)."""
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=6,
            time_window_hours=8,
            elevation_m=3000,
            cloud_low_avg=50,
        )
        assert status == CloudStatus.ABOVE_CLOUDS

    def test_above_clouds_requires_high_elevation(self):
        """Low elevation should not get ABOVE_CLOUDS even with low clouds."""
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=6,
            time_window_hours=8,
            elevation_m=2000,  # Below threshold
            cloud_low_avg=50,
        )
        assert status != CloudStatus.ABOVE_CLOUDS
        assert status == CloudStatus.CLEAR  # 6/8 = 75%

    def test_above_clouds_requires_low_clouds(self):
        """High elevation without low clouds should get CLEAR, not ABOVE_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=6,
            time_window_hours=8,
            elevation_m=3000,
            cloud_low_avg=20,  # Below threshold
        )
        assert status != CloudStatus.ABOVE_CLOUDS
        assert status == CloudStatus.CLEAR

    def test_above_clouds_requires_min_sunshine(self):
        """High elevation needs at least 5h sunshine for ABOVE_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=4,  # Below 5h threshold
            time_window_hours=8,
            elevation_m=3000,
            cloud_low_avg=50,
        )
        assert status != CloudStatus.ABOVE_CLOUDS
        assert status == CloudStatus.LIGHT  # 4/8 = 50%

    def test_clear_75_percent_sunshine(self):
        """75% or more sunshine hours -> CLEAR."""
        # Exactly 75%: 6/8 = 0.75
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=6,
            time_window_hours=8,
            elevation_m=2000,
            cloud_low_avg=10,
        )
        assert status == CloudStatus.CLEAR

    def test_clear_above_75_percent(self):
        """Above 75% sunshine -> CLEAR."""
        # 7/8 = 87.5%
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=7,
            time_window_hours=8,
            elevation_m=2000,
            cloud_low_avg=10,
        )
        assert status == CloudStatus.CLEAR

    def test_light_25_to_75_percent(self):
        """25% to 75% sunshine -> LIGHT."""
        # 3/8 = 37.5%
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=3,
            time_window_hours=8,
            elevation_m=2000,
            cloud_low_avg=30,
        )
        assert status == CloudStatus.LIGHT

    def test_light_exactly_25_percent(self):
        """Exactly 25% sunshine -> LIGHT."""
        # 2/8 = 25%
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=2,
            time_window_hours=8,
            elevation_m=2000,
            cloud_low_avg=30,
        )
        assert status == CloudStatus.LIGHT

    def test_in_clouds_below_25_percent(self):
        """Less than 25% sunshine -> IN_CLOUDS."""
        # 1/8 = 12.5%
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=1,
            time_window_hours=8,
            elevation_m=2000,
            cloud_low_avg=60,
        )
        assert status == CloudStatus.IN_CLOUDS

    def test_in_clouds_zero_sunshine(self):
        """Zero sunshine -> IN_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=0,
            time_window_hours=8,
            elevation_m=2000,
            cloud_low_avg=80,
        )
        assert status == CloudStatus.IN_CLOUDS

    def test_in_clouds_none_sunshine(self):
        """None sunshine hours -> IN_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            sunny_hours=None,
            time_window_hours=8,
            elevation_m=2000,
            cloud_low_avg=50,
        )
        assert status == CloudStatus.IN_CLOUDS


class TestEffectiveCloudSpec:
    """
    Tests against docs/specs/compare_email.md Zeile 134-150.

    High elevations (>= 2500m) ignore low clouds.
    """

    def test_high_elevation_ignores_low_clouds(self):
        """At 3000m, only mid + high clouds matter."""
        eff = WeatherMetricsService.calculate_effective_cloud(
            elevation_m=3000,
            cloud_total_pct=80,  # High because of low clouds
            cloud_mid_pct=10,
            cloud_high_pct=20,
        )
        # Should be (10 + 20) / 2 = 15
        assert eff == 15

    def test_low_elevation_uses_total(self):
        """At 2000m, total cloud cover is used."""
        eff = WeatherMetricsService.calculate_effective_cloud(
            elevation_m=2000,
            cloud_total_pct=80,
            cloud_mid_pct=10,
            cloud_high_pct=20,
        )
        assert eff == 80

    def test_threshold_elevation_uses_effective(self):
        """At exactly 2500m, effective cloud calculation applies."""
        eff = WeatherMetricsService.calculate_effective_cloud(
            elevation_m=2500,
            cloud_total_pct=80,
            cloud_mid_pct=10,
            cloud_high_pct=20,
        )
        assert eff == 15

    def test_missing_layer_data_uses_total(self):
        """If mid/high data missing, use total even at high elevation."""
        eff = WeatherMetricsService.calculate_effective_cloud(
            elevation_m=3000,
            cloud_total_pct=80,
            cloud_mid_pct=None,  # Missing
            cloud_high_pct=20,
        )
        assert eff == 80


class TestWeatherSymbolSpec:
    """Tests for weather symbol generation."""

    def test_precipitation_snow(self):
        """Precipitation + cold temp -> snow symbol."""
        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=80,
            precip_mm=2.0,
            temp_c=-5,
        )
        assert symbol == "❄️"

    def test_precipitation_rain(self):
        """Precipitation + warm temp -> rain symbol."""
        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=80,
            precip_mm=2.0,
            temp_c=5,
        )
        assert symbol == "🌧️"

    def test_sunny_low_clouds(self):
        """Low cloud cover -> sunny symbol."""
        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=10,
            precip_mm=0,
            temp_c=5,
        )
        assert symbol == "☀️"

    def test_partly_cloudy(self):
        """20-50% clouds -> partly cloudy."""
        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=35,
            precip_mm=0,
            temp_c=5,
        )
        assert symbol == "⛅"

    def test_mostly_cloudy(self):
        """50-80% clouds -> mostly cloudy."""
        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=65,
            precip_mm=0,
            temp_c=5,
        )
        assert symbol == "🌥️"

    def test_overcast(self):
        """80%+ clouds -> overcast."""
        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=90,
            precip_mm=0,
            temp_c=5,
        )
        assert symbol == "☁️"

    def test_high_elevation_sunny_above_clouds(self):
        """High elevation with low clouds below -> sunny (effective cloud low)."""
        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=80,  # High total because of low clouds
            precip_mm=0,
            temp_c=-5,
            elevation_m=3000,
            cloud_mid_pct=5,
            cloud_high_pct=5,
        )
        # Effective = (5 + 5) / 2 = 5% -> sunny
        assert symbol == "☀️"


class TestCloudStatusFormatting:
    """Tests for CloudStatus formatting."""

    def test_above_clouds_emoji(self):
        """ABOVE_CLOUDS has sun emoji."""
        emoji = WeatherMetricsService.get_cloud_status_emoji(CloudStatus.ABOVE_CLOUDS)
        assert emoji == "☀️"

    def test_clear_emoji(self):
        """CLEAR has sparkle emoji."""
        emoji = WeatherMetricsService.get_cloud_status_emoji(CloudStatus.CLEAR)
        assert emoji == "✨"

    def test_light_emoji(self):
        """LIGHT has sun behind cloud emoji."""
        emoji = WeatherMetricsService.get_cloud_status_emoji(CloudStatus.LIGHT)
        assert emoji == "🌤️"

    def test_in_clouds_emoji(self):
        """IN_CLOUDS has cloud emoji."""
        emoji = WeatherMetricsService.get_cloud_status_emoji(CloudStatus.IN_CLOUDS)
        assert emoji == "☁️"

    def test_format_includes_style(self):
        """format_cloud_status returns text and CSS style."""
        text, style = WeatherMetricsService.format_cloud_status(CloudStatus.CLEAR)
        assert "klar" in text
        assert "color:" in style or style == ""


class TestSunnyHoursSpec:
    """
    Tests for sunny hours calculation from cloud cover.

    SPEC: docs/specs/modules/weather_metrics.md
    Formula: sunshine_pct = 100 - effective_cloud_pct
    Sum all percentages, divide by 100 = hours.
    """

    def test_clear_sky_full_sunshine(self):
        """0% clouds = 1h sunshine per hour."""
        from datetime import datetime
        from app.models import ForecastDataPoint

        data = [
            ForecastDataPoint(ts=datetime(2025, 1, 1, 9, 0), cloud_total_pct=0),
            ForecastDataPoint(ts=datetime(2025, 1, 1, 10, 0), cloud_total_pct=0),
        ]
        result = WeatherMetricsService.calculate_sunny_hours(data)
        assert result == 2  # 2 * 100% = 200% = 2h

    def test_overcast_zero_sunshine(self):
        """100% clouds = 0h sunshine."""
        from datetime import datetime
        from app.models import ForecastDataPoint

        data = [
            ForecastDataPoint(ts=datetime(2025, 1, 1, 9, 0), cloud_total_pct=100),
            ForecastDataPoint(ts=datetime(2025, 1, 1, 10, 0), cloud_total_pct=100),
        ]
        result = WeatherMetricsService.calculate_sunny_hours(data)
        assert result == 0  # 2 * 0% = 0% = 0h

    def test_partial_clouds_proportional(self):
        """30% clouds = 70% sunshine per hour."""
        from datetime import datetime
        from app.models import ForecastDataPoint

        data = [
            ForecastDataPoint(ts=datetime(2025, 1, 1, 9, 0), cloud_total_pct=30),
            ForecastDataPoint(ts=datetime(2025, 1, 1, 10, 0), cloud_total_pct=30),
            ForecastDataPoint(ts=datetime(2025, 1, 1, 11, 0), cloud_total_pct=30),
        ]
        result = WeatherMetricsService.calculate_sunny_hours(data)
        # 3 * 70% = 210% = 2.1h -> rounded = 2h
        assert result == 2

    def test_mixed_conditions(self):
        """Mixed cloud conditions sum correctly."""
        from datetime import datetime
        from app.models import ForecastDataPoint

        data = [
            ForecastDataPoint(ts=datetime(2025, 1, 1, 9, 0), cloud_total_pct=0),    # 100%
            ForecastDataPoint(ts=datetime(2025, 1, 1, 10, 0), cloud_total_pct=50),  # 50%
            ForecastDataPoint(ts=datetime(2025, 1, 1, 11, 0), cloud_total_pct=100), # 0%
            ForecastDataPoint(ts=datetime(2025, 1, 1, 12, 0), cloud_total_pct=20),  # 80%
        ]
        result = WeatherMetricsService.calculate_sunny_hours(data)
        # 100 + 50 + 0 + 80 = 230% = 2.3h -> rounded = 2h
        assert result == 2

    def test_high_elevation_ignores_low_clouds(self):
        """High elevation uses effective cloud (ignores low clouds)."""
        from datetime import datetime
        from app.models import ForecastDataPoint

        data = [
            ForecastDataPoint(
                ts=datetime(2025, 1, 1, 9, 0),
                cloud_total_pct=80,  # High total (low clouds)
                cloud_mid_pct=10,
                cloud_high_pct=10,
            ),
        ]
        result = WeatherMetricsService.calculate_sunny_hours(data, elevation_m=3000)
        # Effective: (10 + 10) / 2 = 10% -> 90% sunshine -> 0.9h -> rounded = 1h
        assert result == 1

    def test_low_elevation_uses_total_cloud(self):
        """Low elevation uses total cloud cover."""
        from datetime import datetime
        from app.models import ForecastDataPoint

        data = [
            ForecastDataPoint(
                ts=datetime(2025, 1, 1, 9, 0),
                cloud_total_pct=80,  # High total
                cloud_mid_pct=10,
                cloud_high_pct=10,
            ),
        ]
        result = WeatherMetricsService.calculate_sunny_hours(data, elevation_m=1500)
        # Uses total: 80% clouds -> 20% sunshine -> 0.2h -> rounded = 0h
        assert result == 0

    def test_empty_data_returns_zero(self):
        """Empty data list returns 0 hours."""
        result = WeatherMetricsService.calculate_sunny_hours([])
        assert result == 0

    def test_none_cloud_data_skipped(self):
        """Hours with None cloud data are skipped."""
        from datetime import datetime
        from app.models import ForecastDataPoint

        data = [
            ForecastDataPoint(ts=datetime(2025, 1, 1, 9, 0), cloud_total_pct=0),     # 100%
            ForecastDataPoint(ts=datetime(2025, 1, 1, 10, 0), cloud_total_pct=None), # skipped
            ForecastDataPoint(ts=datetime(2025, 1, 1, 11, 0), cloud_total_pct=0),    # 100%
        ]
        result = WeatherMetricsService.calculate_sunny_hours(data)
        # Only 2 valid hours: 2 * 100% = 200% = 2h
        assert result == 2
