"""Gemeinsamer Test-Fixture-Helfer fuer den ComparePreset-Persistenz-Cutover
(Issue #1250 Scheibe 7b).

Nach dem Cutover leben ComparePresets per-Datei unter
``<user_dir>/briefings/<id>.json`` (``kind="vergleich"``) statt in der einen
Array-Datei ``compare_presets.json``. Dieser Helfer konsolidiert die
Array->per-Datei-Umschreibung, die sonst in ~14 Test-Dateien einzeln
dupliziert werden muesste (statt N lokaler ``_write_presets``-Kopien).

``write_compare_briefings`` schreibt jedes Preset als eigene
``briefings/<id>.json`` (kind wird auf "vergleich" gesetzt, damit der
inverse kind-Filter des Loaders sie sieht). ``read_compare_briefings`` liest
den Bestand wieder als Liste ein (sortiert nach Dateiname) — ein
Drop-in-Ersatz fuer das fruehere ``json.loads(compare_presets.json)``, damit
Bestandstests, die die Array-Form zurueckgelesen haben, minimal umgestellt
werden koennen.
"""
from __future__ import annotations

import json
from pathlib import Path


def write_compare_briefings(user_dir: Path, presets: list[dict]) -> Path:
    """Schreibt jedes Preset per-Datei nach ``<user_dir>/briefings/<id>.json``
    mit ``kind="vergleich"``. Gibt das ``briefings/``-Verzeichnis zurueck.

    ``user_dir`` ist das Nutzerverzeichnis (z.B. ``tmp_path/users/<uid>`` bzw.
    ``DATA_ROOT/<uid>``). Presets ohne ``id`` erhalten einen stabilen
    Positions-Fallback, damit der Helfer nie still Dateien ueberschreibt.
    """
    briefings = Path(user_dir) / "briefings"
    briefings.mkdir(parents=True, exist_ok=True)
    for i, preset in enumerate(presets):
        entry = dict(preset)
        entry["kind"] = "vergleich"
        preset_id = entry.get("id") or f"preset-{i}"
        (briefings / f"{preset_id}.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return briefings


def read_compare_briefings(user_dir: Path) -> list[dict]:
    """Liest den vergleich-Bestand aus ``<user_dir>/briefings/`` als Liste
    (sortiert nach Dateiname) — Drop-in fuer das fruehere Array-Rueckle­sen
    von ``compare_presets.json``."""
    briefings = Path(user_dir) / "briefings"
    if not briefings.exists():
        return []
    out: list[dict] = []
    for path in sorted(briefings.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("kind") == "vergleich":
            out.append(data)
    return out
