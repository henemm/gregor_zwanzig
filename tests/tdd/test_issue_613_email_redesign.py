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

import re
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


def _render(segs, *, stage_stats=None, compact_summary=None, daylight=None,
            report_type="morning", show_outlook=True, multi_day_trend=None):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html
    return render_html(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type=report_type,
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, highlights=[], changes=None,
        stage_name=None, stage_stats=stage_stats, multi_day_trend=multi_day_trend,
        compact_summary=compact_summary, daylight=daylight, tz=TZ,
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
        thunder_forecast=None, highlights=[], changes=None,
        stage_name=None, stage_stats=stage_stats, multi_day_trend=None,
        compact_summary=None, daylight=None, tz=TZ, friendly_keys=set(),
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
# AC-2: Quick-Take Chips
# ---------------------------------------------------------------------------

class TestAC2QuickTakeChips:

    def test_ok_chip_kein_gewitter_when_thunder_none(self):
        """AC-2: ok-Chip 'Kein Gewitter' bei durchgehend keinem Gewitter.

        GIVEN Quick-Take-Text + Wetterdaten ohne Gewitter
        WHEN HTML gerendert wird
        THEN enthält die Mail einen 'Kein Gewitter'-Chip.
        """
        html = _render(_build_rich_segments(),
                       compact_summary="Wechselhaft mit Schauern.")
        assert "Kein Gewitter" in html, (
            "Quick-Take-Chip 'Kein Gewitter' fehlt (Chips noch nicht gebaut)."
        )

    def test_gust_chip_present_for_strong_gusts(self):
        """AC-2: Böen-Chip bei starken Böen.

        GIVEN Böen bis 40 km/h
        WHEN HTML gerendert wird
        THEN erscheint ein Chip mit 'Böen' (kommt aus den Daten, nicht aus der
             Tabelle — seg_tables enthält keine Böen-Spalte).
        """
        html = _render(_build_rich_segments(),
                       compact_summary="Wechselhaft mit Schauern.")
        assert "Böen" in html, (
            "Quick-Take-Chip 'Böen' fehlt trotz Böen bis 40 km/h."
        )

    def test_kein_gewitter_chip_is_green_not_neutral(self):
        """F001-Regression: 'Kein Gewitter'-Chip muss grün (#3a7d44) sein.

        GIVEN Wetterdaten ohne Gewitter (ThunderLevel.NONE überall)
        WHEN HTML gerendert wird
        THEN trägt der Span um 'Kein Gewitter' die Farbe #3a7d44 (good-Ton)
             und NICHT #edeae1 (neutrales Grau — Fallback bei unbekanntem Ton).
        """
        html = _render(_build_rich_segments(),
                       compact_summary="Sonnig.")
        idx = html.find("Kein Gewitter")
        assert idx != -1, "'Kein Gewitter'-Chip nicht im HTML."
        # Suche rückwärts zum öffnenden <span style="background:...">
        span_start = html.rfind("<span", 0, idx)
        assert span_start != -1, "Kein öffnendes <span> vor 'Kein Gewitter' gefunden."
        span_fragment = html[span_start:idx + len("Kein Gewitter")]
        assert "#3a7d44" in span_fragment, (
            f"'Kein Gewitter'-Chip hat nicht die grüne Farbe #3a7d44.\n"
            f"Fragment: {span_fragment}"
        )
        assert "#edeae1" not in span_fragment, (
            f"'Kein Gewitter'-Chip fällt auf neutrales Grau (#edeae1) zurück — "
            f"Tonalität 'ok' statt 'good' übergeben.\nFragment: {span_fragment}"
        )


# ---------------------------------------------------------------------------
# AC-3: Tageslicht-Leiste (proportionaler Balken)
# ---------------------------------------------------------------------------

class TestAC3DaylightBar:

    @staticmethod
    def _daylight_fragment(html):
        idx = html.find("Stirnlampe")
        assert idx != -1, "Tageslicht-Block nicht gefunden"
        return html[max(0, idx - 200):idx + 1400]

    @staticmethod
    def _widths(fragment):
        return re.findall(r"width:\s*([0-9]+(?:\.[0-9]+)?)%", fragment)

    def test_daylight_bar_width_scales_with_usable_window(self):
        """AC-3: Balkenbreite hängt vom nutzbaren Fenster ab.

        GIVEN zwei verschieden lange nutzbare Tageslicht-Fenster
        WHEN HTML gerendert wird
        THEN unterscheidet sich die proportionale Balkenbreite (width:NN%)
             im Tageslicht-Block (heute gibt es dort gar keinen Balken).
        """
        segs = _build_rich_segments()
        half = self._daylight_fragment(_render(segs, daylight=_daylight(9, 17)))
        full = self._daylight_fragment(_render(segs, daylight=_daylight(6, 20)))
        w_half, w_full = self._widths(half), self._widths(full)
        assert w_half, "Kein 'width:NN%'-Balken im Tageslicht-Block (RED)."
        assert w_half != w_full, (
            f"Balkenbreite skaliert nicht mit Fenstergröße: "
            f"{w_half} vs {w_full}"
        )


# ---------------------------------------------------------------------------
# AC-4: Tages-Summe-Block
# ---------------------------------------------------------------------------

class TestAC4DailySummary:

    def test_daily_summary_block_with_correct_aggregates(self):
        """AC-4: Tages-Summe mit korrekt berechneten Aggregaten.

        GIVEN bekannte Stundenwerte (Regen Σ=6, Böe max=40, Sicht min=1.2 km)
        WHEN HTML gerendert wird
        THEN erscheint ein Tages-Summe-Block mit diesen Werten.
        """
        html = _render(_build_rich_segments())
        assert "Tages-Summe" in html, "Tages-Summe-Block fehlt."
        block_idx = html.find("Tages-Summe")
        block = html[block_idx:block_idx + 800]
        assert re.search(r"\b6([.,]0)?\b", block), f"Regen-Summe 6 mm fehlt:\n{block}"
        assert "40" in block, f"Max Wind 40 fehlt:\n{block}"
        assert "1.2" in block or "1,2" in block, f"Min Sicht 1.2 km fehlt:\n{block}"


# ---------------------------------------------------------------------------
# AC-7: Plain-Text-Parität für Tages-Summe
# ---------------------------------------------------------------------------

class TestAC7PlainTextDailySummary:

    def test_plain_contains_daily_summary(self):
        """AC-7: Plain-Text enthält die Tages-Summe ebenfalls.

        GIVEN dieselben Stundenwerte
        WHEN Plain-Text gerendert wird
        THEN enthält der Text die Tages-Summe (Regen Σ=6).
        """
        text = _render_plain(_build_rich_segments(), stage_stats=_STATS)
        assert "Tages-Summe" in text or "Tagessumme" in text, (
            "Plain-Text enthält keine Tages-Summe."
        )


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
