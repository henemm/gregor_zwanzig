"""TDD RED — Issue #956, Teile A/B/E: visuelle Layout-Bugs im Trip-Briefing-HTML.

PO-Vorgabe (Issue #956): "Du musst die TDD RED Tests visuell erstellen.
Code-Tests sind hier nicht erlaubt." → Für die sichtbaren Layout-Bugs (A/B/E)
ist ein `assert 'x' in html`-Test verboten. Stattdessen wird das von
`render_html()` erzeugte HTML per Playwright gescreenshottet und gegen ein
Referenz-PNG aus der Design-Vorlage per Pixel-Diff verglichen.

--- Kalibrierungs-Kompromiss (dokumentiert, wie im Brief gefordert) ---
Die Referenz-PNGs unter docs/design-requests/issue-956-mail-vorschau/screenshots/
sind Ausschnitte aus der Claude-Design-Vorlage mit ANDEREN Inhalten (anderer
Trip-Name, andere Datums-/Kilometer-/Höhen-Zahlen) als jedes synthetisch
gerenderte Test-Briefing. Der reine Pixel-Diff-Prozentsatz enthält daher immer
einen Inhalts-Anteil (unterschiedlicher Text), der auch nach einem perfekten
Layout-Fix bestehen bleibt — ein rein absoluter Schwellwert wäre als GREEN-Gate
unzuverlässig (der Diff kann strukturell nie auf ~0 fallen).

Deshalb liefert jeder Test ZWEI Nachweise:
  1. Ein echtes Pixel-Diff-Artefakt (Screenshot + Diff-PNG + gedruckter
     diff_pct) gegen das SOLL-PNG — der visuelle Beleg im Sinne der PO-Vorgabe.
  2. Einen strukturellen Assert auf das TATSÄCHLICH GERENDERTE DOM
     (Playwright-Locator / computed style / Geometrie) — KEIN Roh-String-Match
     auf dem HTML-Quelltext, sondern Prüfung des vom Browser aufgebauten DOM.
     Dieser Assert ist das eigentliche RED/GREEN-Gate: er ist heute rot, WEIL
     der Code-Bug existiert, und wird nach dem Fix grün.

Die drei Bugs (siehe docs/context/fix-956-email-format.md):
  A) Header: horizontale/senkrechte Trennlinien + "· ETAPPE N" in der Eyebrow.
  B) Segment-Header: alter Etappen-Titel-Text statt km-/Höhen-Spanne.
  E) Cell-Tint: sichtbarer weißer Rand um getönte Zelle (margin/padding-Mismatch).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

# tests/ liegt im pytest pythonpath (pyproject: pythonpath = ["src", "."]).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual.email_pixel_diff import compute_diff, screenshot_html  # noqa: E402

from app.metric_catalog import build_default_display_config  # noqa: E402
from app.models import (  # noqa: E402
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from output.renderers.email.helpers import build_friendly_keys  # noqa: E402
from output.renderers.email.html import render_html  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")
_REF_DIR = Path("docs/design-requests/issue-956-mail-vorschau/screenshots")
_ART_DIR = Path("docs/artifacts/fix-956-email-format")
_VIEWPORT = (700, 1600)


# ---------------------------------------------------------------------------
# Test-Fixtures (echte Datenobjekte, keine Mocks)
# ---------------------------------------------------------------------------

def _dp(h: int, precip: float, gust: float) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
        t2m_c=12.0, wind10m_kmh=gust * 0.5, gust_kmh=float(gust),
        precip_1h_mm=float(precip), pop_pct=int(min(precip * 20, 100)),
        cloud_total_pct=60, thunder_level=ThunderLevel.NONE, visibility_m=2000,
    )


def _make_seg(seg_id, start_km, end_km, start_h, end_h, s_elev, e_elev, rows):
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=s_elev,
                             distance_from_start_km=start_km),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=e_elev,
                           distance_from_start_km=end_km),
        start_time=datetime(2026, 7, 11, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h),
        distance_km=round(end_km - start_km, 1),
        ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
                        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc))
    ts = NormalizedTimeseries(meta=meta, data=rows)
    agg = SegmentWeatherSummary(
        temp_min_c=10.0, temp_max_c=14.0, temp_avg_c=12.0,
        wind_max_kmh=20.0, gust_max_kmh=40.0, precip_sum_mm=6.0,
        cloud_avg_pct=60, humidity_avg_pct=55, thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(segment=seg, timeseries=ts, aggregated=agg,
                              fetched_at=datetime.now(timezone.utc), provider="demo")


def _render_sample_html() -> str:
    """Rendert ein Trip-Briefing-HTML nahe an den Vorlagen-Mock-Daten.

    Zwei Segmente mit distance_km 4.6 / 4.7 (kumuliert 0.0-4.6 / 4.6-9.3 km,
    wie in der Vorlage), Höhen 400→1200→1500 m, ein Regen-Wert über
    Warn-Schwelle (precip=5) für die getönte Zelle in Teil E.
    """
    segs = [
        _make_seg(1, 0.0, 4.6, 6, 8, 400.0, 1200.0, [_dp(6, 5, 10), _dp(7, 1, 20)]),
        _make_seg(2, 4.6, 9.3, 8, 10, 1200.0, 1500.0, [_dp(8, 3, 40), _dp(9, 0, 15)]),
    ]
    rows = [{"time": "06:00", "temp": 12.0, "precip": 5.0, "_wind_dir_deg": None,
             "_is_day": True, "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None}]
    dc = build_default_display_config()
    return render_html(
        segments=segs, seg_tables=[rows, rows], trip_name="GR20 Test",
        report_type="morning", dc=dc, night_rows=[],
        thunder_forecast=None, changes=None,
        stage_name="Etappe 3: von Soller nach Tossals Verds",
        stage_stats={"distance_km": 9.3, "ascent_m": 1600.0, "descent_m": 0.0,
                     "max_elevation_m": 1500},
        multi_day_trend=None, compact_summary=None, tz=TZ,
        friendly_keys=build_friendly_keys(dc), stage_total=13,
    )


def _require_playwright():
    try:
        import playwright  # noqa: F401
    except ImportError:  # pragma: no cover
        pytest.skip("playwright nicht installiert — visueller Test übersprungen")


def _dom_query(html: str, js: str):
    """Rendert HTML headless und wertet einen JS-Ausdruck gegen das DOM aus.

    Prüft das TATSÄCHLICH GERENDERTE DOM (nicht den Roh-HTML-String) —
    zulässig laut Auftrags-Brief als visuell/DOM-basierter Nachweis.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(
            viewport={"width": _VIEWPORT[0], "height": _VIEWPORT[1]},
            device_scale_factor=1,
        ).new_page()
        page.set_content(html, wait_until="networkidle")
        page.wait_for_timeout(300)
        result = page.evaluate(js)
        browser.close()
    return result


