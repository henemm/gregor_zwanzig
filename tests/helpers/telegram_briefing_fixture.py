"""Deterministische Golden-Fixture des Telegram-Briefings (Issue #2669, i18n P7).

SPEC: docs/specs/modules/i18n_p7_telegram_2669.md (Abschnitt "Golden-Fixture").

Feste Zeit 2026-10-29T06:00+02:00, feste Wetterwerte, Trip mit zwei Segmenten
(Segment 1 und Ziel), Gewitter (Stufe leicht -> Luftmasse), Sicht, Nullgrad-
grenze, Vortag-Delta, ein Ausblick-Tag und eine amtliche Warnung (ORANGE).
Echte Modellobjekte, echter Renderer-Aufruf, netzfrei, kein Mock.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, MetricConfig, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    UnifiedWeatherDisplayConfig,
)
from output.renderers.narrow import render_telegram_bubbles
from services.day_comparison import (
    ComparisonDirection, DayComparison, DayComparisonEntry, MetricDelta,
)
from services.official_alerts.models import OfficialAlert

TZ = ZoneInfo("Etc/GMT-2")  # feste Zone +02:00 (POSIX-Vorzeichen invertiert)
START = datetime(2026, 10, 29, 6, 0, tzinfo=TZ)
GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden" / "telegram_briefing"
BUBBLE_SEP = "\n---\n"

METRIC_IDS = ["temperature", "wind", "gust", "precipitation", "thunder",
              "visibility", "freezing_level"]
REGION = "Haute-Corse"
TRIP_NAME = "GR20 Nord"


def _dp(ts: datetime, thunder: ThunderLevel) -> ForecastDataPoint:
    h = ts.astimezone(TZ).hour
    return ForecastDataPoint(
        ts=ts, t2m_c=6.0 + h * 0.5, wind10m_kmh=10.0 + h, gust_kmh=20.0 + h,
        precip_1h_mm=0.2 if 12 <= h <= 14 else 0.0, cloud_total_pct=40,
        thunder_level=thunder, humidity_pct=60, pop_pct=20.0,
        visibility_m=15000, freezing_level_m=2800,
    )


def _segment(seg_id: object, km: tuple[float, float], hours: tuple[int, int],
             alerts: list[OfficialAlert]) -> SegmentWeatherData:
    day0 = START.replace(hour=0)
    data = [_dp(day0 + timedelta(hours=h),
                ThunderLevel.LOW if 13 <= h <= 15 else ThunderLevel.NONE)
            for h in range(24)]
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=1200.0,
                             distance_from_start_km=km[0]),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1800.0,
                           distance_from_start_km=km[1]),
        start_time=day0 + timedelta(hours=hours[0]),
        end_time=day0 + timedelta(hours=hours[1]),
        duration_hours=float(hours[1] - hours[0]), distance_km=km[1] - km[0],
        ascent_m=850.0, descent_m=250.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="golden",
                        run=day0.astimezone(timezone.utc), grid_res_km=1.0,
                        interp="point_grid")
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=data),
        aggregated=SegmentWeatherSummary(
            temp_min_c=6.0, temp_max_c=17.5, wind_max_kmh=33.0, gust_max_kmh=43.0,
            precip_sum_mm=0.6, pop_max_pct=20.0, thunder_level_max=ThunderLevel.LOW,
            visibility_min_m=15000, freezing_level_m=2800,
        ),
        fetched_at=START, provider="openmeteo", official_alerts=list(alerts),
    )


def _alert() -> OfficialAlert:
    return OfficialAlert(
        source="meteoalarm", hazard="thunderstorm", level=3, label="Gewitter",
        valid_from=START.replace(hour=12), valid_to=START.replace(hour=18),
        region_label=REGION,
    )


def _rows(hours: range) -> list[dict]:
    return [{"time": f"{h:02d}", "temp": 6 + h // 2, "wind": 10 + h,
             "gust": 20 + h, "precip": 0.2 if 12 <= h <= 14 else 0.0,
             "thunder": "LOW" if 13 <= h <= 15 else "NONE",
             "visibility": 15000, "freeze_lvl": 2800} for h in hours]


def _delta(v: float | None) -> MetricDelta:
    if v is None:
        return MetricDelta(delta=None, direction=ComparisonDirection.MISSING)
    return MetricDelta(delta=v, direction=ComparisonDirection.WORSE)


def _day_comparison() -> DayComparison:
    return DayComparison(entries=[DayComparisonEntry(
        segment_id=1, temp_min=_delta(None), temp_max=_delta(None),
        wind_max=_delta(None), gust_max=_delta(12.0), precip_sum=_delta(3.5),
        thunder=_delta(1.0),
    )])


def _trend(stage_date: date) -> list[dict]:
    return [{
        "weekday": "Fr", "date": stage_date, "name": "Etappe 2",
        "temp_lo": 5.0, "temp_hi": 15.0, "precip_mm": 0.0, "wind_dir": "NW",
        "wind_kmh": 20.0, "thunder": "NONE", "note": None,
    }]


def _display_config() -> UnifiedWeatherDisplayConfig:
    return UnifiedWeatherDisplayConfig(
        trip_id="golden-de",
        metrics=[MetricConfig(metric_id=m, enabled=True, bucket="primary", order=i)
                 for i, m in enumerate(METRIC_IDS)],
        updated_at=START,
    )


def build_bubbles(*, trip_name: str = TRIP_NAME, error_segment: bool = False,
                  **overrides) -> list:
    """Bubbles der Golden-Fixture; ``lang`` und weitere Renderer-Argumente
    optional durchgereicht. ``error_segment`` haengt ein Segment 2 mit
    Provider-Fehler (``has_error``) vor dem Ziel ein."""
    alerts = [_alert()]
    segments = [_segment(1, (0.0, 8.4), (7, 12), alerts)]
    tables = [_rows(range(7, 13))]
    if error_segment:
        segments.append(replace(_segment(2, (8.4, 9.0), (12, 12), []),
                                has_error=True))
        tables.append([])
    segments.append(_segment("Ziel", (8.4, 14.2), (12, 16), alerts))
    tables.append(_rows(range(12, 17)))
    kwargs = {"multi_day_trend": _trend(date(2026, 10, 30)),
              "day_comparison": _day_comparison(), **overrides}
    return render_telegram_bubbles(
        segments=segments, seg_tables=tables, dc=_display_config(),
        report_type="morning", tz=TZ, trip_name=trip_name, **kwargs,
    )


def build_texts(*, trip_name: str = TRIP_NAME, **lang_kwarg) -> list[str]:
    """Bubble-Texte der Golden-Fixture."""
    return [b.text for b in build_bubbles(trip_name=trip_name, **lang_kwarg)]


def golden_path(lang: str) -> Path:
    return GOLDEN_DIR / f"briefing_normalstil.{lang}.txt"


def join_bubbles(texts: list[str]) -> str:
    return BUBBLE_SEP.join(texts) + "\n"
