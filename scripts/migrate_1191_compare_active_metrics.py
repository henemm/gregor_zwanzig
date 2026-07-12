#!/usr/bin/env python3
"""Migration for Issue #1191 (AC-4) — setzt auf bestehenden Compare-Presets
`display_config.active_metrics` auf den vollen alarmfähigen Metrik-Satz.

Spec: docs/specs/modules/issue_1191_compare_alert_deactivated_metric.md (AC-4).
Strukturelles Vorbild: scripts/migrate_1219_email_verified.py (Dry-Run-Default,
--execute, tar.gz-Backup vor jedem schreibenden Lauf, Idempotenz,
Read-Modify-Write-Merge).

Hintergrund: Nach dem #1191-Fix filtert der Compare-Δ-Alarm streng nach
`active_metrics`. Alt-Presets OHNE dieses Feld würden verstummen. Die Migration
setzt daher den vollen Satz — bewahrt „alles feuert", jetzt explizit und pro
Metrik abschaltbar. Presets mit bereits gesetzter (Teil-)Auswahl bleiben
UNANGETASTET (eine bewusste Deaktivierung darf nicht wieder scharf werden).

Usage:
    python3 scripts/migrate_1191_compare_active_metrics.py --root <data/users> \\
        [--backup-dir <path>] [--execute]

Ohne `--root` ist ein Lauf gegen einen echten Baum unmöglich.
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

# Voller alarmfähiger Compare-Metrik-Satz (Summary-Keys). Deckungsgleich mit dem
# Mapper `compare_alert._SUMMARY_KEY_TO_CATALOG_ID` (inkl. der 4 neuen Schalter
# gust/cape/freezing_level/temperature_min).
FULL_METRIC_SET: list[str] = [
    "temp_max_c",
    "temp_min_c",
    "wind_max_kmh",
    "gust_max_kmh",
    "precip_sum_mm",
    "thunder_level_max",
    "visibility_min_m",
    "snow_new_sum_cm",
    "cape_max_jkg",
    "freezing_level_m",
]


def _needs_migration(preset: dict) -> bool:
    """True NUR, wenn `active_metrics` ganz FEHLT (Alt-Preset ohne das Feld) —
    nur dann füllt die Migration den vollen Satz. Eine bereits VORHANDENE Liste
    bleibt UNANGETASTET, auch die leere `[]`: `[]` ist ein bewusster Zustand
    (der Nutzer hat alle Compare-Alarme abgeschaltet) bzw. ein bereits migrierter
    Stand. Überschreiben würde eine bewusste Deaktivierung wieder scharf machen
    und verstieße gegen die Datenerhalt-Regel (nie Replace, CLAUDE.md)."""
    active = (preset.get("display_config") or {}).get("active_metrics")
    return active is None


def _plan(root: Path) -> list[tuple[Path, list[str]]]:
    """Sammelt (compare_presets.json-Pfad, migrationsbedürftige Preset-IDs)."""
    plan: list[tuple[Path, list[str]]] = []
    for preset_file in sorted(root.glob("*/compare_presets.json")):
        try:
            presets = json.loads(preset_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(presets, list):
            continue
        ids = [p.get("id", "?") for p in presets if isinstance(p, dict) and _needs_migration(p)]
        if ids:
            plan.append((preset_file, ids))
    return plan


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"migrate-1191-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(preset_file: Path) -> int:
    """Read-Modify-Write-Merge: nur Presets ohne Auswahl auffüllen, alle anderen
    Felder unangetastet lassen. Gibt Anzahl geänderter Presets zurück."""
    presets = json.loads(preset_file.read_text(encoding="utf-8"))
    changed = 0
    for preset in presets:
        if not isinstance(preset, dict) or not _needs_migration(preset):
            continue
        display_config = preset.get("display_config")
        if not isinstance(display_config, dict):
            display_config = {}
        display_config["active_metrics"] = list(FULL_METRIC_SET)
        preset["display_config"] = display_config
        changed += 1
    if changed:
        preset_file.write_text(
            json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {root}", file=sys.stderr)
        return 1

    plan = _plan(root)
    print(f"Migrationsplan für root: {root}")
    for preset_file, ids in plan:
        print(f"  {preset_file}: {ids}")
    if not plan:
        print("Nichts zu tun — alle Compare-Presets tragen bereits active_metrics.")

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if not plan:
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    backup_path = _make_backup(root, backup_dir)
    print(f"Backup geschrieben: {backup_path}")

    total = 0
    for preset_file, _ in plan:
        total += _apply(preset_file)
    print(f"Migration abgeschlossen: {total} Preset(s) auf vollen Metrik-Satz gesetzt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
