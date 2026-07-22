"""Geteiltes Tagesfenster 04:00-19:00 fuer die vier Kurzform-Kanaele.

SPEC: docs/specs/modules/sms_daywindow_aggregation.md (Epic #1319, Scheibe A)
Bug:  #1317 - Gewitter nach Ankunft fehlte in SMS/Kurzzusammenfassung/
      Kopf-Pille/Telegram-Fusszeile, obwohl die Detailtabelle "Nacht am Ziel"
      es zeigt.

Eine einzige Implementierung, von allen vier Kanaelen konsumiert (ADR-0025-
Konsistenz, Anti-Pattern #874/#1275: nie viermal unabhaengig nachbauen).
DAY_WINDOW_START_HOUR/DAY_WINDOW_END_HOUR sind benannte Konstanten, die
Scheibe B durch einen konfigurierbaren Wert ersetzt.
"""
from __future__ import annotations

import dataclasses
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

from app.models import ForecastDataPoint, NormalizedTimeseries, SegmentWeatherData
from output.metric_format import max_thunder, thunder_ordinal
from utils.timezone import local_hour

DAY_WINDOW_START_HOUR = 4
DAY_WINDOW_END_HOUR = 19


def _max_optional(values: Sequence[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return max(present) if present else None


def _merge_hour(dps: list[ForecastDataPoint]) -> ForecastDataPoint:
    """Merge alle Datenpunkte derselben Ortszeit-Stunde zu EINEM Punkt.

    Höchstwert je Metrik (analog ``sms_trip._dedup_by_hour``), damit eine
    Ueberschneidung an der Ankunftsstunde (Segment inklusive, Nacht-Fenster
    beginnt bei ihr) das staerkere Signal behaelt statt es zu verlieren.
    """
    if len(dps) == 1:
        return dps[0]
    base = max(
        dps,
        key=lambda dp: (
            thunder_ordinal(dp.thunder_level),
            dp.precip_1h_mm or 0.0,
            dp.gust_kmh or 0.0,
        ),
    )
    return dataclasses.replace(
        base,
        thunder_level=max_thunder(dp.thunder_level for dp in dps),
        precip_1h_mm=_max_optional([dp.precip_1h_mm for dp in dps]),
        pop_pct=_max_optional([dp.pop_pct for dp in dps]),
        wind10m_kmh=_max_optional([dp.wind10m_kmh for dp in dps]),
        gust_kmh=_max_optional([dp.gust_kmh for dp in dps]),
    )


def build_day_window_points(
    segments: Sequence[SegmentWeatherData],
    night_weather: Optional[NormalizedTimeseries],
    tz: ZoneInfo,
) -> list[ForecastDataPoint]:
    """``(segments, night_weather, tz)`` -> deduplizierte Punktliste 04-19 Uhr.

    Ortsgenau: bis zur Ankunft aus der jeweils zustaendigen Segment-Zeitreihe
    (unveraendertes Wanderzeit-Fenster pro Segment, nur beim ERSTEN Segment
    die untere Grenze auf ``DAY_WINDOW_START_HOUR`` abgesenkt statt
    ``start_h`` — die volle Tages-Zeitreihe liegt dort bereits vor,
    segment_weather.py:164-166). Ab der Ankunftsstunde bis
    ``DAY_WINDOW_END_HOUR`` ausschliesslich aus ``night_weather`` (nicht aus
    der Zeitreihe des letzten Segments — die haengt geografisch am
    Segment-Start, nicht am Zielort). ``night_weather=None`` -> fail-soft,
    reine Segment-Fensterung (AC-9).

    Workflow fix-briefing-grid-and-summary (Kurzform-Tabelle-Datumsfilter):
    der Nacht-Anteil filtert zusaetzlich zur Uhrzeit auch
    nach dem Ankunfts-Kalendertag (Ortszeit) -- analog dem Datumsfilter in
    trip_report.py::_extract_night_rows (Issue #956). Ohne diesen Filter
    kontaminiert ein Datenpunkt eines SPAETEREN Kalendertags mit derselben
    Uhrzeit (z. B. Folgetag 16:00 in einer mehrtaegigen night_weather-
    Zeitreihe) via _merge_hour die heutige Stunde -- die Kurzform behauptet
    dann ein Gewitter-/Regenfenster, das in KEINER gerenderten Tabellenzeile
    auftaucht (die Tabelle filtert bereits korrekt nach Datum). Das Fenster
    endet hier stets am Ankunftstag selbst (DAY_WINDOW_END_HOUR = 19 Uhr
    desselben Tages) -- anders als _extract_night_rows braucht diese
    Funktion daher KEINEN separaten Folgetag-Zweig (kein Analogon zu deren
    is_next_day, der dort das Nacht-Fenster bis 06:00 morgens erweitert).
    """
    if not segments:
        return []

    raw: list[ForecastDataPoint] = []

    for idx, seg in enumerate(segments):
        ts = seg.timeseries
        if seg.has_error or ts is None or not ts.data:
            continue
        start_h = local_hour(seg.segment.start_time, tz)
        end_h = local_hour(seg.segment.end_time, tz)
        if idx == 0:
            start_h = DAY_WINDOW_START_HOUR
        for dp in ts.data:
            h = local_hour(dp.ts, tz)
            in_window = (start_h <= h <= end_h) if start_h <= end_h else (h >= start_h or h <= end_h)
            if in_window:
                raw.append(dp)

    if night_weather is not None and night_weather.data:
        arrival_dt = segments[-1].segment.end_time
        arrival_hour = local_hour(arrival_dt, tz)
        arrival_date = arrival_dt.astimezone(tz).date()
        for dp in night_weather.data:
            if dp.ts.astimezone(tz).date() != arrival_date:
                continue  # kein Folgetag-Leck in die heutige Stunde (Kurzform-Tabelle-Datumsfilter)
            h = local_hour(dp.ts, tz)
            if arrival_hour <= h <= DAY_WINDOW_END_HOUR:
                raw.append(dp)

    by_hour: dict[int, list[ForecastDataPoint]] = {}
    for dp in raw:
        h = local_hour(dp.ts, tz)
        if DAY_WINDOW_START_HOUR <= h <= DAY_WINDOW_END_HOUR:
            by_hour.setdefault(h, []).append(dp)

    return [_merge_hour(by_hour[h]) for h in sorted(by_hour)]
