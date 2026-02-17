"""
Data Transfer Objects (DTOs) for Gregor Zwanzig.

Defines the normalized data structures used across all providers.
See docs/reference/api_contract.md for full specification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import List, Optional


class Provider(str, Enum):
    """Supported weather data providers."""
    MOSMIX = "MOSMIX"
    MET = "MET"
    NOWCASTMIX = "NOWCASTMIX"
    GEOSPHERE = "GEOSPHERE"
    OPENMETEO = "OPENMETEO"
    SLF = "SLF"
    EUREGIO = "EUREGIO"


class ThunderLevel(str, Enum):
    """Thunderstorm risk level."""
    NONE = "NONE"
    MED = "MED"
    HIGH = "HIGH"


class PrecipType(str, Enum):
    """Precipitation type classification."""
    RAIN = "RAIN"
    SNOW = "SNOW"
    MIXED = "MIXED"
    FREEZING_RAIN = "FREEZING_RAIN"


class AvalancheProblem(str, Enum):
    """European avalanche problem types."""
    NEW_SNOW = "new_snow"
    WIND_SLAB = "wind_slab"
    PERSISTENT_WEAK = "persistent_weak"
    WET_SNOW = "wet_snow"
    GLIDING_SNOW = "gliding_snow"


class DangerTrend(str, Enum):
    """Avalanche danger trend."""
    INCREASING = "increasing"
    STEADY = "steady"
    DECREASING = "decreasing"


@dataclass
class StationInfo:
    """Information about a weather station used for data."""
    id: str
    name: str
    dist_km: float
    elev_diff_m: float


@dataclass
class ForecastMeta:
    """Metadata for a forecast timeseries."""
    provider: Provider
    model: str
    run: datetime
    grid_res_km: float
    interp: str  # e.g., "point_grid", "nearest_station", "idw2"
    stations_used: List[StationInfo] = field(default_factory=list)
    # WEATHER-05b: Fallback tracking
    fallback_model: Optional[str] = None
    fallback_metrics: List[str] = field(default_factory=list)


@dataclass
class ForecastDataPoint:
    """Single data point in a forecast timeseries."""
    ts: datetime

    # Base fields (always present)
    t2m_c: Optional[float] = None
    wind10m_kmh: Optional[float] = None
    wind_direction_deg: Optional[int] = None  # 0-360, 0=N, 90=E, 180=S, 270=W
    gust_kmh: Optional[float] = None
    precip_rate_mmph: Optional[float] = None
    precip_1h_mm: Optional[float] = None
    cloud_total_pct: Optional[int] = None
    symbol: Optional[str] = None
    thunder_level: Optional[ThunderLevel] = None
    cape_jkg: Optional[float] = None
    pop_pct: Optional[int] = None
    pressure_msl_hpa: Optional[float] = None
    humidity_pct: Optional[int] = None
    dewpoint_c: Optional[float] = None
    uv_index: Optional[float] = None

    # Wintersport fields (optional)
    snow_depth_cm: Optional[float] = None
    snow_new_24h_cm: Optional[float] = None
    snow_new_acc_cm: Optional[float] = None
    snowfall_limit_m: Optional[int] = None
    swe_kgm2: Optional[float] = None
    precip_type: Optional[PrecipType] = None
    freezing_level_m: Optional[int] = None
    wind_chill_c: Optional[float] = None
    visibility_m: Optional[int] = None

    # Cloud layers (from Open-Meteo)
    cloud_low_pct: Optional[int] = None   # 0-100%, bis 3km
    cloud_mid_pct: Optional[int] = None   # 0-100%, 3-8km
    cloud_high_pct: Optional[int] = None  # 0-100%, ab 8km


@dataclass
class NormalizedTimeseries:
    """Normalized forecast timeseries from any provider."""
    meta: ForecastMeta
    data: List[ForecastDataPoint]


# --- Avalanche Report DTOs (separate from weather forecast) ---

@dataclass
class AvalancheProblemInfo:
    """Single avalanche problem with location details."""
    type: AvalancheProblem
    aspects: List[str]  # N, NE, E, SE, S, SW, W, NW
    elevation_from_m: Optional[int] = None
    elevation_to_m: Optional[int] = None


@dataclass
class AvalancheDanger:
    """Avalanche danger rating."""
    level: int  # 1-5 European scale
    level_text: str  # gering/maessig/erheblich/gross/sehr gross
    elevation_above_m: Optional[int] = None
    level_below: Optional[int] = None  # danger level below elevation
    trend: Optional[DangerTrend] = None


@dataclass
class SnowpackInfo:
    """Snowpack structure assessment."""
    structure: str  # unfavorable, moderate, favorable
    description: Optional[str] = None


@dataclass
class AvalancheReportMeta:
    """Metadata for avalanche report."""
    provider: Provider
    region_id: str
    region_name: str
    valid_from: datetime
    valid_to: datetime
    published: datetime


@dataclass
class AvalancheReport:
    """
    Avalanche danger report (Lawinenlagebericht).

    Separate DTO from NormalizedTimeseries as per spec decision.
    Providers: EUREGIO (Tirol/Suedtirol), SLF (Switzerland), ZAMG (Austria).
    """
    meta: AvalancheReportMeta
    danger: AvalancheDanger
    problems: List[AvalancheProblemInfo] = field(default_factory=list)
    snowpack: Optional[SnowpackInfo] = None


# --- Risk Assessment DTOs ---

class RiskType(str, Enum):
    """Types of weather/avalanche risks."""
    THUNDERSTORM = "thunderstorm"
    RAIN = "rain"
    WIND = "wind"
    AVALANCHE = "avalanche"
    SNOWFALL = "snowfall"
    WIND_CHILL = "wind_chill"
    POOR_VISIBILITY = "poor_visibility"
    FREEZING_RAIN = "freezing_rain"


class RiskLevel(str, Enum):
    """Risk severity levels."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


