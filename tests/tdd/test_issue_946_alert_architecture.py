"""TDD RED — Issue #946: Alert-Architektur — metric_alert_levels als einzige Quelle.

Diese Tests beweisen die Acceptance-Criteria der Spec `fix-946-alert-single-source`
aus Nutzersicht — KEINE Mocks, echte Objekte aus dem Produktionscode.

Hintergrund (Bug): `_select_change_detector()` in `src/services/trip_alert.py`
hat zu viele implizite Fallback-Schichten. Ist ein Trip NICHT für Alerts
konfiguriert (`metric_alert_levels=None`, `alert_preset=None`), aber hat aktivierte
Anzeige-Metriken, landet der Code in `from_display_config()` und feuert Alerts für
ALLE aktivierten Anzeige-Metriken — obwohl der Nutzer das nie konfiguriert hat.

Ziel: `metric_alert_levels` ist die EINZIGE Datenquelle. Null = keine Alerts.

Heute schlagen diese Tests fehl (RED), weil:
- AC-1/AC-3: `_select_change_detector()` fällt weiterhin auf `from_display_config()`
  zurück → produziert unkonfigurierte Thresholds (`gust_max_kmh: 20.0`).
- AC-8: `expand_per_metric_levels({'freezing_level': 'standard'})` liefert `[]`,
  weil `freezing_level` nicht in der `_PRESET_TABLE` steht (dort heißt es `snow_line`).
- AC-2: das Migrations-Skript `scripts/migrate_946_alert_levels.py` existiert noch nicht.

Geprüfte ACs:
- AC-1: Trip mit metric_alert_levels=None UND alert_preset=None → kein Alert,
  Detektor mit 0 aktiven Regeln (NoOp).
- AC-3: `from_display_config()` / `from_trip_config()` / `alert_preset`-Zweig werden
  NICHT mehr aufgerufen — nur `metric_alert_levels` wird ausgewertet.
- AC-7: Trip mit gesetztem metric_alert_levels → Alerts feuern wie konfiguriert (Regression).
- AC-8: `expand_per_metric_levels()` verarbeitet `freezing_level` und erzeugt korrekte Regel.
- AC-2: Migrations-Skript konvertiert alert_preset → metric_alert_levels.

SPEC: docs/specs/modules/ (fix-946-alert-single-source)
"""
from __future__ import annotations

from datetime import date

import pytest

