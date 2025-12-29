"""Tests for JSON loaders."""
from datetime import date, time


from app.loader import (
    load_trip_from_dict,
    load_user_from_dict,
)
from app.trip import ActivityProfile, AggregationFunc


class TestTripLoader:
    """Tests for trip loading."""

    def test_load_simple_trip(self):
        """Load a simple trip with one stage."""
        data = {
            "trip": {
                "id": "test-trip",
                "name": "Test Trip",
                "stages": [
                    {
                        "id": "T1",
                        "name": "Day 1",
                        "date": "2025-01-15",
                        "waypoints": [
                            {
                                "id": "G1",
                                "name": "Start",
                                "lat": 47.0,
                                "lon": 11.0,
                                "elevation_m": 2000,
                            }
                        ],
                    }
                ],
            }
        }
        trip = load_trip_from_dict(data)
        assert trip.id == "test-trip"
        assert trip.name == "Test Trip"
        assert len(trip.stages) == 1
        assert trip.stages[0].date == date(2025, 1, 15)

    def test_load_trip_with_time_windows(self):
        """Load a trip with time windows on waypoints."""
        data = {
            "trip": {
                "id": "test-trip",
                "name": "Test",
                "stages": [
                    {
                        "id": "T1",
                        "name": "Day 1",
                        "date": "2025-01-15",
                        "waypoints": [
                            {
                                "id": "G1",
                                "name": "Start",
                                "lat": 47.0,
                                "lon": 11.0,
                                "elevation_m": 2000,
                                "time_window": "08:00-10:00",
                            },
                            {
                                "id": "G2",
                                "name": "Gipfel",
                                "lat": 47.05,
                                "lon": 11.05,
                                "elevation_m": 3000,
                                "time_window": "11:00-13:00",
                            },
                        ],
                    }
                ],
            }
        }
        trip = load_trip_from_dict(data)
        wp1 = trip.stages[0].waypoints[0]
        assert wp1.time_window is not None
        assert wp1.time_window.start == time(8, 0)
        assert wp1.time_window.end == time(10, 0)

    def test_load_trip_with_avalanche_regions(self):
        """Load a trip with avalanche regions."""
        data = {
            "trip": {
                "id": "test-trip",
                "name": "Test",
                "avalanche_regions": ["AT-7", "AT-5"],
                "stages": [
                    {
                        "id": "T1",
                        "name": "Day 1",
                        "date": "2025-01-15",
                        "waypoints": [
                            {
                                "id": "G1",
                                "name": "Start",
                                "lat": 47.0,
                                "lon": 11.0,
                                "elevation_m": 2000,
                            }
                        ],
                    }
                ],
            }
        }
        trip = load_trip_from_dict(data)
        assert "AT-7" in trip.avalanche_regions
        assert "AT-5" in trip.avalanche_regions

    def test_load_trip_with_aggregation_profile(self):
        """Load a trip with custom aggregation profile."""
        data = {
            "trip": {
                "id": "test-trip",
                "name": "Test",
                "aggregation": {
                    "profile": "summer_trekking",
                },
                "stages": [
                    {
                        "id": "T1",
                        "name": "Day 1",
                        "date": "2025-01-15",
                        "waypoints": [
                            {
                                "id": "G1",
                                "name": "Start",
                                "lat": 47.0,
                                "lon": 11.0,
                                "elevation_m": 2000,
                            }
                        ],
                    }
                ],
            }
        }
        trip = load_trip_from_dict(data)
        assert trip.aggregation.profile == ActivityProfile.SUMMER_TREKKING

    def test_load_trip_with_aggregation_overrides(self):
        """Load a trip with aggregation overrides."""
        data = {
            "trip": {
                "id": "test-trip",
                "name": "Test",
                "aggregation": {
                    "profile": "wintersport",
                    "overrides": {
                        "wind": "AVG",
                    },
                },
                "stages": [
                    {
                        "id": "T1",
                        "name": "Day 1",
                        "date": "2025-01-15",
                        "waypoints": [
                            {
                                "id": "G1",
                                "name": "Start",
                                "lat": 47.0,
                                "lon": 11.0,
                                "elevation_m": 2000,
                            }
                        ],
                    }
                ],
            }
        }
        trip = load_trip_from_dict(data)
        assert trip.aggregation.wind == AggregationFunc.AVG


class TestUserLoader:
    """Tests for user loading."""

    def test_load_simple_user(self):
        """Load a simple user."""
        data = {
            "user": {
                "id": "user-001",
                "email": "test@example.com",
            }
        }
        user = load_user_from_dict(data)
        assert user.id == "user-001"
        assert user.email == "test@example.com"

    def test_load_user_with_preferences(self):
        """Load user with custom preferences."""
        data = {
            "user": {
                "id": "user-001",
                "email": "test@example.com",
                "preferences": {
                    "language": "en",
                    "units": "imperial",
                    "avalanche_level_warning": 4,
                },
            }
        }
        user = load_user_from_dict(data)
        assert user.preferences.language == "en"
        assert user.preferences.units == "imperial"
        assert user.preferences.avalanche_level_warning == 4

    def test_load_user_with_locations(self):
        """Load user with saved locations."""
        data = {
            "user": {
                "id": "user-001",
                "email": "test@example.com",
            },
            "locations": {
                "stubai": {
                    "name": "Stubaier Gletscher",
                    "lat": 47.0753,
                    "lon": 11.1097,
                    "elevation_m": 2302,
                    "region": "AT-7",
                }
            },
        }
        user = load_user_from_dict(data)
        assert "stubai" in user.locations
        loc = user.locations["stubai"]
        assert loc.name == "Stubaier Gletscher"
        assert loc.region == "AT-7"

    def test_load_user_with_subscriptions(self):
        """Load user with subscriptions."""
        data = {
            "user": {
                "id": "user-001",
                "email": "test@example.com",
            },
            "locations": {
                "stubai": {
                    "name": "Stubai",
                    "lat": 47.0,
                    "lon": 11.0,
                    "elevation_m": 2000,
                }
            },
            "subscriptions": [
                {
                    "type": "location",
                    "name": "Stubai Evening",
                    "location_ref": "stubai",
                    "schedule": "daily_evening",
                },
                {
                    "type": "trip",
                    "name": "Weekend Tour",
                    "trip_file": "trips/weekend.json",
                    "trigger": "2_days_before",
                },
            ],
        }
        user = load_user_from_dict(data)
        assert len(user.location_subscriptions) == 1
        assert len(user.trip_subscriptions) == 1
        assert user.location_subscriptions[0].location_ref == "stubai"
        assert user.trip_subscriptions[0].trip_file == "trips/weekend.json"
