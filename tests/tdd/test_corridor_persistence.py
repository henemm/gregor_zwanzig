"""
TDD RED Tests — Issue #1231 Slice 1: Trip.corridors Datenmodell (Persistenz).

AC-1 (docs/specs/modules/issue_1231_korridor_editor.md): Ein Trip ohne
corridors-Feld wird geladen und gespeichert -> alert_rules bleibt
unveraendert erhalten, corridors wird additiv ergaenzt (Read-Modify-Write,
kein Replace, kein bestehendes Feld geht verloren).

Diese Tests treiben die Slice-1-Erweiterung von app.models.Corridor +
Trip.corridors + loader.py (_trip_to_dict/load_trip) — noch nicht
implementiert, daher ROT.

Persistenz-Pfad folgt dem bestehenden Muster aus
tests/tdd/test_alert_rules_model.py::test_ac6_trip_roundtrip_preserves_alert_rules_and_legacy
(echte Datei via tmp_path, kein Mock).

NO MOCKS — echte Trip-/AlertRule-Objekte, echtes Dateisystem via tmp_path.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.loader import _trip_to_dict, load_trip
from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity
from app.trip import Stage, Trip, Waypoint


def _make_stage() -> Stage:
    return Stage(
        id="s1",
        name="Test-Stage",
        date=date(2026, 7, 12),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1000),
        ],
    )


# --- AC-1a: Bestehende alert_rules unveraendert + corridors additiv leer ---

def test_alert_rules_untouched_and_corridors_additive_empty(tmp_path: Path) -> None:
    """AC-1: Trip mit bestehenden alert_rules laden+speichern -> alert_rules
    byte-identisch erhalten UND corridors additiv als leere Liste vorhanden
    und serialisierbar."""
    rule_1 = AlertRule(
        id="r1", kind=AlertRuleKind.DELTA, metric=AlertMetric.WIND_CHANGE,
        threshold=20.0, unit="km/h", severity=AlertSeverity.WARNING, enabled=True,
    )
    rule_2 = AlertRule(
        id="r2", kind=AlertRuleKind.DELTA, metric=AlertMetric.TEMPERATURE_CHANGE,
        threshold=5.0, unit="°C", severity=AlertSeverity.WARNING, enabled=False,
    )
    trip = Trip(id="t1", name="Test", stages=[_make_stage()], alert_rules=[rule_1, rule_2])

    data = _trip_to_dict(trip)
    trip_path = tmp_path / "trip.json"
    trip_path.write_text(json.dumps(data, indent=2))

    loaded = load_trip(trip_path)

    # Bestehendes Verhalten (Issue #205) — darf durch #1231 nicht regredieren.
    assert len(loaded.alert_rules) == 2
    ids = {r.id for r in loaded.alert_rules}
    assert ids == {"r1", "r2"}

    # NEU (Issue #1231, Slice 1): corridors additiv, leer, typed.
    assert hasattr(loaded, "corridors"), "Trip muss Feld corridors haben (additiv)"
    assert loaded.corridors == []
    assert "corridors" in data, "_trip_to_dict muss corridors immer emittieren (auch leer)"
    assert data["corridors"] == []


# --- AC-1b: gesetzter Corridor-Eintrag uebersteht Roundtrip verlustfrei ----

def test_corridor_entry_roundtrips_lossless_with_open_bounds(tmp_path: Path) -> None:
    """AC-1: Corridor mit einseitig offener Grenze (range=[None, max]),
    notify, mark und optionalem prio uebersteht Save->Load verlustfrei."""
    from app.models import Corridor  # noch nicht vorhanden -> ImportError (ROT)

    corridor = Corridor(
        metric="wind_gust",
        range=[None, 45.0],
        notify=True,
        mark=False,
        prio="hoch",
    )
    trip = Trip(id="t2", name="Korridor-Test", stages=[_make_stage()], corridors=[corridor])

    data = _trip_to_dict(trip)
    trip_path = tmp_path / "trip.json"
    trip_path.write_text(json.dumps(data, indent=2))

    loaded = load_trip(trip_path)

    assert len(loaded.corridors) == 1
    loaded_corridor = loaded.corridors[0]
    assert loaded_corridor.metric == "wind_gust"
    assert loaded_corridor.range == [None, 45.0]
    assert loaded_corridor.notify is True
    assert loaded_corridor.mark is False
    assert loaded_corridor.prio == "hoch"


def test_corridor_entry_with_both_bounds_and_no_prio_roundtrips(tmp_path: Path) -> None:
    """AC-1: Corridor mit beidseitiger Grenze und ohne prio (optional)
    uebersteht Save->Load verlustfrei; prio bleibt None statt Platzhalter."""
    from app.models import Corridor  # noch nicht vorhanden -> ImportError (ROT)

    corridor = Corridor(
        metric="temp_max_c",
        range=[-5.0, 25.0],
        notify=False,
        mark=True,
    )
    trip = Trip(id="t3", name="Korridor-Beide-Grenzen", stages=[_make_stage()], corridors=[corridor])

    data = _trip_to_dict(trip)
    trip_path = tmp_path / "trip.json"
    trip_path.write_text(json.dumps(data, indent=2))

    loaded = load_trip(trip_path)

    assert len(loaded.corridors) == 1
    loaded_corridor = loaded.corridors[0]
    assert loaded_corridor.range == [-5.0, 25.0]
    assert loaded_corridor.notify is False
    assert loaded_corridor.mark is True
    assert loaded_corridor.prio is None


# --- AC-1c: unbekannte Bestandsfelder gehen beim Roundtrip nicht verloren -

def test_unknown_legacy_fields_and_corridors_survive_roundtrip_together(tmp_path: Path) -> None:
    """AC-1 (Read-Modify-Write-Nachweis): Ein rohes Bestands-Trip-JSON mit
    einem unmodellierten Top-Level-Feld (Issue #991 extra-Mechanismus) UND
    einem bereits gesetzten corridors-Eintrag wird geladen und gespeichert
    -> beides bleibt erhalten, kein Replace ueberschreibt das jeweils
    andere Feld."""
    raw = {
        "id": "t4",
        "name": "Bestandstrip",
        "stages": [
            {
                "id": "s1",
                "name": "Test-Stage",
                "date": "2026-07-12",
                "waypoints": [
                    {"id": "G1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 1000},
                ],
            }
        ],
        "alert_rules": [
            {
                "id": "r1",
                "kind": "delta",
                "metric": "wind_gust",
                "threshold": 30.0,
                "unit": "km/h",
                "severity": "warning",
                "enabled": True,
            },
        ],
        "corridors": [
            {
                "metric": "wind_gust",
                "range": [None, 30.0],
                "notify": True,
                "mark": False,
            }
        ],
        # Unmodelliertes Bestandsfeld — muss roundtrip-erhalten bleiben (#991).
        "__reserved_future_field__": {"nested": "value"},
    }

    trip_path = tmp_path / "trip.json"
    trip_path.write_text(json.dumps(raw, indent=2))

    loaded = load_trip(trip_path)

    # corridors muss typed geladen werden, nicht in extra verschwinden.
    assert len(loaded.corridors) == 1
    assert loaded.corridors[0].metric == "wind_gust"
    assert loaded.corridors[0].range == [None, 30.0]
    assert loaded.corridors[0].notify is True
    assert loaded.corridors[0].mark is False

    # alert_rules bleibt unangetastet.
    assert len(loaded.alert_rules) == 1
    assert loaded.alert_rules[0].threshold == 30.0

    # unmodelliertes Feld bleibt in extra erhalten (Read-Modify-Write, kein Replace).
    assert loaded.extra.get("__reserved_future_field__") == {"nested": "value"}

    # Re-Save: alle drei Bestandteile muessen im Output-Dict wieder auftauchen.
    resaved = _trip_to_dict(loaded)
    assert resaved.get("__reserved_future_field__") == {"nested": "value"}
    assert len(resaved["corridors"]) == 1
    resaved_corridor = resaved["corridors"][0]
    assert resaved_corridor["metric"] == "wind_gust"
    assert resaved_corridor["range"] == [None, 30.0]
    assert resaved_corridor["notify"] is True
    assert resaved_corridor["mark"] is False
    assert len(resaved["alert_rules"]) == 1


# --- AC-1d (Adversary F001/F002): malformed range degradiert statt crasht ---
# Datenverlust-Klasse BUG-DATALOSS-GR221: ein einzelner malformter Corridor
# darf NIE den gesamten Trip unladbar machen. Go verarbeitet dieselben
# Inputs fehlerfrei (degradiert zu nil) — Python muss dazu konsistent sein.

def _write_trip_with_corridor(tmp_path: Path, corridor_dict: dict) -> Path:
    raw = {
        "id": "t9",
        "name": "Malformed-Range-Test",
        "stages": [
            {
                "id": "s1",
                "name": "Test-Stage",
                "date": "2026-07-12",
                "waypoints": [
                    {"id": "G1", "name": "Start", "lat": 47.0, "lon": 11.0, "elevation_m": 1000},
                ],
            }
        ],
        "alert_rules": [
            {
                "id": "r1", "kind": "delta", "metric": "wind_gust", "threshold": 30.0,
                "unit": "km/h", "severity": "warning", "enabled": True,
            },
        ],
        "corridors": [corridor_dict],
        "__reserved_future_field__": {"nested": "value"},
    }
    trip_path = tmp_path / "trip.json"
    trip_path.write_text(json.dumps(raw, indent=2))
    return trip_path


def test_corridor_range_null_degrades_to_open_both_sides(tmp_path: Path) -> None:
    """F002: `"range": null` darf den Trip nicht unladbar machen -> degradiert
    zu [None, None] (beidseitig offen)."""
    path = _write_trip_with_corridor(tmp_path, {"metric": "wind_gust", "range": None, "notify": True, "mark": False})
    loaded = load_trip(path)
    assert loaded.corridors[0].range == [None, None]
    assert len(loaded.alert_rules) == 1  # Isolation: Nachbarfelder unberuehrt


def test_corridor_range_single_element_pads_to_two(tmp_path: Path) -> None:
    """F002: `range: [5.0]` (nur 1 Element) darf nicht IndexError werfen ->
    fehlende Obergrenze wird als None ergaenzt."""
    path = _write_trip_with_corridor(tmp_path, {"metric": "wind_gust", "range": [5.0], "notify": False, "mark": True})
    loaded = load_trip(path)
    assert loaded.corridors[0].range == [5.0, None]


def test_corridor_range_extra_elements_truncated_to_two(tmp_path: Path) -> None:
    """F002: `range: [1, 2, 3]` -> nur die ersten zwei Elemente zaehlen."""
    path = _write_trip_with_corridor(tmp_path, {"metric": "wind_gust", "range": [1, 2, 3], "notify": False, "mark": True})
    loaded = load_trip(path)
    assert loaded.corridors[0].range == [1.0, 2.0]


def test_corridor_range_numeric_strings_cast_to_float(tmp_path: Path) -> None:
    """F001: `range: ["10.0", "45.0"]` wird als float geladen (Maszstab
    `_alert_rule_from_dict::threshold`), kein spaeterer TypeError in
    corridor_inside()."""
    path = _write_trip_with_corridor(
        tmp_path, {"metric": "wind_gust", "range": ["10.0", "45.0"], "notify": True, "mark": False}
    )
    loaded = load_trip(path)
    assert loaded.corridors[0].range == [10.0, 45.0]
    assert all(isinstance(v, float) for v in loaded.corridors[0].range)


def test_corridor_range_non_numeric_values_degrade_to_none_not_crash(tmp_path: Path) -> None:
    """Nicht-castbare Werte (z.B. "a") duerfen den Trip nicht unladbar machen
    -> kontrolliertes Degradieren zu None je betroffener Seite (analog Go,
    das solche Werte nie persistiert bekommt und sonst mit Marshal-Error
    ablehnen wuerde — hier degradieren statt Totalausfall)."""
    path = _write_trip_with_corridor(tmp_path, {"metric": "wind_gust", "range": ["a", "b"], "notify": False, "mark": True})
    loaded = load_trip(path)
    assert loaded.corridors[0].range == [None, None]


def test_corridor_malformed_range_does_not_affect_alert_rules_or_legacy(tmp_path: Path) -> None:
    """Malformed corridor range darf alert_rules/unmodellierte Legacy-Felder
    nicht antasten (Read-Modify-Write bleibt scope-isoliert, BUG-DATALOSS-GR221)."""
    path = _write_trip_with_corridor(tmp_path, {"metric": "wind_gust", "range": None, "notify": True, "mark": False})
    loaded = load_trip(path)
    assert len(loaded.alert_rules) == 1
    assert loaded.alert_rules[0].threshold == 30.0
    assert loaded.extra.get("__reserved_future_field__") == {"nested": "value"}


# --- AC-1e (Adversary F003 + NaN/Infinity-Haertung): weitere Malformed-Faelle ---

@pytest.mark.parametrize("scalar_range", [True, 5, 5.5], ids=["bool", "int", "float"])
def test_corridor_range_as_scalar_degrades_to_open_both_sides(tmp_path: Path, scalar_range) -> None:
    """F003: `range` als JSON-Skalar (statt Liste) darf `list(raw_range)`
    nicht mit TypeError crashen lassen -> degradiert zu [None, None],
    Trip bleibt ladbar."""
    path = _write_trip_with_corridor(tmp_path, {"metric": "wind_gust", "range": scalar_range, "notify": True, "mark": False})
    loaded = load_trip(path)
    assert loaded.corridors[0].range == [None, None]
    assert len(loaded.alert_rules) == 1  # Isolation: Nachbarfelder unberuehrt


def test_corridor_range_nan_and_infinity_degrade_to_none(tmp_path: Path) -> None:
    """NaN/Infinity duerfen die range-Grenze nicht stillschweigend
    unwirksam machen (corridor_inside(x, nan, ...) waere sonst immer True) —
    beide degradieren zu None wie jeder andere nicht-endliche Wert."""
    path = _write_trip_with_corridor(
        tmp_path, {"metric": "wind_gust", "range": [float("nan"), float("inf")], "notify": False, "mark": True}
    )
    loaded = load_trip(path)
    assert loaded.corridors[0].range == [None, None]
