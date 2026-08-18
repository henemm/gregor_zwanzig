"""TDD RED — Issue #1948 (Scheibe S1): Retention haelt je Ablage-
Verzeichnis maximal 50 Eingangs-Datensaetze (Vorlage
``WeatherSnapshotService._prune_dated_snapshots``, weather_snapshot.py:165).

SPEC: docs/specs/modules/alarm_eingangsprotokoll.md (AC-5)

RED-Grund: ``services.alert_input_capture`` existiert nicht.

Mock-frei: 55 echte JSON-Dateien mit real gesetzten ``st_mtime``-Werten
(``os.utime``) im pytest-isolierten Datenverzeichnis (#1133); ein echter
Schreibvorgang loest die Bereinigung aus.
"""
from __future__ import annotations

import json
import os
import time
import uuid


def _uid(prefix: str) -> str:
    return f"tdd-1948-retention-{prefix}-{uuid.uuid4().hex[:6]}"


def test_ac5_ueber_50_dateien_werden_die_aeltesten_geloescht():
    """AC-5: GIVEN mehr als 50 Eingangs-Datensaetze liegen bereits in einem
    Ablage-Verzeichnis, WHEN ein weiterer Datensatz geschrieben wird, THEN
    werden die aeltesten Datensaetze ueber die Grenze von 50 hinaus
    geloescht (sortiert nach ``st_mtime``, aelteste zuerst)."""
    from app.loader import get_data_dir
    from services import alert_input_capture

    uid = _uid("prune")
    target_dir = get_data_dir(uid) / "alert_input"
    target_dir.mkdir(parents=True, exist_ok=True)

    base = time.time() - 10_000
    for i in range(55):
        f = target_dir / f"forecast_change_trip_altbestand-{i:03d}_0.json"
        f.write_text(json.dumps({"idx": i}))
        os.utime(f, (base + i, base + i))  # streng steigende st_mtime

    alert_input_capture.capture_user_scoped(
        uid, entity_type="trip", entity_id="frisch",
        payload={"changes": [{
            "metric": "gust", "old_value": 1.0, "new_value": 2.0,
            "delta": 1.0, "threshold": 0.5, "severity": "minor",
            "direction": "increase", "segment_id": "1",
        }]},
    )

    remaining = sorted(target_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
    assert len(remaining) == 50, (
        f"Erwartet genau 50 verbleibende Dateien nach Retention, gefunden "
        f"{len(remaining)}: {[p.name for p in remaining]!r}"
    )
    remaining_names = {p.name for p in remaining}
    # 55 Alt-Dateien (idx 000-054) + 1 frischer Schreibvorgang = 56 Dateien
    # insgesamt -> die 6 aeltesten (idx 000-005) muessen weg sein.
    for i in range(6):
        name = f"forecast_change_trip_altbestand-{i:03d}_0.json"
        assert name not in remaining_names, (
            f"Alt-Datei idx={i} haette geloescht werden muessen (aelteste "
            f"zuerst): verbleibende Dateien {sorted(remaining_names)!r}"
        )
    for i in range(6, 55):
        name = f"forecast_change_trip_altbestand-{i:03d}_0.json"
        assert name in remaining_names, (
            f"Juengere Alt-Datei idx={i} wurde faelschlich geloescht: "
            f"verbleibende Dateien {sorted(remaining_names)!r}"
        )
