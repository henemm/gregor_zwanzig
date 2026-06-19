"""
TDD RED — Issue #808: "Sonne 0 min" trotz sonniger Stunden + Abstiegs-Symbol.

Verifies:
- AC-1: build_metrics_summary_pills(["sunshine"], ...) mit sonnigen DNI-Datenpunkten
         liefert eine Pille "Sonne X min" mit X > 0.
- AC-2: build_metrics_summary_pills(["sunshine"], ...) bei vollständiger Bewölkung
         liefert None (Pille fehlt), nicht "Sonne 0 min".
- AC-3: Abstiegssegment (end_elevation < start_elevation) → render_plain zeigt ↓ im Header.
- AC-4: Aufstiegssegment (end_elevation >= start_elevation) → render_plain zeigt ↑ im Header.

Mock-frei: echte ForecastDataPoint/SegmentWeatherData/TripSegment-Objekte.
Spec: docs/specs/modules/issue_808_sonne_0_min.md
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
    Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
    TripSegment,
)

TZ = ZoneInfo("Europe/Berlin")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_segment_data(dps: list, *, start_h: int = 8, end_h: int = 14,
                       s_elev: float = 400.0, e_elev: float = 1200.0) -> SegmentWeatherData:
    """Erstellt ein SegmentWeatherData mit gegebenen ForecastDataPoints."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=s_elev,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=e_elev,
                           distance_from_start_km=10.0),
        start_time=datetime(2026, 6, 14, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 14, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h),
        distance_km=10.0,
        ascent_m=max(0.0, e_elev - s_elev),
        descent_m=max(0.0, s_elev - e_elev),
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 6, 14, 0, 0, tzinfo=timezone.utc),
    )
    ts = NormalizedTimeseries(meta=meta, data=dps)
    agg = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=22.0, temp_avg_c=18.0,
        wind_max_kmh=10.0, gust_max_kmh=15.0,
        precip_sum_mm=0.0, cloud_avg_pct=10, humidity_avg_pct=40,
        thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="demo",
    )


