"""TDD RED — Adversary-Runde 2 zu #1474, F004/F005: die +1/+2-Tages-Vorschau
im Trip-Report kennt ``ThunderLevel.LOW`` nicht.

F004 (CRITICAL): ``_thunder_entry_from_trend_row()`` indiziert eine lokale
``{NONE:0, MED:1, HIGH:2}``-Kopie mit dem Level als Key — fuer ``LOW`` fehlt
der Eintrag, das Lookup wirft ``KeyError`` und reisst den kompletten
Versandpfad (``send_trip_report``) mit.

F005 (CRITICAL): ``_build_thunder_forecast()`` hat dieselbe Luecke in einer
zweiten lokalen Kopie (``_ORD``) fuer die Peak-Ermittlung UND den Text-Zweig
(``if/elif/else``) — ein reines LOW-Signal faellt in den ELSE-Zweig und wird
als "Starkes Gewitter erwartet" gemeldet, das genaue Gegenteil der in AC-6
vorgeschriebenen Deckelung.

Spec: docs/specs/modules/feat_1474_gewitter_befund_stufen.md v2.4
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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
from output.tokens.dto import HourlyValue
from services.trip_report_scheduler import TripReportSchedulerService

_TARGET = date(2026, 8, 4)
_UTC = ZoneInfo("UTC")


def _dp(day: date, hour: int, thunder: ThunderLevel = ThunderLevel.NONE) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(day.year, day.month, day.day, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=10.0, gust_kmh=20.0, precip_1h_mm=0.0,
        cloud_total_pct=50, thunder_level=thunder, humidity_pct=55,
    )


def _segment(seg_id: int, data_points: list, thunder_level_max=ThunderLevel.NONE) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=47.10, lon=11.30, elevation_m=500.0),
        end_point=GPXPoint(lat=47.11, lon=11.31, elevation_m=600.0),
        start_time=data_points[0].ts, end_time=data_points[-1].ts,
        duration_hours=(data_points[-1].ts - data_points[0].ts).total_seconds() / 3600,
        distance_km=5.0, ascent_m=150.0, descent_m=0.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test",
                               run=datetime(_TARGET.year, _TARGET.month, _TARGET.day, tzinfo=timezone.utc),
                               grid_res_km=1.0, interp="point_grid"),
            data=data_points,
        ),
        aggregated=SegmentWeatherSummary(thunder_level_max=thunder_level_max),
        fetched_at=data_points[0].ts, provider="openmeteo",
    )


class TestThunderEntryFromTrendRowLow:
    """F004: der Trend-Zeilen-Pfad (Evening-Default, Trend deckt +1/+2 ab)."""

    def test_low_does_not_crash_and_reports_correct_hour(self):
        """
        GIVEN: eine Trend-Zeile mit thunder="LOW" und hourly_thunder-Samples,
               deren Werte der kanonischen Render-Skala entsprechen
               (thunder_label_value(LOW) == 1)
        WHEN:  _thunder_entry_from_trend_row() die Zeile abbildet
        THEN:  KEIN KeyError, Level LOW, Stunde = die fruehste Stunde mit
               Wert 1 (14:00)
        """
        row = {
            "thunder": "LOW",
            "hourly_thunder": (
                HourlyValue(hour=10, value=0.0),
                HourlyValue(hour=14, value=1.0),
                HourlyValue(hour=16, value=1.0),
            ),
        }
        entry = TripReportSchedulerService()._thunder_entry_from_trend_row(row, _TARGET)

        assert entry["level"] == ThunderLevel.LOW
        assert entry["hour"] == 14, f"Erwartet fruehste Stunde 14, war {entry!r}"
        assert "14:00" in entry["text"]

    def test_med_and_high_text_unchanged(self):
        """Gegenprobe: MED/HIGH liefern weiterhin ihre bisherigen Texte."""
        med_row = {
            "thunder": "MED",
            "hourly_thunder": (HourlyValue(hour=8, value=2.0),),
        }
        high_row = {
            "thunder": "HIGH",
            "hourly_thunder": (HourlyValue(hour=9, value=3.0),),
        }
        svc = TripReportSchedulerService()

        med_entry = svc._thunder_entry_from_trend_row(med_row, _TARGET)
        high_entry = svc._thunder_entry_from_trend_row(high_row, _TARGET)

        assert med_entry["level"] == ThunderLevel.MED
        assert med_entry["text"] == "Gewitter möglich ab 08:00"
        assert high_entry["level"] == ThunderLevel.HIGH
        assert high_entry["text"] == "Starkes Gewitter erwartet ab 09:00"


class TestBuildThunderForecastLow:
    """F005: der Fallback-Fetch-Pfad, der direkt auf Segmenten aggregiert."""

    def test_low_signal_text_distinct_from_high_and_med(self):
        """
        GIVEN: ein reines LOW-Signal (kein MED/HIGH-Punkt im Fenster)
        WHEN:  _build_thunder_forecast() den Text ableitet
        THEN:  der Text unterscheidet sich NACHWEISLICH vom HIGH- und
               MED-Text, spiegelt "leicht" wider (AC-6: CAPE-Deckelung darf
               nicht ins Gegenteil verkehrt werden)
        """
        points = [
            _dp(_TARGET + timedelta(days=1), h,
                thunder=ThunderLevel.LOW if h == 14 else ThunderLevel.NONE)
            for h in range(0, 24)
        ]
        seg = _segment(1, points, thunder_level_max=ThunderLevel.LOW)

        fc = TripReportSchedulerService()._build_thunder_forecast(seg, _TARGET, tz=_UTC)

        assert fc is not None and "+1" in fc, f"Kein +1-Eintrag: {fc!r}"
        entry = fc["+1"]
        assert entry["level"] == ThunderLevel.LOW
        high_text = "Starkes Gewitter erwartet ab 14:00"
        med_text = "Gewitter möglich ab 14:00"
        assert entry["text"] != high_text, (
            f"F005: LOW darf NICHT als starkes Gewitter gemeldet werden: {entry['text']!r}"
        )
        assert entry["text"] != med_text
        assert "leicht" in entry["text"].lower(), (
            f"LOW-Text muss 'leicht' benennen (Skala AC-6): {entry['text']!r}"
        )

    def test_med_and_high_text_unchanged(self):
        """Gegenprobe: MED/HIGH liefern weiterhin ihre bisherigen Texte."""
        med_points = [
            _dp(_TARGET + timedelta(days=1), h,
                thunder=ThunderLevel.MED if h == 9 else ThunderLevel.NONE)
            for h in range(0, 24)
        ]
        high_points = [
            _dp(_TARGET + timedelta(days=1), h,
                thunder=ThunderLevel.HIGH if h == 9 else ThunderLevel.NONE)
            for h in range(0, 24)
        ]
        svc = TripReportSchedulerService()

        med_fc = svc._build_thunder_forecast(
            _segment(1, med_points, thunder_level_max=ThunderLevel.MED), _TARGET, tz=_UTC,
        )
        high_fc = svc._build_thunder_forecast(
            _segment(2, high_points, thunder_level_max=ThunderLevel.HIGH), _TARGET, tz=_UTC,
        )

        assert med_fc["+1"]["text"] == "Gewitter möglich ab 09:00"
        assert high_fc["+1"]["text"] == "Starkes Gewitter erwartet ab 09:00"

    def test_low_not_lost_against_none_in_peak_selection(self):
        """
        F005 zweiter Effekt: ``_ORD.get(lv, 0)`` gab LOW denselben Rang wie
        NONE -- bei gemischten Punkten (NONE + LOW) muss max() weiterhin LOW
        als Spitzenlevel erkennen, nicht NONE.
        """
        points = [
            _dp(_TARGET + timedelta(days=1), h,
                thunder=ThunderLevel.LOW if h == 12 else ThunderLevel.NONE)
            for h in range(0, 24)
        ]
        seg = _segment(1, points, thunder_level_max=ThunderLevel.LOW)

        fc = TripReportSchedulerService()._build_thunder_forecast(seg, _TARGET, tz=_UTC)

        assert fc["+1"]["level"] == ThunderLevel.LOW, (
            f"LOW muss gegen NONE gewinnen, nicht gleichrangig verloren gehen: {fc!r}"
        )
