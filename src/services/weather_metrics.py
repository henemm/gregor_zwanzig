"""
Weather metrics service - computes basis hiking metrics from timeseries.

Feature 2.2a: Basis-Metriken
Aggregates hourly weather values (MIN/MAX/AVG/SUM) over segment duration.

SPEC: docs/specs/modules/weather_metrics.md v1.0
SPEC: docs/specs/modules/weather_emoji_dni.md v1.0 (DNI-based emoji)
"""
from __future__ import annotations

from typing import List, Optional

import math

from app.debug import DebugBuffer
from app.models import NormalizedTimeseries, PrecipType, SegmentWeatherSummary, ThunderLevel


# =============================================================================
# DNI-based Weather Emoji (SPEC: weather_emoji_dni.md v1.0)
# =============================================================================

# DNI thresholds (W/m²) — based on WMO sunshine definition (DNI > 120)
_DNI_FULL_SUN = 600
_DNI_MOSTLY_SUNNY = 300
_DNI_PARTLY_SUNNY = 120

# WMO precipitation/fog/thunder codes → emoji (priority 1)
_WMO_PRECIP_EMOJI: dict[int, str] = {
    45: "🌫️", 48: "🌫️",                       # Fog
    51: "🌦️", 53: "🌦️", 55: "🌧️",           # Drizzle
    56: "🌧️", 57: "🌧️",                       # Freezing drizzle
    61: "🌧️", 63: "🌧️", 65: "🌧️",           # Rain
    66: "🌨️", 67: "🌨️",                       # Freezing rain
    71: "❄️", 73: "❄️", 75: "❄️", 77: "❄️",   # Snow
    80: "🌦️", 81: "🌧️", 82: "🌧️",           # Rain showers
    85: "🌨️", 86: "🌨️",                       # Snow showers
    95: "⛈️", 96: "⛈️", 99: "⛈️",             # Thunderstorm
}

# WMO severity ranking for aggregation (highest value wins)
_WMO_SEVERITY: dict[int, int] = {
    0: 0, 1: 1, 2: 2, 3: 3,
    45: 10, 48: 11,
    51: 20, 53: 21, 55: 22, 56: 23, 57: 24,
    61: 30, 63: 31, 65: 32, 66: 33, 67: 34,
    71: 35, 73: 36, 75: 37, 77: 38,
    80: 40, 81: 41, 82: 42, 85: 43, 86: 44,
    95: 50, 96: 51, 99: 52,
}


def get_weather_emoji(
    *,
    is_day: Optional[int] = None,
    dni_wm2: Optional[float] = None,
    wmo_code: Optional[int] = None,
    cloud_pct: Optional[int] = None,
) -> str:
    """
    Central weather emoji function. Single Source of Truth.

    Priority:
    1. WMO precipitation/fog/thunder codes — always take precedence
    2. Night (is_day=0) → moon emojis based on cloud%
    3. Day with DNI → DNI-based sun emoji
    4. Fallback: cloud%-based emoji
    """
    # 1. WMO precipitation/fog/thunder always wins
    if wmo_code is not None and wmo_code in _WMO_PRECIP_EMOJI:
        return _WMO_PRECIP_EMOJI[wmo_code]
    # 2. Night
    if is_day is not None and is_day == 0:
        return _night_emoji(cloud_pct)
    # 3. Day with DNI
    if is_day == 1 and dni_wm2 is not None:
        return _dni_emoji(dni_wm2)
    # 4. Fallback (is_day unknown or DNI missing)
    return _cloud_pct_emoji(cloud_pct)


def _night_emoji(cloud_pct: Optional[int]) -> str:
    """Night emoji based on cloud cover."""
    if cloud_pct is None or cloud_pct < 40:
        return "🌙"
    if cloud_pct < 80:
        return "🌙☁️"
    return "☁️"


def _dni_emoji(dni_wm2: float) -> str:
    """Day emoji based on Direct Normal Irradiance."""
    if dni_wm2 >= _DNI_FULL_SUN:
        return "☀️"
    if dni_wm2 >= _DNI_MOSTLY_SUNNY:
        return "🌤️"
    if dni_wm2 >= _DNI_PARTLY_SUNNY:
        return "⛅"
    if dni_wm2 > 0:
        return "🌥️"
    return "☁️"


def _cloud_pct_emoji(cloud_pct: Optional[int]) -> str:
    """Fallback emoji from cloud% (kanonische Skala, Issue #1214 Scheibe 6)."""
    if cloud_pct is None:
        return "?"
    from output.metric_format import cloud_emoji
    return cloud_emoji(cloud_pct)


# =============================================================================
# Issue #435: Simplified-Mode Helpers (single source of truth)
# =============================================================================
# Used by E-Mail-Renderer (helpers.fmt_val) for format_mode="simplified".
# Adjective thresholds mirror compact_summary._format_wind (line 271–279)
# and compact_summary._precip_adjective (line 187–192).

