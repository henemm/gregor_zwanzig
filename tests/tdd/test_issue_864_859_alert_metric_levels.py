"""TDD RED — Issue #864/#859: Per-Metrik-Alert-Levels + Auto-Save AlertsTab.

Diese Tests beweisen die Python-Backend-Acceptance-Criteria der Spec
`docs/specs/modules/feat_864_859_alert_presets.md` aus Nutzersicht — KEINE Mocks.

Heute schlagen sie fehl (RED), weil:
- `src/services/alert_preset.py::expand_per_metric_levels` existiert noch nicht
  (ImportError oder AttributeError).
- `src/services/trip_alert.py` liest `metric_alert_levels` noch nicht aus
  `display_config` (Prioritätskette nicht implementiert).

Geprüfte ACs (Python-Backend):
- AC-11: `trip_alert.py` liest `metric_alert_levels` (pro-Metrik) vor `alert_preset`
  (global, legacy).
- AC-11b: `expand_per_metric_levels()` generiert für jede Nicht-'off'-Metrik eine
  AlertRule mit dem korrekten Schwellwert.
- AC-11c: `visibility` bekommt `AlertRuleKind.THRESHOLD_CROSSING`, alle anderen DELTA.
- AC-9b (Backend): Trips mit altem `alert_preset` (kein `metric_alert_levels`) laufen
  weiterhin durch den alten Expansion-Pfad (Backward-Compat).

SPEC: docs/specs/modules/feat_864_859_alert_presets.md
"""
from __future__ import annotations

from datetime import date

import pytest

from app.models import (
    AlertMetric,
    AlertRuleKind,
)
from app.trip import Stage, Trip, Waypoint


# ───────────────────────── Helpers ──────────────────────────────────────────

def _stage() -> Stage:
    return Stage(
        id="stage-1",
        name="Etappe 1",
        date=date(2026, 6, 23),
        waypoints=[Waypoint(id="wp-1", name="Start", lat=46.0, lon=11.0, elevation_m=800)],
    )


def _trip_with_legacy_preset(preset: str) -> Trip:
    """Baut einen Trip mit altem `display_config.alert_preset` (Legacy-Pfad)."""
    from app.models import UnifiedWeatherDisplayConfig
    config = UnifiedWeatherDisplayConfig(trip_id="tdd-864-legacy", alert_preset=preset)
    return Trip(
        id="tdd-864-legacy",
        name="TDD 864 Legacy Trip",
        stages=[_stage()],
        display_config=config,
    )


# ───────────────────────── AC-11b: expand_per_metric_levels ─────────────────

class TestExpandPerMetricLevels:
    """AC-11b: expand_per_metric_levels() generiert AlertRule-Liste."""

    def test_function_exists_in_alert_preset_module(self):
        """expand_per_metric_levels muss in services.alert_preset importierbar sein."""
        from services.alert_preset import expand_per_metric_levels  # noqa: F401

    def test_off_level_generates_no_rule(self):
        """Metrik mit level='off' → keine AlertRule in der Liste."""
        from services.alert_preset import expand_per_metric_levels
        levels = {"wind_gust": "off"}
        rules = expand_per_metric_levels(levels)
        assert len(rules) == 0, "level='off' darf keine Regel erzeugen"

    def test_standard_wind_gust_has_correct_delta_threshold(self):
        """wind_gust standard → AlertRule mit threshold=20 (Delta-Schwelle aus METRIC_PRESETS)."""
        from services.alert_preset import expand_per_metric_levels
        levels = {"wind_gust": "standard"}
        rules = expand_per_metric_levels(levels)
        assert len(rules) == 1
        rule = rules[0]
        assert str(rule.metric) in ("wind_gust", AlertMetric.WIND_GUST), (
            f"Metrik stimmt nicht: {rule.metric!r}"
        )
        assert rule.threshold == 20, (
            f"Standard-Delta-Schwelle für Böen muss 20 sein, ist {rule.threshold}"
        )

    def test_entspannt_level_uses_relaxed_threshold(self):
        """wind_gust entspannt → threshold=35 (Entspannt-Wert aus METRIC_PRESETS)."""
        from services.alert_preset import expand_per_metric_levels
        rules = expand_per_metric_levels({"wind_gust": "entspannt"})
        assert rules[0].threshold == 35

    def test_sensibel_level_uses_tight_threshold(self):
        """wind_gust sensibel → threshold=12 (Sensibel-Wert aus METRIC_PRESETS)."""
        from services.alert_preset import expand_per_metric_levels
        rules = expand_per_metric_levels({"wind_gust": "sensibel"})
        assert rules[0].threshold == 12

    def test_multiple_metrics_mixed_levels(self):
        """Mehrere Metriken: off wird übersprungen, andere erzeugen je eine Regel."""
        from services.alert_preset import expand_per_metric_levels
        levels = {
            "wind_gust": "standard",
            "precipitation_sum": "off",
            "visibility": "entspannt",
        }
        rules = expand_per_metric_levels(levels)
        assert len(rules) == 2, f"Erwartet 2 Regeln (precipitation_sum=off übersprungen), got {len(rules)}"
        metrics = {str(r.metric) for r in rules}
        assert "wind_gust" in metrics
        assert "visibility" in metrics
        assert "precipitation_sum" not in metrics