# ---------------------------------------------------------------------------
# Test 1 (Teil A): Header-Trennlinien + "· ETAPPE N"-Eyebrow-Text
# ---------------------------------------------------------------------------

# Diagnose-Wert (kein Gate): der Header-Diff enthält viel Inhalts-Divergenz
# (anderer Trip-Name/Datum/Zahlen), daher ist die absolute Prozent-Zahl nur als
# grober Sanity-Indikator gedacht; das eigentliche Gate ist der DOM-Assert unten.
HEADER_DIFF_DIAGNOSTIC = 15.0  # %


def test_header_no_extra_lines_and_no_stage_eyebrow():
    """Test 1 (AC-1, Teil A): Header-Linien + "· ETAPPE 3"-Eyebrow.

    RED-Gate (DOM): Aktuell trägt der Eyebrow den Zusatz "· ETAPPE 3"
    (html.py:810 `_eyebrow(f"{_rt_upper}-BRIEFING · {_stage_label}")`) UND
    der Header-Container hat ein `border-bottom` (html.py:840). Beides muss
    laut Vorlage weg. Der Test schlägt fehl, solange einer dieser Bug-Marker
    im gerenderten DOM vorhanden ist.
    """
    _require_playwright()
    html = _render_sample_html()

    # (1) Visueller Beleg: Header-Ausschnitt gegen Referenz diffen.
    ist = _ART_DIR / "diff-header-ist.png"
    diff = _ART_DIR / "diff-header-diff.png"
    soll = _REF_DIR / "referenz-header-morgenbriefing.png"
    screenshot_html(html, ist, viewport=_VIEWPORT,
                    clip={"x": 15, "y": 30, "width": 670, "height": 195})
    diff_pct = compute_diff(ist, soll, diff)
    print(f"[Teil A] header diff_pct={diff_pct:.2f}% (diagnostic {HEADER_DIFF_DIAGNOSTIC}%)")

    # (2) RED/GREEN-Gate: gerendertes DOM prüfen.
    dom = _dom_query(html, """() => {
        const spans = Array.from(document.querySelectorAll('span'));
        const eyebrow = spans.find(s => (s.innerText || '').includes('BRIEFING'));
        // Header-Container: das <div> mit dem grauen Header-Hintergrund.
        const headerDiv = document.querySelector('table')?.closest('div');
        return {
            eyebrowText: eyebrow ? eyebrow.innerText.trim() : null,
        };
    }""")

    eyebrow_text = dom["eyebrowText"] or ""
    # Der Bug: Eyebrow enthält den Etappen-Zusatz. Nach dem Fix: nur "…-BRIEFING".
    assert "ETAPPE" not in eyebrow_text, (
        "Teil A: Eyebrow-Zeile enthält noch den Etappen-Zusatz "
        f"({eyebrow_text!r}) — laut Vorlage muss '· Etappe N' entfernt werden "
        "(die Etappen-Nummer steht bereits rechts). "
        f"[visueller Diff: {diff_pct:.2f}%]"
    )


