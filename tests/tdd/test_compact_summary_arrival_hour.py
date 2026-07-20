"""Ankunftsstunde in der Natursprache-Kurzzusammenfassung (#1220, AC-11).

SPEC: docs/specs/modules/sms_official_alert_tokens.md — AC-11

Regressions-Absicherung, kein neuer Bug-Beweis: die urspruengliche Ursache
(exklusives Fenster-Ende, `_collect_hourly_data`) ist mit der Umstellung auf das
geteilte `day_window`-Modul (#1317/#1319 Scheibe A) verschwunden —
`build_day_window_points` behandelt die Ankunftsstunde inklusiv
(`day_window.py:91/99`). Dieser Test friert das ein: faellt Regen
AUSSCHLIESSLICH in der Ankunftsstunde, muss die Kurzzusammenfassung ihn samt
Uhrzeit benennen. Wuerde die Ankunftsstunde wieder aus dem Fenster fallen,
bliebe die Stundenliste regenfrei und der Satz nennte nur noch das pauschale
Regen-Adjektiv aus dem Etappen-Aggregat — ohne Zeitangabe.

Verhaltenstest — keine Mocks, echte Segmente, echter Renderer-Aufruf, netzfrei.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, MetricConfig, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    UnifiedWeatherDisplayConfig,
)
from output.renderers.compact_summary import CompactSummaryFormatter

UTC = timezone.utc
_TZ = ZoneInfo("UTC")
_YEAR, _MONTH, _DAY = 2026, 7, 15
_START_H, _ARRIVAL_H = 8, 17
_ARRIVAL_RAIN_MM = 3.0


def _dp(hour: int, rain: float) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=UTC),
        t2m_c=16.0, wind10m_kmh=8.0, gust_kmh=14.0, precip_1h_mm=rain,
        cloud_total_pct=50, thunder_level=ThunderLevel.NONE, humidity_pct=60,
        pop_pct=30.0,
    )


def _segment_rain_only_at_arrival() -> SegmentWeatherData:
    """Etappe 08:00-17:00; Regen ausschliesslich in der Ankunftsstunde 17:00."""
    data = [_dp(h, _ARRIVAL_RAIN_MM if h == _ARRIVAL_H else 0.0) for h in range(24)]
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.2, lon=9.2, elevation_m=1100.0),
        start_time=datetime(_YEAR, _MONTH, _DAY, _START_H, 0, tzinfo=UTC),
        end_time=datetime(_YEAR, _MONTH, _DAY, _ARRIVAL_H, 0, tzinfo=UTC),
        duration_hours=float(_ARRIVAL_H - _START_H),
        distance_km=16.0, ascent_m=900.0, descent_m=300.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(meta=ForecastMeta(
            provider=Provider.OPENMETEO, model="test",
            run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=UTC),
            grid_res_km=1.0, interp="point_grid",
        ), data=data),
        aggregated=SegmentWeatherSummary(
            temp_min_c=11.0, temp_max_c=21.0, wind_max_kmh=8.0, gust_max_kmh=14.0,
            precip_sum_mm=_ARRIVAL_RAIN_MM, pop_max_pct=30.0,
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=UTC),
        provider="openmeteo",
    )


def _dc() -> UnifiedWeatherDisplayConfig:
    return UnifiedWeatherDisplayConfig(
        trip_id="test",
        metrics=[
            MetricConfig(metric_id="temperature", enabled=True, aggregations=["min", "max"]),
            MetricConfig(metric_id="precipitation", enabled=True, aggregations=["sum"]),
            MetricConfig(metric_id="rain_probability", enabled=True, aggregations=["max"]),
        ],
    )


def test_ac11_rain_in_arrival_hour_is_named_with_its_hour():
    text = CompactSummaryFormatter().format_stage_summary(
        [_segment_rain_only_at_arrival()], "Tag 1: von A nach B", _dc(), tz=_TZ,
    )
    assert "Regen" in text, (
        f"Regen in der Ankunftsstunde wird nicht benannt: {text!r}"
    )
    assert f"Regen ab {_ARRIVAL_H}:00" in text, (
        "Die Ankunftsstunde faellt aus dem Tagesfenster — der Regen wird ohne "
        f"Zeitbezug oder gar nicht genannt: {text!r}"
    )


def test_ac11_dry_stage_still_reads_dry():
    """Gegenprobe: ohne Regen bleibt die Aussage 'trocken' (kein Fehlalarm)."""
    seg = _segment_rain_only_at_arrival()
    dry_data = [_dp(h, 0.0) for h in range(24)]
    dry = SegmentWeatherData(
        segment=seg.segment,
        timeseries=NormalizedTimeseries(meta=seg.timeseries.meta, data=dry_data),
        aggregated=SegmentWeatherSummary(
            temp_min_c=11.0, temp_max_c=21.0, wind_max_kmh=8.0, gust_max_kmh=14.0,
            precip_sum_mm=0.0, pop_max_pct=10.0, thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=seg.fetched_at, provider="openmeteo",
    )
    text = CompactSummaryFormatter().format_stage_summary(
        [dry], "Tag 1: von A nach B", _dc(), tz=_TZ,
    )
    assert "trocken" in text.lower(), f"Trockene Etappe nicht als trocken benannt: {text!r}"
    assert "Regen ab" not in text, f"Regen ohne Regendaten gemeldet: {text!r}"
