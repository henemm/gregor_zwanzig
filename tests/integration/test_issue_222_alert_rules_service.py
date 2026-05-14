"""
Integration tests for Issue #222 Workflow 1: TripAlertService detector selection.

Tests that TripAlertService picks the right WeatherChangeDetectionService factory:
- alert_rules with enabled=True → from_alert_rules()
- empty alert_rules → from_trip_config() / from_display_config() (Fallback)
- only disabled alert_rules → Fallback

NO MOCKS - real TripAlertService with synthetic Trip data (CLAUDE.md).

SPEC: docs/specs/modules/issue_222_w1_alert_rules_service.md
"""
from __future__ import annotations

from app.models import (
    AlertMetric,
    AlertRule,
    AlertRuleKind,
    AlertSeverity,
    TripReportConfig,
)
from app.trip import Stage, TimeWindow, Trip, Waypoint


def _trip() -> Trip:
    from datetime import date, time

    waypoint = Waypoint(
        id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0,
        time_window=TimeWindow(start=time(8, 0), end=time(10, 0)),
    )
    stage = Stage(id="T1", name="Tag 1", date=date.today(), waypoints=[waypoint])
    return Trip(id="test-trip-222", name="Test Trip 222", stages=[stage])


def _rule(metric: AlertMetric, threshold: float, enabled: bool = True) -> AlertRule:
    return AlertRule(
        id=f"r-{metric.value}",
        kind=AlertRuleKind.ABSOLUTE,
        metric=metric,
        threshold=threshold,
        severity=AlertSeverity.WARNING,
        enabled=enabled,
    )


class TestDetectorSelection:
    """Issue #222: TripAlertService._select_change_detector(trip)."""

    def test_active_alert_rules_select_from_alert_rules(self):
        """
        AC-1 (service-level): Trip with active absolute rule
        → _select_change_detector returns service from from_alert_rules.
        """
        from services.trip_alert import TripAlertService

        service = TripAlertService()
        trip = _trip()
        trip.alert_rules = [_rule(AlertMetric.WIND_GUST, 50.0, enabled=True)]

        detector = service._select_change_detector(trip)

        assert len(detector._absolute_rules) == 1
        assert detector._absolute_rules[0].metric == AlertMetric.WIND_GUST

    def test_ac4_empty_alert_rules_falls_back_to_trip_config(self):
        """
        AC-4: Trip with empty alert_rules + report_config
        → _select_change_detector returns service from from_trip_config.
        """
        from services.trip_alert import TripAlertService

        service = TripAlertService()
        trip = _trip()
        trip.alert_rules = []
        trip.report_config = TripReportConfig(
            trip_id=trip.id,
            change_threshold_temp_c=3.0,
            change_threshold_wind_kmh=15.0,
            change_threshold_precip_mm=5.0,
            alert_on_changes=True,
        )

        detector = service._select_change_detector(trip)

        assert detector._absolute_rules == []
        assert detector._thresholds["temp_min_c"] == 3.0
        assert detector._thresholds["wind_max_kmh"] == 15.0
        assert detector._thresholds["precip_sum_mm"] == 5.0

    def test_ac5_only_disabled_rules_falls_back_to_trip_config(self):
        """
        AC-5: Trip with only enabled=False rules + report_config
        → _select_change_detector falls back to from_trip_config.
        """
        from services.trip_alert import TripAlertService

        service = TripAlertService()
        trip = _trip()
        trip.alert_rules = [_rule(AlertMetric.WIND_GUST, 50.0, enabled=False)]
        trip.report_config = TripReportConfig(
            trip_id=trip.id,
            change_threshold_temp_c=3.0,
            alert_on_changes=True,
        )

        detector = service._select_change_detector(trip)

        assert detector._absolute_rules == []
        assert detector._thresholds["temp_min_c"] == 3.0

    def test_no_rules_no_config_returns_default_detector(self):
        """
        Regression: Trip without alert_rules, display_config, or report_config
        → _select_change_detector returns plain catalog-default service.
        """
        from app.metric_catalog import get_change_detection_map
        from services.trip_alert import TripAlertService

        service = TripAlertService()
        trip = _trip()
        trip.alert_rules = []
        trip.report_config = None
        trip.display_config = None

        detector = service._select_change_detector(trip)

        assert detector._absolute_rules == []
        assert detector._thresholds == get_change_detection_map()
