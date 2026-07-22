"""
TDD — Issue #790: Briefing-Mail vereinfachen.

Vier Altblöcke aus dem Render-Code entfernt (Quick-Take-Chips, Highlights,
Tageslicht, Tages-Summe), Antwort-Kommandos nur 1x, Metrik-Pills als EINER
fester Block (immer sichtbar, Default-Satz wenn metrics leer), Vortag-Vergleich
als EINE Einordnungszeile weit oben.

Mock-frei: echte render_html()/render_plain()/format_email()-Aufrufe mit echten
ForecastDataPoint/SegmentWeatherData-Objekten. Geprüft wird der gerenderte
Output (Produkt), kein Quelltext.

SPEC: docs/specs/modules/issue_790_briefing_mail_simplify.md AC-1..AC-9
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
# Fixtures — Segmente mit bekannten Stundenwerten (Muster aus #621/#664)
# ---------------------------------------------------------------------------

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


_SIMPLE_ROWS = [{
    "time": "06:00", "temp": 12.0, "_wind_dir_deg": None, "_is_day": True,
    "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None,
}]


def _empty_metrics_dc():
    """display_config mit leerer metrics-Liste."""
    import dataclasses
    from app.metric_catalog import build_default_display_config
    dc = build_default_display_config()
    return dataclasses.replace(dc, metrics=[])


def _render_html(segs, *, dc=None, **kwargs):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html
    params = dict(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type="morning",
        dc=dc or build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name=None, stage_stats=None, multi_day_trend=None,
        compact_summary=None, tz=TZ, friendly_keys=set(),
    )
    params.update(kwargs)
    return render_html(**params)


def _render_plain(segs, *, dc=None, **kwargs):
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.plain import render_plain
    params = dict(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="GR20 Test", report_type="morning",
        dc=dc or build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name=None, stage_stats=None, multi_day_trend=None,
        compact_summary=None, tz=TZ, friendly_keys=set(),
    )
    params.update(kwargs)
    return render_plain(**params)


# ===========================================================================
# AC-1: Keine Quick-Take-Chips mehr
# ===========================================================================

class TestAC1NoQuickTake:

    def test_no_quick_take_chips_html(self):
        html = _render_html(_build_segments())
        # "Kein Gewitter" war der eindeutige Quick-Take-Chip-Text (ThunderLevel.NONE)
        assert "Kein Gewitter" not in html

    def test_no_quick_take_chips_with_thunder_html(self):
        html = _render_html(_build_segments(thunder=True))
        # "Gewitter möglich" war der Quick-Take-Chip bei Gewitter (jetzt entfernt;
        # die Pille zeigt stattdessen "Gewitter ab HH:00")
        assert "Gewitter möglich" not in html


# ===========================================================================
# AC-2: Kein Highlights-/Zusammenfassungs-Block
# ===========================================================================

class TestAC2NoHighlights:

    def test_no_summary_section_html(self):
        html = _render_html(_build_segments())
        assert "Zusammenfassung" not in html

    def test_no_summary_section_plain(self):
        plain = _render_plain(_build_segments())
        assert "Zusammenfassung" not in plain


# ===========================================================================
# AC-3: Kein Tageslicht-/"Ohne Stirnlampe"-Block
# ===========================================================================

class TestAC3NoDaylight:

    def test_no_stirnlampe_html(self):
        html = _render_html(_build_segments())
        assert "Stirnlampe" not in html

    def test_no_stirnlampe_plain(self):
        plain = _render_plain(_build_segments())
        assert "Stirnlampe" not in plain


# ===========================================================================
# AC-4: Kein Tages-Summe-Block
# ===========================================================================

class TestAC4NoDailySummary:

    def test_no_tages_summe_html(self):
        html = _render_html(_build_segments())
        assert "Tages-Summe" not in html

    def test_no_tages_summe_plain(self):
        plain = _render_plain(_build_segments())
        assert "Tages-Summe" not in plain


# ===========================================================================
# AC-5: Antwort-Kommando-Liste genau einmal (HTML)
# ===========================================================================

class TestAC5CommandsOnce:

    def test_command_listing_once_html(self):
        html = _render_html(_build_segments())
        # Der Haupt-Block trägt die Überschrift "Antwort-Kommandos".
        assert html.count("Antwort-Kommandos") == 1
        # Der frühere Footer-Span ("Auf diese Mail antworten mit:") ist entfernt.
        assert "Auf diese Mail antworten mit" not in html


# ===========================================================================
# AC-6: Metriken-Überblick immer sichtbar + Default-Satz bei leeren metrics
# ===========================================================================

class TestAC6MetricsAlwaysVisible:

    def test_overview_present_with_default_config_html(self):
        html = _render_html(_build_segments())
        assert "Metriken-Überblick" in html

    def test_overview_present_with_default_config_plain(self):
        plain = _render_plain(_build_segments())
        assert "Metriken-Überblick" in plain

    def test_empty_metrics_uses_default_set_html(self):
        """Leere metrics-Liste → Default-Satz: mehrere Pillen mit Uhrzeit,
        nicht nur die leere Überschrift."""
        html = _render_html(_build_segments(), dc=_empty_metrics_dc())
        assert "Metriken-Überblick" in html
        # Default-Satz enthält Temperatur (°C), Regen-Pille und Gewitter-Pille.
        assert "°C" in html, "Temperatur-Pille (Default-Satz) fehlt"
        # mindestens eine Uhrzeit (HH:00) als Beleg für gefüllte Pillen
        import re
        # die Metriken-Überblick-Sektion isolieren
        idx = html.find("Metriken-Überblick")
        block = html[idx:idx + 1200]
        assert re.search(r"\d{2}:00", block), f"keine Uhrzeit in Pillen:\n{block}"

    def test_empty_metrics_uses_default_set_plain(self):
        plain = _render_plain(_build_segments(), dc=_empty_metrics_dc())
        idx = plain.find("Metriken-Überblick")
        assert idx != -1
        block = plain[idx:idx + 600]
        # Default-Satz liefert mehrere Pillen-Zeilen. Issue #795: die rohen
        # [TONE]-Marker sind entfernt (AC-2) — gezählt werden eingerückte
        # Pill-Zeilen (zwei führende Leerzeichen) bis zur Leerzeile.
        pill_lines = [
            ln for ln in block.splitlines()
            if ln.startswith("  ") and ln.strip()
            and "Metriken" not in ln
        ]
        assert len(pill_lines) >= 3, f"zu wenige Default-Pillen:\n{block}"

    def test_specific_metrics_rendered_html(self):
        """Bei gefüllter Auswahl erscheinen genau diese Metriken als Pillen.
        Default-config = temperature/wind/gust/precipitation/thunder etc. —
        prüfe dass Temperatur-Pille (°C) erscheint."""
        html = _render_html(_build_segments())
        idx = html.find("Metriken-Überblick")
        block = html[idx:idx + 1500]
        assert "°C" in block, "Temperatur-Pille fehlt bei gefüllter Auswahl"


# ===========================================================================
# AC-7: Vortag-Einordnung — eine Zeile oben, keine Segment-Tabelle
# ===========================================================================

def _comparison(today, yday):
    from services.day_comparison import DayComparisonService
    return DayComparisonService().compare(today, yday)


def _seg_for_compare(seg_id, **agg):
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )
    start = datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1500.0),
        end_point=GPXPoint(lat=42.2, lon=9.2, elevation_m=1600.0),
        start_time=start, end_time=end,
        duration_hours=4.0, distance_km=12.0, ascent_m=600.0, descent_m=300.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo", grid_res_km=1.0)
    ts = NormalizedTimeseries(meta=meta, data=[])
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(**agg),
        fetched_at=datetime.now(timezone.utc), provider="demo")


class TestAC7VortagOneLine:

    def test_warmer_and_drier_line(self):
        """heute wärmer + trockener → 'Vortag: heute wärmer und trockener als gestern'."""
        from services.day_comparison import summarize_day_comparison
        today = [_seg_for_compare(1, temp_min_c=10.0, temp_max_c=20.0,
                                  wind_max_kmh=20.0, precip_sum_mm=1.0)]
        yday = [_seg_for_compare(1, temp_min_c=6.0, temp_max_c=15.0,
                                 wind_max_kmh=20.0, precip_sum_mm=10.0)]
        line = summarize_day_comparison(_comparison(today, yday))
        assert line == "Vergleich zum Vortag: heute wärmer und trockener als gestern", line

    def test_colder_only_line(self):
        """nur Temperatur signifikant kälter, Regen neutral."""
        from services.day_comparison import summarize_day_comparison
        today = [_seg_for_compare(1, temp_min_c=4.0, temp_max_c=10.0,
                                  wind_max_kmh=20.0, precip_sum_mm=5.0)]
        yday = [_seg_for_compare(1, temp_min_c=8.0, temp_max_c=18.0,
                                 wind_max_kmh=20.0, precip_sum_mm=5.0)]
        line = summarize_day_comparison(_comparison(today, yday))
        assert line == "Vergleich zum Vortag: heute kälter als gestern", line

    def test_similar_weather_line(self):
        """beide neutral → 'ähnliches Wetter'."""
        from services.day_comparison import summarize_day_comparison
        today = [_seg_for_compare(1, temp_min_c=8.0, temp_max_c=18.0,
                                  wind_max_kmh=20.0, precip_sum_mm=5.0)]
        yday = [_seg_for_compare(1, temp_min_c=8.0, temp_max_c=18.5,
                                 wind_max_kmh=20.0, precip_sum_mm=5.0)]
        line = summarize_day_comparison(_comparison(today, yday))
        assert line == "Vergleich zum Vortag: heute ähnliches Wetter wie gestern", line

    def test_none_returns_empty(self):
        from services.day_comparison import summarize_day_comparison
        assert summarize_day_comparison(None) == ""

    def test_one_line_in_html_no_segment_table(self):
        """Im HTML: genau eine Einordnungszeile oben, keine 'Segment N:'-Tabelle,
        kein altes 'Vortag-Vergleich'-Sektions-Label."""
        today = [_seg_for_compare(1, temp_min_c=10.0, temp_max_c=20.0,
                                  wind_max_kmh=20.0, precip_sum_mm=1.0)]
        yday = [_seg_for_compare(1, temp_min_c=6.0, temp_max_c=15.0,
                                 wind_max_kmh=20.0, precip_sum_mm=10.0)]
        dc = _comparison(today, yday)
        html = _render_html(_build_segments(), day_comparison=dc)
        assert "Vortag: heute" in html, "Einordnungszeile fehlt"
        assert "Vortag-Vergleich" not in html, "alte Sektion noch da"

    def test_position_above_segments_html(self):
        """Die Vortag-Zeile steht VOR den Stundentabellen (Segment-Köpfen).

        Note: #884 renamed segment headings from "Segment N" to "SEG N".
        """
        today = [_seg_for_compare(1, temp_min_c=10.0, temp_max_c=20.0,
                                  wind_max_kmh=20.0, precip_sum_mm=1.0)]
        yday = [_seg_for_compare(1, temp_min_c=6.0, temp_max_c=15.0,
                                 wind_max_kmh=20.0, precip_sum_mm=10.0)]
        dc = _comparison(today, yday)
        html = _render_html(_build_segments(), day_comparison=dc,
                            compact_summary="Wechselhaft.")
        pos_line = html.find("Vortag: heute")
        # #884: segment heading is now "SEG N" not "Segment N"
        pos_seg = html.find("SEG 1")
        assert pos_line != -1 and pos_seg != -1
        assert pos_line < pos_seg, "Vortag-Zeile muss oben vor den Segmenten stehen"

    def test_one_line_in_plain(self):
        today = [_seg_for_compare(1, temp_min_c=10.0, temp_max_c=20.0,
                                  wind_max_kmh=20.0, precip_sum_mm=1.0)]
        yday = [_seg_for_compare(1, temp_min_c=6.0, temp_max_c=15.0,
                                 wind_max_kmh=20.0, precip_sum_mm=10.0)]
        dc = _comparison(today, yday)
        plain = _render_plain(_build_segments(), day_comparison=dc)
        assert "Vortag: heute" in plain
        assert "Vortag-Vergleich" not in plain

    def test_empty_metrics_list_falls_back_to_legacy(self):
        """Bug #800: selected_metrics=[] darf NICHT 'ähnliches Wetter' liefern wenn echte Deltas existieren."""
        from services.day_comparison import summarize_day_comparison
        today = [_seg_for_compare(1, temp_min_c=14.0, temp_max_c=28.0,
                                  wind_max_kmh=20.0, precip_sum_mm=0.0)]
        yday = [_seg_for_compare(1, temp_min_c=4.0, temp_max_c=15.0,
                                 wind_max_kmh=20.0, precip_sum_mm=18.0)]
        comp = _comparison(today, yday)
        line_empty = summarize_day_comparison(comp, selected_metrics=[])
        line_none = summarize_day_comparison(comp, selected_metrics=None)
        assert line_empty == line_none, (
            f"Bug #800: [] muss identisch zu None sein — leere Liste gab: '{line_empty}'"
        )
        assert "ähnliches Wetter" not in line_empty, (
            f"Bug #800: große Deltas aber Fallback liefert 'ähnliches Wetter': '{line_empty}'"
        )


