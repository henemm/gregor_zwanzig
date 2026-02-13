"""
Weather change detection service - detects significant weather changes.

Feature 2.5: Change-Detection
Compares cached vs fresh weather data and identifies changes exceeding thresholds.

SPEC: docs/specs/modules/weather_change_detection.md v2.0
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models import SegmentWeatherData, TripReportConfig, UnifiedWeatherDisplayConfig

from enum import Enum

from app.models import ChangeSeverity, ThunderLevel, WeatherChange

# Ordinal mapping for enum-type metrics (used for delta calculation)
_THUNDER_ORDINAL = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}


class WeatherChangeDetectionService:
    """
    Service for detecting significant weather changes.

    Compares two SegmentWeatherSummary objects and identifies changes
    that exceed configured thresholds.

    v2.0: Thresholds derived from MetricCatalog via get_change_detection_map().
    User-configured overrides from TripReportConfig applied via from_trip_config().

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
        thresholds: Optional[dict[str, float]] = None,
    ):
        """
        Initialize with thresholds.

        Args:
            thresholds: Custom {field: threshold} dict.
                        If None, uses get_change_detection_map() defaults from MetricCatalog.
        """
        if thresholds is None:
            from app.metric_catalog import get_change_detection_map
            self._thresholds = get_change_detection_map()
        else:
            self._thresholds = dict(thresholds)

    @classmethod
    def from_trip_config(cls, config: "TripReportConfig") -> "WeatherChangeDetectionService":
        """
        Factory: Create service with user-configured thresholds.

        Starts with MetricCatalog defaults, then overrides
        temp/wind/precip thresholds from TripReportConfig.

        Args:
            config: User's trip report configuration

        Returns:
            WeatherChangeDetectionService with merged thresholds
        """
        from app.metric_catalog import get_change_detection_map
        thresholds = get_change_detection_map()

        # Override temp-related fields
        for field_name in ("temp_min_c", "temp_max_c", "temp_avg_c",
                           "wind_chill_min_c", "dewpoint_avg_c"):
            if field_name in thresholds:
                thresholds[field_name] = config.change_threshold_temp_c

        # Override wind-related fields
        for field_name in ("wind_max_kmh", "gust_max_kmh"):
            if field_name in thresholds:
                thresholds[field_name] = config.change_threshold_wind_kmh

        # Override precip-related fields
        for field_name in ("precip_sum_mm",):
            if field_name in thresholds:
                thresholds[field_name] = config.change_threshold_precip_mm

        return cls(thresholds=thresholds)

    @classmethod
    def from_display_config(cls, display_config: "UnifiedWeatherDisplayConfig") -> "WeatherChangeDetectionService":
        """
        Factory: Create service from per-metric alert settings.

        Only metrics with alert_enabled=True are included in detection.
        User-set alert_threshold overrides MetricCatalog default.

        Args:
            display_config: Unified weather display config with per-metric alert settings

        Returns:
            WeatherChangeDetectionService with filtered thresholds
        """
        from app.metric_catalog import get_metric
        thresholds: dict[str, float] = {}
        for mc in display_config.metrics:
            if not mc.alert_enabled:
                continue
            try:
                metric_def = get_metric(mc.metric_id)
            except KeyError:
                continue
            if metric_def.default_change_threshold is None:
                continue  # Enum metrics (thunder, precip_type) — skip
            threshold = mc.alert_threshold if mc.alert_threshold is not None else metric_def.default_change_threshold
            for field in metric_def.summary_fields.values():
                thresholds[field] = threshold
        return cls(thresholds=thresholds)

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
            # Get old and new values
            old_value = getattr(old_summary, metric, None)
            new_value = getattr(new_summary, metric, None)

            # Skip if either is None
            if old_value is None or new_value is None:
                continue

            # Convert enum values to ordinals for delta calculation
            if isinstance(old_value, Enum):
                old_value = _THUNDER_ORDINAL.get(old_value, 0)
                new_value = _THUNDER_ORDINAL.get(new_value, 0)

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
