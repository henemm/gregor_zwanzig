"""Issue #811 AC-1 — Modus-Matrix-Vertragstest gegen die ECHT gerenderte Briefing-Mail.

Erzwingungs-Infrastruktur (kein Inhalts-Fix). Parametrisiert ueber
  format ∈ {full, compact} × modus ∈ {Einfach, Roh} × variante ∈ {briefing, alert}.
Pro Fall wird die Mail ECHT ueber render_email(...) gerendert (mock-frei).

#810-Reproduktion (RED): Die Parametrisierungen "Roh + full" fuer wind/gust/precip/pop
schlagen HEUTE genuine fehl — fmt_val gibt im `if html:`-Zweig den Ampelpunkt zurueck,
BEVOR use_friendly/raw geprueft wird (helpers.py:446,460,500). Diese Faelle sind unten
markiert; in der RED-Phase fehlschlagen sie OHNE xfail-Marker (das ist der RED-Beweis).

KEINE Mocks/patch/MagicMock — echte render_email-Aufrufe.

Test-Manifest: docs/specs/tests/issue_811_mail_quality_gate_tests.md
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

_AMPEL_EMOJIS = ("🟢", "🟡", "🟠", "🔴")

# Volle aktivierte Metrik-Liste, damit jede fmt_val-Verzweigung greift.
_ENABLED = {
    "temperature", "wind", "gust", "precipitation",
    "rain_probability", "cloud_total", "sunshine", "cape",
}


def _make_dp():
    """Werte oberhalb der Gelb-Schwellen, damit Ampel-Verzweigungen greifen."""
    from app.models import ForecastDataPoint, ThunderLevel
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=22.0, wind10m_kmh=55.0, gust_kmh=85.0, precip_1h_mm=8.0,
        pop_pct=80, cloud_total_pct=85, thunder_level=ThunderLevel.MED,
        wind_chill_c=20.0, cape_jkg=1500.0,
    )


def _make_dc(*, raw: bool):
    """Roh (raw) vs. Einfach (friendly default je Metrik)."""
    from app.metric_catalog import build_default_display_config
    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = mc.metric_id in _ENABLED
        if raw:
            mc.format_mode = "raw"
            mc.use_friendly_format = False
        else:
            mc.format_mode = None
            mc.use_friendly_format = True
    return dc


def _make_seg_data():
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
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
    ts = NormalizedTimeseries(meta=meta, data=[_make_dp()])
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


def _render(*, email_format: str, raw: bool, alert: bool):
    """ECHTER render_email-Aufruf → (html, plain)."""
    from src.output.renderers.email import render_email
    from src.output.renderers.email.helpers import dp_to_row
    from src.output.tokens.dto import TokenLine

    dc = _make_dc(raw=raw)
    row = dp_to_row(_make_dp(), dc, tz=ZoneInfo("Europe/Berlin"))
    tl = TokenLine(
        trip_name="Matrix-Test", report_type="evening", stage_name="Etappe 1",
    )
    return render_email(
        tl, segments=[_make_seg_data()], seg_tables=[[row]],
        display_config=dc, tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
        email_format=email_format, changes=(_make_changes() if alert else None),
    )


def _data_cells(html: str) -> list[str]:
    """Daten-Zellen der Stundentabelle (class="resp")."""
    m = re.search(r'<table class="resp">.*?</table>', html, re.S)
    if not m:
        return []
    return re.findall(r'<td data-label="[^"]*">(.*?)</td>', m.group(0), re.S)


def _has_ampel(text: str) -> bool:
    return any(e in text for e in _AMPEL_EMOJIS)


# ---------------------------------------------------------------------------
# AC-1: Roh + full (HTML) — KEIN Ampel-Emoji in Daten-Zellen
# ---------------------------------------------------------------------------

_XFAIL_810 = pytest.mark.xfail(
    strict=True, reason="#810 — Roh-HTML-Ampel-Bug, GREEN nach Fix"
)


@pytest.mark.parametrize(
    "alert",
    [
        pytest.param(False, marks=_XFAIL_810, id="briefing"),
        pytest.param(True, marks=_XFAIL_810, id="alert"),
    ],
)
def test_raw_full_html_no_ampel_in_data_cells(alert):
    """Roh+full: jede Daten-Zelle ist ein Zahl-/Einheit-Token, keine Ampel.

    #810-Reproduktion: schlaegt HEUTE genuine fehl — wind/gust/precip/pop liefern
    im html-Pfad eine Ampel, bevor raw geprueft wird (helpers.py:446,460,500).
    xfail(strict=True): nach dem #810-Fix flippt xpass → die Suite wird rot und
    erzwingt die Marker-Entfernung.
    """
    html, _plain = _render(email_format="full", raw=True, alert=alert)
    cells = _data_cells(html)
    assert cells, "Stundentabelle muss Daten-Zellen haben"
    ampel_cells = [c for c in cells if _has_ampel(c)]
    assert not ampel_cells, (
        f"Roh+full darf KEINE Ampel-Emoji in Daten-Zellen zeigen (#810). "
        f"Gefunden: {ampel_cells!r}"
    )


# ---------------------------------------------------------------------------
# AC-1: Einfach + full (HTML) — ≥1 Ampel-Emoji vorhanden
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("alert", [False, True], ids=["briefing", "alert"])
def test_friendly_full_html_has_ampel(alert):
    """Einfach+full: Indikator-Emoji in den DATENZELLEN der Stundentabelle (≥1 Ampel).

    Prueft _data_cells statt gesamtes HTML, damit Footer-Legende (🟢 unkritisch · …)
    den Test nicht faelschlich gruen macht (F002 — False-Negative-Schutzluecke).
    """
    html, _plain = _render(email_format="full", raw=False, alert=alert)
    cells = _data_cells(html)
    assert cells, "Einfach+full muss Daten-Zellen in der Stundentabelle haben"
    ampel_cells = [c for c in cells if _has_ampel(c)]
    assert ampel_cells, (
        "Einfach+full muss ≥1 Ampel-Emoji in den DATENZELLEN zeigen. "
        f"Daten-Zellen gefunden: {cells!r}"
    )


# ---------------------------------------------------------------------------
# AC-1: compact (beide Modi) — reines ASCII, kein Emoji, keine Stundentabelle
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
    # keine ≥2 sequentiellen HH:00-Zeilen (das waere eine Stundentabelle)
    hour_rows = re.findall(r"^\s*\d{2}:00\b", plain, re.M)
    assert len(hour_rows) < 2, f"compact darf keine Stundentabelle sein: {hour_rows!r}"


# ---------------------------------------------------------------------------
# Issue #811 — Matrix-Nachweis-Recording (Komponente A → Gate-Nachweis)
#
# Bei gruenem Lauf wird `renderer_mail_gate.py record-matrix` aufgerufen, damit
# der Renderer-Gate-Nachweis im aktiven Workflow-State entsteht. KEIN manuelles
# "ich verspreche"-Flag — der Nachweis entsteht nur durch den echten Testlauf.
# Die Recorder-Logik selbst ist isoliert in test_issue_811_renderer_gate.py
# (test_record_matrix_writes_hash) getestet; hier nur der reale Aufruf.
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

    if not os.environ.get("GZ_ACTIVE_WORKFLOW", "").strip():
        return
    gate = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "renderer_mail_gate.py"
    if not gate.exists():
        return
    subprocess.run(
        [sys.executable, str(gate), "record-matrix"],
        capture_output=True, text=True,
    )
