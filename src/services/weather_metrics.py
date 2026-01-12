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
    Cloud layer position classification (elevation-based only).

    SPEC: docs/specs/cloud_layer_refactor.md
    """
    ABOVE_CLOUDS = "above_clouds"  # Location is above the cloud layer
    IN_CLOUDS = "in_clouds"        # Location is within the cloud layer
    NONE = "none"                  # No relevant cloud layer info


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

    # Cloud layer position thresholds (SPEC: docs/specs/cloud_layer_refactor.md)
    # Elevation tiers
    GLACIER_LEVEL_M = 3000               # >= 3000m: in mid-cloud zone
    ALPINE_LEVEL_M = 2000                # 2000-3000m: top of low-cloud zone
    # Cloud thresholds
    ABOVE_CLOUDS_LOW_CLOUD_PCT = 20      # Min low cloud % to show "above clouds"
    ABOVE_CLOUDS_MAX_MID_CLOUD_PCT = 30  # Max mid cloud % for "above clouds"
    IN_CLOUDS_MID_PCT = 50               # Min mid cloud % for glacier "in clouds"
    IN_CLOUDS_ALPINE_LOW_PCT = 50        # Min low cloud % for alpine "in clouds"
    IN_CLOUDS_VALLEY_LOW_PCT = 60        # Min low cloud % for valley "in clouds"

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
        Calculate sunny hours from cloud cover data.

        Formula: sunshine_pct = 100 - effective_cloud_pct
        Sum all percentages, divide by 100 to get hours.

        High elevations (>= 2500m) ignore low clouds via calculate_effective_cloud().

        DATA SOURCE: CALCULATED (not from API!)
        See: docs/specs/data_sources.md (sunshine_duration = REJECTED)

        SPEC: docs/specs/modules/weather_metrics.md

        Args:
            data: List of ForecastDataPoint with weather data
            elevation_m: Location elevation in meters

        Returns:
            Number of sunny hours (rounded integer)
        """
        if not data:
            return 0

        total_sunshine_pct = 0.0

        for dp in data:
            # Calculate effective cloud cover (elevation-aware)
            eff_cloud = WeatherMetricsService.calculate_effective_cloud(
                elevation_m,
                dp.cloud_total_pct,
                getattr(dp, 'cloud_mid_pct', None),
                getattr(dp, 'cloud_high_pct', None),
            )

            if eff_cloud is not None:
                # Sunshine = inverse of cloud cover
                sunshine_pct = max(0, 100 - eff_cloud)
                total_sunshine_pct += sunshine_pct

        # Convert percentage sum to hours (100% = 1h), rounded
        return round(total_sunshine_pct / 100.0)

    @staticmethod
    def calculate_cloud_status(
        elevation_m: Optional[int],
        cloud_low_pct: Optional[int],
        cloud_mid_pct: Optional[int] = None,
        cloud_high_pct: Optional[int] = None,
    ) -> CloudStatus:
        """
        Determine location position relative to cloud layer.

        Cloud layer heights (Open-Meteo / WMO):
        - Low:  0 - 2000m (WMO) / 0 - 3000m (Open-Meteo)
        - Mid:  2000 - 4500m (WMO) / 3000 - 8000m (Open-Meteo)
        - High: > 4500m (WMO) / > 8000m (Open-Meteo)

        Key insight: A location at 3200m is IN the mid-cloud layer, not above it!

        Rules by elevation tier (SPEC: docs/specs/cloud_layer_refactor.md):

        1. Glacier level (>= 3000m) - in the mid-cloud zone:
           - cloud_mid > 50% -> IN_CLOUDS (in mid-level clouds)
           - cloud_low > 20% AND cloud_mid <= 30% -> ABOVE_CLOUDS (above low, clear mid)
           - otherwise -> NONE

        2. Alpine level (2000-3000m) - top of low-cloud zone:
           - cloud_low > 50% -> IN_CLOUDS
           - otherwise -> NONE

        3. Valley level (< 2000m) - in low-cloud zone:
           - cloud_low > 60% -> IN_CLOUDS
           - otherwise -> NONE

        Args:
            elevation_m: Location elevation in meters
            cloud_low_pct: Low cloud cover 0-3km (0-100%)
            cloud_mid_pct: Mid cloud cover 3-8km (0-100%)
            cloud_high_pct: High cloud cover >8km (0-100%) - reserved for future use

        Returns:
            CloudStatus enum value
        """
        if elevation_m is None:
            return CloudStatus.NONE

        low = cloud_low_pct or 0
        mid = cloud_mid_pct or 0

        # Tier 1: Glacier level (>= 3000m) - in the mid-cloud zone
        if elevation_m >= WeatherMetricsService.GLACIER_LEVEL_M:
            # In mid-level clouds?
            if mid > WeatherMetricsService.IN_CLOUDS_MID_PCT:
                return CloudStatus.IN_CLOUDS
            # Above low clouds with clear mid layer?
            if (low > WeatherMetricsService.ABOVE_CLOUDS_LOW_CLOUD_PCT
                    and mid <= WeatherMetricsService.ABOVE_CLOUDS_MAX_MID_CLOUD_PCT):
                return CloudStatus.ABOVE_CLOUDS
            return CloudStatus.NONE

        # Tier 2: Alpine level (2000-3000m) - top of low-cloud zone
        if elevation_m >= WeatherMetricsService.ALPINE_LEVEL_M:
            if low > WeatherMetricsService.IN_CLOUDS_ALPINE_LOW_PCT:
                return CloudStatus.IN_CLOUDS
            return CloudStatus.NONE

        # Tier 3: Valley level (< 2000m) - in low-cloud zone
        if low > WeatherMetricsService.IN_CLOUDS_VALLEY_LOW_PCT:
            return CloudStatus.IN_CLOUDS

        return CloudStatus.NONE

    @staticmethod
    def format_cloud_status(status: CloudStatus, use_emoji: bool = True) -> Tuple[str, str]:
        """
        Format CloudStatus for display.

        SPEC: docs/specs/cloud_layer_refactor.md

        Args:
            status: CloudStatus enum value
            use_emoji: Whether to include emoji prefix (unused, kept for API compat)

        Returns:
            Tuple of (display_text, css_style)
        """
        mapping = {
            CloudStatus.ABOVE_CLOUDS: (
                "above clouds",
                "color: #2e7d32; font-weight: 600;"
            ),
            CloudStatus.IN_CLOUDS: (
                "in clouds",
                "color: #888;"
            ),
            CloudStatus.NONE: (
                "",
                ""
            ),
        }
        return mapping.get(status, ("", ""))

    @staticmethod
    def get_cloud_status_emoji(status: CloudStatus) -> str:
        """
        Get emoji for CloudStatus.

        SPEC: docs/specs/cloud_layer_refactor.md

        Args:
            status: CloudStatus enum value

        Returns:
            Emoji string (empty for NONE)
        """
        mapping = {
            CloudStatus.ABOVE_CLOUDS: "☀️",
            CloudStatus.IN_CLOUDS: "☁️",
            CloudStatus.NONE: "",
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
            return "🌤️"  # Partly cloudy (sun behind small cloud)
        if eff_cloud < 80:
            return "⛅"  # Mostly cloudy (sun behind cloud)
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
        air_temp_c = getattr(dp, 't2m_c', None) or getattr(dp, 'temp_c', None) or 0

        # v4.3: Wind Chill fuer konsistente gefuehlte Temperatur
        # Vergleichs-Header zeigt auch Wind Chill - stundlich muss identisch sein
        wind_chill_c = getattr(dp, 'wind_chill_c', None)
        temp_c = wind_chill_c if wind_chill_c is not None else air_temp_c

        symbol = WeatherMetricsService.get_weather_symbol(
            cloud_total_pct=dp.cloud_total_pct,
            precip_mm=precip_mm,
            temp_c=temp_c,
            elevation_m=elevation_m,
            cloud_mid_pct=getattr(dp, 'cloud_mid_pct', None),
            cloud_high_pct=getattr(dp, 'cloud_high_pct', None),
        )

        # Determine precipitation type and amount
        # Note: Use AIR temperature for precip type (physical reality), not wind chill

        if precip_mm > 0:
            if air_temp_c < 2:
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
