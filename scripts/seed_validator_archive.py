#!/usr/bin/env python3
"""Seed demo archive trips for the validator account.

Issue #583 — Archiv-Screen 1:1 nach screen-archive.jsx.
CLI: python3 scripts/seed_validator_archive.py --data-dir <DIR> --user <USERNAME>

Writes 8 archived Trip JSONs matching the JSX ARCHIVE_LIST mock data.
Idempotent: existing trips are overwritten on re-run.
"""
import argparse
import json
from datetime import date, timedelta
from pathlib import Path


TRIPS = [
    {
        "id": "ortler-2025",
        "name": "Ortler-Überquerung",
        "stage_count": 4,
        "date_from": "2025-09-12",
        "date_to": "2025-09-15",
        "accuracy_pct": 92,
        "headline": "Gewitter Tag 2 wie prognostiziert — Aufstieg vorgezogen",
    },
    {
        "id": "zillertal-2025",
        "name": "Zillertal mit Steffi",
        "stage_count": 1,
        "date_from": "2025-12-28",
        "date_to": "2025-12-30",
        "accuracy_pct": 88,
        "headline": "Sonnig wie vorhergesagt, leichter Föhn ab Mittag",
    },
    {
        "id": "rofan-2025",
        "name": "Rofan Tageswanderung",
        "stage_count": 1,
        "date_from": "2025-08-23",
        "date_to": "2025-08-23",
        "accuracy_pct": 76,
        "headline": "Niederschlag 4 h früher als prognostiziert eingetroffen",
    },
    {
        "id": "venediger-2024",
        "name": "Großvenediger Rundtour",
        "stage_count": 5,
        "date_from": "2024-07-18",
        "date_to": "2024-07-22",
        "accuracy_pct": 94,
        "headline": "Stabile Schönwetter-Phase, Briefings ohne Korrektur",
    },
    {
        "id": "stubai-2024",
        "name": "Stubaier Höhenweg",
        "stage_count": 8,
        "date_from": "2024-08-30",
        "date_to": "2024-09-06",
        "accuracy_pct": 81,
        "headline": "Kaltlufteinbruch Tag 5 erkannt, Etappe 6 umgeplant",
    },
    {
        "id": "khw-402",
        "name": "KHW 402",
        "stage_count": 13,
        "date_from": "2024-05-05",
        "date_to": "2024-05-18",
        "accuracy_pct": 86,
        "headline": "Drei Gewitter-Tage, davon zwei Tage vorher avisiert",
    },
    {
        "id": "gardasee-2024",
        "name": "Gardasee Klettersteige",
        "stage_count": 3,
        "date_from": "2024-04-19",
        "date_to": "2024-04-21",
        "accuracy_pct": 71,
        "headline": "Wind unterschätzt, Bocchette gesperrt — kurzfristig umgeplant",
    },
    {
        "id": "dachstein-2023",
        "name": "Dachstein Überschreitung",
        "stage_count": 2,
        "date_from": "2023-09-08",
        "date_to": "2023-09-09",
        "accuracy_pct": 95,
        "headline": "Bilderbuch-Bedingungen — präzise getroffen",
    },
]


def _build_stages(trip_id: str, date_from: str, date_to: str, count: int) -> list:
    """Build dummy stages evenly distributed between from and to."""
    d_from = date.fromisoformat(date_from)
    d_to = date.fromisoformat(date_to)
    total_days = (d_to - d_from).days
    stages = []
    for i in range(count):
        if count == 1:
            stage_date = d_from
        else:
            offset = round(i * total_days / (count - 1)) if count > 1 else 0
            stage_date = d_from + timedelta(days=min(offset, total_days))
        stages.append({
            "id": f"S{i + 1}",
            "name": f"Etappe {i + 1}",
            "date": stage_date.isoformat(),
            "waypoints": [],
        })
    return stages


def seed(data_dir: str, user: str) -> None:
    trips_dir = Path(data_dir) / "users" / user / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)

    for t in TRIPS:
        d_to = date.fromisoformat(t["date_to"])
        archived_at = (d_to + timedelta(days=1)).isoformat() + "T00:00:00Z"
        stages = _build_stages(t["id"], t["date_from"], t["date_to"], t["stage_count"])

        trip_json = {
            "id": t["id"],
            "name": t["name"],
            "stages": stages,
            "alert_rules": [],
            "accuracy_pct": t["accuracy_pct"],
            "headline": t["headline"],
            "archived_at": archived_at,
        }

        path = trips_dir / f"{t['id']}.json"
        path.write_text(json.dumps(trip_json, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  wrote {path.name}")

    print(f"Seeded {len(TRIPS)} archive trips → {trips_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo archive trips for validator account")
    parser.add_argument("--data-dir", required=True, help="Base data directory (e.g. 'data')")
    parser.add_argument("--user", required=True, help="Username (e.g. 'validator-issue110')")
    args = parser.parse_args()
    seed(args.data_dir, args.user)


if __name__ == "__main__":
    main()