def test_header_container_has_no_bottom_border():
    """Test 1b (AC-1, Teil A): keine horizontale Trennlinie unter dem Header.

    RED-Gate (DOM, computed style): Der Header-Container-<div> (grauer
    Hintergrund) rendert aktuell mit `border-bottom-width > 0` (html.py:840
    `border-bottom:1px solid #e6e1d3`). Laut Vorlage darf keine harte
    horizontale Linie zwischen Header-Grau und weißem Body stehen.
    """
    _require_playwright()
    html = _render_sample_html()

    border = _dom_query(html, """() => {
        // Der Header-Container ist das div mit dem inline background + padding
        // 22px 28px 0 und border-bottom. Wir suchen es über die Struktur:
        // erstes <table> im Body -> nächster div-Vorfahr mit border-bottom.
        const divs = Array.from(document.querySelectorAll('div'));
        const header = divs.find(d => {
            const cs = getComputedStyle(d);
            return cs.paddingTop === '22px' && cs.paddingLeft === '28px';
        });
        if (!header) return {found: false};
        const cs = getComputedStyle(header);
        return {found: true, borderBottomWidth: cs.borderBottomWidth};
    }""")

    assert border["found"], (
        "Header-Container (padding 22px 28px 0) im DOM nicht gefunden — "
        "Test-Setup prüfen (kein Bug-Nachweis)."
    )
    assert border["borderBottomWidth"] in ("0px", ""), (
        "Teil A: Header-Container hat noch eine untere Trennlinie "
        f"(border-bottom-width={border['borderBottomWidth']}) — laut Vorlage "
        "muss die horizontale Linie unter dem Header entfernt werden."
    )


# ---------------------------------------------------------------------------
# Test 2 (Teil B): Segment-Header zeigt km-/Höhen-Spanne statt Titel-Text
# ---------------------------------------------------------------------------

# Diagnose-Wert (kein Gate): Inhalts-Divergenz zur Vorlage, siehe Kopf.
SEG_DIFF_DIAGNOSTIC = 20.0  # %


