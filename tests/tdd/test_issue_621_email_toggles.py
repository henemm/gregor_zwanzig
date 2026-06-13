"""
TDD RED — Issue #621: Mail-Elemente abschaltbar (Konfig-Felder + Render-Gating).

Additive Schalter auf TripReportConfig + Gating im HTML-/Plain-Renderer:
- show_stage_stats        — Etappen-Kennzahlen-Raster
- show_quick_take_tags    — Quick-Take-Chips (nur HTML)
- show_stability          — Großwetterlage-Label
- show_highlights         — Zusammenfassung
- daily_summary_metrics   — Tages-Summe-Auswahl (precipitation/wind/visibility/thunder/temperature)

Mock-frei: echte render_html()/render_plain()/loader-Aufrufe mit echten Datenobjekten.
Spec: docs/specs/modules/email_toggles_621.md
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

TZ = ZoneInfo("Europe/Berlin")


# ---------------------------------------------------------------------------
# Fixtures — Segmente mit bekannten Stundenwerten
# ---------------------------------------------------------------------------

def _build_segments(temps=None):
    """Zwei Segmente mit bekannten Werten.

    Regen-Summe = 0+1+2 + 3+0+0          = 6.0 mm
    Max Böe     = max(10,20,30, 40,15,15) = 40 km/h
    Min Sicht   = min(2000,1500,1200, 3000,2500,1800) = 1200 m = 1.2 km
    Gewitter    = überall NONE
    Temp        = aus `temps` (Default 12.0 konstant)
    """
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    def _dp(h, precip, gust, vis, temp):
        return ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=float(temp), wind10m_kmh=gust * 0.5, gust_kmh=float(gust),
            precip_1h_mm=float(precip), pop_pct=int(min(precip * 20, 100)),
            cloud_total_pct=60, thunder_level=ThunderLevel.NONE,
            visibility_m=vis, freezing_level_m=2500,
        )

    def _make_seg(seg_id, start_km, end_km, start_h, end_h, rows):
        seg = TripSegment(
            segment_id=seg_id,
            start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0,
                                 distance_from_start_km=start_km),
            end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0,
                               distance_from_start_km=end_km),
            start_time=datetime(2026, 7, 11, start_h, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 11, end_h, 0, tzinfo=timezone.utc),
            duration_hours=float(end_h - start_h),
            distance_km=round(end_km - start_km, 1),
            ascent_m=800.0, descent_m=0.0,
        )
        meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo",
                            grid_res_km=1.3,
                            run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc))
        ts = NormalizedTimeseries(meta=meta, data=rows)
        agg = SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=14.0, temp_avg_c=12.0,
            wind_max_kmh=20.0, gust_max_kmh=40.0,
            precip_sum_mm=6.0, cloud_avg_pct=60, humidity_avg_pct=55,
            thunder_level_max=ThunderLevel.NONE,
        )
        return SegmentWeatherData(segment=seg, timeseries=ts, aggregated=agg,
                                  fetched_at=datetime.now(timezone.utc),
                                  provider="demo")

    t = temps or [12.0] * 6
    seg1_rows = [_dp(6, 0, 10, 2000, t[0]), _dp(7, 1, 20, 1500, t[1]),
                 _dp(8, 2, 30, 1200, t[2])]
    seg2_rows = [_dp(8, 3, 40, 3000, t[3]), _dp(9, 0, 15, 2500, t[4]),
                 _dp(10, 0, 15, 1800, t[5])]
    return [
        _make_seg(1, 0.0, 4.2, 6, 8, seg1_rows),
        _make_seg(2, 4.2, 9.3, 8, 10, seg2_rows),
    ]


_SIMPLE_ROWS = [{
    "time": "06:00", "temp": 12.0, "_wind_dir_deg": None, "_is_day": True,
    "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None,
}]

_STATS = {"distance_km": 9.3, "ascent_m": 1600.0, "descent_m": 0.0,
          "max_elevation_m": 1200}


def _stability():
    from app.models import StabilityResult
    return StabilityResult(label="STABIL", confidence_pct=88)


def _render_html(segs, **kwargs):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html
    params = dict(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name=None, stage_stats=None, multi_day_trend=None,
        compact_summary=None, tz=TZ, friendly_keys=set(),
    )
    params.update(kwargs)
    return render_html(**params)


def _render_plain(segs, **kwargs):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.plain import render_plain
    params = dict(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name=None, stage_stats=None, multi_day_trend=None,
        compact_summary=None, tz=TZ, friendly_keys=set(),
    )
    params.update(kwargs)
    return render_plain(**params)


# ---------------------------------------------------------------------------
# AC-1: show_stage_stats
# ---------------------------------------------------------------------------

class TestAC1StageStatsToggle:

    def test_stats_present_when_on(self):
        html = _render_html(_build_segments(), stage_stats=_STATS,
                            show_stage_stats=True)
        assert "Distanz" in html and "Aufstieg" in html

    def test_stats_absent_when_off_html(self):
        html = _render_html(_build_segments(), stage_stats=_STATS,
                            show_stage_stats=False)
        assert "Distanz" not in html and "Aufstieg" not in html

    def test_stats_absent_when_off_plain(self):
        plain = _render_plain(_build_segments(), stage_stats=_STATS,
                              show_stage_stats=False)
        # Werte-Zeile "9.3 km | ↑1600m | ..." darf nicht erscheinen
        assert "↑1600m" not in plain


# ---------------------------------------------------------------------------
# AC-3: show_stability
# ---------------------------------------------------------------------------

class TestAC3StabilityToggle:

    def test_label_present_when_on_html(self):
        html = _render_html(_build_segments(), stability_result=_stability(),
                            show_stability=True)
        assert "Wetterlage: STABIL" in html

    def test_label_absent_when_off_html(self):
        html = _render_html(_build_segments(), stability_result=_stability(),
                            show_stability=False)
        assert "Wetterlage: STABIL" not in html

    def test_label_absent_when_off_plain(self):
        plain = _render_plain(_build_segments(), stability_result=_stability(),
                              show_stability=False)
        assert "Wetterlage: STABIL" not in plain


# ---------------------------------------------------------------------------
# AC-7: Backward-Compat — Loader-Defaults bei fehlenden Feldern
# ---------------------------------------------------------------------------

class TestAC7LoaderDefaults:

    def _trip_dict(self):
        return {
            "trip": {
                "id": "test-trip",
                "name": "Test Trip",
                "report_config": {
                    "trip_id": "test-trip",
                    "morning_time": "07:00:00",
                    "evening_time": "18:00:00",
                },
                "stages": [{
                    "id": "T1", "name": "Day 1", "date": "2026-07-11",
                    "waypoints": [{
                        "id": "G1", "name": "Start",
                        "lat": 42.0, "lon": 9.0, "elevation_m": 400,
                    }],
                }],
            }
        }

    def test_missing_fields_default_to_all_on(self):
        from app.loader import load_trip_from_dict
        trip = load_trip_from_dict(self._trip_dict())
        rc = trip.report_config
        assert rc.show_stage_stats is True
        assert rc.show_quick_take_tags is True
        assert rc.show_stability is True
        assert rc.show_highlights is True
        assert rc.daily_summary_metrics == [
            "precipitation", "wind", "visibility", "thunder"
        ]

    def test_dataclass_defaults(self):
        from app.models import TripReportConfig
        rc = TripReportConfig(trip_id="x")
        assert rc.show_stage_stats is True
        assert rc.show_quick_take_tags is True
        assert rc.show_stability is True
        assert rc.show_highlights is True
        assert rc.daily_summary_metrics == [
            "precipitation", "wind", "visibility", "thunder"
        ]
