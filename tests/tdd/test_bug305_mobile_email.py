"""
TDD RED — Bug #305: Mobile E-Mail Template falsch.

Screenshot-Befund (iOS Mail, iPhone, 375 px):
  - Tabelle zeigt 15 Spalten horizontal (Time, Temp, Feels, Wind, Gust, Rain,
    Rain%, Sicherheit, Thunder, SnowL, Cloud, CldLow, Visib, UV, 0°Line)
  - Spalten laufen über den Bildschirmrand; rechte Spalten abgeschnitten
  - Tabelle nicht nutzbar

Zwei Root-Causes nachgewiesen:

  RC-1: _render_html_table() erzeugt kein <thead>/<tbody>.
        Die CSS-Regel `table.resp thead { display:none }` greift daher nie —
        der Header bleibt auf Mobile sichtbar und erzeugt Überlauf.

  RC-2: @media-Breakpoint ist 480 px.
        iOS Mail rendert E-Mails mit einer virtuellen Breite von ~600 px
        (Email-Client-Standard). Der Breakpoint feuert nie im nativen Client.

Playwright-Befund (Chrome bei 375 px):
  - table.scrollWidth=674px >> table.clientWidth=335px -> interner Overflow
  - Header-Zeile sichtbar und horizontal, ueberlaeuft Container
  - Datenzellen zwar gestapelt (CSS greift in Chrome), aber Layout inakzeptabel

RED-Zustand: Alle Tests SCHEITERN mit aktuellem Code.
GREEN-Zustand (nach Fix):
  - _render_html_table() produziert <thead><tr>...</tr></thead><tbody>...</tbody>
  - @media-Breakpoint >= 600 px
  - table.scrollWidth <= table.clientWidth bei 375 px (kein interner Overflow)
  - Header-Zeile bei 375 px nicht sichtbar
"""
from __future__ import annotations

import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

_FULL_ROW = {
    "time": "08:00",
    "temp": "15",
    "felt": "11",
    "wind": "12",
    "gust": "30",
    "precip": "0.2",
    "pop": "10",
    "confidence": "ok",
    "thunder": None,
    "snow_limit": "2500",
    "cloud": "50",
    "cloud_low": "30",
    "visibility": "good",
    "uv": "4.2",
    "freeze_lvl": "2710",
}
"""Realistische Tabellenzeile mit allen 15 Feldern aus dem Bug-Screenshot."""


def _build_seg_data():
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=900.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1450.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=14.5,
        ascent_m=820.0,
        descent_m=440.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h * 0.3, wind10m_kmh=15.0,
            precip_1h_mm=0.2, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
        )
        for h in range(8, 14)
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
        wind_max_kmh=22.0, gust_max_kmh=35.0,
        precip_sum_mm=0.8, cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="demo",
    )