@dataclass
class Risk:
    """Single risk assessment."""
    type: RiskType
    level: RiskLevel
    from_time: Optional[datetime] = None
    # Type-specific fields (optional)
    amount_mm: Optional[float] = None
    amount_cm: Optional[float] = None
    danger_level: Optional[int] = None
    problems: Optional[List[str]] = None
    feels_like_c: Optional[float] = None
    visibility_m: Optional[int] = None
    gust_kmh: Optional[float] = None


@dataclass
class RiskAssessment:
    """Collection of assessed risks for a forecast period."""
    risks: List[Risk] = field(default_factory=list)


# --- GPX Trip Planning DTOs (Story 1, 2, 3) ---

class WaypointType(str, Enum):
    """Type of detected waypoint in elevation profile."""
    GIPFEL = "GIPFEL"
    TAL = "TAL"
    PASS = "PASS"


@dataclass
class GPXPoint:
    """Single point in a GPX track."""
    lat: float  # Breitengrad
    lon: float  # Längengrad
    elevation_m: Optional[float] = None  # Höhe über Meer [m]
    distance_from_start_km: float = 0.0  # Kumulative Distanz [km]


@dataclass
class GPXWaypoint:
    """Named waypoint from GPX file (e.g. summit, hut)."""
    name: str
    lat: float
    lon: float
    elevation_m: Optional[float] = None


@dataclass
class GPXTrack:
    """Parsed GPX track with computed metrics."""
    name: str
    points: List[GPXPoint]
    waypoints: List["GPXWaypoint"]
    total_distance_km: float
    total_ascent_m: float
    total_descent_m: float


@dataclass
class DetectedWaypoint:
    """Waypoint detected from elevation profile analysis."""
    type: WaypointType
    point: GPXPoint
    prominence_m: float  # Height difference to surrounding terrain
    name: Optional[str] = None  # From GPX waypoint if nearby


@dataclass
class EtappenConfig:
    """Configuration for hiking speed and segmentation."""
    speed_flat_kmh: float = 4.0        # Gehgeschwindigkeit Ebene [km/h]
    speed_ascent_mh: float = 300.0     # Steig-Geschwindigkeit [Hm/h]
    speed_descent_mh: float = 500.0    # Abstiegs-Geschwindigkeit [Hm/h]
    target_duration_hours: float = 2.0  # Ziel-Segment-Dauer [h]


@dataclass
class TripSegment:
    """Single segment of a trip (typically ~2 hours hiking)."""
    segment_id: int | str  # 1-based, or "Ziel" for destination
    start_point: GPXPoint
    end_point: GPXPoint
    start_time: datetime  # UTC!
    end_time: datetime  # UTC!
    duration_hours: float
    distance_km: float
    ascent_m: float
    descent_m: float
    # Optional fields for Story 1 (Feature 1.5)
    adjusted_to_waypoint: bool = False
    waypoint: Optional["DetectedWaypoint"] = None


