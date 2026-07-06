"""TDD RED — Issue #778: Toten Code in trip_report.py entfernen.

SPEC: docs/specs/modules/issue_783_776_778_briefing_fixes.md (AC-5)

`format_email` delegiert seit beta3 an `render_email()`. Fuenf Methoden in
`src/formatters/trip_report.py` sind toter Code und lesen u.a. den seit #759
nicht mehr existierenden `display_thresholds`-Key `blue`:
  _fmt_val, _render_html_table, _render_text_table,
  _format_daylight_html, _format_daylight_plain

`dead_formatter_methods_removed` ist die ROT-Probe: solange die Methoden existieren,
schlaegt sie fehl. `format_email_renders_after_dead_code_removal` ist der
Verhaltens-/Regressionsschutz: der echte Render-Pfad muss vor UND nach der Loeschung
funktionieren (kein Mock).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_DEAD_METHODS = [
    "_fmt_val",
    "_render_html_table",
    "_render_text_table",
    "_format_daylight_html",
    "_format_daylight_plain",
]

_TRIP_REPORT = (
    Path(__file__).resolve().parents[2] / "src" / "formatters" / "trip_report.py"
)


def _make_segment():
    """Ein echtes SegmentWeatherData-Objekt mit einer Stundenreihe (kein Mock)."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary,
        GPXPoint, TripSegment,
    )

    target = date(2026, 7, 15)
    start = datetime(target.year, target.month, target.day, 8, 0, tzinfo=timezone.utc)
    end = datetime(target.year, target.month, target.day, 11, 0, tzinfo=timezone.utc)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=64.1, lon=-21.9, elevation_m=50.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=64.2, lon=-21.0, elevation_m=100.0,
                           distance_from_start_km=5.0),
        start_time=start, end_time=end, duration_hours=3.0,
        distance_km=5.0, ascent_m=50.0, descent_m=0.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="icon_d2",
                        run=start, grid_res_km=2.0, interp="nearest")
    data = [
        ForecastDataPoint(
            ts=datetime(target.year, target.month, target.day, h, 0,
                        tzinfo=timezone.utc),
            t2m_c=12.0 + h, wind10m_kmh=10.0, gust_kmh=20.0,
            pop_pct=10, precip_1h_mm=0.0,
        )
        for h in range(8, 12)
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(),
        fetched_at=start, provider="openmeteo",
    )


# ===========================================================================
# AC-5: format_email rendert weiterhin korrekt (Verhaltens-/Regressionsschutz)
# ===========================================================================

def test_format_email_renders_after_dead_code_removal():
    """AC-5: GIVEN ein echtes Segment / WHEN format_email aufgerufen wird /
    THEN entstehen nicht-leerer HTML- und Plaintext-Output ohne AttributeError/KeyError.

    Muss VOR und NACH der Loeschung gruen sein — beweist, dass der aktive
    render_email()-Pfad nicht von den toten Methoden abhaengt.
    """
    from formatters.trip_report import TripReportFormatter

    formatter = TripReportFormatter()
    report = formatter.format_email(
        segments=[_make_segment()],
        trip_name="Startzeit-Trip",
        report_type="morning",
        tz=ZoneInfo("Atlantic/Reykjavik"),
    )
    assert report.email_html and len(report.email_html) > 100, "HTML-Output muss nicht-leer sein"
    assert report.email_plain and len(report.email_plain) > 50, "Plain-Output muss nicht-leer sein"


# ===========================================================================
# AC-5: tote Methoden sind entfernt (# doc-compliance-test)
# ===========================================================================

def test_dead_formatter_methods_removed():  # doc-compliance-test
    """AC-5: GIVEN trip_report.py nach dem Aufraeumen / WHEN die Datei gelesen wird /
    THEN definieren keine der fuenf toten Methoden mehr ein `def`.

    RED: aktuell sind alle fuenf vorhanden. Markiert als doc-compliance-test, da
    #778 ein reiner Tote-Code-Entfernungs-Bug ist (Struktur-Artefakt, kein Verhalten).
    """
    src = _TRIP_REPORT.read_text(encoding="utf-8")
    still_present = [m for m in _DEAD_METHODS if f"def {m}(" in src]
    assert not still_present, (
        f"Tote Methoden noch in trip_report.py vorhanden: {still_present} — "
        f"#778 verlangt ersatzlose Loeschung (kanonische Logik in "
        f"src/output/renderers/email/)"
    )
