"""
Unit tests for Issue #222 Workflow 1: WeatherChangeDetectionService.from_alert_rules().

Tests the new factory method and detection logic for AlertRule-based change detection:
- Absolute rules with above/below comparison (per-metric direction)
- Delta rules with rule-severity override
- Disabled rules are ignored
- Mixed kinds fire independently

NO MOCKS - real WeatherChangeDetectionService with synthetic data (CLAUDE.md).

SPEC: docs/specs/modules/issue_222_w1_alert_rules_service.md
"""
from datetime import datetime, timezone

import pytest

from app.models import (
    AlertMetric,
    AlertRule,
    AlertRuleKind,
    AlertSeverity,
    ChangeSeverity,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from services.weather_change_detection import WeatherChangeDetectionService


# --- Test Helpers ---------------------------------------------------------

def _segment() -> TripSegment:
    now = datetime.now(timezone.utc)
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1500),
        start_time=now,
        end_time=now,
        duration_hours=2.0,
        distance_km=5.0,
        ascent_m=500,
        descent_m=0,
    )


def _data(**summary_kwargs) -> SegmentWeatherData:
    """Build SegmentWeatherData with the given summary fields."""
    return SegmentWeatherData(
        segment=_segment(),
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.GEOSPHERE,
                model="test",
                run=datetime.now(timezone.utc),
                grid_res_km=1.0,
                interp="test",
            ),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="geosphere",
    )


def _rule(
    kind: AlertRuleKind,
    metric: AlertMetric,
    threshold: float,
    severity: AlertSeverity = AlertSeverity.WARNING,
    enabled: bool = True,
    unit: str = "",
) -> AlertRule:
    return AlertRule(
        id=f"r-{metric.value}",
        kind=kind,
        metric=metric,
        threshold=threshold,
        severity=severity,
        enabled=enabled,
        unit=unit,
    )


# --- Factory Tests --------------------------------------------------------

class TestFromAlertRulesFactory:
    """Factory: enabled-Filter and rule classification by kind."""

    def test_empty_rules_creates_service_with_no_active_rules(self):
        """
        GIVEN: Empty rule list
        WHEN: from_alert_rules([])
        THEN: Service has no absolute rules and no delta thresholds
        """
        service = WeatherChangeDetectionService.from_alert_rules([])
        assert service._absolute_rules == []
        assert service._thresholds == {}

    def test_disabled_rules_are_skipped(self):
        """
        GIVEN: Rule with enabled=False
        WHEN: from_alert_rules([rule])
        THEN: Rule is not included
        """
        rules = [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.WIND_GUST, 50.0, enabled=False)]
        service = WeatherChangeDetectionService.from_alert_rules(rules)
        assert service._absolute_rules == []
        assert service._thresholds == {}

    def test_absolute_rule_goes_to_absolute_rules_list(self):
        """
        GIVEN: enabled absolute rule
        WHEN: from_alert_rules([rule])
        THEN: Rule appears in _absolute_rules; since #816 the ABSOLUTE branch also
              seeds the MetricCatalog-Δ-default into _thresholds via setdefault,
              so absolute-only trips get symmetric Δ-alerts.
        """
        rules = [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.WIND_GUST, 50.0)]
        service = WeatherChangeDetectionService.from_alert_rules(rules)
        assert len(service._absolute_rules) == 1
        assert service._absolute_rules[0].metric == AlertMetric.WIND_GUST
        # Seit #816: absolute Regel seedet zusätzlich den MetricCatalog-Δ-Default
        # ins _thresholds (setdefault), damit absolute-only-Trips symmetrische
        # Δ-Alerts bekommen. Der Katalog-Default für gust_max_kmh ist 20.0.
        assert service._thresholds == {"gust_max_kmh": 20.0}

    def test_delta_rule_fills_thresholds_for_mapped_fields(self):
        """
        GIVEN: enabled delta rule TEMPERATURE_CHANGE
        WHEN: from_alert_rules([rule])
        THEN: temp_min_c and temp_max_c are in _thresholds with the rule threshold
        """
        rules = [_rule(AlertRuleKind.DELTA, AlertMetric.TEMPERATURE_CHANGE, 5.0)]
        service = WeatherChangeDetectionService.from_alert_rules(rules)
        assert service._thresholds.get("temp_min_c") == 5.0
        assert service._thresholds.get("temp_max_c") == 5.0


