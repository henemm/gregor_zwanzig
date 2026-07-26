"""Projektion WeatherChange → AlertMessage (Issue #917, AC-1).

field→metric_id via Reverse-Lookup über den Katalog `summary_fields`, mit
Disambiguierung mehrdeutiger Felder (`temp_min_c` → `temperature` *und*
`temperature_cold`) anhand der WeatherChange-`direction`. Kein stiller Fallback.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.metric_catalog import _METRICS, get_cmp
from utils.timezone import local_fmt, tz_for_coords
from .model import AlertEvent, AlertMessage, OnsetEvent


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


def _find_segment(segments, segment_id: str):
    """Referenziertes Segment. Bei nicht auflösbarer/leerer segment_id Fallback
    auf das erste Segment (kein Crash im Versandpfad — der Detector liefert
    nicht immer eine exakte segment_id)."""
    match = next(
        (s for s in segments if str(s.segment.segment_id) == str(segment_id)),
        segments[0] if segments else None,
    )
    if match is None:
        raise KeyError(f"Kein Segment für segment_id={segment_id!r}")
    return match


def _fmt_occurred_at(value, tz) -> str | None:
    """Peak-Zeitpunkt (UTC-`datetime`, s. `WeatherChange.occurred_at`) → "HH:MM"
    in ORTSZEIT (Issue #1386). Guard: naiv hereingereichte Zeitstempel gelten
    als UTC — sonst deutet `astimezone()` sie als System-Lokalzeit."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return local_fmt(value, tz)


def to_alert_message(changes, segments, trip_name, *, tz, stand_at) -> AlertMessage:
    """WeatherChange-Events → kanonische AlertMessage. source bei Deviation = None.

    Issue #1386: die Ereigniszeit („Wo & wann … · HH:MM", SMS `@HH`) wird HIER
    in ORTSZEIT formatiert — je Event aus den Koordinaten SEINER Etappe
    (`TripSegment.start_point`), `tz` ist Fallback ohne Koordinaten.
    """
    events: list[AlertEvent] = []
    for ch in changes:
        metric_id = _resolve_metric_id(ch.metric, ch.direction)
        cmp = get_cmp(metric_id)
        if not cmp:
            raise ValueError(f"Leeres cmp für metric_id={metric_id!r}")
        match = _find_segment(segments, ch.segment_id)
        km_from = match.segment.start_point.distance_from_start_km
        km_to = match.segment.end_point.distance_from_start_km
        events.append(AlertEvent(
            metric_id=metric_id, value_from=ch.old_value, value_to=ch.new_value,
            threshold=ch.threshold, cmp=cmp,
            occurred_at=_fmt_occurred_at(
                ch.occurred_at, _tz_for_location(match.segment.start_point, tz)
            ),
            km_from=km_from, km_to=km_to,
        ))
    return AlertMessage(
        trip_short=trip_name, stand_at=stand_at, events=tuple(events), source=None,
    )


def to_multi_point_alert_message(groups, *, tz, stand_at) -> AlertMessage:
    """WeatherChange-Events MEHRERER gleichzeitig betroffener Vergleichs-Orte
    (Issue #1170, AC-7-Bündelung) → EINE kanonische AlertMessage.

    `groups`: `list[(location_name, changes, point)]` — `point` trägt
    `.lat`/`.lon` und liefert damit die ZEITZONE DIESES Ortes für die
    Ereigniszeit („Wo & wann … · HH:MM", SMS `@HH`; Issue #1386, vorher
    ungenutzt und die Zeit stand in Weltzeit). Ohne Koordinaten gilt für
    diesen Ort das Bündel-`tz` (Fallback, `_tz_for_location`) — das ist
    zugleich die einzige Rolle des `tz`-Parameters hier. Bei MEHR ALS EINER
    Gruppe trägt jedes `AlertEvent` das `location_label` SEINER Gruppe, damit
    der Renderer je Datenblock den richtigen Ort zeigt (statt nur den
    kollektiven `AlertMessage.location_label`).

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
    for location_name, changes, point in groups:
        point_tz = _tz_for_location(point, tz)
        for ch in changes:
            metric_id = _resolve_metric_id(ch.metric, ch.direction)
            cmp = get_cmp(metric_id)
            if not cmp:
                raise ValueError(f"Leeres cmp für metric_id={metric_id!r}")
            events.append(AlertEvent(
                metric_id=metric_id, value_from=ch.old_value, value_to=ch.new_value,
                threshold=ch.threshold, cmp=cmp,
                occurred_at=_fmt_occurred_at(ch.occurred_at, point_tz),
                km_from=0.0, km_to=0.0,
                location_label=location_name if multi else None,
            ))
    collective_label = ", ".join(name for name, _changes, _point in groups)
    return AlertMessage(
        trip_short=collective_label, stand_at=stand_at, events=tuple(events), source=None,
        location_label=collective_label,
    )


def _tz_for_location(loc, fallback_tz):
    """Zeitzone DIESES Ortes aus seinen Koordinaten (Issue #1385).

    Guard: kein Ortsobjekt oder fehlende/`None`-Koordinaten → `fallback_tz`
    (das Bündel-`tz`), niemals ein Absturz im Versandpfad.
    """
    lat = getattr(loc, "lat", None)
    lon = getattr(loc, "lon", None)
    if lat is None or lon is None:
        return fallback_tz
    try:
        return tz_for_coords(lat, lon)
    except Exception:
        return fallback_tz


def to_multi_location_onset_alert_message(
    groups, *, tz, stand_at, cooldown_display: str | None = None
) -> AlertMessage:
    """Radar-Onset-Ergebnisse MEHRERER gleichzeitig auslösender Vergleichs-Orte
    (Issue #1041 Slice 1a) → EINE kanonische AlertMessage.

    `groups`: `list[(location_name: str, location, NowcastResult)]` — `location`
    trägt `.lat`/`.lon` und damit die ZEITZONE DIESES Ortes. Die kurze Form
    `(location_name, NowcastResult)` bleibt zulässig (Aufrufer ohne Ortsobjekt);
    dann gilt für diesen Ort das übergebene Bündel-`tz`. Je Gruppe ein
    `OnsetEvent` (`km_from=km_to=0.0`, kein Etappen-km, Muster
    `to_multi_point_alert_message:98`). Bei MEHR ALS EINER Gruppe trägt jedes
    Event das `location_label` SEINER Gruppe (Renderer-Multi-Zweig).

    Issue #1385: `onset_time` („ab HH:MM") wird JE ORT in dessen eigener
    Ortszeit formatiert (`tz_for_coords(loc.lat, loc.lon)`). Vorher galt das
    eine Bündel-`tz` (= Zeitzone des ERSTEN Ortes) für alle Orte — bei Orten in
    verschiedenen Zeitzonen war die Angabe für jeden weiteren Ort schlicht
    falsch. Fehlen Koordinaten (kein Ortsobjekt, `lat`/`lon` `None`), gilt für
    diesen Ort weiterhin das Bündel-`tz` (Guard statt Absturz).

    `tz` bleibt: (a) Zeitzone für `stand_at`, (b) Fallback ohne Koordinaten.
    ABSICHTLICH NICHT je Ort aufgelöst wird `stand_at` — es ist eine Aussage
    über die NACHRICHT („Stand: heute HH:MM", Fußzeile, genau EINMAL pro Mail),
    nicht über einen Ort; es bleibt in der Zeitzone des ersten Ortes. Das ist
    kein Bug (Issue #1385, bewusste Entscheidung).

    INVARIANTE: bei GENAU einer Gruppe bleibt `location_label=None` — fällt
    damit auf den unveränderten Single-Onset-Renderpfad zurück (AC-5).
    `source` trägt den festen Marker "compare-radar", damit die Renderer
    weiterhin über den Onset-Zweig (`msg.source is not None`) routen.

    `cooldown_display`: optionaler, bereits formatierter Cooldown-Hinweis-Text
    (Issue Pflicht-Fix, analog `send_radar_alert()`s `cooldown_display`) —
    wird unverändert auf die gebaute `AlertMessage` durchgereicht.

    Härtung (#1041 Fix-Loop, Findings F001/F002): eine leere `groups`-Liste
    ist ein Aufrufer-Fehler → definierter `ValueError` statt `IndexError`.
    Orte ohne Onset (`NowcastResult.onset_minutes is None`) gehören nicht in
    einen Radar-Alarm-Bündel und werden VOR dem `OnsetEvent`/`timedelta`-Bau
    defensiv herausgefiltert; bleibt danach kein Ort übrig, ebenfalls
    `ValueError` (verhindert einen Absturz in Slice 1b).
    """
    if not groups:
        raise ValueError(
            "to_multi_location_onset_alert_message benötigt mindestens einen Ort"
        )
    normalized = [
        (g[0], g[1], g[2]) if len(g) == 3 else (g[0], None, g[1]) for g in groups
    ]
    valid_groups = [
        (name, loc, nc) for name, loc, nc in normalized if nc.onset_minutes is not None
    ]
    if not valid_groups:
        raise ValueError(
            "to_multi_location_onset_alert_message benötigt mindestens einen Ort "
            "mit gesetztem onset_minutes"
        )
    multi = len(valid_groups) > 1
    now = datetime.now(timezone.utc)
    events: list[OnsetEvent] = []
    for location_name, loc, nc in valid_groups:
        onset_time = local_fmt(
            now + timedelta(minutes=nc.onset_minutes), _tz_for_location(loc, tz),
        )
        events.append(OnsetEvent(
            onset_minutes=nc.onset_minutes, onset_time=onset_time,
            km_from=0.0, km_to=0.0, is_convective=nc.is_convective,
            intensity_label=nc.intensity_label, source_label=nc.source,
            location_label=location_name if multi else None,
        ))
    trip_short = (
        ", ".join(name for name, _loc, _nc in valid_groups)
        if multi else valid_groups[0][0]
    )
    return AlertMessage(
        trip_short=trip_short, stand_at=stand_at, events=tuple(events),
        source="compare-radar", cooldown_display=cooldown_display,
    )


def to_point_alert_message(changes, points, entity_name, *, tz, stand_at) -> AlertMessage:
    """WeatherChange-Events (Punkt-Kontext, Issue #1169) → kanonische
    AlertMessage — OHNE `_find_segment()`-Lookup (ein Vergleichs-Ort ist ein
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
