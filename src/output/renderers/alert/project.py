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


def to_multi_point_alert_message(groups, *, tz, stand_at) -> AlertMessage:
    """WeatherChange-Events MEHRERER gleichzeitig betroffener Vergleichs-Orte
    (Issue #1170, AC-7-Bündelung) → EINE kanonische AlertMessage.

    `groups`: `list[(location_name, changes, point)]` — `point` ist aktuell
    ungenutzt (Formangleichung an `to_point_alert_message`, Platz für
    künftige Positions-Anreicherung). Bei MEHR ALS EINER Gruppe trägt jedes
    `AlertEvent` das `location_label` SEINER Gruppe, damit der Renderer je
    Datenblock den richtigen Ort zeigt (statt nur den kollektiven
    `AlertMessage.location_label`).

    INVARIANTE: bei GENAU einer Gruppe ist das Ergebnis byte-identisch zu
    `to_point_alert_message()` — `to_point_alert_message()` delegiert
    deshalb direkt hierher (Einzel-Ort-Regressions-Invariante, #1169 AC-7).
    Dazu bleibt das per-Event `location_label` bei genau einer Gruppe None:
    nur das nachrichtenweite `AlertMessage.location_label` (Footer/Where)
    ist gesetzt — sonst zeigt der Mehr-Metrik-Zweig von `render_email` einen
    redundanten Orts-Präfix vor JEDER Metrik-Zeile (Issue #1170 Finding F007).
    """
    events: list[AlertEvent] = []
    multi = len(groups) > 1
    for location_name, changes, _point in groups:
        for ch in changes:
            metric_id = _resolve_metric_id(ch.metric, ch.direction)
            cmp = get_cmp(metric_id)
            if not cmp:
                raise ValueError(f"Leeres cmp für metric_id={metric_id!r}")
            events.append(AlertEvent(
                metric_id=metric_id, value_from=ch.old_value, value_to=ch.new_value,
                threshold=ch.threshold, cmp=cmp, occurred_at=ch.occurred_at,
                km_from=0.0, km_to=0.0,
                location_label=location_name if multi else None,
            ))
    collective_label = ", ".join(name for name, _changes, _point in groups)
    return AlertMessage(
        trip_short=collective_label, stand_at=stand_at, events=tuple(events), source=None,
        location_label=collective_label,
    )


def to_point_alert_message(changes, points, entity_name, *, tz, stand_at) -> AlertMessage:
    """WeatherChange-Events (Punkt-Kontext, Issue #1169) → kanonische
    AlertMessage — OHNE `_segment_km()`-Lookup (ein Vergleichs-Ort ist ein
    Punkt ohne km-Spanne, `km_from=km_to=0.0` als neutraler Platzhalter).
    Setzt zusätzlich `location_label`, damit der geteilte Renderer den
    Ortsnamen statt "km 0–0" zeigt (`render.py`).

    Issue #1170: EINE-Ort-Sonderfall von `to_multi_point_alert_message()` —
    Delegation statt Duplikation garantiert Byte-Identität (siehe dort).
    """
    point = points[0] if points else None
    return to_multi_point_alert_message(
        [(entity_name, changes, point)], tz=tz, stand_at=stand_at,
    )
