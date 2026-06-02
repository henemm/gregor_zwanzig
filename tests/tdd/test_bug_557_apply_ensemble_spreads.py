"""
TDD RED Tests fuer Bug #557 — _apply_ensemble_spreads() als testbare reine Methode.

Spec: docs/specs/modules/bug_557_confidence_pct_min.md

Diese Tests MUESSEN im RED-Phase fehlschlagen weil:
- TripReportSchedulerService._apply_ensemble_spreads() existiert noch nicht

KEINE MOCKS — echte Dataclasses, echte compute_confidence_pct(), kein Mock()/patch().
"""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Dict, Optional, Tuple

import pytest


# ---------------------------------------------------------------------------
# Helpers (identisch zu test_bug_288_ensemble_api_limit.py)
# ---------------------------------------------------------------------------

def _make_waypoint(id_: str = "wp-1", lat: float = 47.27, lon: float = 11.39):
    from app.trip import Waypoint
    return Waypoint(id=id_, name=f"Punkt {id_}", lat=lat, lon=lon, elevation_m=800)


def _make_stage(stage_id: str = "s-1", waypoints=None):
    from app.trip import Stage
    if waypoints is None:
        waypoints = [_make_waypoint("wp-1"), _make_waypoint("wp-2")]
    return Stage(id=stage_id, name=f"Etappe {stage_id}",
                 date=date(2026, 6, 15), waypoints=waypoints)


def _make_segment(lat: float = 47.27, lon: float = 11.39):
    from app.models import GPXPoint, TripSegment
    # Segment 06:00–14:00 UTC, identisch zu test_bug_288
    base = datetime.now(timezone.utc).replace(hour=6, minute=0, second=0, microsecond=0)
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=800),
        end_point=GPXPoint(lat=lat + 0.05, lon=lon + 0.05, elevation_m=1200),
        start_time=base,
        end_time=base + timedelta(hours=8),
        duration_hours=8.0,
        distance_km=12.0,
        ascent_m=500,
        descent_m=100,
    )


def _make_scheduler():
    from services.trip_report_scheduler import TripReportSchedulerService
    svc = TripReportSchedulerService.__new__(TripReportSchedulerService)
    svc._user_id = "default"
    return svc


def _spreads_for_segment(segment, spread_t: float = 1.5, spread_p: float = 0.8) -> Dict:
    """Erzeugt naive-datetime-Spread-Dict mit einem Eintrag mitten im Segment-Zeitfenster."""
    mid = segment.start_time + timedelta(hours=4)  # 10:00 UTC
    mid_naive = mid.replace(tzinfo=None)
    return {mid_naive: (spread_t, spread_p)}


# ---------------------------------------------------------------------------
# AC-1: confidence_pct_min wird gesetzt wenn timeseries=None und Spreads vorhanden
# ---------------------------------------------------------------------------

def test_ac1_apply_ensemble_spreads_sets_confidence_when_timeseries_none():
    """
    AC-1: _apply_ensemble_spreads() setzt confidence_pct_min wenn timeseries=None
    und Spreads das Segment-Zeitfenster abdecken.

    GIVEN: SegmentWeatherData mit timeseries=None; Spreads mit Eintrag im Segment-Fenster
    WHEN:  svc._apply_ensemble_spreads(weather_data, spreads_naive, now_utc) aufgerufen
    THEN:  weather_item.aggregated.confidence_pct_min ist nicht None

    RED: AttributeError — _apply_ensemble_spreads() existiert noch nicht
    """
    from app.models import SegmentWeatherData, SegmentWeatherSummary

    segment = _make_segment()
    summary = SegmentWeatherSummary()
    assert summary.confidence_pct_min is None

    weather_item = SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
        has_error=False,
    )

    spreads_naive = _spreads_for_segment(segment)
    now_utc = datetime.now(timezone.utc)

    svc = _make_scheduler()
    svc._apply_ensemble_spreads([weather_item], spreads_naive, now_utc)

    assert weather_item.aggregated.confidence_pct_min is not None, (
        "confidence_pct_min sollte nach _apply_ensemble_spreads() gesetzt sein, ist aber None"
    )


