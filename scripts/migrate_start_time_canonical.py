"""Issue #991 (AC-6): Migration — start_time auf kanonisches "HH:MM" normalisieren.

Persistierte Trip-JSONs enthalten gemischte start_time-Formate ("HH:MM" und
"HH:MM:SS"), weil Go start_time als opaquen String durchreicht. Diese Migration
ersetzt AUSSCHLIESSLICH das Sekunden-Suffix in "start_time"-Werten — rein
string-basiert per Regex am Dateitext, KEIN json.load/dump. Das verhindert
jede Umformatierung/jeden Feldverlust an anderen Stellen der Datei.

Idempotent: ein zweiter Lauf matcht keine "HH:MM"-Werte mehr (das Regex
verlangt ein ":\\d{2}"-Sekunden-Suffix).

Backup: vor jedem Schreib-Lauf wird ein tar.gz aller
data/users/*/trips/*.json nach .backups/start_time_migration_<timestamp>.tar.gz
angelegt.

Usage:
    uv run python scripts/migrate_start_time_canonical.py [--dry-run] [--data-dir PATH]
"""
from __future__ import annotations

import argparse
import re
import tarfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Matcht "start_time": "HH:MM:SS" (mit beliebigem Whitespace um den Doppelpunkt
# im JSON-Key) und kappt das Sekunden-Suffix. "HH:MM" (ohne Sekunden-Suffix)
# matcht NICHT -> idempotent.
START_TIME_PATTERN = re.compile(
    r'("start_time"\s*:\s*")(\d{2}:\d{2}):\d{2}(")'
)


def find_trip_files(data_dir: Path) -> list[Path]:
    return sorted(data_dir.glob("*/trips/*.json"))


def migrate_text(text: str) -> tuple[str, int]:
    """Reine Text-Transformation. Returns (new_text, replacement_count)."""
    new_text, count = START_TIME_PATTERN.subn(r"\1\2\3", text)
    return new_text, count


def make_backup(trip_files: list[Path], data_dir: Path) -> Path:
    backup_dir = PROJECT_ROOT / ".backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup_path = backup_dir / f"start_time_migration_{timestamp}.tar.gz"
    with tarfile.open(backup_path, "w:gz") as tar:
        for f in trip_files:
            tar.add(f, arcname=str(f.relative_to(data_dir.parent)))
    return backup_path


def main(data_dir: Path, dry_run: bool = False) -> int:
    if not data_dir.exists():
        print(f"FAIL: {data_dir} fehlt")
        return 1

    trip_files = find_trip_files(data_dir)
    if not trip_files:
        print(f"Keine Trip-JSONs unter {data_dir} gefunden.")
        return 0

    print(f"Migrations-Lauf{' (DRY-RUN)' if dry_run else ''} ueber {len(trip_files)} Trip-File(s):")

    affected: list[tuple[Path, int]] = []
    for path in trip_files:
        text = path.read_text()
        new_text, count = migrate_text(text)
        if count > 0:
            affected.append((path, count))

    if dry_run:
        for path, count in affected:
            print(f"  would-change: {path} ({count} replacement(s))")
        print(
            f"\nZusammenfassung (DRY-RUN): {len(trip_files)} geprueft, "
            f"{len(affected)} betroffen, "
            f"{sum(c for _, c in affected)} Ersetzung(en) insgesamt."
        )
        return 0

    if affected:
        backup_path = make_backup(trip_files, data_dir)
        print(f"Backup angelegt: {backup_path}")

    total_replacements = 0
    changed_count = 0
    for path, _count in affected:
        text = path.read_text()
        new_text, count = migrate_text(text)
        if count > 0:
            path.write_text(new_text)
            changed_count += 1
            total_replacements += count
            print(f"  changed: {path} ({count} replacement(s))")

    print(
        f"\nZusammenfassung: {len(trip_files)} geprueft, "
        f"{changed_count} geaendert, "
        f"{total_replacements} Ersetzung(en) insgesamt."
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts schreiben")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "users",
        help="Basisverzeichnis mit <user_id>/trips/*.json (Default: data/users)",
    )
    args = parser.parse_args()
    raise SystemExit(main(args.data_dir, dry_run=args.dry_run))
