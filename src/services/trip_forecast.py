"""
Trip forecast service for multi-waypoint weather data.

Fetches weather forecasts for all waypoints in a trip and
provides aggregated summaries.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional

from app.config import Location
from app.debug import DebugBuffer
from app.models import NormalizedTimeseries
from services.aggregation import (
    AggregatedSummary,
    AggregationService,
    WaypointForecast,
)
from services.trip_segments import (
    _interpolate_missing_times,
    _known_time_for_index,
)

if TYPE_CHECKING:
    from app.trip import Stage, Trip, Waypoint
    from providers.base import WeatherProvider


class TripForecastService:
    """
    Service for fetching and aggregating forecasts for a trip.

    Fetches weather data for each waypoint in a trip and provides
    both per-waypoint details and aggregated summaries.

    Example:
        >>> from providers.base import get_provider
        >>> provider = get_provider("geosphere")
        >>> service = TripForecastService(provider)
        >>> result = service.get_trip_forecast(trip)
        >>> print(f"Coldest: {result.summary.temp_min.value}°C")
    """

    def __init__(
        self,
        provider: "WeatherProvider",
        debug: Optional[DebugBuffer] = None,
    ) -> None:
        """
        Initialize with a weather provider.

        Args:
            provider: Weather data provider
            debug: Optional debug buffer for logging
        """
        self._provider = provider
        self._debug = debug if debug is not None else DebugBuffer()

    @property
    def provider_name(self) -> str:
        """Name of the underlying weather provider."""
        return self._provider.name

    def get_trip_forecast(self, trip: "Trip") -> "TripForecastResult":
        """
        Fetch forecasts for all waypoints in a trip.

        Args:
            trip: Trip with stages and waypoints

        Returns:
            TripForecastResult with per-waypoint data and summary
        """
        self._debug.add(f"trip: {trip.name}")
        self._debug.add(f"trip.stages: {len(trip.stages)}")
        self._debug.add(f"trip.waypoints: {len(trip.all_waypoints)}")
        self._debug.add(f"trip.dates: {trip.start_date} - {trip.end_date}")

        waypoint_forecasts: List[WaypointForecast] = []

        for stage in trip.stages:
            self._debug.add(f"stage: {stage.id} {stage.name} ({stage.date})")

            for waypoint in stage.waypoints:
                forecast = self._fetch_waypoint_forecast(waypoint, stage)
                waypoint_forecasts.append(
                    WaypointForecast(waypoint=waypoint, timeseries=forecast)
                )

        # Aggregate results
        aggregation_service = AggregationService(trip.aggregation)
        summary = aggregation_service.aggregate(waypoint_forecasts)

        self._debug.add(f"summary.temp_min: {summary.temp_min.value}")
        self._debug.add(f"summary.temp_max: {summary.temp_max.value}")
        self._debug.add(f"summary.wind: {summary.wind.value}")

        return TripForecastResult(
            trip=trip,
            waypoint_forecasts=waypoint_forecasts,
            summary=summary,
        )

    def get_stage_forecast(self, stage: "Stage") -> "StageForecastResult":
        """
        Fetch forecasts for all waypoints in a single stage.

        Args:
            stage: Stage with waypoints

        Returns:
            StageForecastResult with per-waypoint data
        """
        self._debug.add(f"stage: {stage.id} {stage.name}")

        waypoint_forecasts: List[WaypointForecast] = []

        for waypoint in stage.waypoints:
            forecast = self._fetch_waypoint_forecast(waypoint, stage)
            waypoint_forecasts.append(
                WaypointForecast(waypoint=waypoint, timeseries=forecast)
            )

        return StageForecastResult(
            stage=stage,
            waypoint_forecasts=waypoint_forecasts,
        )

    def _fetch_waypoint_forecast(
        self,
        waypoint: "Waypoint",
        stage: "Stage",
    ) -> NormalizedTimeseries:
        """
        Fetch forecast for a single waypoint.

        Issue #1005: Uses the same SSoT time chain as convert_trip_to_segments
        (arrival_override > stage.start_time > arrival_calculated > default)
        instead of the obsolete waypoint.time_window.
        """
        location = Location(
            latitude=waypoint.lat,
            longitude=waypoint.lon,
            name=waypoint.name,
            elevation_m=waypoint.elevation_m,
        )

        start, end = self._waypoint_time_window(waypoint, stage)

        self._debug.add(
            f"  waypoint: {waypoint.id} {waypoint.name} "
            f"({waypoint.elevation_m}m) {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
        )

        return self._provider.fetch_forecast(location, start=start, end=end)

    def _waypoint_time_window(
        self,
        waypoint: "Waypoint",
        stage: "Stage",
    ) -> tuple[datetime, datetime]:
        """Determine the forecast query window for a waypoint using the #1004 SSoT chain."""
        default_start = stage.start_time if stage.start_time else time(8, 0)

        # Compute effective arrival time for every waypoint in the stage.
        known_times = [
            _known_time_for_index(stage.waypoints, idx, stage, default_start)
            for idx in range(len(stage.waypoints))
        ]
        wp_times = _interpolate_missing_times(known_times)

        try:
            idx = stage.waypoints.index(waypoint)
        except ValueError:
            idx = 0

        wp_time = wp_times[idx]
        if wp_time is None:
            # No time information available: fall back to entire day.
            start = datetime.combine(stage.date, time(0, 0), tzinfo=timezone.utc)
            end = datetime.combine(stage.date, time(23, 59), tzinfo=timezone.utc)
            return start, end

        start = datetime.combine(stage.date, wp_time, tzinfo=timezone.utc)

        # End time: next waypoint's arrival time, or +2h for the last waypoint.
        # Issue #1090: compute via full datetime arithmetic (no .time()-truncate)
        # so a midnight rollover is preserved, analog to trip_segments.py.
        if idx + 1 < len(wp_times) and wp_times[idx + 1] is not None:
            end = datetime.combine(stage.date, wp_times[idx + 1], tzinfo=timezone.utc)
        else:
            end = start + timedelta(hours=2)

        # Safety net: never emit an inverted/zero-length window (e.g. a
        # next-waypoint time that already rolled over midnight itself).
        if end <= start:
            end = start + timedelta(hours=2)

        return start, end


