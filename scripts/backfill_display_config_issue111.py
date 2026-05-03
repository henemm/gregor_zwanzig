"""Issue #111: Backfill display_config-Block in bestehenden Trip-JSONs.

Ergaenzt minimal-invasiv ein default display_config in jedes Trip-JSON unter
data/users/*/trips/, das weder display_config noch weather_config hat.
Alle anderen Felder bleiben unangetastet (kein Read-Modify-Write durch Loader,
sondern direkt JSON-Merge).

Profile aus aggregation.profile, Fallback ALLGEMEIN.

Usage:
    uv run python scripts/backfill_display_config_issue111.py [--dry-run]
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from app.metric_catalog import build_default_display_config_for_profile
from app.profile import ActivityProfile

DATA_DIR = PROJECT_ROOT / "data" / "users"


def display_config_to_json(dc) -> dict:
    """Serialize UnifiedWeatherDisplayConfig to JSON dict (matches loader._trip_to_dict)."""
    return {
        "trip_id": dc.trip_id,
        "metrics": [
            {
                "metric_id": mc.metric_id,
                "enabled": mc.enabled,
                "aggregations": mc.aggregations,
                "morning_enabled": mc.morning_enabled,
                "evening_enabled": mc.evening_enabled,
                "use_friendly_format": mc.use_friendly_format,
                "alert_enabled": mc.alert_enabled,
                "alert_threshold": mc.alert_threshold,
            }
            for mc in dc.metrics
        ],
        "show_night_block": dc.show_night_block,
        "night_interval_hours": dc.night_interval_hours,
        "thunder_forecast_days": dc.thunder_forecast_days,
        "multi_day_trend_reports": dc.multi_day_trend_reports,
        "sms_metrics": dc.sms_metrics,
        "updated_at": dc.updated_at.isoformat(),
    }


def resolve_profile(data: dict) -> ActivityProfile:
    """Lookup ActivityProfile from trip JSON aggregation block; fallback ALLGEMEIN."""
    aggregation = data.get("aggregation") or {}
    profile_str = aggregation.get("profile")
    if not profile_str:
        return ActivityProfile.ALLGEMEIN
    try:
        return ActivityProfile(profile_str)
    except ValueError:
        return ActivityProfile.ALLGEMEIN


def backfill_trip(path: Path, dry_run: bool = False) -> str:
    """Returns: status string (skipped/added/dry-run)."""
    with open(path) as f:
        data = json.load(f)

    if "display_config" in data:
        return "skip:already-has-display_config"
    if "weather_config" in data:
        return "skip:has-legacy-weather_config"

    profile = resolve_profile(data)
    trip_id = data.get("id", path.stem)
    dc = build_default_display_config_for_profile(trip_id, profile)
    dc_json = display_config_to_json(dc)

    data["display_config"] = dc_json

    if dry_run:
        return f"would-add (profile={profile.value}, metrics={len(dc.metrics)})"

    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return f"added (profile={profile.value}, metrics={len(dc.metrics)})"


def main(dry_run: bool = False) -> int:
    if not DATA_DIR.exists():
        print(f"FAIL: {DATA_DIR} fehlt")
        return 1

    trip_files = sorted(DATA_DIR.glob("*/trips/*.json"))
    if not trip_files:
        print(f"Keine Trip-JSONs unter {DATA_DIR} gefunden.")
        return 0

    print(f"Backfill-Lauf{' (DRY-RUN)' if dry_run else ''} ueber {len(trip_files)} Trip-File(s):")
    for p in trip_files:
        rel = p.relative_to(PROJECT_ROOT)
        status = backfill_trip(p, dry_run=dry_run)
        print(f"  {rel}: {status}")

    print("Fertig.")
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