@dataclass
class SegmentWeatherSummary:
    """Aggregated weather summary for segment duration."""
    # Basis metrics (Feature 2.2a) - ALL None for Feature 2.1
    temp_min_c: Optional[float] = None
    temp_max_c: Optional[float] = None
    temp_avg_c: Optional[float] = None
    wind_max_kmh: Optional[float] = None
    gust_max_kmh: Optional[float] = None
    precip_sum_mm: Optional[float] = None
    cloud_avg_pct: Optional[int] = None
    humidity_avg_pct: Optional[int] = None
    thunder_level_max: Optional[ThunderLevel] = None
    visibility_min_m: Optional[int] = None

    # Extended metrics (Feature 2.2b) - ALL None for Feature 2.1
    dewpoint_avg_c: Optional[float] = None
    pressure_avg_hpa: Optional[float] = None
    wind_chill_min_c: Optional[float] = None
    snow_depth_cm: Optional[float] = None
    freezing_level_m: Optional[int] = None

    # Additional metrics (OpenMeteo)
    pop_max_pct: Optional[int] = None
    cape_max_jkg: Optional[float] = None

    # Phase A: New metrics (v2.3)
    uv_index_max: Optional[float] = None
    snow_new_sum_cm: Optional[float] = None
    wind_direction_avg_deg: Optional[int] = None
    precip_type_dominant: Optional["PrecipType"] = None

    # Metadata
    aggregation_config: dict[str, str] = field(default_factory=dict)


@dataclass
class SegmentWeatherData:
    """Weather data for a single trip segment."""
    segment: TripSegment
    timeseries: Optional[NormalizedTimeseries]  # None bei Provider-Fehler
    aggregated: SegmentWeatherSummary  # Empty for Feature 2.1, populated by Feature 2.3
    fetched_at: datetime
    provider: str  # "geosphere", "openmeteo", etc.
    # Error tracking (WEATHER-04)
    has_error: bool = False
    error_message: Optional[str] = None


# --- Weather Change Detection DTOs (Feature 2.5) ---

class ChangeSeverity(str, Enum):
    """Severity classification for weather changes."""
    MINOR = "minor"       # 10-50% over threshold (1.1x - 1.5x)
    MODERATE = "moderate" # 50-100% over threshold (1.5x - 2.0x)
    MAJOR = "major"       # >100% over threshold (>2.0x)


@dataclass
class WeatherChange:
    """
    Detected significant weather change.

    Example:
        WeatherChange(
            metric="temp_max_c",
            old_value=18.0,
            new_value=25.0,
            delta=+7.0,
            threshold=5.0,
            severity=ChangeSeverity.MODERATE,
            direction="increase"
        )
    """
    metric: str                    # e.g., "temp_max_c", "wind_max_kmh"
    old_value: float               # Cached forecast value
    new_value: float               # Fresh forecast value
    delta: float                   # new_value - old_value (signed)
    threshold: float               # Configured threshold
    severity: ChangeSeverity       # minor/moderate/major
    direction: str                 # "increase" or "decrease"


# --- Trip Weather Config DTOs (Feature 2.6) ---

@dataclass
class TripWeatherConfig:
    """
    Weather metrics configuration per trip.

    Stores which of the 13 available metrics the user wants
    to see in their trip weather reports (Story 3).

    Example:
        TripWeatherConfig(
            trip_id="gr20-etappe3",
            enabled_metrics=["temp_max_c", "wind_max_kmh", "precip_sum_mm"],
            updated_at=datetime.now(timezone.utc)
        )
    """
    trip_id: str
    enabled_metrics: list[str]  # Subset of 13 metric names
    updated_at: datetime


# --- Email Display Config (Feature 3.1 v2) ---

@dataclass
class EmailReportDisplayConfig:
    """User-configurable display preferences for email trip reports."""
    show_temp_measured: bool = True
    show_temp_felt: bool = True
    temp_aggregation_day: str = "max"
    temp_aggregation_night: str = "min"
    show_wind: bool = True
    show_gusts: bool = True
    show_precipitation: bool = True
    show_thunder: bool = True
    show_snowfall_limit: bool = True
    show_clouds: bool = True
    show_humidity: bool = False
    show_night_block: bool = True
    night_interval_hours: int = 2
    thunder_forecast_days: int = 2


