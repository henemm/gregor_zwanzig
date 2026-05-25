"""
Unit Tests: WeatherMetricsService Legacy Static Methods

Tests for restored static methods that were accidentally deleted in Feature 2.2b.
These tests MUST FAIL initially (TDD RED phase) because methods don't exist yet.

Related Spec: docs/specs/bugfix/empty_subscription_emails.md
"""
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.weather_metrics import WeatherMetricsService
from app.models import ForecastDataPoint


class TestHighElevationThresholdConstant:
    """Test HIGH_ELEVATION_THRESHOLD_M constant exists."""

    def test_constant_exists(self):
        """
        GIVEN: WeatherMetricsService class
        WHEN: Accessing HIGH_ELEVATION_THRESHOLD_M attribute
        THEN: Constant exists and equals 2500

        Expected: FAIL - AttributeError (constant doesn't exist)
        """
        assert hasattr(WeatherMetricsService, 'HIGH_ELEVATION_THRESHOLD_M')
        assert WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M == 2500


class TestCalculateEffectiveCloud:
    """Test calculate_effective_cloud() static method."""

    def test_method_exists(self):
        """
        GIVEN: WeatherMetricsService class
        WHEN: Checking for calculate_effective_cloud method
        THEN: Method exists and is callable

        Expected: FAIL - AttributeError (method doesn't exist)
        """
        assert hasattr(WeatherMetricsService, 'calculate_effective_cloud')
        assert callable(WeatherMetricsService.calculate_effective_cloud)

    def test_high_elevation_ignores_low_clouds(self):
        """
        GIVEN: High elevation location (>=2500m) with cloud data
        WHEN: Calculating effective cloud cover
        THEN: Returns average of mid+high clouds, ignoring low clouds

        Expected: FAIL - AttributeError (method doesn't exist)
        """
        eff = WeatherMetricsService.calculate_effective_cloud(
            elevation_m=2600,
            cloud_total_pct=80,
            cloud_mid_pct=40,
            cloud_high_pct=20,
        )
        assert eff == 30


class TestCalculateSunnyHours:
    """Test calculate_sunny_hours() static method."""

    def test_method_exists(self):
        """
        GIVEN: WeatherMetricsService class
        WHEN: Checking for calculate_sunny_hours method
        THEN: Method exists and is callable

        Expected: FAIL - AttributeError (method doesn't exist)
        """
        assert hasattr(WeatherMetricsService, 'calculate_sunny_hours')
        assert callable(WeatherMetricsService.calculate_sunny_hours)

    def test_empty_data_returns_zero(self):
        """
        GIVEN: Empty forecast data list
        WHEN: Calculating sunny hours
        THEN: Returns 0

        Expected: FAIL - AttributeError (method doesn't exist)
        """
        hours = WeatherMetricsService.calculate_sunny_hours([])
        assert hours == 0

    def test_api_sunshine_duration(self):
        """
        GIVEN: Forecast data with cloud cover, no DNI (Geosphere-style),
               low elevation (1500 m)
        WHEN: Calculating sunny hours
        THEN: Returns the proportional cloud-fallback sum (NOT 0)

        Issue #347 (AC-4): Die alte Erwartung `hours == 0` war durch den Defekt
        erzwungen (Cloud-Fallback griff nur ab 2500 m, binaerer 30%-Cutoff).
        Nach dem Fix greift der proportionale Cloud-Fallback auch unter 2500 m:
            cloud=20% -> (100-20)/100 = 0.8
            cloud=25% -> (100-25)/100 = 0.75
        Summe ~1.55 -> klar > 0.
        """
        # Create data points with cloud cover, no DNI (Geosphere-style)
        dp1 = ForecastDataPoint(
            ts=datetime(2026, 2, 4, 9, 0),
            cloud_total_pct=20,  # Mostly clear
            dni_wm2=None,
        )
        dp2 = ForecastDataPoint(
            ts=datetime(2026, 2, 4, 10, 0),
            cloud_total_pct=25,  # Mostly clear
            dni_wm2=None,
        )
        # Low elevation + proportional cloud fallback -> positive sunny hours
        hours = WeatherMetricsService.calculate_sunny_hours([dp1, dp2], elevation_m=1500)
        assert hours > 1.0, (
            f"#347 AC-4: proportionaler Cloud-Fallback muss > 1.0 h ergeben "
            f"(0.8 + 0.75), war {hours}"
        )
