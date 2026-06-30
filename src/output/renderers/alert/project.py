"""Projektion WeatherChange → AlertMessage (Issue #917, AC-1).

field→metric_id via Reverse-Lookup über den Katalog `summary_fields`, mit
Disambiguierung mehrdeutiger Felder (`temp_min_c` → `temperature` *und*
`temperature_cold`) anhand der WeatherChange-`direction`. Kein stiller Fallback.
"""
from __future__ import annotations

from app.metric_catalog import _METRICS, get_cmp
from .model import AlertEvent, AlertMessage


def _resolve_metric_id(field: str, direction: str) -> str:
    """summary_field → catalog metric_id, disambiguiert per Richtung.

    `decrease` bevorzugt die cmp='unter'-Metrik (Kältealarm → temperature_cold),
    `increase` die cmp='über'-Metrik (Tageshoch → temperature). Unbekanntes Feld
    → KeyError (kein stiller Fallback).
    """
    candidates = [m for m in _METRICS if field in m.summary_fields.values()]
    if not candidates:
        raise KeyError(f"Unbekanntes summary_field für Alert-Projektion: {field!r}")
    if len(candidates) == 1:
        return candidates[0].id
    want = "unter" if direction == "decrease" else "über"
    for m in candidates:
        if m.cmp == want:
            return m.id
    # Mehrdeutig, aber keine cmp-Übereinstimmung → definierter Fehler.
    raise ValueError(
        f"Mehrdeutiges Feld {field!r} (direction={direction!r}) ohne passende cmp"
    )


def _segment_km(segments, segment_id: str) -> tuple[float, float]:
    """km-Spanne des referenzierten Segments. Bei nicht auflösbarer/leerer
    segment_id Fallback auf das erste Segment (kein Crash im Versandpfad —
    der Detector liefert nicht immer eine exakte segment_id)."""
    match = next(
        (s for s in segments if str(s.segment.segment_id) == str(segment_id)),
        segments[0] if segments else None,
    )
    if match is None:
        raise KeyError(f"Kein Segment für segment_id={segment_id!r}")
    return (match.segment.start_point.distance_from_start_km,
            match.segment.end_point.distance_from_start_km)


def to_alert_message(changes, segments, trip_name, *, tz, stand_at) -> AlertMessage:
    """WeatherChange-Events → kanonische AlertMessage. source bei Deviation = None."""
    events: list[AlertEvent] = []
    for ch in changes:
        metric_id = _resolve_metric_id(ch.metric, ch.direction)
        cmp = get_cmp(metric_id)
        if not cmp:
            raise ValueError(f"Leeres cmp für metric_id={metric_id!r}")
        km_from, km_to = _segment_km(segments, ch.segment_id)
        events.append(AlertEvent(
            metric_id=metric_id, value_from=ch.old_value, value_to=ch.new_value,
            threshold=ch.threshold, cmp=cmp, occurred_at=ch.occurred_at,
            km_from=km_from, km_to=km_to,
        ))
    return AlertMessage(
        trip_short=trip_name, stand_at=stand_at, events=tuple(events), source=None,
    )
