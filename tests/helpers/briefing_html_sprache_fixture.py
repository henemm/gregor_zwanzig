"""Reiches Trip-Briefing-Szenario fuer die Sprachtests der HTML-Mail (#2664).

Ein Aufruf des ECHTEN ``TripReportFormatter.format_email`` mit allen
Bloecken, die ``email/html.py`` selbst beschriftet: Kennzahlen, Etappen-
Zaehler, Stabilitaets-Box, Nacht am Ziel, 3-Tages-Ausblick, Pillen mit
mittlerem Gewitter und Fusszeile. Kein Mock; die Daten sind fest.

``sichtbarer_text`` liefert den Text, den ein Mensch im Mailprogramm sieht
(ohne ``<head>``/``<style>``), ``ohne_spaetere_pakete`` schneidet die
Bloecke heraus, deren Woerter laut Spec erst spaetere Pakete umstellen
(Tageslage-Satz und Antwort-Kommandos: P3 #2665/P10 #2673).
"""
from __future__ import annotations

import html as _html
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, StabilityResult, ThunderLevel,
    TripSegment,
)
from output.renderers.trip_report import TripReportFormatter
from output.tokens.dto import HourlyValue

TZ = ZoneInfo("Europe/Paris")
UTC = timezone.utc
SENT_AT = datetime(2026, 10, 29, 4, 0, tzinfo=UTC)  # Do 29.10.2026 05:00 CET


def _dp(tag: int, stunde: int, *, gewitter=ThunderLevel.NONE, regen=0.0) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 10, tag, stunde, 0, tzinfo=UTC), t2m_c=9.0 + stunde % 6,
        wind10m_kmh=24.0, gust_kmh=48.0 + stunde, precip_1h_mm=regen, pop_pct=60,
        cloud_total_pct=70, thunder_level=gewitter, wind_chill_c=6.0,
        visibility_m=18000.0, humidity_pct=70,
    )


def _segment() -> SegmentWeatherData:
    data = [_dp(29, h, gewitter=ThunderLevel.MED if 10 <= h <= 12 else ThunderLevel.NONE,
                regen=1.5 if h == 11 else 0.0) for h in range(6, 15)]
    # Hagel in der Gewitterstunde 11 UTC (Doppelring + Hagel-Legende) und eine
    # unsichere Stunde (Verlaesslichkeits-Hinweis im Mailkopf).
    data[5].hail_flag = True
    data[6].confidence_pct = 40
    seg = TripSegment(
        segment_id=1, start_point=GPXPoint(lat=42.10, lon=9.10, elevation_m=900.0),
        end_point=GPXPoint(lat=42.15, lon=9.14, elevation_m=1600.0),
        start_time=datetime(2026, 10, 29, 7, 0, tzinfo=UTC),
        end_time=datetime(2026, 10, 29, 12, 0, tzinfo=UTC),
        duration_hours=5.0, distance_km=11.0, ascent_m=900.0, descent_m=200.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 10, 29, 0, 0, tzinfo=UTC), grid_res_km=1.3, interp="point_grid",
    )
    agg = SegmentWeatherSummary(
        temp_min_c=9.0, temp_max_c=14.0, temp_avg_c=11.5, wind_max_kmh=24.0,
        gust_max_kmh=62.0, precip_sum_mm=1.5, cloud_avg_pct=70, humidity_avg_pct=70,
        thunder_level_max=ThunderLevel.MED, wind_chill_min_c=6.0, wind_chill_max_c=8.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=data), aggregated=agg,
        fetched_at=SENT_AT, provider="openmeteo",
    )


def _nacht() -> NormalizedTimeseries:
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 10, 29, 0, 0, tzinfo=UTC), grid_res_km=1.3, interp="point_grid",
    )
    dps = [_dp(29, h) for h in range(12, 24)] + [_dp(30, h) for h in range(0, 6)]
    return NormalizedTimeseries(meta=meta, data=dps)


def _trend() -> list[dict]:
    gewitter = (HourlyValue(13, 2.0), HourlyValue(15, 3.0))
    return [
        {"weekday": "Fr", "temp_lo": 7, "temp_hi": 14, "precip_mm": 2.0, "wind_kmh": 22,
         "rain_probability_pct": 50, "confidence_pct": 80, "thunder": "MED",
         "hourly_thunder": gewitter},
        {"weekday": "Sa", "temp_lo": 6, "temp_hi": 12, "precip_mm": 0.0, "wind_kmh": 18,
         "rain_probability_pct": 20, "confidence_pct": 65, "thunder": "NONE"},
    ]


def render_reich(lang: str | None = None, *, dc=None, profile=None,
                 trip_name: str = "Corsica North", ausblick: bool = True):
    """Rendert das reiche Szenario; ``lang=None`` = Aufruf ohne ``lang``.

    ``ausblick=False``: ohne 3-Tages-Ausblick -- die Stabilitaets-Box steht
    dann im eigenen Zweig statt im Ausblick-Block."""
    kw = {} if lang is None else {"lang": lang}
    dc = dc or build_default_display_config()
    report = TripReportFormatter().format_email(
        [_segment()], trip_name, "morning", display_config=dc,
        night_weather=_nacht(), multi_day_trend=_trend() if ausblick else None,
        stage_name="Etappe 2: Vizzavona → Capannelle", stage_total=5,
        stage_stats={"distance_km": 11.0, "ascent_m": 900, "descent_m": 200,
                     "max_elevation_m": 1600},
        stability_result=StabilityResult(label="WECHSELHAFT", confidence_pct=60),
        tz=TZ, profile=profile, trip_url="https://gregor20.henemm.com/trips/t1", **kw,
    )
    return report


def sichtbarer_text(html: str) -> str:
    s = re.sub(r"<head>.*?</head>", "", html, flags=re.S)
    s = re.sub(r"<[^>]+>", "\n", s)
    zeilen = [z.strip() for z in _html.unescape(s).split("\n")]
    return "\n".join(z for z in zeilen if z)


def ohne_spaetere_pakete(text: str) -> str:
    """Schneidet Tageslage-Satz (P3) und Antwort-Kommandos (P3/P10) heraus."""
    text = re.sub(r"DAY SUMMARY\n.*?\n(?=Metrics overview)", "", text, flags=re.S)
    return re.sub(r"Antwort-Kommandos\n.*?\n(?=RISK)", "", text, flags=re.S)
