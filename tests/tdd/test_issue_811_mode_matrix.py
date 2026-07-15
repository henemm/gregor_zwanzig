"""Issue #811 AC-1 — Modus-Matrix-Vertragstest gegen die ECHT gerenderte Briefing-Mail.

Erzwingungs-Infrastruktur (kein Inhalts-Fix). Parametrisiert ueber
  format ∈ {full, compact} × modus ∈ {Einfach, Roh} × variante ∈ {briefing, alert}.
Pro Fall wird die Mail ECHT ueber render_email(...) gerendert (mock-frei).

Issue #814 (v2.0): Metrik-spezifische RED-Tests fuer den vollstaendigen Vertrag.
  - AC-1 RED: Einfach+full → wind/gust/precip/pop-Zellen sind Ampel-Emoji (heute: Zahl)
  - AC-4 RED: CAPE Plain-Einfach = Zahl (heute: Emoji). CAPE Roh-HTML = nackte Zahl ohne Span.
  - AC-5 RED: Sicht = km-Zahl (heute: englisches Wort good/fair/poor/fog)
  - AC-6 RED: Gewitter Roh = deutsches Wort ohne Blitzsymbol (heute: Blitzsymbol)
  - AC-8 RED: Roh-HTML hat KEIN inline background:/color:-Style (heute: CAPE Span)
  - AC-2/AC-3/AC-10: GREEN-Sicherungen

KEINE Mocks/patch/MagicMock — echte render_email-Aufrufe.

Test-Manifest: docs/specs/tests/issue_814_ampel_einfach_roh_tests.md
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

# Issue #1222: Kreis-Emojis wurden durch gestylte CSS-Dots ersetzt. Der
# Emoji-Satz bleibt als Regress-Set fuer Abwesenheits-Checks erhalten.
_AMPEL_EMOJIS = ("🟢", "🟡", "🟠", "🔴")

# Volle aktivierte Metrik-Liste, damit jede fmt_val-Verzweigung greift.
_ENABLED = {
    "temperature", "wind", "gust", "precipitation",
    "rain_probability", "cloud_total", "sunshine", "cape",
    "visibility",
}


def _make_dp():
    """Werte oberhalb der Gelb-Schwellen, damit Ampel-Verzweigungen greifen."""
    from app.models import ForecastDataPoint, ThunderLevel
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=22.0, wind10m_kmh=55.0, gust_kmh=85.0, precip_1h_mm=8.0,
        pop_pct=80, cloud_total_pct=85, thunder_level=ThunderLevel.MED,
        wind_chill_c=20.0, cape_jkg=1500.0,
        visibility_m=15000.0,
    )


def _make_dc(*, raw: bool, enabled: set[str] | None = None):
    """Roh (raw) vs. Einfach (friendly default je Metrik)."""
    from app.metric_catalog import build_default_display_config
    dc = build_default_display_config()
    active = enabled if enabled is not None else _ENABLED
    for mc in dc.metrics:
        mc.enabled = mc.metric_id in active
        if raw:
            mc.format_mode = "raw"
            mc.use_friendly_format = False
        else:
            mc.format_mode = None
            mc.use_friendly_format = True
    return dc


def _make_seg_data(dp=None):
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    if dp is None:
        dp = _make_dp()
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=24.0, temp_avg_c=19.0,
        wind_max_kmh=55.0, gust_max_kmh=85.0, precip_sum_mm=8.0,
        cloud_avg_pct=85, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.MED, wind_chill_min_c=20.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_changes():
    """Alert-Variante: echte WeatherChange-Objekte (Wetteraenderung)."""
    from app.models import ChangeSeverity, WeatherChange
    return [
        WeatherChange(
            metric="wind_max_kmh", old_value=20.0, new_value=55.0, delta=35.0,
            threshold=10.0, severity=ChangeSeverity.MAJOR, direction="increase",
        ),
    ]


def _render(*, email_format: str, raw: bool, alert: bool,
            enabled: set[str] | None = None, dp=None):
    """ECHTER render_email-Aufruf → (html, plain)."""
    from src.output.renderers.email import render_email
    from src.output.renderers.email.helpers import dp_to_row
    from src.output.tokens.dto import TokenLine

    if dp is None:
        dp = _make_dp()
    dc = _make_dc(raw=raw, enabled=enabled)
    row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Berlin"))
    tl = TokenLine(
        trip_name="Matrix-Test", report_type="evening", stage_name="Etappe 1",
    )
    return render_email(
        tl, segments=[_make_seg_data(dp=dp)], seg_tables=[[row]],
        display_config=dc, tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
        email_format=email_format, changes=(_make_changes() if alert else None),
    )


def _render_one_metric(metric_id: str, *, raw: bool, alert: bool = False, dp=None):
    """Rendert GENAU eine Zielmetrik + temperature als Anker. Gibt (html, plain) zurueck."""
    return _render(
        email_format="full", raw=raw, alert=alert,
        enabled={"temperature", metric_id},
        dp=dp,
    )


def _data_cells(html: str) -> list[str]:
    """Daten-Zellen der Stundentabelle (class="resp")."""
    m = re.search(r'<table[^>]*data-table="resp"[^>]*>.*?</table>', html, re.S)
    if not m:
        return []
    return re.findall(r'<td[^>]*data-label="[^"]*"[^>]*>(.*?)</td>', m.group(0), re.S)


def _has_ampel(text: str) -> bool:
    """Issue #1222: 'hat Ampel' heisst jetzt CSS-Dot (border-radius:50%),
    kein Kreis-Emoji mehr. Emoji-Check bleibt als Regress-Absicherung."""
    return "border-radius:50%" in text or any(e in text for e in _AMPEL_EMOJIS)


# ---------------------------------------------------------------------------
# AC-2 GREEN-Sicherung: Roh+full → Metrik-Zelle ist KEINE Ampel
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("alert", [False, True], ids=["briefing", "alert"])
@pytest.mark.parametrize("metric_id", [
    "wind", "gust", "precipitation", "rain_probability",
], ids=["wind", "gust", "precip", "pop"])
def test_raw_full_html_metric_no_ampel(metric_id, alert):
    """AC-2 GREEN-Sicherung: Roh+full → keine Ampel in der Metrik-Zelle.

    Sichert den korrekten Roh-Pfad ab. Muss sowohl heute als auch nach
    dem Fix gruen sein.
    """
    html, _plain = _render_one_metric(metric_id, raw=True, alert=alert)
    cells = _data_cells(html)
    assert cells, f"Stundentabelle muss Zellen haben fuer {metric_id}"
    ampel_cells = [c for c in cells if _has_ampel(c)]
    assert not ampel_cells, (
        f"AC-2: Roh+full darf KEINE Ampel-Emoji zeigen fuer {metric_id}. "
        f"Gefunden: {ampel_cells!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 GREEN-Sicherung: Plain numerisch in beiden Modi
# ---------------------------------------------------------------------------

def _plain_table_rows(plain: str) -> list[str]:
    """Extrahiert die Daten-Zeilen der Stundentabelle aus dem Plain-Text.

    Die Tabelle beginnt nach der '-----'-Trennzeile. Wir suchen die Zeilen
    die mit einer Uhrzeit (Zahl) beginnen (z.B. '  12     22.0   55   ').
    """
    lines = plain.splitlines()
    in_table = False
    data_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("-----"):
            in_table = True
            continue
        if in_table:
            if not stripped:
                in_table = False
                continue
            # Nur echte Stundentabellen-Zeilen (beginnen mit einer Uhrzeit/Zahl,
            # s. Docstring). Footer-/Meta-Zeilen (Generated:/Data:/Herkunfts-
            # Fußzeile #1241) beginnen nie mit einer Ziffer und bleiben außen vor.
            if stripped[0].isdigit():
                data_lines.append(stripped)
    return data_lines


@pytest.mark.parametrize("raw", [False, True], ids=["einfach", "roh"])
@pytest.mark.parametrize("metric_id", [
    "wind", "gust", "precipitation", "rain_probability",
], ids=["wind", "gust", "precip", "pop"])
def test_plain_numeric_in_both_modes(metric_id, raw):
    """AC-3 GREEN-Sicherung: Stundentabelle im Plain-Teil ist in beiden Modi ASCII ohne Ampel-Emoji.

    Prueft nur die Daten-Zeilen der Stundentabelle, nicht den gesamten Plain-Text
    (Header/Summary-Abschnitt kann legitim non-ASCII enthalten, z.B. Metriken-Ueberblick).
    """
    _html, plain = _render_one_metric(metric_id, raw=raw)
    table_rows = _plain_table_rows(plain)
    assert table_rows, (
        f"AC-3: Plain muss Stundentabellen-Zeilen haben fuer {metric_id}: {plain[:300]!r}"
    )
    for row in table_rows:
        assert row.isascii(), (
            f"AC-3: Plain Stundentabellen-Zeile muss ASCII sein fuer {metric_id}: {row!r}"
        )
        assert not _has_ampel(row), (
            f"AC-3: Plain Stundentabellen-Zeile darf kein Ampel-Emoji enthalten "
            f"fuer {metric_id}: {row!r}"
        )


# ---------------------------------------------------------------------------
# AC-1 RED: Einfach+full → Metrik-Zelle ist Ampel-Emoji (heute: Zahl → FAIL)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("alert", [False, True], ids=["briefing", "alert"])
@pytest.mark.parametrize("metric_id", [
    "wind", "gust", "precipitation", "rain_probability",
], ids=["wind", "gust", "precip", "pop"])
def test_einfach_full_html_metric_has_ampel(metric_id, alert):
    """AC-1 RED: Einfach+full → Metrik-Zelle zeigt Ampel-Emoji in HTML.

    Schlaegt HEUTE fehl: build_format_modes() gibt 'raw' fuer wind/gust/precip/pop
    auch wenn use_friendly_format=True gesetzt ist (catalog.default_format_mode='raw').
    """
    html, _plain = _render_one_metric(metric_id, raw=False, alert=alert)
    cells = _data_cells(html)
    assert cells, f"AC-1: Stundentabelle muss Zellen haben fuer {metric_id}"
    ampel_cells = [c for c in cells if _has_ampel(c)]
    assert ampel_cells, (
        f"AC-1 RED: Einfach+full muss Ampel-Emoji zeigen fuer {metric_id}. "
        f"Daten-Zellen: {cells!r}. "
        f"(Bug: use_friendly_format=True → build_format_modes gibt 'raw' → keine Ampel)"
    )


# ---------------------------------------------------------------------------
# AC-4: CAPE harmonisiert
# ---------------------------------------------------------------------------

def test_cape_plain_einfach_is_number_not_emoji():
    """AC-4 RED: CAPE Plain-Einfach Stundentabelle zeigt numerischen Wert, kein Ampel-Emoji.

    Heute: use_friendly=True → symbol-Modus → Emoji in der Stundentabellen-Zeile (FAIL).
    Die Pruefung erfolgt nur auf Stundentabellen-Zeilen (header/summary sind legitim non-ASCII).
    """
    _html, plain = _render_one_metric("cape", raw=False)
    table_rows = _plain_table_rows(plain)
    assert table_rows, (
        f"AC-4: Plain muss Stundentabellen-Zeilen haben. plain={plain[:300]!r}"
    )
    for row in table_rows:
        assert not _has_ampel(row), (
            f"AC-4 RED: CAPE Plain-Stundentabelle darf KEIN Ampel-Emoji enthalten. "
            f"Zeile: {row!r}"
        )
        assert row.isascii(), (
            f"AC-4 RED: CAPE Plain-Stundentabelle muss ASCII sein. Zeile: {row!r}"
        )


def test_cape_roh_html_no_yellow_span():
    """AC-4 RED: CAPE Roh-HTML zeigt nackte Zahl ohne Gelb-Hintergrund-Span.

    Heute: fmt_val('cape', 1500, use_friendly=False, html=True) erzeugt
    <span style='background:#fff9c4;...'> (FAIL).
    """
    html, _plain = _render_one_metric("cape", raw=True)
    cells = _data_cells(html)
    assert cells, "CAPE Roh muss Daten-Zellen haben"
    for cell in cells:
        assert "background" not in cell, (
            f"AC-4 RED: CAPE Roh-HTML darf KEINEN background-Style enthalten. "
            f"Zelle: {cell!r}"
        )
        assert "<span" not in cell, (
            f"AC-4 RED: CAPE Roh-HTML darf KEINEN <span>-Tag enthalten. "
            f"Zelle: {cell!r}"
        )


def test_cape_einfach_html_has_ampel():
    """AC-4 GREEN-Sicherung: CAPE Einfach-HTML zeigt Ampel-Emoji.

    cape_jkg=1500 → 🟡 gemaess Schwellen 1000/2500/3500.
    """
    html, _plain = _render_one_metric("cape", raw=False)
    cells = _data_cells(html)
    assert cells, "CAPE Einfach muss Daten-Zellen haben"
    ampel_cells = [c for c in cells if _has_ampel(c)]
    assert ampel_cells, (
        f"AC-4: CAPE Einfach-HTML muss Ampel-Emoji zeigen "
        f"(cape_jkg=1500 >= yellow=1000). Daten-Zellen: {cells!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 RED: Sicht = km-Zahl, KEIN englisches Wort
# ---------------------------------------------------------------------------

_VISIBILITY_ENGLISH_WORDS = ("good", "fair", "poor", "fog")


def _contains_visibility_english(text: str) -> bool:
    return any(w in text.lower() for w in _VISIBILITY_ENGLISH_WORDS)


@pytest.mark.parametrize("raw", [False, True], ids=["einfach", "roh"])
def test_visibility_numeric_km_no_english_word(raw):
    """AC-5 RED: Sicht zeigt km-Zahl, kein englisches Wort good/fair/poor/fog.

    Heute (Einfach): fmt_val gibt 'good'/'fair'/'poor'/'fog' (FAIL).
    """
    html, plain = _render_one_metric("visibility", raw=raw)
    cells = _data_cells(html)
    for cell in cells:
        assert not _contains_visibility_english(cell), (
            f"AC-5 RED: Sicht-Zelle darf kein englisches Wort enthalten "
            f"({'Einfach' if not raw else 'Roh'}). Zelle: {cell!r}"
        )
    assert not _contains_visibility_english(plain), (
        f"AC-5 RED: Sicht Plain-Teil darf kein englisches Wort enthalten "
        f"({'Einfach' if not raw else 'Roh'}). plain={plain[:300]!r}"
    )


def test_visibility_roh_html_no_inline_style():
    """AC-5/AC-8: Sicht Roh-HTML trägt keine ALTE fmt_val-Ampel (#fff3e0) und keinen
    Text-Farb-Span.

    fix-911-visual-table AC-2 (PO-Entscheidung): Die #911-Severity-Zell-Tönung
    (`<span style="display:block;background:#fbeeb8|#fad6b8|#f6c5bf;...">`) ist erlaubt
    — Schweregrad-Hintergrund gilt in BEIDEN Modi (visibility_m=200 → 0.2 km → danger).
    Verboten bleibt jeder Text-`color:`-Span und jedes andere `background:`.
    """
    from app.models import ForecastDataPoint, ThunderLevel

    dp_low_vis = ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=5.0, gust_kmh=10.0, precip_1h_mm=0.0,
        pop_pct=10, cloud_total_pct=30, thunder_level=ThunderLevel.NONE,
        wind_chill_c=13.0, visibility_m=200.0,
    )
    html, _plain = _render_one_metric("visibility", raw=True, dp=dp_low_vis)
    cells = _data_cells(html)

    def _strip_severity_wrapper(cell: str) -> str:
        return re.sub(
            r'<span style="display:block;background:#[0-9a-fA-F]{6};'
            r'margin:-6px -6px;padding:6px 6px;">|</span>',
            "", cell,
        )

    for cell in cells:
        stripped = _strip_severity_wrapper(cell)
        assert "color:" not in stripped, (
            f"Sicht Roh-HTML darf KEINEN Text-Farb-Span haben. Zelle: {cell!r}"
        )
        assert "background" not in stripped, (
            f"Sicht Roh-HTML darf ausser der #911-Severity-Tönung KEIN background: "
            f"haben (alte fmt_val-Ampel #fff3e0). Zelle: {cell!r}"
        )


# ---------------------------------------------------------------------------
# AC-6: Gewitter — Einfach = Blitzsymbol, Roh = deutsches Wort
# ---------------------------------------------------------------------------

def _render_thunder_full(*, raw: bool, thunder_level):
    """Rendert thunder+temperature, gibt (html, plain) zurueck."""
    from app.models import ForecastDataPoint

    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.5,
        pop_pct=20, cloud_total_pct=50, thunder_level=thunder_level,
        wind_chill_c=18.0,
    )
    return _render_one_metric("thunder", raw=raw, dp=dp)


def test_thunder_einfach_med_has_lightning_symbol():
    """AC-6 GREEN-Sicherung: Gewitter Einfach MED zeigt Blitzsymbol in HTML."""
    from app.models import ThunderLevel
    html, _plain = _render_thunder_full(raw=False, thunder_level=ThunderLevel.MED)
    cells = _data_cells(html)
    lightning_cells = [c for c in cells if "⚡" in c]
    assert lightning_cells, (
        f"AC-6: Einfach MED muss Blitzsymbol zeigen. Daten-Zellen: {cells!r}"
    )


def test_thunder_einfach_high_has_double_lightning():
    """AC-6 GREEN-Sicherung: Gewitter Einfach HIGH zeigt doppeltes Blitzsymbol."""
    from app.models import ThunderLevel
    html, _plain = _render_thunder_full(raw=False, thunder_level=ThunderLevel.HIGH)
    cells = _data_cells(html)
    double_lightning = [c for c in cells if "⚡⚡" in c]
    assert double_lightning, (
        f"AC-6: Einfach HIGH muss doppeltes Blitzsymbol zeigen. Daten-Zellen: {cells!r}"
    )


def test_thunder_roh_med_german_word_no_lightning():
    """AC-6 RED: Gewitter Roh MED zeigt deutsches Wort, kein Blitzsymbol.

    Heute: fmt_val('thunder', MED) gibt 'Blitz mögl.' unabhaengig vom raw-Modus (FAIL).
    """
    from app.models import ThunderLevel
    html, plain = _render_thunder_full(raw=True, thunder_level=ThunderLevel.MED)
    cells = _data_cells(html)
    lightning_cells = [c for c in cells if "⚡" in c]
    assert not lightning_cells, (
        f"AC-6 RED: Gewitter Roh MED darf kein Blitzsymbol zeigen. "
        f"Gefunden: {lightning_cells!r}. "
        f"(Bug: fmt_val ignoriert raw-Modus fuer thunder)"
    )
    full_text = html + plain
    assert any(w in full_text for w in ("mögl", "kein", "hoch")), (
        f"AC-6 RED: Gewitter Roh MED muss deutsches Wort enthalten. "
        f"HTML-Zellen: {cells!r}"
    )


def test_thunder_roh_high_german_word_no_lightning():
    """AC-6 RED: Gewitter Roh HIGH zeigt deutsches Wort 'hoch', kein Blitzsymbol.

    Heute: fmt_val gibt doppeltes Blitzsymbol unabhaengig vom raw-Modus (FAIL).
    """
    from app.models import ThunderLevel
    html, plain = _render_thunder_full(raw=True, thunder_level=ThunderLevel.HIGH)
    cells = _data_cells(html)
    lightning_cells = [c for c in cells if "⚡" in c]
    assert not lightning_cells, (
        f"AC-6 RED: Gewitter Roh HIGH darf kein Blitzsymbol zeigen. "
        f"Gefunden: {lightning_cells!r}"
    )
    full_text = html + plain
    assert any(w in full_text for w in ("hoch", "mögl", "kein")), (
        f"AC-6 RED: Gewitter Roh HIGH muss deutsches Wort enthalten. "
        f"HTML-Zellen: {cells!r}"
    )


def test_thunder_roh_none_german_word_kein():
    """AC-6 F001: Gewitter Roh NONE = 'kein' (deutsches Wort), nicht '–'.

    Adversary-Finding F001: NONE fiel auf den abschliessenden 'return "-"' und
    lieferte '–' statt 'kein' — Roh-Wort-Vertrag fuer NONE war unvollstaendig.
    Einfach-NONE bleibt '–' (kein Symbol, kein Wort in Datenzellen).
    """
    from app.models import ThunderLevel
    html_roh, plain_roh = _render_thunder_full(raw=True, thunder_level=ThunderLevel.NONE)
    # Prüfe Datenzellen + Plain (Pills "kein Gewitter" sind OK, kommen nicht aus fmt_val).
    cells_roh = _data_cells(html_roh)
    thunder_cells_roh = [c for c in cells_roh if "kein" in c or "mögl" in c or "hoch" in c or "–" in c]
    assert any("kein" in c for c in thunder_cells_roh), (
        f"AC-6 F001: Thunder-Datenzelle Roh NONE muss 'kein' enthalten. "
        f"Thunder-Zellen: {thunder_cells_roh!r}, alle Zellen: {cells_roh!r}"
    )
    assert "kein" in plain_roh, (
        f"AC-6 F001: Plain Roh NONE muss 'kein' enthalten, war: {plain_roh!r}"
    )

    # Einfach-NONE: Datenzellen zeigen '–', kein Blitzsymbol.
    html_ein, plain_ein = _render_thunder_full(raw=False, thunder_level=ThunderLevel.NONE)
    cells_ein = _data_cells(html_ein)
    assert "⚡" not in html_ein, (
        "AC-6: Einfach NONE darf kein Blitzsymbol zeigen"
    )
    assert not any("kein" in c for c in cells_ein), (
        f"AC-6: Einfach NONE Datenzellen duerfen 'kein' nicht enthalten "
        f"(nur Pills duerfen 'kein Gewitter' zeigen). Zellen: {cells_ein!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 RED: Roh-HTML hat in keiner Daten-Zelle inline background:/color:-Style
# ---------------------------------------------------------------------------

def test_raw_full_html_no_inline_style_any_metric():
    """AC-8: Roh-HTML enthaelt in keiner Daten-Zelle einen inline Text-Farb-Span (color:).

    Der Wert selbst (aus fmt_val) darf im Roh-Modus keine Farb-/Ampel-Markierung
    tragen (z.B. CAPE-Gelb-Span).

    fix-911-table-jsx AC-2 (PO-Entscheidung): Die SEVERITY-Zell-Tönung des #911-
    Renderers (`<span style="display:block;background:#fbeeb8|#fad6b8|#f6c5bf;...">`)
    ist erlaubt — sie ist ein Schweregrad-Hintergrund, KEINE Ampel/Text-Farbe und
    gilt in beiden Modi. Verboten bleibt jeder Text-`color:`-Span sowie ein
    `background:` das NICHT der #911-Severity-Wrapper ist.
    """
    html, _plain = _render(email_format="full", raw=True, alert=False)
    cells = _data_cells(html)
    assert cells, "Roh+full muss Daten-Zellen haben"

    def _strip_severity_wrapper(cell: str) -> str:
        # #911-Severity-Tönung herausfiltern: nur den display:block-background-Wrapper.
        return re.sub(
            r'<span style="display:block;background:#[0-9a-fA-F]{6};'
            r'margin:-6px -6px;padding:6px 6px;">|</span>',
            "", cell,
        )

    color_cells = [c for c in cells if "color:" in c]
    other_bg_cells = [
        c for c in cells
        if "background" in _strip_severity_wrapper(c)
    ]
    assert not color_cells, (
        f"AC-8: Roh-HTML darf KEINEN Text-Farb-Span (color:) haben. "
        f"Gefunden: {color_cells!r}"
    )
    assert not other_bg_cells, (
        f"AC-8: Roh-HTML darf ausser der #911-Severity-Toenung KEIN background: haben. "
        f"Gefunden: {other_bg_cells!r}"
    )


# ---------------------------------------------------------------------------
# AC-10: compact (beide Modi) — reines ASCII, kein Emoji, keine Stundentabelle
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [True, False], ids=["roh", "einfach"])
@pytest.mark.parametrize("alert", [False, True], ids=["briefing", "alert"])
def test_compact_ascii_no_emoji_no_hourly_table(raw, alert):
    """compact: nur Text, reines ASCII, kein Emoji, keine Stundentabelle."""
    html, plain = _render(email_format="compact", raw=raw, alert=alert)
    assert html == "", "compact darf keinen HTML-Body erzeugen"
    assert plain.isascii(), f"compact muss reines ASCII sein: {plain!r}"
    assert not _has_ampel(plain), "compact darf KEIN Ampel-Emoji enthalten"
    assert "<table" not in plain, "compact darf KEINE Stundentabelle enthalten"
    hour_rows = re.findall(r"^\s*\d{2}:00\b", plain, re.M)
    assert len(hour_rows) < 2, f"compact darf keine Stundentabelle sein: {hour_rows!r}"


# ---------------------------------------------------------------------------
# Issue #833 AC-2 — Roh/Einfach-Vertrag im Mobile-Viewport (.mobile-compact)
# ---------------------------------------------------------------------------
# `_data_cells` prueft nur die Desktop-Tabelle (class="resp"). Der Mobile-Block
# (.mobile-compact: <pre> im Roh, resp-Tabelle im Einfach) blieb ungeprueft —
# genau die Luecke, durch die #831 (Einfach mobil folgenlos) rutschte. Diese
# Tests erzwingen die Vertragspruefung in BEIDEN Aufloesungen.
# In der RED-Phase fehlt `_data_cells_mobile()` noch → klarer Fehlschlag.


def _data_cells_mobile(html: str) -> list[str]:
    """Datenzellen des `.mobile-compact`-Blocks (Roh: <pre>-Raster, Einfach: resp-Tabelle).

    Roh: Tokens der Datenzeilen im <pre> (Header-Zeile 'Zeit ...' wird verworfen).
    Einfach: <td data-label>-Zellen der eingebetteten <table class="resp">.
    """
    m = re.search(r'<div class="mobile-compact".*?(?=<div class="mobile-compact"|$)', html, re.S)
    if not m:
        return []
    block = m.group(0)
    # Einfach-Modus: eingebettete resp-Tabelle.
    t = re.search(r'<table[^>]*data-table="resp"[^>]*>.*?</table>', block, re.S)
    if t:
        return re.findall(r'<td[^>]*data-label="[^"]*"[^>]*>(.*?)</td>', t.group(0), re.S)
    # Roh-Modus: Monospace-<pre>. Header-Zeile (beginnt mit 'Zeit') verwerfen.
    pre = re.search(r'<pre[^>]*>(.*?)</pre>', block, re.S)
    if not pre:
        return []
    cells: list[str] = []
    for line in pre.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("Zeit"):
            continue
        cells.extend(line.split())
    return cells


def _mobile_cells_fn():
    fn = globals().get("_data_cells_mobile")
    assert fn is not None, (
        "_data_cells_mobile() ist noch nicht definiert — Issue #833 AC-2 "
        "(RED erwartet, wird in der Implement-Phase ergaenzt)."
    )
    return fn


@pytest.mark.parametrize("alert", [False, True], ids=["briefing", "alert"])
def test_mobile_block_data_cells_roh(alert):
    """AC-2: Roh+full → der .mobile-compact-Block liefert Datenzellen ohne Ampel."""
    fn = _mobile_cells_fn()
    html, _plain = _render(email_format="full", raw=True, alert=alert)
    cells = fn(html)
    assert cells, "Mobile-Block muss Stunden-Datenzellen liefern (Roh)"
    ampel_cells = [c for c in cells if _has_ampel(c)]
    assert not ampel_cells, (
        f"AC-2: Roh-Mobile darf KEINE Ampel zeigen, fand: {ampel_cells!r}"
    )


def test_mobile_block_data_cells_einfach():
    """AC-2: Einfach+full → der .mobile-compact-Block zeigt Symbole/Ampel mobil.

    'Desktop gruen, Mobile leer/nur-Zahlen' ist KEIN Bestehen — sonst rutscht
    die #831-Klasse (Einfach mobil folgenlos) wieder durch.
    """
    fn = _mobile_cells_fn()
    html, _plain = _render_one_metric("gust", raw=False)
    cells = fn(html)
    assert cells, "Mobile-Block muss im Einfach-Modus Datenzellen liefern"
    assert any(_has_ampel(c) for c in cells), (
        "AC-2: Einfach-Modus muss mobil Ampel/Symbole zeigen (#831-Regressionsschutz). "
        f"Mobile-Zellen: {cells!r}"
    )


# ---------------------------------------------------------------------------
# Issue #811 — Matrix-Nachweis-Recording (Komponente A → Gate-Nachweis)
# ---------------------------------------------------------------------------

_module_failed = False


def pytest_runtest_makereport(item, call):  # noqa: D401 — pytest hook
    """Merkt echte Fehler dieses Moduls (xfail/xpass zaehlen nicht)."""
    global _module_failed
    if item.module.__name__ != __name__:
        return
    if call.when == "call" and call.excinfo is not None:
        from _pytest.outcomes import XFailed
        if not isinstance(call.excinfo.value, XFailed):
            _module_failed = True


@pytest.fixture(scope="module", autouse=True)
def _record_matrix_on_success():
    yield
    if _module_failed:
        return
    import os
    import subprocess
    import sys
    from pathlib import Path

    if not (os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "").strip()
            or os.environ.get("GZ_ACTIVE_WORKFLOW", "").strip()):
        return
    gate = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "renderer_mail_gate.py"
    if not gate.exists():
        return
    subprocess.run(
        [sys.executable, str(gate), "record-matrix"],
        capture_output=True, text=True,
    )
