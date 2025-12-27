"""Tests for Trip, Stage, and Waypoint models."""
from datetime import date, time

import pytest

from app.trip import (
    ActivityProfile,
    AggregationConfig,
    AggregationFunc,
    Stage,
    TimeWindow,
    Trip,
    Waypoint,
)


class TestTimeWindow:
    """Tests for TimeWindow."""

    def test_time_window_creation(self):
        """TimeWindow can be created with start and end times."""
        tw = TimeWindow(start=time(8, 0), end=time(10, 0))
        assert tw.start == time(8, 0)
        assert tw.end == time(10, 0)

    def test_time_window_from_string(self):
        """TimeWindow can be parsed from string."""
        tw = TimeWindow.from_string("08:00-10:30")
        assert tw.start == time(8, 0)
        assert tw.end == time(10, 30)

    def test_time_window_str(self):
        """TimeWindow string representation."""
        tw = TimeWindow(start=time(8, 0), end=time(10, 0))
        assert str(tw) == "08:00-10:00"


class TestWaypoint:
    """Tests for Waypoint."""

    def test_waypoint_creation(self):
        """Waypoint can be created with required fields."""
        wp = Waypoint(
            id="G1",
            name="Start",
            lat=47.0753,
            lon=11.1097,
            elevation_m=2302,
        )
        assert wp.id == "G1"
        assert wp.name == "Start"
        assert wp.elevation_m == 2302
        assert wp.time_window is None

    def test_waypoint_with_time_window(self):
        """Waypoint can have optional time window."""
        tw = TimeWindow(start=time(8, 0), end=time(10, 0))
        wp = Waypoint(
            id="G1",
            name="Start",
            lat=47.0753,
            lon=11.1097,
            elevation_m=2302,
            time_window=tw,
        )
        assert wp.time_window == tw

    def test_waypoint_is_frozen(self):
        """Waypoint should be immutable."""
        wp = Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=2000)
        with pytest.raises(AttributeError):
            wp.elevation_m = 3000


class TestStage:
    """Tests for Stage."""

    def _create_waypoints(self):
        """Helper to create test waypoints."""
        return [
            Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1700),
            Waypoint(id="G2", name="Gipfel", lat=47.05, lon=11.05, elevation_m=3200),
            Waypoint(id="G3", name="Ende", lat=47.0, lon=11.0, elevation_m=1700),
        ]

    def test_stage_creation(self):
        """Stage can be created with waypoints."""
        waypoints = self._create_waypoints()
        stage = Stage(
            id="T1",
            name="Tag 1",
            date=date(2025, 1, 15),
            waypoints=waypoints,
        )
        assert stage.id == "T1"
        assert len(stage.waypoints) == 3

    def test_stage_requires_waypoints(self):
        """Stage must have at least one waypoint."""
        with pytest.raises(ValueError, match="at least one waypoint"):
            Stage(id="T1", name="Empty", date=date(2025, 1, 15), waypoints=[])

    def test_stage_first_last_waypoint(self):
        """Stage provides first and last waypoint."""
        waypoints = self._create_waypoints()
        stage = Stage(id="T1", name="Tag 1", date=date(2025, 1, 15), waypoints=waypoints)
        assert stage.first_waypoint.id == "G1"
        assert stage.last_waypoint.id == "G3"

    def test_stage_highest_lowest_waypoint(self):
        """Stage provides highest and lowest waypoint."""
        waypoints = self._create_waypoints()
        stage = Stage(id="T1", name="Tag 1", date=date(2025, 1, 15), waypoints=waypoints)
        assert stage.highest_waypoint.elevation_m == 3200
        assert stage.lowest_waypoint.elevation_m == 1700


class TestAggregationConfig:
    """Tests for AggregationConfig."""

    def test_default_config(self):
        """Default config is for wintersport."""
        config = AggregationConfig()
        assert config.profile == ActivityProfile.WINTERSPORT
        assert AggregationFunc.MIN in config.temperature
        assert AggregationFunc.MAX in config.temperature
        assert config.wind == AggregationFunc.MAX

    def test_wintersport_profile(self):
        """Wintersport profile has correct defaults."""
        config = AggregationConfig.for_profile(ActivityProfile.WINTERSPORT)
        assert config.wind_chill == AggregationFunc.MIN
        assert config.avalanche_level == AggregationFunc.MAX

    def test_summer_trekking_profile(self):
        """Summer trekking profile differs from wintersport."""
        config = AggregationConfig.for_profile(ActivityProfile.SUMMER_TREKKING)
        # Summer focuses on heat, not cold
        assert AggregationFunc.MAX in config.temperature


class TestTrip:
    """Tests for Trip."""

    def _create_trip(self):
        """Helper to create a test trip."""
        waypoints = [
            Waypoint(id="G1", name="Start", lat=47.0, lon=11.0, elevation_m=1700),
            Waypoint(id="G2", name="Gipfel", lat=47.05, lon=11.05, elevation_m=3200),
            Waypoint(id="G3", name="Ende", lat=47.0, lon=11.0, elevation_m=1700),
        ]
        stage = Stage(
            id="T1",
            name="Skitour",
            date=date(2025, 1, 15),
            waypoints=waypoints,
        )
        return Trip(
            id="stubai-2025",
            name="Stubaier Skitour",
            stages=[stage],
            avalanche_regions=["AT-7"],
        )

    def test_trip_creation(self):
        """Trip can be created with stages."""
        trip = self._create_trip()
        assert trip.id == "stubai-2025"
        assert len(trip.stages) == 1
        assert len(trip.all_waypoints) == 3

    def test_trip_requires_stages(self):
        """Trip must have at least one stage."""
        with pytest.raises(ValueError, match="at least one stage"):
            Trip(id="empty", name="Empty", stages=[])

    def test_trip_dates(self):
        """Trip provides start and end dates."""
        trip = self._create_trip()
        assert trip.start_date == date(2025, 1, 15)
        assert trip.end_date == date(2025, 1, 15)

    def test_trip_highest_lowest_point(self):
        """Trip provides highest and lowest waypoints."""
        trip = self._create_trip()
        assert trip.highest_point.elevation_m == 3200
        assert trip.lowest_point.elevation_m == 1700

    def test_trip_get_stage_for_date(self):
        """Trip can find stage by date."""
        trip = self._create_trip()
        stage = trip.get_stage_for_date(date(2025, 1, 15))
        assert stage is not None
        assert stage.id == "T1"

        missing = trip.get_stage_for_date(date(2025, 1, 16))
        assert missing is None

    def test_trip_avalanche_regions(self):
        """Trip stores avalanche regions."""
        trip = self._create_trip()
        assert "AT-7" in trip.avalanche_regions
