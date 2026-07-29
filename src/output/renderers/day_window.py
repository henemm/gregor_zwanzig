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
from datetime import datetime, timedelta
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

from app.models import ForecastDataPoint, NormalizedTimeseries, SegmentWeatherData
from utils.timezone import local_dt, local_hour

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
    # Issue #1391/#1392 F001 (Adversary): lazy statt Modulkopf-Import.
    # `output.metric_format` importierte frueher (fuer einen inzwischen
    # entfernten toten `tone_css`-Re-Export) die `output.renderers.email`-
    # Paketkette, die WIEDER dieses Modul importierte -- ein Selbstbezug
    # innerhalb des `output`-Pakets. Die eigentliche Ursache ist behoben
    # (der Re-Export ist weg), dieser lazy Import bleibt trotzdem als
    # zusaetzliche Absicherung: derselbe Import-Stil, den
    # `WeatherMetricsService._compute_thunder_level` fuer `max_thunder`
    # schon verwendet, verhindert, dass der naechste Modulkopf-Import
    # irgendwo in der Renderer-Kette dieselbe Falle wieder aufreisst.
    from output.metric_format import max_thunder, thunder_ordinal
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
    """Epic #1319 Scheibe B (erweitert Issue #1361/#1372 S1b, AC-3): eine
    Quelle fuer die effektiven Fenster-Grenzen.

    ``None``/fehlend (Alt-Trip, Rueckwaertskompatibilitaet) oder ein
    ungueltiges Paar (ausserhalb 0-23, ``start == end``) faellt still auf
    den Default 4/19 zurueck -- Defense-in-Depth, falls eine ungueltige
    Kombination den Go-Store-Klemmpfad umgeht und dennoch bis zum Renderer
    durchreicht (AC-4).

    ``start > end`` ist seit #1361/#1372 S1b (PO-Entscheidung 2026-07-25)
    ein GUELTIGES Fenster ueber Mitternacht (z. B. 22-2 Uhr) -- NICHT mehr
    invalide. Nur ``start == end`` (Nullstunden- bzw. Ganztags-Mehrdeutigkeit)
    bleibt abgelehnt. Konsumenten (``build_day_window_points()``,
    ``comparison_engine._filter_by_target_date_and_window()``) muessen den
    Mitternachts-Fall selbst wrap-aware behandeln.
    """
    if day_window_start_hour is None or day_window_end_hour is None:
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    # F004: bool ist eine int-Subklasse in Python -- ohne den expliziten
    # Ausschluss wuerde JSON true/false als Stunde 1/0 durchgehen.
    if not (type(day_window_start_hour) is int and type(day_window_end_hour) is int):
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    if not (0 <= day_window_start_hour <= 23 and 0 <= day_window_end_hour <= 23):
        return DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR
    if day_window_start_hour == day_window_end_hour:
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
    endet normalerweise (``start_hour <= end_hour``) am Ankunftstag selbst.

    Issue #1361/#1372 S1b (AC-3): geht das Fenster ueber Mitternacht
    (``start_hour > end_hour``, z. B. 22-2 Uhr), erweitert sich der
    Nacht-Anteil zusaetzlich auf den ARRIVAL-Folgetag bis ``end_hour``
    desselben -- analog ``_extract_night_rows``' ``is_next_day``-Zweig, den
    diese Funktion vorher bewusst nicht brauchte (s. Historie unten).
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

    wraps = start_hour > end_hour
    if night_weather is not None and night_weather.data:
        arrival_dt = segments[-1].segment.end_time
        arrival_hour = local_hour(arrival_dt, tz)
        # Issue #1402: NIE .astimezone(tz) direkt auf einem naiven dp.ts/
        # arrival_dt aufrufen -- das deutet die Prozess-Zeitzone statt der
        # Hausnorm "naiv = UTC" (#1345). local_dt() geht ueber den zentralen
        # Naiv-Guard (utils.timezone._as_utc).
        arrival_date = local_dt(arrival_dt, tz).date()
        next_date = arrival_date + timedelta(days=1)
        for dp in night_weather.data:
            dp_date = local_dt(dp.ts, tz).date()
            h = local_hour(dp.ts, tz)
            if dp_date == arrival_date:
                # Mitternachts-Fenster (AC-3): am Ankunftstag reicht der
                # Nacht-Anteil bis 23 Uhr (der Rest liegt im Folgetag-Zweig
                # unten); ohne Wrap wie bisher nur bis end_hour.
                upper = 23 if wraps else end_hour
                if arrival_hour <= h <= upper:
                    raw.append(dp)
            elif wraps and dp_date == next_date:
                # Mitternachts-Fenster: der Folgetag-Anteil bis end_hour
                # (analog trip_report.py::_extract_night_rows is_next_day).
                if h <= end_hour:
                    raw.append(dp)
            # kein Wrap + anderer Kalendertag: kein Folgetag-Leck
            # (Kurzform-Tabelle-Datumsfilter, unveraendertes Bestandsverhalten).

    by_hour: dict[int, list[ForecastDataPoint]] = {}
    for dp in raw:
        h = local_hour(dp.ts, tz)
        in_final_window = (start_hour <= h <= end_hour) if not wraps else (h >= start_hour or h <= end_hour)
        if in_final_window:
            by_hour.setdefault(h, []).append(dp)

    return [_merge_hour(by_hour[h]) for h in sorted(by_hour)]


