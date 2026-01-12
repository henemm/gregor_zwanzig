"""
Spec Tests for WeatherMetricsService.

These tests verify that the implementation matches the spec.
SPEC: docs/specs/modules/weather_metrics.md
SPEC: docs/specs/cloud_layer_refactor.md (Cloud Layer rules)

Run with: uv run pytest tests/spec/test_weather_metrics_spec.py -v
"""
import pytest

from services.weather_metrics import CloudStatus, WeatherMetricsService


class TestCloudStatusSpec:
    """
    Tests against docs/specs/cloud_layer_refactor.md.

    Cloud Layer uses elevation tiers + relevant cloud layer:

    Tier 1: Glacier (>= 3000m) - in mid-cloud zone
    - cloud_mid > 50% -> IN_CLOUDS
    - cloud_low > 20% AND cloud_mid <= 30% -> ABOVE_CLOUDS
    - otherwise -> NONE

    Tier 2: Alpine (2000-3000m) - top of low-cloud zone
    - cloud_low > 50% -> IN_CLOUDS
    - otherwise -> NONE

    Tier 3: Valley (< 2000m) - in low-cloud zone
    - cloud_low > 60% -> IN_CLOUDS
    - otherwise -> NONE
    """

    # --- Tier 1: Glacier level (>= 3000m) ---

    def test_glacier_above_clouds_low_clouds_clear_mid(self):
        """Glacier (3200m) with low clouds below and clear mid -> ABOVE_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=3200,
            cloud_low_pct=40,
            cloud_mid_pct=10,
        )
        assert status == CloudStatus.ABOVE_CLOUDS

    def test_glacier_in_mid_clouds(self):
        """Glacier (3200m) with high mid clouds -> IN_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=3200,
            cloud_low_pct=40,
            cloud_mid_pct=60,  # In mid-level clouds
        )
        assert status == CloudStatus.IN_CLOUDS

    def test_glacier_clear_sky(self):
        """Glacier (3200m) with clear sky -> NONE."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=3200,
            cloud_low_pct=5,
            cloud_mid_pct=5,
        )
        assert status == CloudStatus.NONE

    def test_glacier_requires_low_clouds_for_above(self):
        """Glacier needs low clouds > 20% to show ABOVE_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=3200,
            cloud_low_pct=20,  # At threshold, not above
            cloud_mid_pct=10,
        )
        assert status == CloudStatus.NONE

    def test_glacier_mid_clouds_at_threshold(self):
        """Glacier with mid clouds at 30% threshold -> can still be ABOVE_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=3200,
            cloud_low_pct=40,
            cloud_mid_pct=30,  # At threshold
        )
        assert status == CloudStatus.ABOVE_CLOUDS

    def test_glacier_mid_clouds_above_threshold_blocks_above(self):
        """Glacier with mid clouds > 30% but < 50% -> NONE (not clear, not in clouds)."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=3200,
            cloud_low_pct=40,
            cloud_mid_pct=40,  # Above 30% but below 50%
        )
        assert status == CloudStatus.NONE

    # --- Tier 2: Alpine level (2000-3000m) ---

    def test_alpine_in_clouds(self):
        """Alpine (2500m) with high low clouds -> IN_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=2500,
            cloud_low_pct=60,
            cloud_mid_pct=10,
        )
        assert status == CloudStatus.IN_CLOUDS

    def test_alpine_moderate_clouds(self):
        """Alpine (2500m) with moderate low clouds -> NONE."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=2500,
            cloud_low_pct=50,  # At threshold, not above
            cloud_mid_pct=10,
        )
        assert status == CloudStatus.NONE

    def test_alpine_clear(self):
        """Alpine (2200m) with clear sky -> NONE."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=2200,
            cloud_low_pct=20,
            cloud_mid_pct=5,
        )
        assert status == CloudStatus.NONE

    # --- Tier 3: Valley level (< 2000m) ---

    def test_valley_in_clouds(self):
        """Valley (1500m) with high low clouds -> IN_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=1500,
            cloud_low_pct=70,
            cloud_mid_pct=5,
        )
        assert status == CloudStatus.IN_CLOUDS

    def test_valley_moderate_clouds(self):
        """Valley (1500m) with moderate low clouds -> NONE."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=1500,
            cloud_low_pct=60,  # At threshold, not above
            cloud_mid_pct=5,
        )
        assert status == CloudStatus.NONE

    def test_valley_clear(self):
        """Valley (1000m) with clear sky -> NONE."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=1000,
            cloud_low_pct=20,
            cloud_mid_pct=5,
        )
        assert status == CloudStatus.NONE

    # --- Edge cases ---

    def test_none_missing_elevation(self):
        """Missing elevation -> NONE."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=None,
            cloud_low_pct=50,
            cloud_mid_pct=50,
        )
        assert status == CloudStatus.NONE

    def test_none_missing_cloud_data(self):
        """Missing cloud data treated as 0% -> NONE."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=3200,
            cloud_low_pct=None,
            cloud_mid_pct=None,
        )
        assert status == CloudStatus.NONE

    def test_glacier_missing_mid_data(self):
        """Glacier with missing mid cloud data (treated as 0%) -> can be ABOVE_CLOUDS."""
        status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=3200,
            cloud_low_pct=40,
            cloud_mid_pct=None,  # Treated as 0%
        )
        assert status == CloudStatus.ABOVE_CLOUDS


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
        """20-50% clouds -> partly cloudy (sun behind small cloud)."""
        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=35,
            precip_mm=0,
            temp_c=5,
        )
        assert symbol == "🌤️"

    def test_mostly_cloudy(self):
        """50-80% clouds -> mostly cloudy (sun behind cloud)."""
        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=65,
            precip_mm=0,
            temp_c=5,
        )
        assert symbol == "⛅"

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
    """Tests for CloudStatus formatting (SPEC: docs/specs/cloud_layer_refactor.md)."""

    def test_above_clouds_emoji(self):
        """ABOVE_CLOUDS has sun emoji."""
        emoji = WeatherMetricsService.get_cloud_status_emoji(CloudStatus.ABOVE_CLOUDS)
        assert emoji == "☀️"

    def test_in_clouds_emoji(self):
        """IN_CLOUDS has cloud emoji."""
        emoji = WeatherMetricsService.get_cloud_status_emoji(CloudStatus.IN_CLOUDS)
        assert emoji == "☁️"

    def test_none_emoji(self):
        """NONE has no emoji."""
        emoji = WeatherMetricsService.get_cloud_status_emoji(CloudStatus.NONE)
        assert emoji == ""

    def test_format_above_clouds(self):
        """ABOVE_CLOUDS formats to 'above clouds' with green style."""
        text, style = WeatherMetricsService.format_cloud_status(CloudStatus.ABOVE_CLOUDS)
        assert text == "above clouds"
        assert "color:" in style
        assert "font-weight:" in style

    def test_format_in_clouds(self):
        """IN_CLOUDS formats to 'in clouds' with gray style."""
        text, style = WeatherMetricsService.format_cloud_status(CloudStatus.IN_CLOUDS)
        assert text == "in clouds"
        assert "color:" in style

    def test_format_none(self):
        """NONE formats to empty string with no style."""
        text, style = WeatherMetricsService.format_cloud_status(CloudStatus.NONE)
        assert text == ""
        assert style == ""


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