def _sunny_dp(h: int) -> ForecastDataPoint:
    """Sonniger Datenpunkt: DNI = 200 W/m² (über Max-Schwelle → 1.0 h)."""
    return ForecastDataPoint(
        ts=datetime(2026, 6, 14, h, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind10m_kmh=5.0, gust_kmh=8.0,
        precip_1h_mm=0.0, pop_pct=0,
        cloud_total_pct=5, thunder_level=ThunderLevel.NONE,
        visibility_m=15000, freezing_level_m=3500,
        dni_wm2=200.0,
    )


def _cloudy_dp(h: int) -> ForecastDataPoint:
    """Vollständig bewölkter Datenpunkt: kein DNI, 100% Bewölkung."""
    return ForecastDataPoint(
        ts=datetime(2026, 6, 14, h, 0, tzinfo=timezone.utc),
        t2m_c=12.0, wind10m_kmh=15.0, gust_kmh=20.0,
        precip_1h_mm=2.0, pop_pct=80,
        cloud_total_pct=100, thunder_level=ThunderLevel.NONE,
        visibility_m=3000, freezing_level_m=2500,
        dni_wm2=None,
    )


# ---------------------------------------------------------------------------
# AC-1: Sonnige Datenpunkte → Pille > 0 Minuten
# ---------------------------------------------------------------------------

class TestAC1SunshinePillPositiveMinutes:
    """AC-1: build_metrics_summary_pills mit sonnigen DNI-Datenpunkten → X min > 0."""

    def test_sunny_dni_dps_produce_positive_sunshine_pill(self):
        """
        GIVEN: Segment mit 6 Stunden sonniger Datenpunkte (DNI = 200 W/m²)
        WHEN:  build_metrics_summary_pills(["sunshine"], ...) aufgerufen wird
        THEN:  Ergebnis enthält Pille "Sonne X min" mit X > 0

        RED: Aktuell liefert die Funktion immer "Sonne 0 min" weil hasattr(dp, "_sunny_hours")
             auf ForecastDataPoint immer False ist.
        """
        from output.renderers.email.helpers import build_metrics_summary_pills

        dps = [_sunny_dp(h) for h in range(8, 14)]  # 6 Stunden sonnig
        seg_data = _make_segment_data(dps, start_h=8, end_h=14)

        pills = build_metrics_summary_pills([seg_data], ["sunshine"], {}, tz=TZ)

        assert len(pills) == 1, f"Erwarte 1 Pille, war {len(pills)}: {pills}"
        text, _tone = pills[0]
        assert text.startswith("Sonne "), f"Pille soll mit 'Sonne ' beginnen: {text!r}"
        import re
        m = re.search(r"(\d+) min", text)
        assert m, f"Keine Minutenzahl in Pille: {text!r}"
        minutes = int(m.group(1))
        assert minutes > 0, (
            f"RED: 0 Minuten trotz sonniger Datenpunkte — hasattr-Bug nicht gefixt: {text!r}"
        )


# ---------------------------------------------------------------------------
# AC-2: Vollständig bewölkt → Pille fehlt (kein "Sonne 0 min")
# ---------------------------------------------------------------------------

class TestAC2NoSunshinePillWhenCloudy:
    """AC-2: Komplett bewölkte Datenpunkte → Sunshine-Pille wird weggelassen."""

    def test_fully_cloudy_produces_no_sunshine_pill(self):
        """
        GIVEN: Segment mit 6 vollständig bewölkten Datenpunkten (kein DNI, 100% Wolken)
        WHEN:  build_metrics_summary_pills(["sunshine"], ...) aufgerufen wird
        THEN:  Ergebnis enthält KEINE Pille — NICHT "Sonne 0 min"

        RED: Aktuell liefert die Funktion "Sonne 0 min" statt None.
        """
        from output.renderers.email.helpers import build_metrics_summary_pills

        dps = [_cloudy_dp(h) for h in range(8, 14)]
        seg_data = _make_segment_data(dps, start_h=8, end_h=14)

        pills = build_metrics_summary_pills([seg_data], ["sunshine"], {}, tz=TZ)

        assert len(pills) == 0, (
            f"Erwarte keine Pille bei vollständiger Bewölkung, war {pills!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: Abstiegssegment → ↓ im Segment-Header (Plain-Text)
# ---------------------------------------------------------------------------

class TestAC3DescentSegmentShowsDownArrow:
    """AC-3: Abstiegssegment → Segment-Header zeigt ↓ statt ↑."""

    def test_descent_segment_header_shows_down_arrow_in_plain(self):
        """
        GIVEN: Segment mit Start-Höhe 1200m und End-Höhe 750m (Abstieg 450m)
        WHEN:  render_plain() aufgerufen wird
        THEN:  Segment-Header enthält "↓" und kein "↑"

        RED: Aktuell zeigt render_plain immer "↑1200m → 750m" auch für Abstiegssegmente.
        """
        from app.metric_catalog import build_default_display_config
        from output.renderers.email.plain import render_plain

        dps = [_cloudy_dp(h) for h in range(8, 12)]
        seg_data = _make_segment_data(
            dps, start_h=8, end_h=12, s_elev=1200.0, e_elev=750.0
        )

        _SIMPLE_ROWS = [{
            "time": "08:00", "temp": 15.0, "_wind_dir_deg": None, "_is_day": True,
            "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None,
        }]

        text = render_plain(
            segments=[seg_data], seg_tables=[_SIMPLE_ROWS],
            trip_name="Test-Tour", report_type="morning",
            dc=build_default_display_config(), night_rows=[],
            thunder_forecast=None, changes=None,
            stage_name=None, stage_stats=None, multi_day_trend=None,
            compact_summary=None, tz=TZ, friendly_keys=set(),
        )

        header_line = next(
            (l for l in text.splitlines() if "Segment 1:" in l and "km" in l), ""
        )
        assert "↓" in header_line, (
            f"RED: '↓' nicht in Abstiegs-Segment-Header: {header_line!r}"
        )
        assert "↑" not in header_line, (
            f"RED: '↑' soll nicht im Abstiegs-Header stehen: {header_line!r}"
        )


# ---------------------------------------------------------------------------
# AC-4: Aufstiegssegment → ↑ im Segment-Header (Plain-Text)
# ---------------------------------------------------------------------------

class TestAC4AscentSegmentShowsUpArrow:
    """AC-4: Aufstiegssegment → Segment-Header zeigt ↑ (unverändertes Verhalten)."""

    def test_ascent_segment_header_shows_up_arrow_in_plain(self):
        """
        GIVEN: Segment mit Start-Höhe 400m und End-Höhe 1200m (Aufstieg 800m)
        WHEN:  render_plain() aufgerufen wird
        THEN:  Segment-Header enthält "↑"
        """
        from app.metric_catalog import build_default_display_config
        from output.renderers.email.plain import render_plain

        dps = [_sunny_dp(h) for h in range(8, 12)]
        seg_data = _make_segment_data(
            dps, start_h=8, end_h=12, s_elev=400.0, e_elev=1200.0
        )

        _SIMPLE_ROWS = [{
            "time": "08:00", "temp": 18.0, "_wind_dir_deg": None, "_is_day": True,
            "_dni_wm2": 200.0, "_sunny_hours": 1.0, "_wmo_code": None,
        }]

        text = render_plain(
            segments=[seg_data], seg_tables=[_SIMPLE_ROWS],
            trip_name="Test-Tour", report_type="morning",
            dc=build_default_display_config(), night_rows=[],
            thunder_forecast=None, changes=None,
            stage_name=None, stage_stats=None, multi_day_trend=None,
            compact_summary=None, tz=TZ, friendly_keys=set(),
        )

        header_line = next(
            (l for l in text.splitlines() if "Segment 1:" in l and "km" in l), ""
        )
        assert "↑" in header_line, (
            f"Aufstiegssegment soll '↑' im Header zeigen: {header_line!r}"
        )
