"""TDD RED -- Issue #2158 AC-13 (Skript-Teil): ``cleanup_1708c_dead_trips.py``
behandelt eine Sperrdatei ``<id>.json.lock`` nicht als Trip.

SPEC: docs/specs/bugfix/fix_2158_schreibsperren.md (AC-13)

Das Skript wird relativ zur Testdatei geladen (nie ueber den Hauptrepo-Pfad).
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

_SKRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cleanup_1708c_dead_trips.py"


def _lade():
    spec = importlib.util.spec_from_file_location("cleanup_1708c_dead_trips_2158", _SKRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ac13_sperrdatei_im_trips_ordner_loest_keine_trip_zeitwarnung_aus(tmp_path):
    """AC-13 (#2158). GIVEN users/default/trips/ mit einer alten Trip-Datei und
    einer NEUEN Sperrdatei x.json.lock WHEN der Dry-Run laeuft THEN steht die
    Sperrdatei nicht in den Zeit-Warnungen (sie ist kein Trip)."""
    mod = _lade()
    users = tmp_path / "users"
    trips = users / "default" / "trips"
    trips.mkdir(parents=True)
    trip = trips / "x.json"
    trip.write_text("{}", encoding="utf-8")
    os.utime(trip, (1_600_000_000, 1_600_000_000))  # lange vor dem Cutover
    (trips / "x.json.lock").write_text("", encoding="utf-8")  # mtime = jetzt

    result = mod.run_cleanup(users, tmp_path / "backup", execute=False)

    assert not any(w.endswith(".lock") for w in result["time_warnings"]), result["time_warnings"]


def test_ac13_execute_laesst_sperrdatei_in_briefings_unberuehrt(tmp_path):
    """AC-13 (#2158), Regressionswaechter (heute gruen). GIVEN briefings/ mit
    Trip und Sperrdatei plus ein toter trips/-Ordner WHEN das Skript mit
    --execute laeuft THEN bleiben briefings/<id>.json und <id>.json.lock
    unberuehrt."""
    mod = _lade()
    users = tmp_path / "users"
    (users / "default" / "trips").mkdir(parents=True)
    briefings = users / "default" / "briefings"
    briefings.mkdir()
    (briefings / "t.json").write_text("{}", encoding="utf-8")
    (briefings / "t.json.lock").write_text("", encoding="utf-8")

    mod.run_cleanup(users, tmp_path / "backup", execute=True)

    assert (briefings / "t.json").exists()
    assert (briefings / "t.json.lock").exists()
