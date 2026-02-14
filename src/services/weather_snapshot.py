"""
Weather Snapshot Service — persists aggregated weather data for alert comparison.

ALERT-01: Saves SegmentWeatherSummary to JSON after report send,
loads during alert checks so change detection compares real deltas.

SPEC: docs/specs/modules/weather_snapshot.md v1.0
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from app.loader import get_snapshots_dir
from app.models import (
    GPXPoint,
    PrecipType,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Fields that hold Enum values and their types
_ENUM_FIELDS: dict[str, type] = {
    "thunder_level_max": ThunderLevel,
    "precip_type_dominant": PrecipType,
}


class WeatherSnapshotService:
    """Persist and load aggregated weather snapshots as JSON files."""

    def __init__(self, user_id: str = "default") -> None:
        self._user_id = user_id
        self._snapshots_dir = get_snapshots_dir(user_id)

    def save(
        self,
        trip_id: str,
        segments: List[SegmentWeatherData],
        target_date: date,
    ) -> None:
        """Save aggregated weather snapshot to JSON file."""
        try:
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)

            snapshot = {
                "trip_id": trip_id,
                "target_date": target_date.isoformat(),
                "snapshot_at": datetime.now(timezone.utc).isoformat(),
                "provider": segments[0].provider if segments else "unknown",
                "segments": [
                    {
                        "segment_id": seg.segment.segment_id,
                        "start_time": seg.segment.start_time.isoformat(),
                        "end_time": seg.segment.end_time.isoformat(),
                        "aggregated": _serialize_summary(seg.aggregated),
                    }
                    for seg in segments
                ],
            }

            filepath = self._snapshots_dir / f"{trip_id}.json"
            filepath.write_text(json.dumps(snapshot, indent=2))
            logger.info(f"Snapshot saved: {trip_id}")
        except Exception as e:
            logger.warning(f"Failed to save snapshot {trip_id}: {e}")

    def load(self, trip_id: str) -> Optional[List[SegmentWeatherData]]:
        """Load aggregated weather snapshot from JSON file."""
        filepath = self._snapshots_dir / f"{trip_id}.json"

        if not filepath.exists():
            logger.debug(f"No snapshot for {trip_id}")
            return None

        try:
            data = json.loads(filepath.read_text())
            snapshot_at = datetime.fromisoformat(data["snapshot_at"])
            provider = data.get("provider", "unknown")

            result: List[SegmentWeatherData] = []
            for seg_data in data["segments"]:
                segment = _reconstruct_segment(seg_data)
                aggregated = _deserialize_summary(seg_data["aggregated"])
                result.append(
                    SegmentWeatherData(
                        segment=segment,
                        timeseries=None,
                        aggregated=aggregated,
                        fetched_at=snapshot_at,
                        provider=provider,
                    )
                )
            return result
        except (json.JSONDecodeError, ValueError, KeyError, OSError) as e:
            logger.warning(f"Corrupt snapshot {trip_id}: {e}")
            return None


def _serialize_summary(summary: SegmentWeatherSummary) -> dict:
    """Serialize SegmentWeatherSummary to dict, omitting None values."""
    result = {}
    for field_name, value in vars(summary).items():
        if value is None:
            continue
        if field_name == "aggregation_config":
            if value:
                result[field_name] = value
            continue
        if isinstance(value, Enum):
            result[field_name] = value.name
        else:
            result[field_name] = value
    return result


def _deserialize_summary(data: dict) -> SegmentWeatherSummary:
    """Deserialize dict to SegmentWeatherSummary, reconstructing Enums."""
    kwargs = {}
    for key, value in data.items():
        if key in _ENUM_FIELDS and isinstance(value, str):
            kwargs[key] = _ENUM_FIELDS[key](value)
        else:
            kwargs[key] = value
    return SegmentWeatherSummary(**kwargs)


def _reconstruct_segment(seg_data: dict) -> TripSegment:
    """Reconstruct minimal TripSegment from snapshot data."""
    dummy_point = GPXPoint(lat=0.0, lon=0.0)
    return TripSegment(
        segment_id=seg_data["segment_id"],
        start_point=dummy_point,
        end_point=dummy_point,
        start_time=datetime.fromisoformat(seg_data["start_time"]),
        end_time=datetime.fromisoformat(seg_data["end_time"]),
        duration_hours=0.0,
        distance_km=0.0,
        ascent_m=0.0,
        descent_m=0.0,
    )
