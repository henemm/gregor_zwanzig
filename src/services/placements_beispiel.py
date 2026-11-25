"""Fester Beispiel-Datensatz der Tabelle "Was steht wo" (Issue #3122, B2).

Spec ``docs/specs/modules/feat_3122_was_steht_wo.md`` Teil A Nr. 9: Beispiel-
werte und SMS-Beispiel entstehen in denselben Renderer-Funktionen wie der
Versand, aus diesem festen, versionierten Datensatz -- ohne Wetterabruf.

Reine Daten: ein Sommertag mit Wind, der am Nachmittag ins Gelbe kommt,
leichtem Schauer, Gewitter am Nachmittag und allen Feldern, die eine Metrik der
Grundauswahl braucht (sonst zeigte die Tabelle fuer sie keinen Wert). Trip:
eine Etappe aus zwei Segmenten; Orte: dieselben Stundenwerte je Ort leicht
verschoben. Aenderungen am Datensatz erhoehen ``VERSION``.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, PrecipType,
    Provider, SegmentWeatherData, ThunderLevel, TripSegment,
)
from utils.timezone import local_hour, to_utc, tz_for_coords

VERSION = 2
#: Ort des Beispiels (Innsbruck); die Zone kommt aus den Koordinaten wie bei
#: jedem Ort (kein festes Zonen-Literal, #1402).
LAT, LON = 47.27, 11.39
ZONE = tz_for_coords(LAT, LON)
TAG = date(2026, 7, 14)
#: Wochentags-Kuerzel der drei Ausblick-Tage (Protokoll-Token, nie uebersetzt).
AUSBLICK_TAGE = ("Mi", "Do", "Fr")


def _gewitter(h: int) -> ThunderLevel:
    if h in (15, 16):
        return ThunderLevel.MED
    return ThunderLevel.LOW if h in (14, 17) else ThunderLevel.NONE


def _punkt(ts: datetime, h: int, versatz: int = 0) -> ForecastDataPoint:
    """Ein Stundenwert; ``h`` ist die Ortsstunde, ``versatz`` verschiebt die
    Werte je Ort bzw. Ausblick-Tag."""
    nass = 13 <= h <= 16
    return ForecastDataPoint(
        ts=ts, t2m_c=9.5 + 0.6 * h + versatz, wind10m_kmh=8.0 + 2.2 * h + versatz,
        wind_direction_deg=240 + 5 * versatz, gust_kmh=14.0 + 3.0 * h + versatz,
        precip_1h_mm=(0.4 + 0.3 * (h - 13)) if nass else 0.0, cloud_total_pct=min(20 + 4 * h, 95),
        cloud_low_pct=min(5 + 3 * h, 90), cloud_mid_pct=min(10 + 2 * h, 80), cloud_high_pct=25,
        thunder_level=_gewitter(h), cape_jkg=650.0 if nass else 120.0,
        pop_pct=70 if nass else 15, pressure_msl_hpa=1016.0 - 0.2 * h,
        humidity_pct=55 + h, dewpoint_c=6.0 + 0.2 * h, uv_index=float(max(0, 7 - abs(13 - h))),
        snow_depth_cm=0.0, snow_new_24h_cm=0.0, snowfall_limit_m=2900 + 10 * versatz,
        precip_type=PrecipType.RAIN if nass else None, freezing_level_m=3300 + 10 * versatz,
        wind_chill_c=7.0 + 0.6 * h + versatz, visibility_m=24000 - 600 * h,
        wmo_code=95 if h in (15, 16) else (61 if nass else 2), is_day=1 if 6 <= h <= 20 else 0,
        dni_wm2=0.0 if nass or not 6 <= h <= 20 else 520.0,
    )


def tagespunkte(tag: date = TAG, versatz: int = 0) -> list[ForecastDataPoint]:
    """24 Stundenwerte eines Tages in Ortszeit (Zeitstempel UTC)."""
    beginn = datetime(tag.year, tag.month, tag.day, tzinfo=ZONE)
    return [
        _punkt(to_utc(beginn + timedelta(hours=h)), h, versatz)
        for h in range(24)
    ]


def _ortsstunde(p: ForecastDataPoint) -> int:
    """Ortsstunde eines Stundenwerts (Zeitstempel naive = UTC, Hausnorm)."""
    return local_hour(p.ts, ZONE)


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="beispiel", grid_res_km=1.0,
        run=datetime(2026, 7, 14, 0, 0, tzinfo=timezone.utc), interp="point_grid",
    )


def _segment(seg_id: int | str, km: tuple[float, float], stunden: tuple[int, int]) -> SegmentWeatherData:
    from services.weather_metrics import summarize_points

    punkte = tagespunkte()
    beginn = datetime(TAG.year, TAG.month, TAG.day, tzinfo=ZONE)
    start = to_utc(beginn + timedelta(hours=stunden[0]))
    ende = to_utc(beginn + timedelta(hours=stunden[1]))
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=LAT, lon=LON, elevation_m=1200.0, distance_from_start_km=km[0]),
        end_point=GPXPoint(lat=47.30, lon=11.45, elevation_m=1850.0, distance_from_start_km=km[1]),
        start_time=start, end_time=ende, duration_hours=float(stunden[1] - stunden[0]),
        distance_km=km[1] - km[0], ascent_m=820.0, descent_m=170.0,
    )
    gehzeit = [p for p in punkte if stunden[0] <= _ortsstunde(p) <= stunden[1]]
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=_meta(), data=punkte),
        aggregated=summarize_points(gehzeit), fetched_at=start, provider="openmeteo",
    )


def trip_segmente() -> list[SegmentWeatherData]:
    """Eine Etappe: Segment 1 (08-12 Uhr) und Ziel (12-16 Uhr)."""
    return [_segment(1, (0.0, 7.5), (8, 12)), _segment("Ziel", (7.5, 14.0), (12, 16))]


def nacht_zeitreihe() -> NormalizedTimeseries:
    """Nacht am Ziel (#3373): Ankunft 16 Uhr bis 06 Uhr Ortszeit am Folgetag,
    der Zeitraum, den der Versand als Nachtwetter abruft. Folgetag ohne
    Versatz (dieselbe Wetterlage, die Nacht gehoert zur Etappe)."""
    abend = [p for p in tagespunkte(TAG) if _ortsstunde(p) >= 16]
    morgen = [p for p in tagespunkte(TAG + timedelta(days=1)) if _ortsstunde(p) <= 6]
    return NormalizedTimeseries(meta=_meta(), data=abend + morgen)


def ausblick_tage() -> list[tuple[str, list[ForecastDataPoint]]]:
    """(Wochentags-Kuerzel, Stundenwerte) der drei Ausblick-Tage."""
    return [
        (kuerzel, tagespunkte(TAG + timedelta(days=i + 1), versatz=2 * (i + 1)))
        for i, kuerzel in enumerate(AUSBLICK_TAGE)
    ]


def orte_ergebnis(orte: list):
    """``ComparisonResult`` fuer die gegebenen Orte (``SavedLocation``), je
    Ort dieselben Stundenwerte leicht verschoben, mit 3-Tages-Ausblick."""
    from app.user import ComparisonResult, LocationResult
    from services.weather_metrics import summarize_points

    ergebnisse = []
    for i, ort in enumerate(orte):
        punkte = tagespunkte(versatz=i)
        tag = [p for p in punkte if 9 <= _ortsstunde(p) <= 16]
        summe = summarize_points(tag)
        ausblick = [p for d in range(1, 4) for p in tagespunkte(TAG + timedelta(days=d), versatz=i + d)]
        ergebnisse.append(LocationResult(
            location=ort, temp_max=summe.temp_max_c, temp_min=summe.temp_min_c,
            wind_max=summe.wind_max_kmh, gust_max=summe.gust_max_kmh, sunny_hours=5 + i,
            cloud_avg=summe.cloud_avg_pct, cloud_low_avg=summe.cloud_low_avg_pct,
            cloud_mid_avg=summe.cloud_mid_avg_pct, cloud_high_avg=summe.cloud_high_avg_pct,
            wind_chill_min=summe.wind_chill_min_c, wind_chill_max=summe.wind_chill_max_c,
            wind_direction_avg=summe.wind_direction_avg_deg, snow_depth_cm=summe.snow_depth_cm,
            snow_new_cm=summe.snow_new_sum_cm, official_alerts=[], hourly_data=tag,
            outlook_hourly_data=ausblick,
        ))
    return ComparisonResult(
        locations=ergebnisse, time_window=(9, 16), target_date=TAG,
        created_at=datetime(2026, 7, 14, 4, 0),
    )
