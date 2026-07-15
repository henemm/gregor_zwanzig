#!/usr/bin/env python3
"""Seed demo archive entries (Trips + Orts-Vergleiche) for the validator account.

Issue #611 — reines Archiv für Trips UND Vergleiche (screen-archive.jsx).
Die #583-Forecast-Analytik-Felder (accuracy_pct/headline/briefings_count/
alerts_count) wurden entfernt; das Archiv zeigt nur noch Name/Umfang/Datum.

CLI: python3 scripts/seed_validator_archive.py --data-dir <DIR> --user <USERNAME>

Writes archived Trip JSONs + archived ComparePreset JSONs so the staging
archive lists both types. Idempotent: existing entries are overwritten.
"""
import argparse
import json
from datetime import date, timedelta
from pathlib import Path


TRIPS = [
    {"id": "ortler-2025", "name": "Ortler-Überquerung", "stage_count": 4,
     "date_from": "2025-09-12", "date_to": "2025-09-15"},
    {"id": "zillertal-2025", "name": "Zillertal mit Steffi", "stage_count": 1,
     "date_from": "2025-12-28", "date_to": "2025-12-30"},
    {"id": "rofan-2025", "name": "Rofan Tageswanderung", "stage_count": 1,
     "date_from": "2025-08-23", "date_to": "2025-08-23"},
    {"id": "venediger-2024", "name": "Großvenediger Rundtour", "stage_count": 5,
     "date_from": "2024-07-18", "date_to": "2024-07-22"},
    {"id": "stubai-2024", "name": "Stubaier Höhenweg", "stage_count": 8,
     "date_from": "2024-08-30", "date_to": "2024-09-06"},
    {"id": "khw-402", "name": "KHW 402", "stage_count": 13,
     "date_from": "2024-05-05", "date_to": "2024-05-18"},
    {"id": "gardasee-2024", "name": "Gardasee Klettersteige", "stage_count": 3,
     "date_from": "2024-04-19", "date_to": "2024-04-21"},
    {"id": "dachstein-2023", "name": "Dachstein Überschreitung", "stage_count": 2,
     "date_from": "2023-09-08", "date_to": "2023-09-09"},
]

# Issue #611 — archivierte Orts-Vergleiche, damit das Archiv beide Typen zeigt.
COMPARE_PRESETS = [
    {"id": "cmp-skitirol", "name": "Skigebiete Tirol",
     "location_ids": ["loc-stubai", "loc-soelden", "loc-ischgl", "loc-kitzbuehel",
                      "loc-axamer", "loc-obergurgl"],
     "archived_at": "2025-11-04T00:00:00Z"},
    {"id": "cmp-wochenende", "name": "Wochenend-Touren Süd",
     "location_ids": ["loc-gardasee", "loc-dolomiten", "loc-comer", "loc-tessin"],
     "archived_at": "2024-10-12T00:00:00Z"},
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
    user_dir = Path(data_dir) / "users" / user
    # Issue #1250 Scheibe 7a (Adversary F005): briefings/ ist seit dem
    # Cutover der Lesepfad von load_all_trips -- ohne kind="route" waere ein
    # frisch geseedeter Trip fuer die App unsichtbar.
    trips_dir = user_dir / "briefings"
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
            "archived_at": archived_at,
            "kind": "route",
        }

        path = trips_dir / f"{t['id']}.json"
        path.write_text(json.dumps(trip_json, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  wrote {path.name}")

    # Issue #611 — archivierte Vergleiche (merge in bestehende compare_presets.json).
    presets_path = user_dir / "compare_presets.json"
    existing = []
    if presets_path.exists():
        try:
            existing = json.loads(presets_path.read_text(encoding="utf-8")) or []
        except (json.JSONDecodeError, OSError):
            existing = []
    by_id = {p.get("id"): p for p in existing if isinstance(p, dict)}
    for c in COMPARE_PRESETS:
        by_id[c["id"]] = {
            "id": c["id"],
            "name": c["name"],
            "user_id": user,
            "location_ids": c["location_ids"],
            "schedule": "manual",
            "profil": "SUMMER_TREKKING",
            "hour_from": 6,
            "hour_to": 18,
            "empfaenger": [],
            "created_at": c["archived_at"],
            "archived_at": c["archived_at"],
        }
    presets_path.write_text(
        json.dumps(list(by_id.values()), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for c in COMPARE_PRESETS:
        print(f"  wrote compare preset {c['id']}")

    print(
        f"Seeded {len(TRIPS)} archive trips + {len(COMPARE_PRESETS)} compare presets → {user_dir}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo archive trips for validator account")
    parser.add_argument("--data-dir", required=True, help="Base data directory (e.g. 'data')")
    parser.add_argument("--user", required=True, help="Username (e.g. 'validator-issue110')")
    args = parser.parse_args()
    seed(args.data_dir, args.user)


if __name__ == "__main__":
    main()
