#!/usr/bin/env python3
"""Migration for Issue #1219 (Scheibe 1) — setzt `email_verified_at` für die
real existierenden Konten `henning`/`steffi`.

Spec: docs/specs/modules/fix_1219_email_verify.md, Abschnitt 5.
Strukturelles Vorbild: scripts/cleanup_1133_testdata.py (Dry-Run-Default,
--execute, tar.gz-Backup vor jedem --execute-Lauf, Idempotenz).

Usage:
    python3 scripts/migrate_1219_email_verified.py --root <path/to/data/users> \\
        [--backup-dir <path>] [--execute] [--force]

Ohne `--root` ist ein Lauf gegen einen echten Baum unmöglich (analog #1133).

Behavior:
    1. tar.gz-Backup des vollen `--root`-Baums nach `--backup-dir` (Default:
       `<root>/../.backups/`) VOR jeder Ausführung mit `--execute`.
    2. Für jedes Konto der festen Positivliste (`henning`, `steffi`):
       `<root>/<id>/user.json` per Read-Modify-Write laden, NUR
       `email_verified_at` ergänzen (aktueller UTC-ISO-8601-Zeitstempel),
       alle anderen Felder unangetastet lassen, zurückschreiben.
    3. Idempotent: ist `email_verified_at` bereits gesetzt, wird das Konto
       übersprungen (kein Überschreiben ohne `--force`).
    4. Dry-Run per Default (zeigt nur den Änderungsplan), `--execute` führt
       aus.
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

POSITIVLIST = ["henning", "steffi"]


def _plan(root: Path, force: bool) -> tuple[list[str], list[str]]:
    """Returns (to_update, to_skip) account IDs."""
    to_update: list[str] = []
    to_skip: list[str] = []
    for user_id in POSITIVLIST:
        profile_path = root / user_id / "user.json"
        if not profile_path.is_file():
            to_skip.append(f"{user_id} (user.json fehlt: {profile_path})")
            continue
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            to_skip.append(f"{user_id} (kaputte user.json: {exc})")
            continue
        if profile.get("email_verified_at") and not force:
            to_skip.append(f"{user_id} (email_verified_at bereits gesetzt)")
            continue
        to_update.append(user_id)
    return to_update, to_skip


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"migrate-1219-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(root: Path, to_update: list[str]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for user_id in to_update:
        profile_path = root / user_id / "user.json"
        # Read-Modify-Write-Merge: volles Profil laden, NUR das eine Feld
        # ergänzen — nie überschreiben/ersetzen (Datenverlust-Regel).
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["email_verified_at"] = now
        profile_path.write_text(
            json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Aktualisiert: {user_id} -> email_verified_at={now}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {root}", file=sys.stderr)
        return 1

    to_update, to_skip = _plan(root, args.force)

    print(f"Migrationsplan für root: {root}")
    print(f"  Zu aktualisieren ({len(to_update)}): {to_update}")
    print(f"  Übersprungen ({len(to_skip)}): {to_skip}")

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if not to_update:
        print("Nichts zu tun — alle Konten bereits verifiziert oder nicht gefunden.")
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    backup_path = _make_backup(root, backup_dir)
    print(f"Backup geschrieben: {backup_path}")

    _apply(root, to_update)
    print("Migration abgeschlossen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
