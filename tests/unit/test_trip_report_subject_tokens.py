"""
Validator-Finding CRITICAL (2026-04-27):

TripReportFormatter._generate_subject baut TokenLine ohne Wetter-Tokens —
Subject endet bei `Abend —` statt mit `D{temp} W{wind} G{gust}`.

SPEC: docs/specs/modules/output_subject_filter.md §11
EVIDENCE: mail_712.eml — `[VALIDATOR β2 Test] Tag 1: Pollença → Lluc — Abend —`
"""
from __future__ import annotations

from datetime import datetime, timezone

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


def _segment_weather_with_aggregated(
    *,
    temp_max_c: float = 21.0,
    wind_max_kmh: float = 17.0,
    gust_max_kmh: float = 38.0,
) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=39.71, lon=2.62, elevation_m=400.0),
        end_point=GPXPoint(lat=39.75, lon=2.65, elevation_m=800.0),
        start_time=datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 4, 28, 18, 0, tzinfo=timezone.utc),
        duration_hours=10.0,
        distance_km=12.0,
        ascent_m=400.0,
        descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="arome_france",
        run=datetime(2026, 4, 28, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
        interp="point_grid",
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 4, 28, h, 0, tzinfo=timezone.utc),
            t2m_c=temp_max_c - 1.0,
            wind10m_kmh=wind_max_kmh - 1.0,
            gust_kmh=gust_max_kmh - 1.0,
            precip_1h_mm=0.0,
            cloud_total_pct=20,
            thunder_level=ThunderLevel.NONE,
        )
        for h in range(0, 24)
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)
    agg = SegmentWeatherSummary(
        temp_min_c=10.0,
        temp_max_c=temp_max_c,
        temp_avg_c=15.0,
        wind_max_kmh=wind_max_kmh,
        gust_max_kmh=gust_max_kmh,
        precip_sum_mm=0.0,
        cloud_avg_pct=30,
        humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=agg,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def test_trip_report_subject_includes_dwg_tokens():
    """
    GIVEN: TripReportFormatter mit Segment, das aggregierte temp/wind/gust hat
    WHEN: format_email() wird aufgerufen
    THEN: report.email_subject enthaelt Wetter-Tokens D{temp} W{wind} G{gust}
          (Validator-Finding 2026-04-27 — mail_712.eml endete mit `Abend —`)
    """
    seg = _segment_weather_with_aggregated(
        temp_max_c=21.0, wind_max_kmh=17.0, gust_max_kmh=38.0,
    )
    formatter = TripReportFormatter()
    report = formatter.format_email(
        [seg],
        trip_name="VALIDATOR β2 Test",
        report_type="evening",
        stage_name="Tag 1: Pollença → Lluc",
    )

    subj = report.email_subject

    assert "D21" in subj, f"expected 'D21' in subject, got {subj!r}"
    assert "W17" in subj, f"expected 'W17' in subject, got {subj!r}"
    assert "G38" in subj, f"expected 'G38' in subject, got {subj!r}"
    assert not subj.endswith(" —") and not subj.endswith("— "), (
        f"subject must not end with dangling em-dash, got {subj!r}"
    )
