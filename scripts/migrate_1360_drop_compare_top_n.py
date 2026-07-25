#!/usr/bin/env python3
"""Migration für Issue #1360 (AC-8) — entfernt den toten `top_n`-Ballast aus dem
alten Layout-Reiter aus bestehenden Vergleichs-Presets (`kind=vergleich`) unter
`<root>/<uid>/briefings/<id>.json`. Trip-Presets (`kind=route`) bleiben
unangetastet.

Warum: `top_n` wurde seit der PO-Entscheidung 2026-07-08 von JEDEM Compare-
Render-Pfad verworfen (`compare_html.py`: `_ = top_n_details`) und ist mit
dieser Scheibe auch aus der Auflösung entfernt (`report_config_resolver.py`).
Ein Schlüssel ohne Konsument gehört nicht in die Daten — aber er wird bewusst
per einmaliger, nachvollziehbarer Bereinigung entfernt, NICHT als Nebenwirkung
eines Speichervorgangs (der Editor kennt nicht alle Preset-Felder; ein
verwerfendes Speichern löschte Fremdes mit — BUG-DATALOSS-GR221 / #102).

Spec: docs/specs/modules/compare_layout_tab_dissolution.md, Implementation
Details Punkt 6. Strukturelles Vorbild:
`scripts/migrate_1351_drop_compare_channel_layouts.py` (#1351, Commit
08d3fb91) — Dry-Run-Default, `--execute`, tar.gz-Backup vor jedem schreibenden
Lauf, zweiphasig Plan->Apply, Idempotenz, Read-Modify-Write-Merge.

NICHT betroffen: `hour_from`/`hour_to` (werden in Scheibe S1b/#1361 bedienbar)
und `channel_layouts` (bereits mit #1351 bereinigt).

Usage:
    python3 scripts/migrate_1360_drop_compare_top_n.py --root <data/users> \\
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
    `display_config.top_n` noch existiert. Jedes andere `kind` (insbesondere
    `route`) wird NIE angefasst."""
    if preset.get("kind") != "vergleich":
        return False
    display_config = preset.get("display_config")
    if not isinstance(display_config, dict):
        return False
    return "top_n" in display_config


def _plan(root: Path) -> list[Path]:
    """Sammelt Pfade zu Vergleichs-Presets mit totem `top_n`-Feld — über ALLE
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
    backup_path = backup_dir / f"migrate-1360-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(preset_file: Path) -> None:
    """Read-Modify-Write-Merge: entfernt NUR `top_n` aus `display_config`, alle
    anderen Felder (inkl. `hour_from`/`hour_to` und unbekannter Zukunftsfelder)
    bleiben unverändert (BUG-DATALOSS-GR221: kein Replace)."""
    preset = json.loads(preset_file.read_text(encoding="utf-8"))
    preset["display_config"].pop("top_n", None)
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
        print("Nichts zu tun — keine Vergleichs-Presets mit top_n gefunden.")

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

    # Adversary Runde 2 (F001, MEDIUM): Schreibfehler duerfen nicht als roher
    # Traceback beim Deploy landen -- gleicher sauberer Fehlerpfad wie beim
    # Backup-Fehlschlag oben. Kein Datenverlust: die betroffene Datei bleibt
    # unveraendert, das Backup ist bereits geschrieben, ein zweiter Lauf holt
    # die uebrigen Presets nach (Idempotenz).
    failed: list[tuple[Path, OSError]] = []
    migrated = 0
    for preset_file in plan:
        try:
            _apply(preset_file)
        except OSError as exc:
            failed.append((preset_file, exc))
            continue
        migrated += 1

    print(f"Migration abgeschlossen: {migrated} Preset(s) von top_n befreit.")
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
