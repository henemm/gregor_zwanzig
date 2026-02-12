"""
Weather change detection service - detects significant weather changes.

Feature 2.5: Change-Detection
Compares cached vs fresh weather data and identifies changes exceeding thresholds.

SPEC: docs/specs/modules/weather_change_detection.md v1.0
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import SegmentWeatherData

from app.models import ChangeSeverity, WeatherChange


class WeatherChangeDetectionService:
    """
    Service for detecting significant weather changes.

    Compares two SegmentWeatherSummary objects and identifies changes
    that exceed configured thresholds.

    Example:
        >>> service = WeatherChangeDetectionService()
        >>> changes = service.detect_changes(old_data, new_data)
        >>> for change in changes:
        ...     print(f"{change.metric}: {change.delta:+.1f} ({change.severity})")
        temp_max_c: +7.0 (moderate)
        wind_max_kmh: +25.0 (major)
    """

    def __init__(
        self,
        temp_threshold_c: float = 5.0,
        wind_threshold_kmh: float = 20.0,
        precip_threshold_mm: float = 10.0,
        visibility_threshold_m: int = 1000,
        cloud_threshold_pct: int = 30,
        humidity_threshold_pct: int = 20,
        pressure_threshold_hpa: float = 10.0,
    ):
        """
        Initialize with configurable thresholds.

        Args:
            temp_threshold_c: Temperature delta threshold (default: ±5°C)
            wind_threshold_kmh: Wind speed delta threshold (default: ±20 km/h)
            precip_threshold_mm: Precipitation delta threshold (default: ±10 mm)
            visibility_threshold_m: Visibility delta threshold (default: ±1000 m)
            cloud_threshold_pct: Cloud cover delta threshold (default: ±30%)
            humidity_threshold_pct: Humidity delta threshold (default: ±20%)
            pressure_threshold_hpa: Pressure delta threshold (default: ±10 hPa)
        """
        self._thresholds = {
            "temp_min_c": temp_threshold_c,
            "temp_max_c": temp_threshold_c,
            "temp_avg_c": temp_threshold_c,
            "wind_max_kmh": wind_threshold_kmh,
            "gust_max_kmh": wind_threshold_kmh,
            "precip_sum_mm": precip_threshold_mm,
            "cloud_avg_pct": cloud_threshold_pct,
            "humidity_avg_pct": humidity_threshold_pct,
            "visibility_min_m": visibility_threshold_m,
            "dewpoint_avg_c": temp_threshold_c,
            "pressure_avg_hpa": pressure_threshold_hpa,
            "wind_chill_min_c": temp_threshold_c,
            "snow_depth_cm": 10.0,  # Default for snow
            "freezing_level_m": 200,  # Default for freezing level
            "pop_max_pct": 20,  # ±20% change in rain probability
            "cape_max_jkg": 500.0,  # ±500 J/kg change in convective energy
        }

    def detect_changes(
        self,
        old_data: "SegmentWeatherData",
        new_data: "SegmentWeatherData",
    ) -> list[WeatherChange]:
        """
        Detect significant changes between old and new weather data.

        Args:
            old_data: Cached weather data
            new_data: Fresh weather data

        Returns:
            List of WeatherChange objects for metrics exceeding thresholds.
            Empty list if no significant changes detected.

        Algorithm:
            1. Extract old and new summaries
            2. For each metric:
               a. Skip if either value is None
               b. Calculate delta (new - old)
               c. Check if |delta| > threshold
               d. If yes: classify severity, create WeatherChange
            3. Return all detected changes
        """
        old_summary = old_data.aggregated
        new_summary = new_data.aggregated
        changes = []

        # Compare all numeric metrics
        for metric, threshold in self._thresholds.items():
            # Skip thunder_level_max (enum, special handling needed)
            if metric == "thunder_level_max":
                continue

            # Get old and new values
            old_value = getattr(old_summary, metric, None)
            new_value = getattr(new_summary, metric, None)

            # Skip if either is None
            if old_value is None or new_value is None:
                continue

            # Calculate delta
            delta = new_value - old_value

            # Check if exceeds threshold
            if abs(delta) > threshold:
                severity = self._classify_severity(abs(delta), threshold)
                direction = "increase" if delta > 0 else "decrease"

                change = WeatherChange(
                    metric=metric,
                    old_value=float(old_value),
                    new_value=float(new_value),
                    delta=float(delta),
                    threshold=float(threshold),
                    severity=severity,
                    direction=direction,
                )
                changes.append(change)

        return changes

    def _classify_severity(self, delta: float, threshold: float) -> ChangeSeverity:
        """
        Classify change severity based on delta/threshold ratio.

        Thresholds:
        - MINOR: 10-50% over threshold (1.0x - <1.5x)
        - MODERATE: 50-100% over threshold (1.5x - <2.0x)
        - MAJOR: >100% over threshold (>=2.0x)

        Args:
            delta: Absolute delta value
            threshold: Configured threshold

        Returns:
            ChangeSeverity enum value
        """
        ratio = abs(delta) / threshold

        if ratio >= 2.0:
            return ChangeSeverity.MAJOR
        elif ratio >= 1.5:
            return ChangeSeverity.MODERATE
        else:
            return ChangeSeverity.MINOR
