#!/usr/bin/env python3
"""
Verifikations-Skript fuer ActivityProfile-Harmonisierung (Issue #98).

Scant rekursiv alle JSON-Dateien unter --data-dir (Default: data/users) und
prueft jeden gefundenen Profile-Wert gegen die kanonische Whitelist:

    {wintersport, wandern, summer_trekking, allgemein}

Erkannte Felder:
- Trip-JSON          : data["aggregation"]["profile"]
- Location-JSON      : data["activity_profile"]
- Compare-Subscriptions (Liste): item["activity_profile"] pro Eintrag

Exit-Codes:
- 0: Alle gefundenen Werte sind gueltig (oder kein Wert vorhanden).
- 1: Mindestens ein unbekannter Wert wurde gefunden.

Usage:
    uv run python3 scripts/verify_activity_profile_migration.py
    uv run python3 scripts/verify_activity_profile_migration.py --data-dir data/users
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple


VALID_VALUES = {"wintersport", "wandern", "summer_trekking", "allgemein"}


def _check_value(val: object, source: Path, errors: List[str]) -> int:
    """Validate a single profile-string. Returns 1 if a value was checked, else 0."""
    if val is None:
        return 0
    if not isinstance(val, str):
        errors.append(f"Unbekannter Wert '{val!r}' in {source}")
        return 1
    if val not in VALID_VALUES:
        errors.append(f"Unbekannter Wert '{val}' in {source}")
    return 1


def scan_dir(data_dir: Path) -> Tuple[int, int, List[str]]:
    """Walk data_dir recursively and validate profile-fields in JSON files.

    Returns (files_scanned, profiles_found, errors).
    JSON-decode errors are reported on stderr but do not abort the scan.
    """
    errors: List[str] = []
    files_scanned = 0
    profiles_found = 0

    if not data_dir.exists():
        # Nothing to check is not an error — script exits 0.
        return (0, 0, errors)

    for path in sorted(data_dir.rglob("*.json")):
        files_scanned += 1
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARN: konnte {path} nicht parsen: {exc}", file=sys.stderr)
            continue

        if isinstance(data, dict):
            agg = data.get("aggregation")
            if isinstance(agg, dict) and "profile" in agg:
                profiles_found += _check_value(agg.get("profile"), path, errors)
            if "activity_profile" in data:
                profiles_found += _check_value(
                    data.get("activity_profile"), path, errors
                )
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "activity_profile" in item:
                    profiles_found += _check_value(
                        item.get("activity_profile"), path, errors
                    )

    return (files_scanned, profiles_found, errors)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifiziere ActivityProfile-Werte in data/users/."
    )
    parser.add_argument(
        "--data-dir",
        default="data/users",
        help="Wurzelverzeichnis fuer den Scan (default: data/users).",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    files_scanned, profiles_found, errors = scan_dir(data_dir)

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    print(
        f"OK: {files_scanned} Dateien gescannt, "
        f"{profiles_found} Profile-Werte alle gueltig"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
