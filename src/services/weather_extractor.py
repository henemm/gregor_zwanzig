"""
WeatherExtractor — schlanke Ad-Hoc-Datenschicht über Snapshots.

SPEC: docs/specs/modules/weather_extractor.md v1.0
Issue #652, Epic #639 Teil 3/6
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

from app.models import SegmentWeatherSummary
from services.weather_snapshot import WeatherSnapshotService


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class TimelinePoint:
    arrival_time: datetime
    elevation_m: Optional[float]
    label: str
    metrics: SegmentWeatherSummary


@dataclass
class TimelineResult:
    trip_id: str
    target_date: Optional[date]
    points: List[TimelinePoint]
    available: bool
    message: Optional[str] = None


@dataclass
class DrilldownPoint:
    ts: datetime
    value: Optional[object]


@dataclass
class DrilldownResult:
    trip_id: str
    metric: str
    points: List[DrilldownPoint]
    available: bool
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class WeatherExtractor:
    def __init__(self, user_id: str = "default") -> None:
        self._snapshots = WeatherSnapshotService(user_id)

    def timeline(
        self,
        trip_id: str,
        target_date: Optional[date] = None,
    ) -> TimelineResult:
        segments = self._snapshots.load(trip_id)
        if not segments:
            return TimelineResult(
                trip_id=trip_id,
                target_date=target_date,
                points=[],
                available=False,
                message=f"Kein Snapshot für Trip '{trip_id}' gefunden.",
            )
        points = [
            TimelinePoint(
                arrival_time=seg.segment.end_time,
                elevation_m=seg.segment.end_point.elevation_m,
                label=str(seg.segment.segment_id),
                metrics=seg.aggregated,
            )
            for seg in segments
        ]
        return TimelineResult(
            trip_id=trip_id,
            target_date=target_date,
            points=points,
            available=True,
        )

    def drilldown(
        self,
        trip_id: str,
        metric: str,
        from_time: Optional[datetime] = None,
        hours: int = 12,
    ) -> DrilldownResult:
        segments = self._snapshots.load(trip_id)

        # Alle Stundenpunkte aus allen Segmenten sammeln
        all_points: list[tuple[datetime, object]] = []
        if segments:
            for seg in segments:
                if seg.timeseries is None:
                    continue
                for p in seg.timeseries.data:
                    all_points.append((p.ts, getattr(p, metric, None)))

        if not all_points:
            return DrilldownResult(
                trip_id=trip_id,
                metric=metric,
                points=[],
                available=False,
                message=f"Keine stündlichen Daten für Trip '{trip_id}' / Metrik '{metric}'.",
            )

        # Sortieren und deduplizieren nach ts
        all_points.sort(key=lambda x: x[0])
        seen: set[datetime] = set()
        deduped: list[tuple[datetime, object]] = []
        for ts, val in all_points:
            if ts not in seen:
                seen.add(ts)
                deduped.append((ts, val))

        # Zeitfenster anwenden
        start = from_time if from_time is not None else deduped[0][0]
        end = start + timedelta(hours=hours)
        windowed = [
            DrilldownPoint(ts=ts, value=val)
            for ts, val in deduped
            if start <= ts < end
        ]

        if not windowed:
            return DrilldownResult(
                trip_id=trip_id,
                metric=metric,
                points=[],
                available=False,
                message=f"Keine Daten im angefragten Zeitfenster für '{metric}'.",
            )

        return DrilldownResult(
            trip_id=trip_id,
            metric=metric,
            points=windowed,
            available=True,
        )
