"""
TDD RED tests — Bundle #771 / #796 / #787
  #771: Spaltenköpfe in der Breite optimieren (Thunder → Blitz)
  #796: Compact-Mail °C wird als "CC" transliteriert
  #787: Outbound-Briefing Trip.shortcode fehlt im Betreff

SPEC: docs/specs/modules/bundle_771_796_787_mail_darstellung.md

Expected at RED-time:
  AC-1 → FAIL: get_col_defs() gibt noch col_label="Thunder" zurück (7 Zeichen)
  AC-2 → FAIL: visible_cols() liefert "Thunder" für den thunder-Schlüssel
  AC-3 → FAIL: render_compact() gibt "CC" als Einheit aus (°→C-Map-Bug)
  AC-4 → FAIL: format_email() kennt kein shortcode-Parameter (TypeError)
  AC-5 → FAIL: format_email() kennt kein shortcode-Parameter (TypeError)
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


from app.metric_catalog import build_default_display_config, get_col_defs
from app.models import (
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
from formatters.trip_report import TripReportFormatter
from output.renderers.email.compact import render_compact
from output.renderers.email.helpers import visible_cols

# ---------------------------------------------------------------------------
# Fixture helpers (mock-free)
# ---------------------------------------------------------------------------

_YEAR, _MONTH, _DAY = 2026, 7, 15
_UTC = ZoneInfo("UTC")


def _dp(hour: int, temp: float = 15.0) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=timezone.utc),
        t2m_c=temp,
        wind10m_kmh=20.0,
        gust_kmh=30.0,
        precip_1h_mm=0.0,
        cloud_total_pct=40,
        thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _segment(start_hour: int = 8, end_hour: int = 18) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.1, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.2, lon=9.1, elevation_m=800.0),
        start_time=datetime(_YEAR, _MONTH, _DAY, start_hour, 0, tzinfo=timezone.utc),
        end_time=datetime(_YEAR, _MONTH, _DAY, end_hour, 0, tzinfo=timezone.utc),
        duration_hours=float(end_hour - start_hour),
        distance_km=12.0,
        ascent_m=600.0,
        descent_m=100.0,
    )
    data = [_dp(h, temp=10.0 + h * 0.5) for h in range(0, 24)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    summary = SegmentWeatherSummary(
        temp_min_c=10.0,
        temp_max_c=22.0,
        temp_avg_c=16.0,
        wind_max_kmh=25.0,
        gust_max_kmh=35.0,
        precip_sum_mm=0.0,
        cloud_avg_pct=40,
        humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
        wind_chill_min_c=8.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


# ---------------------------------------------------------------------------
# AC-1: col_label für thunder ≤5 Zeichen, nicht "Thunder"
# ---------------------------------------------------------------------------

class TestAC1ThunderColLabel:
    """
    GIVEN: MetricCatalog mit thunder-Metrik
    WHEN: get_col_defs() aufgerufen wird
    THEN: thunder-Eintrag hat col_label ≤5 Zeichen (nicht "Thunder")
    """

    def test_thunder_col_label_not_thunder(self):
        col_defs = get_col_defs()
        thunder_label = next(
            (label for key, label, _ in col_defs if key == "thunder"), None
        )
        assert thunder_label is not None, "thunder muss in col_defs vorhanden sein"
        assert thunder_label != "Thunder", (
            f"col_label darf nicht 'Thunder' (7 Zeichen) sein, ist: {thunder_label!r}"
        )

    def test_thunder_col_label_max_5_chars(self):
        col_defs = get_col_defs()
        thunder_label = next(
            (label for key, label, _ in col_defs if key == "thunder"), None
        )
        assert thunder_label is not None
        assert len(thunder_label) <= 5, (
            f"col_label muss ≤5 Zeichen haben, ist {len(thunder_label)}: {thunder_label!r}"
        )


# ---------------------------------------------------------------------------
# AC-2: visible_cols() gibt für thunder keinen "Thunder"-Label zurück
# ---------------------------------------------------------------------------

class TestAC2CompactNoThunderLabel:
    """
    GIVEN: Stunden-Zeilen mit thunder-Spalte
    WHEN: visible_cols(rows) aufgerufen wird (liefert Labels für alle Renderer-Pfade)
    THEN: thunder-Label ist nicht "Thunder"
    """

    def test_visible_cols_thunder_not_thunder(self):
        rows = [{"time": "08:00", "thunder": "MED", "temp": 15, "wind": 20}]
        cols = visible_cols(rows)
        thunder_label = next((label for key, label in cols if key == "thunder"), None)
        assert thunder_label is not None, "thunder muss als Spalte erkannt werden"
        assert thunder_label != "Thunder", (
            f"visible_cols() liefert noch 'Thunder', erwartet kürzer: {thunder_label!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: render_compact() gibt Temperatur ohne "CC" aus
# ---------------------------------------------------------------------------

class TestAC3CompactNoCCUnit:
    """
    GIVEN: Compact-Renderer mit Segment das Temperatur-Daten enthält
    WHEN: render_compact() aufgerufen wird (ASCII 7bit Pfad)
    THEN: Ausgabe enthält kein "CC" als Einheit (war Bug: °C → CC durch ASCII-Map)
    """

    def test_compact_temperature_no_cc_unit(self):
        seg = _segment()
        dc = build_default_display_config()
        output = render_compact(
            segments=[seg],
            dc=dc,
            multi_day_trend=None,
            stability_result=None,
            tz=_UTC,
            report_type="morning",
            trip_name="GR20",
            stage_name="Etappe 1",
            stage_stats=None,
        )
        assert output.isascii(), "render_compact muss reines ASCII zurückgeben"
        assert "CC" not in output, (
            f"Compact enthält 'CC' — Grad-Zeichen °→C mappt auf 'CC' (Bug #796). Ausgabe:\n{output!r}"
        )



# ---------------------------------------------------------------------------
# AC-4: format_email() mit shortcode → Betreff beginnt mit [GZ#HERM]
# ---------------------------------------------------------------------------

class TestAC4ShortcodeInSubject:
    """
    GIVEN: TripReportFormatter.format_email() mit shortcode="GZ#HERM"
    WHEN: format_email() aufgerufen wird
    THEN: email_subject beginnt mit "[GZ#HERM]"

    RED: format_email() kennt kein shortcode-Parameter → TypeError
    """

    def test_format_email_subject_contains_shortcode(self):
        seg = _segment()
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="GR20",
            report_type="morning",
            tz=_UTC,
            shortcode="GZ#HERM",
        )
        assert report.email_subject.startswith("[GZ#HERM]"), (
            f"Betreff beginnt nicht mit [GZ#HERM]: {report.email_subject!r}"
        )


# ---------------------------------------------------------------------------
# AC-5: format_email() mit leerem shortcode → kein leeres [] im Betreff
# ---------------------------------------------------------------------------

class TestAC5EmptyShortcodeNoBrackets:
    """
    GIVEN: TripReportFormatter.format_email() mit shortcode="" (leer)
    WHEN: format_email() aufgerufen wird
    THEN: email_subject enthält kein leeres "[]"

    RED: format_email() kennt kein shortcode-Parameter → TypeError
    """

    def test_format_email_empty_shortcode_no_brackets(self):
        seg = _segment()
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="GR20",
            report_type="morning",
            tz=_UTC,
            shortcode="",
        )
        assert "[]" not in report.email_subject, (
            f"Betreff enthält leeres '[]': {report.email_subject!r}"
        )

    def test_format_email_none_shortcode_no_brackets(self):
        seg = _segment()
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="GR20",
            report_type="morning",
            tz=_UTC,
            shortcode=None,
        )
        assert "[]" not in report.email_subject, (
            f"Betreff enthält leeres '[]' bei shortcode=None: {report.email_subject!r}"
        )