def format_wind_strength(kmh: Optional[float]) -> str:
    """Wind-strength adjective (kürzel) for simplified-mode rendering.

    Thresholds mirror compact_summary._format_wind (line 271–279):
      <10 km/h  -> "schwach"
      <25 km/h  -> "mäßig"
      <40 km/h  -> "stark"
      >=40 km/h -> "sehr stark"
    None -> "–"
    """
    if kmh is None:
        return "–"
    if kmh < 10:
        return "schwach"
    if kmh < 25:
        return "mäßig"
    if kmh < 40:
        return "stark"
    return "sehr stark"


def format_precip_intensity(mm: Optional[float]) -> str:
    """Precipitation-intensity adjective (kürzel) for simplified-mode rendering.

    Thresholds mirror compact_summary._precip_adjective (line 187–192):
      None or 0  -> "trocken"
      <=2 mm     -> "leicht"
      <=10 mm    -> "mäßig"
      >10 mm     -> "stark"
    """
    if mm is None or mm <= 0:
        return "trocken"
    if mm <= 2:
        return "leicht"
    if mm <= 10:
        return "mäßig"
    return "stark"


def compute_dominant_wmo(data) -> Optional[int]:
    """Most severe WMO code from hourly data points."""
    codes = [dp.wmo_code for dp in data if getattr(dp, 'wmo_code', None) is not None]
    if not codes:
        return None
    return max(codes, key=lambda c: _WMO_SEVERITY.get(c, 0))


def compute_dni_day_avg(data) -> Optional[float]:
    """Average DNI over daytime hours only (is_day=1)."""
    day_dni = [dp.dni_wm2 for dp in data
               if getattr(dp, 'is_day', None) == 1 and getattr(dp, 'dni_wm2', None) is not None]
    if not day_dni:
        return None
    return sum(day_dni) / len(day_dni)