def test_segment_header_shows_km_and_elevation_span():
    """Test 2 (AC-2, Teil B): SEG-Header mit km-/Höhen-Spanne, ohne Titel-Text.

    RED-Gate (DOM): Der SEG-Header zeigt aktuell den Etappen-Titel
    "Etappe 3: von Soller nach Tossals Verds" (html.py:940-941
    `{sub_header or seg_header_text(seg)}`) und rechts nur einen einzelnen
    km-Wert + Starthöhe ("4.6 km · ↑400"). Laut Vorlage
    (EmailSegmentBlock) MUSS stattdessen die kumulierte km-Spanne
    ("0.0 km - 4.6 km") und die Höhen-Spanne ("400 - 1200 m") erscheinen,
    OHNE den Titel-Text.
    """
    _require_playwright()
    html = _render_sample_html()

    # (1) Visueller Beleg.
    ist = _ART_DIR / "diff-segment-ist.png"
    diff = _ART_DIR / "diff-segment-diff.png"
    soll = _REF_DIR / "soll-segment-header.png"
    screenshot_html(html, ist, viewport=_VIEWPORT,
                    clip={"x": 40, "y": 360, "width": 620, "height": 50})
    diff_pct = compute_diff(ist, soll, diff)
    print(f"[Teil B] segment diff_pct={diff_pct:.2f}% (diagnostic {SEG_DIFF_DIAGNOSTIC}%)")

    # (2) RED/GREEN-Gate: gerendertes DOM prüfen.
    dom = _dom_query(html, """() => {
        // Den ersten SEG-Header-Block finden (enthält den Text 'SEG 1').
        const spans = Array.from(document.querySelectorAll('span'));
        const segTag = spans.find(s => (s.innerText || '').trim() === 'SEG 1');
        const block = segTag ? segTag.closest('div').parentElement : null;
        const text = block ? block.innerText : '';
        return {segHeaderText: text};
    }""")

    header_text = (dom["segHeaderText"] or "").replace("\n", " ")
    # Bug-Marker 1: der alte Titel-Text ist noch da.
    assert "von Soller" not in header_text and "Tossals" not in header_text, (
        "Teil B: SEG-Header zeigt noch den Etappen-Titel-Text "
        f"({header_text!r}) — laut Vorlage muss der Titel entfallen. "
        f"[visueller Diff: {diff_pct:.2f}%]"
    )
    # Bug-Marker 2: die kumulierte km-Spanne fehlt (aktuell nur "4.6 km").
    assert "0.0 km - 4.6 km" in header_text, (
        "Teil B: SEG-Header zeigt keine kumulierte Kilometer-Spanne "
        f"'0.0 km - 4.6 km' ({header_text!r}) — aktuell nur ein einzelner "
        "km-Wert. Laut Vorlage: '{fromKm:.1f} km - {toKm:.1f} km'."
    )
    # Bug-Marker 3: die Höhen-Spanne fehlt (aktuell nur '↑400').
    assert "400 - 1200 m" in header_text, (
        "Teil B: SEG-Header zeigt keine Höhen-Spanne '400 - 1200 m' "
        f"({header_text!r}) — aktuell nur Pfeil + Starthöhe. "
        "Laut Vorlage: '{fromElev} - {toElev} m'."
    )


def test_segment_header_accumulates_km_for_later_segments():
    """Test 2b (AC-2, Teil B): kumulierte km-Spanne auch für SEG 2 (fromKm > 0).

    RED-Gate (DOM): Der bisherige Test deckte nur SEG 1 (Trivialfall fromKm=0).
    Die Spec verlangt die kumulative Laufsumme über *mehrere* vorangehende
    Segmente. SEG 2 muss daher "4.6 km - 9.3 km" und die Höhen-Spanne
    "1200 - 1500 m" zeigen, ohne den Etappen-Titel.
    """
    _require_playwright()
    html = _render_sample_html()

    dom = _dom_query(html, """() => {
        // Den zweiten SEG-Header-Block finden (enthält den Text 'SEG 2').
        const spans = Array.from(document.querySelectorAll('span'));
        const segTag = spans.find(s => (s.innerText || '').trim() === 'SEG 2');
        const block = segTag ? segTag.closest('div').parentElement : null;
        const text = block ? block.innerText : '';
        return {segHeaderText: text};
    }""")

    header_text = (dom["segHeaderText"] or "").replace("\n", " ")
    assert "von Soller" not in header_text and "Tossals" not in header_text, (
        "Teil B (SEG 2): SEG-Header zeigt noch den Etappen-Titel-Text "
        f"({header_text!r}) — laut Vorlage muss der Titel entfallen."
    )
    assert "4.6 km - 9.3 km" in header_text, (
        "Teil B (SEG 2): SEG-Header zeigt keine kumulierte Kilometer-Spanne "
        f"'4.6 km - 9.3 km' ({header_text!r}). "
        "Laut Vorlage muss fromKm der echten Laufsumme entsprechen."
    )
    assert "1200 - 1500 m" in header_text, (
        "Teil B (SEG 2): SEG-Header zeigt keine Höhen-Spanne '1200 - 1500 m' "
        f"({header_text!r})."
    )


# ---------------------------------------------------------------------------
# Test 3 (Teil E): Cell-Tint füllt die Zelle randlos (kein weißer Rand)
# ---------------------------------------------------------------------------

# Diagnose-Wert (kein Gate): Inhalts-Divergenz zur Vorlage, siehe Kopf.
TINT_DIFF_DIAGNOSTIC = 25.0  # %


