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


class TestEffectiveCloudLivesInTheNormalisation:
    """Issue #3106 / ADR-0122: die Bewoelkungsregel (inkl. Hochlagen-Schwelle)
    lebt genau einmal in ``app.cloud_cover``; der Service rechnet sie nicht
    mehr selbst nach (die alte Hochlagen-Formel ``(mittel+hoch)//2`` ist in
    der neuen Regel aufgegangen, s. tests/unit/test_wirksame_bewoelkung.py)."""

    def test_service_rechnet_keine_eigene_bewoelkung(self):
        assert not hasattr(WeatherMetricsService, "calculate_effective_cloud")
        assert not hasattr(WeatherMetricsService, "HIGH_ELEVATION_THRESHOLD_M")

    def test_hochlage_wirkt_ueber_die_eine_regel(self):
        from app.cloud_cover import HOCHLAGE_SCHWELLE_M, wirksame_bewoelkung

        assert HOCHLAGE_SCHWELLE_M == 2500
        # Frueher (mittel+hoch)//2 = 30; jetzt mittel voll, Rest der hohen
        # Wolken halb: 40 + (40 - 40) * 0,5 = 40 (hoch 20 < mittel 40).
        assert wirksame_bewoelkung(80, 60, 40, 20, 2600) == 40


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
        # Proportional cloud fallback -> positive sunny hours
        hours = WeatherMetricsService.calculate_sunny_hours([dp1, dp2])
        assert hours > 1.0, (
            f"#347 AC-4: proportionaler Cloud-Fallback muss > 1.0 h ergeben "
            f"(0.8 + 0.75), war {hours}"
        )