# --- Absolute Above (AC-1, AC-2) -----------------------------------------

class TestAbsoluteAboveDetection:
    """AC-1, AC-2: WIND_GUST above-comparison."""

    def test_ac1_wind_gust_above_threshold_fires(self):
        """
        AC-1: GIVEN absolute WIND_GUST threshold=50, WHEN new gust=60,
        THEN one WeatherChange with severity=MODERATE, direction=above.
        """
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.WIND_GUST, 50.0,
                   severity=AlertSeverity.WARNING)]
        )
        old = _data(gust_max_kmh=40.0)
        new = _data(gust_max_kmh=60.0)

        changes = service.detect_changes(old, new)

        assert len(changes) == 1
        assert changes[0].metric == "gust_max_kmh"
        assert changes[0].direction == "above"
        assert changes[0].severity == ChangeSeverity.MODERATE

    def test_ac2_wind_gust_below_threshold_no_fire(self):
        """
        AC-2: GIVEN absolute WIND_GUST threshold=50, WHEN new gust=40,
        THEN no changes (above-comparison: 40 not > 50).
        """
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.WIND_GUST, 50.0)]
        )
        old = _data(gust_max_kmh=30.0)
        new = _data(gust_max_kmh=40.0)

        assert service.detect_changes(old, new) == []


# --- Absolute Below (AC-7, AC-8) — Kältealarm ----------------------------

class TestAbsoluteBelowDetection:
    """AC-7, AC-8: TEMPERATURE_MIN below-comparison (winter cold alert)."""

    def test_ac7_temperature_min_below_threshold_fires(self):
        """
        AC-7: GIVEN absolute TEMPERATURE_MIN threshold=-5.0,
        WHEN new temp_min_c=-8.0, THEN one WeatherChange direction=below,
        severity=MODERATE.
        """
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.TEMPERATURE_MIN, -5.0,
                   severity=AlertSeverity.WARNING)]
        )
        old = _data(temp_min_c=-3.0)
        new = _data(temp_min_c=-8.0)

        changes = service.detect_changes(old, new)

        assert len(changes) == 1
        assert changes[0].metric == "temp_min_c"
        assert changes[0].direction == "below"
        assert changes[0].severity == ChangeSeverity.MODERATE

    def test_ac8_temperature_min_above_threshold_no_fire(self):
        """
        AC-8: GIVEN absolute TEMPERATURE_MIN threshold=-5.0,
        WHEN new temp_min_c=-2.0, THEN no changes (-2 > -5, not below).
        """
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.TEMPERATURE_MIN, -5.0)]
        )
        old = _data(temp_min_c=-3.0)
        new = _data(temp_min_c=-2.0)

        assert service.detect_changes(old, new) == []


# --- Delta + Severity Override (AC-3) ------------------------------------

class TestDeltaRuleSeverityOverride:
    """AC-3: Delta-Rule severity comes from rule, not from ratio."""

    def test_ac3_delta_rule_severity_from_rule_not_ratio(self):
        """
        AC-3: GIVEN delta TEMPERATURE_CHANGE threshold=5.0, severity=WARNING,
        WHEN temp_max delta=6.0 (ratio 1.2 = MINOR ratio-based),
        THEN WeatherChange has severity=MODERATE (rule-override, not ratio).
        """
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.DELTA, AlertMetric.TEMPERATURE_CHANGE, 5.0,
                   severity=AlertSeverity.WARNING)]
        )
        old = _data(temp_max_c=15.0, temp_min_c=10.0)
        new = _data(temp_max_c=21.0, temp_min_c=10.0)

        changes = service.detect_changes(old, new)

        temp_max_changes = [c for c in changes if c.metric == "temp_max_c"]
        assert len(temp_max_changes) == 1
        assert temp_max_changes[0].severity == ChangeSeverity.MODERATE


# --- Absolute THUNDER_LEVEL >= Comparison (AC-9, F003 fix-loop 1) --------

