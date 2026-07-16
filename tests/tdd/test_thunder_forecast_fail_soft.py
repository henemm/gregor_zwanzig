"""AC-3 (Bug #1275) — Fail-soft: kann die Wetterdaten-Beschaffung für die
tatsächliche Folge-Etappe nicht gelingen (echte Fehlerbedingung, KEIN Mock),
bricht der Trip-Report nicht ab: `_collect_future_stage_weather()` liefert eine
leere Liste, das `thunder_forecast`-Dict fehlt der "+1"-Eintrag und die SMS
zeigt `TH+:-`.

Echte Fehlerbedingung ohne Mock: Die morgige Etappe hat nur EINEN Waypoint.
`convert_trip_to_segments()` (services/trip_segments.py) liefert für Etappen mit
< 2 Waypoints bewusst `[]` — dieselbe reale Codepfad-Verzweigung, die auch bei
Datenlücken greift. Dadurch wird `_fetch_weather()` gar nicht erst aufgerufen
(kein Netzwerk), der Report läuft fail-soft weiter.

Spec: docs/specs/bugfix/fix_1275_sms_th_mismatch.md (AC-3)
"""
from __future__ import annotations

from datetime import date, timedelta

from src.app.trip import AggregationConfig, Stage, Trip, Waypoint
from src.output.renderers.sms_trip import SMSTripFormatter
from src.services.trip_report_scheduler import TripReportSchedulerService

from src.app.models import (
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)


def _today_segment() -> SegmentWeatherData:
    """Minimales heutiges Segment für den SMS-Formatter (kein Gewitter heute)."""
    from datetime import datetime, timezone

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=datetime(2026, 7, 15, 7, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 15, 17, 0, tzinfo=timezone.utc),
        duration_hours=10.0,
        distance_km=12.0,
        ascent_m=300.0,
        descent_m=0.0,
    )
    ts = NormalizedTimeseries(
        meta=ForecastMeta(
            provider=Provider.OPENMETEO, model="test",
            run=datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc),
            grid_res_km=1.0, interp="point_grid",
        ),
        data=[],
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(thunder_level_max=ThunderLevel.NONE),
        fetched_at=datetime(2026, 7, 15, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _trip_with_unfetchable_next_stage(today: date) -> Trip:
    """Trip, dessen morgige Etappe nur EINEN Waypoint hat → convert_trip_to_
    segments() liefert [] (reale Verzweigung, kein Mock) → Fetch scheitert
    fail-soft."""
    wp_a = Waypoint(id="A", name="Start", lat=42.0, lon=9.0, elevation_m=500)
    wp_b = Waypoint(id="B", name="Ziel", lat=42.1, lon=9.1, elevation_m=600)
    stages = [
        Stage(id="heute", name="Heute", date=today, waypoints=[wp_a, wp_b]),
        # Morgige Etappe: nur EIN Waypoint → keine Segmente ableitbar
        Stage(id="morgen", name="Morgen", date=today + timedelta(days=1),
              waypoints=[wp_a]),
    ]
    return Trip(
        id="failsoft", name="Fail-Soft Trip", stages=stages,
        avalanche_regions=[], aggregation=AggregationConfig(),
    )


class TestThunderForecastFailSoft:
    """AC-3: Fetch-Fehler der Folge-Etappe blockiert den Report nicht."""

    def test_unfetchable_next_stage_yields_empty_collection(self):
        """
        GIVEN: Trip mit morgiger Etappe, deren Wetterdaten nicht beschaffbar
               sind (nur 1 Waypoint → keine Segmente)
        WHEN:  _collect_future_stage_weather() für die Folge-Etappe(n) läuft
        THEN:  leere Liste (fail-soft), keine Exception
        """
        today = date.today()
        trip = _trip_with_unfetchable_next_stage(today)

        collected = TripReportSchedulerService()._collect_future_stage_weather(
            trip, today, tz=None,
        )

        assert collected == [], (
            f"Bei nicht beschaffbarer Folge-Etappe muss fail-soft eine leere "
            f"Liste zurückkommen, war: {collected!r}"
        )

    def test_report_falls_back_to_th_dash_when_next_stage_unavailable(self):
        """
        GIVEN: leere Folge-Etappen-Sammlung (Fetch-Fehler, s.o.)
        WHEN:  thunder_forecast daraus abgeleitet und die SMS gerendert wird
        THEN:  thunder_forecast ist None (kein "+1"-Key) und die SMS zeigt
               'TH+:-' — der Report wird trotzdem erzeugt (kein Crash)
        """
        # Aus leerer Sammlung wird thunder_forecast None (wie in der
        # Aufrufstelle: `... if future_stage_weather else None`).
        thunder_forecast = (
            TripReportSchedulerService()._build_thunder_forecast(
                [], date.today(), tz=None,
            )
        )
        assert thunder_forecast is None

        sms = SMSTripFormatter().format_sms(
            [_today_segment()],
            report_type="evening",
            thunder_forecast=thunder_forecast,
        )
        assert "TH+:-" in sms, (
            f"Fail-soft: ohne beschaffbare Folge-Etappe muss die SMS 'TH+:-' "
            f"zeigen, bekommen: {sms!r}"
        )
