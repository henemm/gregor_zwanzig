"""
Backfill-Migration — Issue #802: arrival_calculated für alle Bestandstrips befüllen.

Idempotent (#102-konform): Lädt alle Trips pro Nutzer über save_trip neu (berechnet
arrival_calculated via Compute-on-Save). Stage-/Waypoint-Counts bleiben unverändert,
time_window/arrival_override werden bewahrt.

Usage:
    python scripts/backfill_arrival_calculated_802.py [--dry-run]
    python scripts/backfill_arrival_calculated_802.py --user default
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def backfill_user(user_id: str, data_dir: Optional[Path] = None) -> dict:
    """Füllt arrival_calculated für alle Trips eines Nutzers nach (Compute-on-Save).

    Args:
        user_id: Nutzer-ID (Verzeichnisname unter data/users/).
        data_dir: Optionales Basisverzeichnis (für Tests); Standard: data/ im Projektroot.

    Returns:
        {"trips_updated": N, "trips_total": M}
    """
    from app.loader import save_trip, load_trip

    if data_dir is None:
        # Standard-Pfad relativ zum Projektroot
        data_dir = Path(__file__).parent.parent / "data"

    trips_dir = Path(data_dir) / "users" / user_id / "trips"
    if not trips_dir.exists():
        logger.info("Kein Trips-Verzeichnis für Nutzer %s: %s", user_id, trips_dir)
        return {"trips_updated": 0, "trips_total": 0}

    trip_files = list(trips_dir.glob("*.json"))
    trips_total = len(trip_files)
    trips_updated = 0

    for trip_file in trip_files:
        try:
            trip_id = trip_file.stem
            trip = load_trip(trip_id, user_id=user_id, data_dir=data_dir)
            if trip is None:
                logger.warning("Trip %s konnte nicht geladen werden", trip_id)
                continue
            save_trip(trip, user_id=user_id, data_dir=data_dir)
            trips_updated += 1
            logger.debug("Backfill OK: %s/%s", user_id, trip_id)
        except Exception as exc:
            logger.error("Fehler bei Trip %s/%s: %s", user_id, trip_file.name, exc)

    return {"trips_updated": trips_updated, "trips_total": trips_total}


def backfill_user_dry_run(user_id: str, data_dir: Optional[Path] = None) -> list:
    """Listet alle Trips ohne Schreiben (--dry-run).

    Returns:
        Liste von Trip-IDs die betroffen wären.
    """
    if data_dir is None:
        data_dir = Path(__file__).parent.parent / "data"

    trips_dir = Path(data_dir) / "users" / user_id / "trips"
    if not trips_dir.exists():
        return []
    return [f.stem for f in trips_dir.glob("*.json")]


def _find_users(data_dir: Path) -> list:
    """Gibt alle Nutzer-IDs unter data/users/ zurück."""
    users_dir = data_dir / "users"
    if not users_dir.exists():
        return []
    return [d.name for d in users_dir.iterdir() if d.is_dir()]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Backfill arrival_calculated für alle Trips (Issue #802)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Nur auflisten, nicht schreiben.",
    )
    parser.add_argument(
        "--user", default=None,
        help="Nur diesen Nutzer backfillen (Standard: alle).",
    )
    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / "data"
    users = [args.user] if args.user else _find_users(data_dir)

    if not users:
        print("Keine Nutzer gefunden.")
        sys.exit(0)

    total_updated = 0
    total_trips = 0

    for user_id in users:
        if args.dry_run:
            affected = backfill_user_dry_run(user_id, data_dir=data_dir)
            print(f"[dry-run] {user_id}: {len(affected)} Trips → {affected}")
        else:
            stats = backfill_user(user_id, data_dir=data_dir)
            print(f"{user_id}: {stats['trips_updated']}/{stats['trips_total']} Trips aktualisiert")
            total_updated += stats["trips_updated"]
            total_trips += stats["trips_total"]

    if not args.dry_run:
        print(f"\nGesamt: {total_updated}/{total_trips} Trips backgefüllt.")


if __name__ == "__main__":
    main()
