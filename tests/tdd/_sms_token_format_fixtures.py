"""Geteilte Fixtures fuer #1824 (SMS-Bereichs-Token + Trenner bei Buchstaben-Werten).

Kein Test-Modul (fuehrender Unterstrich -> pytest sammelt es nicht ein), nur
echte Datenmodell-Objekte und echte Renderer-Aufrufe. Kein ``Mock()``, kein
``patch()``, kein Netz, keine Mail. Vorbild fuer den Aufbau:
``tests/tdd/_min_temp_felt_fixtures.py`` (#1410) — dort sind die Temperaturen
allerdings Modul-Konstanten; #1824 braucht sie parametrisierbar (negative
Werte, fehlende Haelften, gefuehltes Pendant), deshalb diese eigene Datei.

Prueforte, die diese Fixtures bedienen:

* ``TripReportFormatter().format_email(...).sms_text`` — der echte Weg von der
  Nutzereinstellung (Metrik-Auswahl) bis zur fertigen Kurznachricht. Seit
  #1728 Scheibe 1 gaten dort die eigenen Tagesrichtungs-Groessen; das
  Auswertungs-Gate aus #1660 A (``_AGG_GATE_SYMBOLS``) ist entfallen.
* ``SMSTripFormatter().format_sms(..., max_length=...)`` — derselbe Renderer,
  den ``format_email`` aufruft; nur so laesst sich Kuerzungsdruck (§6)
  erzeugen, ohne den 160er-Default zu verbiegen.

Die Zeitreihe traegt neben den Temperaturen Regen-/Wind-/Boeen-/Gewitter-
Verlaeufe, damit die Zeile realistisch lang wird.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    PrecipType,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from output.renderers.trip_report import TripReportFormatter

YEAR, MONTH, DAY = 2026, 7, 20
TZ = ZoneInfo("Europe/Paris")  # CEST = UTC+2 im Juli

WALK_START_H = 8   # Ortszeit
ARRIVAL_H = 12     # Ortszeit, Etappenende == Ankunft am Ziel
COLD_HOUR = 8      # kaelteste Gehzeit-Stunde (Ortszeit)
WARM_HOUR = 11     # waermste Gehzeit-Stunde (Ortszeit)
NIGHT_LOW_HOUR = 3  # Folgetag, Ortszeit — Tiefpunkt der Nacht am Ziel

STAGE_NAME = "E7"

# Spec-Werte der Akzeptanzkriterien (AC-1/AC-9/AC-10).
HIKE_MIN_C = 13.0
HIKE_MAX_C = 27.0
FELT_HIKE_MIN_C = 10.0
FELT_HIKE_MAX_C = 20.0
NIGHT_MIN_C = 9.0
FELT_NIGHT_MIN_C = 7.0

NW_DEGREES = 315  # _COMPASS_SECTORS[7] == "NW" (sms_trip.py:142)


def local_to_utc(day: int, hour: int) -> datetime:
    """Ortszeit-Wanduhr (Europe/Paris) -> echter UTC-Instant."""
    return datetime(YEAR, MONTH, day, hour, 0, tzinfo=TZ).astimezone(timezone.utc)


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(YEAR, MONTH, DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _mid(low: Optional[float], high: Optional[float]) -> Optional[float]:
    """Mittelwert der Randstunden — liegt garantiert zwischen beiden, damit
    Min/Max ueber das Gehzeit-Fenster exakt die uebergebenen Werte sind."""
    if low is None or high is None:
        return low if high is None else high
    return (low + high) / 2.0


def segment(
    *,
    temp_min: Optional[float] = HIKE_MIN_C,
    temp_max: Optional[float] = HIKE_MAX_C,
    felt_min: Optional[float] = FELT_HIKE_MIN_C,
    felt_max: Optional[float] = FELT_HIKE_MAX_C,
    hourly_temps: bool = True,
    wind_dir_deg: Optional[int] = None,
    precip_type: Optional[PrecipType] = None,
    day: int = DAY,
    snow_depth_cm: Optional[float] = None,
) -> SegmentWeatherData:
    """Wander-Segment lokal 08:00-12:00 mit voller 24h-Zeitreihe.

    ``hourly_temps=False``: die Stundenpunkte tragen KEINE Temperatur
    (``t2m_c``/``wind_chill_c`` = None). Der Renderer faellt dann auf den
    Segment-Aggregat-Pfad zurueck (``sms_trip.py::_agg``), in dem Tiefst- und
    Hoechstwert UNABHAENGIG voneinander fehlen koennen — der einzige reale
    Weg zu einer halb besetzten Temperatur-Spanne (AC-6/AC-8).

    ``snow_depth_cm``: optionaler echter Wintersport-Wert (Default ``None``
    -- unveraendertes Verhalten fuer alle bestehenden Aufrufer). Fix #1887
    E6 Scheibe A: seit ``WC`` ersatzlos entfaellt, ist dies der einzige Weg,
    ueberhaupt einen Wintersport-Token (``SD``) aus diesem Segment zu
    erzeugen -- ohne ihn bleibt der Wintersport-Block leer.
    """
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1400.0,
                           distance_from_start_km=12.0),
        start_time=local_to_utc(day, WALK_START_H),
        end_time=local_to_utc(day, ARRIVAL_H),
        duration_hours=float(ARRIVAL_H - WALK_START_H),
        distance_km=12.0, ascent_m=900.0, descent_m=100.0,
    )
    base_temp, base_felt = _mid(temp_min, temp_max), _mid(felt_min, felt_max)
    data: list[ForecastDataPoint] = []
    for h in range(0, 24):
        if not hourly_temps:
            temp = felt = None
        elif h == COLD_HOUR:
            temp, felt = temp_min, felt_min
        elif h == WARM_HOUR:
            temp, felt = temp_max, felt_max
        else:
            temp, felt = base_temp, base_felt
        data.append(ForecastDataPoint(
            ts=local_to_utc(day, h),
            t2m_c=temp, wind_chill_c=felt,
            wind10m_kmh=45.0 if h == 10 else 12.0,
            gust_kmh=70.0 if h == 10 else 22.0,
            wind_direction_deg=wind_dir_deg,
            precip_1h_mm=0.5 if h == 5 else (8.4 if h == WARM_HOUR else 0.0),
            pop_pct=40 if h == 5 else (95 if h == WARM_HOUR else 0),
            cloud_total_pct=50, humidity_pct=55, precip_type=precip_type,
            thunder_level=ThunderLevel.MED if h == WARM_HOUR else ThunderLevel.NONE,
        ))
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(meta=_meta(), data=data),
        aggregated=SegmentWeatherSummary(
            temp_min_c=temp_min, temp_max_c=temp_max, temp_avg_c=base_temp,
            wind_chill_min_c=felt_min, wind_chill_max_c=felt_max,
            wind_max_kmh=45.0, gust_max_kmh=70.0, precip_sum_mm=8.9,
            pop_max_pct=95, cloud_avg_pct=50,
            thunder_level_max=ThunderLevel.MED,
            snow_depth_cm=snow_depth_cm,
        ),
        fetched_at=datetime(YEAR, MONTH, day, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def night_weather(day: int = DAY) -> NormalizedTimeseries:
    """Nacht-Zeitreihe Ankunft (12:00) -> 06:00 Folgetag am Etappenziel,
    Tiefpunkt um 03:00 (gemessen 9 °C / gefuehlt 7 °C), sonst milder."""
    points: list[ForecastDataPoint] = []
    for d, hours in ((day, range(ARRIVAL_H, 24)), (day + 1, range(0, 7))):
        for h in hours:
            low = (d == day + 1 and h == NIGHT_LOW_HOUR)
            points.append(ForecastDataPoint(
                ts=local_to_utc(d, h),
                t2m_c=NIGHT_MIN_C if low else NIGHT_MIN_C + 5.0,
                wind_chill_c=FELT_NIGHT_MIN_C if low else FELT_NIGHT_MIN_C + 5.0,
                wind10m_kmh=12.0, gust_kmh=22.0, precip_1h_mm=0.0, pop_pct=0,
                cloud_total_pct=50, humidity_pct=55,
                thunder_level=ThunderLevel.NONE,
            ))
    return NormalizedTimeseries(meta=_meta(), data=points)


def dc(*metric_ids: str) -> UnifiedWeatherDisplayConfig:
    """Displaykonfiguration mit genau den genannten Metriken aktiv.

    Issue #1728 Scheibe 1: der fruehere ``aggregations``-Parameter ist
    entfernt — die Sichtbarkeit von K/D bzw. FK/FD steuert jetzt die Auswahl
    der eigenen Groessen ``temperature_day_low``/``_high`` bzw.
    ``wind_chill_day_low``/``_high``, nicht mehr ``MetricConfig.aggregations``.
    """
    return UnifiedWeatherDisplayConfig(
        trip_id="i1824",
        metrics=[MetricConfig(metric_id=m, enabled=True) for m in metric_ids],
    )


def sms(*metric_ids: str,
        report_type: str = "evening",
        segments: Optional[list[SegmentWeatherData]] = None,
        with_night_weather: bool = True,
        has_gap: bool = False) -> str:
    """Echt gerenderte Trip-SMS ueber ``TripReportFormatter.format_email()``."""
    report = TripReportFormatter().format_email(
        segments if segments is not None else [segment()],
        trip_name="Issue1824",
        report_type=report_type,
        night_weather=night_weather() if with_night_weather else None,
        display_config=dc(*metric_ids),
        stage_name=STAGE_NAME,
        tz=TZ,
        has_gap=has_gap,
    )
    return report.sms_text


def body(sms_text: str) -> str:
    """SMS ohne Etappen-Praefix ('E7: ' -> Rest)."""
    return sms_text.split(": ", 1)[1] if ": " in sms_text else sms_text


def tokens(sms_text: str) -> list[str]:
    """Die whitespace-getrennten Token der gerenderten Zeile."""
    return body(sms_text).split(" ")


def token_with_symbol(sms_text: str, symbol: str) -> Optional[str]:
    """Das VOLLSTAENDIGE Token zum Kuerzel (``None`` = kommt nicht vor).

    Bewusst KEINE Wert-Grammatik im Muster (anders als die Bestands-Helfer
    ``_min_temp_felt_fixtures.sms_token_value``/``_hiking_window_fixtures``,
    deren ``(-?\\d+|-|\\?)`` die Bereichsform strukturell ausschliesst) — der
    Test soll den Wert BEOBACHTEN, nicht vorschreiben. Praefix-Verwechslungen
    sind dennoch ausgeschlossen: 'FD13/27' beginnt mit 'F', nicht mit 'D',
    und das Kuerzel endet, wo Ziffer/'-'/'?' beginnt.
    """
    for tok in tokens(sms_text):
        rest = tok[len(symbol):]
        if not tok.startswith(symbol):
            continue
        if rest[:1] in ("", "-", "?", "/") or rest[:1].isdigit():
            return tok
    return None


def token_for_prefix(sms_text: str, prefix: str) -> Optional[str]:
    """Das erste Token, das mit ``prefix`` beginnt — fuer Kuerzel mit
    BUCHSTABEN-Wert (``WD``/``PT``), deren Trenner gerade die Streitfrage ist:
    ein Muster, das den Doppelpunkt schon voraussetzt, koennte den Ist-Zustand
    (``WDNW``) gar nicht mehr sehen. Kein anderes Kuerzel beginnt mit 'WD'
    oder 'PT'."""
    for tok in tokens(sms_text):
        if tok.startswith(prefix):
            return tok
    return None
