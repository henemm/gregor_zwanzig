"""
TDD RED: Kurzform-Zusammenfassung <-> Stundentabelle Konsistenz (Workflow fix-briefing-grid-and-summary, Fix B).

SPEC: docs/specs/modules/briefing_grid_and_summary_consistency.md AC-2/AC-3(b)

Belegter Hergang (12:00-KHW-Mail): Die Kurzform warnte "Gewitter moeglich
16:00-18:00", obwohl die Stundentabellen (Segment-Tabelle + Nacht-Block) fuer
16:00/18:00 "Regen 0.0"/"Gewitter -" zeigten -- eine Warnung ohne deckende
Tabellenzeile.

Root Cause (verifiziert am echten Code, keine Vermutung): Die Kurzform-Quelle
``day_window.build_day_window_points()`` filtert den Nacht-Anteil NUR nach
Ortszeit-Stunde (``arrival_hour <= h <= DAY_WINDOW_END_HOUR``), OHNE Datum zu
pruefen. Datenpunkte eines SPAETEREN Kalendertags mit derselben Uhrzeit (z.B.
Folgetag 16:00) rutschen so in den Merge fuer "Stunde 16" und ueberschreiben
den echten (ruhigen) Wert von HEUTE via ``_merge_hour`` (nimmt das jeweils
staerkere Signal). Die Tabellen-Quelle ``trip_report._extract_night_rows()``
filtert dagegen korrekt nach Datum (``is_same_day``/``is_next_day ==
first_date + 1 Tag``, s. Issue #956) -- der kontaminierte Folgetag-Punkt
erscheint dort NIRGENDS, weil seine Stunde (16) > 6 fuer den Folgetag-Zweig
ist. Ergebnis: Kurzform behauptet ein Gewitter-/Regenfenster, das KEINE
gerenderte Tabellenzeile deckt.

Kein Mock: echte ``ForecastDataPoint``/``SegmentWeatherData``/
``NormalizedTimeseries``-Objekte, echte Formatter-Methoden (analog
tests/unit/test_day_window_gap_detection.py und
tests/tdd/test_issue_956_night_rows_date_bug.py).

Muss VOR Fix B rot sein (Kurzform meldet "16:00"/"Gewitter" trotz leerer
Tabellenzeilen), NACH Fix B gruen.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.app.metric_catalog import build_default_display_config
from src.app.models import (
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
from src.output.renderers.compact_summary import CompactSummaryFormatter
from src.output.renderers.trip_report import TripReportFormatter

_TZ = ZoneInfo("UTC")


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _quiet_dp(day: int, hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=18.0, wind10m_kmh=5.0, gust_kmh=8.0, precip_1h_mm=0.0,
        pop_pct=0, cloud_total_pct=30, thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )


def _storm_dp(day: int, hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=17.0, wind10m_kmh=10.0, gust_kmh=25.0, precip_1h_mm=8.0,
        pop_pct=90, cloud_total_pct=95, thunder_level=ThunderLevel.HIGH,
        humidity_pct=80,
    )


def _wander_segment() -> SegmentWeatherData:
    """Wanderzeit 08:00-11:00 am 20.7. -- ruhige Daten, kein Gewitter/Regen."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=41.9, lon=8.7, elevation_m=800.0),
        end_point=GPXPoint(lat=42.0, lon=8.8, elevation_m=1100.0),
        start_time=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 20, 11, 0, tzinfo=timezone.utc),
        duration_hours=3.0, distance_km=6.0, ascent_m=300.0, descent_m=0.0,
    )
    data = [_quiet_dp(20, h) for h in range(8, 12)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(temp_min_c=14.0, temp_max_c=19.0),
        fetched_at=datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _night_weather_with_leaked_next_day_peak() -> NormalizedTimeseries:
    """Ankunftstag (20.7., 11-19 Uhr) real ruhig + Folgetag (21.7.) 16/17 Uhr
    Sturm-Kontamination.

    Der Folgetag-Peak liegt bei ``h<=6``-Ausschluss (``_extract_night_rows``)
    NIE in einer Tabellenzeile, kontaminiert aber ``build_day_window_points``
    (kein Datumsfilter) die Stunden 16/17 im Kurzform-Fenster.
    """
    same_day = [_quiet_dp(20, h) for h in range(11, 20)]
    leaked_next_day = [_storm_dp(21, 16), _storm_dp(21, 17)]
    return NormalizedTimeseries(meta=_meta(), data=same_day + leaked_next_day)


class TestShortformMatchesTableWindow:
    """AC-2: Kurzform darf keine Gewitter-/Regen-Aussage treffen, die keine
    gerenderte Tabellenzeile deckt."""

    def _build(self):
        segments = [_wander_segment()]
        night_weather = _night_weather_with_leaked_next_day_peak()
        dc = build_default_display_config()
        return segments, night_weather, dc

    def test_table_rows_show_no_thunder_or_rain_anywhere(self):
        """Vorbedingung: die tatsaechlich gerenderten Tabellenzeilen (Segment
        + Nacht-Block) sind komplett ruhig -- der Sturm-Peak vom Folgetag
        erscheint in KEINER Zeile (Datumsfilter greift korrekt)."""
        segments, night_weather, dc = self._build()
        fmt = TripReportFormatter()
        fmt._tz = _TZ

        seg_rows = fmt._extract_hourly_rows(segments[0], dc)
        night_rows = fmt._extract_night_rows(
            night_weather, arrival_hour=11, interval=2, dc=dc,
        )

        all_rows = seg_rows + night_rows
        assert all_rows, "Testaufbau fehlerhaft: keine Tabellenzeilen erzeugt"
        for row in all_rows:
            assert row.get("precip") in (0.0, None), (
                f"Tabellenzeile zeigt Regen, Testaufbau falsch: {row}"
            )
            assert row.get("thunder") in (ThunderLevel.NONE, None), (
                f"Tabellenzeile zeigt Gewitter, Testaufbau falsch: {row}"
            )

    def test_compact_summary_reports_no_thunder_without_table_coverage(self):
        """AC-2/AC-3(b): Kurzform darf kein Gewitter melden, weil keine
        Tabellenzeile es zeigt (Vorbedingung oben bewiesen).

        RED (vor Fix B): ``build_day_window_points`` mischt den Folgetag-Peak
        ungefenstert nach Stunde in "16:00 Uhr" -- die Kurzform behauptet
        "Gewitter moeglich 16:00-18:00" bzw. Regen ab/um 16:00.
        GRUEN (nach Fix B): keine Gewitter-/Regen-Aussage fuer 16:00.
        """
        segments, night_weather, dc = self._build()
        summary = CompactSummaryFormatter().format_stage_summary(
            segments, "Etappe KHW", dc, tz=_TZ, night_weather=night_weather,
        )

        assert "⚡" not in summary, (
            f"Kurzform meldet Gewitter ohne deckende Tabellenzeile: {summary!r}"
        )
        assert "16:00" not in summary, (
            f"Kurzform nennt eine Uhrzeit, die keine Tabellenzeile stuetzt: {summary!r}"
        )
        assert "trocken" in summary, (
            f"Erwartet 'trocken' (alle echten Tabellenstunden sind regenfrei): {summary!r}"
        )
