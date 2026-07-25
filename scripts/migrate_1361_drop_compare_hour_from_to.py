#!/usr/bin/env python3
"""Migration für Issue #1361/#1372 S1b (AC-8) — entfernt die toten Felder
`hour_from`/`hour_to` aus bestehenden Vergleichs-Presets (`kind=vergleich`)
unter `<root>/<uid>/briefings/<id>.json`. Trip-Presets (`kind=route`) bleiben
unangetastet.

Warum: `hour_from`/`hour_to` sind seit Issue #1268 aus Auflösung/Versand
ignoriert und verlieren mit dieser Scheibe auch ihre Bedienfläche — das neue
gemeinsame Tagesfenster (`day_window_start_hour`/`_end_hour`) übernimmt ihre
Rolle vollständig (Spec docs/specs/modules/compare_shared_day_window.md, PO-
Entscheidung 4: "Kein Übernehmen der Altwerte — das Fenster kommt aus der
gemeinsamen Quelle"). Ein Schlüssel ohne Konsument gehört nicht in die Daten,
wird aber bewusst per einmaliger, nachvollziehbarer Bereinigung entfernt,
NICHT als Nebenwirkung eines Speichervorgangs (BUG-DATALOSS-GR221 / #102).

Spec: docs/specs/modules/compare_shared_day_window.md, AC-8. Strukturelles
Vorbild: `scripts/migrate_1360_drop_compare_top_n.py` (#1360) — Dry-Run-
Default, `--execute`, tar.gz-Backup vor jedem schreibenden Lauf, zweiphasig
Plan->Apply, Idempotenz, Read-Modify-Write-Merge.

NICHT betroffen: `day_window_start_hour`/`_end_hour` (die neuen, wirksamen
Felder) und alle übrigen Preset-Felder.

Usage:
    python3 scripts/migrate_1361_drop_compare_hour_from_to.py --root <data/users> \\
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

_DEAD_FIELDS = ("hour_from", "hour_to")


def _needs_migration(preset: dict) -> bool:
    """True NUR für Vergleichs-Presets (`kind=vergleich`), die noch mindestens
    eines der toten Felder tragen. Jedes andere `kind` (insbesondere `route`)
    wird NIE angefasst."""
    if preset.get("kind") != "vergleich":
        return False
    return any(field in preset for field in _DEAD_FIELDS)


def _plan(root: Path) -> list[Path]:
    """Sammelt Pfade zu Vergleichs-Presets mit toten Feldern — über ALLE
    Nutzerverzeichnisse (Mandantenfähigkeit: kein `default`-Sonderweg)."""
    plan: list[Path] = []
    for preset_file in sorted(root.glob("*/briefings/*.json")):
        try:
            preset = json.loads(preset_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(preset, dict):
            continue
        if _needs_migration(preset):
            plan.append(preset_file)
    return plan


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"migrate-1361-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(preset_file: Path) -> None:
    """Read-Modify-Write-Merge: entfernt NUR hour_from/hour_to, alle anderen
    Felder (inkl. day_window_start_hour/_end_hour und unbekannter
    Zukunftsfelder) bleiben unverändert (BUG-DATALOSS-GR221: kein Replace)."""
    preset = json.loads(preset_file.read_text(encoding="utf-8"))
    for field in _DEAD_FIELDS:
        preset.pop(field, None)
    preset_file.write_text(
        json.dumps(preset, indent=2, ensure_ascii=False), encoding="utf-8"
    )


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

    plan = _plan(root)
    print(f"Migrationsplan für root: {root}")
    for preset_file in plan:
        print(f"  {preset_file}")
    if not plan:
        print("Nichts zu tun — keine Vergleichs-Presets mit hour_from/hour_to gefunden.")

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if not plan:
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    try:
        backup_path = _make_backup(root, backup_dir)
    except OSError as exc:
        # Ohne Backup kein Schreiben -- sonst waere ein Rollback nicht mehr moeglich.
        print(f"Error: Backup nach '{backup_dir}' fehlgeschlagen -- {exc}", file=sys.stderr)
        return 1
    print(f"Backup geschrieben: {backup_path}")

    # Schreibfehler duerfen nicht als roher Traceback beim Deploy landen —
    # gleicher saubere Fehlerpfad wie beim Backup-Fehlschlag oben. Kein
    # Datenverlust: die betroffene Datei bleibt unveraendert, das Backup ist
    # bereits geschrieben, ein zweiter Lauf holt die uebrigen Presets nach
    # (Idempotenz).
    failed: list[tuple[Path, OSError]] = []
    migrated = 0
    for preset_file in plan:
        try:
            _apply(preset_file)
        except OSError as exc:
            failed.append((preset_file, exc))
            continue
        migrated += 1

    print(f"Migration abgeschlossen: {migrated} Preset(s) von hour_from/hour_to befreit.")
    if failed:
        print(
            f"Error: {len(failed)} Preset(s) konnten nicht geschrieben werden "
            f"(unveraendert, Backup: {backup_path}):",
            file=sys.stderr,
        )
        for preset_file, exc in failed:
            print(f"  {preset_file} -- {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
