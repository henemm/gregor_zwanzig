"""Issue #1357 (Epic #1372 S4a), AC-6: eine getroffene Auswertungs-Einschraenkung
ueberlebt Speichern und erneutes Laden.

Spec: docs/specs/modules/trip_aggregation_selection.md (AC-6).

Kern-Schicht, deterministisch: kein Mock, kein Netz, kein ``patch()``. Echter
Persistenzpfad ``save_trip`` -> Datei -> ``load_trip`` inklusive des
Read-Modify-Write-Merges (``_deep_merge_preserve_unknown``), Test-Isolation
ueber ``data_dir=tmp_path``.

STAND DIESER DATEI: **heute bereits gruen** — Invarianten-Waechter, kein RED.
``MetricConfig.aggregations`` wird von ``loader.py:159`` geschrieben und an drei
Stellen (``loader.py:779/813/846``) gelesen; der Python-Rand traegt das Feld
also schon. Der Wert dieser Datei liegt darin, dass die Umsetzung von #1357
(erstmalige Nutzung des Feldes durch den Renderer) diesen Rand nicht
beschaedigt — insbesondere darf die bewusst leere Auswahl ``[]`` nicht in den
Schreib-Default ``["min", "max"]`` zurueckkippen (das wuerde AC-8 aushebeln).

Die tatsaechliche Datenverlust-Stelle fuer AC-6 liegt NICHT hier, sondern im
Frontend: ``buildWeatherConfigMetrics``
(frontend/src/lib/components/trip-detail/metricsEditor.ts:330-364) baut die
Metrik-Eintraege beim Speichern neu auf und kennt ``aggregations`` nicht;
``WeatherConfigMetric`` (frontend/src/lib/types.ts:178-194) fuehrt das Feld
ebenfalls nicht. Zusammen mit ``mergeConfigMap``
(internal/handler/config_merge.go:11-22), das den Top-Level-Schluessel
``metrics`` komplett ersetzt, geht die Nutzerwahl beim ersten Speichern ueber
die Oberflaeche verloren. Der dazugehoerige rote Nachweis muss als
co-lokierter Frontend-Test neben ``metricsEditor.ts`` entstehen — der
RED-Phasen-Gate blockiert co-lokierte Frontend-Testdateien, er gehoert damit in
die Umsetzungsphase (Umfang: ``buildWeatherConfigMetrics`` reicht die gewaehlten
Auswertungen durch, ``WeatherConfigMetric`` bekommt ``aggregations?: string[]``).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.loader import load_trip, load_trip_from_dict, save_trip

USER = "u-1357"


def _trip_dict(temperature_aggs, wind_chill_aggs) -> dict:
    return {
        "id": "trip-1357-aggregations",
        "name": "Auswertungswahl-Roundtrip",
        "stages": [
            {
                "id": "stage-1",
                "name": "Etappe 1",
                "date": "2026-07-11",
                "waypoints": [
                    {"id": "wp-1", "name": "Start", "lat": 42.13, "lon": 9.13,
                     "elevation_m": 400},
                    {"id": "wp-2", "name": "Ziel", "lat": 42.10, "lon": 9.18,
                     "elevation_m": 1200},
                ],
            },
        ],
        "aggregation": {"profile": "allgemein"},
        "display_config": {
            "metrics": [
                {"metric_id": "temperature", "enabled": True,
                 "aggregations": temperature_aggs, "bucket": "primary", "order": 0},
                {"metric_id": "wind_chill", "enabled": True,
                 "aggregations": wind_chill_aggs, "bucket": "primary", "order": 1},
            ],
        },
    }


def _aggs_by_id(trip) -> dict[str, list[str]]:
    # #1484: abgeleitete Eintraege (derived=True) sind keine explizite
    # Auswahl und werden nie zurueckgeschrieben — hier ausblenden.
    return {mc.metric_id: mc.aggregations
            for mc in trip.display_config.metrics if not mc.derived}


def _aggs_on_disk(path: Path) -> dict[str, list[str]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        m["metric_id"]: m.get("aggregations")
        for m in raw["display_config"]["metrics"]
    }


# ---------------------------------------------------------------------------
# AC-6 — Einschraenkung ueberlebt Speichern und erneutes Laden
# ---------------------------------------------------------------------------

def test_explicit_selection_survives_save_and_load(tmp_path):
    """AC-6: „nur Hoechstwert" bei der Temperatur und „nur Tiefstwert" bei der
    gefuehlten Temperatur stehen nach dem Neuladen unveraendert da."""
    trip = load_trip_from_dict(_trip_dict(["max"], ["min"]))

    path = save_trip(trip, user_id=USER, data_dir=tmp_path)
    reloaded = load_trip(trip.id, data_dir=tmp_path, user_id=USER)

    assert _aggs_on_disk(path) == {"temperature": ["max"], "wind_chill": ["min"]}
    assert _aggs_by_id(reloaded) == {"temperature": ["max"], "wind_chill": ["min"]}


def test_empty_selection_survives_and_is_not_refilled_with_default(tmp_path):
    """AC-6 + AC-8: eine bewusst geleerte Auswahl (``[]``) bleibt leer und wird
    beim Laden NICHT mit dem Schreib-Default ``["min", "max"]`` aufgefuellt —
    sonst waere „keine Auswertung anzeigen" nicht ausdrueckbar."""
    trip = load_trip_from_dict(_trip_dict(["min", "max"], []))

    path = save_trip(trip, user_id=USER, data_dir=tmp_path)
    reloaded = load_trip(trip.id, data_dir=tmp_path, user_id=USER)

    assert _aggs_on_disk(path)["wind_chill"] == []
    assert _aggs_by_id(reloaded)["wind_chill"] == [], (
        "Leere Auswahl wurde beim Laden mit dem Default aufgefuellt: "
        f"{_aggs_by_id(reloaded)!r}"
    )


def test_changed_selection_replaces_previous_value_on_second_save(tmp_path):
    """AC-6: aendert der Nutzer seine Wahl, gewinnt der neue Wert.

    Prueft den Read-Modify-Write-Merge in ``save_trip``: beim zweiten
    Schreiben liegt bereits eine Datei mit der alten Auswahl vor. Ein
    listenweise mischender Merge wuerde hier alte und neue Auswertungen
    vermengen.
    """
    trip = load_trip_from_dict(_trip_dict(["min", "max"], ["min", "max"]))
    path = save_trip(trip, user_id=USER, data_dir=tmp_path)

    reloaded = load_trip(trip.id, data_dir=tmp_path, user_id=USER)
    for mc in reloaded.display_config.metrics:
        if mc.metric_id == "wind_chill":
            mc.aggregations = ["max"]
    save_trip(reloaded, user_id=USER, data_dir=tmp_path)

    again = load_trip(trip.id, data_dir=tmp_path, user_id=USER)
    assert _aggs_on_disk(path)["wind_chill"] == ["max"]
    assert _aggs_by_id(again)["wind_chill"] == ["max"], (
        "Zweites Speichern hat die geaenderte Auswahl nicht durchgesetzt: "
        f"{_aggs_by_id(again)!r}"
    )
    assert _aggs_by_id(again)["temperature"] == ["min", "max"], (
        "Die unberuehrte Temperatur-Auswahl hat sich mitveraendert: "
        f"{_aggs_by_id(again)!r}"
    )