# ===========================================================================
# Bug #798: leere Metrik-Auswahl → Stundentabelle zeigt keine Spalten
# ===========================================================================

class TestBug798EmptyMetricsHourTable:

    def test_allowed_col_keys_returns_none_when_no_metrics_enabled(self):
        """Bug #798: _allowed_col_keys_for_horizon muss None (kein Filter) zurückgeben wenn metrics leer."""
        from output.renderers.email.html import _allowed_col_keys_for_horizon
        dc = _empty_metrics_dc()
        result = _allowed_col_keys_for_horizon(dc, "short")
        assert result is None, (
            f"Bug #798: leere metrics → kein Filter erwartet (None), aber got {result!r}"
        )

    def test_html_table_has_columns_when_metrics_empty(self):
        """Bug #798: render_html mit leeren Metriken darf nicht nur 'Zeit'-Spalte liefern.

        Note: #884 added header tables (stats-grid, two-column layout) before the data tables.
        We search for the first data table with class="resp" (the hourly segment table).
        """
        segs = _build_segments()
        dc = _empty_metrics_dc()
        html = _render_html(segs, dc=dc)
        # Find first <table data-table="resp" — that's the hourly data table
        table_start = html.find('<table data-table="resp"')
        assert table_start != -1, "Bug #798: Keine <table class=\"resp\"> im HTML gefunden"
        table_html = html[table_start:]
        header_end = table_html.find('</tr>')
        header = table_html[:header_end]
        # Issue #900: <th> tragen jetzt Inline-Styles (Header-Kennzeichnung +
        # Gitterlinien), daher auf '<th' statt exakt '<th>' zählen.
        th_count = header.count('<th')
        assert th_count > 1, (
            f"Bug #798: nur {th_count} <th>-Element(e) im Tabellen-Header — erwartet >1 (mehr als 'Zeit')"
        )


