"""Tests for TripForecastService."""
from datetime import date, datetime, time, timezone
from unittest.mock import MagicMock

import pytest

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from app.trip import AggregationConfig, Stage, TimeWindow, Trip, Waypoint
from services.trip_forecast import (
    StageForecastResult,
    TripForecastResult,
    TripForecastService,
)


class TestTripForecastService:
    """Tests for TripForecastService."""

    def _create_mock_provider(self, temp: float = -5.0, wind: float = 20.0):
        """Create a mock weather provider."""
        provider = MagicMock()
        provider.name = "mock"

        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="TEST",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="bilinear",
        )
        dp = ForecastDataPoint(
            ts=datetime.now(timezone.utc),
            t2m_c=temp,
            wind10m_kmh=wind,
            gust_kmh=wind * 1.5,
        )
        provider.fetch_forecast.return_value = NormalizedTimeseries(
            meta=meta, data=[dp]
        )
        return provider

    def _create_simple_trip(self):
        """Create a simple trip with one stage and two waypoints."""
        waypoints = [
            Waypoint(
                id="G1",
                name="Start",
                lat=47.0,
                lon=11.0,
                elevation_m=1700,
                time_window=TimeWindow(start=time(8, 0), end=time(10, 0)),
            ),
            Waypoint(
                id="G2",
                name="Gipfel",
                lat=47.05,
                lon=11.05,
                elevation_m=3200,
                time_window=TimeWindow(start=time(11, 0), end=time(13, 0)),
            ),
        ]
        stage = Stage(
            id="T1",
            name="Tag 1",
            date=date(2025, 1, 15),
            waypoints=waypoints,
        )
        return Trip(
            id="test-trip",
            name="Test Trip",
            stages=[stage],
            avalanche_regions=["AT-7"],
        )

    def test_service_init(self):
        """TripForecastService can be initialized."""
        provider = self._create_mock_provider()
        service = TripForecastService(provider)
        assert service.provider_name == "mock"

    def test_get_trip_forecast(self):
        """get_trip_forecast fetches data for all waypoints."""
        provider = self._create_mock_provider()
        service = TripForecastService(provider)
        trip = self._create_simple_trip()

        result = service.get_trip_forecast(trip)

        assert isinstance(result, TripForecastResult)
        assert result.trip == trip
        assert len(result.waypoint_forecasts) == 2
        # Provider should be called once per waypoint
        assert provider.fetch_forecast.call_count == 2

    def test_trip_forecast_has_summary(self):
        """Trip forecast includes aggregated summary."""
        provider = self._create_mock_provider(temp=-10.0, wind=40.0)
        service = TripForecastService(provider)
        trip = self._create_simple_trip()

        result = service.get_trip_forecast(trip)

        assert result.summary is not None
        assert result.summary.temp_min.value == -10.0
        assert result.summary.wind.value == 40.0

    def test_get_forecast_for_waypoint(self):
        """Can retrieve forecast for specific waypoint."""
        provider = self._create_mock_provider()
        service = TripForecastService(provider)
        trip = self._create_simple_trip()

        result = service.get_trip_forecast(trip)
        wf = result.get_forecast_for_waypoint("G1")

        assert wf is not None
        assert wf.waypoint.name == "Start"

    def test_get_forecast_for_unknown_waypoint(self):
        """Returns None for unknown waypoint."""
        provider = self._create_mock_provider()
        service = TripForecastService(provider)
        trip = self._create_simple_trip()

        result = service.get_trip_forecast(trip)
        wf = result.get_forecast_for_waypoint("UNKNOWN")

        assert wf is None

    def test_get_forecasts_for_stage(self):
        """Can retrieve forecasts for all waypoints in a stage."""
        provider = self._create_mock_provider()
        service = TripForecastService(provider)
        trip = self._create_simple_trip()

        result = service.get_trip_forecast(trip)
        forecasts = result.get_forecasts_for_stage("T1")

        assert len(forecasts) == 2

    def test_get_stage_forecast(self):
        """get_stage_forecast fetches data for single stage."""
        provider = self._create_mock_provider()
        service = TripForecastService(provider)
        trip = self._create_simple_trip()

        result = service.get_stage_forecast(trip.stages[0])

        assert isinstance(result, StageForecastResult)
        assert result.stage == trip.stages[0]
        assert len(result.waypoint_forecasts) == 2

    def test_waypoint_without_time_window(self):
        """Waypoint without time window uses full day."""
        waypoint = Waypoint(
            id="G1",
            name="Test",
            lat=47.0,
            lon=11.0,
            elevation_m=2000,
            # No time_window
        )
        stage = Stage(
            id="T1",
            name="Test",
            date=date(2025, 1, 15),
            waypoints=[waypoint],
        )
        trip = Trip(id="test", name="Test", stages=[stage])

        provider = self._create_mock_provider()
        service = TripForecastService(provider)

        result = service.get_trip_forecast(trip)

        assert len(result.waypoint_forecasts) == 1
        provider.fetch_forecast.assert_called_once()


class TestTripForecastResult:
    """Tests for TripForecastResult."""

    def test_get_forecasts_for_unknown_stage(self):
        """Returns empty list for unknown stage."""
        waypoint = Waypoint(id="G1", name="Test", lat=47.0, lon=11.0, elevation_m=2000)
        stage = Stage(id="T1", name="Test", date=date(2025, 1, 15), waypoints=[waypoint])
        trip = Trip(id="test", name="Test", stages=[stage])

        from services.aggregation import AggregatedSummary

        result = TripForecastResult(
            trip=trip,
            waypoint_forecasts=[],
            summary=AggregatedSummary(),
        )

        forecasts = result.get_forecasts_for_stage("UNKNOWN")
        assert forecasts == []
