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
        th_pos = result.find("<th ")
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
        AC-4 (Mobile-First): Desktop-@media-Breakpoint muss >= 601px sein.

        GIVEN ein gerendertes Trip-Briefing-HTML (Mobile-First-Design)
        WHEN der @media-Block auf den Desktop-Breakpoint geprueft wird
        THEN gibt es einen @media (min-width) >= 601px (Desktop einblenden)

        Mobile ist der Default — Desktop wird erst ab min-width eingeblendet.
        Sinn: Mobil (< 601px) greift kein @media, Desktop erst darueber.
        """
        html = _render_full_html()
        breakpoints = [int(m) for m in re.findall(r'min-width:\s*(\d+)px', html)]
        assert breakpoints, "@media min-width-Regel fehlt komplett (Mobile-First erwartet)"
        max_breakpoint = max(breakpoints)
        assert max_breakpoint >= 601, (
            f"Desktop @media-Breakpoint ist {max_breakpoint}px -- erwartet >= 601px.\n"
            f"Mobile-First: Mobil ist Default, Desktop wird erst ab min-width eingeblendet."
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
                const tables = Array.from(document.querySelectorAll('table[data-table="resp"]'));
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
                const ths = Array.from(document.querySelectorAll('table[data-table="resp"] th'));
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


# ---------------------------------------------------------------------------
# v2 Fix: Dual-Mode-Layout — desktop-only / mobile-compact
# ---------------------------------------------------------------------------

class TestMobileCompactLayout:
    """AC-7..AC-10: HTML-Struktur und CSS für Dual-Mode-Rendering."""

    def test_desktop_only_wrapper_exists(self):
        """
        AC-7: render_html() muss mindestens einen desktop-only-Wrapper mit table.resp erzeugen.

        GIVEN render_html() mit einem Segment
        WHEN das HTML auf Wrapper-Klassen geprüft wird
        THEN enthält es 'desktop-only' in der HTML-Body-Sektion mit einer <table> darin

        Ohne diesen Wrapper wird die Tabelle auf Mobile nie ausgeblendet.
        """
        html = _render_full_html()
        body_start = html.find("<body>")
        body = html[body_start:] if body_start != -1 else html
        assert "desktop-only" in body, (
            "FEHLT: Kein 'desktop-only'-Wrapper im HTML-Body.\n"
            "Ohne diesen Wrapper kann die Tabelle auf Mobile nicht ausgeblendet werden."
        )
        # desktop-only must contain a <table> before mobile-compact
        desktop_idx = body.find("desktop-only")
        table_after = body.find("<table", desktop_idx)
        mc_idx = body.find("mobile-compact", desktop_idx)
        assert table_after != -1, "Kein <table> nach desktop-only in Body gefunden"
        assert mc_idx == -1 or table_after < mc_idx, (
            f"<table> liegt NICHT vor mobile-compact nach desktop-only.\n"
            f"desktop-only@{desktop_idx}, table@{table_after}, mobile-compact@{mc_idx}"
        )

    def test_mobile_compact_wrapper_exists(self):
        """
        AC-8: render_html() muss mindestens einen mobile-compact-Wrapper erzeugen.

        GIVEN render_html() mit einem Segment
        WHEN das HTML auf Mobile-Wrapper geprüft wird
        THEN enthält es 'mobile-compact'

        Ohne diesen Wrapper gibt es keine kompakte Mobile-Ansicht.
        """
        html = _render_full_html()
        assert "mobile-compact" in html, (
            "FEHLT: Kein 'mobile-compact'-Wrapper im HTML.\n"
            "Ohne diesen Wrapper gibt es keine kompakte Mobile-Ansicht."
        )

    def test_css_hides_desktop_on_mobile(self):
        """
        AC-9 (Mobile-First): Basis-CSS (vor @media) muss .desktop-only verstecken.

        GIVEN render_html()
        WHEN der CSS-Block VOR dem ersten @media-Block geprüft wird (Basis-CSS)
        THEN enthält die Basis-Regel '.desktop-only' mit 'none' (standardmäßig versteckt)

        Mobile-First: Desktop ist standardmäßig versteckt, nur per @media eingeblendet.
        Ohne diese Basis-Regel bleibt Desktop in @media-ignorierenden Clients sichtbar.
        """
        html = _render_full_html()
        style_start = html.find("<style")
        media_start = html.find("@media", style_start)
        assert media_start != -1, "Kein @media-Block gefunden"
        base_css = html[style_start:media_start].replace(" ", "")
        do = re.search(r"\.desktop-only\{[^}]*\}", base_css)
        assert do is not None, (
            "FEHLT: '.desktop-only'-Regel im Basis-CSS (vor @media) nicht gefunden.\n"
            "Mobile-First erwartet: .desktop-only { display: none; } als Basis."
        )
        assert "none" in do.group(0), (
            f"FEHLT: 'none' in '.desktop-only'-Basis-Regel nicht gefunden.\n"
            f"Gefunden: {do.group(0)!r}"
        )

    def test_css_shows_compact_on_mobile(self):
        """
        AC-10 (Mobile-First): Basis-CSS (vor @media) muss .mobile-compact einblenden.

        GIVEN render_html()
        WHEN der CSS-Block VOR dem ersten @media-Block geprüft wird (Basis-CSS)
        THEN enthält die Basis-Regel '.mobile-compact' mit 'block' (standardmäßig sichtbar)

        Mobile-First: Mobil-Variante ist der Default, Desktop wird per @media eingeblendet.
        Ohne diese Basis-Regel bleibt die Compact-Ansicht in Gmail-artigen Clients versteckt.
        """
        html = _render_full_html()
        style_start = html.find("<style")
        media_start = html.find("@media", style_start)
        assert media_start != -1, "Kein @media-Block gefunden"
        base_css = html[style_start:media_start].replace(" ", "")
        mc = re.search(r"\.mobile-compact\{[^}]*\}", base_css)
        assert mc is not None, (
            "FEHLT: '.mobile-compact'-Regel im Basis-CSS (vor @media) nicht gefunden.\n"
            "Mobile-First erwartet: .mobile-compact { display: block; } als Basis."
        )
        assert "block" in mc.group(0), (
            f"FEHLT: 'block' in '.mobile-compact'-Basis-Regel nicht gefunden.\n"
            f"Gefunden: {mc.group(0)!r}"
        )

    def test_mobile_compact_has_time_slots(self):
        """
        AC-8b: mobile-compact muss Zeitstempel-Einträge aus den Rows enthalten.

        GIVEN render_html() mit Rows die Zeitstempel haben
        WHEN das HTML auf mobile-compact geprüft wird
        THEN enthält der mobile-compact-Bereich mindestens einen Zeitstempel

        Wenn der mobile-compact-Block leer ist, gibt es auf Mobile gar nichts zu sehen.
        """
        html = _render_full_html()
        mc_start = html.find("mobile-compact")
        assert mc_start != -1, "Kein mobile-compact gefunden"
        mc_block = html[mc_start:mc_start + 5000]
        has_time = any(f"{h:02d}:00" in mc_block for h in range(6, 16))
        assert has_time, (
            "FEHLT: Kein Zeitstempel im mobile-compact-Block.\n"
            "Der Block ist entweder leer oder enthält keine Row-Daten."
        )


class TestMobileCompactLayoutPlaywright:
    """AC-11..AC-13: Playwright-Tests bei 375px Viewport."""

    @pytest.fixture(scope="class")
    def html_path(self, tmp_path_factory) -> str:
        html = _render_full_html()
        p = tmp_path_factory.mktemp("bug305v2") / "email_v2.html"
        p.write_text(html, encoding="utf-8")
        return str(p)

    def test_desktop_only_hidden_at_375px(self, html_path):
        """
        AC-11: .desktop-only-Elemente müssen bei 375px Viewport unsichtbar sein.

        GIVEN gerendertes HTML bei 375px Viewport
        WHEN Sichtbarkeit von .desktop-only geprüft wird
        THEN hat kein .desktop-only-Element offsetHeight > 0
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 375, "height": 812})
            page = context.new_page()
            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")
            heights = page.evaluate("""() => {
                return Array.from(document.querySelectorAll(".desktop-only"))
                    .map(el => ({ tag: el.tagName, height: el.offsetHeight }));
            }""")
            browser.close()

        assert heights, "Keine .desktop-only-Elemente gefunden — AC-7 muss zuerst grün sein."
        visible = [h for h in heights if h["height"] > 0]
        assert not visible, (
            f"desktop-only sichtbar bei 375px: {visible}\n"
            "CSS '.desktop-only { display:none !important }' fehlt oder greift nicht."
        )

    def test_mobile_compact_visible_at_375px(self, html_path):
        """
        AC-12: .mobile-compact-Elemente müssen bei 375px Viewport sichtbar sein.

        GIVEN gerendertes HTML bei 375px Viewport
        WHEN Sichtbarkeit von .mobile-compact geprüft wird
        THEN hat mindestens ein .mobile-compact-Element offsetHeight > 0
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 375, "height": 812})
            page = context.new_page()
            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")
            heights = page.evaluate("""() => {
                return Array.from(document.querySelectorAll(".mobile-compact"))
                    .map(el => ({ tag: el.tagName, height: el.offsetHeight }));
            }""")
            page.screenshot(path="/tmp/bug305v2_mobile_375px.png", full_page=True)
            browser.close()

        assert heights, "Keine .mobile-compact-Elemente gefunden — AC-8 muss zuerst grün sein."
        visible = [h for h in heights if h["height"] > 0]
        assert visible, (
            "Kein .mobile-compact-Element sichtbar bei 375px.\n"
            "CSS '.mobile-compact { display:block !important }' fehlt oder greift nicht.\n"
            "Screenshot: /tmp/bug305v2_mobile_375px.png"
        )

    def test_mobile_compact_no_overflow_at_375px(self, html_path):
        """
        AC-13: .mobile-compact-Elemente dürfen bei 375px keinen horizontalen Overflow haben.

        GIVEN gerendertes HTML bei 375px Viewport
        WHEN scrollWidth vs. clientWidth geprüft wird
        THEN ist für alle .mobile-compact scrollWidth <= clientWidth
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 375, "height": 812})
            page = context.new_page()
            page.goto(f"file://{html_path}")
            page.wait_for_load_state("networkidle")
            metrics = page.evaluate("""() => {
                return Array.from(document.querySelectorAll(".mobile-compact"))
                    .map(el => ({
                        scrollWidth: el.scrollWidth,
                        clientWidth: el.clientWidth,
                        overflow: el.scrollWidth - el.clientWidth,
                    }));
            }""")
            browser.close()

        assert metrics, "Keine .mobile-compact-Elemente gefunden"
        for i, el in enumerate(metrics):
            assert el["scrollWidth"] <= el["clientWidth"], (
                f"mobile-compact[{i}]: Overflow {el['overflow']}px bei 375px.\n"
                f"  scrollWidth={el['scrollWidth']}px, clientWidth={el['clientWidth']}px\n"
                f"  Screenshot: /tmp/bug305v2_mobile_375px.png"
            )