# ===========================================================================
# AC-8: Regressionsschutz — erhaltene Blöcke
# ===========================================================================

def _trend_stage():
    return {"weekday": "Mi", "name": "Nächste Etappe", "temp_lo": 12,
            "temp_hi": 18, "precip_mm": 0.5, "wind_dir": "W", "wind_kmh": 17,
            "thunder": "NONE", "note": None, "confidence_pct": 80,
            "hourly_precip": (), "hourly_wind": (), "hourly_gust": (),
            "hourly_thunder": ()}


class TestAC8RegressionPreserved:

    def test_stage_stats_preserved_html(self):
        stats = {"distance_km": 9.3, "ascent_m": 1600.0, "descent_m": 0.0}
        html = _render_html(_build_segments(), stage_stats=stats)
        assert "Distanz" in html and "Aufstieg" in html

    def test_stability_preserved_html(self):
        from app.models import StabilityResult
        html = _render_html(_build_segments(),
                            stability_result=StabilityResult(label="STABIL",
                                                             confidence_pct=88),
                            multi_day_trend=None)
        assert "Wetterlage: STABIL" in html

    def test_outlook_preserved_html(self):
        # Issue #899: Das "Ausblick · nächste 4 Tage"-Label wurde entfernt; der
        # Trend-Bereich selbst (mehrtägige Vorschau) bleibt erhalten und wird als
        # Chips pro Tag gerendert. Regressionsschutz: der Trend-Tag muss erscheinen.
        html = _render_html(_build_segments(), multi_day_trend=[_trend_stage()])
        assert "Mi" in html, "Trend-Vorschau (Wochentag des Trend-Tages) muss vorhanden sein"
        # Issue #899 (Punkt 5): Etappenname erscheint NICHT mehr in der Trend-Zeile
        assert "Nächste Etappe" not in html, "Etappenname darf in der Trend-Zeile nicht erscheinen"

    def test_hourly_table_preserved_html(self):
        # #884: segment heading changed from "Segment N" to "SEG N"
        html = _render_html(_build_segments())
        assert "SEG 1" in html, "#884 design: segment heading is 'SEG 1' not 'Segment 1'"

    def test_thunder_forecast_preserved_html(self):
        from app.models import ThunderLevel
        tf = {"+1": {"date": "Sa 12.07", "text": "Gewitter nachmittags",
                     "level": ThunderLevel.MED}}
        html = _render_html(_build_segments(), thunder_forecast=tf)
        assert "Gewitter-Vorschau" in html

    def test_changes_preserved_html(self):
        from app.models import ChangeSeverity, WeatherChange
        ch = [WeatherChange(metric="precip_sum_mm", old_value=0.0, new_value=12.5,
                            delta=12.5, threshold=5.0,
                            severity=ChangeSeverity.MAJOR, direction="increase")]
        html = _render_html(_build_segments(), changes=ch)
        assert "Wetteränderungen" in html


