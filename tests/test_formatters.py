"""Tests for report formatters."""
from datetime import date, datetime, time, timezone

import pytest

from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from app.trip import Stage, TimeWindow, Trip, Waypoint
from formatters.wintersport import WintersportFormatter
from services.aggregation import AggregatedSummary, AggregatedValue, AggregationFunc, WaypointForecast
from services.trip_forecast import TripForecastResult


class TestWintersportFormatter:
    """Tests for WintersportFormatter."""

    def _create_simple_result(self):
        """Create a simple TripForecastResult for testing."""
        # Create waypoints
        wp1 = Waypoint(
            id="G1",
            name="Start",
            lat=47.0,
            lon=11.0,
            elevation_m=1700,
            time_window=TimeWindow(start=time(8, 0), end=time(10, 0)),
        )
        wp2 = Waypoint(
            id="G2",
            name="Gipfel",
            lat=47.05,
            lon=11.05,
            elevation_m=3200,
            time_window=TimeWindow(start=time(11, 0), end=time(13, 0)),
        )

        # Create stage and trip
        stage = Stage(id="T1", name="Tag 1", date=date(2025, 1, 15), waypoints=[wp1, wp2])
        trip = Trip(
            id="test-trip",
            name="Stubaier Skitour",
            stages=[stage],
            avalanche_regions=["AT-7"],
        )

        # Create forecasts
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="AROME",
            run=datetime.now(timezone.utc),
            grid_res_km=2.5,
            interp="bilinear",
        )

        dp1 = ForecastDataPoint(
            ts=datetime.now(timezone.utc),
            t2m_c=-5.0,
            wind10m_kmh=15.0,
            gust_kmh=25.0,
            wind_chill_c=-12.0,
        )
        dp2 = ForecastDataPoint(
            ts=datetime.now(timezone.utc),
            t2m_c=-15.0,
            wind10m_kmh=45.0,
            gust_kmh=70.0,
            wind_chill_c=-28.0,
        )

        wf1 = WaypointForecast(
            waypoint=wp1,
            timeseries=NormalizedTimeseries(meta=meta, data=[dp1]),
        )
        wf2 = WaypointForecast(
            waypoint=wp2,
            timeseries=NormalizedTimeseries(meta=meta, data=[dp2]),
        )

        # Create summary
        summary = AggregatedSummary(
            temp_min=AggregatedValue(value=-15.0, source_waypoint="Gipfel", aggregation=AggregationFunc.MIN),
            temp_max=AggregatedValue(value=-5.0, source_waypoint="Start", aggregation=AggregationFunc.MAX),
            wind_chill=AggregatedValue(value=-28.0, source_waypoint="Gipfel", aggregation=AggregationFunc.MIN),
            wind=AggregatedValue(value=45.0, source_waypoint="Gipfel", aggregation=AggregationFunc.MAX),
            gust=AggregatedValue(value=70.0, source_waypoint="Gipfel", aggregation=AggregationFunc.MAX),
        )

        return TripForecastResult(
            trip=trip,
            waypoint_forecasts=[wf1, wf2],
            summary=summary,
        )

    def test_format_basic(self):
        """Formatter produces output."""
        result = self._create_simple_result()
        formatter = WintersportFormatter()

        output = formatter.format(result)

        assert output is not None
        assert len(output) > 0

    def test_format_includes_trip_name(self):
        """Output includes trip name."""
        result = self._create_simple_result()
        formatter = WintersportFormatter()

        output = formatter.format(result)

        assert "STUBAIER SKITOUR" in output

    def test_format_includes_summary(self):
        """Output includes summary section."""
        result = self._create_simple_result()
        formatter = WintersportFormatter()

        output = formatter.format(result)

        assert "ZUSAMMENFASSUNG" in output
        assert "Temperatur" in output
        assert "-15" in output  # Min temp

    def test_format_includes_waypoints(self):
        """Output includes waypoint details."""
        result = self._create_simple_result()
        formatter = WintersportFormatter()

        output = formatter.format(result)

        assert "WEGPUNKT-DETAILS" in output
        assert "Start" in output
        assert "Gipfel" in output
        assert "1700m" in output
        assert "3200m" in output

    def test_format_includes_avalanche_regions(self):
        """Output includes avalanche regions."""
        result = self._create_simple_result()
        formatter = WintersportFormatter()

        output = formatter.format(result)

        assert "LAWINENREGIONEN" in output
        assert "AT-7" in output

    def test_format_shows_warnings(self):
        """Output shows warning symbols for dangerous values."""
        result = self._create_simple_result()
        formatter = WintersportFormatter()

        output = formatter.format(result)

        # Wind chill <= -20 should have warning
        assert "⚠️" in output

    def test_format_compact(self):
        """Compact format produces short output."""
        result = self._create_simple_result()
        formatter = WintersportFormatter()

        output = formatter.format_compact(result)

        assert "Stubaier Skitour:" in output
        assert len(output) < 160  # SMS length

    def test_format_compact_includes_key_values(self):
        """Compact format includes temperature and wind."""
        result = self._create_simple_result()
        formatter = WintersportFormatter()

        output = formatter.format_compact(result)

        assert "T" in output  # Temperature
        assert "W" in output  # Wind

    def test_format_report_type(self):
        """Report type is included in header."""
        result = self._create_simple_result()
        formatter = WintersportFormatter()

        morning = formatter.format(result, report_type="morning")
        evening = formatter.format(result, report_type="evening")

        assert "Morning Report" in morning
        assert "Evening Report" in evening