def test_ac1_apply_ensemble_spreads_exact_value_matches_compute_confidence():
    """
    AC-1 (Wert): confidence_pct_min entspricht compute_confidence_pct() fuer den Spread-Eintrag.

    GIVEN: Ein Spread-Eintrag (s_t=1.5, s_p=0.8) mitten im Segment-Fenster
    WHEN:  _apply_ensemble_spreads aufgerufen
    THEN:  confidence_pct_min == compute_confidence_pct(1.5, 0.8, lead_h)

    RED: AttributeError — _apply_ensemble_spreads() existiert noch nicht
    """
    from app.models import SegmentWeatherData, SegmentWeatherSummary
    from providers.openmeteo import compute_confidence_pct

    segment = _make_segment()
    s_t, s_p = 1.5, 0.8
    spreads_naive = _spreads_for_segment(segment, spread_t=s_t, spread_p=s_p)
    now_utc = datetime.now(timezone.utc)

    # Erwarteten Wert vorausberechnen (pure function)
    mid_naive = list(spreads_naive.keys())[0]
    mid_utc = mid_naive.replace(tzinfo=timezone.utc)
    lead_h = max(0.0, (mid_utc - now_utc).total_seconds() / 3600.0)
    expected = compute_confidence_pct(s_t, s_p, lead_h)

    summary = SegmentWeatherSummary()
    weather_item = SegmentWeatherData(
        segment=segment, timeseries=None, aggregated=summary,
        fetched_at=now_utc, provider="openmeteo", has_error=False,
    )

    svc = _make_scheduler()
    svc._apply_ensemble_spreads([weather_item], spreads_naive, now_utc)

    assert weather_item.aggregated.confidence_pct_min == expected, (
        f"Erwartet confidence_pct_min={expected}, "
        f"erhalten={weather_item.aggregated.confidence_pct_min}"
    )


# ---------------------------------------------------------------------------
# AC-2: confidence_pct_min = Minimum ueber alle DataPoints wenn timeseries vorhanden
# ---------------------------------------------------------------------------

def test_ac2_apply_ensemble_spreads_uses_minimum_across_datapoints():
    """
    AC-2: Wenn timeseries vorhanden und DataPoints Confidence-Werte erhalten,
    ist confidence_pct_min das Minimum ueber alle DataPoints.

    GIVEN: timeseries mit 2 DataPoints; Spreads treffen beide Zeitstempel
    WHEN:  _apply_ensemble_spreads aufgerufen
    THEN:  confidence_pct_min == min(confidence_pct beider DataPoints)

    RED: AttributeError — _apply_ensemble_spreads() existiert noch nicht
    """
    from app.models import (
        ForecastDataPoint, ForecastMeta, NormalizedTimeseries,
        SegmentWeatherData, SegmentWeatherSummary,
    )
    from providers.openmeteo import compute_confidence_pct

    segment = _make_segment()
    now_utc = datetime.now(timezone.utc)

    # Zwei Zeitpunkte im Segment-Fenster (06:00 + 4h = 10:00, + 6h = 12:00)
    ts1 = segment.start_time + timedelta(hours=4)
    ts2 = segment.start_time + timedelta(hours=6)

    dp1 = ForecastDataPoint(ts=ts1)
    dp2 = ForecastDataPoint(ts=ts2)

    meta = ForecastMeta(
        provider="openmeteo",
        model="best_match",
        grid_res_km=1.0,
    )
    timeseries = NormalizedTimeseries(data=[dp1, dp2], meta=meta)

    summary = SegmentWeatherSummary()
    weather_item = SegmentWeatherData(
        segment=segment, timeseries=timeseries, aggregated=summary,
        fetched_at=now_utc, provider="openmeteo", has_error=False,
    )

    # Spreads fuer beide Zeitstempel (hoeherer Spread = niedrigere Konfidenz)
    ts1_naive = ts1.replace(tzinfo=None)
    ts2_naive = ts2.replace(tzinfo=None)
    spreads_naive = {
        ts1_naive: (1.0, 0.5),   # moderate spread
        ts2_naive: (3.0, 2.0),   # higher spread -> niedrigere Konfidenz
    }

    svc = _make_scheduler()
    svc._apply_ensemble_spreads([weather_item], spreads_naive, now_utc)

    lead1 = max(0.0, (ts1 - now_utc).total_seconds() / 3600.0)
    lead2 = max(0.0, (ts2 - now_utc).total_seconds() / 3600.0)
    conf1 = compute_confidence_pct(1.0, 0.5, lead1)
    conf2 = compute_confidence_pct(3.0, 2.0, lead2)
    expected_min = min(conf1, conf2)

    assert weather_item.aggregated.confidence_pct_min == expected_min, (
        f"Erwartet confidence_pct_min={expected_min} (min von {conf1}, {conf2}), "
        f"erhalten={weather_item.aggregated.confidence_pct_min}"
    )


