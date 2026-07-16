#!/usr/bin/env python3
"""Migration für Issue #1262 — heilt Legacy-Flach-String-`display_config.metrics`
in bestehenden briefings/*.json-Dateien zur dict-Form.

Spec: docs/specs/modules/fix_1262_legacy_flat_metrics.md, AC-5. Vorbild:
scripts/migrate_1244_null_lists.py (Dry-Run-Default, `--execute`, `--root`,
tar.gz-Backup, zweiphasig `_collect_plan`/`_apply`, Read-Modify-Write nach
BUG-DATALOSS-GR221-Prinzip, Idempotenz).

Hintergrund: Ein Trip, dessen `display_config.metrics` als Flach-String-Liste
(`["temperature", "wind_speed"]`) gespeichert ist, crasht beim Laden. Der
Python-Loader heilt sich seit Issue #1262 selbst beim naechsten Lesen
(fail-soft), aber die Datei auf Platte bleibt Flach-String, bis sie ueber
`save_trip` neu geschrieben ODER dieses Skript ausgefuehrt wird.

Wie migrate_1244_null_lists.py gilt: ein LEERER Plan beim zweiten (idempotenten)
Lauf ist der Erfolgsfall, kein Fehler -- Exit 0.

Usage:
    python3 scripts/migrate_1262_flat_metrics.py --root <data/users> \\
        [--backup-dir <path>] [--execute]
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def _fix_metrics(trip: dict) -> tuple[dict, bool]:
    """Read-Modify-Write: nur Flach-String-Eintraege in
    `display_config.metrics` zu `{"metric_id": s, "enabled": true}`
    umschreiben. ALLE anderen Keys (auch unbekannte) bleiben unangetastet.
    Gibt (evtl. geaenderter Trip, changed?) zurueck -- trip wird NICHT
    in-place mutiert."""
    display = trip.get("display_config")
    if not isinstance(display, dict):
        return trip, False
    metrics = display.get("metrics")
    if not isinstance(metrics, list) or not any(isinstance(m, str) for m in metrics):
        return trip, False

    new_metrics = [
        {"metric_id": m, "enabled": True} if isinstance(m, str) else m
        for m in metrics
    ]
    fixed = dict(trip)
    fixed["display_config"] = {**display, "metrics": new_metrics}
    return fixed, True


def _collect_plan(root: Path) -> list[tuple[Path, dict]]:
    """Sammelt alle briefings/*.json (nur `kind` != "vergleich"), deren
    `display_config.metrics` mindestens einen Flach-String-Eintrag hat, und
    liefert (Datei, repariertes-dict). Schreibt noch nichts. Nicht
    lesbare/parsebare Dateien werden uebersprungen."""
    plan: list[tuple[Path, dict]] = []
    for trip_file in sorted(root.glob("*/briefings/*.json")):
        try:
            trip = json.loads(trip_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(trip, dict) or trip.get("kind") == "vergleich":
            continue
        fixed, changed = _fix_metrics(trip)
        if changed:
            plan.append((trip_file, fixed))
    return plan


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"migrate-1262-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(plan: list[tuple[Path, dict]]) -> int:
    """Read-Modify-Write: schreibt die bereits reparierten Objekte. Gibt die
    Anzahl geschriebener Dateien zurueck."""
    changed = 0
    for trip_file, fixed in plan:
        trip_file.write_text(
            json.dumps(fixed, indent=2, ensure_ascii=False), encoding="utf-8"
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

    plan = _collect_plan(root)
    print(f"Migrationsplan für root: {root}")
    for trip_file, _ in plan:
        print(f"  {trip_file}: Flach-String-metrics -> dict-Form")
    if not plan:
        print("Nichts zu tun -- keine Flach-String-metrics gefunden.")

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if not plan:
        # Idempotenter zweiter Lauf: leerer Plan ist der Erfolgsfall.
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    try:
        backup_path = _make_backup(root, backup_dir)
    except OSError as exc:
        print(f"Error: Backup nach '{backup_dir}' fehlgeschlagen -- {exc}", file=sys.stderr)
        return 1
    print(f"Backup geschrieben: {backup_path}")

    changed = _apply(plan)
    print(f"Migration abgeschlossen: {changed} Datei(en) migriert.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
