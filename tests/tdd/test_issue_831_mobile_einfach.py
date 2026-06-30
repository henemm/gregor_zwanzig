"""Issue #831 — Mobile Stundenraster: Ampel-Emojis im Einfach-Modus.

RED-Tests: Schlagen FEHL bis der Fix implementiert ist.

Root cause: _render_mobile_compact_rows ruft fmt_val(html=False) auf —
damit gibt fmt_val fuer Ampel-Metriken (wind/gust/precip/pop/cape) immer
Zahlen zurueck, egal ob Einfach-Modus aktiv ist.

Fix (geplant): _render_mobile_compact_rows erhaelt indicator_keys-Parameter;
wenn gesetzt → delegiert an _render_html_table (html=True) statt <pre>-Block.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

_AMPEL_EMOJIS = ("🟢", "🟡", "🟠", "🔴")


def _make_dp():
    """Werte oberhalb der Gelb-Schwellen, damit Ampel-Verzweigungen greifen."""
    from app.models import ForecastDataPoint
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=22.0, wind10m_kmh=55.0, gust_kmh=85.0, precip_1h_mm=8.0,
        pop_pct=80, cloud_total_pct=85,
        wind_chill_c=20.0, cape_jkg=1500.0,
        visibility_m=15000.0,
    )


def _make_dc(*, raw: bool, enabled: set[str] | None = None):
    from app.metric_catalog import build_default_display_config
    dc = build_default_display_config()
    active = enabled if enabled is not None else {"temperature", "wind", "gust", "precipitation", "rain_probability"}
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
        SegmentWeatherData, SegmentWeatherSummary, TripSegment, ThunderLevel,
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
        temp_min_c=18.0, temp_max_c=24.0, temp_avg_c=21.0,
        wind_max_kmh=55.0, gust_max_kmh=85.0, precip_sum_mm=8.0,
        cloud_avg_pct=85, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.MED, wind_chill_min_c=20.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _render(*, raw: bool, enabled: set[str] | None = None):
    """ECHTER render_email-Aufruf → (html, plain). Mock-frei."""
    from src.output.renderers.email import render_email
    from src.output.renderers.email.helpers import dp_to_row
    from src.output.tokens.dto import TokenLine

    dp = _make_dp()
    dc = _make_dc(raw=raw, enabled=enabled)
    row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Berlin"))
    tl = TokenLine(trip_name="Mobile-Einfach-Test", report_type="morning", stage_name="Etappe 1")
    return render_email(
        tl,
        segments=[_make_seg_data(dp=dp)],
        seg_tables=[[row]],
        display_config=dc,
        tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=set(),
        email_format="full",
    )


def _mobile_compact_inner(html: str) -> list[str]:
    """Extrahiert nur <pre>- oder <table>-Inhalte aus .mobile-compact Divs.

    Gibt den eigentlichen Daten-Block zurueck (pre-Text oder table-HTML),
    NICHT den gesamten Div-Chunk. So wird der Ampel-Footer/Legende
    nicht faelschlicherweise mitgezaehlt.
    """
    results = []
    for m in re.finditer(r'class="mobile-compact"[^>]*>', html):
        start = m.end()
        chunk = html[start:start + 2000]
        # Roh-Modus: <pre>-Block
        pre = re.search(r'<pre[^>]*>(.*?)</pre>', chunk, re.S)
        if pre:
            results.append(pre.group(1))
            continue
        # Einfach-Modus (nach Fix): <table>-Block
        table = re.search(r'(<table[^>]*>.*?</table>)', chunk, re.S)
        if table:
            results.append(table.group(1))
    return results


def _has_ampel(text: str) -> bool:
    return any(e in text for e in _AMPEL_EMOJIS)


def _has_pre_block(html: str) -> bool:
    """Prueft ob ein .mobile-compact Div einen <pre>-Block enthaelt (Roh-Modus)."""
    for m in re.finditer(r'class="mobile-compact"[^>]*>', html):
        start = m.end()
        chunk = html[start:start + 2000]
        if re.search(r'<pre[^>]*>', chunk):
            return True
    return False


# ---------------------------------------------------------------------------
# AC-1 RED: Mobile Einfach-Modus zeigt Ampel-Emojis (SCHLAEGT HEUTE FEHL)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("metric_id", [
    "wind", "gust", "precipitation", "rain_probability",
], ids=["wind", "gust", "precip", "pop"])
def test_mobile_compact_einfach_shows_ampel(metric_id):
    """AC-1 RED: Einfach-Modus → .mobile-compact-Div zeigt Ampel-Emojis.

    SCHLAEGT HEUTE FEHL: _render_mobile_compact_rows benutzt fmt_val(html=False),
    daher kommen fuer wind/gust/precip/pop immer Zahlen — nie Ampel-Emojis.

    Nach Fix: indicator_keys wird durchgereicht → _render_html_table → html=True
    → fmt_val gibt Ampel zurueck.
    """
    html, _plain = _render(raw=False, enabled={"temperature", metric_id})
    inner_blocks = _mobile_compact_inner(html)
    assert inner_blocks, "AC-1: Kein Daten-Block in .mobile-compact-Div gefunden"

    combined = "\n".join(inner_blocks)
    assert _has_ampel(combined), (
        f"AC-1 RED: Mobile Einfach-Modus muss Ampel-Emoji fuer '{metric_id}' zeigen. "
        f"Gefunden: kein Ampel in mobile-compact-Divs. "
        f"Bug: _render_mobile_compact_rows gibt html=False → fmt_val → Zahl statt Ampel. "
        f"Mobile-Block-Inhalt (Anfang): {combined[:500]!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 GREEN-Sicherung: Roh-Modus bleibt Monospace-<pre> (MUSS HEUTE GRUEN SEIN)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("metric_id", [
    "wind", "gust", "precipitation", "rain_probability",
], ids=["wind", "gust", "precip", "pop"])
def test_mobile_compact_roh_keeps_pre_block(metric_id):
    """AC-2 GREEN: Roh-Modus → .mobile-compact-Div enthaelt <pre>-Block, kein Ampel.

    Sichert das unveraenderte #636-Verhalten ab. Muss vor und nach dem Fix gruen sein.
    """
    html, _plain = _render(raw=True, enabled={"temperature", metric_id})
    assert _has_pre_block(html), (
        f"AC-2: Roh-Modus muss <pre>-Block im .mobile-compact enthalten fuer '{metric_id}'."
    )
    inner_blocks = _mobile_compact_inner(html)
    assert inner_blocks, "AC-2: Kein Daten-Block in .mobile-compact-Div gefunden"

    combined = "\n".join(inner_blocks)
    assert not _has_ampel(combined), (
        f"AC-2: Roh-Modus darf KEIN Ampel-Emoji im <pre>-Block zeigen fuer '{metric_id}'. "
        f"Gefunden: {[e for e in _AMPEL_EMOJIS if e in combined]}"
    )


# ---------------------------------------------------------------------------
# AC-3 RED: Kein Viewport-Mismatch — Desktop und Mobile im gleichen Modus
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("metric_id", [
    "wind", "gust", "precipitation", "rain_probability",
], ids=["wind", "gust", "precip", "pop"])
def test_no_viewport_mismatch_einfach(metric_id):
    """AC-3 RED: Einfach-Modus → Desktop UND Mobile zeigen beide Ampel.

    SCHLAEGT HEUTE FEHL: Desktop (.desktop-only) zeigt Ampel, aber
    Mobile (.mobile-compact) zeigt Zahlen → Viewport-Mismatch.
    """
    html, _plain = _render(raw=False, enabled={"temperature", metric_id})

    # Desktop: alle <table class="resp"> im HTML (diese sind ausschliesslich in
    # .desktop-only Divs; .mobile-compact benutzt bis zum Fix <pre>-Bloecke)
    desktop_tables = re.findall(r'<table class="resp">.*?</table>', html, re.S)
    desktop_combined = "\n".join(desktop_tables)
    desktop_has_ampel = _has_ampel(desktop_combined)

    # Mobile: nur pre/table-Inhalte aus .mobile-compact (kein Footer-Spillover)
    mobile_inner = _mobile_compact_inner(html)
    mobile_combined = "\n".join(mobile_inner)
    mobile_has_ampel = _has_ampel(mobile_combined)

    assert desktop_has_ampel, (
        f"AC-3: Desktop-Tabelle (class=resp) muss Ampel zeigen fuer '{metric_id}' im Einfach-Modus. "
        f"Desktop-Tabellen-Inhalt (Anfang): {desktop_combined[:300]!r}"
    )
    assert mobile_has_ampel, (
        f"AC-3 RED: Mobile-Daten-Block muss Ampel zeigen fuer '{metric_id}' im Einfach-Modus. "
        f"Viewport-Mismatch: Desktop hat Ampel, Mobile nicht. "
        f"Mobile-Block-Inhalt (Anfang): {mobile_combined[:500]!r}"
    )


def test_no_viewport_mismatch_roh():
    """AC-3 GREEN-Sicherung: Roh-Modus → weder Desktop noch Mobile zeigen Ampel.

    Muss vor und nach dem Fix gruen sein.
    """
    html, _plain = _render(raw=True, enabled={"temperature", "wind"})

    desktop_tables = re.findall(r'<table class="resp">.*?</table>', html, re.S)
    desktop_combined = "\n".join(desktop_tables)

    mobile_inner = _mobile_compact_inner(html)
    mobile_combined = "\n".join(mobile_inner)

    assert not _has_ampel(desktop_combined), (
        "AC-3 Roh: Desktop-Tabelle darf KEIN Ampel zeigen im Roh-Modus."
    )
    assert not _has_ampel(mobile_combined), (
        "AC-3 Roh: Mobile-Daten-Block darf KEIN Ampel zeigen im Roh-Modus."
    )
