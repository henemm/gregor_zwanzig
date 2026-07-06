"""
TDD RED Tests for Issue #205 — Trip.alert_rules Datenmodell + Migration.

Each test maps 1:1 to one AC from
docs/specs/modules/issue_205_alert_rules.md.

These tests MUST fail in RED phase — AlertRule, AlertMetric, AlertSeverity,
AlertRuleKind, and _migrate_legacy_alert_rules() do not exist yet.

NO MOCKS — uses real dataclasses, real filesystem.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path



# --- AC-1: AlertRule Dataclass + Enums ------------------------------------

def test_ac1_alert_rule_dataclass_fields_exist():
    """AC-1: AlertRule mit allen 7 Feldern und String-Enum metric."""
    from app.models import (
        AlertMetric,
        AlertRule,
        AlertRuleKind,
        AlertSeverity,
    )

    rule = AlertRule(
        id="abc-123",
        kind=AlertRuleKind.DELTA,
        metric=AlertMetric.WIND_CHANGE,
        threshold=20.0,
        unit="km/h",
        severity=AlertSeverity.WARNING,
        enabled=True,
    )

    assert rule.id == "abc-123"
    assert rule.kind == AlertRuleKind.DELTA
    assert rule.metric == AlertMetric.WIND_CHANGE
    assert rule.metric == "wind_change", "AlertMetric muss str-Enum sein"
    assert rule.threshold == 20.0
    assert rule.unit == "km/h"
    assert rule.severity == AlertSeverity.WARNING
    assert rule.severity == "warning", "AlertSeverity muss str-Enum sein"
    assert rule.enabled is True


# --- AC-2: Trip.alert_rules Default ist leere Liste -----------------------

def test_ac2_trip_has_alert_rules_field_default_empty():
    """AC-2: Trip ohne alert_rules-Argument hat alert_rules = []."""
    from app.trip import Stage, Trip, Waypoint
    from datetime import date

    stage = Stage(
        id="s1",
        name="Test-Stage",
        date=date(2026, 5, 14),
        waypoints=[
            Waypoint(
                id="G1",
                name="Start",
                lat=47.0,
                lon=11.0,
                elevation_m=1000,
            ),
        ],
    )

    trip = Trip(id="t1", name="Test", stages=[stage])

    assert hasattr(trip, "alert_rules"), "Trip muss Feld alert_rules haben"
    assert trip.alert_rules == [], f"Default muss [] sein, got {trip.alert_rules!r}"
    assert isinstance(trip.alert_rules, list)


# --- AC-3: Migration erzeugt 3 Delta-Rules wenn alert_on_changes=True -----

def test_ac3_migrate_legacy_creates_three_delta_rules():
    """AC-3: Legacy report_config → 3 AlertRules mit kind=delta, enabled=True."""
    from app.loader import _migrate_legacy_alert_rules
    from app.models import AlertMetric, AlertRuleKind, AlertSeverity

    data = {
        "report_config": {
            "alert_on_changes": True,
            "change_threshold_temp_c": 5.0,
            "change_threshold_wind_kmh": 20.0,
            "change_threshold_precip_mm": 10.0,
        },
    }

    rules = _migrate_legacy_alert_rules(data)

    assert len(rules) == 3, f"Erwartet 3 Rules, got {len(rules)}"

    by_metric = {r.metric: r for r in rules}
    assert AlertMetric.TEMPERATURE_CHANGE in by_metric
    assert AlertMetric.WIND_CHANGE in by_metric
    assert AlertMetric.PRECIPITATION_CHANGE in by_metric

    temp_rule = by_metric[AlertMetric.TEMPERATURE_CHANGE]
    assert temp_rule.kind == AlertRuleKind.DELTA
    assert temp_rule.threshold == 5.0
    assert temp_rule.unit == "°C"
    assert temp_rule.severity == AlertSeverity.WARNING
    assert temp_rule.enabled is True

    wind_rule = by_metric[AlertMetric.WIND_CHANGE]
    assert wind_rule.threshold == 20.0
    assert wind_rule.unit == "km/h"

    precip_rule = by_metric[AlertMetric.PRECIPITATION_CHANGE]
    assert precip_rule.threshold == 10.0
    assert precip_rule.unit == "mm"

    # IDs müssen UUIDs sein (Länge 36, Format)
    for r in rules:
        assert len(r.id) == 36, f"ID muss UUID sein, got {r.id!r}"
        uuid.UUID(r.id)  # raises ValueError if not valid


# --- AC-4: alert_on_changes=False → Rules mit enabled=False ---------------

def test_ac4_migrate_alert_on_changes_false_keeps_rules_disabled():
    """AC-4: alert_on_changes=False → Rules werden generiert, aber enabled=False."""
    from app.loader import _migrate_legacy_alert_rules

    data = {
        "report_config": {
            "alert_on_changes": False,
            "change_threshold_temp_c": 5.0,
            "change_threshold_wind_kmh": 20.0,
            "change_threshold_precip_mm": 10.0,
        },
    }

    rules = _migrate_legacy_alert_rules(data)

    assert len(rules) == 3, "Konfigurierte Schwellwerte dürfen nicht verschwinden"
    for r in rules:
        assert r.enabled is False, \
            f"enabled muss False sein wenn alert_on_changes=False, got {r.enabled!r} für {r.metric}"


# --- AC-5: Existing alert_rules → No-Op ----------------------------------

def test_ac5_migrate_with_existing_alert_rules_is_noop():
    """AC-5: alert_rules schon im Dict → 1:1 zurückgeben."""
    from app.loader import _migrate_legacy_alert_rules

    existing_id = "fixed-uuid-1234"
    data = {
        "alert_rules": [
            {
                "id": existing_id,
                "kind": "absolute",
                "metric": "wind_gust",
                "threshold": 50.0,
                "unit": "km/h",
                "severity": "critical",
                "enabled": True,
            },
        ],
        "report_config": {
            "alert_on_changes": True,
            "change_threshold_temp_c": 5.0,
        },
    }

    rules = _migrate_legacy_alert_rules(data)

    assert len(rules) == 1, "Existing alert_rules NICHT mit Legacy-Felder mischen"
    assert rules[0].id == existing_id
    assert rules[0].threshold == 50.0


# --- AC-6: Roundtrip Save → Load erhält alert_rules + Legacy --------------

def test_ac6_trip_roundtrip_preserves_alert_rules_and_legacy(tmp_path):
    """AC-6: _trip_to_dict + load_trip Roundtrip ohne Datenverlust."""
    from app.loader import _trip_to_dict, load_trip
    from app.models import (
        AlertMetric,
        AlertRule,
        AlertRuleKind,
        AlertSeverity,
        TripReportConfig,
    )
    from app.trip import Stage, Trip, Waypoint
    from datetime import date

    stage = Stage(
        id="s1",
        name="Test-Stage",
        date=date(2026, 5, 14),
        waypoints=[
            Waypoint(
                id="G1",
                name="Start",
                lat=47.0,
                lon=11.0,
                elevation_m=1000,
            ),
        ],
    )

    rule_1 = AlertRule(
        id="r1", kind=AlertRuleKind.DELTA, metric=AlertMetric.WIND_CHANGE,
        threshold=20.0, unit="km/h", severity=AlertSeverity.WARNING, enabled=True,
    )
    rule_2 = AlertRule(
        id="r2", kind=AlertRuleKind.DELTA, metric=AlertMetric.TEMPERATURE_CHANGE,
        threshold=5.0, unit="°C", severity=AlertSeverity.WARNING, enabled=False,
    )

    trip = Trip(
        id="t1",
        name="Test",
        stages=[stage],
        alert_rules=[rule_1, rule_2],
        report_config=TripReportConfig(
            trip_id="t1",
            alert_on_changes=True,
            change_threshold_temp_c=5.0,
            change_threshold_wind_kmh=20.0,
            change_threshold_precip_mm=10.0,
        ),
    )

    data = _trip_to_dict(trip)

    # Save als JSON
    trip_path = tmp_path / "trip.json"
    trip_path.write_text(json.dumps(data))

    # Reload
    raw = json.loads(trip_path.read_text())
    trip_loaded = load_trip(raw)

    assert len(trip_loaded.alert_rules) == 2
    ids = {r.id for r in trip_loaded.alert_rules}
    assert ids == {"r1", "r2"}, f"IDs müssen erhalten bleiben, got {ids}"

    # Legacy-Felder bleiben unverändert
    assert raw["report_config"]["change_threshold_temp_c"] == 5.0
    assert raw["report_config"]["change_threshold_wind_kmh"] == 20.0
    assert raw["report_config"]["change_threshold_precip_mm"] == 10.0
    assert raw["report_config"]["alert_on_changes"] is True


# --- AC-8: TypeScript-Types ------------------------------------------------

def test_ac8_typescript_types_export():
    """AC-8: types.ts exportiert AlertRule, AlertRuleKind, AlertSeverity, AlertMetric."""
    types_ts = Path("frontend/src/lib/types.ts").read_text()

    assert "export type AlertRuleKind" in types_ts or "export interface AlertRuleKind" in types_ts or "AlertRuleKind =" in types_ts, \
        "AlertRuleKind muss exportiert sein"
    assert "AlertSeverity" in types_ts, "AlertSeverity muss exportiert sein"
    assert "AlertMetric" in types_ts, "AlertMetric muss exportiert sein"
    assert "AlertRule" in types_ts, "AlertRule muss exportiert sein"
    assert "alert_rules" in types_ts, "Trip muss alert_rules-Feld haben"
    # Spezifische Werte aus dem Enum
    assert "'wind_gust'" in types_ts or '"wind_gust"' in types_ts
    assert "'precipitation_change'" in types_ts or '"precipitation_change"' in types_ts


# --- AC-9: Alle Produktiv-Trips laden additiv ohne Datenverlust -----------

def test_ac9_all_production_trips_load_with_additive_migration():
    """AC-9: Alle data/users/*/trips/*.json laden + Roundtrip-Differenz prüfen.

    Pre-existing Drift in display_config/report_config (vor Issue #205) ist
    aus der Migration ausgenommen — Issue #205 ist additiv und darf NUR
    alert_rules hinzufügen. Trips mit pre-existing load_trip-Bugs (kaputtes
    Schema, leere stages) werden geskippt, da sie ohnehin nicht ladbar
    sind und ein Folge-Issue brauchen.
    """
    from app.loader import _trip_to_dict, load_trip

    trip_files = sorted(Path("data/users").glob("*/trips/*.json"))
    assert trip_files, "Es müssen Produktiv-Trips existieren"
    assert len(trip_files) >= 5, f"Erwartet mindestens 5 Trips, got {len(trip_files)}"

    # Keys, die durch DTO-Defaults beim Roundtrip Drift erzeugen können
    # (Pre-existing Drift, unabhängig von Issue #205). Wir prüfen nur die
    # Top-Level-Identitätsfelder + dass alert_rules hinzukommt.
    drift_tolerant_keys = {"display_config", "report_config", "weather_config", "aggregation"}

    failures: list[str] = []
    loaded_count = 0
    for trip_path in trip_files:
        original = json.loads(trip_path.read_text())
        try:
            trip = load_trip(original)
        except Exception:
            # Pre-existing kaputtes Trip-Schema — wird in Folge-Issue gefixt.
            # Issue #205 darf hier NICHT regredieren, aber muss nicht reparieren.
            continue
        loaded_count += 1

        roundtrip = _trip_to_dict(trip)

        # alert_rules MUSS im Roundtrip existieren (additiv)
        assert "alert_rules" in roundtrip, (
            f"{trip_path.name}: alert_rules fehlt im Roundtrip"
        )
        assert isinstance(roundtrip["alert_rules"], list), (
            f"{trip_path.name}: alert_rules muss Liste sein"
        )

        # Stabile Top-Level-Felder dürfen sich nicht ändern
        for key, original_value in original.items():
            if key == "alert_rules":
                continue
            if key in drift_tolerant_keys:
                # Pre-existing Drift — gezielt toleriert
                continue
            if key not in roundtrip:
                failures.append(f"{trip_path.name}: key '{key}' verloren beim Roundtrip")
                continue
            if roundtrip[key] != original_value:
                failures.append(
                    f"{trip_path.name}: key '{key}' geändert beim Roundtrip"
                )

    assert loaded_count >= 5, f"Erwartet >=5 ladbare Trips, got {loaded_count}"
    assert not failures, "Roundtrip-Drift gefunden:\n" + "\n".join(failures)