# ───────────────────────── AC-11c: visibility = THRESHOLD_CROSSING ───────────

class TestVisibilityThresholdCrossing:
    """AC-11c: visibility nutzt THRESHOLD_CROSSING, nicht DELTA."""

    def test_visibility_rule_has_threshold_crossing_kind(self):
        """visibility → AlertRuleKind.THRESHOLD_CROSSING (absoluter Schwellwert, nicht Delta)."""
        from services.alert_preset import expand_per_metric_levels
        rules = expand_per_metric_levels({"visibility": "standard"})
        assert len(rules) == 1
        rule = rules[0]
        assert rule.kind == AlertRuleKind.THRESHOLD_CROSSING, (
            f"visibility muss THRESHOLD_CROSSING sein, ist {rule.kind!r}"
        )

    def test_visibility_standard_threshold_is_1000(self):
        """visibility standard → threshold=1000 (m, unter dieser Grenze wird gewarnt)."""
        from services.alert_preset import expand_per_metric_levels
        rules = expand_per_metric_levels({"visibility": "standard"})
        assert rules[0].threshold == 1000, (
            f"visibility Standard-Schwelle muss 1000 m sein, ist {rules[0].threshold}"
        )

    def test_visibility_entspannt_threshold_is_500(self):
        """visibility entspannt → threshold=500 m."""
        from services.alert_preset import expand_per_metric_levels
        rules = expand_per_metric_levels({"visibility": "entspannt"})
        assert rules[0].threshold == 500

    def test_wind_gust_rule_has_delta_kind(self):
        """wind_gust → AlertRuleKind.DELTA (nicht THRESHOLD_CROSSING)."""
        from services.alert_preset import expand_per_metric_levels
        rules = expand_per_metric_levels({"wind_gust": "standard"})
        assert rules[0].kind == AlertRuleKind.DELTA, (
            f"wind_gust muss DELTA sein, ist {rules[0].kind!r}"
        )


# ───────────────────────── AC-11: trip_alert Prioritätskette ─────────────────

class TestTripAlertPriority:
    """AC-11: trip_alert.py liest metric_alert_levels vor alert_preset."""

    def test_metric_alert_levels_takes_priority_over_alert_preset(self):
        """
        Trip hat metric_alert_levels={'wind_gust':'off'} UND alert_preset='entspannt'.
        Erwartung: metric_alert_levels gewinnt → wind_gust hat KEINEN Threshold.
        Vor Implementierung schlägt dieser Test fehl, weil _select_change_detector
        nur alert_preset liest (→ wind_gust=35 statt None).
        """
        from app.models import UnifiedWeatherDisplayConfig
        from services.trip_alert import TripAlertService
        config = UnifiedWeatherDisplayConfig(trip_id="tdd-864-priority", alert_preset="entspannt")
        # metric_alert_levels existiert noch nicht als Modell-Feld → dynamisch setzen
        object.__setattr__(config, "metric_alert_levels", {"wind_gust": "off"})
        trip = Trip(
            id="tdd-864-priority",
            name="Priority Test",
            stages=[_stage()],
            display_config=config,
        )
        service = TripAlertService()
        detector = service._select_change_detector(trip)
        # Summary-Field-Schlüssel für wind_gust ist "gust_max_kmh" (via _ALERT_METRIC_TO_SUMMARY_FIELD)
        wind_threshold = detector._thresholds.get("gust_max_kmh")
        assert wind_threshold is None, (
            f"metric_alert_levels='off' muss alert_preset='entspannt' überschreiben, "
            f"aber gust_max_kmh-Threshold ist {wind_threshold!r} "
            f"(alert_preset hat fälschlicherweise gewonnen)"
        )

    # Issue #946: test_legacy_alert_preset_used_when_no_metric_levels entfernt —
    # der Legacy-alert_preset-Fallback in _select_change_detector wurde abgeschafft.
    # metric_alert_levels ist die einzige Alert-Quelle; ein Trip mit nur alert_preset
    # (ohne metric_alert_levels) feuert bewusst keine Alerts mehr.

    def test_metric_alert_levels_off_for_all_produces_no_rules(self):
        """metric_alert_levels mit allen Metriken='off' → leere Regel-Liste."""
        from services.alert_preset import expand_per_metric_levels
        levels = {
            "wind_gust": "off",
            "precipitation_sum": "off",
            "visibility": "off",
        }
        rules = expand_per_metric_levels(levels)
        assert rules == [], f"Alle 'off' → leere Regelliste, got {rules}"