class TestAbsoluteThunderLevelDetection:
    """AC-9: THUNDER_LEVEL uses >= for above-comparison (user intent: 'ab MED alarmieren')."""

    def test_ac9_thunder_level_med_at_threshold_fires(self):
        """
        AC-9: GIVEN absolute THUNDER_LEVEL threshold=1.0, severity=WARNING,
        WHEN new thunder_level_max=ThunderLevel.MED (ordinal=1),
        THEN one WeatherChange with metric=thunder_level_max, direction=above,
        severity=MODERATE (>=-comparison fires at ordinal 1 >= 1.0).
        """
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.THUNDER_LEVEL, 1.0,
                   severity=AlertSeverity.WARNING)]
        )
        old = _data(thunder_level_max=ThunderLevel.NONE)
        new = _data(thunder_level_max=ThunderLevel.MED)

        changes = service.detect_changes(old, new)

        assert len(changes) == 1
        assert changes[0].metric == "thunder_level_max"
        assert changes[0].direction == "above"
        assert changes[0].severity == ChangeSeverity.MODERATE

    def test_ac9_thunder_level_high_with_threshold_2_fires(self):
        """
        AC-9 (Folge): Schwelle 2.0 fasst HIGH (ordinal 2 >= 2.0), nicht MED.
        """
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.THUNDER_LEVEL, 2.0,
                   severity=AlertSeverity.CRITICAL)]
        )
        # MED with threshold 2.0 must NOT fire
        assert service.detect_changes(
            _data(thunder_level_max=ThunderLevel.NONE),
            _data(thunder_level_max=ThunderLevel.MED),
        ) == []
        # HIGH with threshold 2.0 fires
        changes = service.detect_changes(
            _data(thunder_level_max=ThunderLevel.NONE),
            _data(thunder_level_max=ThunderLevel.HIGH),
        )
        assert len(changes) == 1
        assert changes[0].severity == ChangeSeverity.MAJOR


# --- Mixed Kinds (AC-6) --------------------------------------------------

class TestMixedKinds:
    """AC-6: Absolute + delta rules fire independently."""

    def test_ac6_mixed_absolute_and_delta_both_fire(self):
        """
        AC-6: GIVEN absolute WIND_GUST=50 AND delta TEMPERATURE_CHANGE=5,
        WHEN gust=60 (above) AND temp_max delta=7 (above threshold),
        THEN two changes, each with its rule-severity.
        """
        rules = [
            _rule(AlertRuleKind.ABSOLUTE, AlertMetric.WIND_GUST, 50.0,
                  severity=AlertSeverity.WARNING),
            _rule(AlertRuleKind.DELTA, AlertMetric.TEMPERATURE_CHANGE, 5.0,
                  severity=AlertSeverity.CRITICAL),
        ]
        service = WeatherChangeDetectionService.from_alert_rules(rules)

        old = _data(gust_max_kmh=30.0, temp_max_c=15.0, temp_min_c=10.0)
        new = _data(gust_max_kmh=60.0, temp_max_c=22.0, temp_min_c=10.0)

        changes = service.detect_changes(old, new)
        by_metric = {c.metric: c for c in changes}

        assert "gust_max_kmh" in by_metric
        assert by_metric["gust_max_kmh"].direction == "above"
        assert by_metric["gust_max_kmh"].severity == ChangeSeverity.MODERATE

        assert "temp_max_c" in by_metric
        assert by_metric["temp_max_c"].severity == ChangeSeverity.MAJOR


# --- Issue #821: Absolute/Δ-Dedup bei include_absolute=True ---------------