def collect_hiking_window_points(
    segments: Sequence[SegmentWeatherData],
) -> list[ForecastDataPoint]:
    """Gehzeit-Fenster je Segment: inklusiver Start, EXKLUSIVES Ende — ausser
    beim LETZTEN verwertbaren Segment eines Reports, dessen Ende INKLUSIV
    zaehlt (Bug #1146: die Ankunftsstunde ist erlebte Gehzeit). Innere
    Segmentgrenzen bleiben dadurch exakt einmal gezaehlt (#806/#807).

    EINZIGE Quelle fuer Temperatur/gefuehlte Temperatur in Mail-Kachelzeile,
    SMS, Telegram-Kurzuebersicht und E-Mail-Kurzzusammenfassung (Issue #1417).
    Verschoben aus ``email/helpers.py::_collect_hiking_window_dps()``; Logik
    unveraendert bis auf AC-9 (s.u.).

    Issue #1417 AC-9: „letztes Segment" wird ueber die VERWERTBAREN Teile
    bestimmt, nicht ueber die Rohliste. Faellt der letzte Teil aus (Provider-
    Fehler -> ``timeseries is None``), ist der davorliegende Teil die
    tatsaechliche Ankunft und behaelt seine Endstunde — vorher verlor er sie,
    weil ein ausgefallener Teil hinter ihm stand.

    Bewusst NICHT geaendert: die naive ``.hour``-Verwendung (kein
    ``local_hour(dp.ts, tz)``) — bestehendes Verhalten der Mail-Kachelzeile,
    die Funktion nimmt bis heute keinen ``tz``-Parameter (s. Spec „Known
    Limitations").
    """
    usable = [s for s in segments if getattr(s, "timeseries", None) is not None]
    all_dps: list[ForecastDataPoint] = []
    last_idx = len(usable) - 1
    for idx, seg_data in enumerate(usable):
        s = seg_data.segment
        s_h = s.start_time.hour
        e_h = s.end_time.hour
        is_last = idx == last_idx
        for dp in seg_data.timeseries.data:
            h = dp.ts.hour
            if s_h <= e_h:
                include = (s_h <= h <= e_h) if is_last else (s_h <= h < e_h)
            else:
                include = (h >= s_h or h <= e_h) if is_last else (h >= s_h or h < e_h)
            if include:
                all_dps.append(dp)
    return all_dps


def hiking_field_min_max(
    points: Sequence[ForecastDataPoint], field: str,
) -> Optional[tuple[float, float, datetime]]:
    """``(min_value, max_value, max_ts)`` fuer EIN ``ForecastDataPoint``-Feld aus
    bereits gefensterten Rohpunkten (``collect_hiking_window_points()``).

    ``max_ts`` bedient sowohl den Mail-Zeitanker (``· Max HH:00``) als auch die
    Telegram-Spitzenstunde (``@{h}``) — EINE Ableitung, zwei Verwendungen statt
    zweier paralleler Berechnungen. ``None``, wenn kein Punkt das Feld traegt
    (Fail-soft-Signal an den Aufrufer, der dann auf seine bisherige Quelle
    zurueckfaellt). Muster wie ``_night_min_of_field()`` (Issue #1410).
    """
    vals_ts = [(getattr(dp, field, None), dp.ts) for dp in points]
    vals_ts = [(float(v), ts) for v, ts in vals_ts if v is not None]
    if not vals_ts:
        return None
    min_val = min(v for v, _ in vals_ts)
    max_val, max_ts = max(vals_ts, key=lambda x: x[0])
    return min_val, max_val, max_ts


def _night_min_of_field(
    night_weather: Optional[NormalizedTimeseries],
    segments: Sequence[SegmentWeatherData],
    tz: ZoneInfo,
    field: str,
) -> Optional[float]:
    """Geteilter Kern (Issue #1410): Minimum EINES ForecastDataPoint-Feldes im
    Nachtfenster Ankunft -> 06:00 Folgetag.

    Fenster- und Datumsfilter sind fuer gemessene wie gefuehlte Temperatur
    identisch -- die beiden oeffentlichen Wrapper unterscheiden sich
    ausschliesslich im gelesenen Feld (``t2m_c`` bzw. ``wind_chill_c``).
    """
    if not night_weather or not night_weather.data or not segments:
        return None
    arrival_dt = segments[-1].segment.end_time
    arrival_hour = local_hour(arrival_dt, tz)
    # Issue #1402: local_dt() statt rohem .astimezone(tz) -- s. Begruendung
    # oben in extract_day_window_hours().
    arrival_date = local_dt(arrival_dt, tz).date()
    next_day = arrival_date + timedelta(days=1)
    temps: list[float] = []
    for dp in night_weather.data:
        dp_local_dt = local_dt(dp.ts, tz)
        dp_date = dp_local_dt.date()
        is_same_day = dp_date == arrival_date
        is_next_day = dp_date == next_day
        in_range = (is_same_day and dp_local_dt.hour >= arrival_hour) or (
            is_next_day and dp_local_dt.hour <= 6
        )
        value = getattr(dp, field, None)
        if in_range and value is not None:
            temps.append(float(value))
    return min(temps) if temps else None


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

    Signatur und Verhalten unveraendert (Issue #1410: nur der Rumpf wandert
    in den geteilten Kern ``_night_min_of_field``).
    """
    return _night_min_of_field(night_weather, segments, tz, "t2m_c")


def night_wind_chill_min_c(
    night_weather: Optional[NormalizedTimeseries],
    segments: Sequence[SegmentWeatherData],
    tz: ZoneInfo,
) -> Optional[float]:
    """Echte GEFUEHLTE Nacht-Tiefsttemperatur am Schlafplatz (Issue #1410).

    Exakt dasselbe Fenster und derselbe Datumsfilter wie
    ``night_temp_min_c()`` -- PO-Vorgabe „die gefuehlte Temperatur verhaelt
    sich exakt wie die gemessene" (F4). Einziger Unterschied: gelesen wird
    ``wind_chill_c`` statt ``t2m_c``.
    """
    return _night_min_of_field(night_weather, segments, tz, "wind_chill_c")
