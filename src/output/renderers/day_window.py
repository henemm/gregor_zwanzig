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
from datetime import timedelta
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


def resolve_configured_window(
    day_window_start_hour: Optional[int],
    day_window_end_hour: Optional[int],
) -> tuple[int, int]:
    """Epic #1319 Scheibe B: eine Quelle fuer die effektiven Fenster-Grenzen.

    ``None``/fehlend (Alt-Trip, Rueckwaertskompatibilitaet) oder ein
    ungueltiges Paar (ausserhalb 0-23, ``start >= end``) faellt still auf
    den Default 4/19 zurueck -- Defense-in-Depth, falls eine ungueltige
    Kombination den Go-Store-Klemmpfad umgeht und dennoch bis zum Renderer
    durchreicht (AC-4).
    """
    if day_window_start_hour is None or day_window_end_hour is None:
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    # F004: bool ist eine int-Subklasse in Python -- ohne den expliziten
    # Ausschluss wuerde JSON true/false als Stunde 1/0 durchgehen.
    if not (type(day_window_start_hour) is int and type(day_window_end_hour) is int):
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    if not (0 <= day_window_start_hour <= 23 and 0 <= day_window_end_hour <= 23):
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    if day_window_start_hour >= day_window_end_hour:
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    return day_window_start_hour, day_window_end_hour


def build_day_window_points(
    segments: Sequence[SegmentWeatherData],
    night_weather: Optional[NormalizedTimeseries],
    tz: ZoneInfo,
    start_hour: int = DAY_WINDOW_START_HOUR,
    end_hour: int = DAY_WINDOW_END_HOUR,
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
            start_h = start_hour
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
            if arrival_hour <= h <= end_hour:
                raw.append(dp)

    by_hour: dict[int, list[ForecastDataPoint]] = {}
    for dp in raw:
        h = local_hour(dp.ts, tz)
        if start_hour <= h <= end_hour:
            by_hour.setdefault(h, []).append(dp)

    return [_merge_hour(by_hour[h]) for h in sorted(by_hour)]


def night_temp_min_c(
    night_weather: Optional[NormalizedTimeseries],
    segments: Sequence[SegmentWeatherData],
    tz: ZoneInfo,
) -> Optional[float]:
    """Echte Nacht-Tiefsttemperatur am Schlafplatz (Issue #1319 Scheibe D).

    Fenster: Ankunft (Ende des letzten Segments) bis 06:00 Folgetag,
    gefiltert wie ``trip_report.py::_extract_night_rows`` Schritt 1 (gegen
    WeatherCacheService-"covers"-Kontamination durch Datenpunkte anderer
    Kalendertage), dann ``min(t2m_c)`` ueber die verbleibenden Punkte.
    ``None`` bei fehlenden Daten (fail-soft, kein Crash). Ersetzt NICHT
    ``_extract_night_rows()`` (bleibt fuer die grosse E-Mail-Tabelle
    unveraendert, DEC-3) -- separate, einfachere Ableitung ohne
    2h-Block-Aggregation.
    """
    if not night_weather or not night_weather.data or not segments:
        return None
    arrival_dt = segments[-1].segment.end_time
    arrival_hour = local_hour(arrival_dt, tz)
    arrival_date = arrival_dt.astimezone(tz).date()
    next_day = arrival_date + timedelta(days=1)
    temps: list[float] = []
    for dp in night_weather.data:
        local_dt = dp.ts.astimezone(tz)
        dp_date = local_dt.date()
        is_same_day = dp_date == arrival_date
        is_next_day = dp_date == next_day
        in_range = (is_same_day and local_dt.hour >= arrival_hour) or (
            is_next_day and local_dt.hour <= 6
        )
        if in_range and dp.t2m_c is not None:
            temps.append(dp.t2m_c)
    return min(temps) if temps else None
