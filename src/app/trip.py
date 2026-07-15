"""
Trip and Waypoint data models.

Defines the structure for multi-waypoint trips/tours with support for:
- Multiple stages (days/sections)
- Multiple waypoints per stage with coordinates and time windows
- Configurable aggregation profiles
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, time
from enum import Enum
from typing import Any, Dict, List, Optional


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


from app.profile import ActivityProfile  # noqa: E402,F401  # re-export — siehe docs/specs/modules/activity_profile.md

# Issue #760: Dedup-Pattern für Etappen-Präfixe (Etappe N / Tag N)
_STAGE_PREFIX_RE = re.compile(
    r"^\s*(?:Etappe|Tag)\s*\d+\b\s*[:.\-–—]?\s*(?P<rest>.*)$",
    re.IGNORECASE,
)


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
    arrival_calculated: Optional[str] = None  # Issue #296 — "HH:MM", vom Backend berechnet (Naismith)
    # Issue #303 — algorithmische Wegpunktvorschläge + Override.
    origin: Optional[str] = None              # "manual" | "algorithmic"
    confirmed: Optional[bool] = None          # True = bestätigt; False bleibt erhalten (≠ None)
    suggestion_reason: Optional[str] = None   # "detected_peak" | "detected_valley" | "detected_pass" | "legacy_suggested"
    arrival_override: Optional[str] = None    # User-Override "HH:MM"

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
    start_time: Optional[time] = None  # Startzeit der Etappe (default: 08:00 in Business Logic)

    @property
    def first_waypoint(self) -> Optional[Waypoint]:
        """First waypoint (G1) - typically the start. None for pause stages."""
        return self.waypoints[0] if self.waypoints else None

    @property
    def last_waypoint(self) -> Optional[Waypoint]:
        """Last waypoint (Gn) - typically the end. None for pause stages."""
        return self.waypoints[-1] if self.waypoints else None

    @property
    def highest_waypoint(self) -> Optional[Waypoint]:
        """Waypoint with highest elevation. None for pause stages."""
        return max(self.waypoints, key=lambda w: w.elevation_m) if self.waypoints else None

    @property
    def lowest_waypoint(self) -> Optional[Waypoint]:
        """Waypoint with lowest elevation. None for pause stages."""
        return min(self.waypoints, key=lambda w: w.elevation_m) if self.waypoints else None

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
    alert_rules: List["AlertRule"] = field(default_factory=list)  # Issue #205
    corridors: List["Corridor"] = field(default_factory=list)  # Issue #1231: additiv, s. Corridor
    alert_cooldown_minutes: Optional[int] = None  # Issue #181: per-trip cooldown (0=no limit)
    alert_quiet_from: Optional[str] = None  # Issue #181: quiet hours start "HH:MM"
    alert_quiet_to: Optional[str] = None  # Issue #181: quiet hours end "HH:MM"
    shortcode: str = ""  # Bug #775: GZ#XXXX — per-user eindeutig, ASCII, immun gegen Q-Encoding
    activity: str = ""  # Issue #802: Aktivitätstyp (z.B. "fahrrad_20") für Segment-Tempo
    region: str = ""  # Issue #805: Go-Feld region (z.B. "GR20") — roundtrip-erhalten
    archived_at: Optional[str] = None  # Issue #805: Go-Feld archived_at (ISO-String) — roundtrip-erhalten
    paused_at: Optional[str] = None  # Issue #995: Go-Feld paused_at (ISO-String) — Trip-Detail-Pause, roundtrip-erhalten
    official_alerts_enabled: Optional[bool] = None  # Issue #1087: None/True=aktiv, False=strukturell kein Fetch
    official_alert_triggers_enabled: Optional[bool] = None  # Issue #1088: None/True=aktiv, False=kein Sofort-Alert-Trigger
    # Issue #1258: additiv, loest official_alert_triggers_enabled funktional ab.
    # Bare-Konstruktor (Neuanlage) -> {"enabled": False}; ein aus JSON GELADENER
    # Trip ohne Schluessel bleibt None (= noch nicht migriert, s. app.loader._parse_trip).
    official_warnings: Optional[dict] = field(default_factory=lambda: {"enabled": False})
    extra: Dict[str, Any] = field(default_factory=dict)  # #991: unmodellierte Top-Level-Keys, roundtrip-erhalten
    # Issue #1250 Scheibe 4: additive flache Slot-/Kanal-Felder, beim Laden aus
    # `report_config` ABGELEITET (Dual-Read, s. app.loader._parse_trip). Nicht
    # autoritativ — `report_config` bleibt die einzige Wahrheit fuer den Versand.
    # KEIN `end_date`-Feld hier (bleibt @property, s.u.) — wuerde sonst die
    # Property verdecken (Risiko i, docs/context/feat-1250-s4-trip-konvergenz.md).
    morning_time: Optional[str] = None
    evening_time: Optional[str] = None
    morning_enabled: Optional[bool] = None
    evening_enabled: Optional[bool] = None
    send_email: Optional[bool] = None
    send_sms: Optional[bool] = None
    send_telegram: Optional[bool] = None

    @property
    def start_date(self) -> Optional[date]:
        """First date of the trip. None if the trip has no stages (leerer
        Editor-Zustand ist erlaubt, s. Fix-Loop F001/F002 Issue #1250 S4:
        Adversary BROKEN -- Materialisierung darf nicht crashen)."""
        return min((s.date for s in self.stages), default=None)

    @property
    def end_date(self) -> Optional[date]:
        """Last date of the trip. None if the trip has no stages (s.
        start_date)."""
        return max((s.date for s in self.stages), default=None)

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

    def get_future_stages(self, from_date: date) -> List[Stage]:
        """Get all stages strictly after from_date, sorted by date."""
        return sorted(
            [s for s in self.stages if s.date > from_date],
            key=lambda s: s.date,
        )

    def numbered_stage_label(self, stage: "Stage") -> str:
        """Etappen-Bezeichnung mit zwingender, dedupliziert vorangestellter Nummer.

        Die Nummer ist die 1-basierte chronologische Position der Etappe innerhalb
        der Tour (Etappen nach Datum sortiert). Trägt der Name bereits ein
        'Etappe N'/'Tag N'-Präfix, wird dieses durch die korrekte 'Etappe N:'-Form
        ersetzt (keine doppelte Nummer). Spec: docs/specs/modules/issue_760_stage_number.md
        """
        ordered = sorted(self.stages, key=lambda s: s.date)
        try:
            number = ordered.index(stage) + 1
        except ValueError:
            number = self.stages.index(stage) + 1  # Fallback: Listenposition
        name = (stage.name or "").strip()
        m = _STAGE_PREFIX_RE.match(name)
        rest = m.group("rest").strip() if m else name
        return f"Etappe {number}: {rest}" if rest else f"Etappe {number}"

    def __str__(self) -> str:
        dates = f"{self.start_date}" if self.start_date == self.end_date else f"{self.start_date} - {self.end_date}"
        return f"{self.name} ({dates}): {len(self.stages)} stages, {len(self.all_waypoints)} waypoints"
