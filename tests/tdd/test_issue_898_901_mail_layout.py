"""
TDD RED — Issues #898/#899/#900/#901: HTML-Briefing-Mail Layout-Bugs.

Tests call render_html() directly with real fixture data and assert on the
rendered HTML output. No mocks, no file-content checks, no patch().

SPEC: docs/specs/modules/issue_898_901_mail_layout.md AC-1..AC-13
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
# Helpers — reused from test_issue_790_briefing_simplify.py pattern
# ---------------------------------------------------------------------------

_SIMPLE_ROWS = [{
    "time": "06:00", "temp": 12.0, "_wind_dir_deg": None, "_is_day": True,
    "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None,
}]


def _build_segments(temps=None, thunder=False):
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    tl = ThunderLevel.MED if thunder else ThunderLevel.NONE

    def _dp(h, precip, gust, vis, temp):
        return ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=float(temp), wind10m_kmh=gust * 0.5, gust_kmh=float(gust),
            precip_1h_mm=float(precip), pop_pct=int(min(precip * 20, 100)),
            cloud_total_pct=60, thunder_level=tl,
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
            thunder_level_max=tl,
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


def _render_html(segs, *, dc=None, **kwargs):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html
    params = dict(
        segments=segs,
        seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test",
        report_type="morning",
        dc=dc or build_default_display_config(),
        night_rows=[],
        thunder_forecast=None,
        changes=None,
        stage_name=None,
        stage_stats=None,
        multi_day_trend=None,
        compact_summary=None,
        tz=TZ,
        friendly_keys=set(),
    )
    params.update(kwargs)
    return render_html(**params)


def _trend_stage(weekday="Mo", name="Etappe X", conf=None):
    """Build a minimal multi_day_trend entry."""
    return {
        "weekday": weekday,
        "name": name,
        "temp_lo": 12,
        "temp_hi": 22,
        "precip_mm": 0.5,
        "wind_dir": "W",
        "wind_kmh": 15,
        "thunder": "NONE",
        "note": None,
        "confidence_pct": conf,
        "hourly_precip": (),
        "hourly_wind": (),
        "hourly_gust": (),
        "hourly_thunder": (),
    }


def _comparison_warmer():
    """Build a DayComparison where today is warmer and drier than yesterday."""
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    from services.day_comparison import DayComparisonService

    def _seg(tid, tmin, tmax, precip):
        seg = TripSegment(
            segment_id=tid,
            start_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1500.0),
            end_point=GPXPoint(lat=42.2, lon=9.2, elevation_m=1600.0),
            start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
            duration_hours=4.0, distance_km=12.0, ascent_m=600.0, descent_m=300.0,
        )
        meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo", grid_res_km=1.0)
        ts = NormalizedTimeseries(meta=meta, data=[])
        return SegmentWeatherData(
            segment=seg, timeseries=ts,
            aggregated=SegmentWeatherSummary(
                temp_min_c=tmin, temp_max_c=tmax,
                wind_max_kmh=20.0, precip_sum_mm=precip,
            ),
            fetched_at=datetime.now(timezone.utc), provider="demo",
        )

    today = [_seg(1, 10.0, 22.0, 0.5)]
    yday = [_seg(1, 4.0, 14.0, 12.0)]
    return DayComparisonService().compare(today, yday)


# ===========================================================================
# AC-1 (#900): Vollständiges Tabellengitter (Zeilen + Spalten + Header-BG)
# ===========================================================================

class TestAC1TableGrid:
    """AC-1: Stundentabelle hat border-right auf Zellen (außer letzter Spalte),
    border-bottom auf Datenzeilen UND Header-Hintergrundfarbe."""

    def _get_hourly_rows(self, html: str) -> list[str]:
        """Return all <tr> elements from the first data table."""
        m = re.search(r'<table[^>]*data-table="resp"[^>]*>(.*?)</table>', html, re.DOTALL)
        if not m:
            return []
        table_html = m.group(1)
        return re.findall(r'<tr>(.*?)</tr>', table_html, re.DOTALL)

    def test_column_borders_on_td(self):
        """Data cells must carry border-right (except last column / risk-dot)."""
        segs = _build_segments()
        html = _render_html(segs, seg_tables=[[
            {
                "time": "06:00", "temp": 12.0, "wind": 10.0, "gust": 15.0,
                "precip": 0.0, "pop": 10, "thunder": 0.0, "vis": 2000.0,
                "risk": "ok",
            }
        ]] * 2)
        # At least some data <td> elements must have border-right
        assert "border-right:" in html, (
            "AC-1: keine border-right in Zellen gefunden — Spaltenlinien fehlen"
        )

    def test_column_borders_on_th(self):
        """Die Kopfzeile (th) muss Spaltenlinien (border-right) tragen.

        Issue #900: Die th-Spaltenlinie läuft über die globale th-Regel im
        gerenderten <style>-Block (nicht inline), damit die <th>-Tags schlank
        bleiben und bestehende Renderer-Tests stabil sind. Die Datenzellen-
        Linien (td) bleiben inline/Outlook-fest (siehe test_column_borders_on_td).
        """
        segs = _build_segments()
        html = _render_html(segs, seg_tables=[[
            {
                "time": "06:00", "temp": 12.0, "wind": 10.0, "gust": 15.0,
                "precip": 0.0, "pop": 10, "thunder": 0.0, "vis": 2000.0,
                "risk": "ok",
            }
        ]] * 2)
        # th-Regel im gerenderten CSS-Block trägt border-right
        assert re.search(r'th \{[^}]*border-right[^}]*\}', html) is not None, (
            "AC-1: th-Regel hat kein border-right — Spalten-Header-Linie fehlt"
        )

    def test_row_borders_on_data_rows(self):
        """Datenzeilen müssen border-bottom inline tragen (für Outlook-Kompatibilität)."""
        segs = _build_segments()
        html = _render_html(segs, seg_tables=[[
            {
                "time": "06:00", "temp": 12.0, "wind": 10.0,
                "precip": 0.0, "pop": 5, "thunder": 0.0,
                "vis": 2000.0, "risk": "ok",
            },
            {
                "time": "07:00", "temp": 13.0, "wind": 12.0,
                "precip": 0.1, "pop": 10, "thunder": 0.0,
                "vis": 2000.0, "risk": "ok",
            },
        ]] * 2)
        # Inline border-bottom on data <td> cells (horizontal grid lines)
        assert re.search(r'<td[^>]*border-bottom[^>]*>', html) is not None, (
            "AC-1: keine inline border-bottom auf Datenzeilen-Zellen — horizontale Linien fehlen"
        )

    def test_header_background_color(self):
        """Die th-Kopfzeile muss einen sichtbaren Hintergrund (Kennzeichnung) haben.

        Issue #900: läuft über die globale th-Regel im gerenderten <style>-Block.
        """
        segs = _build_segments()
        html = _render_html(segs, seg_tables=[[
            {
                "time": "06:00", "temp": 12.0, "wind": 10.0,
                "precip": 0.0, "pop": 5, "thunder": 0.0,
                "vis": 2000.0, "risk": "ok",
            }
        ]] * 2)
        # th-Regel im gerenderten CSS-Block trägt eine Hintergrundfarbe
        assert re.search(r'th \{[^}]*background[^}]*\}', html) is not None, (
            "AC-1: th-Regel hat keinen Hintergrund — Header-Kennzeichnung fehlt"
        )


# ===========================================================================
# AC-2 (#898): Kein Doppel-Einzug im Tageslage-Block
# ===========================================================================

class TestAC2NoDoubleIndent:
    """AC-2: Outer-Div der Tageslage-Sektion hat padding-left < 28px."""

    def _extract_outer_padding_left(self, html: str) -> int:
        """Extract the effective left padding from the outer tageslage div.

        The outer div is the first div that contains the 'TAGESLAGE' eyebrow.
        We look for the padding attribute on the div just before TAGESLAGE.
        """
        tageslage_pos = html.find("TAGESLAGE")
        if tageslage_pos == -1:
            return -1
        # Search backwards for the enclosing outer div opening
        context = html[max(0, tageslage_pos - 600):tageslage_pos + 50]
        # Find all padding declarations in this context area
        # Current: padding:18px 28px 16px (3-part: top right/left bottom → left=28)
        # After fix: padding:18px 28px 16px 12px (4-part, left=12) or padding:18px 28px 16px
        padding_matches = re.findall(r'padding:([^;>"]+)', context)
        for match in reversed(padding_matches):
            parts = match.strip().split()
            if len(parts) == 4:
                # top right bottom left
                try:
                    return int(parts[3].rstrip("px"))
                except ValueError:
                    pass
            elif len(parts) == 3:
                # top right-left bottom → left = right (middle value)
                try:
                    return int(parts[1].rstrip("px"))
                except ValueError:
                    pass
            elif len(parts) == 2:
                # top right-left → left = right
                try:
                    return int(parts[1].rstrip("px"))
                except ValueError:
                    pass
            elif len(parts) == 1:
                try:
                    return int(parts[0].rstrip("px"))
                except ValueError:
                    pass
        return -1

    def test_tageslage_outer_padding_left_below_28px(self):
        """Outer padding-left des Tageslage-Containers muss unter 28px liegen.

        Current bug: outer div has padding:18px 28px 16px → left=28px.
        Combined with inner border-left+padding-left:14px = 42px total indent.
        Fix: outer left padding reduced (e.g. 12px) so 12+2+14=28px total.
        """
        segs = _build_segments()
        html = _render_html(segs, compact_summary="Sonnig und warm.")
        tageslage_pos = html.find("TAGESLAGE")
        assert tageslage_pos != -1, "TAGESLAGE-Block nicht gefunden"

        left_pad = self._extract_outer_padding_left(html)
        assert left_pad != -1, "Kein padding auf Tageslage-Outer-Div gefunden"
        assert left_pad < 28, (
            f"AC-2: Tageslage-Outer-Div hat padding-left={left_pad}px (>= 28px) — "
            f"Doppel-Einzug vorhanden (28 + 14 = 42px total)"
        )


# ===========================================================================
# AC-3 (#898): Gleiche font-size für Summary und Vortagesvergleich
# ===========================================================================

class TestAC3UniformFontSize:
    """AC-3: _summary_div und _vortag_div haben identische font-size."""

    def test_summary_and_vortag_same_font_size(self):
        segs = _build_segments()
        dc = _comparison_warmer()
        html = _render_html(
            segs,
            compact_summary="Wechselhaft mit Schauern.",
            day_comparison=dc,
        )
        # Find font-size values in the tageslage section
        tageslage_pos = html.find("TAGESLAGE")
        assert tageslage_pos != -1, "TAGESLAGE-Block nicht gefunden"

        # Grab section from TAGESLAGE up to the next block. Der TAGESLAGE-Block
        # endet vor dem Metriken-Überblick (der eigene font-sizes mitbringt);
        # Fallback auf die erste Segment-Tabelle.
        end_pos = html.find("Metriken-Überblick", tageslage_pos)
        if end_pos == -1:
            end_pos = html.find("SEG 1", tageslage_pos)
        if end_pos == -1:
            end_pos = len(html)
        section = html[tageslage_pos:end_pos]

        sizes = re.findall(r'font-size:(\d+(?:\.\d+)?)px', section)
        # We need at least two text-carrying elements with the same font-size
        # Summary-Div should have the same size as Vortag-Div
        # Currently summary=16px, vortag=12.5px → test FAILS (RED)
        assert len(sizes) >= 2, f"Zu wenige font-size Werte im Tageslage-Block: {sizes}"
        # All non-eyebrow font sizes (> 10px) should be identical
        text_sizes = [s for s in sizes if float(s) > 10]
        assert len(set(text_sizes)) == 1, (
            f"AC-3: Summary und Vortagesvergleich haben unterschiedliche font-sizes: {text_sizes}"
        )


# ===========================================================================
# AC-4 (#898): Stage-Name-Prefix wird aus compact_summary entfernt
# ===========================================================================

class TestAC4PrefixStrip:
    """AC-4: Wenn compact_summary mit stage_name beginnt, wird der Prefix entfernt."""

    def test_prefix_not_shown_in_rendered_html(self):
        segs = _build_segments()
        stage = "Etappe 10"
        summary_with_prefix = "Etappe 10: Sonnig und warm, kaum Wind"
        html = _render_html(
            segs,
            stage_name=stage,
            compact_summary=summary_with_prefix,
        )
        # The prefix "Etappe 10: " must NOT appear in the rendered mail body
        assert "Etappe 10: Sonnig" not in html, (
            "AC-4: Stage-Name-Prefix 'Etappe 10:' erscheint noch im gerenderten Wettertext"
        )
        # The weather part must still be there
        assert "Sonnig und warm" in html, (
            "AC-4: Wettertext-Teil nach Strip-Prefix fehlt im gerenderten HTML"
        )

    def test_prefix_strip_with_named_stage(self):
        """Stage-Name im Format 'Etappe 8: Vizzavona–Bocognano' — nur Wetter-Teil bleibt."""
        segs = _build_segments()
        stage = "Etappe 8: Vizzavona"
        # compact_summary erzeugt shorten_stage_name(stage) + ": " + weather
        # shorten_stage_name truncates to max 40 chars
        prefix = "Etappe 8: Vizzavona"
        summary = f"{prefix}: Regnerisch, Böen 55 km/h"
        html = _render_html(segs, stage_name=stage, compact_summary=summary)
        assert f"{prefix}:" not in html, (
            f"AC-4: Prefix '{prefix}:' erscheint noch im HTML"
        )
        assert "Regnerisch" in html, "AC-4: Wettertext nach Prefix-Strip fehlt"


# ===========================================================================
# AC-5 (#898): Trend-Dreieck als Eyebrow-Headline, nicht im Fließtext
# ===========================================================================

class TestAC5TriangleInEyebrow:
    """AC-5: ▲/▼ Trend-Dreieck ist Teil der Eyebrow-Headline (Eyebrow-Stil),
    nicht als eigenständiger Inline-Span neben dem Fließtext.

    Aktuelle Implementierung: drei separate <span>-Elemente:
      <span eyebrow>VS. GESTERN</span>
      <span>▬</span>   ← Glyph als eigenständiger Span (NICHT im Eyebrow-Label)
      <span font-size:12.5px>Vergleich-Text</span>

    Nach Fix (AC-5): das Glyph ist TEIL des Eyebrow-Labels:
      <span eyebrow>▲ VORTAGESVERGLEICH</span>
      <span font-size:16px>Vergleich-Text</span>  ← kein separater Glyph-Span
    """

    def test_glyph_not_as_standalone_span_between_eyebrow_and_prose(self):
        """Das Trend-Glyph darf NICHT als eigener Span zwischen Eyebrow und Fließtext stehen.

        Aktueller Bug: <span>▬</span> oder <span color=...>▲</span> erscheint
        als separates Element zwischen dem Eyebrow-Span und dem Fließtext-Span.
        """
        segs = _build_segments()
        dc = _comparison_warmer()
        html = _render_html(
            segs,
            compact_summary="Sonnig.",
            day_comparison=dc,
        )
        # The current structure has a standalone glyph span:
        # ...>VS. GESTERN</span><span style="color:...;">▬</span><span style="font-size:...
        # This pattern: </span><span ...>▬</span> (glyph as isolated span) must NOT exist
        standalone_glyph_pattern = re.compile(
            r'</span><span[^>]*>([▲▼▬])</span><span',
            re.DOTALL
        )
        match = standalone_glyph_pattern.search(html)
        assert match is None, (
            f"AC-5: Trend-Glyph '{match.group(1) if match else '?'}' steht als eigenständiger "
            f"<span> zwischen Eyebrow und Fließtext — muss Teil der Eyebrow-Headline sein"
        )

    def test_vortagesvergleich_eyebrow_contains_trend_glyph(self):
        """Nach Fix: Der Eyebrow-Span für den Vortagesvergleich enthält das Glyph.

        Eyebrow-Stile: letter-spacing:0.12em, text-transform:uppercase.
        """
        segs = _build_segments()
        dc = _comparison_warmer()
        html = _render_html(
            segs,
            compact_summary="Sonnig.",
            day_comparison=dc,
        )
        # Look for an eyebrow span that contains a trend glyph
        # Eyebrow style signature: letter-spacing:0.12em
        eyebrow_with_glyph = re.search(
            r'<span[^>]*letter-spacing:0\.12em[^>]*>[^<]*[▲▼▬][^<]*</span>',
            html
        )
        assert eyebrow_with_glyph is not None, (
            "AC-5: Kein Eyebrow-Span (letter-spacing:0.12em) gefunden der ein "
            "Trend-Glyph (▲/▼/▬) als Teil des Labels enthält"
        )


# ===========================================================================
# AC-6 (#899): Keine Trend-Labels mehr
# ===========================================================================

class TestAC6NoTrendLabels:
    """AC-6: Strings '3-Tage-Trend' und 'Ausblick · nächste 4 Tage' sind entfernt."""

    def test_no_3_tage_trend_label(self):
        """'3-Tage-Trend' erscheint im context_label_html nur wenn sent_at gesetzt ist."""
        segs = _build_segments()
        trend = [
            _trend_stage("Mo", "Etappe A", conf=80),
            _trend_stage("Di", "Etappe B", conf=70),
            _trend_stage("Mi", "Etappe C", conf=45),
        ]
        # Must pass sent_at so that context_label_html is rendered
        sent = datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc)
        html = _render_html(segs, multi_day_trend=trend, sent_at=sent)
        assert "3-Tage-Trend" not in html, (
            "AC-6: String '3-Tage-Trend' noch im gerenderten HTML"
        )

    def test_no_ausblick_naechste_4_tage_label(self):
        segs = _build_segments()
        trend = [_trend_stage("Mo", "Etappe A", conf=80)]
        html = _render_html(segs, multi_day_trend=trend)
        # Neither the exact eyebrow text nor German equivalents
        assert "Ausblick · nächste 4 Tage" not in html, (
            "AC-6: 'Ausblick · nächste 4 Tage' noch im HTML"
        )
        assert "NÄCHSTE 4 TAGE" not in html, (
            "AC-6: 'NÄCHSTE 4 TAGE' noch im HTML (uppercase variant)"
        )


# ===========================================================================
# AC-7 (#911): Trend-Tage als Tabelle (<table>/<tr> je Trend-Tag), Zellhintergrund
# nach Warnlevel — PO hat das in #899 eingeführte Chip/Pill-Format wieder verworfen
# und das Tabellenformat aus #911 final freigegeben.
# ===========================================================================

class TestAC7TrendAsTable:
    """AC-7: Ausblick-Trend rendert eine <table> mit einer <tr>-Zeile je Trend-Tag,
    Zellhintergrund entspricht dem jeweiligen Warnlevel (_outlook_cell_bg/_THUNDER_LEVEL_BG)."""

    def _get_trend_section(self, html: str, trend_days: list[str]) -> str:
        """Extract the trend section by finding the last occurrence of a trend weekday.

        The trend section is a div that contains the multi_day_trend rows.
        We find the last occurrence of a weekday that's unique to the trend block
        (after all segment tables are rendered).
        """
        # Die Trend-Sektion endet, wo die nächste Sektion ("Antwort-Kommandos")
        # beginnt — sonst fängt das Fenster deren <tr>-Tabelle mit ein.
        def _clip(start: int, fallback_len: int) -> str:
            end = html.find("Antwort-Kommandos", start)
            if end == -1:
                end = start + fallback_len
            return html[start:end]

        # Aktueller Trend-Container-Header (fix #911): 'padding:24px 28px 20px;'
        pos = html.rfind('padding:24px 28px 20px')
        if pos == -1:
            # Fallback: find the last weekday occurrence (trend section is near end)
            for day in trend_days:
                rpos = html.rfind(f'>{day}<')
                if rpos != -1:
                    return _clip(max(0, rpos - 500), 3000)
            return ""
        return _clip(pos, 4000)

    def test_trend_row_count_matches_stage_count(self):
        """AC-7: Anzahl <tr>-Datenzeilen im Ausblick-Tabellenkörper entspricht der Anzahl Trend-Tage."""
        segs = _build_segments()
        trend = [
            _trend_stage("Mo", "Etappe A", conf=80),
            _trend_stage("Di", "Etappe B", conf=65),
            _trend_stage("Mi", "Etappe C", conf=45),
        ]
        html = _render_html(segs, multi_day_trend=trend)
        trend_section = self._get_trend_section(html, ["Mo", "Di", "Mi"])
        assert trend_section, "Trend-Abschnitt nicht im HTML gefunden"
        tbody_match = re.search(r"<tbody>(.*?)</tbody>", trend_section, re.DOTALL)
        assert tbody_match, "Kein <tbody> im Ausblick-Tabellenmarkup gefunden"
        tr_count = tbody_match.group(1).count("<tr>")
        assert tr_count == len(trend), (
            f"AC-7: Erwartete {len(trend)} <tr>-Zeilen im Ausblick-Tabellenkörper, "
            f"gefunden: {tr_count}"
        )

    def test_trend_cell_has_warnlevel_background(self):
        """AC-7: Zelle mit gesetztem Gewitter-Warnlevel (HIGH) trägt den definierten Zellhintergrund."""
        segs = _build_segments()
        trend = [_trend_stage("Mo", "Etappe A", conf=80)]
        trend[0]["thunder"] = "HIGH"
        html = _render_html(segs, multi_day_trend=trend)
        trend_section = self._get_trend_section(html, ["Mo"])
        assert trend_section, "Trend-Abschnitt nicht gefunden"
        tbody_match = re.search(r"<tbody>(.*?)</tbody>", trend_section, re.DOTALL)
        assert tbody_match, "Kein <tbody> im Ausblick-Tabellenmarkup gefunden"
        assert "background:#f6c5bf;" in tbody_match.group(1), (
            "AC-7: Zelle mit Gewitter-Warnlevel HIGH muss den definierten "
            "Zellhintergrund (_THUNDER_LEVEL_BG['HIGH']) tragen"
        )


# ===========================================================================
# AC-8 (#899): Keine Stage-Namen in Trend-Chips
# ===========================================================================

class TestAC8NoStageNamesInTrend:
    """AC-8: name-Felder der Trend-Dicts erscheinen NICHT in den Chip-Zeilen."""

    def test_stage_names_not_in_trend_section(self):
        segs = _build_segments()
        distinct_name_a = "GipfelRoute-X99"
        distinct_name_b = "TalPfad-Y77"
        trend = [
            _trend_stage("Mo", distinct_name_a, conf=80),
            _trend_stage("Di", distinct_name_b, conf=65),
        ]
        html = _render_html(segs, multi_day_trend=trend)
        # These stage names must NOT appear in the output
        assert distinct_name_a not in html, (
            f"AC-8: Stage-Name '{distinct_name_a}' erscheint in Trend-Chips"
        )
        assert distinct_name_b not in html, (
            f"AC-8: Stage-Name '{distinct_name_b}' erscheint in Trend-Chips"
        )


# ===========================================================================
# AC-9 (#899): Genauigkeits-Indikator pro Trend-Tag (risk_dot-Kreis)
# ===========================================================================

class TestAC9ConfidenceDotPerTrendDay:
    """AC-9: Pro Trend-Tag ein _risk_dot-Kreis in der erwarteten Farbe;
    confidence_pct=None → kein Indikator."""

    def test_three_confidence_levels_produce_three_dots(self):
        """conf=85 → grün #15803d, conf=70 → orange #c2410c, conf=45 → rot #b91c1c."""
        segs = _build_segments()
        trend = [
            _trend_stage("Mo", "A", conf=85),
            _trend_stage("Di", "B", conf=70),
            _trend_stage("Mi", "C", conf=45),
        ]
        html = _render_html(segs, multi_day_trend=trend)

        # Each color must appear in the HTML (as a confidence dot)
        # Currently: no confidence dots → RED
        assert "#15803d" in html, (
            "AC-9: Farbe #15803d (grün, conf>=80) nicht gefunden — Indikator für conf=85 fehlt"
        )
        assert "#c2410c" in html, (
            "AC-9: Farbe #c2410c (orange, 60-79) nicht gefunden — Indikator für conf=70 fehlt"
        )
        assert "#b91c1c" in html, (
            "AC-9: Farbe #b91c1c (rot, <60) nicht gefunden — Indikator für conf=45 fehlt"
        )

    def test_confidence_dot_uses_border_radius_50(self):
        """Der Indikator muss border-radius:50% haben (risk_dot-Stil)."""
        segs = _build_segments()
        trend = [_trend_stage("Mo", "A", conf=75)]
        html = _render_html(segs, multi_day_trend=trend)
        # _risk_dot() always produces border-radius:50%
        # After fix, a confidence dot must appear with this style
        # Currently no confidence dot → the count will be low
        dot_count = html.count("border-radius:50%")
        # The trend section should add at least one extra dot per trend day (confidence dot)
        # Before fix, only weather risk dots appear (from table cells)
        # We need at least 1 occurrence per trend entry that carries confidence
        # Simplest assertion: at least 1 border-radius:50% in the trend area
        trend_pos = html.find("Mo")
        if trend_pos == -1:
            assert False, "Trend-Abschnitt nicht gefunden"
        trend_area = html[trend_pos - 100:trend_pos + 1000]
        confidence_dot = re.search(
            r'border-radius:50%[^"]*["].*?#c2410c|#c2410c.*?border-radius:50%',
            trend_area, re.DOTALL
        )
        assert confidence_dot is not None, (
            "AC-9: Kein border-radius:50%-Kreis in #c2410c (conf=75) im Trend-Abschnitt"
        )

    def test_no_confidence_dot_when_none(self):
        """confidence_pct=None → kein Genauigkeits-Indikator für diesen Tag."""
        segs = _build_segments()
        trend_with_none = [_trend_stage("Mo", "A", conf=None)]
        trend_with_conf = [_trend_stage("Mo", "A", conf=80)]
        html_none = _render_html(segs, multi_day_trend=trend_with_none)
        html_conf = _render_html(segs, multi_day_trend=trend_with_conf)
        # With conf=80, green dot #15803d appears; without conf, it should not
        # (This is the fail-soft requirement)
        # If #15803d appears in BOTH it would be from the weather risk-dot, not confidence
        # So we check that the confidence-specific color pattern is absent for None
        # Since we can't always distinguish source, we check the trend area only
        trend_pos_none = html_none.find("Mo")
        if trend_pos_none != -1:
            trend_area_none = html_none[trend_pos_none - 50:trend_pos_none + 800]
            # For None confidence, there should be no confidence-specific annotation
            # Currently passes trivially (no dots at all) → add stricter check after fix
            # For now: verify that conf=80 adds #15803d in the trend area, None doesn't add extra
            trend_pos_conf = html_conf.find("Mo")
            if trend_pos_conf != -1:
                trend_area_conf = html_conf[trend_pos_conf - 50:trend_pos_conf + 800]
                count_green_none = trend_area_none.count("#15803d")
                count_green_conf = trend_area_conf.count("#15803d")
                # conf=80 should result in more green color occurrences than conf=None
                assert count_green_conf > count_green_none, (
                    "AC-9: conf=80 erzeugt nicht mehr #15803d-Vorkommen als conf=None — "
                    "Konfidenz-Indikator nicht implementiert"
                )


