"""TDD RED — Issue #1475 Nachbesserung (Epic #1419), AC-2/AC-3: Trip-
Stundentabelle, Ampel-Kreis-Modus zeigt bei `hail_flag=True` einen
zusaetzlichen, aeusseren box-shadow-Ring (Doppelring) plus einen
Erklaerungssatz -- NUR wenn mindestens eine sichtbare Zeile den Doppelring
zeigt.

SPEC: docs/specs/modules/feat_1475_hagel_luecken_nachbesserung.md, AC-2/AC-3,
Implementation Details Punkt 2.

RED-Ursache (heute): `email/helpers.py::_ampel_dot_css(level)` kennt keinen
`hail`-Parameter, `dp_to_row()` setzt kein `row["_hail_flag"]`, und der
thunder-Zweig von `fmt_val()` reicht `row` nicht an `_ampel_dot_css()` durch
-- eine Stunde mit `hail_flag=True` sieht daher IDENTISCH aus wie eine mit
`hail_flag=None`. Der Erklaerungssatz "Doppelring bei Gewitter = Hagel
moeglich" existiert nirgends im Renderer.

Kein isolierter `_ampel_dot_css()`-Aufruf (Lehre #1467 AG6) -- beide Tests
laufen gegen den echten `TripReportFormatter.format_email()`-Renderpfad.
Keine Mocks/patch()/MagicMock.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

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

_TZ = ZoneInfo("Europe/Berlin")


def _dc_ampel_kreis_modus():
    """Nur die Metrik 'thunder' aktiv, einfache HTML-Ansicht (Ampel-Kreis),
    analog `tests/tdd/test_thunder_column_ampel.py::_dc`."""
    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = mc.metric_id == "thunder"
        mc.format_mode = None
        mc.use_friendly_format = True
    return dc


def _segment_zwei_stunden_high_hagel_a_kein_hagel_b() -> SegmentWeatherData:
    """Zwei Stunden, beide `thunder_level=HIGH`: Stunde 10 traegt
    `hail_flag=True` (A), Stunde 12 `hail_flag=None` (B) -- Vergleichsstunde
    bei GLEICHEM `thunder_level`, damit ein Unterschied NUR vom Hagel-Flag
    stammen kann."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 14, 0, tzinfo=timezone.utc),
        duration_hours=6.0, distance_km=10.0, ascent_m=700.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
            t2m_c=20.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.5,
            pop_pct=20, cloud_total_pct=50, thunder_level=ThunderLevel.HIGH,
            hail_flag=True,
        ),
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
            t2m_c=21.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.5,
            pop_pct=20, cloud_total_pct=50, thunder_level=ThunderLevel.HIGH,
            hail_flag=None,
        ),
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)
    agg = SegmentWeatherSummary(
        temp_min_c=18.0, temp_max_c=22.0, wind_max_kmh=10.0, gust_max_kmh=20.0,
        precip_sum_mm=1.0, thunder_level_max=ThunderLevel.HIGH, hail_flag=True,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _segment_ohne_jede_hagelstunde() -> SegmentWeatherData:
    """Gegenstueck fuer AC-3: eine Gewitterstunde, aber `hail_flag=None`
    (unbekannt) -- keine Zeile darf den Doppelring zeigen."""
    seg_data = _segment_zwei_stunden_high_hagel_a_kein_hagel_b()
    new_data = [
        ForecastDataPoint(
            ts=dp.ts, t2m_c=dp.t2m_c, wind10m_kmh=dp.wind10m_kmh,
            gust_kmh=dp.gust_kmh, precip_1h_mm=dp.precip_1h_mm,
            pop_pct=dp.pop_pct, cloud_total_pct=dp.cloud_total_pct,
            thunder_level=dp.thunder_level, hail_flag=None,
        )
        for dp in seg_data.timeseries.data
    ]
    ts = NormalizedTimeseries(meta=seg_data.timeseries.meta, data=new_data)
    agg = SegmentWeatherSummary(
        temp_min_c=18.0, temp_max_c=22.0, wind_max_kmh=10.0, gust_max_kmh=20.0,
        precip_sum_mm=1.0, thunder_level_max=ThunderLevel.HIGH, hail_flag=None,
    )
    return SegmentWeatherData(
        segment=seg_data.segment, timeseries=ts, aggregated=agg,
        fetched_at=seg_data.fetched_at, provider="openmeteo",
    )


def _render(seg_data: SegmentWeatherData):
    from output.renderers.trip_report import TripReportFormatter

    report = TripReportFormatter().format_email(
        [seg_data], trip_name="Hagel-Doppelring-Test", report_type="evening",
        stage_name="Etappe 1", tz=_TZ, display_config=_dc_ampel_kreis_modus(),
    )
    return report.email_html


def _thunder_cells(html: str) -> list[str]:
    """Alle `<td data-label="Thdr">`-Zellen der Desktop-Stundentabelle."""
    m = re.search(r'<table[^>]*data-table="resp"[^>]*>.*?</table>', html, re.S)
    assert m, f"Stundentabelle nicht gefunden. HTML-Ausschnitt: {html[:1500]!r}"
    return re.findall(r'<td[^>]*data-label="Thdr"[^>]*>.*?</td>', m.group(0), re.S)


def _box_shadow_layer_count(cell_html: str) -> int:
    """Anzahl der Ring-Layer im `box-shadow`-Wert des `<span>` (kommagetrennt)."""
    m = re.search(r'box-shadow:([^;"]+)', cell_html)
    assert m, f"Keine box-shadow-Deklaration in der Zelle gefunden: {cell_html!r}"
    return len(m.group(1).split(","))


# =============================================================================
# AC-2 — Doppelring erscheint bei hail_flag=True, Vergleichsstunde bleibt einfach
# =============================================================================

def test_ac2_hail_true_stunde_zeigt_zusaetzlichen_aeusseren_ring():
    html = _render(_segment_zwei_stunden_high_hagel_a_kein_hagel_b())
    cells = _thunder_cells(html)
    assert len(cells) == 2, f"Erwarte genau zwei Gewitter-Zellen, gefunden: {cells!r}"

    layer_a = _box_shadow_layer_count(cells[0])  # Stunde 10, hail_flag=True
    layer_b = _box_shadow_layer_count(cells[1])  # Stunde 12, hail_flag=None

    assert layer_a > layer_b, (
        f"AC-2: Die Zelle mit hail_flag=True muss MEHR box-shadow-Ring-Layer "
        f"zeigen als die Vergleichsstunde mit hail_flag=None (gleicher "
        f"thunder_level). A={layer_a} (>{cells[0]!r}), "
        f"B={layer_b} (>{cells[1]!r})"
    )


# =============================================================================
# AC-3 — Erklaerungssatz NUR bei mindestens einem Doppelring
# =============================================================================

def test_ac3_erklaerungssatz_erscheint_nur_bei_mindestens_einem_doppelring():
    html_mit_hagel = _render(_segment_zwei_stunden_high_hagel_a_kein_hagel_b())
    html_ohne_hagel = _render(_segment_ohne_jede_hagelstunde())

    satz = "Doppelring bei Gewitter = Hagel möglich"
    assert satz in html_mit_hagel, (
        f"AC-3: mindestens eine Zeile zeigt den Doppelring -- der "
        f"Erklaerungssatz {satz!r} muss unter der Tabelle erscheinen. "
        f"HTML-Ausschnitt: {html_mit_hagel[:2000]!r}"
    )
    assert satz not in html_ohne_hagel, (
        f"AC-3: KEINE Zeile zeigt den Doppelring (alle hail_flag None) -- "
        f"der Erklaerungssatz {satz!r} darf NICHT erscheinen (kein Rauschen). "
        f"HTML-Ausschnitt: {html_ohne_hagel[:2000]!r}"
    )
