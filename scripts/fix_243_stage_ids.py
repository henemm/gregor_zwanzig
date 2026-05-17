#!/usr/bin/env python3
"""Einmalige Migration: leere Stage-IDs in allen Trip-JSONs backfüllen (Issue #243)."""
import json
import os
import secrets
import sys
from pathlib import Path

data_dir = Path("data/users")
if not data_dir.exists():
    print("data/users/ nicht gefunden — falsches Verzeichnis?", file=sys.stderr)
    sys.exit(1)

fixed = 0
for trip_file in data_dir.glob("*/trips/*.json"):
    with open(trip_file) as f:
        trip = json.load(f)

    changed = False
    for stage in trip.get("stages", []):
        if not stage.get("id"):
            stage["id"] = secrets.token_hex(4)
            changed = True

    if changed:
        with open(trip_file, "w") as f:
            json.dump(trip, f, ensure_ascii=False, indent=2)
        print(f"Gefixt: {trip_file}")
        fixed += 1

print(f"\nFertig: {fixed} Trip(s) migriert.")