# ===========================================================================
# AC-10 (#901): Footer enthält kein "Abmelden"
# ===========================================================================

class TestAC10NoAbmelden:
    """AC-10: Footer-Abschnitt enthält das Wort 'Abmelden' nicht."""

    def test_abmelden_not_in_footer(self):
        segs = _build_segments()
        html = _render_html(segs)
        assert "Abmelden" not in html, (
            "AC-10: 'Abmelden' noch im gerenderten HTML (Footer)"
        )


# ===========================================================================
# AC-11 (#901): Deep-Links wenn trip_url gesetzt
# ===========================================================================

class TestAC11DeepLinksPresent:
    """AC-11: Footer enthält <a href>-Links auf trip_url und trip_url/edit."""

    TRIP_URL = "https://gregor20.henemm.com/trips/test-trip-123"

    def test_trip_overview_link(self):
        segs = _build_segments()
        # trip_url parameter does not yet exist → lands in **_ignored, no links
        html = _render_html(segs, trip_url=self.TRIP_URL)
        assert f'<a href="{self.TRIP_URL}"' in html, (
            f"AC-11: Kein <a href='{self.TRIP_URL}'> im Footer — trip_url-Parameter fehlt"
        )

    def test_trip_edit_link(self):
        segs = _build_segments()
        html = _render_html(segs, trip_url=self.TRIP_URL)
        edit_url = f"{self.TRIP_URL}/edit"
        assert f'<a href="{edit_url}"' in html, (
            f"AC-11: Kein <a href='{edit_url}'> im Footer — Deep-Link für Briefing-Zeitplan fehlt"
        )


