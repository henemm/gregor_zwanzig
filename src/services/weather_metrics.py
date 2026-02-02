"""
Weather metrics service - computes basis hiking metrics from timeseries.

Feature 2.2a: Basis-Metriken
Aggregates hourly weather values (MIN/MAX/AVG/SUM) over segment duration.

SPEC: docs/specs/modules/weather_metrics.md v1.0
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.debug import DebugBuffer
from app.models import NormalizedTimeseries, SegmentWeatherSummary, ThunderLevel


class WeatherMetricsService:
    """
    Service for computing basic weather metrics from timeseries data.

    Aggregates hourly weather values (MIN/MAX/AVG/SUM) over segment duration
    to populate SegmentWeatherSummary fields.
    """

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

        # Order: NONE < MED < HIGH
        ordering = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}
        return max(levels, key=lambda x: ordering[x])

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
# Legacy Classes (pre-Feature 2.2a)
# Used by src/web/pages/compare.py - kept for backward compatibility
# ============================================================================


@dataclass
class HourlyCell:
    """
    Stunden-Zelle für UI und Email.

    Used by compare.py for hourly weather display.
    """

    hour: int  # 9, 10, 11, ...
    symbol: str  # "☀️", "🌤️", "⛅", "☁️"
    temp_c: int  # -5, 12, ...
    precip_symbol: str  # "🌨️", "🌧️", ""
    precip_amount: Optional[float]  # 2.5, None wenn kein Niederschlag
    precip_unit: str  # "cm", "mm", ""
    wind_kmh: int  # 15
    gust_kmh: int  # 25
    wind_dir: str  # "SW", "N", "NE"


class CloudStatus(str, Enum):
    """
    Cloud layer position classification (elevation-based).

    Used by compare.py for cloud status display.
    """

    ABOVE_CLOUDS = "above_clouds"  # Location is above the cloud layer
    IN_CLOUDS = "in_clouds"  # Location is within the cloud layer
    NONE = "none"  # No relevant cloud layer info
