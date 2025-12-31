"""
JSON loaders and savers for Trip and User configurations.

Provides functions to load and save Trip and User objects from/to JSON files
with validation and error handling.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Union

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
    CompareSubscription,
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


# =============================================================================
# Data Directory Helpers
# =============================================================================

def get_data_dir(user_id: str = "default") -> Path:
    """Get the data directory for a user."""
    return Path("data/users") / user_id


def get_locations_dir(user_id: str = "default") -> Path:
    """Get the locations directory for a user."""
    return get_data_dir(user_id) / "locations"


def get_trips_dir(user_id: str = "default") -> Path:
    """Get the trips directory for a user."""
    return get_data_dir(user_id) / "trips"


# =============================================================================
# Location CRUD
# =============================================================================

def load_all_locations(user_id: str = "default") -> List[SavedLocation]:
    """
    Load all locations for a user.

    Args:
        user_id: User identifier (default: "default")

    Returns:
        List of SavedLocation objects
    """
    locations_dir = get_locations_dir(user_id)
    if not locations_dir.exists():
        return []

    locations = []
    for path in locations_dir.glob("*.json"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            locations.append(SavedLocation(
                id=data.get("id", path.stem),
                name=data["name"],
                lat=data["lat"],
                lon=data["lon"],
                elevation_m=data["elevation_m"],
                region=data.get("region"),
                bergfex_slug=data.get("bergfex_slug"),
            ))
        except (json.JSONDecodeError, KeyError):
            continue
    return locations


def save_location(location: SavedLocation, user_id: str = "default") -> Path:
    """
    Save a location to JSON file.

    Args:
        location: SavedLocation object to save
        user_id: User identifier (default: "default")

    Returns:
        Path to the saved file
    """
    locations_dir = get_locations_dir(user_id)
    locations_dir.mkdir(parents=True, exist_ok=True)

    path = locations_dir / f"{location.id}.json"
    data = {
        "id": location.id,
        "name": location.name,
        "lat": location.lat,
        "lon": location.lon,
        "elevation_m": location.elevation_m,
        "region": location.region,
        "bergfex_slug": location.bergfex_slug,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return path


def delete_location(location_id: str, user_id: str = "default") -> None:
    """
    Delete a location file.

    Args:
        location_id: ID of the location to delete
        user_id: User identifier (default: "default")
    """
    path = get_locations_dir(user_id) / f"{location_id}.json"
    if path.exists():
        path.unlink()


# =============================================================================
# Trip CRUD
# =============================================================================

def load_all_trips(user_id: str = "default") -> List[Trip]:
    """
    Load all trips for a user.

    Args:
        user_id: User identifier (default: "default")

    Returns:
        List of Trip objects
    """
    trips_dir = get_trips_dir(user_id)
    if not trips_dir.exists():
        return []

    trips = []
    for path in trips_dir.glob("*.json"):
        try:
            trips.append(load_trip(path))
        except LoaderError:
            continue
    return trips


def _trip_to_dict(trip: Trip) -> Dict[str, Any]:
    """Convert a Trip object to a dictionary for JSON serialization."""
    stages_data = []
    for stage in trip.stages:
        waypoints_data = []
        for wp in stage.waypoints:
            wp_dict: Dict[str, Any] = {
                "id": wp.id,
                "name": wp.name,
                "lat": wp.lat,
                "lon": wp.lon,
                "elevation_m": wp.elevation_m,
            }
            if wp.time_window:
                wp_dict["time_window"] = str(wp.time_window)
            waypoints_data.append(wp_dict)

        stages_data.append({
            "id": stage.id,
            "name": stage.name,
            "date": stage.date.isoformat(),
            "waypoints": waypoints_data,
        })

    return {
        "id": trip.id,
        "name": trip.name,
        "stages": stages_data,
        "avalanche_regions": trip.avalanche_regions,
        "aggregation": {
            "profile": trip.aggregation.profile.value,
        },
    }


def save_trip(trip: Trip, user_id: str = "default") -> Path:
    """
    Save a trip to JSON file.

    Args:
        trip: Trip object to save
        user_id: User identifier (default: "default")

    Returns:
        Path to the saved file
    """
    trips_dir = get_trips_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)

    path = trips_dir / f"{trip.id}.json"
    data = _trip_to_dict(trip)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return path


def delete_trip(trip_id: str, user_id: str = "default") -> None:
    """
    Delete a trip file.

    Args:
        trip_id: ID of the trip to delete
        user_id: User identifier (default: "default")
    """
    path = get_trips_dir(user_id) / f"{trip_id}.json"
    if path.exists():
        path.unlink()


# =============================================================================
# Compare Subscription CRUD
# =============================================================================

def get_compare_subscriptions_file(user_id: str = "default") -> Path:
    """Get the compare subscriptions file path for a user."""
    return get_data_dir(user_id) / "compare_subscriptions.json"


def load_compare_subscriptions(user_id: str = "default") -> List[CompareSubscription]:
    """
    Load all compare subscriptions for a user.

    Args:
        user_id: User identifier (default: "default")

    Returns:
        List of CompareSubscription objects
    """
    path = get_compare_subscriptions_file(user_id)
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return []

    subscriptions = []
    for sub_data in data.get("subscriptions", []):
        # Handle legacy "weekly_friday" -> "weekly" with weekday=4
        schedule_str = sub_data.get("schedule", "weekly")
        if schedule_str == "weekly_friday":
            schedule_str = "weekly"
            weekday = 4
        else:
            weekday = sub_data.get("weekday", 4)

        subscriptions.append(CompareSubscription(
            id=sub_data["id"],
            name=sub_data["name"],
            enabled=sub_data.get("enabled", True),
            locations=sub_data.get("locations", []),
            forecast_hours=sub_data.get("forecast_hours", 48),
            time_window_start=sub_data.get("time_window_start", 9),
            time_window_end=sub_data.get("time_window_end", 16),
            schedule=Schedule(schedule_str),
            weekday=weekday,
            include_hourly=sub_data.get("include_hourly", True),
            top_n=sub_data.get("top_n", 3),
        ))
    return subscriptions


def save_compare_subscriptions(
    subscriptions: List[CompareSubscription],
    user_id: str = "default"
) -> Path:
    """
    Save all compare subscriptions for a user.

    Args:
        subscriptions: List of CompareSubscription objects
        user_id: User identifier (default: "default")

    Returns:
        Path to the saved file
    """
    path = get_compare_subscriptions_file(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "subscriptions": [
            {
                "id": sub.id,
                "name": sub.name,
                "enabled": sub.enabled,
                "locations": sub.locations,
                "forecast_hours": sub.forecast_hours,
                "time_window_start": sub.time_window_start,
                "time_window_end": sub.time_window_end,
                "schedule": sub.schedule.value,
                "weekday": sub.weekday,
                "include_hourly": sub.include_hourly,
                "top_n": sub.top_n,
            }
            for sub in subscriptions
        ]
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return path


def save_compare_subscription(
    subscription: CompareSubscription,
    user_id: str = "default"
) -> Path:
    """
    Save or update a single compare subscription.

    Args:
        subscription: CompareSubscription object to save
        user_id: User identifier (default: "default")

    Returns:
        Path to the saved file
    """
    subs = load_compare_subscriptions(user_id)

    # Update existing or add new
    updated = False
    for i, sub in enumerate(subs):
        if sub.id == subscription.id:
            subs[i] = subscription
            updated = True
            break

    if not updated:
        subs.append(subscription)

    return save_compare_subscriptions(subs, user_id)


def delete_compare_subscription(sub_id: str, user_id: str = "default") -> None:
    """
    Delete a compare subscription.

    Args:
        sub_id: ID of the subscription to delete
        user_id: User identifier (default: "default")
    """
    subs = load_compare_subscriptions(user_id)
    subs = [s for s in subs if s.id != sub_id]
    save_compare_subscriptions(subs, user_id)