# ===========================================================================
# AC-12 (#901): Keine Deep-Links wenn trip_url=None (Backward-Compat)
# Backward-Compat, initial grün — render_html nimmt trip_url=None über **_ignored an
# ===========================================================================

class TestAC12NoLinksWithoutTripUrl:
    """AC-12: Backward-Compat — ohne trip_url keine <a href>-Tags im Footer.

    Dieser Test kann initial GRÜN sein, da render_html trip_url=None
    über **_ignored aufnimmt und keine Links rendert.
    """

    def test_no_href_links_in_footer_without_trip_url(self):
        segs = _build_segments()
        html = _render_html(segs)  # no trip_url
        # Footer should not contain href links to trip URLs
        # (other links like data: or mailto: are not expected either)
        trip_links = re.findall(r'<a href="https://gregor20\.henemm\.com/trips/', html)
        assert len(trip_links) == 0, (
            f"AC-12: Ohne trip_url erscheinen {len(trip_links)} Trip-Links im Footer"
        )


# ===========================================================================
# AC-13 (#901): Segmente-Zelle vertikal bündig (Alignment-Fix)
# ===========================================================================

class TestAC13SegmenteAlignment:
    """AC-13: 'Segmente'-Stat-Zelle hat identische Struktur wie andere Stat-Zellen.

    Diagnostik: Die Zelle hat unit="" (leere Einheit), was bei den anderen Zellen
    (km, m) eine <span>-Einheit erzeugt. Die Segmente-Zelle fehlt dieser Span oder
    hat andere Dimensionen → vertikale Ausrichtung bricht.

    Erwartetes Fix-Verhalten: Alle Stat-Zellen haben einen unit-<span>, auch wenn
    die Einheit leer ist — damit alle identische HTML-Struktur und vertikale Flucht haben.
    """

    def test_segmente_cell_present(self):
        """Segmente-Zelle muss im Stats-Grid vorhanden sein."""
        segs = _build_segments()
        stats = {
            "distance_km": 12.3,
            "ascent_m": 428.0,
            "descent_m": 421.0,
            "max_elevation_m": 1943.0,
        }
        html = _render_html(segs, stage_stats=stats)
        assert "Segmente" in html, (
            "AC-13: 'Segmente'-Zelle nicht im Stats-Grid gefunden"
        )

    def test_segmente_cell_empty_unit_span_has_min_width(self):
        """Die Segmente-Zelle hat unit='' — der leere unit-Span braucht min-width
        oder eine andere Methode damit die Zelle dieselbe vertikale Höhe wie
        Distanz/Aufstieg/etc. hat und nicht nach unten verrutscht.

        Aktueller Bug: leerer <span></span> hat keine Mindestbreite/Mindesthöhe →
        Baseline-Alignment-Fehler in E-Mail-Clients.

        Nach Fix: entweder min-width auf dem Span, Inline-Block mit fester Höhe,
        oder ein Nicht-Leer-Placeholder (z.B. ' ' = non-breaking space).
        """
        segs = _build_segments()
        stats = {
            "distance_km": 12.3,
            "ascent_m": 428.0,
            "descent_m": 421.0,
            "max_elevation_m": 1943.0,
        }
        html = _render_html(segs, stage_stats=stats)

        stat_td_pattern = re.compile(
            r'<td[^>]*vertical-align:top[^>]*>(.*?)</td>', re.DOTALL
        )
        stat_cells = stat_td_pattern.findall(html)
        segmente_cell = next((c for c in stat_cells if "Segmente" in c), None)
        distanz_cell = next((c for c in stat_cells if "Distanz" in c), None)

        assert segmente_cell is not None, "Segmente-Zelle nicht gefunden"
        assert distanz_cell is not None, "Distanz-Referenz-Zelle nicht gefunden"

        # Find the unit span in the Segmente cell
        # Current: <span style="font-size:11px;...;margin-left:3px;"></span>
        # The unit span in the Segmente cell must NOT be empty (no content, no min-width)
        segmente_unit_span = re.search(
            r'<span[^>]*font-size:11px[^>]*>(.*?)</span>',
            segmente_cell, re.DOTALL
        )
        assert segmente_unit_span is not None, (
            "AC-13: Kein unit-<span> (font-size:11px) in Segmente-Zelle gefunden"
        )
        span_content = segmente_unit_span.group(1)
        span_full = segmente_unit_span.group(0)

        # The span must either have content OR a min-width/display:inline-block style
        # to preserve vertical alignment — currently it's completely empty with no sizing
        has_content = bool(span_content.strip())
        has_min_width = "min-width" in span_full
        has_inline_block = "inline-block" in span_full
        assert has_content or has_min_width or has_inline_block, (
            f"AC-13: Segmente unit-Span ist leer und hat kein min-width/inline-block — "
            f"vertikale Ausrichtung bricht in E-Mail-Clients. "
            f"Span: {span_full!r}"
        )
