#!/usr/bin/env python3
"""Nachtrag fuer Issue #2406 (S3 aus #2153) — traegt fuer jede heute
eingetragene SMS-Nummer den Bestaetigungsstand nach.

Spec: docs/specs/modules/sms_nummer_verifikation.md §10, AC-10.
Strukturelles Vorbild: scripts/backfill_2271_email_verified.py (Dry-Run-Default,
--execute, tar.gz-Backup vor jedem --execute-Lauf, Read-Modify-Write,
Idempotenz).

Ohne diesen Nachtrag sperrte die Fail-closed-Sperre in
``src/app/config.py::with_user_profile`` jedes Bestandskonto aus — mitten in
einer laufenden Tour. Der Nachtrag MUSS deshalb laufen, waehrend kein Prozess
``user.json`` schreiben kann (Deploy-Reihenfolge, Spec §11).

Usage:
    python3 scripts/backfill_2406_sms_verified.py --root <path/to/users> \\
        [--backup-dir <path>] [--execute]

Behavior:
    1. Dry-Run per Default: nennt die betroffenen Konto-IDs, aendert nichts.
    2. ``--execute``: tar.gz-Backup des vollen ``--root``-Baums VOR der ersten
       Aenderung, dann je Konto Read-Modify-Write — nur die zwei neuen Felder
       kommen hinzu, alle uebrigen (auch dem Skript unbekannte) bleiben
       unangetastet.
    3. Plan-Kriterium: ``sms_to`` nicht leer UND ``sms_verified_number`` noch
       nicht gesetzt. Konten ohne Nummer haben nichts zu bestaetigen.
    4. ``sms_verified_number`` ist die UNVERAENDERTE Kopie des gelesenen
       ``sms_to`` (kein Trimmen hier) — die Normalisierungs-Symmetrie entsteht
       an der Wirkstelle (config.py, AC-12), nicht im Nachtrag.
    5. Idempotent: ein bereits gesetztes ``sms_verified_number`` wird NIE
       ueberschrieben. Keine Lesepfad-Ausnahme "Feld fehlt ⇒ gilt als
       bestaetigt".

Bekannte Grenze (wie beim E-Mail-Vorbild): eine heute bereits fremd
eingetragene Nummer wird ebenfalls als bestaetigt uebernommen — die Luecke
schliesst sich nur fuer kuenftige Aenderungen.
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
    bliebe ein spaeter angelegtes Konto stillschweigend ausgesperrt.
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
        if not (profile.get("sms_to") or "").strip():
            to_skip.append(f"{entry.name} (keine sms_to)")
            continue
        if profile.get("sms_verified_number"):
            to_skip.append(f"{entry.name} (sms_verified_number bereits gesetzt)")
            continue
        to_update.append(entry.name)
    return to_update, to_skip


def _make_backup(root: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"backfill-2406-{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        tar.add(root, arcname=root.name)
    return backup_path


def _apply(root: Path, to_update: list[str]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for user_id in to_update:
        profile_path = root / user_id / "user.json"
        # Read-Modify-Write-Merge: volles Profil laden, NUR die zwei Felder
        # ergaenzen — nie ersetzen (BUG-DATALOSS-GR221 / #102).
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["sms_verified_number"] = profile["sms_to"]
        profile["sms_verified_at"] = now
        profile_path.write_text(
            json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Aktualisiert: {user_id} -> sms_verified_number={profile['sms_to']!r}")


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
        print("Nichts zu tun — alle Konten mit Nummer tragen bereits den Nachweis.")
        return 0

    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    backup_path = _make_backup(root, backup_dir)
    print(f"Backup geschrieben: {backup_path}")

    _apply(root, to_update)
    print("Nachtrag abgeschlossen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
