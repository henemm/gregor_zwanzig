"""
Plain-Text-Goldens für E-Mail-Renderer-Migration (β3 — TDD RED Phase).

SPEC: docs/specs/modules/output_channel_renderers.md §A7 (Pflicht-Gate)
TESTS-SPEC: docs/specs/tests/output_channel_renderers_tests.md
EPIC: render-pipeline-consolidation (#96), Phase β3

A7-Verträge:
  * 5 Plain-Text-Goldens, eingefroren vor erstem Umzug-Commit.
  * Bit-Vergleich vor und nach Renderer-Migration.
  * Datei-Pfad: tests/golden/email/{profil}-plain.txt.

RED-Zustand (jetzt):
  Goldens existieren noch NICHT → pytest.fail.

GREEN-Zustand (nach β3-Implementation):
  Developer friert die 5 Goldens aus dem heutigen TripReportFormatter-Output ein
  vor jedem Render-Umzug, migriert dann das Modul, und der Bit-Vergleich bleibt
  identisch.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from formatters.trip_report import TripReportFormatter

GOLDEN_DIR = Path(__file__).parent


def _read_golden(stem: str) -> str:
    """Read frozen plain-text golden. RED if file missing."""
    path = GOLDEN_DIR / f"{stem}-plain.txt"
    if not path.exists():
        pytest.fail(
            f"Plain-Text-Golden fehlt: {path}\n"
            f"Spec §A7 verlangt 5 Goldens vor Migration. "
            f"In Phase 6 (Implement) friert der Developer den heutigen "
            f"format_email().email_plain Output in diese Datei ein."
        )
    return path.read_text(encoding="utf-8")


def _make_dp(hour: int, day: int = 11, **overrides) -> ForecastDataPoint:
    defaults = dict(
        ts=datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0 + hour * 0.3,
        wind10m_kmh=12.0 + hour * 0.5,
        gust_kmh=30.0 + hour * 1.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        wind_chill_c=10.0 + hour * 0.2,
        snowfall_limit_m=None,
        humidity_pct=55,
    )
    defaults.update(overrides)
    return ForecastDataPoint(**defaults)


def _make_timeseries(hours, day: int = 11, **dp_overrides) -> NormalizedTimeseries:
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="arome_france",
        run=datetime(2026, 7, day, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
        interp="point_grid",
    )
    data = [_make_dp(h, day=day, **dp_overrides) for h in hours]
    return NormalizedTimeseries(meta=meta, data=data)


def _make_segment(
    seg_id: int,
    start_hour: int,
    end_hour: int,
    day: int = 11,
    start_elev: float = 400.0,
    end_elev: float = 1200.0,
    lat: float = 42.20,
    lon: float = 9.05,
) -> TripSegment:
    return TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=start_elev),
        end_point=GPXPoint(lat=lat + 0.05, lon=lon + 0.04, elevation_m=end_elev),
        start_time=datetime(2026, 7, day, start_hour, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, day, end_hour, 0, tzinfo=timezone.utc),
        duration_hours=float(end_hour - start_hour),
        distance_km=4.2,
        ascent_m=max(0, end_elev - start_elev),
        descent_m=max(0, start_elev - end_elev),
    )


def _build_seg_weather(
    seg_id: int,
    start_hour: int,
    end_hour: int,
    *,
    day: int = 11,
    temp_min: float = 14.0,
    temp_max: float = 24.0,
    wind_max: float = 25.0,
    gust_max: float = 40.0,
    precip_total: float = 0.0,
    thunder: ThunderLevel = ThunderLevel.NONE,
    snow_new_cm: float | None = None,
    freezing_level_m: int | None = None,
    lat: float = 42.20,
    lon: float = 9.05,
    start_elev: float = 400.0,
    end_elev: float = 1200.0,
) -> SegmentWeatherData:
    seg = _make_segment(
        seg_id, start_hour, end_hour, day=day,
        start_elev=start_elev, end_elev=end_elev, lat=lat, lon=lon,
    )
    ts = _make_timeseries(range(0, 24), day=day, thunder_level=thunder)
    if gust_max > 60:
        ts.data[start_hour].gust_kmh = gust_max
    if precip_total > 0:
        ts.data[start_hour].precip_1h_mm = precip_total
    agg = SegmentWeatherSummary(
        temp_min_c=temp_min,
        temp_max_c=temp_max,
        temp_avg_c=(temp_min + temp_max) / 2,
        wind_max_kmh=wind_max,
        gust_max_kmh=gust_max,
        precip_sum_mm=precip_total,
        cloud_avg_pct=60,
        humidity_avg_pct=55,
        thunder_level_max=thunder,
        wind_chill_min_c=temp_min - 4.0,
        snow_new_sum_cm=snow_new_cm,
        freezing_level_m=freezing_level_m,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=agg,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _assert_plain_matches_golden(stem: str, plain: str) -> None:
    expected = _read_golden(stem)
    assert plain == expected, (
        f"Plain-Body-Drift in {stem}.\n"
        f"Bit-Vergleich gegen tests/golden/email/{stem}-plain.txt fehlgeschlagen.\n"
        f"Spec §A7 verlangt bit-identischen Output vor und nach β3-Migration."
    )


def test_email_plain_golden_gr20_summer_evening():
    """GR20 Sommer Evening: Korsika Sommer-Forecast, 2 Etappen."""
    seg1 = _build_seg_weather(
        1, 9, 12, day=11, temp_min=14.0, temp_max=24.0,
        wind_max=18.0, gust_max=28.0, precip_total=2.5,
    )
    seg2 = _build_seg_weather(
        2, 12, 16, day=11, temp_min=18.0, temp_max=26.0,
        wind_max=22.0, gust_max=35.0, precip_total=0.0,
    )
    formatter = TripReportFormatter()
    report = formatter.format_email(
        [seg1, seg2], "GR20", "evening",
        display_config=build_default_display_config(),
        stage_name="GR20 E3",
    )
    _assert_plain_matches_golden("gr20-summer-evening", report.email_plain)


def test_email_plain_golden_gr20_spring_morning():
    """GR20 Frühjahr Morning: kalt + Niederschlag."""
    seg = _build_seg_weather(
        1, 6, 10, day=11, temp_min=2.0, temp_max=9.0,
        wind_max=35.0, gust_max=70.0, precip_total=18.5,
        thunder=ThunderLevel.MED,
    )
    formatter = TripReportFormatter()
    report = formatter.format_email(
        [seg], "GR20", "morning",
        display_config=build_default_display_config(),
        stage_name="GR20 E1",
    )
    _assert_plain_matches_golden("gr20-spring-morning", report.email_plain)


def test_email_plain_golden_gr221_mallorca_evening():
    """GR221 Mallorca Evening: warm, breezy, kein Regen."""
    seg = _build_seg_weather(
        1, 9, 14, day=11, temp_min=8.0, temp_max=15.0,
        wind_max=25.0, gust_max=55.0, precip_total=0.0,
        lat=39.71, lon=2.62, start_elev=200.0, end_elev=900.0,
    )
    formatter = TripReportFormatter()
    report = formatter.format_email(
        [seg], "GR221 Mallorca", "evening",
        display_config=build_default_display_config(),
        stage_name="GR221 Tag1",
    )
    _assert_plain_matches_golden("gr221-mallorca-evening", report.email_plain)


def test_email_plain_golden_arlberg_winter_morning():
    """Wintersport Arlberg Morning: profile=wintersport, Schnee/Lawine."""
    seg = _build_seg_weather(
        1, 8, 13, day=11,
        temp_min=-12.0, temp_max=-4.0,
        wind_max=45.0, gust_max=110.0,
        precip_total=0.0,
        snow_new_cm=25.0, freezing_level_m=1800,
        lat=47.13, lon=10.20, start_elev=1500.0, end_elev=2300.0,
    )
    formatter = TripReportFormatter()
    report = formatter.format_email(
        [seg], "Arlberg Winter", "morning",
        display_config=build_default_display_config(),
        stage_name="Arlberg",
    )
    _assert_plain_matches_golden("arlberg-winter-morning", report.email_plain)


def test_email_plain_golden_corsica_vigilance():
    """Korsika Vigilance Update: MétéoFrance-Vigilance high + Update-Report."""
    seg = _build_seg_weather(
        1, 10, 15, day=11, temp_min=18.0, temp_max=32.0,
        wind_max=30.0, gust_max=85.0, precip_total=8.0,
        thunder=ThunderLevel.HIGH,
        lat=42.20, lon=9.05,
    )
    formatter = TripReportFormatter()
    report = formatter.format_email(
        [seg], "Korsika Trail", "update",
        display_config=build_default_display_config(),
        stage_name="Corsica E5",
        changes=[],
    )
    _assert_plain_matches_golden("corsica-vigilance", report.email_plain)
