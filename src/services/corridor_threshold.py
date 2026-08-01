"""Reine Schwellen-Auswertung: Korridore + Wetterpunkte -> gerissene Grenzen.

Issue #1444 Scheibe 1. Kein Trip-Wissen, kein Versand -- nimmt eine Liste
`SegmentWeatherData` + eine Liste `Corridor` (nur `notify=True` zaehlt)
entgegen und liefert `CorridorHit` je gerissener Grenze im aktiven
Etappenfenster (dieselbe Regel wie `TripAlertService._fetch_fresh_weather()`:
`end_time >= jetzt` und `start_time.date() <= heute` -- keine neue Definition).

SPEC: docs/specs/modules/feat_1444_s1_schwellen_alarm.md AC-1/AC-2/AC-5.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.models import Corridor, SegmentWeatherData
from services.corridor_match import corridor_inside
from services.weather_change_detection import (
    _ALERT_METRIC_TO_SUMMARY_FIELD,
    _peak_occurred_at,
)


@dataclass(frozen=True)
class CorridorHit:
    """Eine im aktiven Etappenfenster gerissene Nutzer-Grenze (Issue #1444 S1)."""

    metric: str
    value: float
    bound: float  # die TATSAECHLICH gerissene Grenze (min ODER max)
    direction: str  # "above" | "below"
    segment_id: str
    occurred_at: Optional[datetime]


def evaluate_corridor_thresholds(
    points: list[SegmentWeatherData],
    corridors: list[Corridor],
) -> list[CorridorHit]:
    """Wertet je Wetterpunkt im aktiven Fenster und je Korridor mit
    `notify=True` die eingestellte Grenze aus.

    Unbekannte Metriken (kein Eintrag in `_ALERT_METRIC_TO_SUMMARY_FIELD`)
    und fehlende Aggregatwerte werden uebersprungen (kein Crash im
    Alarm-Lauf -- R6: nicht jede Groesse ist vergleichbar). Enum-Werte
    (Gewitter) werden ueber `thunder_ordinal()` normalisiert. Der Grenzwert
    selbst zaehlt als eingehalten (`corridor_inside`-Semantik, C5).
    """
    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()
    hits: list[CorridorHit] = []
    for point in points:
        seg = point.segment
        if seg.end_time < now_utc or seg.start_time.date() > today:
            continue  # ausserhalb des aktiven Etappenfensters
        for corridor in corridors:
            if not corridor.notify:
                continue
            field = _ALERT_METRIC_TO_SUMMARY_FIELD.get(corridor.metric)
            if not field:
                continue
            value = getattr(point.aggregated, field, None)
            if value is None:
                continue
            if isinstance(value, Enum):
                from output.metric_format import thunder_ordinal
                value = thunder_ordinal(value)
            value = float(value)
            min_bound, max_bound = corridor.range[0], corridor.range[1]
            if corridor_inside(value, min_bound, max_bound) is not False:
                continue
            if min_bound is not None and value < min_bound:
                direction, bound = "below", float(min_bound)
            else:
                direction, bound = "above", float(max_bound)
            hits.append(CorridorHit(
                metric=corridor.metric,
                value=value,
                bound=bound,
                direction=direction,
                segment_id=str(seg.segment_id),
                occurred_at=_peak_occurred_at(field, point),
            ))
    return hits