# ===========================================================================
# AC-9: Bestandsschutz — entfernte report_config-Felder bleiben im Schema
# ===========================================================================

class TestAC9LegacyFieldsPreserved:

    def _trip_dict(self):
        return {
            "id": "trip-790", "name": "Bestandstrip", "stages": [],
            "report_config": {
                "trip_id": "trip-790", "enabled": True,
                "morning_time": "07:00:00", "evening_time": "18:00:00",
                "show_quick_take_tags": False,
                "show_highlights": False,
                # Issue #1224: show_daylight ist kein TripReportConfig-Feld
                # mehr — hier bewusst als Alt-Feld in der Roh-JSON belassen,
                # um zu beweisen, dass das Laden trotzdem nicht crasht (AC-3).
                "show_daylight": False,
                "daily_summary_metrics": ["temperature"],
            },
        }

    def test_fields_still_loadable(self):
        """AC-3 (#1224): unbekanntes Alt-Feld show_daylight crasht das Laden
        nicht; die uebrigen Legacy-Felder bleiben unveraendert ladbar."""
        from app.loader import load_trip_from_dict
        trip = load_trip_from_dict(self._trip_dict())
        rc = trip.report_config
        assert rc.show_quick_take_tags is False
        assert rc.show_highlights is False
        assert not hasattr(rc, "show_daylight"), (
            "Issue #1224: show_daylight wurde aus TripReportConfig entfernt"
        )
        assert rc.daily_summary_metrics == ["temperature"]

    def test_roundtrip_preserves_fields(self):
        """Issue #1224: show_daylight ist aus der Python-eigenen
        _trip_to_dict()-Serialisierung entfernt (kein Modellfeld mehr) —
        die uebrigen Legacy-Felder roundtrippen unveraendert weiter."""
        from app.loader import load_trip_from_dict, _trip_to_dict
        trip = load_trip_from_dict(self._trip_dict())
        dumped = _trip_to_dict(trip)
        rc = dumped["report_config"]
        assert rc["show_quick_take_tags"] is False
        assert rc["show_highlights"] is False
        assert "show_daylight" not in rc
        assert rc["daily_summary_metrics"] == ["temperature"]
