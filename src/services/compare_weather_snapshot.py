"""Δ-Anker-Store für Compare-Orte (Issue #1169, Scheibe 2/3, Epic #1095).

Persistiert `PointWeatherData` je Preset/Ort unter
`data/users/<user_id>/compare_weather_snapshots/`, keyed
`"{preset_id}__{location_id}"`. Analog zu `WeatherSnapshotService`, aber
location-generisch (kein `TripSegment`-Bezug). Wird von
`send_one_compare_preset()` nach erfolgreichem Report-Versand geschrieben; der
Alert-Check liest nur (ADR-0009). Serialisierung teilt die Summary-/
Timeseries-(De)serialisierungs-Helfer aus `weather_snapshot.py` (ADR-0021:
kein Duplikat der Enum-/Hourly-Logik).

SPEC: docs/specs/modules/issue_1169_compare_alert_consumer.md
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List

from app.loader import get_data_dir
from services.point_weather import PointWeatherData
from services.weather_snapshot import (
    _deserialize_summary,
    _deserialize_timeseries,
    _serialize_summary,
)

logger = logging.getLogger("compare_weather_snapshot")


class CompareWeatherSnapshotService:
    """Lädt/speichert den Δ-Anker-Snapshot je Compare-Preset/Ort (mandantengetrennt).

    Jeder Key (`preset_id__location_id`) besitzt eine exklusive Datei — ein
    Read-Modify-Write anderer Felder ist hier nicht nötig, da `save()` die
    einzige Quelle dieser Datei ist (kein Client-editierbares Schema).
    """

    def __init__(self, user_id: str = "default") -> None:
        self._user_id = user_id
        self._dir = get_data_dir(user_id) / "compare_weather_snapshots"

    def _key(self, preset_id: str, location_id: str) -> str:
        return f"{preset_id}__{location_id}"

    def _path(self, preset_id: str, location_id: str) -> Path:
        return self._dir / f"{self._key(preset_id, location_id)}.json"

    def save(self, preset_id: str, location_id: str, point: PointWeatherData) -> None:
        """Persist a single `PointWeatherData` as the Δ-anchor for this key."""
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            entry: dict = {
                "id": point.id,
                "name": point.name,
                "lat": point.lat,
                "lon": point.lon,
                "fetched_at": point.fetched_at.isoformat(),
                "provider": point.provider,
                "aggregated": _serialize_summary(point.aggregated),
            }
            if point.timeseries is not None:
                hourly = []
                for dp in point.timeseries.data:
                    row: dict = {"ts": dp.ts.isoformat()}
                    for fname, fval in vars(dp).items():
                        if fname == "ts" or fval is None:
                            continue
                        row[fname] = fval.name if isinstance(fval, Enum) else fval
                    hourly.append(row)
                entry["hourly"] = hourly
            self._path(preset_id, location_id).write_text(json.dumps(entry, indent=2))
        except OSError as e:
            logger.error(f"Failed to save compare snapshot {preset_id}/{location_id}: {e}")

    def load(self, preset_id: str, location_id: str) -> List[PointWeatherData]:
        """Return `[PointWeatherData]` (0 or 1 entries — list-Form, damit
        `DeviationAlertEngine.evaluate()` mit leerem `cached=[]` im
        Bootstrap-Fall (kein Snapshot) ohne Sonderfall auskommt)."""
        path = self._path(preset_id, location_id)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text())
            provider = data.get("provider", "unknown")
            timeseries = _deserialize_timeseries(data, provider)
            point = PointWeatherData(
                id=data["id"], name=data["name"], lat=data["lat"], lon=data["lon"],
                timeseries=timeseries,
                aggregated=_deserialize_summary(data["aggregated"]),
                fetched_at=datetime.fromisoformat(data["fetched_at"]),
                provider=provider,
            )
            return [point]
        except (json.JSONDecodeError, ValueError, KeyError, OSError) as e:
            logger.warning(f"Corrupt compare snapshot {preset_id}/{location_id}: {e}")
            return []
