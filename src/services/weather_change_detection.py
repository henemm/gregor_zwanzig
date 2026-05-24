"""
Weather change detection service - detects significant weather changes.

Feature 2.5: Change-Detection
Compares cached vs fresh weather data and identifies changes exceeding thresholds.

SPEC: docs/specs/modules/weather_change_detection.md v2.0
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.models import (
        AlertRule,
        SegmentWeatherData,
        TripReportConfig,
        UnifiedWeatherDisplayConfig,
    )

from enum import Enum

from app.models import (
    AlertMetric,
    AlertRuleKind,
    AlertSeverity,
    ChangeSeverity,
    ThunderLevel,
    WeatherChange,
)

# Ordinal mapping for enum-type metrics (used for delta calculation)
_THUNDER_ORDINAL = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}

# --- Issue #222 Workflow 1: AlertRule → SegmentWeatherSummary field mappings ---

# Absolute-Rule metrics → summary field name (one field per metric)
_ALERT_METRIC_TO_SUMMARY_FIELD: dict[AlertMetric, str] = {
    AlertMetric.WIND_GUST: "gust_max_kmh",
    AlertMetric.PRECIPITATION_SUM: "precip_sum_mm",
    AlertMetric.TEMPERATURE_MIN: "temp_min_c",
    AlertMetric.TEMPERATURE_MAX: "temp_max_c",
    AlertMetric.THUNDER_LEVEL: "thunder_level_max",
    AlertMetric.SNOW_LINE: "freezing_level_m",
}

# Delta-Rule metrics → tuple of summary fields (metric-aggregating)
_ALERT_DELTA_METRIC_TO_FIELDS: dict[AlertMetric, tuple[str, ...]] = {
    AlertMetric.TEMPERATURE_CHANGE: ("temp_min_c", "temp_max_c"),
    AlertMetric.WIND_CHANGE: ("wind_max_kmh", "gust_max_kmh"),
    AlertMetric.PRECIPITATION_CHANGE: ("precip_sum_mm",),
}

# Comparison direction per absolute-rule metric ("above" or "below")
_ALERT_METRIC_COMPARISON: dict[AlertMetric, str] = {
    AlertMetric.WIND_GUST: "above",
    AlertMetric.PRECIPITATION_SUM: "above",
    AlertMetric.TEMPERATURE_MIN: "below",  # Kältealarm
    AlertMetric.TEMPERATURE_MAX: "above",
    AlertMetric.THUNDER_LEVEL: "above",
    AlertMetric.SNOW_LINE: "above",
}

# AlertSeverity (Issue #205) → ChangeSeverity (DTO for mail filter)
_RULE_SEVERITY_TO_CHANGE_SEVERITY: dict[AlertSeverity, ChangeSeverity] = {
    AlertSeverity.INFO: ChangeSeverity.MINOR,
    AlertSeverity.WARNING: ChangeSeverity.MODERATE,
    AlertSeverity.CRITICAL: ChangeSeverity.MAJOR,
}


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
        absolute_rules: Optional[list["AlertRule"]] = None,
        severity_overrides: Optional[dict[str, AlertSeverity]] = None,
    ):
        """
        Initialize with thresholds.

        Args:
            thresholds: Custom {field: threshold} dict.
                        If None, uses get_change_detection_map() defaults from MetricCatalog.
            absolute_rules: Issue #222 — Absolute AlertRules (kind=absolute, enabled=True).
                            Detected via comparison-direction (above/below) per metric.
            severity_overrides: Issue #222 — Maps summary-field → AlertSeverity for delta
                                detection, so rule.severity wins over ratio-based classify.
        """
        if thresholds is None:
            from app.metric_catalog import get_change_detection_map
            self._thresholds = get_change_detection_map()
        else:
            self._thresholds = dict(thresholds)
        self._absolute_rules: list["AlertRule"] = list(absolute_rules) if absolute_rules else []
        self._severity_overrides: dict[str, AlertSeverity] = (
            dict(severity_overrides) if severity_overrides else {}
        )

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
        Factory: Create service from per-metric display settings.

        Only metrics with enabled=True are included in detection (display flag;
        bewusst so seit Issue #131 — NICHT alert_enabled). User-set
        alert_threshold overrides MetricCatalog default.

        Args:
            display_config: Unified weather display config with per-metric alert settings

        Returns:
            WeatherChangeDetectionService with filtered thresholds
        """
        from app.metric_catalog import get_metric
        thresholds: dict[str, float] = {}
        for mc in display_config.metrics:
            if not mc.enabled:
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

    @classmethod
    def from_alert_rules(cls, rules: list["AlertRule"]) -> "WeatherChangeDetectionService":
        """Factory: Build a service from Issue-#205 AlertRule list (Issue #222 W1).

        Only rules with enabled=True contribute. Delta-rules fill _thresholds
        (compatible with existing detect_changes logic). Absolute-rules go to
        a separate _absolute_rules list (consumed by detect_changes). The rule
        severity overrides the ratio-based classification for both paths.

        Args:
            rules: List of AlertRule objects (typically from Trip.alert_rules).

        Returns:
            WeatherChangeDetectionService with only rule-driven thresholds
            (no MetricCatalog defaults — explicit opt-in via rules).
        """
        thresholds: dict[str, float] = {}
        absolute_rules: list["AlertRule"] = []
        severity_overrides: dict[str, AlertSeverity] = {}

        for rule in rules:
            if not rule.enabled:
                continue
            if rule.kind == AlertRuleKind.ABSOLUTE:
                absolute_rules.append(rule)
            elif rule.kind == AlertRuleKind.DELTA:
                fields = _ALERT_DELTA_METRIC_TO_FIELDS.get(rule.metric, ())
                if not fields:
                    # Issue #222 F004: Surface unmapped delta-metrics instead of
                    # silently dropping (e.g. WIND_GUST/TEMPERATURE_MIN as delta).
                    logger.warning(
                        "AlertRule kind=delta with unsupported metric %s (id=%s) — dropped",
                        rule.metric, rule.id,
                    )
                    continue
                for field_name in fields:
                    thresholds[field_name] = rule.threshold
                    severity_overrides[field_name] = rule.severity

        return cls(
            thresholds=thresholds,
            absolute_rules=absolute_rules,
            severity_overrides=severity_overrides,
        )

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
                # Issue #222: Rule-driven severity override (delta-rules from from_alert_rules)
                if metric in self._severity_overrides:
                    severity = _RULE_SEVERITY_TO_CHANGE_SEVERITY[
                        self._severity_overrides[metric]
                    ]
                else:
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
                    segment_id=str(new_data.segment.segment_id),
                )
                changes.append(change)

        # Issue #222 Workflow 1: Absolute-rule detection (new_value vs threshold)
        changes.extend(self._detect_absolute_changes(new_summary, new_data))

        return changes

    def _detect_absolute_changes(
        self,
        new_summary,
        new_data: "SegmentWeatherData",
    ) -> list[WeatherChange]:
        """Detect absolute-rule violations (Issue #222 W1).

        For each absolute rule:
        - Resolve summary field via _ALERT_METRIC_TO_SUMMARY_FIELD
        - Look up comparison direction (above/below)
        - Emit WeatherChange if threshold violated, using rule-severity
        """
        results: list[WeatherChange] = []
        for rule in self._absolute_rules:
            field_name = _ALERT_METRIC_TO_SUMMARY_FIELD.get(rule.metric)
            if not field_name:
                continue
            new_value = getattr(new_summary, field_name, None)
            if new_value is None:
                continue
            # Convert enum values (e.g., ThunderLevel) to ordinals
            if isinstance(new_value, Enum):
                new_value = _THUNDER_ORDINAL.get(new_value, 0)
            comparison = _ALERT_METRIC_COMPARISON.get(rule.metric, "above")
            # Issue #222 F003: THUNDER_LEVEL uses >= for above (user intent
            # "ab Stufe MED alarmieren" — threshold=1.0 must match MED=1).
            # Other numeric metrics keep strict > to avoid spurious noise.
            if rule.metric == AlertMetric.THUNDER_LEVEL:
                triggered = (
                    (comparison == "above" and new_value >= rule.threshold)
                    or (comparison == "below" and new_value <= rule.threshold)
                )
            else:
                triggered = (
                    (comparison == "above" and new_value > rule.threshold)
                    or (comparison == "below" and new_value < rule.threshold)
                )
            if not triggered:
                continue
            severity = _RULE_SEVERITY_TO_CHANGE_SEVERITY[rule.severity]
            results.append(
                WeatherChange(
                    metric=field_name,
                    old_value=0.0,  # Absolute rules have no "old" comparison
                    new_value=float(new_value),
                    delta=float(new_value) - float(rule.threshold),
                    threshold=float(rule.threshold),
                    severity=severity,
                    direction=comparison,  # "above" or "below"
                    segment_id=str(new_data.segment.segment_id),
                )
            )
        return results

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
