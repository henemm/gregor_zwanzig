"""
JSON loaders for Trip and User configurations.

Provides functions to load Trip and User objects from JSON files
with validation and error handling.
"""
from __future__ import annotations

import json
from datetime import date, time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.trip import (
    ActivityProfile,
    AggregationConfig,
    AggregationFunc,
    Stage,
    TimeWindow,
    Trip,
    Waypoint,
)
from app.user import (
    LocationSubscription,
    SavedLocation,
    Schedule,
    TriggerTiming,
    TripSubscription,
    User,
    UserPreferences,
)


class LoaderError(Exception):
    """Error loading configuration."""
    pass


def load_trip(path: Union[str, Path]) -> Trip:
    """
    Load a Trip from a JSON file.

    Args:
        path: Path to the JSON file

    Returns:
        Trip object

    Raises:
        LoaderError: If the file cannot be loaded or is invalid
    """
    path = Path(path)
    if not path.exists():
        raise LoaderError(f"Trip file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise LoaderError(f"Invalid JSON in {path}: {e}")

    return _parse_trip(data.get("trip", data))


def load_trip_from_dict(data: Dict[str, Any]) -> Trip:
    """Load a Trip from a dictionary."""
    return _parse_trip(data.get("trip", data))


def _parse_trip(data: Dict[str, Any]) -> Trip:
    """Parse trip data from dictionary."""
    stages = []
    for stage_data in data.get("stages", []):
        waypoints = []
        for wp_data in stage_data.get("waypoints", []):
            time_window = None
            if "time_window" in wp_data:
                time_window = TimeWindow.from_string(wp_data["time_window"])

            waypoint = Waypoint(
                id=wp_data["id"],
                name=wp_data["name"],
                lat=wp_data["lat"],
                lon=wp_data["lon"],
                elevation_m=wp_data["elevation_m"],
                time_window=time_window,
            )
            waypoints.append(waypoint)

        stage = Stage(
            id=stage_data["id"],
            name=stage_data["name"],
            date=date.fromisoformat(stage_data["date"]),
            waypoints=waypoints,
        )
        stages.append(stage)

    # Parse aggregation config if present
    aggregation = AggregationConfig()
    if "aggregation" in data:
        agg_data = data["aggregation"]
        profile = ActivityProfile(agg_data.get("profile", "wintersport"))
        aggregation = AggregationConfig.for_profile(profile)

        # Apply overrides
        if "overrides" in agg_data:
            overrides = agg_data["overrides"]
            for key, value in overrides.items():
                if hasattr(aggregation, key):
                    if isinstance(value, list):
                        setattr(aggregation, key, [AggregationFunc(v) for v in value])
                    else:
                        setattr(aggregation, key, AggregationFunc(value))

    return Trip(
        id=data["id"],
        name=data["name"],
        stages=stages,
        avalanche_regions=data.get("avalanche_regions", []),
        aggregation=aggregation,
    )


def load_user(path: Union[str, Path]) -> User:
    """
    Load a User from a JSON file.

    Args:
        path: Path to the JSON file

    Returns:
        User object

    Raises:
        LoaderError: If the file cannot be loaded or is invalid
    """
    path = Path(path)
    if not path.exists():
        raise LoaderError(f"User file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise LoaderError(f"Invalid JSON in {path}: {e}")

    return _parse_user(data)


def load_user_from_dict(data: Dict[str, Any]) -> User:
    """Load a User from a dictionary."""
    return _parse_user(data)


def _parse_user(data: Dict[str, Any]) -> User:
    """Parse user data from dictionary."""
    user_data = data.get("user", data)

    # Parse preferences
    prefs_data = user_data.get("preferences", {})
    preferences = UserPreferences(
        units=prefs_data.get("units", "metric"),
        language=prefs_data.get("language", "de"),
        wind_chill_warning=prefs_data.get("wind_chill_warning", -20),
        avalanche_level_warning=prefs_data.get("avalanche_level_warning", 3),
        wind_warning=prefs_data.get("wind_warning", 50),
        gust_warning=prefs_data.get("gust_warning", 70),
        include_debug=prefs_data.get("include_debug", False),
        compact_format=prefs_data.get("compact_format", False),
    )

    # Parse saved locations
    locations: Dict[str, SavedLocation] = {}
    for loc_id, loc_data in data.get("locations", {}).items():
        locations[loc_id] = SavedLocation(
            id=loc_id,
            name=loc_data["name"],
            lat=loc_data["lat"],
            lon=loc_data["lon"],
            elevation_m=loc_data["elevation_m"],
            region=loc_data.get("region"),
        )

    # Parse subscriptions
    location_subs: List[LocationSubscription] = []
    trip_subs: List[TripSubscription] = []

    for sub_data in data.get("subscriptions", []):
        sub_type = sub_data.get("type", "location")

        if sub_type == "location":
            location_subs.append(LocationSubscription(
                id=sub_data.get("id", sub_data.get("name", "")),
                name=sub_data.get("name", ""),
                location_ref=sub_data["location_ref"],
                schedule=Schedule(sub_data.get("schedule", "daily_evening")),
                report_type=sub_data.get("report_type", "evening"),
                enabled=sub_data.get("enabled", True),
            ))
        elif sub_type == "trip":
            trip_subs.append(TripSubscription(
                id=sub_data.get("id", sub_data.get("name", "")),
                name=sub_data.get("name", ""),
                trip_file=sub_data["trip_file"],
                trigger=TriggerTiming(sub_data.get("trigger", "2_days_before")),
                enabled=sub_data.get("enabled", True),
            ))

    return User(
        id=user_data["id"],
        email=user_data["email"],
        preferences=preferences,
        locations=locations,
        location_subscriptions=location_subs,
        trip_subscriptions=trip_subs,
    )
