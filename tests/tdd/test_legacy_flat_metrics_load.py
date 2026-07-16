"""RED-Tests (Issue #1262) — Legacy-Flach-String-Metrics brechen den Loader.

Spec: docs/specs/modules/fix_1262_legacy_flat_metrics.md, AC-1/AC-2/AC-3.

Root-Cause: `src/app/loader.py::_parse_display_config` nimmt an, jeder Eintrag
in `display_config.metrics` sei ein dict (`mc["metric_id"]`, `mc.get(...)`).
Eine Legacy-Flach-String-Liste (`"metrics": ["temperature", "wind_speed"]`)
crasht dort (`TypeError: string indices must be integers`). `load_all_trips`
faengt jede Exception pro Trip ab (`logger.error` + `continue`) — der Trip
faellt still aus der Liste, die Briefing-Scheduler UND Alarm-Engine speist.

Kern-Schicht, deterministisch: echte Loader-/Dateipfade, KEINE Mocks. Der
autouse-Fixture `tests/conftest.py::_isolate_data_root` (Issue #1133) setzt
`app.loader._DATA_ROOT` auf ein tmp-Root je Test, sodass `get_briefings_dir`
in eine isolierte Wurzel zeigt.

RED-Erwartung:
- AC-1 (test_flat_string_metrics_load_as_metricconfig): rot, crasht heute im
  `_parse_display_config`-Pfad.
- AC-2 (test_flat_string_trip_survives_load_all_trips): rot, heute `len == 0`,
  weil der Trip beim Laden crasht und im `except`-Block verworfen wird.
- AC-3 (test_dict_metrics_roundtrip_field_identical): darf JETZT SCHON gruen
  sein — Regressionswaechter fuer den bestehenden dict-Pfad.
"""
from __future__ import annotations

import json
from pathlib import Path

from app import loader
from app.loader import _trip_to_dict, load_all_trips, load_trip


def _flat_metrics_trip(trip_id: str, name: str = "Flat-Metrics-Tour") -> dict:
    """Trip-Dict mit Legacy-Flach-String-`display_config.metrics`."""
    return {
        "id": trip_id,
        "name": name,
        "kind": "route",
        "stages": [],
        "display_config": {
            "trip_id": trip_id,
            "metrics": ["temperature", "wind_speed"],
            "updated_at": "2026-07-01T10:00:00",
        },
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-1 — load_trip heilt Flach-Strings zu MetricConfig(metric_id=s, enabled=True)
# ---------------------------------------------------------------------------

def test_flat_string_metrics_load_as_metricconfig():
    """GIVEN ein Trip-Dict, dessen `display_config.metrics` eine Flach-String-
    Liste ist / WHEN es via `load_trip` geladen wird / THEN wird es ohne
    Exception geladen und jeder String-Eintrag erscheint als
    `MetricConfig(metric_id=<string>, enabled=True)` (AC-1)."""
    trip = load_trip(_flat_metrics_trip("gr20-flat"))

    assert trip is not None
    metrics = trip.display_config.metrics
    assert [m.metric_id for m in metrics] == ["temperature", "wind_speed"], (
        "jeder Flach-String muss als MetricConfig.metric_id erscheinen (AC-1)"
    )
    assert all(m.enabled is True for m in metrics), (
        "aus einem Flach-String migrierte Metrik ist enabled=True (AC-1)"
    )


# ---------------------------------------------------------------------------
# AC-2 — Nutzersicht: Flach-String-Trip ueberlebt load_all_trips (Kern-Repro)
# ---------------------------------------------------------------------------

def test_flat_string_trip_survives_load_all_trips():
    """GIVEN ein Nutzer mit genau EINEM Trip, dessen `metrics` eine Flach-
    String-Liste ist, abgelegt in seinem echten `briefings/`-Ordner / WHEN
    `load_all_trips` fuer den Briefing-Scheduler/Alarm-Engine laeuft / THEN
    ist der Trip enthalten (`len == 1`), nicht uebersprungen (AC-2).

    RED heute: `len == 0`, weil der Trip beim Laden crasht und der
    `except Exception`-Block ihn verwirft — der Nutzer bekommt weder
    Briefings noch Alarme, ohne sichtbaren Fehler.
    """
    uid = "flat-metrics-user"
    trip_id = "corse-flat"
    _write_json(loader.get_briefings_dir(uid) / f"{trip_id}.json", _flat_metrics_trip(trip_id))

    result = load_all_trips(user_id=uid)

    assert len(result) == 1, (
        f"Flach-String-Trip muss geladen werden, bekam {len(result)} Trips "
        "(vor Fix: 0 — Trip crasht und wird still verworfen, AC-2)"
    )
    assert result[0].id == trip_id
    assert [m.metric_id for m in result[0].display_config.metrics] == [
        "temperature",
        "wind_speed",
    ]


# ---------------------------------------------------------------------------
# AC-3 — Regressionsschutz: voll ausgepraegter dict-Pfad bleibt unveraendert
# ---------------------------------------------------------------------------

def test_dict_metrics_roundtrip_field_identical():
    """GIVEN ein Trip mit voll ausgepraegten dict-`MetricConfig` (inkl.
    `bucket`, `order`, `alert_threshold`, `aggregations`) / WHEN er geladen,
    serialisiert (`_trip_to_dict`) und erneut geladen wird / THEN bleibt die
    `metrics`-Config feldweise identisch — die Flach-String-Normalisierung
    fasst den bestehenden dict-Pfad NICHT an (AC-3, darf heute schon gruen
    sein)."""
    trip_id = "vanoise-dict"
    source = {
        "id": trip_id,
        "name": "Dict-Metrics-Tour",
        "kind": "route",
        "stages": [],
        "display_config": {
            "trip_id": trip_id,
            "metrics": [
                {
                    "metric_id": "temperature",
                    "enabled": True,
                    "aggregations": ["min", "max", "avg"],
                    "bucket": "primary",
                    "order": 2,
                    "alert_enabled": True,
                    "alert_threshold": 42.0,
                },
                {
                    "metric_id": "wind_speed",
                    "enabled": False,
                    "aggregations": ["max"],
                    "bucket": "secondary",
                    "order": 5,
                    "alert_enabled": False,
                    "alert_threshold": None,
                },
            ],
            "updated_at": "2026-07-01T10:00:00",
        },
    }

    trip1 = load_trip(source)
    dict_out = _trip_to_dict(trip1)
    trip2 = load_trip(dict_out)

    m1 = trip1.display_config.metrics
    m2 = trip2.display_config.metrics
    assert len(m1) == len(m2) == 2

    fields = ("metric_id", "enabled", "aggregations", "bucket", "order",
              "alert_enabled", "alert_threshold")
    for a, b in zip(m1, m2):
        for f in fields:
            assert getattr(a, f) == getattr(b, f), (
                f"dict-Pfad-Feld '{f}' muss ueber load->serialize->load "
                f"identisch bleiben (AC-3): {getattr(a, f)!r} != {getattr(b, f)!r}"
            )
