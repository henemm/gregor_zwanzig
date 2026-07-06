"""
TDD RED — Issue #613: E-Mail-Briefing visuelles Redesign.

Setzt den Claude-Design-Handoff "Gregor 20 — Mail Vorschau" (EmailPreview) um:
- Etappen-Kennzahlen als Raster (Distanz/Aufstieg/Abstieg/Max-Höhe/Segmente)
- Quick-Take farbige Chips (warn/ok/info)
- Tageslicht-Block mit visueller proportionaler Leiste
- neuer Tages-Summe-Block (Regen Σ · Max Wind · Min Sicht · Gewitter)
- km-Bereich im Segment-Kopf bleibt erhalten (Regressionsschutz)

Mock-frei: echte render_html()/render_plain()-Aufrufe mit echten Datenobjekten.
Spec: docs/specs/modules/email_redesign_613.md
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
# Fixtures — zwei Segmente mit reichhaltigen Stundenwerten
# ---------------------------------------------------------------------------

def _build_rich_segments():
    """Zwei Segmente mit bekannten Werten für Aggregat-Prüfungen.

    Regen-Summe = 0+1+2 + 3+0+0          = 6.0 mm
    Max Böe     = max(10,20,30, 40,15,15) = 40 km/h
    Min Sicht   = min(2000,1500,1200, 3000,2500,1800) = 1200 m = 1.2 km
    Gewitter    = überall NONE
    """
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    def _dp(h, precip, gust, vis):
        return ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=12.0, wind10m_kmh=gust * 0.5, gust_kmh=float(gust),
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

    seg1_rows = [_dp(6, 0, 10, 2000), _dp(7, 1, 20, 1500), _dp(8, 2, 30, 1200)]
    seg2_rows = [_dp(8, 3, 40, 3000), _dp(9, 0, 15, 2500), _dp(10, 0, 15, 1800)]
    return [
        _make_seg(1, 0.0, 4.2, 6, 8, seg1_rows),
        _make_seg(2, 4.2, 9.3, 8, 10, seg2_rows),
    ]


_SIMPLE_ROWS = [{
    "time": "06:00", "temp": 12.0, "_wind_dir_deg": None, "_is_day": True,
    "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None,
}]


def _daylight(usable_start_h, usable_end_h):
    """DaylightWindow mit civil 05:00–21:00 und variablem nutzbarem Fenster."""
    from services.daylight_service import DaylightWindow
    us = datetime(2026, 7, 11, usable_start_h, 0, tzinfo=timezone.utc)
    ue = datetime(2026, 7, 11, usable_end_h, 0, tzinfo=timezone.utc)
    return DaylightWindow(
        civil_dawn=datetime(2026, 7, 11, 5, 0, tzinfo=timezone.utc),
        civil_dusk=datetime(2026, 7, 11, 21, 0, tzinfo=timezone.utc),
        sunrise=datetime(2026, 7, 11, 5, 30, tzinfo=timezone.utc),
        sunset=datetime(2026, 7, 11, 20, 30, tzinfo=timezone.utc),
        usable_start=us, usable_end=ue,
        duration_minutes=int((ue - us).total_seconds() // 60),
    )


def _render(segs, *, stage_stats=None, compact_summary=None,
            report_type="morning", show_outlook=True, multi_day_trend=None):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html
    return render_html(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type=report_type,
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name=None, stage_stats=stage_stats, multi_day_trend=multi_day_trend,
        compact_summary=compact_summary, tz=TZ,
        friendly_keys=set(), show_outlook=show_outlook,
    )


def _minimal_trend():
    """Minimal multi_day_trend for outlook-block rendering."""
    from datetime import date
    return [{"weekday": "Mi", "date": date(2026, 7, 12),
             "stage_name": "Nächste Etappe", "summary": "12–18°C, trocken"}]


def _render_plain(segs, *, stage_stats=None):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.plain import render_plain
    return render_plain(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name=None, stage_stats=stage_stats, multi_day_trend=None,
        compact_summary=None, tz=TZ, friendly_keys=set(),
    )


_STATS = {"distance_km": 9.3, "ascent_m": 1600.0, "descent_m": 0.0,
          "max_elevation_m": 1200}


# ---------------------------------------------------------------------------
# AC-1: Etappen-Kennzahlen-Raster (mit Labels statt nur Werten)
# ---------------------------------------------------------------------------

class TestAC1StageStatsGrid:

    def test_grid_shows_named_metric_labels(self):
        """AC-1: Kennzahlen-Raster mit benannten Labels.

        GIVEN Etappen-Stats (Distanz/Aufstieg/Abstieg/Max-Höhe)
        WHEN HTML gerendert wird
        THEN erscheinen die Labels 'Distanz', 'Aufstieg', 'Abstieg', 'Max'
             als Rasterzellen (heute nur eine Werte-Textzeile ohne Labels).
        """
        html = _render(_build_rich_segments(), stage_stats=_STATS)
        for label in ("Distanz", "Aufstieg", "Abstieg"):
            assert label in html, (
                f"Kennzahlen-Raster-Label '{label}' fehlt — Header zeigt noch "
                f"die alte Werte-Textzeile."
            )


# ---------------------------------------------------------------------------
# Issue #790: Quick-Take-Chips, Tageslicht-Block und Tages-Summe wurden
# vollständig aus dem Render-Code entfernt (Negativ-Regression).
# ---------------------------------------------------------------------------

class TestIssue790RemovedBlocks:

    def test_no_quick_take_chip(self):
        html = _render(_build_rich_segments(),
                       compact_summary="Wechselhaft mit Schauern.")
        assert "Kein Gewitter" not in html

    def test_no_daylight_block(self):
        html = _render(_build_rich_segments())
        assert "Stirnlampe" not in html

    def test_no_daily_summary_block_html(self):
        html = _render(_build_rich_segments())
        assert "Tages-Summe" not in html

    def test_no_daily_summary_block_plain(self):
        text = _render_plain(_build_rich_segments(), stage_stats=_STATS)
        assert "Tages-Summe" not in text and "Tagessumme" not in text


# ---------------------------------------------------------------------------
# AC-5 (Regressionsschutz): km-Bereich bleibt im Segment-Kopf
# ---------------------------------------------------------------------------

class TestAC5KmRangePreserved:

    def test_km_range_still_in_header(self):
        """AC-5: km-Bereich bleibt erhalten (kein Rückfall auf einzelne km).

        GIVEN Segment km 0.0–4.2
        WHEN HTML und Plain gerendert werden
        THEN enthält der Segment-Kopf weiterhin 'km 0.0–4.2'.
        """
        segs = _build_rich_segments()
        assert "km 0.0–4.2" in _render(segs)
        assert "km 0.0–4.2" in _render_plain(segs)


# ---------------------------------------------------------------------------
# AC-6 (Issue #723): show_outlook steuert Ausblick-Block im Renderer
# ---------------------------------------------------------------------------

class TestAC6SectionsPreserved:

    def test_show_outlook_true_renders_outlook_block(self):
        """AC-6a: show_outlook=True → Ausblick-Block vorhanden.

        GIVEN Renderer wird mit show_outlook=True und multi_day_trend aufgerufen
        WHEN HTML gerendert wird
        THEN enthält die Mail das Ausblick-Section-Label (Issue #721).
        """
        html = _render(_build_rich_segments(), show_outlook=True,
                       multi_day_trend=_minimal_trend())
        assert "Ausblick" in html, (
            "Ausblick-Block fehlt bei show_outlook=True."
        )

    def test_show_outlook_false_suppresses_outlook_block(self):
        """AC-6b: show_outlook=False → Ausblick-Block unterdrückt.

        GIVEN Renderer wird mit show_outlook=False und multi_day_trend aufgerufen
        WHEN HTML gerendert wird
        THEN fehlt das Ausblick-Section-Label im HTML.
        """
        html = _render(_build_rich_segments(), show_outlook=False,
                       multi_day_trend=_minimal_trend())
        assert "Ausblick" not in html, (
            "Ausblick-Block sollte bei show_outlook=False unterdrückt sein."
        )
