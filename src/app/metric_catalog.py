"""
MetricCatalog - Single Source of Truth for weather metrics.

SPEC: docs/specs/modules/weather_config.md v2.0

Defines all available weather metrics with:
- ForecastDataPoint field mapping
- Provider availability
- UI labels and units
- Default aggregations
- Formatter column definitions
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import UnifiedWeatherDisplayConfig


@dataclass(frozen=True)
class MetricDefinition:
    """Definition of a single weather metric."""
    id: str
    label_de: str
    unit: str
    dp_field: str
    category: str  # temperature, wind, precipitation, atmosphere, winter
    default_aggregations: tuple[str, ...]
    compact_label: str
    col_key: str
    col_label: str
    providers: dict[str, bool]
    default_enabled: bool = True


# --- Metric Registry ---

_METRICS: list[MetricDefinition] = [
    MetricDefinition(
        id="temperature", label_de="Temperatur", unit="°C",
        dp_field="t2m_c", category="temperature",
        default_aggregations=("min", "max", "avg"),
        compact_label="T", col_key="temp", col_label="Temp",
        providers={"openmeteo": True, "geosphere": True},
    ),
    MetricDefinition(
        id="wind_chill", label_de="Gefühlte Temperatur", unit="°C",
        dp_field="wind_chill_c", category="temperature",
        default_aggregations=("min",),
        compact_label="TF", col_key="felt", col_label="Feels",
        providers={"openmeteo": True, "geosphere": True},
    ),
    MetricDefinition(
        id="wind", label_de="Wind", unit="km/h",
        dp_field="wind10m_kmh", category="wind",
        default_aggregations=("max",),
        compact_label="W", col_key="wind", col_label="Wind",
        providers={"openmeteo": True, "geosphere": True},
    ),
    MetricDefinition(
        id="gust", label_de="Böen", unit="km/h",
        dp_field="gust_kmh", category="wind",
        default_aggregations=("max",),
        compact_label="G", col_key="gust", col_label="Gust",
        providers={"openmeteo": True, "geosphere": True},
    ),
    MetricDefinition(
        id="precipitation", label_de="Niederschlag", unit="mm",
        dp_field="precip_1h_mm", category="precipitation",
        default_aggregations=("sum",),
        compact_label="R", col_key="precip", col_label="Rain",
        providers={"openmeteo": True, "geosphere": True},
    ),
    MetricDefinition(
        id="thunder", label_de="Gewitter", unit="",
        dp_field="thunder_level", category="precipitation",
        default_aggregations=("max",),
        compact_label="⚡", col_key="thunder", col_label="Thunder",
        providers={"openmeteo": True, "geosphere": False},
    ),
    MetricDefinition(
        id="snowfall_limit", label_de="Schneefallgrenze", unit="m",
        dp_field="snowfall_limit_m", category="precipitation",
        default_aggregations=("min", "max"),
        compact_label="SG", col_key="snow_limit", col_label="SnowL",
        providers={"openmeteo": False, "geosphere": True},
    ),
    MetricDefinition(
        id="cloud_total", label_de="Bewölkung", unit="%",
        dp_field="cloud_total_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="C", col_key="cloud", col_label="Cloud",
        providers={"openmeteo": True, "geosphere": True},
    ),
    MetricDefinition(
        id="cloud_low", label_de="Tiefe Wolken", unit="%",
        dp_field="cloud_low_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="CL", col_key="cloud_low", col_label="CldLow",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
    ),
    MetricDefinition(
        id="cloud_mid", label_de="Mittelhohe Wolken", unit="%",
        dp_field="cloud_mid_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="CM", col_key="cloud_mid", col_label="CldMid",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
    ),
    MetricDefinition(
        id="cloud_high", label_de="Hohe Wolken", unit="%",
        dp_field="cloud_high_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="CH", col_key="cloud_high", col_label="CldHi",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
    ),
    MetricDefinition(
        id="humidity", label_de="Luftfeuchtigkeit", unit="%",
        dp_field="humidity_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="H", col_key="humidity", col_label="Humid",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
    ),
    MetricDefinition(
        id="dewpoint", label_de="Taupunkt", unit="°C",
        dp_field="dewpoint_c", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="DP", col_key="dewpoint", col_label="Cond°",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
    ),
    MetricDefinition(
        id="pressure", label_de="Luftdruck", unit="hPa",
        dp_field="pressure_msl_hpa", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="P", col_key="pressure", col_label="hPa",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
    ),
    MetricDefinition(
        id="visibility", label_de="Sichtweite", unit="m",
        dp_field="visibility_m", category="atmosphere",
        default_aggregations=("min",),
        compact_label="V", col_key="visibility", col_label="Visib",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
    ),
    MetricDefinition(
        id="rain_probability", label_de="Regenwahrscheinlichkeit", unit="%",
        dp_field="pop_pct", category="precipitation",
        default_aggregations=("max",),
        compact_label="P%", col_key="pop", col_label="Rain%",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
    ),
    MetricDefinition(
        id="cape", label_de="Gewitterenergie (CAPE)", unit="J/kg",
        dp_field="cape_jkg", category="precipitation",
        default_aggregations=("max",),
        compact_label="CE", col_key="cape", col_label="Thndr%",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
    ),
    MetricDefinition(
        id="freezing_level", label_de="Nullgradgrenze", unit="m",
        dp_field="freezing_level_m", category="winter",
        default_aggregations=("min", "max"),
        compact_label="0G", col_key="freeze_lvl", col_label="0°Line",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
    ),
    MetricDefinition(
        id="snow_depth", label_de="Schneehöhe", unit="cm",
        dp_field="snow_depth_cm", category="winter",
        default_aggregations=("max",),
        compact_label="SD", col_key="snow_depth", col_label="SnowH",
        providers={"openmeteo": False, "geosphere": True},
        default_enabled=False,
    ),
]

# Lookup by id
_METRICS_BY_ID: dict[str, MetricDefinition] = {m.id: m for m in _METRICS}

# Lookup by col_key (for formatter backward compat)
_METRICS_BY_COL_KEY: dict[str, MetricDefinition] = {m.col_key: m for m in _METRICS}


def get_metric(metric_id: str) -> MetricDefinition:
    """Get metric definition by ID. Raises KeyError if not found."""
    return _METRICS_BY_ID[metric_id]


def get_metric_by_col_key(col_key: str) -> MetricDefinition:
    """Get metric definition by column key. Raises KeyError if not found."""
    return _METRICS_BY_COL_KEY[col_key]


def get_all_metrics() -> list[MetricDefinition]:
    """Get all metric definitions in display order."""
    return list(_METRICS)


def get_metrics_by_category(category: str) -> list[MetricDefinition]:
    """Get metrics filtered by category."""
    return [m for m in _METRICS if m.category == category]


def get_default_enabled_metrics() -> list[str]:
    """Get IDs of metrics enabled by default."""
    return [m.id for m in _METRICS if m.default_enabled]


def build_default_display_config(trip_id: str = "") -> "UnifiedWeatherDisplayConfig":
    """
    Build default UnifiedWeatherDisplayConfig matching current EmailReportDisplayConfig defaults.

    This ensures backward compatibility: reports without explicit config
    produce identical output to the current hardcoded defaults.
    """
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    metrics = []
    for m in _METRICS:
        metrics.append(MetricConfig(
            metric_id=m.id,
            enabled=m.default_enabled,
            aggregations=list(m.default_aggregations),
        ))

    return UnifiedWeatherDisplayConfig(
        trip_id=trip_id,
        metrics=metrics,
        show_night_block=True,
        night_interval_hours=2,
        thunder_forecast_days=2,
        updated_at=datetime.now(timezone.utc),
    )


def get_col_defs() -> list[tuple[str, str, str]]:
    """
    Get column definitions for formatter, ordered by catalog order.

    Returns list of (col_key, col_label, col_key) tuples matching
    the old _COL_DEFS format.
    """
    return [(m.col_key, m.col_label, m.col_key) for m in _METRICS]