class WeatherMetricsService:
    """
    Service for computing basic weather metrics from timeseries data.

    Aggregates hourly weather values (MIN/MAX/AVG/SUM) over segment duration
    to populate SegmentWeatherSummary fields.
    """

    # Cloud status constants (legacy - for compare.py compatibility)
    GLACIER_LEVEL_M = 3000               # >= 3000m: in mid-cloud zone
    ALPINE_LEVEL_M = 2000                # 2000-3000m: top of low-cloud zone
    ABOVE_CLOUDS_LOW_CLOUD_PCT = 20      # Min low cloud % to show "above clouds"
    ABOVE_CLOUDS_MAX_MID_CLOUD_PCT = 30  # Max mid cloud % for "above clouds"
    IN_CLOUDS_MID_PCT = 50               # Min mid cloud % for glacier "in clouds"
    IN_CLOUDS_ALPINE_LOW_PCT = 50        # Min low cloud % for alpine "in clouds"
    IN_CLOUDS_VALLEY_LOW_PCT = 60        # Min low cloud % for valley "in clouds"

    def __init__(
        self,
        debug: Optional[DebugBuffer] = None,
    ) -> None:
        """
        Initialize weather metrics service.

        Args:
            debug: Optional debug buffer for logging
        """
        self._debug = debug if debug is not None else DebugBuffer()

    @staticmethod
    def degrees_to_compass(degrees: int | None) -> str:
        """
        Convert wind direction in degrees (0-360) to compass direction.

        Legacy static method for backward compatibility with compare.py.
        Delegates to utils.geo.degrees_to_compass (single source of truth).
        """
        from utils.geo import degrees_to_compass as _degrees_to_compass

        return _degrees_to_compass(degrees, none_label="-")

    # ============================================================================
    # Legacy Static Methods for compare.py Compatibility
    # ============================================================================
    # These methods were restored after accidental deletion in Feature 2.2b.
    # They are still used by compare.py at 12 locations.
    # DO NOT DELETE without refactoring compare.py first!
    # Restored: 2026-02-03 via Bugfix: Empty Subscription Emails
    # ============================================================================

    # Legacy constants for compare.py compatibility
    HIGH_ELEVATION_THRESHOLD_M = 2500
    SUNNY_HOUR_CLOUD_THRESHOLD_PCT = 30

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

        Legacy static method for compare.py compatibility.

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
    def dni_to_sunny_fraction(
        dni_wm2: Optional[float],
        dni_min: float = 60.0,
        dni_max: float = 180.0,
    ) -> float:
        """
        WMO-conform sunny-hour fraction for a single hour from DNI (Issue #347).

        ``dni >= max`` -> 1.0, ``min < dni < max`` -> linear interpolation,
        ``dni <= min`` or None -> 0.0.
        """
        if dni_wm2 is None:
            return 0.0
        if dni_wm2 >= dni_max:
            return 1.0
        if dni_wm2 > dni_min:
            return (dni_wm2 - dni_min) / (dni_max - dni_min)
        return 0.0

    @staticmethod
    def calculate_sunny_hours(
        data: List["ForecastDataPoint"],
        elevation_m: Optional[int] = None,
        settings: Optional["Settings"] = None,
    ) -> float:
        """
        Calculate sunny hours from forecast data (Issue #347).

        Main path (DNI): for each data point with ``dni_wm2`` set, contribute a
        WMO-conform linearly interpolated fraction over the configured band:
        ``dni >= max`` -> +1.0 h, ``min < dni < max`` -> +(dni-min)/(max-min) h,
        ``dni <= min`` -> +0.0 h.

        Fallback path (proportional cloud): only when NO data point carries DNI
        (e.g. Geosphere). Per point ``(100 - effective_cloud) / 100`` h via
        ``calculate_effective_cloud`` (elevation logic preserved). No binary cutoff.

        Legacy static method for compare.py compatibility.

        SPEC: docs/specs/modules/issue_347_sunshine_hours.md

        Args:
            data: List of ForecastDataPoint with weather data
            elevation_m: Location elevation in meters
            settings: Optional Settings for DNI band; None -> defaults 60/180

        Returns:
            Number of sunny hours (float, rounded to 1 decimal place)
        """
        if not data:
            return 0.0

        if settings is None:
            from app.config import Settings
            settings = Settings()

        dni_min = settings.sunny_dni_min_wm2
        dni_max = settings.sunny_dni_max_wm2

        # Main path: any data point with DNI -> DNI interpolation (cloud fallback off)
        has_dni = any(getattr(dp, "dni_wm2", None) is not None for dp in data)

        total_hours = 0.0
        for dp in data:
            dni = getattr(dp, "dni_wm2", None)
            if has_dni:
                total_hours += WeatherMetricsService.dni_to_sunny_fraction(
                    dni, dni_min, dni_max
                )
            else:
                # Proportional cloud fallback (no DNI available, e.g. Geosphere)
                eff_cloud = WeatherMetricsService.calculate_effective_cloud(
                    elevation_m,
                    dp.cloud_total_pct,
                    getattr(dp, "cloud_mid_pct", None),
                    getattr(dp, "cloud_high_pct", None),
                )
                if eff_cloud is not None:
                    total_hours += (100 - eff_cloud) / 100

        return round(total_hours, 1)

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

        Legacy static method for compare.py compatibility.

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

    def compute_basis_metrics(
        self,
        timeseries: NormalizedTimeseries,
    ) -> SegmentWeatherSummary:
        """
        Compute 8 basic hiking metrics from timeseries.

        Metrics computed:
        1. Temperature: MIN/MAX/AVG from t2m_c
        2. Wind: MAX from wind10m_kmh
        3. Gust: MAX from gust_kmh
        4. Precipitation: SUM from precip_1h_mm
        5. Cloud Cover: AVG from cloud_total_pct
        6. Humidity: AVG from humidity_pct
        7. Thunder: MAX from thunder_level (NONE < MED < HIGH)
        8. Visibility: MIN from visibility_m

        Args:
            timeseries: Weather timeseries from provider

        Returns:
            SegmentWeatherSummary with 8 basis metrics populated

        Raises:
            ValueError: If timeseries is empty
        """
        # Validate timeseries
        if not timeseries.data:
            raise ValueError("Cannot compute metrics from empty timeseries")

        self._debug.add(f"metrics: Computing from {len(timeseries.data)} data points")

        # Compute each metric
        temp_min, temp_max, temp_avg = self._compute_temperature(timeseries)
        wind_max = self._compute_wind(timeseries)
        gust_max = self._compute_gust(timeseries)
        precip_sum = self._compute_precipitation(timeseries)
        cloud_avg = self._compute_cloud_cover(timeseries)
        humidity_avg = self._compute_humidity(timeseries)
        thunder_max = self._compute_thunder_level(timeseries)
        visibility_min = self._compute_visibility(timeseries)

        # DNI-based emoji aggregation (SPEC: weather_emoji_dni.md)
        dominant_wmo = compute_dominant_wmo(timeseries.data)
        dni_avg = compute_dni_day_avg(timeseries.data)
        # Issue #347: precompute sunny hours (h) via the single source of truth
        # so Trip-Summary and Compare render the identical quantity (AC-9).
        sunny_hours = WeatherMetricsService.calculate_sunny_hours(timeseries.data)

        # Create summary with aggregation config
        summary = SegmentWeatherSummary(
            temp_min_c=temp_min,
            temp_max_c=temp_max,
            temp_avg_c=temp_avg,
            wind_max_kmh=wind_max,
            gust_max_kmh=gust_max,
            precip_sum_mm=precip_sum,
            cloud_avg_pct=cloud_avg,
            humidity_avg_pct=humidity_avg,
            thunder_level_max=thunder_max,
            visibility_min_m=visibility_min,
            dominant_wmo_code=dominant_wmo,
            dni_avg_wm2=dni_avg,
            sunny_hours=sunny_hours,
            aggregation_config={
                "temp_min_c": "min",
                "temp_max_c": "max",
                "temp_avg_c": "avg",
                "wind_max_kmh": "max",
                "gust_max_kmh": "max",
                "precip_sum_mm": "sum",
                "cloud_avg_pct": "avg",
                "humidity_avg_pct": "avg",
                "thunder_level_max": "max",
                "visibility_min_m": "min",
                "dominant_wmo_code": "max_wmo_severity",
                "dni_avg_wm2": "avg",
            },
        )

        # Validate plausibility
        self._validate_plausibility(summary)

        # Log computed metrics
        self._debug.add(f"metrics: temp={temp_min}/{temp_max}/{temp_avg}°C")
        self._debug.add(f"metrics: wind={wind_max}km/h, gust={gust_max}km/h")
        self._debug.add(f"metrics: precip={precip_sum}mm")
        self._debug.add(
            f"metrics: cloud={cloud_avg}%, humidity={humidity_avg}%"
        )

        return summary

    def _compute_temperature(
        self,
        timeseries: NormalizedTimeseries,
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Compute temperature MIN/MAX/AVG.

        Returns:
            (temp_min_c, temp_max_c, temp_avg_c)
        """
        temps = [dp.t2m_c for dp in timeseries.data if dp.t2m_c is not None]

        if not temps:
            return None, None, None

        return min(temps), max(temps), sum(temps) / len(temps)

    def _compute_wind(
        self,
        timeseries: NormalizedTimeseries,
    ) -> Optional[float]:
        """
        Compute wind MAX.

        Returns:
            wind_max_kmh
        """
        winds = [dp.wind10m_kmh for dp in timeseries.data if dp.wind10m_kmh is not None]
        return max(winds) if winds else None

    def _compute_gust(
        self,
        timeseries: NormalizedTimeseries,
    ) -> Optional[float]:
        """
        Compute gust MAX.

        Returns:
            gust_max_kmh
        """
        gusts = [dp.gust_kmh for dp in timeseries.data if dp.gust_kmh is not None]
        return max(gusts) if gusts else None

    def _compute_precipitation(
        self,
        timeseries: NormalizedTimeseries,
    ) -> Optional[float]:
        """
        Compute precipitation SUM.

        Returns:
            precip_sum_mm
        """
        precip_vals = [
            dp.precip_1h_mm for dp in timeseries.data if dp.precip_1h_mm is not None
        ]
        return sum(precip_vals) if precip_vals else None

    def _compute_cloud_cover(
        self,
        timeseries: NormalizedTimeseries,
    ) -> Optional[int]:
        """
        Compute cloud cover AVG.

        Returns:
            cloud_avg_pct (rounded to int)
        """
        clouds = [
            dp.cloud_total_pct for dp in timeseries.data if dp.cloud_total_pct is not None
        ]

        if not clouds:
            return None

        return round(sum(clouds) / len(clouds))

    def _compute_humidity(
        self,
        timeseries: NormalizedTimeseries,
    ) -> Optional[int]:
        """
        Compute humidity AVG.

        Returns:
            humidity_avg_pct (rounded to int)
        """
        humidity_vals = [
            dp.humidity_pct for dp in timeseries.data if dp.humidity_pct is not None
        ]

        if not humidity_vals:
            return None

        return round(sum(humidity_vals) / len(humidity_vals))

    def _compute_thunder_level(
        self,
        timeseries: NormalizedTimeseries,
    ) -> Optional[ThunderLevel]:
        """
        Compute thunder level MAX.

        Returns:
            thunder_level_max (NONE < MED < HIGH)
        """
        levels = [
            dp.thunder_level for dp in timeseries.data if dp.thunder_level is not None
        ]

        if not levels:
            return None

        # Issue #1214 Scheibe 6: kanonische Ordnungsquelle statt lokalem Dict.
        from output.metric_format import max_thunder
        return max_thunder(levels)

    def _compute_visibility(
        self,
        timeseries: NormalizedTimeseries,
    ) -> Optional[int]:
        """
        Compute visibility MIN.

        Returns:
            visibility_min_m
        """
        vis_vals = [
            dp.visibility_m for dp in timeseries.data if dp.visibility_m is not None
        ]

        if not vis_vals:
            return None

        return round(min(vis_vals))

    def _validate_plausibility(
        self,
        summary: SegmentWeatherSummary,
    ) -> None:
        """
        Validate metric plausibility and log warnings.

        Checks (logs WARNING if out of range, does NOT raise):
        - Temperature: -50°C to +50°C
        - Wind/Gust: 0 to 300 km/h
        - Precipitation: 0 to 500 mm
        - Cloud/Humidity: 0 to 100%
        - Visibility: 0 to 100000 m
        """
        # Temperature
        if summary.temp_min_c is not None:
            if not (-50 <= summary.temp_min_c <= 50):
                self._debug.add(
                    f"WARNING: temp_min_c={summary.temp_min_c}°C out of plausible range (-50..50)"
                )
        if summary.temp_max_c is not None:
            if not (-50 <= summary.temp_max_c <= 50):
                self._debug.add(
                    f"WARNING: temp_max_c={summary.temp_max_c}°C out of plausible range (-50..50)"
                )

        # Wind/Gust
        if summary.wind_max_kmh is not None:
            if not (0 <= summary.wind_max_kmh <= 300):
                self._debug.add(
                    f"WARNING: wind_max_kmh={summary.wind_max_kmh} km/h out of plausible range (0..300)"
                )
        if summary.gust_max_kmh is not None:
            if not (0 <= summary.gust_max_kmh <= 300):
                self._debug.add(
                    f"WARNING: gust_max_kmh={summary.gust_max_kmh} km/h out of plausible range (0..300)"
                )

        # Precipitation
        if summary.precip_sum_mm is not None:
            if not (0 <= summary.precip_sum_mm <= 500):
                self._debug.add(
                    f"WARNING: precip_sum_mm={summary.precip_sum_mm} mm out of plausible range (0..500)"
                )

        # Cloud/Humidity
        if summary.cloud_avg_pct is not None:
            if not (0 <= summary.cloud_avg_pct <= 100):
                self._debug.add(
                    f"WARNING: cloud_avg_pct={summary.cloud_avg_pct}% out of plausible range (0..100)"
                )
        if summary.humidity_avg_pct is not None:
            if not (0 <= summary.humidity_avg_pct <= 100):
                self._debug.add(
                    f"WARNING: humidity_avg_pct={summary.humidity_avg_pct}% out of plausible range (0..100)"
                )

        # Visibility
        if summary.visibility_min_m is not None:
            if not (0 <= summary.visibility_min_m <= 100000):
                self._debug.add(
                    f"WARNING: visibility_min_m={summary.visibility_min_m} m out of plausible range (0..100000)"
                )


# ============================================================================

    # ========================================================================
    # Feature 2.2b: Extended Metrics
    # ========================================================================

    def compute_extended_metrics(
        self,
        timeseries: NormalizedTimeseries,
        basis_summary: SegmentWeatherSummary,
    ) -> SegmentWeatherSummary:
        """
        Compute 7 extended hiking metrics and merge with basis metrics.

        Metrics computed:
        1. Dewpoint: AVG from dewpoint_c
        2. Pressure: AVG from pressure_msl_hpa
        3. Wind-Chill: MIN from wind_chill_c
        4. Snow-Depth: MAX from snow_depth_cm (optional, winter)
        5. Freezing-Level: AVG from freezing_level_m (optional, winter)
        6. Rain Probability: MAX from pop_pct (OpenMeteo)
        7. CAPE: MAX from cape_jkg (OpenMeteo)

        Args:
            timeseries: Weather timeseries from provider
            basis_summary: Summary with basis metrics from compute_basis_metrics()

        Returns:
            SegmentWeatherSummary with 7 extended metrics added

        Raises:
            ValueError: If timeseries is empty
        """
        # Validate timeseries
        if not timeseries.data:
            raise ValueError("Cannot compute metrics from empty timeseries")

        self._debug.add(f"extended_metrics: Computing from {len(timeseries.data)} data points")

        # Compute extended metrics
        dewpoint_avg = self._compute_dewpoint(timeseries)
        pressure_avg = self._compute_pressure(timeseries)
        wind_chill_min = self._compute_wind_chill(timeseries)
        wind_chill_max = self._compute_wind_chill_max(timeseries)
        snow_depth = self._compute_snow_depth(timeseries)
        freezing_level = self._compute_freezing_level(timeseries)
        pop_max = self._compute_pop(timeseries)
        cape_max = self._compute_cape(timeseries)
        uv_index_max = self._compute_uv_index(timeseries)
        fresh_snow_sum = self._compute_fresh_snow(timeseries)
        wind_dir_avg = self._compute_wind_direction(timeseries)
        precip_type_dom = self._compute_precip_type(timeseries)
        confidence_min = self._compute_confidence_min(timeseries)

        # Create new summary with basis + extended metrics
        extended_summary = SegmentWeatherSummary(
            # Copy basis metrics
            temp_min_c=basis_summary.temp_min_c,
            temp_max_c=basis_summary.temp_max_c,
            temp_avg_c=basis_summary.temp_avg_c,
            wind_max_kmh=basis_summary.wind_max_kmh,
            gust_max_kmh=basis_summary.gust_max_kmh,
            precip_sum_mm=basis_summary.precip_sum_mm,
            cloud_avg_pct=basis_summary.cloud_avg_pct,
            humidity_avg_pct=basis_summary.humidity_avg_pct,
            thunder_level_max=basis_summary.thunder_level_max,
            visibility_min_m=basis_summary.visibility_min_m,
            # Felder aus compute_basis_metrics() die bisher fehlten (Issue #226)
            dominant_wmo_code=basis_summary.dominant_wmo_code,
            dni_avg_wm2=basis_summary.dni_avg_wm2,
            sunny_hours=basis_summary.sunny_hours,  # Issue #347
            # Add extended metrics
            dewpoint_avg_c=dewpoint_avg,
            pressure_avg_hpa=pressure_avg,
            wind_chill_min_c=wind_chill_min,
            wind_chill_max_c=wind_chill_max,
            snow_depth_cm=snow_depth,
            freezing_level_m=freezing_level,
            pop_max_pct=pop_max,
            cape_max_jkg=cape_max,
            # New metrics (v2.3)
            uv_index_max=uv_index_max,
            snow_new_sum_cm=fresh_snow_sum,
            wind_direction_avg_deg=wind_dir_avg,
            precip_type_dominant=precip_type_dom,
            # Issue #121: forecast confidence aggregation
            confidence_pct_min=confidence_min,
            # Merge aggregation config
            aggregation_config={
                **basis_summary.aggregation_config,
                "dewpoint_avg_c": "avg",
                "pressure_avg_hpa": "avg",
                "wind_chill_min_c": "min",
                "wind_chill_max_c": "max",
                "snow_depth_cm": "max",
                "freezing_level_m": "avg",
                "pop_max_pct": "max",
                "cape_max_jkg": "max",
                "uv_index_max": "max",
                "snow_new_sum_cm": "sum",
                "wind_direction_avg_deg": "avg",
                "precip_type_dominant": "max",
                "confidence_pct_min": "min",
            },
        )

        # Validate plausibility (extended metrics)
        self._validate_extended_plausibility(extended_summary)

        # Log extended metrics
        self._debug.add(f"extended_metrics: dewpoint={dewpoint_avg}°C")
        self._debug.add(f"extended_metrics: pressure={pressure_avg} hPa")
        self._debug.add(f"extended_metrics: wind_chill={wind_chill_min}°C")

        return extended_summary

    def _compute_dewpoint(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute dewpoint AVG. Returns dewpoint_avg_c."""
        dewpoints = [dp.dewpoint_c for dp in timeseries.data if dp.dewpoint_c is not None]
        return sum(dewpoints) / len(dewpoints) if dewpoints else None

    def _compute_pressure(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute pressure AVG. Returns pressure_avg_hpa."""
        pressures = [
            dp.pressure_msl_hpa for dp in timeseries.data if dp.pressure_msl_hpa is not None
        ]
        return sum(pressures) / len(pressures) if pressures else None

    def _compute_wind_chill(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute wind-chill MIN. Returns wind_chill_min_c."""
        wind_chills = [
            dp.wind_chill_c for dp in timeseries.data if dp.wind_chill_c is not None
        ]
        return min(wind_chills) if wind_chills else None

    def _compute_wind_chill_max(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute wind-chill MAX. Returns wind_chill_max_c (Issue #1135:
        Grundlage fuer das Hitzewarnungs-Plausibilitaets-Gate)."""
        wind_chills = [
            dp.wind_chill_c for dp in timeseries.data if dp.wind_chill_c is not None
        ]
        return max(wind_chills) if wind_chills else None

    def _compute_snow_depth(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute snow-depth MAX. Returns snow_depth_cm (optional, winter)."""
        snow_depths = [
            dp.snow_depth_cm for dp in timeseries.data if dp.snow_depth_cm is not None
        ]
        return max(snow_depths) if snow_depths else None

    def _compute_freezing_level(self, timeseries: NormalizedTimeseries) -> Optional[int]:
        """Compute freezing-level AVG. Returns freezing_level_m (optional, winter)."""
        freezing_levels = [
            dp.freezing_level_m for dp in timeseries.data if dp.freezing_level_m is not None
        ]
        return round(sum(freezing_levels) / len(freezing_levels)) if freezing_levels else None

    def _compute_pop(self, timeseries: NormalizedTimeseries) -> Optional[int]:
        """Compute precipitation probability MAX. Returns pop_max_pct."""
        pop_vals = [dp.pop_pct for dp in timeseries.data if dp.pop_pct is not None]
        return round(max(pop_vals)) if pop_vals else None

    def _compute_confidence_min(
        self, timeseries: NormalizedTimeseries
    ) -> Optional[int]:
        """Compute confidence MIN over all hourly data points (Issue #121).

        Worst-case aggregation: a single low-confidence hour makes the segment
        low-confidence. Returns None when no data point has confidence_pct set.
        """
        vals = [
            dp.confidence_pct
            for dp in timeseries.data
            if dp.confidence_pct is not None
        ]
        return min(vals) if vals else None

    def _compute_cape(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute CAPE MAX. Returns cape_max_jkg."""
        cape_vals = [dp.cape_jkg for dp in timeseries.data if dp.cape_jkg is not None]
        return max(cape_vals) if cape_vals else None

    def _compute_uv_index(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute UV-Index MAX. Returns uv_index_max (0-15 plausible)."""
        uv_vals = [dp.uv_index for dp in timeseries.data if dp.uv_index is not None]
        return max(uv_vals) if uv_vals else None

    def _compute_fresh_snow(self, timeseries: NormalizedTimeseries) -> Optional[float]:
        """Compute fresh snow SUM. Returns snow_new_sum_cm."""
        snow_vals = [dp.snow_new_24h_cm for dp in timeseries.data if dp.snow_new_24h_cm is not None]
        return sum(snow_vals) if snow_vals else None

    def _compute_wind_direction(self, timeseries: NormalizedTimeseries) -> Optional[int]:
        """
        Compute wind direction circular mean. Returns wind_direction_avg_deg.

        Uses atan2(mean(sin(rad)), mean(cos(rad))) to correctly average circular values.
        """
        dirs = [dp.wind_direction_deg for dp in timeseries.data if dp.wind_direction_deg is not None]
        if not dirs:
            return None
        sin_sum = sum(math.sin(math.radians(d)) for d in dirs)
        cos_sum = sum(math.cos(math.radians(d)) for d in dirs)
        avg_rad = math.atan2(sin_sum / len(dirs), cos_sum / len(dirs))
        avg_deg = math.degrees(avg_rad) % 360
        return round(avg_deg)

    def _compute_precip_type(self, timeseries: NormalizedTimeseries) -> Optional[PrecipType]:
        """
        Compute dominant precipitation type. Returns precip_type_dominant.

        Most frequent PrecipType; on tie, "worst" wins:
        FREEZING_RAIN > SNOW > MIXED > RAIN.
        """
        types = [dp.precip_type for dp in timeseries.data if dp.precip_type is not None]
        if not types:
            return None
        # Severity ordering for tie-breaking (higher = worse)
        severity = {
            PrecipType.RAIN: 0,
            PrecipType.MIXED: 1,
            PrecipType.SNOW: 2,
            PrecipType.FREEZING_RAIN: 3,
        }
        from collections import Counter
        counts = Counter(types)
        # Sort by (-count, -severity) so most frequent + worst wins
        return max(counts, key=lambda t: (counts[t], severity.get(t, 0)))

    def _validate_extended_plausibility(self, summary: SegmentWeatherSummary) -> None:
        """
        Validate extended metric plausibility and log warnings.

        Checks (logs WARNING if out of range, does NOT raise):
        - Dewpoint: -50°C to +40°C
        - Pressure: 800 to 1100 hPa
        - Wind-Chill: -60°C to +30°C
        - Snow-Depth: 0 to 1000 cm
        - Freezing-Level: 0 to 6000 m
        """
        if summary.dewpoint_avg_c is not None:
            if not (-50 <= summary.dewpoint_avg_c <= 40):
                self._debug.add(
                    f"WARNING: dewpoint_avg_c={summary.dewpoint_avg_c}°C out of plausible range (-50..40)"
                )

        if summary.pressure_avg_hpa is not None:
            if not (800 <= summary.pressure_avg_hpa <= 1100):
                self._debug.add(
                    f"WARNING: pressure_avg_hpa={summary.pressure_avg_hpa} hPa out of plausible range (800..1100)"
                )

        if summary.wind_chill_min_c is not None:
            if not (-60 <= summary.wind_chill_min_c <= 30):
                self._debug.add(
                    f"WARNING: wind_chill_min_c={summary.wind_chill_min_c}°C out of plausible range (-60..30)"
                )

        if summary.snow_depth_cm is not None:
            if not (0 <= summary.snow_depth_cm <= 1000):
                self._debug.add(
                    f"WARNING: snow_depth_cm={summary.snow_depth_cm} cm out of plausible range (0..1000)"
                )

        if summary.freezing_level_m is not None:
            if not (0 <= summary.freezing_level_m <= 6000):
                self._debug.add(
                    f"WARNING: freezing_level_m={summary.freezing_level_m} m out of plausible range (0..6000)"
                )

        if summary.pop_max_pct is not None:
            if not (0 <= summary.pop_max_pct <= 100):
                self._debug.add(
                    f"WARNING: pop_max_pct={summary.pop_max_pct}% out of plausible range (0..100)"
                )

        if summary.cape_max_jkg is not None:
            if not (0 <= summary.cape_max_jkg <= 5000):
                self._debug.add(
                    f"WARNING: cape_max_jkg={summary.cape_max_jkg} J/kg out of plausible range (0..5000)"
                )

        if summary.uv_index_max is not None:
            if not (0 <= summary.uv_index_max <= 15):
                self._debug.add(
                    f"WARNING: uv_index_max={summary.uv_index_max} out of plausible range (0..15)"
                )


# ===========================================================================
# Level-1 Aggregation ueber eine nackte Stundenliste (Issue #1285)
# SPEC: docs/specs/modules/compare_location_summary.md (AC-15)
# ===========================================================================

def summarize_points(points: list) -> Optional[SegmentWeatherSummary]:
    """Tages-Aggregat aus einer reinen ``ForecastDataPoint``-Liste.

    Duenner Wrapper um die KANONISCHEN Level-1-Regeln
    (``compute_basis_metrics`` — Regen SUM, Gewitter MAX-Ordinal, Sicht MIN —
    plus ``_compute_pop``/``_compute_uv_index`` fuer die beiden Groessen, die
    ``compute_basis_metrics`` nicht selbst fuellt). Es gibt hier bewusst KEINE
    eigene Rechenregel: derselbe Stundensatz muss im Orts-Vergleich denselben
    Tageswert ergeben wie im Trip-Briefing (AC-15).

    Der Aufrufer (Compare-Pfad) hat nur Stundendaten, keine
    ``NormalizedTimeseries`` — die Provider-Metadaten werden hier neutral
    gesetzt; ``compute_basis_metrics`` liest ausschliesslich ``.data``.

    ``None`` bei leerer Liste (kein Aggregat statt eines Null-Aggregats).
    """
    from app.models import ForecastMeta, Provider

    if not points:
        return None
    svc = WeatherMetricsService()
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="aggregate", grid_res_km=0.0),
        data=list(points),
    )
    summary = svc.compute_basis_metrics(ts)
    summary.pop_max_pct = svc._compute_pop(ts)
    summary.uv_index_max = svc._compute_uv_index(ts)
    summary.cape_max_jkg = svc._compute_cape(ts)
    summary.freezing_level_m = svc._compute_freezing_level(ts)
    return summary


# ===========================================================================
# Level-2 Aggregation: Stage-level (across segments)
# SPEC: docs/specs/modules/multi_day_trend.md v2.0
# ===========================================================================

def aggregate_stage(
    segments: list,
) -> SegmentWeatherSummary:
    """
    Level-2 aggregation: Combine all segment summaries of a stage
    into a single stage-level summary.

    Applies the same aggregation rule per metric (MAX over MAXes,
    MIN over MINs, SUM over SUMs, AVG over AVGs) using each
    segment's aggregation_config.

    Args:
        segments: All SegmentWeatherData of one stage (with .aggregated)

    Returns:
        SegmentWeatherSummary with stage-level aggregated values

    Raises:
        ValueError: If segments is empty or all segments have errors
    """
    if not segments:
        raise ValueError("Cannot aggregate empty segment list")

    # Filter out error segments
    summaries = [
        s.aggregated for s in segments
        if not s.has_error and s.aggregated
    ]
    if not summaries:
        raise ValueError("All segments have errors, cannot aggregate")

    # Get aggregation config from first valid summary
    agg_config = summaries[0].aggregation_config

    # Build result dict by applying aggregation rules
    result_fields: dict = {}
    for field_name, agg_rule in agg_config.items():
        values = [
            getattr(s, field_name) for s in summaries
            if getattr(s, field_name, None) is not None
        ]
        if not values:
            result_fields[field_name] = None
            continue

        if agg_rule == "max":
            if hasattr(values[0], "value"):
                # Issue #1214 Scheibe 6: Hybrid-Dict fuer generische Enum-Max-
                # Aggregation (ThunderLevel UND PrecipType) — nur der Thunder-
                # Anteil bezieht sich kanonisch aus thunder_ordinal, der
                # PrecipType-Anteil bleibt lokal (kein Duplikat, eigenes Konzept).
                from output.metric_format import thunder_ordinal
                _ENUM_ORDER = {
                    **{lvl: thunder_ordinal(lvl) for lvl in ThunderLevel},
                    PrecipType.RAIN: 0, PrecipType.SNOW: 1, PrecipType.MIXED: 2,
                }
                result_fields[field_name] = max(values, key=lambda v: _ENUM_ORDER.get(v, 0))
            else:
                result_fields[field_name] = max(values)
        elif agg_rule == "max_wmo_severity":
            # WMO code aggregation: pick most severe code by _WMO_SEVERITY ranking
            result_fields[field_name] = max(values, key=lambda c: _WMO_SEVERITY.get(c, 0))
        elif agg_rule == "min":
            result_fields[field_name] = min(values)
        elif agg_rule == "sum":
            result_fields[field_name] = sum(values)
        elif agg_rule == "avg":
            if field_name == "wind_direction_avg_deg":
                result_fields[field_name] = _circular_mean_deg(values)
            else:
                avg_val = sum(values) / len(values)
                if isinstance(values[0], int):
                    result_fields[field_name] = round(avg_val)
                else:
                    result_fields[field_name] = avg_val
        else:
            result_fields[field_name] = values[0]

    return SegmentWeatherSummary(
        **{k: v for k, v in result_fields.items() if k != "aggregation_config"},
        aggregation_config=agg_config,
    )


def _circular_mean_deg(degrees: list) -> int:
    """Circular mean for wind direction in degrees."""
    rads = [math.radians(float(d)) for d in degrees]
    sin_avg = sum(math.sin(r) for r in rads) / len(rads)
    cos_avg = sum(math.cos(r) for r in rads) / len(rads)
    return round(math.degrees(math.atan2(sin_avg, cos_avg))) % 360
