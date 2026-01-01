"""
Weather Metrics Service - Single Source of Truth.

This module contains ALL weather metric calculations.
All renderers (Email, Web-UI, CLI) MUST use these functions.

SPEC: docs/specs/modules/weather_metrics.md

NO DUPLICATES ALLOWED! If you need a weather calculation,
add it here - do NOT implement it locally in a renderer.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from app.models import ForecastDataPoint


@dataclass
class HourlyCell:
    """
    Eine Stunden-Zelle - identisch fuer UI und Email.

    SPEC: docs/specs/compare_email.md v4.2 Zeile 184-260

    Single Source of Truth fuer Stunden-Formatierung.
    Wird von BEIDEN Renderern verwendet:
    - render_comparison_html() fuer E-Mail
    - render_hourly_table() fuer WebUI
    """
    hour: int                        # 9, 10, 11, ...
    symbol: str                      # "☀️", "🌤️", "⛅", "☁️"
    temp_c: int                      # -5, 12, ...
    precip_symbol: str               # "🌨️", "🌧️", ""
    precip_amount: Optional[float]   # 2.5, None wenn kein Niederschlag
    precip_unit: str                 # "cm", "mm", ""
    wind_kmh: int                    # 15
    gust_kmh: int                    # 25
    wind_dir: str                    # "SW", "N", "NE"


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

    @staticmethod
    def degrees_to_compass(degrees: Optional[float]) -> str:
        """
        Convert wind direction from degrees to compass direction.

        SPEC: docs/specs/compare_email.md v4.2

        Args:
            degrees: Wind direction in degrees (0-360)

        Returns:
            Compass direction (N, NE, E, SE, S, SW, W, NW)
        """
        if degrees is None:
            return ""

        # Normalize to 0-360
        degrees = degrees % 360

        # 8 compass directions, each covers 45 degrees
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        index = round(degrees / 45) % 8
        return directions[index]

    @staticmethod
    def format_hourly_cell(
        dp: "ForecastDataPoint",
        elevation_m: Optional[int] = None,
    ) -> HourlyCell:
        """
        Single Source of Truth fuer Stunden-Formatierung.

        SPEC: docs/specs/compare_email.md v4.2 Zeile 204-244

        Wird von BEIDEN Renderern verwendet:
        - render_comparison_html() fuer E-Mail
        - render_hourly_table() fuer WebUI

        Args:
            dp: ForecastDataPoint with weather data
            elevation_m: Location elevation in meters

        Returns:
            HourlyCell with formatted data
        """
        # Get weather symbol based on effective cloud cover
        # ForecastDataPoint uses precip_1h_mm, t2m_c, wind10m_kmh, wind_direction_deg
        precip_mm = getattr(dp, 'precip_1h_mm', None) or getattr(dp, 'precip_mm', None) or 0
        temp_c = getattr(dp, 't2m_c', None) or getattr(dp, 'temp_c', None) or 0

        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=dp.cloud_total_pct,
            precip_mm=precip_mm,
            temp_c=temp_c,
            elevation_m=elevation_m,
            cloud_mid_pct=getattr(dp, 'cloud_mid_pct', None),
            cloud_high_pct=getattr(dp, 'cloud_high_pct', None),
        )

        # Determine precipitation type and amount

        if precip_mm > 0:
            if temp_c < 2:
                # Snow: mm water -> cm snow (factor ~10)
                precip_symbol = "🌨️"
                precip_unit = "cm"
                precip_amount = round(precip_mm / 10, 1)
                # Minimum display of 0.1cm if there's any precipitation
                if precip_amount == 0 and precip_mm > 0:
                    precip_amount = 0.1
            else:
                # Rain: keep in mm
                precip_symbol = "🌧️"
                precip_unit = "mm"
                precip_amount = round(precip_mm, 1)
        else:
            precip_symbol = ""
            precip_amount = None
            precip_unit = ""

        # Wind data - ForecastDataPoint uses wind10m_kmh, gust_kmh, wind_direction_deg
        wind_kmh = round(
            getattr(dp, 'wind10m_kmh', None) or getattr(dp, 'wind_kmh', None) or 0
        )
        gust_kmh = round(
            getattr(dp, 'gust_kmh', None) or wind_kmh
        )
        wind_dir = WeatherMetricsService.degrees_to_compass(
            getattr(dp, 'wind_direction_deg', None) or getattr(dp, 'wind_direction', None)
        )

        return HourlyCell(
            hour=dp.ts.hour,
            symbol=symbol,
            temp_c=round(temp_c),
            precip_symbol=precip_symbol,
            precip_amount=precip_amount,
            precip_unit=precip_unit,
            wind_kmh=wind_kmh,
            gust_kmh=gust_kmh,
            wind_dir=wind_dir,
        )

    @staticmethod
    def hourly_cell_to_compact(cell: HourlyCell) -> str:
        """
        Kompakte String-Darstellung fuer Tabellen-Zelle.

        SPEC: docs/specs/compare_email.md v4.2 Zeile 246-250

        Format: ☀️-5° 🌨️2cm 15/25SW

        Args:
            cell: HourlyCell with formatted data

        Returns:
            Compact string representation
        """
        # Precipitation part
        if cell.precip_amount is not None and cell.precip_amount > 0:
            # Format amount without trailing .0
            if cell.precip_amount == int(cell.precip_amount):
                precip = f"{cell.precip_symbol}{int(cell.precip_amount)}{cell.precip_unit}"
            else:
                precip = f"{cell.precip_symbol}{cell.precip_amount}{cell.precip_unit}"
        else:
            precip = "-"

        # Wind part
        wind = f"{cell.wind_kmh}/{cell.gust_kmh}{cell.wind_dir}"

        return f"{cell.symbol}{cell.temp_c}° {precip} {wind}"
