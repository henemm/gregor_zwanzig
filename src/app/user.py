"""
User and Subscription data models.

Defines user profiles with:
- Saved locations
- Subscription preferences
- Notification settings
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SubscriptionType(str, Enum):
    """Types of subscriptions."""
    LOCATION = "location"  # Regular reports for a location
    TRIP = "trip"          # Reports before a specific trip


class Schedule(str, Enum):
    """Subscription schedules."""
    DAILY_MORNING = "daily_morning"
    DAILY_EVENING = "daily_evening"
    WEEKLY_FRIDAY = "weekly_friday"
    BEFORE_TRIP = "before_trip"  # X days before trip


class TriggerTiming(str, Enum):
    """Trigger timing for trip subscriptions."""
    ONE_DAY_BEFORE = "1_day_before"
    TWO_DAYS_BEFORE = "2_days_before"
    THREE_DAYS_BEFORE = "3_days_before"
    WEEK_BEFORE = "7_days_before"


@dataclass(frozen=True)
class SavedLocation:
    """
    A saved location in the user's profile.

    Represents a frequently used location with coordinates,
    elevation, and optional avalanche region.
    """
    id: str
    name: str
    lat: float
    lon: float
    elevation_m: int
    region: Optional[str] = None  # Avalanche region code (e.g., "AT-7")

    def __str__(self) -> str:
        region_str = f" [{self.region}]" if self.region else ""
        return f"{self.name} ({self.lat:.4f}N, {self.lon:.4f}E, {self.elevation_m}m){region_str}"


@dataclass
class UserPreferences:
    """
    User preferences for reports and notifications.
    """
    units: str = "metric"  # "metric" or "imperial"
    language: str = "de"   # "de", "en", etc.

    # Warning thresholds
    wind_chill_warning: int = -20      # Warn below this temperature
    avalanche_level_warning: int = 3   # Warn at this level or higher
    wind_warning: int = 50             # Warn above this wind speed (km/h)
    gust_warning: int = 70             # Warn above this gust speed (km/h)

    # Report preferences
    include_debug: bool = False
    compact_format: bool = False  # SMS-style compact output


@dataclass
class LocationSubscription:
    """
    Subscription for regular reports about a location.
    """
    id: str
    name: str
    location_ref: str  # Reference to saved location ID
    schedule: Schedule
    report_type: str = "evening"  # "morning", "evening", "alert"
    enabled: bool = True


@dataclass
class TripSubscription:
    """
    Subscription for reports before a specific trip.
    """
    id: str
    name: str
    trip_file: str  # Path to trip JSON file
    trigger: TriggerTiming
    enabled: bool = True


@dataclass
class User:
    """
    User profile with locations and subscriptions.

    Example:
        >>> user = User(
        ...     id="user-001",
        ...     email="user@example.com",
        ...     locations={"stubai": SavedLocation(...)},
        ...     subscriptions=[LocationSubscription(...)],
        ... )
    """
    id: str
    email: str
    preferences: UserPreferences = field(default_factory=UserPreferences)
    locations: Dict[str, SavedLocation] = field(default_factory=dict)
    location_subscriptions: List[LocationSubscription] = field(default_factory=list)
    trip_subscriptions: List[TripSubscription] = field(default_factory=list)

    def get_location(self, ref: str) -> Optional[SavedLocation]:
        """Get a saved location by ID."""
        return self.locations.get(ref)

    def get_active_location_subscriptions(self) -> List[LocationSubscription]:
        """Get all enabled location subscriptions."""
        return [s for s in self.location_subscriptions if s.enabled]

    def get_active_trip_subscriptions(self) -> List[TripSubscription]:
        """Get all enabled trip subscriptions."""
        return [s for s in self.trip_subscriptions if s.enabled]

    def __str__(self) -> str:
        return f"User {self.id} ({self.email}): {len(self.locations)} locations, {len(self.location_subscriptions) + len(self.trip_subscriptions)} subscriptions"