# ---------------------------------------------------------------------------
# Bug #463 / Issue #538 — include_header-Parameter (fehlende Tests)
# AC-1: include_header=True + sichtbare Spalten → Header mit "Zeit" vor Daten
# AC-2: Night-Rows via render_html → Header vorhanden
# AC-3: Leere Rows + include_header=True → kein Header
# AC-4: include_header=False (Default) → kein Header-Div
# AC-5: Nur sichtbare Spalten im Header
# ---------------------------------------------------------------------------

_HEADER_TEST_ROW = {
    "time": "08:00",
    "temp": "15",
    "wind": "12",
    "gust": "30",
    "precip": "0.2",
    "pop": "10",
    "confidence": "ok",
    "thunder": None,
    "snow_limit": None,
    "cloud": "50",
    "cloud_low": None,
    "visibility": None,
    "uv": None,
    "freeze_lvl": None,
}


class TestMobileCompactHeader:
    """AC-1..AC-5: include_header-Parameter in _render_mobile_compact_rows (Issue #538)."""

    def test_header_present_when_include_header_true(self):
        """
        AC-1: include_header=True + sichtbare Spalten → Header-Element mit Label "Zeit".

        GIVEN _render_mobile_compact_rows mit einer Zeile und include_header=True
        WHEN  das Ergebnis ausgewertet wird
        THEN  enthält es ein Header-Element mit dem Label "Zeit" (font-size:11px)
        """
        from src.output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            [_HEADER_TEST_ROW], friendly_keys=set(), include_header=True
        )
        assert "Zeit" in result, (
            "Header-Label 'Zeit' fehlt bei include_header=True"
        )
        assert "font-size:11px" in result, (
            "Header-Div (font-size:11px) fehlt bei include_header=True"
        )

    def test_header_appears_before_data_rows(self):
        """
        AC-1: Header-Div (font-size:11px) muss vor Daten-Rows (font-size:12px) erscheinen.

        GIVEN _render_mobile_compact_rows mit include_header=True
        WHEN  das Ergebnis auf Reihenfolge geprüft wird
        THEN  liegt 'font-size:11px' (Header) vor 'font-size:12px' (Daten-Row)
        """
        from src.output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            [_HEADER_TEST_ROW], friendly_keys=set(), include_header=True
        )
        header_pos = result.find("font-size:11px")
        data_pos = result.find("font-size:12px")
        assert header_pos != -1, "Kein Header (font-size:11px) im Output"
        assert data_pos != -1, "Keine Daten-Row (font-size:12px) im Output"
        assert header_pos < data_pos, (
            f"Header@{header_pos} liegt NACH Daten-Row@{data_pos} — Header muss zuerst kommen"
        )

    def test_no_header_when_rows_empty(self):
        """
        AC-3: Leere Rows-Liste + include_header=True → kein Header, leerer/kurzer String.

        GIVEN _render_mobile_compact_rows mit rows=[] und include_header=True
        WHEN  das Ergebnis geprüft wird
        THEN  enthält es kein "Zeit"-Label (kein Header erzeugt)
        """
        from src.output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows([], friendly_keys=set(), include_header=True)
        assert "Zeit" not in result, (
            f"Header unerwartet erzeugt bei leerer Rows-Liste — Output: {result!r}"
        )

    def test_no_header_when_include_header_false(self):
        """
        AC-4: include_header=False (Default) → kein Header-Div.

        GIVEN _render_mobile_compact_rows mit Daten-Rows und include_header=False
        WHEN  das Ergebnis auf Header geprüft wird
        THEN  enthält es kein Header-Div mit font-size:11px
              (Daten-Rows selbst haben font-size:12px → unterscheidbar)
        """
        from src.output.renderers.email.html import _render_mobile_compact_rows

        result = _render_mobile_compact_rows(
            [_HEADER_TEST_ROW], friendly_keys=set(), include_header=False
        )
        assert "font-size:11px" not in result, (
            "Header-Div (font-size:11px) unerwartet vorhanden bei include_header=False"
        )

    def test_only_allowed_columns_in_header(self):
        """
        AC-5: Wenn allowed_col_keys gesetzt, erscheinen nur diese Spalten im Header.

        GIVEN _render_mobile_compact_rows mit allowed_col_keys={"temp", "wind"}
        WHEN  include_header=True gerendert wird
        THEN  enthält der Header "Temp" und "Wind",
              aber nicht "Thunder" (nicht in allowed_col_keys)
        """
        from src.output.renderers.email.html import _render_mobile_compact_rows

        rows = [_HEADER_TEST_ROW]
        result = _render_mobile_compact_rows(
            rows,
            friendly_keys=set(),
            allowed_col_keys={"temp", "wind"},
            include_header=True,
        )
        assert "Zeit" in result, "Header-Label 'Zeit' fehlt"
        assert "Temp" in result, "Spalten-Label 'Temp' fehlt im Header"
        assert "Wind" in result, "Spalten-Label 'Wind' fehlt im Header"
        assert "Thunder" not in result, (
            "'Thunder' darf nicht im Header erscheinen — nicht in allowed_col_keys"
        )
