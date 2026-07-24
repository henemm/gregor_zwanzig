#!/usr/bin/env python3
"""Migration für Issue #1351 Teil 2 (AC-6/AC-7/AC-8) — entfernt toten
`channel_layouts`-Ballast aus bestehenden Vergleichs-Presets (`kind=vergleich`)
unter `<root>/<uid>/briefings/<id>.json`. Trip-Presets (`kind=route`) bleiben
unangetastet — `channel_layouts` ist dort eine echte, funktionale Kanal-
Kaskadenstufe (`per_channel_layouts`, `src/app/models.py:595`).

Spec: docs/specs/modules/rework_1351_compare_catalog.md, Abschnitt "Teil 2".
Strukturelles Vorbild: `scripts/migrate_1191_compare_active_metrics.py`,
`scripts/migrate_1244_null_lists.py`, `scripts/migrate_1250_briefings.py`
(Dry-Run-Default, `--execute`, tar.gz-Backup vor jedem schreibenden Lauf,
Idempotenz, Read-Modify-Write-Merge — kein Replace, BUG-DATALOSS-GR221).

Usage:
    python3 scripts/migrate_1351_drop_compare_channel_layouts.py --root <data/users> \\
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


def _needs_migration(preset: dict) -> bool:
    """True NUR für Vergleichs-Presets (`kind=vergleich`), deren
    `display_config.channel_layouts` noch existiert. Trip-Presets (`kind=route`
    oder jedes andere `kind`) werden NIE angefasst (AC-8)."""
    if preset.get("kind") != "vergleich":
        return False
    display_config = preset.get("display_config")
    if not isinstance(display_config, dict):
        return False
    return "channel_layouts" in display_config


def _plan(root: Path) -> list[Path]:
    """Sammelt Pfade zu Vergleichs-Presets mit totem `channel_layouts`-Feld."""
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
    backup_path = backup_dir / f"migrate-1351-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(preset_file: Path) -> None:
    """Read-Modify-Write-Merge: entfernt NUR `channel_layouts` aus
    `display_config`, alle anderen Felder (inkl. unbekannter Zukunftsfelder)
    bleiben unverändert (BUG-DATALOSS-GR221: kein Replace)."""
    preset = json.loads(preset_file.read_text(encoding="utf-8"))
    preset["display_config"].pop("channel_layouts", None)
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
        print("Nichts zu tun — keine Vergleichs-Presets mit channel_layouts gefunden.")

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

    for preset_file in plan:
        _apply(preset_file)
    print(f"Migration abgeschlossen: {len(plan)} Preset(s) von channel_layouts befreit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
