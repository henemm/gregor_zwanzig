#!/usr/bin/env python3
"""Migration für Issue #1258 Scheibe 1 (AC-1..AC-3) — überführt bestehende
`official_alert_triggers_enabled` additiv nach `official_warnings.enabled`
auf Trip UND ComparePreset.

Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md,
Sektion „Implementation Details" Nr. 2 (Migration) + AC-1..AC-3. Vorbild:
`scripts/migrate_1231_corridors.py` (Dry-Run-Default, --execute, tar.gz-
Backup, Read-Modify-Write, Idempotenz).

Formel (PO-Entscheidung F1, 2026-07-15):
    official_warnings.enabled := (official_alert_triggers_enabled != False)
d.h. fehlend/True -> True, False -> False — identisch zum bisherigen
Ist-Verhalten der Sofort-Alarm-Pipeline (kein Verhaltenswechsel für
Bestand). Das Legacy-Feld bleibt UNVERÄNDERT in den Daten (Rollback-
Sicherheit, keine Löschung, kein neues Hinzufügen bei zuvor ungesetztem
Feld). Ein Trip/Preset mit bereits gesetztem, nicht-leerem
`official_warnings` gilt als migriert und wird beim erneuten Lauf
übersprungen (Idempotenz, AC-3) — auch wenn der Wert inzwischen manuell
verändert wurde.

Usage:
    python3 scripts/migrate_1258_official_warnings.py --root <data/users> \\
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


def _needs_migration(obj: dict) -> bool:
    """Idempotenz (AC-3): ein Trip/Preset mit bereits gesetztem
    `official_warnings` (Objekt MIT "enabled"-Schlüssel) gilt als migriert
    und wird übersprungen — auch wenn der Wert seither manuell verändert
    wurde (kein stilles Zurücksetzen).

    Fix-Loop F003: ein leeres `{}` (kein "enabled"-Schlüssel, z.B.
    Datenmüll/abgebrochene Migration) zählt NICHT als migriert — reine
    Truthy-Prüfung hätte auch ein `{"sources": [...]}` ohne "enabled" als
    "bereits migriert" durchgehen lassen (Go-Äquivalent:
    internal/store/migrate_1258.go officialWarningsRawHasEnabledKey)."""
    ow = obj.get("official_warnings")
    return not (isinstance(ow, dict) and "enabled" in ow)


def _compute_enabled(obj: dict) -> bool:
    """AC-1/AC-2: fehlend/True -> True, False -> False (Ist-Verhalten)."""
    return obj.get("official_alert_triggers_enabled") is not False


def _collect_plan(root: Path):
    trip_plan: list[tuple[Path, dict, bool]] = []
    preset_plan: list[tuple[Path, list, list[tuple[dict, bool]]]] = []
    report_lines: list[str] = []

    for trip_file in sorted(root.glob("*/trips/*.json")):
        try:
            trip = json.loads(trip_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(trip, dict):
            continue
        if not _needs_migration(trip):
            report_lines.append(f"SKIP {trip_file}: bereits migriert (official_warnings gesetzt)")
            continue
        enabled = _compute_enabled(trip)
        trip_plan.append((trip_file, trip, enabled))
        report_lines.append(f"{trip_file}: official_warnings.enabled={enabled}")

    for preset_file in sorted(root.glob("*/compare_presets.json")):
        try:
            presets = json.loads(preset_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(presets, list):
            continue
        changed_presets: list[tuple[dict, bool]] = []
        for preset in presets:
            if not isinstance(preset, dict):
                continue
            if not _needs_migration(preset):
                report_lines.append(
                    f"SKIP {preset_file} [{preset.get('id', '?')}]: bereits migriert"
                )
                continue
            enabled = _compute_enabled(preset)
            changed_presets.append((preset, enabled))
            report_lines.append(
                f"{preset_file} [{preset.get('id', '?')}]: official_warnings.enabled={enabled}"
            )
        if changed_presets:
            preset_plan.append((preset_file, presets, changed_presets))

    return trip_plan, preset_plan, report_lines


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"migrate-1258-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(trip_plan, preset_plan) -> int:
    """Read-Modify-Write: nur `official_warnings` ergänzen, alle anderen
    Felder (inkl. des unveränderten Legacy-Felds) bleiben unangetastet."""
    changed = 0
    for trip_file, trip, enabled in trip_plan:
        trip["official_warnings"] = {"enabled": enabled}
        trip_file.write_text(json.dumps(trip, indent=2, ensure_ascii=False), encoding="utf-8")
        changed += 1
    for preset_file, presets, changed_presets in preset_plan:
        for preset, enabled in changed_presets:
            preset["official_warnings"] = {"enabled": enabled}
        preset_file.write_text(
            json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        changed += 1
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {root}", file=sys.stderr)
        return 1

    trip_plan, preset_plan, report_lines = _collect_plan(root)

    print(f"Migrationsplan für root: {root}")
    for line in report_lines:
        print(line)
    if not trip_plan and not preset_plan:
        print("Nichts zu tun -- keine migrationsbedürftigen Trips/Presets gefunden.")

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if not trip_plan and not preset_plan:
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    try:
        backup_path = _make_backup(root, backup_dir)
    except OSError as exc:
        print(f"Error: Backup nach '{backup_dir}' fehlgeschlagen -- {exc}", file=sys.stderr)
        return 1
    print(f"Backup geschrieben: {backup_path}")

    total = _apply(trip_plan, preset_plan)
    print(f"Migration abgeschlossen: {total} Datei(en) migriert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