# ---------------------------------------------------------------------------
# AC-3: test_ac3 aus Bug-#288 laeuft nach Refaktor ohne xfail
# Vorgeschmack: gleicher Test-Inhalt wie test_ac3, aber via _apply_ensemble_spreads
# ---------------------------------------------------------------------------

def test_ac3_former_xfail_now_passes_via_apply_ensemble_spreads():
    """
    AC-3: Der vorherige xfail-Test (AC-3 aus Bug #288) laeuft gruen
    wenn er _apply_ensemble_spreads() statt _enrich_ensemble_for_trip() aufruft.

    GIVEN: Trip + SegmentWeatherData mit timeseries=None (identisch zum frueheren xfail)
    WHEN:  svc._apply_ensemble_spreads(weather_data, spreads_naive, now_utc)
    THEN:  confidence_pct_min ist nicht None

    RED: AttributeError — _apply_ensemble_spreads() existiert noch nicht
    """
    from app.models import SegmentWeatherData, SegmentWeatherSummary

    segment = _make_segment(lat=47.20, lon=9.30)
    summary = SegmentWeatherSummary()
    assert summary.confidence_pct_min is None

    weather_item = SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
        has_error=False,
    )

    spreads_naive = _spreads_for_segment(segment)
    now_utc = datetime.now(timezone.utc)

    svc = _make_scheduler()
    svc._apply_ensemble_spreads([weather_item], spreads_naive, now_utc)

    assert weather_item.aggregated.confidence_pct_min is not None, (
        "confidence_pct_min sollte nach _apply_ensemble_spreads() gesetzt sein, ist aber None"
    )


# ---------------------------------------------------------------------------
# AC-4: Spreads ausserhalb des Segment-Fensters werden ignoriert
# ---------------------------------------------------------------------------

def test_ac4_spreads_outside_segment_window_are_ignored():
    """
    AC-4: Spreads, die ausserhalb des Segment-Zeitfensters liegen,
    werden nicht fuer confidence_pct_min herangezogen.

    GIVEN: Spreads NUR ausserhalb des Segment-Fensters (1h vor Start, 1h nach Ende)
    WHEN:  _apply_ensemble_spreads aufgerufen
    THEN:  confidence_pct_min bleibt None (keine passenden Spreads)

    RED: AttributeError — _apply_ensemble_spreads() existiert noch nicht
    """
    from app.models import SegmentWeatherData, SegmentWeatherSummary

    segment = _make_segment()
    summary = SegmentWeatherSummary()

    weather_item = SegmentWeatherData(
        segment=segment, timeseries=None, aggregated=summary,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo", has_error=False,
    )

    # Spreads 1h vor Segment-Start und 1h nach Segment-Ende
    before = (segment.start_time - timedelta(hours=1)).replace(tzinfo=None)
    after = (segment.end_time + timedelta(hours=1)).replace(tzinfo=None)
    spreads_naive = {
        before: (1.0, 0.5),
        after: (1.0, 0.5),
    }
    now_utc = datetime.now(timezone.utc)

    svc = _make_scheduler()
    svc._apply_ensemble_spreads([weather_item], spreads_naive, now_utc)

    assert weather_item.aggregated.confidence_pct_min is None, (
        "confidence_pct_min sollte None bleiben wenn keine Spreads ins Fenster fallen, "
        f"ist aber: {weather_item.aggregated.confidence_pct_min}"
    )
