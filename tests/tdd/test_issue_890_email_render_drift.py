"""
TDD RED — Issue #890 (Design-Handoff #26): Briefing-Email Render-Drift.

Drei Regressions-Checks gegen render_html():
  A1 — Header: Strecken-Titel links, Trip-Name+Etappen-Zähler rechts, Datum+Uhrzeit
  A3 — RiskDot-Spalte in der Stunden-Tabelle
  B1-B3 — Ein Tageslage-Akzent-Bar-Lead statt zwei farbiger Kästen

Mock-frei: echter render_html()-Aufruf mit echten Datenobjekten.
Spec: docs/specs/modules/fix_26_email_render_drift.md
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
SENT_AT = datetime(2026, 6, 27, 4, 1, tzinfo=timezone.utc)  # 06:01 MESZ


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

def _build_segments(*, gust_kmh: float = 15.0, thunder_pct: float = 0.0):
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    dp = ForecastDataPoint(
        ts=datetime(2026, 6, 27, 8, 0, tzinfo=timezone.utc),
        t2m_c=12.0,
        wind10m_kmh=10.0,
        gust_kmh=gust_kmh,
        precip_1h_mm=0.0,
        pop_pct=10,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        visibility_m=5000.0,
        freezing_level_m=2500.0,
    )
    seg = TripSegment(
        segment_id="1",
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=400.0,
                              distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1200.0,
                            distance_from_start_km=15.0),
        start_time=datetime(2026, 6, 27, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 27, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=15.0,
        ascent_m=800.0,
        descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 6, 27, 0, 0, tzinfo=timezone.utc),
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=14.0, temp_avg_c=12.0,
        wind_max_kmh=10.0, gust_max_kmh=gust_kmh,
        precip_sum_mm=0.0, cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    return [SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )]


def _render(
    *,
    stage_name: str = "Etappe 1: Calenzana → Carrozzu",
    trip_name: str = "GR20",
    stage_total: int | None = 15,
    compact_summary: str | None = None,
    day_comparison=None,
    gust_kmh: float = 15.0,
):
    from app.metric_catalog import build_default_display_config
    from src.output.renderers.email.html import render_html
    from src.output.renderers.email.helpers import build_friendly_keys

    segs = _build_segments(gust_kmh=gust_kmh)
    dc = build_default_display_config()
    # visibility ist im Default-DC NICHT aktiviert; für die Vortag-Tests
    # (metric-driven "bessere Sicht") muss visibility in den selected_metrics
    # erscheinen — sonst filtert summarize_day_comparison() den Entry raus.
    for _mc in dc.metrics:
        if _mc.metric_id == "visibility":
            _mc.enabled = True
    fk = build_friendly_keys(dc)

    from formatters.trip_report import TripReportFormatter
    fmt = TripReportFormatter()
    seg_tables = [fmt._extract_hourly_rows(s, dc) for s in segs]

    return render_html(
        segments=segs,
        seg_tables=seg_tables,
        trip_name=trip_name,
        report_type="morning",
        dc=dc,
        night_rows=[],
        thunder_forecast=None,
        changes=None,
        stage_name=stage_name,
        stage_stats={"distance_km": 15.0, "ascent_m": 800.0, "descent_m": 0.0, "max_elevation_m": 1200.0},
        multi_day_trend=None,
        compact_summary=compact_summary,
        tz=TZ,
        friendly_keys=fk,
        sent_at=SENT_AT,
        stage_total=stage_total,
        day_comparison=day_comparison,
    )


def _day_comparison_better_visibility():
    """Echtes DayComparison-Objekt (entries-API), das via metric-driven
    summarize_day_comparison() den Satz 'heute bessere Sicht als gestern'
    erzeugt — visibility_min mit positivem Delta über der Spürbarkeitsschwelle.
    visibility wird in _render() für den DC aktiviert.
    """
    from services.day_comparison import (
        ComparisonDirection, DayComparison, DayComparisonEntry, MetricDelta,
    )

    def _missing():
        return MetricDelta(delta=None, direction=ComparisonDirection.MISSING)

    entry = DayComparisonEntry(
        segment_id=1,
        temp_min=_missing(),
        temp_max=_missing(),
        wind_max=_missing(),
        gust_max=_missing(),
        precip_sum=_missing(),
        thunder=_missing(),
        visibility_min=MetricDelta(delta=8000.0, direction=ComparisonDirection.BETTER),
    )
    return DayComparison(entries=[entry])


# ---------------------------------------------------------------------------
# AC-1: Strecken-Titel links (nicht Trip-Name)
# ---------------------------------------------------------------------------

def test_ac1_route_title_left_col():
    """
    GIVEN stage_name='Etappe 1: Calenzana → Carrozzu', trip_name='GR20'
    WHEN render_html() called
    THEN linke Header-Spalte enthält 'Calenzana → Carrozzu' als 22px-Titel,
         NICHT 'GR20'.
    """
    html = _render()
    # Der 22px-Haupttitel muss den Streckentitel enthalten, nicht den Trip-Namen
    route_title_pattern = re.compile(
        r'font-size:22px[^>]*>([^<]*Calenzana[^<]*Carrozzu[^<]*)<', re.DOTALL
    )
    assert route_title_pattern.search(html), (
        "AC-1 FAIL: '22px'-Titel enthält nicht den Strecken-Titel 'Calenzana → Carrozzu'. "
        "Aktuell steht dort vermutlich der Trip-Name 'GR20'."
    )


def test_ac1_trip_name_right_col():
    """
    GIVEN trip_name='GR20'
    WHEN render_html() called
    THEN rechte Header-Spalte enthält 'GR20' als 14px-Titel.
    """
    html = _render()
    trip_name_pattern = re.compile(
        r'font-size:14px[^>]*font-weight:600[^>]*>GR20<', re.DOTALL
    )
    assert trip_name_pattern.search(html), (
        "AC-1 FAIL: Trip-Name 'GR20' nicht als 14px-bold in rechter Spalte gefunden."
    )


# ---------------------------------------------------------------------------
# AC-2: Datum-Zeile mit Wochentag + Uhrzeit
# ---------------------------------------------------------------------------

def test_ac2_date_line_with_time():
    """
    GIVEN sent_at=2026-06-27T04:01Z (= Sa 06:01 MESZ)
    WHEN render_html() called
    THEN Datum-Zeile enthält Wochentag + Datum + Uhrzeit.
    """
    html = _render()
    # Sa · 27.06.2026 · 06:01 (Wochentag · TT.MM.JJJJ · HH:MM)
    date_pattern = re.compile(r'Sa\s*·\s*27\.06\.2026\s*·\s*06:01')
    assert date_pattern.search(html), (
        "AC-2 FAIL: Datum-Zeile enthält nicht 'Sa · 27.06.2026 · 06:01'. "
        "Aktuell wird nur das Datum ohne Wochentag/Uhrzeit ausgegeben."
    )


# ---------------------------------------------------------------------------
# AC-3: Etappen-Zähler rechts
# ---------------------------------------------------------------------------

def test_ac3_stage_counter():
    """
    GIVEN stage_name='Etappe 1: ...', stage_total=15
    WHEN render_html() called
    THEN rechte Spalte enthält 'Etappe 1 / 15'.
    """
    html = _render(stage_total=15)
    assert "Etappe 1 / 15" in html, (
        "AC-3 FAIL: 'Etappe 1 / 15' nicht im Header-HTML gefunden. "
        "Parameter stage_total ist noch nicht implementiert."
    )


# ---------------------------------------------------------------------------
# AC-4: RiskDot-Spalte in der Stunden-Tabelle
# ---------------------------------------------------------------------------

def test_ac4_riskdot_ok_row():
    """
    GIVEN eine Zeile mit gust=15 km/h (unter watch-Schwelle)
    WHEN render_html() called
    THEN enthält die Tabelle eine Zelle mit grünem RiskDot (#15803d).
    """
    html = _render(gust_kmh=15.0)
    assert "#15803d" in html, (
        "AC-4 FAIL: Grüner RiskDot (#15803d) nicht in Tabelle gefunden. "
        "Die RiskDot-Spalte ist noch nicht implementiert."
    )


def test_ac4_riskdot_watch_row():
    """
    GIVEN eine Zeile mit gust=35 km/h (über watch-Schwelle 30)
    WHEN render_html() called
    THEN enthält die Tabelle eine Zelle mit orangem RiskDot (#c2410c).
    """
    html = _render(gust_kmh=35.0)
    # Farbe #c2410c für "watch" — darf nicht nur im Highlighting-Span sein,
    # sondern muss auch als RiskDot-Hintergrund erscheinen
    risk_dot_pattern = re.compile(
        r'border-radius:50%[^;]*;background:#c2410c', re.DOTALL
    )
    assert risk_dot_pattern.search(html), (
        "AC-4 FAIL: Oranger RiskDot (border-radius:50%;background:#c2410c) "
        "nicht in Tabelle gefunden bei gust=35 km/h."
    )


# ---------------------------------------------------------------------------
# AC-5: Ein Tageslage-Lead statt zwei Kästen
# ---------------------------------------------------------------------------

def test_ac5_single_tageslage_block():
    """
    GIVEN compact_summary und day_comparison_line beide vorhanden
    WHEN render_html() called
    THEN genau ein Block mit border-left:2px solid #c45a2a,
         kein background:#dde8f3 (alter blauer Info-Kasten).
    """
    dc_obj = _day_comparison_better_visibility()
    html = _render(
        compact_summary="Mäßiger Regen ab 11:00, Böen bis 25 km/h.",
        day_comparison=dc_obj,
    )
    # Kein alter blauer Info-Kasten mehr. Der alte summary_html-/
    # day_comparison_html-Block nutzte G_BOX_INFO_BG (#dfe7f0) als
    # Hintergrund — dieser Box-Hintergrund darf nicht mehr im HTML stehen.
    # (Hinweis: #dde8f3 ist die info-Pille im Metriken-Überblick, NICHT der
    #  alte Tageslage-Kasten — daher wird gegen #dfe7f0 geprüft.)
    assert "#dfe7f0" not in html, (
        "AC-5 FAIL: Alter blauer Info-Kasten (background:#dfe7f0) noch im HTML. "
        "compact_summary und day_comparison müssen zu einem Lead zusammengefasst werden."
    )
    # Genau ein Akzent-Bar-Lead
    accent_bars = len(re.findall(r'border-left:2px solid #c45a2a', html))
    assert accent_bars == 1, (
        f"AC-5 FAIL: Erwartet genau 1 Akzent-Bar (border-left:2px solid #c45a2a), "
        f"gefunden: {accent_bars}."
    )
    # Eyebrow TAGESLAGE vorhanden
    assert "TAGESLAGE" in html, (
        "AC-5 FAIL: Eyebrow 'TAGESLAGE' nicht im Lead-Block gefunden."
    )


def test_ac5_vortag_mono_line():
    """
    GIVEN day_comparison_line = 'heute bessere Sicht als gestern'
    WHEN render_html() called
    THEN enthält der Lead 'VS. GESTERN' und den Trend-Glyph ▲.
    """
    dc_obj = _day_comparison_better_visibility()
    html = _render(
        compact_summary="Guter Wandertag mit leichtem Wind.",
        day_comparison=dc_obj,
    )
    assert "VS. GESTERN" in html, (
        "AC-5 FAIL: 'VS. GESTERN' nicht im Vortag-Bereich gefunden."
    )
    assert "▲" in html, (
        "AC-5 FAIL: Trend-Glyph ▲ nicht gefunden (Satz enthält 'besser')."
    )


# ---------------------------------------------------------------------------
# AC-6: Leerer Summary-Satz wird nicht gerendert
# ---------------------------------------------------------------------------

def test_ac6_no_empty_summary_div():
    """
    GIVEN compact_summary=None, day_comparison vorhanden
    WHEN render_html() called
    THEN kein leerer <div> im Lead-Block (kein '<div></div>' oder '<div> </div>').
    """
    dc_obj = _day_comparison_better_visibility()
    html = _render(compact_summary=None, day_comparison=dc_obj)
    # Kein leeres Tageslage-div
    empty_div = re.compile(r'<div[^>]*>\s*</div>')
    # Wir prüfen speziell im Tageslage-Bereich — wenn TAGESLAGE vorhanden
    # dann darf darunter kein leeres Summary-div sein
    if "TAGESLAGE" in html:
        tageslage_idx = html.index("TAGESLAGE")
        snippet = html[tageslage_idx:tageslage_idx + 300]
        assert not re.search(r'font-weight:500[^>]*>\s*<', snippet), (
            "AC-6 FAIL: Leerer 500-weight-div (Summary-Platzhalter) im Lead-Block gefunden."
        )
