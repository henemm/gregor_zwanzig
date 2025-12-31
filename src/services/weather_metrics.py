"""
Weather Metrics Service - Single Source of Truth.

This module contains ALL weather metric calculations.
All renderers (Email, Web-UI, CLI) MUST use these functions.

SPEC: docs/specs/modules/weather_metrics.md

NO DUPLICATES ALLOWED! If you need a weather calculation,
add it here - do NOT implement it locally in a renderer.
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from app.models import ForecastDataPoint


class CloudStatus(str, Enum):
    """
    Wolkenlage classification.

    SPEC: docs/specs/compare_email.md Zeile 212-216
    """
    ABOVE_CLOUDS = "above_clouds"  # High elevation above low clouds
    CLEAR = "clear"                # >= 75% sunshine
    LIGHT = "light"                # >= 25% sunshine
    IN_CLOUDS = "in_clouds"        # < 25% sunshine


class WeatherMetricsService:
    """
    Single Source of Truth for all weather metric calculations.

    IMPORTANT: All renderers (Email, Web-UI, CLI) MUST use this class.
    No local calculations allowed!

    Usage:
        >>> from services.weather_metrics import WeatherMetricsService
        >>> sunny = WeatherMetricsService.calculate_sunny_hours(data, elevation)
        >>> status = WeatherMetricsService.calculate_cloud_status(sunny, 8, elevation, cloud_low)
    """

    # Thresholds (configurable, but with sensible defaults)
    HIGH_ELEVATION_THRESHOLD_M = 2500
    SUNNY_HOUR_CLOUD_THRESHOLD_PCT = 30
    CLEAR_SUNSHINE_RATIO = 0.75  # >= 75% = clear
    LIGHT_SUNSHINE_RATIO = 0.25  # >= 25% = light
    ABOVE_CLOUDS_MIN_SUNNY_HOURS = 5
    ABOVE_CLOUDS_MIN_LOW_CLOUD_PCT = 30

    @staticmethod
    def calculate_effective_cloud(
        elevation_m: Optional[int],
        cloud_total_pct: Optional[int],
        cloud_mid_pct: Optional[int] = None,
        cloud_high_pct: Optional[int] = None,
    ) -> Optional[int]:
        """
        Calculate effective cloud cover based on elevation.

        High elevations (>= 2500m) ignore low clouds because they are
        below the observation point.

        SPEC: docs/specs/compare_email.md Zeile 134-150

        Args:
            elevation_m: Location elevation in meters
            cloud_total_pct: Total cloud cover (0-100%)
            cloud_mid_pct: Mid-level clouds 3-8km (0-100%)
            cloud_high_pct: High-level clouds >8km (0-100%)

        Returns:
            Effective cloud cover in % (0-100) or None if no data
        """
        if (elevation_m is not None
            and elevation_m >= WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M
            and cloud_mid_pct is not None
            and cloud_high_pct is not None):
            # High elevation: ignore low clouds, use only mid + high
            return (cloud_mid_pct + cloud_high_pct) // 2
        return cloud_total_pct

    @staticmethod
    def calculate_sunny_hours(
        data: List["ForecastDataPoint"],
        elevation_m: Optional[int] = None,
    ) -> int:
        """
        Calculate sunny hours from forecast data.

        Primary: Uses sunshine_duration_s from Open-Meteo API (most accurate)
        Fallback for high elevations: effective_cloud < 30%

        For high elevations, takes maximum of both methods to avoid
        penalizing locations that are above low clouds.

        SPEC: docs/specs/modules/weather_metrics.md

        Args:
            data: List of ForecastDataPoint with weather data
            elevation_m: Location elevation in meters

        Returns:
            Number of sunny hours (rounded integer)
        """
        if not data:
            return 0

        # Method 1: API-based (preferred, most accurate)
        sunshine_seconds = [
            dp.sunshine_duration_s for dp in data
            if hasattr(dp, 'sunshine_duration_s') and dp.sunshine_duration_s is not None
        ]
        api_hours = round(sum(sunshine_seconds) / 3600) if sunshine_seconds else 0

        # Method 2: Spec-based for high elevations (fallback)
        # High elevations should not be penalized by low clouds
        spec_hours = 0
        if elevation_m is not None and elevation_m >= WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M:
            for dp in data:
                eff_cloud = WeatherMetricsService.calculate_effective_cloud(
                    elevation_m,
                    dp.cloud_total_pct,
                    getattr(dp, 'cloud_mid_pct', None),
                    getattr(dp, 'cloud_high_pct', None),
                )
                if eff_cloud is not None and eff_cloud < WeatherMetricsService.SUNNY_HOUR_CLOUD_THRESHOLD_PCT:
                    spec_hours += 1

        # Take maximum to benefit high elevations
        return max(api_hours, spec_hours)

    @staticmethod
    def calculate_cloud_status(
        sunny_hours: Optional[int],
        time_window_hours: int,
        elevation_m: Optional[int] = None,
        cloud_low_avg: Optional[int] = None,
    ) -> CloudStatus:
        """
        Determine cloud status based on sunny hours.

        Rules (SPEC: docs/specs/compare_email.md Zeile 212-216):
        1. High elevation (>= 2500m) + cloud_low > 30% + sunny >= 5h -> ABOVE_CLOUDS
        2. sunny >= 75% of hours -> CLEAR
        3. sunny >= 25% of hours -> LIGHT
        4. Otherwise -> IN_CLOUDS

        Args:
            sunny_hours: Number of sunny hours in time window
            time_window_hours: Total hours in time window (e.g., 8 for 09:00-16:00)
            elevation_m: Location elevation in meters
            cloud_low_avg: Average low cloud cover (0-100%)

        Returns:
            CloudStatus enum value
        """
        if sunny_hours is None:
            return CloudStatus.IN_CLOUDS

        # Rule 1: High elevation above low clouds
        if (elevation_m is not None
            and elevation_m >= WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M
            and cloud_low_avg is not None
            and cloud_low_avg > WeatherMetricsService.ABOVE_CLOUDS_MIN_LOW_CLOUD_PCT
            and sunny_hours >= WeatherMetricsService.ABOVE_CLOUDS_MIN_SUNNY_HOURS):
            return CloudStatus.ABOVE_CLOUDS

        # Rules 2-4: Based on sunshine ratio
        if time_window_hours > 0:
            ratio = sunny_hours / time_window_hours
            if ratio >= WeatherMetricsService.CLEAR_SUNSHINE_RATIO:
                return CloudStatus.CLEAR
            elif ratio >= WeatherMetricsService.LIGHT_SUNSHINE_RATIO:
                return CloudStatus.LIGHT

        return CloudStatus.IN_CLOUDS

    @staticmethod
    def format_cloud_status(status: CloudStatus, use_emoji: bool = True) -> Tuple[str, str]:
        """
        Format CloudStatus for display.

        SPEC: docs/specs/compare_email.md Zeile 212-216

        Args:
            status: CloudStatus enum value
            use_emoji: Whether to include emoji prefix

        Returns:
            Tuple of (display_text, css_style)
        """
        mapping = {
            CloudStatus.ABOVE_CLOUDS: (
                "ueber Wolken" if not use_emoji else "ueber Wolken",
                "color: #2e7d32; font-weight: 600;"
            ),
            CloudStatus.CLEAR: (
                "klar" if not use_emoji else "klar",
                "color: #2e7d32;"
            ),
            CloudStatus.LIGHT: (
                "leicht" if not use_emoji else "leicht",
                ""
            ),
            CloudStatus.IN_CLOUDS: (
                "in Wolken" if not use_emoji else "in Wolken",
                "color: #888;"
            ),
        }
        return mapping.get(status, ("-", ""))

    @staticmethod
    def get_cloud_status_emoji(status: CloudStatus) -> str:
        """
        Get emoji for CloudStatus.

        Args:
            status: CloudStatus enum value

        Returns:
            Emoji string
        """
        mapping = {
            CloudStatus.ABOVE_CLOUDS: "☀️",
            CloudStatus.CLEAR: "✨",
            CloudStatus.LIGHT: "🌤️",
            CloudStatus.IN_CLOUDS: "☁️",
        }
        return mapping.get(status, "")

    @staticmethod
    def get_weather_symbol(
        cloud_total_pct: Optional[int],
        precip_mm: Optional[float],
        temp_c: Optional[float],
        elevation_m: Optional[int] = None,
        cloud_mid_pct: Optional[int] = None,
        cloud_high_pct: Optional[int] = None,
    ) -> str:
        """
        Determine weather symbol based on conditions.

        Considers elevation for effective cloud cover.

        SPEC: docs/specs/modules/weather_metrics.md

        Args:
            cloud_total_pct: Total cloud cover (0-100%)
            precip_mm: Precipitation amount in mm
            temp_c: Temperature in Celsius
            elevation_m: Location elevation in meters
            cloud_mid_pct: Mid-level clouds (0-100%)
            cloud_high_pct: High-level clouds (0-100%)

        Returns:
            Weather symbol emoji
        """
        # Precipitation takes priority
        if precip_mm is not None and precip_mm > 0.5:
            if temp_c is not None and temp_c < 0:
                return "❄️"  # Snow
            return "🌧️"  # Rain

        # Cloud-based symbol
        eff_cloud = WeatherMetricsService.calculate_effective_cloud(
            elevation_m, cloud_total_pct, cloud_mid_pct, cloud_high_pct
        )

        if eff_cloud is None:
            return "?"
        if eff_cloud < 20:
            return "☀️"  # Sunny
        if eff_cloud < 50:
            return "⛅"  # Partly cloudy
        if eff_cloud < 80:
            return "🌥️"  # Mostly cloudy
        return "☁️"  # Overcast