# --- Unified Weather Display Config (Feature 2.6 v2) ---

@dataclass
class MetricConfig:
    """Per-metric configuration within UnifiedWeatherDisplayConfig."""
    metric_id: str
    enabled: bool = True
    aggregations: list[str] = field(default_factory=lambda: ["min", "max"])
    # Phase 3: per-report-type overrides (None = follows global enabled)
    morning_enabled: Optional[bool] = None
    evening_enabled: Optional[bool] = None
    use_friendly_format: bool = True
    # Per-metric alert configuration (v2.3)
    alert_enabled: bool = False
    alert_threshold: Optional[float] = None  # None = MetricCatalog default


@dataclass
class UnifiedWeatherDisplayConfig:
    """
    Unified weather display configuration per trip.

    Replaces TripWeatherConfig (UI storage) + EmailReportDisplayConfig (formatter defaults)
    with a single config backed by MetricCatalog.

    SPEC: docs/specs/modules/weather_config.md v2.0
    """
    trip_id: str
    metrics: list[MetricConfig] = field(default_factory=list)
    show_night_block: bool = True
    night_interval_hours: int = 2
    thunder_forecast_days: int = 2
    multi_day_trend_reports: list[str] = field(default_factory=lambda: ["evening"])  # F3: Etappen-Ausblick
    sms_metrics: list[str] = field(default_factory=list)  # Phase 3
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_metric_enabled(self, metric_id: str) -> bool:
        """Check if a metric is enabled."""
        for mc in self.metrics:
            if mc.metric_id == metric_id:
                return mc.enabled
        return False

    def get_enabled_metric_ids(self) -> list[str]:
        """Return list of enabled metric IDs."""
        return [mc.metric_id for mc in self.metrics if mc.enabled]

    def get_enabled_metrics(self) -> list[MetricConfig]:
        """Return list of enabled MetricConfig entries."""
        return [mc for mc in self.metrics if mc.enabled]

    def get_alert_enabled_metrics(self) -> list[MetricConfig]:
        """Return metrics with alert_enabled=True."""
        return [mc for mc in self.metrics if mc.alert_enabled]


# --- Trip Report DTOs (Feature 3.1) ---

@dataclass
class TripReport:
    """
    Generated trip weather report.

    Contains formatted content ready for email/SMS delivery.
    Generated by TripReportFormatter (Feature 3.1).

    Example:
        TripReport(
            trip_id="gr20-etappe3",
            trip_name="GR20 Etappe 3",
            report_type="morning",
            generated_at=datetime.now(timezone.utc),
            segments=[...],
            email_subject="[GR20 Etappe 3] Morning - 29.08.2026",
            email_html="<!DOCTYPE html>...",
            email_plain="GR20 Etappe 3\n...",
            triggered_by="schedule"
        )
    """
    trip_id: str
    trip_name: str
    report_type: str  # "morning", "evening", "alert"
    generated_at: datetime
    segments: list[SegmentWeatherData]  # From Story 2

    # Formatted content
    email_subject: str
    email_html: str
    email_plain: str
    sms_text: Optional[str] = None  # Feature 3.2 will populate

    # Metadata
    triggered_by: Optional[str] = None  # "schedule" or "change_detection"
    changes: list[WeatherChange] = field(default_factory=list)  # If alert


# --- Trip Report Config DTO (Feature 3.5) ---

@dataclass
class TripReportConfig:
    """
    Configuration for trip weather reports (Feature 3.5).

    Stores user preferences for scheduled reports and alerts.

    Example:
        TripReportConfig(
            trip_id="gr20-etappe3",
            morning_time=time(7, 0),
            evening_time=time(18, 0),
            send_email=True,
            alert_on_changes=True,
            change_threshold_temp_c=5.0,
        )
    """
    trip_id: str
    enabled: bool = True

    # Schedule
    morning_time: time = field(default_factory=lambda: time(7, 0))
    evening_time: time = field(default_factory=lambda: time(18, 0))

    # Channels
    send_email: bool = True
    send_sms: bool = False

    # Alerts
    alert_on_changes: bool = True
    change_threshold_temp_c: float = 5.0
    change_threshold_wind_kmh: float = 20.0
    change_threshold_precip_mm: float = 10.0

    # Metadata
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
