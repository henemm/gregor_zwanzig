"""
Trip and Waypoint data models.

Defines the structure for multi-waypoint trips/tours with support for:
- Multiple stages (days/sections)
- Multiple waypoints per stage with coordinates and time windows
- Configurable aggregation profiles
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from typing import List, Optional


class AggregationFunc(str, Enum):
    """Supported aggregation functions."""
    MIN = "MIN"
    MAX = "MAX"
    SUM = "SUM"
    AVG = "AVG"
    FIRST = "FIRST"
    LAST = "LAST"
    AT_HIGHEST = "AT_HIGHEST"  # Value at highest elevation point
    AT_LOWEST = "AT_LOWEST"    # Value at lowest elevation point


class ActivityProfile(str, Enum):
    """Pre-defined activity profiles with default aggregation rules."""
    WINTERSPORT = "wintersport"
    SUMMER_TREKKING = "summer_trekking"
    CUSTOM = "custom"


@dataclass(frozen=True)
class TimeWindow:
    """
    Time window for a waypoint.

    Represents the expected time range when the user will be at this waypoint.
    """
    start: time
    end: time

    def __str__(self) -> str:
        return f"{self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"

    @classmethod
    def from_string(cls, s: str) -> "TimeWindow":
        """Parse time window from string like '08:00-10:00'."""
        start_str, end_str = s.split("-")
        start = time.fromisoformat(start_str.strip())
        end = time.fromisoformat(end_str.strip())
        return cls(start=start, end=end)


@dataclass(frozen=True)
class Waypoint:
    """
    A single waypoint in a trip.

    Represents a geographic point with coordinates, elevation,
    and an optional time window for when the user expects to be there.

    Naming convention: G1, G2, G3 within a stage.
    """
    id: str  # e.g., "G1", "G2", "G3"
    name: str
    lat: float
    lon: float
    elevation_m: int
    time_window: Optional[TimeWindow] = None

    def __str__(self) -> str:
        tw = f" ({self.time_window})" if self.time_window else ""
        return f"{self.id} {self.name} ({self.elevation_m}m){tw}"


@dataclass(frozen=True)
class Stage:
    """
    A stage (Etappe) in a multi-day trip.

    Contains multiple waypoints for a single day/section.
    Naming convention: T1 (today), T2 (tomorrow), T3 (day after).
    """
    id: str  # e.g., "T1", "T2"
    name: str
    date: date
    waypoints: List[Waypoint]

    def __post_init__(self) -> None:
        if not self.waypoints:
            raise ValueError("Stage must have at least one waypoint")

    @property
    def first_waypoint(self) -> Waypoint:
        """First waypoint (G1) - typically the start."""
        return self.waypoints[0]

    @property
    def last_waypoint(self) -> Waypoint:
        """Last waypoint (Gn) - typically the end."""
        return self.waypoints[-1]

    @property
    def highest_waypoint(self) -> Waypoint:
        """Waypoint with highest elevation."""
        return max(self.waypoints, key=lambda w: w.elevation_m)

    @property
    def lowest_waypoint(self) -> Waypoint:
        """Waypoint with lowest elevation."""
        return min(self.waypoints, key=lambda w: w.elevation_m)

    def __str__(self) -> str:
        return f"{self.id} {self.name} ({self.date}): {len(self.waypoints)} waypoints"


@dataclass
class AggregationConfig:
    """
    Configuration for how metrics are aggregated across waypoints.

    Allows per-metric customization of aggregation functions.
    """
    profile: ActivityProfile = ActivityProfile.WINTERSPORT

    # Per-metric aggregation (can be single function or list for multiple)
    temperature: List[AggregationFunc] = field(
        default_factory=lambda: [AggregationFunc.MIN, AggregationFunc.MAX]
    )
    wind_chill: AggregationFunc = AggregationFunc.MIN
    wind: AggregationFunc = AggregationFunc.MAX
    gust: AggregationFunc = AggregationFunc.MAX
    precipitation: AggregationFunc = AggregationFunc.SUM
    snow_new: AggregationFunc = AggregationFunc.MAX
    snow_depth: AggregationFunc = AggregationFunc.AT_HIGHEST
    visibility: AggregationFunc = AggregationFunc.MIN
    avalanche_level: AggregationFunc = AggregationFunc.MAX
    thunderstorm: AggregationFunc = AggregationFunc.MAX

    @classmethod
    def for_profile(cls, profile: ActivityProfile) -> "AggregationConfig":
        """Create aggregation config for a specific activity profile."""
        if profile == ActivityProfile.WINTERSPORT:
            return cls(profile=profile)
        elif profile == ActivityProfile.SUMMER_TREKKING:
            return cls(
                profile=profile,
                temperature=[AggregationFunc.MAX, AggregationFunc.MIN],
                wind_chill=AggregationFunc.MAX,  # Heat index instead
                snow_new=AggregationFunc.MAX,
                snow_depth=AggregationFunc.MAX,
                avalanche_level=AggregationFunc.MAX,
            )
        else:
            return cls(profile=profile)


@dataclass
class Trip:
    """
    A complete trip with multiple stages and waypoints.

    Supports both single-day trips (one stage) and multi-day tours
    (multiple stages with different dates).

    Example:
        >>> trip = Trip(
        ...     id="stubai-2025-01-15",
        ...     name="Stubaier Skitour",
        ...     stages=[stage1, stage2],
        ...     avalanche_regions=["AT-7"],
        ... )
    """
    id: str
    name: str
    stages: List[Stage]
    avalanche_regions: List[str] = field(default_factory=list)
    aggregation: AggregationConfig = field(default_factory=AggregationConfig)
    weather_config: Optional["TripWeatherConfig"] = None  # Feature 2.6 (legacy, kept for migration)
    display_config: Optional["UnifiedWeatherDisplayConfig"] = None  # Feature 2.6 v2
    report_config: Optional["TripReportConfig"] = None  # Feature 3.5

    def __post_init__(self) -> None:
        if not self.stages:
            raise ValueError("Trip must have at least one stage")

    @property
    def start_date(self) -> date:
        """First date of the trip."""
        return min(s.date for s in self.stages)

    @property
    def end_date(self) -> date:
        """Last date of the trip."""
        return max(s.date for s in self.stages)

    @property
    def all_waypoints(self) -> List[Waypoint]:
        """All waypoints across all stages."""
        return [wp for stage in self.stages for wp in stage.waypoints]

    @property
    def highest_point(self) -> Waypoint:
        """Highest waypoint across entire trip."""
        return max(self.all_waypoints, key=lambda w: w.elevation_m)

    @property
    def lowest_point(self) -> Waypoint:
        """Lowest waypoint across entire trip."""
        return min(self.all_waypoints, key=lambda w: w.elevation_m)

    def get_stage_for_date(self, d: date) -> Optional[Stage]:
        """Get stage for a specific date."""
        for stage in self.stages:
            if stage.date == d:
                return stage
        return None

    def __str__(self) -> str:
        dates = f"{self.start_date}" if self.start_date == self.end_date else f"{self.start_date} - {self.end_date}"
        return f"{self.name} ({dates}): {len(self.stages)} stages, {len(self.all_waypoints)} waypoints"