from app.models import (
    AlertMetric,
    AlertRuleKind,
    MetricConfig,
    UnifiedWeatherDisplayConfig,
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


def _trip(
    *,
    metric_alert_levels=None,
    alert_preset=None,
    enabled_metrics=None,
) -> Trip:
    """Baut einen minimalen Trip mit definierter Alert-/Display-Konfiguration.

    enabled_metrics: Liste von metric_id-Strings, die als aktivierte Anzeige-Metrik
                     gesetzt werden (um den from_display_config-Fallback zu triggern).
    """
    metrics = [
        MetricConfig(metric_id=mid, enabled=True)
        for mid in (enabled_metrics or [])
    ]
    config = UnifiedWeatherDisplayConfig(
        trip_id="tdd-946",
        metrics=metrics,
        alert_preset=alert_preset,
        metric_alert_levels=metric_alert_levels,
    )
    return Trip(
        id="tdd-946",
        name="TDD 946 Trip",
        stages=[_stage()],
        display_config=config,
    )


def _detector_thresholds(detector) -> dict:
    """Sammelt alle aktiven Threshold-Felder eines Detektors (Delta + absolut + crossing)."""
    result = dict(getattr(detector, "_thresholds", {}) or {})
    return result


def _detector_is_noop(detector) -> bool:
    """True, wenn der Detektor keine aktiven Alert-Regeln trägt (NoOp).

    Prüft Delta-Thresholds, absolute Regeln und Threshold-Crossing-Regeln.
    """
    if _detector_thresholds(detector):
        return False
    if getattr(detector, "_absolute_rules", None):
        return False
    if getattr(detector, "_threshold_crossing_rules", None):
        return False
    return True


# ───────────────────────── Gruppe 1: AC-1 — Null = keine Alerts ─────────────

class TestAC1NullMeansNoAlerts:
    """AC-1: metric_alert_levels=None + alert_preset=None → NoOp-Detektor."""

    def test_unconfigured_trip_with_display_metrics_is_noop(self):
        """
        Trip hat aktivierte Anzeige-Metrik 'gust', aber weder metric_alert_levels
        noch alert_preset. Erwartung: Detektor OHNE Alert-Regeln (NoOp).

        RED heute: Code fällt auf from_display_config() zurück und setzt
        gust_max_kmh=20.0 → Detektor ist NICHT NoOp.
        """
        from services.trip_alert import TripAlertService

        trip = _trip(metric_alert_levels=None, alert_preset=None, enabled_metrics=["gust"])
        service = TripAlertService()
        detector = service._select_change_detector(trip)

        assert _detector_is_noop(detector), (
            "Unkonfigurierter Trip (metric_alert_levels=None, alert_preset=None) muss "
            f"einen NoOp-Detektor liefern, aber Thresholds sind "
            f"{_detector_thresholds(detector)!r} (from_display_config-Fallback feuert)."
        )

    def test_unconfigured_trip_has_no_gust_threshold(self):
        """
        Konkreter Nachweis: 'gust' ist als Anzeige-Metrik aktiv, aber nicht als
        Alert konfiguriert → gust_max_kmh darf KEINEN Threshold haben.

        RED heute: gust_max_kmh=20.0 aus MetricCatalog via from_display_config.
        """
        from services.trip_alert import TripAlertService

        trip = _trip(metric_alert_levels=None, alert_preset=None, enabled_metrics=["gust"])
        service = TripAlertService()
        detector = service._select_change_detector(trip)

        gust = _detector_thresholds(detector).get("gust_max_kmh")
        assert gust is None, (
            f"Ohne konfigurierte Alerts darf gust_max_kmh keinen Threshold haben, "
            f"ist aber {gust!r}."
        )

    def test_empty_metric_alert_levels_is_noop(self):
        """metric_alert_levels={} (leer) + alert_preset=None → NoOp (kein Fallback)."""
        from services.trip_alert import TripAlertService

        trip = _trip(metric_alert_levels={}, alert_preset=None, enabled_metrics=["gust", "temperature"])
        service = TripAlertService()
        detector = service._select_change_detector(trip)

        assert _detector_is_noop(detector), (
            "Leeres metric_alert_levels muss NoOp bleiben, "
            f"Thresholds: {_detector_thresholds(detector)!r}."
        )


# ───────────────────────── Gruppe 2: AC-3 — Keine Fallback-Aufrufe ──────────

class TestAC3NoFallbackCalls:
    """AC-3: from_display_config / from_trip_config / alert_preset werden nicht aufgerufen."""

    def _spy(self, monkeypatch, method_name):
        """Ersetzt eine Factory-Classmethod durch einen Zähler-Spy (kein Mock-Objekt).

        Es wird echt aufgerufen, aber der Aufruf wird gezählt — kein Verhalten
        vorgetäuscht, daher konform mit der No-Mock-Regel (echter Code läuft weiter).
        """
        from services.weather_change_detection import WeatherChangeDetectionService

        original = getattr(WeatherChangeDetectionService, method_name).__func__
        calls = {"count": 0}

        def wrapper(cls, *args, **kwargs):
            calls["count"] += 1
            return original(cls, *args, **kwargs)

        monkeypatch.setattr(
            WeatherChangeDetectionService,
            method_name,
            classmethod(wrapper),
        )
        return calls

    def test_from_display_config_not_called_for_unconfigured_trip(self, monkeypatch):
        """
        Unkonfigurierter Trip mit aktivierten Anzeige-Metriken.
        from_display_config() darf NICHT aufgerufen werden.

        RED heute: from_display_config wird aufgerufen (Fallback-Zweig aktiv).
        """
        from services.trip_alert import TripAlertService

        calls = self._spy(monkeypatch, "from_display_config")
        trip = _trip(metric_alert_levels=None, alert_preset=None, enabled_metrics=["gust"])
        service = TripAlertService()
        service._select_change_detector(trip)

        assert calls["count"] == 0, (
            f"from_display_config() darf nicht mehr aufgerufen werden, "
            f"wurde aber {calls['count']}× aufgerufen (Fallback nicht entfernt)."
        )

    def test_from_trip_config_not_called_for_unconfigured_trip(self, monkeypatch):
        """from_trip_config() darf nicht als Fallback aufgerufen werden."""
        from services.trip_alert import TripAlertService

        calls = self._spy(monkeypatch, "from_trip_config")
        trip = _trip(metric_alert_levels=None, alert_preset=None, enabled_metrics=["gust"])
        service = TripAlertService()
        service._select_change_detector(trip)

        assert calls["count"] == 0, (
            f"from_trip_config() darf nicht mehr aufgerufen werden, "
            f"wurde aber {calls['count']}× aufgerufen."
        )

    def test_alert_preset_branch_not_used(self, monkeypatch):
        """
        Selbst wenn ein alter alert_preset gesetzt ist, darf der alert_preset-Zweig
        (expand_preset) nicht mehr aufgerufen werden — metric_alert_levels ist einzige Quelle.

        RED heute: alert_preset='standard' triggert expand_preset().
        """
        import services.alert_preset as ap
        from services.trip_alert import TripAlertService

        original = ap.expand_preset
        calls = {"count": 0}

        def wrapper(name):
            calls["count"] += 1
            return original(name)

        monkeypatch.setattr(ap, "expand_preset", wrapper)

        trip = _trip(metric_alert_levels=None, alert_preset="standard", enabled_metrics=[])
        service = TripAlertService()
        service._select_change_detector(trip)

        assert calls["count"] == 0, (
            f"expand_preset() (alert_preset-Zweig) darf nicht mehr aufgerufen werden, "
            f"wurde aber {calls['count']}× aufgerufen — metric_alert_levels ist die einzige Quelle."
        )


# ───────────────────────── Gruppe 3: AC-7 — Regression ──────────────────────

class TestAC7ConfiguredTripStillFires:
    """AC-7: Trip mit gesetztem metric_alert_levels feuert Alerts wie konfiguriert."""

    def test_wind_gust_standard_produces_gust_threshold(self):
        """
        Trip mit metric_alert_levels={'wind_gust':'standard'} → Detektor enthält
        eine Delta-Regel für gust_max_kmh mit Schwelle 20.

        Sollte bereits grün sein (Regression-Schutz), trotzdem geschrieben.
        """
        from services.trip_alert import TripAlertService

        trip = _trip(metric_alert_levels={"wind_gust": "standard"}, alert_preset=None)
        service = TripAlertService()
        detector = service._select_change_detector(trip)

        thresholds = _detector_thresholds(detector)
        assert thresholds.get("gust_max_kmh") == 20.0, (
            f"metric_alert_levels={{'wind_gust':'standard'}} muss gust_max_kmh=20.0 liefern, "
            f"ist {thresholds.get('gust_max_kmh')!r} (Thresholds: {thresholds!r})."
        )

    def test_configured_trip_is_not_noop(self):
        """Ein konfigurierter Trip darf KEIN NoOp-Detektor sein."""
        from services.trip_alert import TripAlertService

        trip = _trip(metric_alert_levels={"wind_gust": "standard"}, alert_preset=None)
        service = TripAlertService()
        detector = service._select_change_detector(trip)

        assert not _detector_is_noop(detector), (
            "Konfigurierter Trip darf kein NoOp sein — es müssen Alert-Regeln aktiv sein."
        )


# ───────────────────────── Gruppe 4: AC-8 — freezing_level ──────────────────

class TestAC8FreezingLevelExpansion:
    """AC-8: expand_per_metric_levels verarbeitet freezing_level korrekt."""

    def test_freezing_level_produces_a_rule(self):
        """
        expand_per_metric_levels({'freezing_level':'standard'}) muss mindestens
        eine AlertRule erzeugen.

        RED heute: liefert [] — freezing_level ist nicht in der _PRESET_TABLE
        (dort heißt die verwandte Metrik snow_line).
        """
        from services.alert_preset import expand_per_metric_levels

        rules = expand_per_metric_levels({"freezing_level": "standard"})
        assert len(rules) >= 1, (
            "freezing_level muss eine Alert-Regel erzeugen, "
            f"expand_per_metric_levels lieferte aber {rules!r}."
        )

    def test_freezing_level_rule_has_positive_threshold(self):
        """Die erzeugte freezing_level-Regel hat metric='freezing_level' und threshold > 0."""
        from services.alert_preset import expand_per_metric_levels

        rules = expand_per_metric_levels({"freezing_level": "standard"})
        assert len(rules) >= 1, f"Keine Regel erzeugt: {rules!r}"
        rule = rules[0]
        assert str(rule.metric) in ("freezing_level", getattr(AlertMetric, "FREEZING_LEVEL", "freezing_level")), (
            f"Regel-Metrik muss freezing_level sein, ist {rule.metric!r}."
        )
        assert rule.threshold > 0, (
            f"freezing_level-Schwelle muss > 0 sein, ist {rule.threshold!r}."
        )

    def test_freezing_level_off_produces_no_rule(self):
        """freezing_level='off' → keine Regel (konsistent mit anderen Metriken)."""
        from services.alert_preset import expand_per_metric_levels

        rules = expand_per_metric_levels({"freezing_level": "off"})
        assert rules == [], f"level='off' darf keine Regel erzeugen, got {rules!r}."


# ───────────────────────── Gruppe 5: AC-2 — Migrations-Skript ───────────────

class TestAC2MigrationScript:
    """AC-2: scripts/migrate_946_alert_levels.py konvertiert alert_preset → metric_alert_levels."""

    def test_migration_module_is_importable(self):
        """
        Das Migrations-Skript muss existieren und importierbar sein.

        RED heute: ModuleNotFoundError — Skript existiert noch nicht.
        """
        import importlib

        mod = importlib.import_module("scripts.migrate_946_alert_levels")
        assert hasattr(mod, "migrate_trip"), (
            "Migrations-Skript muss eine Funktion migrate_trip(trip_json: dict) -> dict haben."
        )

    def test_migrate_trip_converts_preset_to_metric_levels(self):
        """
        migrate_trip mit alert_preset='standard' (ohne metric_alert_levels) →
        befüllt metric_alert_levels aus dem Preset.

        RED heute: Skript existiert nicht (ImportError im import).
        """
        from scripts.migrate_946_alert_levels import migrate_trip

        trip_json = {
            "id": "tdd-946-migrate",
            "display_config": {
                "alert_preset": "standard",
                "metric_alert_levels": None,
            },
        }
        result = migrate_trip(trip_json)
        levels = result["display_config"]["metric_alert_levels"]
        assert isinstance(levels, dict) and levels, (
            f"metric_alert_levels muss nach Migration ein nicht-leeres dict sein, ist {levels!r}."
        )

    def test_migrate_standard_preset_yields_all_13_metrics(self):
        """
        alert_preset='standard' → alle 13 Metriken im Ergebnis, jede mit level='standard'.

        RED heute: Skript existiert nicht.
        """
        from scripts.migrate_946_alert_levels import migrate_trip

        trip_json = {
            "id": "tdd-946-13",
            "display_config": {"alert_preset": "standard", "metric_alert_levels": None},
        }
        result = migrate_trip(trip_json)
        levels = result["display_config"]["metric_alert_levels"]
        assert len(levels) == 13, (
            f"Preset 'standard' muss 13 Metriken erzeugen, sind aber {len(levels)}: {list(levels)!r}."
        )
        assert all(v == "standard" for v in levels.values()), (
            f"Jede Metrik muss level='standard' haben, got {levels!r}."
        )

    def test_migrate_leaves_existing_metric_levels_untouched(self):
        """
        Trip hat bereits metric_alert_levels → Migration überschreibt sie NICHT.

        RED heute: Skript existiert nicht.
        """
        from scripts.migrate_946_alert_levels import migrate_trip

        existing = {"wind_gust": "sensibel"}
        trip_json = {
            "id": "tdd-946-keep",
            "display_config": {
                "alert_preset": "standard",
                "metric_alert_levels": dict(existing),
            },
        }
        result = migrate_trip(trip_json)
        assert result["display_config"]["metric_alert_levels"] == existing, (
            "Bestehende metric_alert_levels dürfen von der Migration nicht überschrieben werden."
        )
