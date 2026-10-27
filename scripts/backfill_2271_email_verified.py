#!/usr/bin/env python3
"""Nachtrag fuer Issue #2304 (S1 aus #2271/#2146) — traegt `email_verified_at`
fuer ALLE Bestandskonten unter `--root` nach, die es noch nicht tragen.

Spec: docs/specs/modules/email_verify_vorbereitung_2304.md, AC-1..AC-3.
Strukturelles Vorbild: scripts/migrate_1219_email_verified.py (Dry-Run-Default,
--execute, tar.gz-Backup vor jedem --execute-Lauf, Read-Modify-Write,
Idempotenz). Anders als das Vorbild: KEINE feste Positivliste — betroffen ist
jedes Konto unter `--root`, dessen `user.json` noch kein `email_verified_at`
haelt. Damit sperrt die spaetere Login-Pflicht (#2271) niemanden aus.

Usage:
    python3 scripts/backfill_2271_email_verified.py --root <path/to/users> \\
        [--backup-dir <path>] [--execute]

Ohne `--root` ist ein Lauf gegen einen echten Baum unmoeglich.

Behavior:
    1. Dry-Run per Default: nennt die betroffenen Konto-IDs auf stdout und
       veraendert keine einzige Datei.
    2. `--execute`: tar.gz-Backup des vollen `--root`-Baums VOR der ersten
       Aenderung, dann je Konto Read-Modify-Write — nur `email_verified_at`
       kommt hinzu, alle uebrigen Felder (auch dem Skript unbekannte) bleiben
       unangetastet.
    3. Idempotent: ein bereits gesetzter Zeitstempel wird NIE ueberschrieben.
    4. Exit 0 in beiden Betriebsarten, solange `--root` lesbar ist.
"""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def _plan(root: Path) -> tuple[list[str], list[str]]:
    """Returns (to_update, to_skip) account IDs.

    Aufgezaehlt wird der Baum selbst — kein handgepflegter Katalog, sonst
    bliebe ein spaeter angelegtes Konto stillschweigend unbestaetigt.
    """
    to_update: list[str] = []
    to_skip: list[str] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        profile_path = entry / "user.json"
        if not profile_path.is_file():
            continue
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            to_skip.append(f"{entry.name} (kaputte user.json: {exc})")
            continue
        if profile.get("email_verified_at"):
            to_skip.append(f"{entry.name} (email_verified_at bereits gesetzt)")
            continue
        to_update.append(entry.name)
    return to_update, to_skip


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"backfill-2271-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(root: Path, to_update: list[str]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for user_id in to_update:
        profile_path = root / user_id / "user.json"
        # Read-Modify-Write-Merge: volles Profil laden, NUR das eine Feld
        # ergaenzen — nie ersetzen (BUG-DATALOSS-GR221 / #102).
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
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {root}", file=sys.stderr)
        return 1

    to_update, to_skip = _plan(root)

    print(f"Nachtragsplan fuer root: {root}")
    print(f"  Zu aktualisieren ({len(to_update)}): {to_update}")
    print(f"  Uebersprungen ({len(to_skip)}): {to_skip}")

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausfuehren).")
        return 0

    if not to_update:
        print("Nichts zu tun — alle Konten tragen bereits einen Zeitstempel.")
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    backup_path = _make_backup(root, backup_dir)
    print(f"Backup geschrieben: {backup_path}")

    _apply(root, to_update)
    print("Nachtrag abgeschlossen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