class TripForecastResult:
    """
    Result of a trip forecast request.

    Contains per-waypoint forecasts and an aggregated summary.
    """

    def __init__(
        self,
        trip: "Trip",
        waypoint_forecasts: List[WaypointForecast],
        summary: AggregatedSummary,
    ) -> None:
        self.trip = trip
        self.waypoint_forecasts = waypoint_forecasts
        self.summary = summary

    def get_forecast_for_waypoint(self, waypoint_id: str) -> Optional[WaypointForecast]:
        """Get forecast for a specific waypoint by ID."""
        for wf in self.waypoint_forecasts:
            if wf.waypoint.id == waypoint_id:
                return wf
        return None

    def get_forecasts_for_stage(self, stage_id: str) -> List[WaypointForecast]:
        """Get all forecasts for waypoints in a stage."""
        stage = next((s for s in self.trip.stages if s.id == stage_id), None)
        if not stage:
            return []

        waypoint_ids = {wp.id for wp in stage.waypoints}
        return [wf for wf in self.waypoint_forecasts if wf.waypoint.id in waypoint_ids]


class StageForecastResult:
    """
    Result of a stage forecast request.

    Contains per-waypoint forecasts for a single stage.
    """

    def __init__(
        self,
        stage: "Stage",
        waypoint_forecasts: List[WaypointForecast],
    ) -> None:
        self.stage = stage
        self.waypoint_forecasts = waypoint_forecasts

    def get_forecast_for_waypoint(self, waypoint_id: str) -> Optional[WaypointForecast]:
        """Get forecast for a specific waypoint by ID."""
        for wf in self.waypoint_forecasts:
            if wf.waypoint.id == waypoint_id:
                return wf
        return None
