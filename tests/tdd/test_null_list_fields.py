"""TDD RED — Issue #1244: Null-Listenfelder brechen den Trip-Loader.

Spec: docs/specs/modules/fix_1244_null_list_fields.md (AC-1 Python-Teil,
AC-3, AC-6). Context: docs/context/fix-1244-corridors-null.md.

Ein über `POST /api/trips` angelegter Trip ohne explizit gesetzte
`corridors`/`stages`/... wird als JSON `null` persistiert statt als leere
Liste. `src/app/loader.py::_parse_trip` (und `_alert_rule_from_dict`) nutzen
heute das Idiom `data.get("x", [])`, dessen Default bei explizitem JSON
`null` NICHT greift (`.get()` liefert `None`) — Folge ist ein
`TypeError`/`AttributeError` beim Laden, und `load_all_trips()` verschluckt
diese Exception lautlos (`logger.warning`) statt sie sichtbar zu machen.

Nutzersicht-Bug: Ein Trip mit `"corridors": null` auf Platte ist in der Liste
sichtbar, bekommt aber NIE ein Briefing — der Sende-Endpoint antwortet 404.

RED heute: Der Loader nutzt noch `data.get("x", [])` statt `data.get("x") or
[]`; `load_all_trips` loggt noch `warning` statt `error`. Nach der
Implementierung (GREEN) laufen alle Tests hier grün.

NO MOCKS — echte JSON-Dateien via `tmp_path` / dem autouse-isolierten
`_DATA_ROOT` (Issue #1133, `tests/conftest.py`), echter Loader.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app import loader


def _minimal_trip(trip_id: str = "trip-x", **overrides) -> dict:
    """Ein minimal valides Trip-Dict (laedt heute schon fehlerfrei), das
    gezielt mit `overrides` um kaputte `null`-Felder ergaenzt werden kann."""
    base: dict = {
        "id": trip_id,
        "name": "Test Trip",
        "stages": [
            {
                "id": "stage-1",
                "name": "Etappe 1",
                "date": "2026-07-20",
                "waypoints": [
                    {
                        "id": "wp-1",
                        "name": "Start",
                        "lat": 47.0,
                        "lon": 11.0,
                        "elevation_m": 1500,
                    }
                ],
            }
        ],
    }
    base.update(overrides)
    return base


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


# ═══════════════════════════════ AC-3 ════════════════════════════════════════

def test_ac3_corridors_null_loads_as_empty_list(tmp_path):
    """AC-3 GIVEN eine Trip-Datei mit `"corridors": null` / WHEN `load_trip()`
    aufgerufen wird / THEN gibt es ein valides `Trip`-Objekt mit
    `corridors == []` statt eines `TypeError`.

    RED heute: `data.get("corridors", [])` liefert bei explizitem `null`
    `None` -> `for c in None` wirft `TypeError: 'NoneType' object is not
    iterable` in `_parse_trip` (loader.py:455).
    """
    trip = _minimal_trip("trip-corridors-null", corridors=None)
    path = _write_json(tmp_path / "trip-corridors-null.json", trip)

    loaded = loader.load_trip(path)

    assert loaded is not None
    assert loaded.corridors == [], (
        f"Erwartet leere Corridor-Liste bei null-Bestandsdatei, erhalten: {loaded.corridors!r}"
    )


def test_ac1_ac3_stages_null_loads_as_empty_list(tmp_path):
    """AC-1/AC-3 GIVEN eine Trip-Datei mit `"stages": null` (z.B. neu
    angelegter Trip ohne konfigurierte Etappen) / WHEN `load_trip()`
    aufgerufen wird / THEN gibt es ein valides `Trip`-Objekt mit
    `stages == []` statt eines `TypeError`.

    RED heute: `data.get("stages", [])` liefert bei explizitem `null` `None`
    -> `for stage_data in None` wirft `TypeError` (loader.py:308).
    """
    trip = _minimal_trip("trip-stages-null", stages=None)
    path = _write_json(tmp_path / "trip-stages-null.json", trip)

    loaded = loader.load_trip(path)

    assert loaded is not None
    assert loaded.stages == [], (
        f"Erwartet leere Stage-Liste bei null-Bestandsdatei, erhalten: {loaded.stages!r}"
    )


def test_ac1_ac3_waypoints_null_within_stage_loads_as_empty_list(tmp_path):
    """AC-1/AC-3 GIVEN eine Trip-Datei mit einer Stage, deren `"waypoints":
    null` gesetzt ist / WHEN `load_trip()` aufgerufen wird / THEN gibt es ein
    valides `Trip`-Objekt mit einer Stage, deren `waypoints == []` statt
    eines `TypeError`.

    RED heute: `stage_data.get("waypoints", [])` liefert bei explizitem
    `null` `None` -> `for wp_data in None` wirft `TypeError` (loader.py:310).
    """
    trip = _minimal_trip("trip-waypoints-null")
    trip["stages"][0]["waypoints"] = None
    path = _write_json(tmp_path / "trip-waypoints-null.json", trip)

    loaded = loader.load_trip(path)

    assert loaded is not None
    assert len(loaded.stages) == 1
    assert loaded.stages[0].waypoints == [], (
        f"Erwartet leere Waypoint-Liste bei null-Bestandsdatei, "
        f"erhalten: {loaded.stages[0].waypoints!r}"
    )


def test_ac3_channels_null_in_alert_rule_loads_as_empty_list(tmp_path):
    """AC-3 GIVEN eine Trip-Datei mit einer `alert_rules`-Regel, deren
    `"channels": null` gesetzt ist / WHEN `load_trip()` aufgerufen wird /
    THEN gibt es ein valides `Trip`-Objekt mit einer AlertRule, deren
    `channels == []` statt eines `TypeError`.

    RED heute: `d.get("channels", [])` liefert bei explizitem `null` `None`
    -> `list(None)` wirft `TypeError` in `_alert_rule_from_dict`
    (loader.py:166).
    """
    trip = _minimal_trip(
        "trip-channels-null",
        alert_rules=[
            {
                "id": "rule-1",
                "kind": "delta",
                "metric": "wind_gust",
                "threshold": 40.0,
                "unit": "km/h",
                "severity": "warning",
                "enabled": True,
                "channels": None,
            }
        ],
    )
    path = _write_json(tmp_path / "trip-channels-null.json", trip)

    loaded = loader.load_trip(path)

    assert loaded is not None
    assert len(loaded.alert_rules) == 1
    assert loaded.alert_rules[0].channels == [], (
        f"Erwartet leere Channels-Liste bei null-Bestandsdatei, "
        f"erhalten: {loaded.alert_rules[0].channels!r}"
    )


def test_ac3_display_config_null_loads_without_crash(tmp_path):
    """AC-3 GIVEN eine Trip-Datei mit `"display_config": null` / WHEN
    `load_trip()` aufgerufen wird / THEN gibt es ein valides `Trip`-Objekt
    statt eines `AttributeError`.

    RED heute: `data["display_config"]` ist `None`, `_parse_display_config`
    ruft `data.get("metrics", [])` auf `None` auf -> `AttributeError:
    'NoneType' object has no attribute 'get'` (loader.py:391/531).
    """
    trip = _minimal_trip("trip-display-config-null", display_config=None)
    path = _write_json(tmp_path / "trip-display-config-null.json", trip)

    loaded = loader.load_trip(path)

    assert loaded is not None, "Trip muss trotz null-display_config ladbar sein"
    assert loaded.display_config is not None, (
        "Ein explizites display_config:null darf nicht zu einem kaputten "
        "Ladeergebnis führen — fail-soft heißt hier: valider Default statt Crash"
    )


def test_ac3_avalanche_regions_null_loads_as_empty_list(tmp_path):
    """AC-3 GIVEN eine Trip-Datei mit `"avalanche_regions": null` / WHEN
    `load_trip()` aufgerufen wird / THEN ist `avalanche_regions == []` statt
    `None`.

    RED heute: `data.get("avalanche_regions", [])` liefert bei explizitem
    `null` `None` durch (loader.py:472) — kein Crash, aber stiller
    Datenschaden (z.B. spätere `len(trip.avalanche_regions)`-Aufrufe würden
    crashen).
    """
    trip = _minimal_trip("trip-avalanche-null", avalanche_regions=None)
    path = _write_json(tmp_path / "trip-avalanche-null.json", trip)

    loaded = loader.load_trip(path)

    assert loaded is not None
    assert loaded.avalanche_regions == [], (
        f"Erwartet leere Liste statt None, erhalten: {loaded.avalanche_regions!r}"
    )


# ═══════════════════ Nutzersicht-Bug: load_all_trips() ═══════════════════════

def test_central_bug_load_all_trips_returns_trip_with_null_corridors():
    """Der eigentliche Nutzersicht-Bug (AC-1/AC-3): Ein Trip mit
    `"corridors": null` liegt in `data/users/<user>/trips/<id>.json`.
    `load_all_trips(user_id)` liefert ihn HEUTE NICHT zurück — er wird still
    übersprungen (`logger.warning("Skipping corrupt trip ...")`). Der Nutzer
    sieht den Trip zwar (falls die Liste anders befüllt wird), bekommt aber
    nie ein Briefing dafür, und der Sende-Endpoint antwortet 404.

    Nutzt den autouse-isolierten `_DATA_ROOT` (Issue #1133, tests/conftest.py)
    -- kein expliziter Test-Override nötig.

    RED heute: `load_all_trips("user-1244-central")` liefert eine leere
    Liste statt des einen geschriebenen Trips.
    """
    user_id = "user-1244-central"
    trip = _minimal_trip("trip-central-corridors-null", corridors=None)
    trips_dir = loader.get_briefings_dir(user_id)
    _write_json(trips_dir / "trip-central-corridors-null.json", trip)

    trips = loader.load_all_trips(user_id)

    trip_ids = [t.id for t in trips]
    assert "trip-central-corridors-null" in trip_ids, (
        f"Der Trip mit 'corridors': null muss in load_all_trips() erscheinen -- "
        f"nicht still verschwinden (Sende-Endpoint würde sonst 404 liefern). "
        f"Gefundene Trips: {trip_ids!r}"
    )
    loaded = next(t for t in trips if t.id == "trip-central-corridors-null")
    assert loaded.corridors == []


# ═══════════════════════════════ AC-6 ════════════════════════════════════════

def test_ac6_structurally_broken_trip_logs_error_not_warning(caplog):
    """AC-6 GIVEN eine strukturell defekte Trip-Datei (fehlendes Pflichtfeld
    `id` -> `KeyError` in `_parse_trip`, bleibt auch nach dem Null-Listen-Fix
    unladbar) neben einer validen Trip-Datei / WHEN `load_all_trips()`
    aufgerufen wird / THEN erscheint für die defekte Datei ein Log-Eintrag
    auf Level ERROR (nicht nur WARNING), der den Dateinamen nennt; die valide
    Datei wird trotzdem zurückgegeben.

    RED heute: `load_all_trips` loggt den Skip-Pfad mit `logger.warning(...)`
    (loader.py:1098) -- kein ERROR-Eintrag vorhanden.
    """
    user_id = "user-1244-ac6"

    broken = _minimal_trip("trip-broken")
    del broken["id"]  # strukturell defekt: Pflichtfeld fehlt -> KeyError beim Parsen
    good = _minimal_trip("trip-good")

    trips_dir = loader.get_briefings_dir(user_id)
    _write_json(trips_dir / "trip-broken.json", broken)
    _write_json(trips_dir / "trip-good.json", good)

    with caplog.at_level(logging.WARNING, logger="app.loader"):
        trips = loader.load_all_trips(user_id)

    assert [t.id for t in trips] == ["trip-good"], (
        "Die defekte Datei muss weiterhin übersprungen werden, die valide "
        "Datei muss trotzdem geladen werden"
    )

    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert error_records, (
        "Erwartet mindestens einen ERROR-Log-Eintrag für die defekte Trip-Datei "
        f"(bisherige Log-Einträge: {[(r.levelname, r.getMessage()) for r in caplog.records]!r})"
    )
    assert any("trip-broken.json" in r.getMessage() for r in error_records), (
        "Der ERROR-Log-Eintrag muss den Dateinamen der defekten Trip-Datei nennen"
    )
