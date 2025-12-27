"""
Data Transfer Objects (DTOs) for Gregor Zwanzig.

Defines the normalized data structures used across all providers.
See docs/reference/api_contract.md for full specification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class Provider(str, Enum):
    """Supported weather data providers."""
    MOSMIX = "MOSMIX"
    MET = "MET"
    NOWCASTMIX = "NOWCASTMIX"
    GEOSPHERE = "GEOSPHERE"
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


@dataclass
class ForecastDataPoint:
    """Single data point in a forecast timeseries."""
    ts: datetime

    # Base fields (always present)
    t2m_c: Optional[float] = None
    wind10m_kmh: Optional[float] = None
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