def _render_full_html() -> str:
    """HTML mit realistischen 15-Spalten-Daten wie im Bug-Screenshot."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html

    seg_data = _build_seg_data()
    rows = [_FULL_ROW.copy() for _ in range(5)]
    return render_html(
        segments=[seg_data],
        seg_tables=[rows],
        trip_name="KHW 403",
        report_type="morning",
        dc=build_default_display_config(),
        night_rows=[],
        thunder_forecast=None,
        highlights=[],
        changes=None,
        stage_name="KHW_00b: Von Helmhotel nach Sillianer Huette",
        stage_stats={"distance_km": 14.5, "ascent_m": 820},
        multi_day_trend=None,
        compact_summary="Guter Wandertag.",
        daylight=None,
        tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=set(),
    )


# ---------------------------------------------------------------------------
# RC-1: <thead>/<tbody>-Struktur fehlt
# ---------------------------------------------------------------------------

class TestTableStructure:
    """RC-1: _render_html_table() muss <thead>/<tbody> erzeugen."""

    def test_table_has_thead(self):
        """
        AC-1: _render_html_table() muss eine <thead>-Sektion erzeugen.

        GIVEN _render_html_table() mit 15-Spalten-Daten
        WHEN das Ergebnis auf <thead> geprueft wird
        THEN enthaelt es <thead>

        Ohne <thead> greift CSS-Regel 'table.resp thead { display:none }' nicht
        der Header bleibt auf Mobile sichtbar (Bug-RC-1).
        """
        from src.output.renderers.email.html import _render_html_table
        rows = [_FULL_ROW.copy() for _ in range(3)]
        result = _render_html_table(rows, friendly_keys=set())
        assert "<thead>" in result, (
            "FEHLT: <thead>-Tag in _render_html_table()-Ausgabe.\n"
            "Ohne <thead> kann CSS-Regel 'table.resp thead { display:none }' "
            "den Header auf Mobile nicht verstecken -> horizontaler Overflow."
        )

    def test_table_has_tbody(self):
        """
        AC-2: _render_html_table() muss eine <tbody>-Sektion erzeugen.

        GIVEN _render_html_table() mit Datenzeilen
        WHEN das Ergebnis auf <tbody> geprueft wird
        THEN enthaelt es <tbody>
        """
        from src.output.renderers.email.html import _render_html_table
        rows = [_FULL_ROW.copy() for _ in range(3)]
        result = _render_html_table(rows, friendly_keys=set())
        assert "<tbody>" in result, (
            "FEHLT: <tbody>-Tag in _render_html_table()-Ausgabe.\n"
            "Ohne <tbody> ist das stacked-card-Layout auf Mobile unzuverlaessig."
        )

    def test_th_elements_are_inside_thead(self):
        """
        AC-3: Alle <th>-Elemente muessen innerhalb von <thead> liegen.

        GIVEN _render_html_table() mit Datenzeilen
        WHEN die Position von <th> vs. <thead> geprueft wird
        THEN liegt jedes <th> zwischen <thead> und </thead>
        """
        from src.output.renderers.email.html import _render_html_table
        rows = [_FULL_ROW.copy() for _ in range(3)]
        result = _render_html_table(rows, friendly_keys=set())
        thead_start = result.find("<thead>")
        thead_end = result.find("</thead>")
        th_pos = result.find("<th>")
        assert thead_start != -1, "Kein <thead> gefunden"
        assert thead_end > thead_start, "Kein </thead> gefunden"
        assert thead_start < th_pos < thead_end, (
            f"<th> liegt NICHT innerhalb von <thead>: "
            f"thead@{thead_start}, </thead>@{thead_end}, <th>@{th_pos}"
        )

    def test_empty_rows_table_has_thead_tbody(self):
        """
        AC-1/AC-2 Leerfall: _render_html_table([]) muss ebenfalls <thead>/<tbody> erzeugen.

        GIVEN _render_html_table() mit leerer Zeilen-Liste
        WHEN das Ergebnis auf Tabellenstruktur geprueft wird
        THEN enthaelt es <thead> und <tbody> (kein nacktes <tr> auf top-level)
        """
        from src.output.renderers.email.html import _render_html_table
        result = _render_html_table([], friendly_keys=set())
        assert "<thead>" in result, f"Leerfall: kein <thead> — {result}"
        assert "<tbody>" in result, f"Leerfall: kein <tbody> — {result}"


# ---------------------------------------------------------------------------
# RC-2: @media-Breakpoint zu klein fuer iOS Mail
# ---------------------------------------------------------------------------

class TestMediaQueryBreakpoint:
    """RC-2: @media-Breakpoint muss >= 600 px sein."""

    def test_mobile_breakpoint_covers_ios_mail_viewport(self):
        """
        AC-4: @media-Breakpoint muss >= 600 px sein.

        GIVEN ein gerendertes Trip-Briefing-HTML
        WHEN der @media-Block auf den Breakpoint geprueft wird
        THEN ist der Breakpoint mindestens 600px

        iOS Mail rendert E-Mails intern mit ~600 px virtueller Breite
        und skaliert dann. Ein Breakpoint < 600 px feuert dort nie.
        Aktuell: 480 px -> Media Query greift in iOS Mail nicht.
        """
        html = _render_full_html()
        breakpoints = [int(m) for m in re.findall(r'max-width:\s*(\d+)px', html)]
        assert breakpoints, "@media max-width-Regel fehlt komplett"
        max_breakpoint = max(breakpoints)
        assert max_breakpoint >= 600, (
            f"@media-Breakpoint ist {max_breakpoint}px -- zu klein fuer iOS Mail.\n"
            f"iOS Mail virtuelle Renderbreite: ~600px. "
            f"Breakpoint muss >= 600px sein, sonst feuert die Media Query nie."
        )


# ---------------------------------------------------------------------------
# Playwright: Visueller Overflow-Test bei 375 px
# ---------------------------------------------------------------------------

class TestMobileLayoutPlaywright:
    """Playwright-Tests: Layout bei 375 px Viewport (iPhone)."""

    @pytest.fixture(scope="class")
    def html_path(self, tmp_path_factory) -> str:
        html = _render_full_html()
        p = tmp_path_factory.mktemp("bug305") / "email.html"
        p.write_text(html, encoding="utf-8")
        return str(p)

    def test_table_has_no_internal_overflow_at_375px(self, html_path):
        """
        AC-5: Tabelle darf bei 375 px keinen internen Overflow haben.

        GIVEN ein gerendertes HTML mit 15-Spalten-Tabelle
        WHEN die Seite in einem 375-px-Viewport (iPhone) geoeffnet wird
        THEN ist table.scrollWidth <= table.clientWidth

        Aktuell: scrollWidth=674px >> clientWidth=335px
        -> 339px versteckter Inhalt -> auf iOS Mail als horizontaler Scroll sichtbar.
        Screenshot gespeichert nach /tmp/bug305_mobile_375px_ist.png
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                viewport={"width": 375, "height": 812},
                device_scale_factor=3,
            )
            page = context.new_page()
            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")

            metrics = page.evaluate("""() => {
                const tables = Array.from(document.querySelectorAll("table.resp"));
                return tables.map(t => ({
                    scrollWidth: t.scrollWidth,
                    clientWidth: t.clientWidth,
                    overflow: t.scrollWidth - t.clientWidth,
                }));
            }""")
            page.screenshot(path="/tmp/bug305_mobile_375px_ist.png", full_page=False)
            browser.close()

        assert metrics, "Keine table.resp-Elemente im gerenderten HTML gefunden"
        for i, tbl in enumerate(metrics):
            assert tbl["scrollWidth"] <= tbl["clientWidth"], (
                f"Tabelle {i}: interner Overflow von {tbl['overflow']}px bei 375px Viewport.\n"
                f"  scrollWidth={tbl['scrollWidth']}px, clientWidth={tbl['clientWidth']}px\n"
                f"  Screenshot: /tmp/bug305_mobile_375px_ist.png\n"
                f"  Dieser Overflow entspricht dem Screenshot in Bug #305:\n"
                f"  15 Spalten (Time, Temp, Feels, Wind, Gust, Rain, Rain%,\n"
                f"  Sicherheit, Thunder, SnowL, Cloud, CldLow, Visib, UV, 0 Grad-Line)\n"
                f"  laufen horizontal ueber den Bildschirmrand."
            )

    def test_header_row_hidden_at_375px(self, html_path):
        """
        AC-6: Header-Zeile muss bei 375 px versteckt sein.

        GIVEN ein gerendertes HTML mit Tabellen-Header
        WHEN die Seite bei 375 px geoeffnet wird
        THEN hat kein <th>-Element eine sichtbare Hoehe > 0

        Aktuell: <th>-Elemente sind sichtbar und horizontal (kein <thead>
        im HTML -> CSS-Regel 'thead { display:none }' greift nicht).
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                viewport={"width": 375, "height": 812},
            )
            page = context.new_page()
            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")

            th_visible = page.evaluate("""() => {
                const ths = Array.from(document.querySelectorAll("table.resp th"));
                return ths.map(th => ({
                    text: th.textContent.trim(),
                    offsetHeight: th.offsetHeight,
                    visible: th.offsetHeight > 0,
                }));
            }""")
            browser.close()

        visible_headers = [th for th in th_visible if th["visible"]]
        assert not visible_headers, (
            f"Header-Zeile sichtbar bei 375px -- {len(visible_headers)} sichtbare <th>-Elemente:\n"
            + "\n".join(
                f"  - '{th['text']}' (Hoehe: {th['offsetHeight']}px)"
                for th in visible_headers
            )
            + "\n\nRoot Cause: Kein <thead>-Tag -> CSS-Regel greift nicht."
        )