class TestIssue821AbsoluteDeltaDedup:
    """#821: Eine absolute Regel darf bei include_absolute=True denselben Sprung
    NICHT doppelt melden (geseedeter Δ + Absolut-Pfad). Ein Sprung = ein Change.
    """

    def test_ac1_absolute_thunder_high_fires_once(self):
        """AC-1: absolute THUNDER_LEVEL=2.0, NONE→HIGH, include_absolute=True →
        genau EIN Change (Absolut-Pfad, severity MAJOR), kein doppelter Δ-Change."""
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.THUNDER_LEVEL, 2.0,
                   severity=AlertSeverity.CRITICAL)]
        )
        changes = service.detect_changes(
            _data(thunder_level_max=ThunderLevel.NONE),
            _data(thunder_level_max=ThunderLevel.HIGH),
        )
        assert len(changes) == 1
        assert changes[0].metric == "thunder_level_max"
        assert changes[0].direction == "above"
        assert changes[0].severity == ChangeSeverity.MAJOR

    def test_ac2_absolute_thunder_below_threshold_no_fire(self):
        """AC-2: absolute THUNDER_LEVEL=2.0, NONE→MED (1<2), include_absolute=True →
        KEIN Change (auch der geseedete Δ darf nicht feuern)."""
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.THUNDER_LEVEL, 2.0,
                   severity=AlertSeverity.CRITICAL)]
        )
        changes = service.detect_changes(
            _data(thunder_level_max=ThunderLevel.NONE),
            _data(thunder_level_max=ThunderLevel.MED),
        )
        assert changes == []

    def test_ac3_seeded_delta_still_fires_on_alert_path(self):
        """AC-3: absolute WIND_GUST=50, include_absolute=False (Forecast-Alert-Pfad),
        Böen-Sprung 30→60 → der geseedete Δ-Change feuert weiterhin (genau einer)."""
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.WIND_GUST, 50.0,
                   severity=AlertSeverity.WARNING)]
        )
        changes = service.detect_changes(
            _data(gust_max_kmh=30.0),
            _data(gust_max_kmh=60.0),
            include_absolute=False,
        )
        assert len(changes) == 1
        assert changes[0].metric == "gust_max_kmh"
        # Δ-Pfad: direction increase/decrease (kein above/below)
        assert changes[0].direction in ("increase", "decrease")

    def test_ac4_explicit_delta_plus_absolute_both_fire(self):
        """AC-4: explizite Δ-Regel TEMPERATURE_CHANGE=5 UND absolute TEMPERATURE_MAX=20
        auf demselben Feld temp_max_c. Sprung 15→25 verletzt beide → BEIDE Changes
        bleiben (explizit gesetzter Δ wird NIE unterdrückt)."""
        rules = [
            _rule(AlertRuleKind.DELTA, AlertMetric.TEMPERATURE_CHANGE, 5.0,
                  severity=AlertSeverity.CRITICAL),
            _rule(AlertRuleKind.ABSOLUTE, AlertMetric.TEMPERATURE_MAX, 20.0,
                  severity=AlertSeverity.WARNING),
        ]
        service = WeatherChangeDetectionService.from_alert_rules(rules)
        old = _data(temp_max_c=15.0, temp_min_c=10.0)
        new = _data(temp_max_c=25.0, temp_min_c=10.0)

        changes = service.detect_changes(old, new)  # include_absolute=True
        temp_changes = [c for c in changes if c.metric == "temp_max_c"]
        assert len(temp_changes) == 2
        directions = {c.direction for c in temp_changes}
        # Ein Δ-Change (increase) UND ein Absolut-Change (above)
        assert directions == {"increase", "above"}

    def test_ac4_explicit_delta_plus_absolute_reversed_order(self):
        """AC-4 (Ordering): Regel-Reihenfolge umgekehrt (absolute zuerst) — explizit
        gesetzter Δ darf trotzdem nicht als 'geseedet' gelten."""
        rules = [
            _rule(AlertRuleKind.ABSOLUTE, AlertMetric.TEMPERATURE_MAX, 20.0,
                  severity=AlertSeverity.WARNING),
            _rule(AlertRuleKind.DELTA, AlertMetric.TEMPERATURE_CHANGE, 5.0,
                  severity=AlertSeverity.CRITICAL),
        ]
        service = WeatherChangeDetectionService.from_alert_rules(rules)
        old = _data(temp_max_c=15.0, temp_min_c=10.0)
        new = _data(temp_max_c=25.0, temp_min_c=10.0)

        changes = service.detect_changes(old, new)
        temp_changes = [c for c in changes if c.metric == "temp_max_c"]
        assert len(temp_changes) == 2
        assert {c.direction for c in temp_changes} == {"increase", "above"}

    def test_ac5_threshold_map_unchanged_seed_preserved(self):
        """AC-5: Dedup ändert die _thresholds-Map NICHT — Seed bleibt erhalten
        (F222-A bleibt gültig: gust_max_kmh seeded mit Katalog-Default 20.0)."""
        service = WeatherChangeDetectionService.from_alert_rules(
            [_rule(AlertRuleKind.ABSOLUTE, AlertMetric.WIND_GUST, 50.0)]
        )
        assert service._thresholds == {"gust_max_kmh": 20.0}