def test_cell_tint_fills_cell_to_gridlines():
    """Test 3 (AC-4, Teil E): getönter Hintergrund randlos bis an die Gitterlinien.

    RED-Gate (DOM, Geometrie): Die getönte Zelle wickelt ihren Inhalt in
    `<span style="…margin:-6px -4px;padding:6px 4px">` (html.py:553-557),
    während das umgebende `<td>` `padding:6px` (html.py:1428) hat. Der
    horizontale Negativ-Margin (-4px) kompensiert das 6px-td-Padding NICHT
    vollständig → links/rechts bleibt ein sichtbarer weißer Rand von ~2px.
    Der Test misst die Geometrie: der getönte <span> muss die Zellen-
    Innenbreite vollständig ausfüllen (Rand ≤ 1px). Aktuell tut er das nicht.
    """
    _require_playwright()
    html = _render_sample_html()

    # (1) Visueller Beleg: eine getönte Zelle + Nachbarn.
    ist = _ART_DIR / "diff-celltint-ist.png"
    diff = _ART_DIR / "diff-celltint-diff.png"
    soll = _REF_DIR / "soll-cell-tint-spacing.png"
    screenshot_html(html, ist, viewport=_VIEWPORT,
                    clip={"x": 375, "y": 435, "width": 170, "height": 40})
    diff_pct = compute_diff(ist, soll, diff)
    print(f"[Teil E] cell-tint diff_pct={diff_pct:.2f}% (diagnostic {TINT_DIFF_DIAGNOSTIC}%)")

    # (2) RED/GREEN-Gate: Geometrie der getönten Zellen-Box vs. der <td>-Zelle.
    # Issue #995 (Gruppe B): die Tönung sitzt jetzt als `background:` direkt am
    # <td> selbst (kein innerer <span>-Wrapper mit Negativ-Margin mehr). Die
    # Query prüft ZUERST den Altfall (span mit background — Kompatibilität, falls
    # andere Pfade das noch nutzen) und fällt sonst auf den <td>-eigenen
    # Hintergrund zurück. Bei <td>-eigenem Background ist die Tönung per
    # Definition randlos (die getönte Box IST die Zelle → leftGap/rightGap = 0).
    geom = _dom_query(html, """() => {
        const tds = Array.from(document.querySelectorAll('td[data-label]'));
        for (const td of tds) {
            const tdCS = getComputedStyle(td);
            const tdBox = td.getBoundingClientRect();
            // Altfall: innerer <span> trägt den Hintergrund.
            const span = td.querySelector('span');
            if (span) {
                const cs = getComputedStyle(span);
                const bg = cs.backgroundColor;
                if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
                    const spanBox = span.getBoundingClientRect();
                    return {
                        found: true,
                        tintSource: 'span',
                        tdPaddingLeft: tdCS.paddingLeft,
                        spanMarginLeft: cs.marginLeft,
                        leftGap: spanBox.left - tdBox.left,
                        rightGap: tdBox.right - spanBox.right,
                        background: bg,
                    };
                }
            }
            // Neuer Fall (#995): der <td> selbst trägt den Hintergrund.
            const tdBg = tdCS.backgroundColor;
            if (tdBg && tdBg !== 'rgba(0, 0, 0, 0)' && tdBg !== 'transparent') {
                return {
                    found: true,
                    tintSource: 'td',
                    tdPaddingLeft: tdCS.paddingLeft,
                    spanMarginLeft: 'n/a',
                    // Die getönte Box IST die Zelle → definitionsgemäß randlos.
                    leftGap: 0,
                    rightGap: 0,
                    background: tdBg,
                };
            }
        }
        return {found: false};
    }""")

    assert geom["found"], (
        "Getönte Zelle (background in td[data-label] oder innerem span) im DOM "
        "nicht gefunden — Test-Setup prüfen (precip-Wert über Warn-Schwelle?)."
    )
    # Der getönte Bereich muss die Zelle randlos ausfüllen. Bug: ~2px Lücke
    # links/rechts, weil margin -4px das td-padding 6px nicht ausgleicht.
    max_gap = max(abs(geom["leftGap"]), abs(geom["rightGap"]))
    assert max_gap <= 1.0, (
        "Teil E: getönter Hintergrund füllt die Zelle NICHT randlos — "
        f"sichtbare Lücke links/rechts (leftGap={geom['leftGap']:.1f}px, "
        f"rightGap={geom['rightGap']:.1f}px; td-padding-left="
        f"{geom['tdPaddingLeft']}, span-margin-left={geom['spanMarginLeft']}). "
        "Der Negativ-Margin muss das td-Padding exakt kompensieren. "
        f"[visueller Diff: {diff_pct:.2f}%]"
    )
