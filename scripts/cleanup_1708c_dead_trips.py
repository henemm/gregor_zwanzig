#!/usr/bin/env python3
"""Bereinigungs-Script für Issue #1708 Scheibe C — entfernt die tote
`trips`/`trips.TOT-legacy-…`-Ablage unter `users/<id>/` (seit #1250
Scheibe 7a durch `briefings/` abgelöst, seit Scheibe A/B produktivcodeseitig
ohne Leser/Schreiber).

Spec: docs/specs/modules/fix_1708_c_tote_ablage_loeschen.md. Vorbild:
`scripts/cleanup_1265_prod_testdata.py` (Dry-Run-Default, --execute,
tar.gz-Backup vor Löschung). Anders als das Vorbild arbeitet dieses Script
mit einer Muster-Liste statt einer Einzel-User-Positivliste, da die drei
Wurzeln (Prod/Staging/lokal) unterschiedliche Nutzerbestände haben, und
sichert nur die betroffenen `trips*`-Unterordner statt der gesamten
`users_root`.

Usage:
    python3 scripts/cleanup_1708c_dead_trips.py --root <users_root> \\
        [--backup-dir <path>] [--execute]

stdlib-only — läuft ohne `uv run`/venv per `sudo -n python3 ...` gegen
Prod/Staging, wo Dateien anderem Owner gehören.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

# Beide Namensmuster gelten gleichwertig als Löschziel (Spec Implementation
# Details, "Cleanup-Script").
TARGET_DIR_NAMES = ["trips", "trips.TOT-legacy-1250-nicht-lesen"]

# Referenzdatum #1250 Scheibe 7a / ADR-0023 — Dateien mit neuerer mtime lösen
# nur eine informative Warnung aus, keinen Abbruch (Spec AC-5).
CUTOVER_DATE = datetime(2026, 7, 15)

# Konten-Check (Abbruch-Wirkung, Spec AC-4): mindestens `default` muss unter
# --root existieren, sonst zeigt --root vermutlich auf das falsche
# Verzeichnis.
REQUIRED_ACCOUNTS = ("default",)


def _plan_targets(users_root: Path) -> list[Path]:
    """Gefundene `trips`/`trips.TOT-legacy-…`-Unterordner je `users/<id>/`."""
    if not users_root.is_dir():
        return []
    targets = []
    for user_dir in sorted(users_root.iterdir()):
        if not user_dir.is_dir():
            continue
        for name in TARGET_DIR_NAMES:
            candidate = user_dir / name
            if candidate.is_dir():
                targets.append(candidate)
    return targets


def _missing_required_accounts(users_root: Path) -> list[str]:
    return [name for name in REQUIRED_ACCOUNTS if not (users_root / name).is_dir()]


def _time_warnings(targets: list[Path]) -> list[str]:
    """Dateien innerhalb eines Zielordners mit mtime nach CUTOVER_DATE —
    informativ, kein Abbruch (Spec AC-5)."""
    warnings = []
    for target in targets:
        for path in target.rglob("*"):
            if path.is_file() and datetime.fromtimestamp(path.stat().st_mtime) > CUTOVER_DATE:
                warnings.append(str(path))
    return warnings


def _make_backup(targets: list[Path], users_root: Path, backup_dir: Path) -> Path:
    """Sichert nur die betroffenen `trips*`-Unterordner, nicht die gesamte
    `users_root` (Spec-Vorgabe, weicht vom 1265-Vorbild ab)."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"cleanup-1708c-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        for target in targets:
            arcname = str(target.relative_to(users_root.parent))
            tar.add(target, arcname=arcname)
    return backup_path


def run_cleanup(users_root: Path, backup_dir: Path, execute: bool = False) -> dict:
    """Kern-Funktion (Test-Vertrag): Dry-Run meldet Kandidaten ohne zu
    schreiben; Execute sichert per tar.gz-Backup, löscht dann exakt die
    gefundenen `trips*`-Unterordner. Konten-Check bricht vor jedem Schreiben
    ab; die Zeit-Warnung blockiert nicht. Idempotent (zweiter Lauf: 0
    Aktionen, kein Backup)."""
    users_root = Path(users_root)
    backup_dir = Path(backup_dir)

    targets = _plan_targets(users_root)

    result: dict = {
        "would_remove": [str(t) for t in targets],
        "time_warnings": _time_warnings(targets),
        "actions": 0,
        "backup_path": None,
        "error": None,
    }

    if not execute:
        return result

    missing_accounts = _missing_required_accounts(users_root)
    if missing_accounts:
        result["error"] = (
            f"Abbruch: {users_root} enthält nicht die erwarteten Konten "
            f"({', '.join(missing_accounts)} fehlen) — falsches --root? "
            "Kein Backup geschrieben, nichts gelöscht."
        )
        return result

    if not targets:
        return result

    backup_path = _make_backup(targets, users_root, backup_dir)
    result["backup_path"] = str(backup_path)
    print(f"Backup geschrieben: {backup_path} (Restore: tar xzf {backup_path} -C <ziel>)")

    actions = 0
    for target in targets:
        shutil.rmtree(target)
        actions += 1
    result["actions"] = actions
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    users_root = args.root.resolve()
    if not users_root.exists() or not users_root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {users_root}", file=sys.stderr)
        return 1
    backup_dir = (args.backup_dir or (users_root.parent / ".backups")).resolve()

    result = run_cleanup(users_root, backup_dir, execute=args.execute)

    print(f"Root: {users_root}")
    print(f"Kandidaten ({len(result['would_remove'])}): {result['would_remove']}")
    for warning in result["time_warnings"]:
        print(f"WARNUNG: Datei neuer als 2026-07-15 (#1250 Scheibe 7a): {warning}")

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if result["backup_path"]:
        print(f"Backup: {result['backup_path']}")
    print(f"Aktionen: {result['actions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
