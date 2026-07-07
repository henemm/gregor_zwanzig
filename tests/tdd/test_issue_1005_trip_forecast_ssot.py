"""
TDD RED — Issue #1005: Legacy-CLI TripForecast liest waypoint.time_window (out of scope in #1004).

Spec: docs/specs/modules/issue_1004_startzeit_ssot.md → Known Limitations

Der Legacy-CLI-Pfad (src/app/cli.py --trip) ist der einzige Verwender von
TripForecastService. Dieser Service muss auf dieselbe SSoT-Kette umgestellt
werden wie die Produkt-Pfade in src/services/trip_segments.py:

  arrival_override > stage.start_time (nur erster WP) > arrival_calculated > Default 08:00

 waypoint.time_window darf NICHT mehr massgeblich sein.

KEINE Mocks: wir verwenden eine echte Test-Subclass eines WeatherProvider,
die den tatsächlich übergebenen start/end-Zeitpunkt aufzeichnet.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import List, Optional, Tuple

from app.config import Location
from app.models import ForecastMeta, NormalizedTimeseries, Provider
from app.trip import Stage, Trip, Waypoint, TimeWindow
from services.trip_forecast import TripForecastService


class RecordingProvider:
    """Echter Objekt-Stub (kein unittest.mock): zeichnet fetch_forecast-Argumente auf."""

    name = "recording"

    def __init__(self) -> None:
        self.calls: List[Tuple[Location, Optional[datetime], Optional[datetime]]] = []

    def fetch_forecast(
        self,
        location: Location,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        enrich_ensemble: bool = True,
    ) -> NormalizedTimeseries:
        self.calls.append((location, start, end))
        return NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.GEOSPHERE, model="test", grid_res_km=1.0),
            data=[],
        )


def _trip_with_stage(
    stage_start_time: Optional[time] = None,
    waypoint_time_window: Optional[TimeWindow] = None,
    arrival_calculated: Optional[str] = None,
    arrival_override: Optional[str] = None,
) -> Trip:
    """Baut einen minimalen Trip mit einer Stage und zwei Waypoints."""
    wp1 = Waypoint(
        id="G1",
        name="Start",
        lat=47.0,
        lon=11.0,
        elevation_m=1000,
        time_window=waypoint_time_window,
        arrival_calculated=arrival_calculated,
        arrival_override=arrival_override,
    )
    wp2 = Waypoint(
        id="G2",
        name="Ziel",
        lat=47.1,
        lon=11.1,
        elevation_m=1200,
    )
    stage = Stage(
        id="T1",
        name="Etappe 1",
        date=date(2026, 7, 7),
        waypoints=[wp1, wp2],
        start_time=stage_start_time,
    )
    return Trip(
        id="trip-1005",
        name="Testtrip",
        stages=[stage],
        activity="hike",
    )


class TestTripForecastUsesSSoTChain:
    """Issue #1005: TripForecastService verwendet SSoT-Kette statt time_window."""

    def test_stage_start_time_overrides_time_window(self):
        """GIVEN: Stage start_time=14:00, waypoint.time_window=07:00-09:00
        WHEN: TripForecastService fragt Wetter für ersten Wegpunkt ab
        THEN: Startzeit ist 14:00 (nicht 07:00 aus time_window).
        """
        provider = RecordingProvider()
        service = TripForecastService(provider)
        trip = _trip_with_stage(
            stage_start_time=time(14, 0),
            waypoint_time_window=TimeWindow(time(7, 0), time(9, 0)),
        )

        service.get_trip_forecast(trip)

        assert len(provider.calls) == 2, f"expected 2 calls, got {len(provider.calls)}"
        start = provider.calls[0][1]
        assert start is not None
        assert start.hour == 14 and start.minute == 0, (
            f"RED: expected start=14:00 from stage.start_time, got {start.strftime('%H:%M')}"
        )

    def test_arrival_override_takes_precedence(self):
        """GIVEN: arrival_override=16:30, stage.start_time=14:00
        WHEN: TripForecastService fragt Wetter ab
        THEN: Startzeit ist 16:30 (oberste Priorität).
        """
        provider = RecordingProvider()
        service = TripForecastService(provider)
        trip = _trip_with_stage(
            stage_start_time=time(14, 0),
            arrival_override="16:30",
        )

        service.get_trip_forecast(trip)

        start = provider.calls[0][1]
        assert start is not None
        assert start.hour == 16 and start.minute == 30, (
            f"RED: expected start=16:30 from arrival_override, got {start.strftime('%H:%M')}"
        )

    def test_arrival_calculated_used_when_no_stage_start_time(self):
        """GIVEN: kein stage.start_time, aber arrival_calculated=09:15
        WHEN: TripForecastService fragt Wetter ab
        THEN: Startzeit ist 09:15.
        """
        provider = RecordingProvider()
        service = TripForecastService(provider)
        trip = _trip_with_stage(arrival_calculated="09:15")

        service.get_trip_forecast(trip)

        start = provider.calls[0][1]
        assert start is not None
        assert start.hour == 9 and start.minute == 15, (
            f"RED: expected start=09:15 from arrival_calculated, got {start.strftime('%H:%M')}"
        )

    def test_default_start_time_when_nothing_set(self):
        """GIVEN: weder stage.start_time noch arrival_calculated noch override
        WHEN: TripForecastService fragt Wetter ab
        THEN: Startzeit defaultet auf 08:00.
        """
        provider = RecordingProvider()
        service = TripForecastService(provider)
        trip = _trip_with_stage()

        service.get_trip_forecast(trip)

        start = provider.calls[0][1]
        assert start is not None
        assert start.hour == 8 and start.minute == 0, (
            f"RED: expected default start=08:00, got {start.strftime('%H:%M')}"
        )
