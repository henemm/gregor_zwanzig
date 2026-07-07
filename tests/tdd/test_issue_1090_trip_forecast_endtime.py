"""
TDD RED — Issue #1090: TripForecast-Endzeit nie invertiert (Regression aus #1005).

Spec: docs/specs/modules/issue_1090_trip_forecast_endtime.md (AC-1..AC-3)

Bug: TripForecastService._waypoint_time_window berechnet die Endzeit des
letzten Wegpunkts einer Etappe als
    (datetime.combine(stage.date, wp_time) + timedelta(hours=2)).time()
Das ``.time()`` verwirft einen Datumsueberlauf. Bei Ankunft >= 22:00
(z.B. 23:00 -> +2h = 01:00) entsteht ``end < start`` (invertiertes Fenster),
das unveraendert an den Provider weitergereicht wird.

KEINE Mocks: RecordingProvider ist eine echte Objekt-Subclass eines
WeatherProvider (analog test_issue_1005_trip_forecast_ssot.py), die die
tatsaechlich uebergebenen start/end-Argumente aufzeichnet.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import List, Optional, Tuple

from app.config import Location
from app.models import ForecastMeta, NormalizedTimeseries, Provider
from app.trip import Stage, Trip, Waypoint
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
    arrival_calculated: Optional[str] = None,
    arrival_override: Optional[str] = None,
    last_arrival_override: Optional[str] = None,
) -> Trip:
    """Baut einen minimalen Trip mit einer Stage und zwei Waypoints.

    ``last_arrival_override`` steuert den arrival_override des LETZTEN
    Wegpunkts (fuer AC-1: spaete Ankunft am Etappenende).
    """
    wp1 = Waypoint(
        id="G1",
        name="Start",
        lat=47.0,
        lon=11.0,
        elevation_m=1000,
        arrival_calculated=arrival_calculated,
        arrival_override=arrival_override,
    )
    wp2 = Waypoint(
        id="G2",
        name="Ziel",
        lat=47.1,
        lon=11.1,
        elevation_m=1200,
        arrival_override=last_arrival_override,
    )
    stage = Stage(
        id="T1",
        name="Etappe 1",
        date=date(2026, 7, 7),
        waypoints=[wp1, wp2],
        start_time=stage_start_time,
    )
    return Trip(
        id="trip-1090",
        name="Testtrip",
        stages=[stage],
        activity="hike",
    )


def _trip_with_single_waypoint_stage(arrival_override: str) -> Trip:
    """Etappe mit genau EINEM Wegpunkt, der zugleich erster und letzter ist."""
    wp = Waypoint(
        id="G1",
        name="Solo",
        lat=47.0,
        lon=11.0,
        elevation_m=1000,
        arrival_override=arrival_override,
    )
    stage = Stage(
        id="T1",
        name="Etappe Solo",
        date=date(2026, 7, 7),
        waypoints=[wp],
    )
    return Trip(
        id="trip-1090-solo",
        name="Testtrip Solo",
        stages=[stage],
        activity="hike",
    )


class TestTripForecastEndtimeNeverInverted:
    """Issue #1090: end > start muss fuer JEDES Wetterfenster gelten."""

    def test_last_waypoint_late_arrival_end_after_start(self):
        """AC-1: letzter Wegpunkt mit arrival_override=23:00 -> end muss ECHT
        nach start liegen (nicht 01:00 durch .time()-Truncate)."""
        provider = RecordingProvider()
        service = TripForecastService(provider)
        trip = _trip_with_stage(last_arrival_override="23:00")

        service.get_trip_forecast(trip)

        assert len(provider.calls) == 2, f"expected 2 calls, got {len(provider.calls)}"
        start = provider.calls[-1][1]
        end = provider.calls[-1][2]
        assert start is not None and end is not None
        assert start.hour == 23 and start.minute == 0, (
            f"expected start=23:00 from arrival_override, got {start.strftime('%H:%M')}"
        )
        assert end > start, (
            f"RED: invertiertes Fenster erwartet keinen Fix — "
            f"start={start.isoformat()} end={end.isoformat()} (end <= start)"
        )

    def test_no_inverted_window_across_all_start_times(self):
        """AC-2: fuer eine Reihe von Ankunftszeiten (auch spaet am Abend) muss
        end > start IMMER gelten, unabhaengig von Tageszeit."""
        candidate_times = ["08:00", "14:00", "22:30", "23:00", "23:59"]
        failures = []

        for arrival in candidate_times:
            provider = RecordingProvider()
            service = TripForecastService(provider)
            trip = _trip_with_single_waypoint_stage(arrival_override=arrival)

            service.get_trip_forecast(trip)

            assert len(provider.calls) == 1
            start = provider.calls[0][1]
            end = provider.calls[0][2]
            assert start is not None and end is not None
            if not (end > start):
                failures.append(
                    f"arrival={arrival}: start={start.isoformat()} end={end.isoformat()}"
                )

        assert not failures, (
            "RED: invertierte Fenster fuer folgende Ankunftszeiten: "
            + "; ".join(failures)
        )

    def test_start_time_priority_unchanged(self):
        """AC-3: arrival_override schlaegt stage.start_time weiterhin (keine
        Regression an der #1005-SSoT-Kette). Darf bereits jetzt gruen sein."""
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
            f"expected start=16:30 from arrival_override, got {start.strftime('%H:%M')}"
        )
