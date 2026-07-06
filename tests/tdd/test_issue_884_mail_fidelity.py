"""Issue #884 — E-Mail-Renderer Fidelity: 1:1-Übereinstimmung mit Claude-Design-Vorlage.

TDD RED: Alle Tests schlagen heute fehl, weil html.py noch nicht die neuen Design-Elemente
implementiert (zweispaltiger Header, Gruppen-Header-Tabelle, Risk-Dot, Antwort-Kommandos-Sektion,
geteilter Footer, mobile EmailHourList, etc.).

KEINE Mocks/patch/MagicMock — echte render_html/render_email-Aufrufe.
Spec: docs/specs/modules/issue_884_mail_fidelity.md
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


_TZ = ZoneInfo("Europe/Berlin")

# ---------------------------------------------------------------------------
# Gemeinsame Test-Daten Factories (mock-frei)
# ---------------------------------------------------------------------------

def _make_dp(*, wind_kmh: float = 8.0, gust_kmh: float = 15.0, thunder_pct: float = 0.0):
    from app.models import ForecastDataPoint, ThunderLevel
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=12.0, wind10m_kmh=wind_kmh, gust_kmh=gust_kmh,
        precip_1h_mm=0.0, pop_pct=10,
        cloud_total_pct=60,
        thunder_level=ThunderLevel.MED if thunder_pct > 20 else ThunderLevel.NONE,
        wind_chill_c=11.0, cape_jkg=0.0, visibility_m=20000.0,
    )


def _make_dp_wind_high():
    """Wind 25 km/h — überschreitet 20er-Schwelle → soll fett+orange."""
    from app.models import ForecastDataPoint, ThunderLevel
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=10.0, wind10m_kmh=25.0, gust_kmh=18.0,
        precip_1h_mm=0.0, pop_pct=5,
        cloud_total_pct=40, thunder_level=ThunderLevel.NONE,
        wind_chill_c=9.0, cape_jkg=0.0, visibility_m=30000.0,
    )


def _make_seg_data(dp=None, *, segment_id=1):
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    if dp is None:
        dp = _make_dp()
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=800.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1400.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=6.5, ascent_m=600.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.2, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=16.0, temp_avg_c=13.0,
        wind_max_kmh=dp.wind10m_kmh or 8.0, gust_max_kmh=dp.gust_kmh or 15.0,
        precip_sum_mm=dp.precip_1h_mm or 0.0, cloud_avg_pct=60, humidity_avg_pct=65,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=11.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_dc(enabled: set[str] | None = None):
    from app.metric_catalog import build_default_display_config
    dc = build_default_display_config()
    active = enabled or {"temperature", "wind", "gust", "precipitation", "rain_probability", "thunder"}
    for mc in dc.metrics:
        mc.enabled = mc.metric_id in active
    return dc


def _make_trend_stages(*, with_thunder: bool = False):
    """Multi-day-trend-Daten für Ausblick-Sektion."""
    base = [
        {"weekday": "Do", "name": "Etappe 2", "temp_min_c": 4.0, "temp_max_c": 14.0,
         "precip_mm": 0.0, "wind_kmh": 10, "wind_dir": "NW", "thunder_pct_max": 0},
        {"weekday": "Fr", "name": "Etappe 3", "temp_min_c": 2.0, "temp_max_c": 11.0,
         "precip_mm": 2.5, "wind_kmh": 15, "wind_dir": "E", "thunder_pct_max": 5},
    ]
    if with_thunder:
        base.append({
            "weekday": "Sa", "name": "Etappe 4", "temp_min_c": -1.0, "temp_max_c": 9.0,
            "precip_mm": 8.0, "wind_kmh": 28, "wind_dir": "SE", "thunder_pct_max": 35,
        })
    return base


def _render(dp=None, *, with_trend=True, with_thunder=False,
            compact_summary: str | None = None,
            stage_stats: dict | None = None,
            email_format: str = "full"):
    from src.output.renderers.email import render_email
    from src.output.renderers.email.helpers import dp_to_row
    from src.output.tokens.dto import TokenLine

    if dp is None:
        dp = _make_dp()
    dc = _make_dc()
    row = dp_to_row(dp, dc, tz=_TZ)
    seg = _make_seg_data(dp=dp)
    tl = TokenLine(
        trip_name="Karnischer Höhenweg",
        report_type="morning",
        stage_name="Helmhotel → Sillianer Hütte",
    )
    _stage_stats = stage_stats or {
        "distance_km": 7.9, "ascent_m": 603.0, "descent_m": 0.0, "max_elevation_m": 2447.0,
    }
    trend = _make_trend_stages(with_thunder=with_thunder) if with_trend else None
    return render_email(
        tl,
        segments=[seg],
        seg_tables=[[row]],
        display_config=dc,
        tz=_TZ,
        friendly_keys=set(),
        email_format=email_format,
        stage_stats=_stage_stats,
        compact_summary=compact_summary,
        multi_day_trend=trend,
    )


# ---------------------------------------------------------------------------
# AC-1: Header zweispaltig — rechts "GREGOR ZWANZIG", Hintergrund #fbfaf6
# ---------------------------------------------------------------------------

def test_header_has_gregor_zwanzig_brand():
    """AC-1 RED: Header muss 'GREGOR ZWANZIG' als rechtsbündiges Brand-Label enthalten.

    IST: Kein 'GREGOR ZWANZIG' im Header.
    SOLL: Mono-Text 'GREGOR ZWANZIG' in color:#9a978d rechts im Header.
    """
    html, _plain = _render()
    assert "GREGOR ZWANZIG" in html, (
        "AC-1 RED: 'GREGOR ZWANZIG' fehlt im gerenderten HTML. "
        "JSX: <EmailEyebrow>GREGOR ZWANZIG</EmailEyebrow> in rechter Header-Spalte."
    )


def test_header_background_fbfaf6():
    """AC-1 RED: Header-Hintergrund muss #fbfaf6 sein (nicht #f6f4ee = G_PAPER).

    IST: background:#f6f4ee (G_PAPER) im .header.
    SOLL: background:#fbfaf6 (G_HEADER_BG, heller).
    """
    html, _plain = _render()
    assert "#fbfaf6" in html, (
        "AC-1 RED: Hintergrundfarbe #fbfaf6 fehlt. "
        "Aktuell: #f6f4ee (G_PAPER). JSX: EmailPreview header background:#fbfaf6."
    )


def test_header_eyebrow_morgen_briefing():
    """AC-1 RED: Eyebrow 'MORGEN-BRIEFING' muss im Header erscheinen.

    IST: Kein 'MORGEN-BRIEFING'-Eyebrow.
    SOLL: Mono 10px '#c45a2a' Eyebrow 'MORGEN-BRIEFING · {stage_code}'.
    """
    html, _plain = _render()
    assert "MORGEN-BRIEFING" in html, (
        "AC-1 RED: Eyebrow 'MORGEN-BRIEFING' fehlt im Header. "
        "JSX: EmailEyebrow 'MORGEN-BRIEFING · {stage.code}'."
    )


def test_header_stats_grid_border_separator():
    """AC-1 RED: Stats-Grid-Trennlinie muss border-right:1px solid #e6e1d3 haben.

    IST: Stats-Zellen ohne #e6e1d3-Trennlinie.
    SOLL: border-right:1px solid #e6e1d3 zwischen Stats-Zellen.
    """
    html, _plain = _render(stage_stats={
        "distance_km": 7.9, "ascent_m": 603.0, "descent_m": 0.0, "max_elevation_m": 2447.0,
    })
    assert "#e6e1d3" in html, (
        "AC-1 RED: Stats-Grid-Trennlinie '#e6e1d3' fehlt. "
        "JSX: EmailStat border-right:1px solid #e6e1d3."
    )


# ---------------------------------------------------------------------------
# AC-4: Highlighting — Wind > 20 km/h fett + #c2410c
# ---------------------------------------------------------------------------

def test_wind_above_threshold_gets_highlight_color():
    """AC-4 RED: Wind 25 km/h muss in der Datenzelle fett + #c2410c erscheinen.

    IST: Keine Highlighting-Logik für Wind-Schwellen in der Datentabelle.
    SOLL: Wenn wind > 20 km/h → font-weight:700;color:#c2410c in der Wind-Zelle.
    """
    dp = _make_dp_wind_high()
    html, _plain = _render(dp=dp)
    assert "#c2410c" in html, (
        "AC-4 RED: Highlighting-Farbe #c2410c fehlt bei Wind=25 km/h. "
        "JSX: dCellStyle('center', wind>20, wind>20 ? '#c2410c' : null)."
    )


def test_wind_above_threshold_gets_bold():
    """AC-4 RED: Wind 25 km/h muss font-weight:700 in der Wind-Zelle haben."""
    dp = _make_dp_wind_high()
    html, _plain = _render(dp=dp)
    # Prüfen ob font-weight:700 zusammen mit c2410c vorkommt
    snippet = re.search(r'font-weight:700[^>]*>25<|>25<[^<]*font-weight:700|c2410c[^>]*font-weight:700|font-weight:700[^>]*c2410c', html)
    assert snippet is not None or ("font-weight:700" in html and "#c2410c" in html), (
        "AC-4 RED: font-weight:700 + #c2410c fehlt für Wind=25 km/h. "
        "JSX: fontWeight:bold wenn wind>20."
    )


# ---------------------------------------------------------------------------
# AC-6: Wetter am Ziel — eigene Sektion mit accent-Eyebrow
# ---------------------------------------------------------------------------

def test_destination_weather_section_has_accent_eyebrow():
    """AC-6 RED: Ziel-Sektion muss Eyebrow 'ANKUNFT · WETTER AM ZIEL' haben.

    IST: Ziel-Segment wird mit '🏁 Wetter am Ziel: ...' als <h3> dargestellt.
    SOLL: Eyebrow 'ANKUNFT · WETTER AM ZIEL' in color:#c45a2a (accent).
    """
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    from src.output.renderers.email import render_email
    from src.output.renderers.email.helpers import dp_to_row
    from src.output.tokens.dto import TokenLine

    dp = _make_dp()
    dc = _make_dc()
    row = dp_to_row(dp, dc, tz=_TZ)

    # Ziel-Segment hat segment_id="Ziel"
    seg_ziel = TripSegment(
        segment_id="Ziel",
        start_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=2447.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=2447.0),
        start_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 15, 0, tzinfo=timezone.utc),
        duration_hours=3.0, distance_km=0.0, ascent_m=0.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.2, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=14.0, temp_avg_c=12.0,
        wind_max_kmh=8.0, gust_max_kmh=15.0, precip_sum_mm=0.0,
        cloud_avg_pct=60, humidity_avg_pct=65,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=11.0,
    )
    seg_data_ziel = SegmentWeatherData(
        segment=seg_ziel, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )

    tl = TokenLine(trip_name="Karnischer Höhenweg", report_type="morning", stage_name="Test")
    html, _plain = render_email(
        tl,
        segments=[_make_seg_data(), seg_data_ziel],
        seg_tables=[[row], [row]],
        display_config=dc, tz=_TZ, friendly_keys=set(),
    )

    assert "ANKUNFT" in html or "WETTER AM ZIEL" in html, (
        "AC-6 RED: Eyebrow 'ANKUNFT · WETTER AM ZIEL' fehlt für Ziel-Segment. "
        "IST: '<h3>🏁 Wetter am Ziel: ...' "
        "SOLL: accent-Eyebrow 'ANKUNFT · WETTER AM ZIEL' in eigener Sektion mit #fbfaf6 bg."
    )


# ---------------------------------------------------------------------------
# AC-7: Folge-Etappen — Risk-Dot (border-radius:50%)
# ---------------------------------------------------------------------------

def test_upcoming_rows_have_riskdot():
    """AC-7 RED: Ausblick-Block muss einen Risk-Dot mit border-radius:50% haben.

    IST: Ausblick als 4-Spalten-Tabelle (TEMP/REGEN/WIND/GEWITTER) ohne Risk-Dot.
    SOLL: Jede Folge-Etappe mit <span border-radius:50%> als Risk-Dot (farbiger Kreis).
    """
    html, _plain = _render(with_trend=True)
    assert "border-radius:50%" in html, (
        "AC-7 RED: Risk-Dot (border-radius:50%) fehlt im Ausblick-Block. "
        "JSX: RiskDot = <span style='border-radius:50%;width:10px;height:10px;background:{color}'/>."
    )


def test_upcoming_rows_have_thunder_badge_when_thunder():
    """AC-7 RED: Ausblick-Zeile mit Gewitter muss einen ⚡ Gewitter-Badge haben.

    IST: Gewitter-Zelle zeigt colored square + Wort (4-Spalten-Format).
    SOLL: '⚡ Gewitter {zeitangabe}' Badge in #b91c1c background.
    """
    html, _plain = _render(with_trend=True, with_thunder=True)
    # Badge-Hintergrund muss rgba(185,28,28,...) oder #b91c1c sein
    has_thunder_badge = (
        "rgba(185,28,28" in html
        or "b91c1c" in html.lower()
        or "⚡ Gewitter" in html
    )
    assert has_thunder_badge, (
        "AC-7 RED: Gewitter-Badge fehlt in Ausblick-Zeile mit thunder_pct_max=35. "
        "JSX: <span style='color:#b91c1c;background:rgba(185,28,28,0.09)'>⚡ Gewitter {time}</span>."
    )


# ---------------------------------------------------------------------------
# AC-8: Antwort-Kommandos — eigene Sektion
# ---------------------------------------------------------------------------

def test_kommandos_section_has_eyebrow():
    """AC-8: Antwort-Kommandos muss in eigenständigem hellen Block (nicht dark footer) erscheinen."""
    html, _plain = _render()
    # Eyebrow vorhanden
    assert "Antwort-Kommandos" in html, (
        "AC-8: 'Antwort-Kommandos' fehlt. "
        "JSX: Eigenständiger Block mit Eyebrow + #fbfaf6 Hintergrund."
    )
    # Steht im hellen Block, NICHT im dunklen Footer
    dark_footer_start = html.find("background:#1d1c1a")
    kommandos_pos = html.find("Antwort-Kommandos")
    assert dark_footer_start < 0 or kommandos_pos < dark_footer_start, (
        "AC-8: 'Antwort-Kommandos' erscheint NACH dem Dark-Footer — gehört in die helle Sektion."
    )


def test_kommandos_section_has_all_six_commands():
    """AC-8 RED: Kommandos-Sektion muss alle 6 Einträge enthalten (PAUSE 2d, SKIP, STOP, STATUS, CONFIG, HELP)."""
    html, _plain = _render()
    for cmd in ["PAUSE 2d", "SKIP", "STOP", "STATUS", "CONFIG", "HELP"]:
        assert cmd in html, (
            f"AC-8 RED: Kommando '{cmd}' fehlt im Kommandos-Block. "
            "JSX: 6 Einträge in 3×2-Grid-Sektion."
        )


def test_kommandos_hint_text():
    """AC-8 RED: Hinweistext 'Antworte auf diese E-Mail' muss vorhanden sein."""
    html, _plain = _render()
    assert "Antworte auf diese E-Mail" in html, (
        "AC-8 RED: Hinweistext 'Antworte auf diese E-Mail mit einem Schlüsselwort.' fehlt. "
        "JSX: Unterhalb des Kommandos-Grid."
    )


# ---------------------------------------------------------------------------
# AC-9: Footer zweigeteilt — GREGOR ZWANZIG + Link-Zeile
# ---------------------------------------------------------------------------

def test_footer_has_gregor_zwanzig_in_white():
    """AC-9 RED: Footer muss 'GREGOR ZWANZIG' in color:#fff (weiß) enthalten.

    IST: Footer ohne 'GREGOR ZWANZIG' Brand-Label in weiß.
    SOLL: Obere Footer-Zeile: 'GREGOR ZWANZIG' in color:#fff, fontWeight:600.
    """
    html, _plain = _render()
    has_brand_white = bool(re.search(
        r'color:#fff[^>]*>GREGOR ZWANZIG|GREGOR ZWANZIG[^<]*</[^>]+>[^<]*color:#fff',
        html, re.S
    ))
    # Einfachere Alternative: beide Elemente müssen gleichzeitig im Footer-Block erscheinen
    if not has_brand_white:
        # Prüfe ob #1d1c1a (footer bg) und GREGOR ZWANZIG nah beieinander liegen
        footer_match = re.search(r'1d1c1a.{0,2000}GREGOR ZWANZIG', html, re.S)
        has_brand_white = footer_match is not None
    assert has_brand_white, (
        "AC-9 RED: 'GREGOR ZWANZIG' in Footer (bg #1d1c1a) mit color:#fff fehlt. "
        "JSX: Footer obere Zeile: 'GREGOR ZWANZIG' color:#fff, fontWeight:600."
    )


def test_footer_has_link_section_trip_uebersicht():
    """AC-9 RED: Footer muss 'Trip-Übersicht öffnen →' in der Link-Zeile enthalten.

    IST: Kein 'Trip-Übersicht'-Link im Footer.
    SOLL: Untere Footer-Zeile mit 'Trip-Übersicht öffnen →' in color:#c45a2a.
    """
    html, _plain = _render()
    assert "Trip-Übersicht" in html or "Trip-Uebersicht" in html, (
        "AC-9 RED: 'Trip-Übersicht öffnen →' Link-Label fehlt im Footer. "
        "JSX: Footer Link-Zeile: 'Trip-Übersicht öffnen →' color:#c45a2a."
    )


def test_footer_border_top_separator():
    """AC-9 RED: Footer muss border-top:1px solid #3a3835 als Trennlinie enthalten.

    IST: Kein #3a3835 im Footer.
    SOLL: border-top:1px solid #3a3835 zwischen Brand-Zeile und Link-Zeile.
    """
    html, _plain = _render()
    assert "#3a3835" in html, (
        "AC-9 RED: Footer-Trennlinie '#3a3835' fehlt. "
        "JSX: border-top:1px solid #3a3835 zwischen oberer und unterer Footer-Zeile."
    )


# ---------------------------------------------------------------------------
# AC-10: Mode-Matrix-Nicht-Regression
# ---------------------------------------------------------------------------

def test_mode_matrix_no_regression():
    """AC-10: Mode-Matrix-Vertragstest muss nach der Implementierung grün bleiben.

    Dies ist ein Nicht-Regressions-Test — er ist HEUTE bereits grün und soll
    es nach den Renderer-Änderungen bleiben.
    """
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/tdd/test_issue_811_mode_matrix.py", "-v", "--tb=short", "-q"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        "AC-10: Mode-Matrix-Vertragstest fehlgeschlagen nach Renderer-Änderungen.\n"
        f"STDOUT: {result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout}\n"
        f"STDERR: {result.stderr[-500:]}"
    )
