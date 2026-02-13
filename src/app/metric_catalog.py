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

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

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
    friendly_label: str = ""
    summary_fields: dict[str, str] = field(default_factory=dict)
    default_change_threshold: Optional[float] = None

    @property
    def has_friendly_format(self) -> bool:
        return bool(self.friendly_label)


# --- Metric Registry ---

_METRICS: list[MetricDefinition] = [
    # === TEMPERATURE ===
    MetricDefinition(
        id="temperature", label_de="Temperatur", unit="°C",
        dp_field="t2m_c", category="temperature",
        default_aggregations=("min", "max", "avg"),
        compact_label="T", col_key="temp", col_label="Temp",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"min": "temp_min_c", "max": "temp_max_c", "avg": "temp_avg_c"},
        default_change_threshold=5.0,
    ),
    MetricDefinition(
        id="wind_chill", label_de="Gefühlte Temperatur", unit="°C",
        dp_field="wind_chill_c", category="temperature",
        default_aggregations=("min",),
        compact_label="TF", col_key="felt", col_label="Feels",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"min": "wind_chill_min_c"},
        default_change_threshold=5.0,
    ),
    MetricDefinition(
        id="humidity", label_de="Luftfeuchtigkeit", unit="%",
        dp_field="humidity_pct", category="temperature",
        default_aggregations=("avg",),
        compact_label="H", col_key="humidity", col_label="Humid",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
        summary_fields={"avg": "humidity_avg_pct"},
        default_change_threshold=20,
    ),
    MetricDefinition(
        id="dewpoint", label_de="Taupunkt", unit="°C",
        dp_field="dewpoint_c", category="temperature",
        default_aggregations=("avg",),
        compact_label="DP", col_key="dewpoint", col_label="Cond°",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
        summary_fields={"avg": "dewpoint_avg_c"},
        default_change_threshold=5.0,
    ),
    # === WIND ===
    MetricDefinition(
        id="wind", label_de="Wind", unit="km/h",
        dp_field="wind10m_kmh", category="wind",
        default_aggregations=("max",),
        compact_label="W", col_key="wind", col_label="Wind",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"max": "wind_max_kmh"},
        default_change_threshold=20.0,
    ),
    MetricDefinition(
        id="gust", label_de="Böen", unit="km/h",
        dp_field="gust_kmh", category="wind",
        default_aggregations=("max",),
        compact_label="G", col_key="gust", col_label="Gust",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"max": "gust_max_kmh"},
        default_change_threshold=20.0,
    ),
    MetricDefinition(
        id="wind_direction", label_de="Windrichtung", unit="°",
        dp_field="wind_direction_deg", category="wind",
        default_aggregations=("avg",),
        compact_label="WD", col_key="wind_dir", col_label="WDir",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
        summary_fields={"avg": "wind_direction_avg_deg"},
        # Circular mean: no numeric delta comparison for alerts
    ),
    # === PRECIPITATION ===
    MetricDefinition(
        id="precipitation", label_de="Niederschlag", unit="mm",
        dp_field="precip_1h_mm", category="precipitation",
        default_aggregations=("sum",),
        compact_label="R", col_key="precip", col_label="Rain",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"sum": "precip_sum_mm"},
        default_change_threshold=10.0,
    ),
    MetricDefinition(
        id="rain_probability", label_de="Regenwahrscheinlichkeit", unit="%",
        dp_field="pop_pct", category="precipitation",
        default_aggregations=("max",),
        compact_label="P%", col_key="pop", col_label="Rain%",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        summary_fields={"max": "pop_max_pct"},
        default_change_threshold=20,
    ),
    MetricDefinition(
        id="thunder", label_de="Gewitter", unit="",
        dp_field="thunder_level", category="precipitation",
        default_aggregations=("max",),
        compact_label="⚡", col_key="thunder", col_label="Thunder",
        providers={"openmeteo": True, "geosphere": False},
        summary_fields={"max": "thunder_level_max"},
        default_change_threshold=1.0,
        friendly_label="⚡",
    ),
    MetricDefinition(
        id="cape", label_de="Gewitterenergie (CAPE)", unit="J/kg",
        dp_field="cape_jkg", category="precipitation",
        default_aggregations=("max",),
        compact_label="CE", col_key="cape", col_label="Thndr%",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        friendly_label="\U0001f7e2\U0001f7e1\U0001f534",
        summary_fields={"max": "cape_max_jkg"},
        default_change_threshold=500.0,
    ),
    MetricDefinition(
        id="snowfall_limit", label_de="Schneefallgrenze", unit="m",
        dp_field="snowfall_limit_m", category="precipitation",
        default_aggregations=("min", "max"),
        compact_label="SG", col_key="snow_limit", col_label="SnowL",
        providers={"openmeteo": False, "geosphere": True},
        # No summary_fields: not on SegmentWeatherSummary
    ),
    MetricDefinition(
        id="precip_type", label_de="Niederschlagsart", unit="",
        dp_field="precip_type", category="precipitation",
        default_aggregations=("max",),
        compact_label="PT", col_key="precip_type", col_label="PType",
        providers={"openmeteo": False, "geosphere": True},
        default_enabled=False,
        summary_fields={"max": "precip_type_dominant"},
        # Enum type: no numeric delta comparison for alerts
    ),
    # === ATMOSPHERE ===
    MetricDefinition(
        id="cloud_total", label_de="Bewölkung", unit="%",
        dp_field="cloud_total_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="C", col_key="cloud", col_label="Cloud",
        providers={"openmeteo": True, "geosphere": True},
        friendly_label="\u2600\ufe0f\u26c5\u2601\ufe0f",
        summary_fields={"avg": "cloud_avg_pct"},
        default_change_threshold=30,
    ),
    MetricDefinition(
        id="cloud_low", label_de="Tiefe Wolken", unit="%",
        dp_field="cloud_low_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="CL", col_key="cloud_low", col_label="CldLow",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        friendly_label="\u2600\ufe0f\u26c5\u2601\ufe0f",
        # No summary_fields: not on SegmentWeatherSummary
    ),
    MetricDefinition(
        id="cloud_mid", label_de="Mittelhohe Wolken", unit="%",
        dp_field="cloud_mid_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="CM", col_key="cloud_mid", col_label="CldMid",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        friendly_label="\u2600\ufe0f\u26c5\u2601\ufe0f",
        # No summary_fields: not on SegmentWeatherSummary
    ),
    MetricDefinition(
        id="cloud_high", label_de="Hohe Wolken", unit="%",
        dp_field="cloud_high_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="CH", col_key="cloud_high", col_label="CldHi",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        friendly_label="\u2600\ufe0f\u26c5\u2601\ufe0f",
        # No summary_fields: not on SegmentWeatherSummary
    ),
    MetricDefinition(
        id="visibility", label_de="Sichtweite", unit="m",
        dp_field="visibility_m", category="atmosphere",
        default_aggregations=("min",),
        compact_label="V", col_key="visibility", col_label="Visib",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        friendly_label="good/fog",
        summary_fields={"min": "visibility_min_m"},
        default_change_threshold=1000,
    ),
    MetricDefinition(
        id="uv_index", label_de="UV-Index", unit="",
        dp_field="uv_index", category="atmosphere",
        default_aggregations=("max",),
        compact_label="UV", col_key="uv", col_label="UV",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        summary_fields={"max": "uv_index_max"},
        default_change_threshold=3.0,
    ),
    MetricDefinition(
        id="pressure", label_de="Luftdruck", unit="hPa",
        dp_field="pressure_msl_hpa", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="P", col_key="pressure", col_label="hPa",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
        summary_fields={"avg": "pressure_avg_hpa"},
        default_change_threshold=10.0,
    ),
    # === WINTER ===
    MetricDefinition(
        id="freezing_level", label_de="Nullgradgrenze", unit="m",
        dp_field="freezing_level_m", category="winter",
        default_aggregations=("min", "max"),
        compact_label="0G", col_key="freeze_lvl", col_label="0°Line",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        # Single field on SegmentWeatherSummary (not min/max split)
        summary_fields={"min": "freezing_level_m"},
        default_change_threshold=200,
    ),
    MetricDefinition(
        id="snow_depth", label_de="Schneehöhe", unit="cm",
        dp_field="snow_depth_cm", category="winter",
        default_aggregations=("max",),
        compact_label="SD", col_key="snow_depth", col_label="SnowH",
        providers={"openmeteo": False, "geosphere": True},
        default_enabled=False,
        summary_fields={"max": "snow_depth_cm"},
        default_change_threshold=10.0,
    ),
    MetricDefinition(
        id="fresh_snow", label_de="Neuschnee", unit="cm",
        dp_field="snow_new_24h_cm", category="winter",
        default_aggregations=("sum",),
        compact_label="NS", col_key="fresh_snow", col_label="NewSn",
        providers={"openmeteo": False, "geosphere": True},
        default_enabled=False,
        summary_fields={"sum": "snow_new_sum_cm"},
        default_change_threshold=5.0,
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

    # Core metrics that get alert_enabled=True by default
    # (matches the old 3-slider behavior: temp, wind, gust, precip, wind_chill)
    _DEFAULT_ALERT_METRICS = {"temperature", "wind", "gust", "precipitation", "wind_chill"}

    metrics = []
    for m in _METRICS:
        metrics.append(MetricConfig(
            metric_id=m.id,
            enabled=m.default_enabled,
            aggregations=list(m.default_aggregations),
            alert_enabled=m.id in _DEFAULT_ALERT_METRICS,
        ))

    return UnifiedWeatherDisplayConfig(
        trip_id=trip_id,
        metrics=metrics,
        show_night_block=True,
        night_interval_hours=2,
        thunder_forecast_days=2,
        updated_at=datetime.now(timezone.utc),
    )


def get_change_detection_map() -> dict[str, float]:
    """
    Build {summary_field: threshold} from MetricCatalog.

    Iterates all metrics, expands summary_fields, pairs each field
    with default_change_threshold. Skips metrics with threshold=None.

    Returns:
        Dict mapping SegmentWeatherSummary field names to thresholds.
        Example: {"temp_min_c": 5.0, "temp_max_c": 5.0, "wind_max_kmh": 20.0, ...}
    """
    result: dict[str, float] = {}
    for m in _METRICS:
        if m.default_change_threshold is None:
            continue
        for summary_field in m.summary_fields.values():
            result[summary_field] = m.default_change_threshold
    return result


def get_compact_label_for_field(summary_field: str) -> tuple[str, str] | None:
    """
    Reverse-lookup: summary_field -> (compact_label, unit_short).

    Finds the MetricDefinition that maps to this summary field
    and returns compact label + short unit for SMS formatting.

    Args:
        summary_field: SegmentWeatherSummary field name (e.g. "temp_max_c")

    Returns:
        (compact_label, unit_short) or None if not found.
        Example: ("T", "C") for "temp_max_c"
    """
    for m in _METRICS:
        if summary_field in m.summary_fields.values():
            # Derive short unit from full unit (remove special chars)
            unit_short = m.unit.replace("°", "").replace("/", "").replace(" ", "")
            return (m.compact_label, unit_short)
    return None


def get_label_for_field(summary_field: str) -> tuple[str, str, str] | None:
    """
    Reverse-lookup: summary_field -> (label_de, aggregation, unit).

    For human-readable display in alert emails.
    Example: "temp_max_c" -> ("Temperatur", "max", "°C")
    """
    for m in _METRICS:
        for agg, field in m.summary_fields.items():
            if field == summary_field:
                return (m.label_de, agg, m.unit)
    return None


def get_col_defs() -> list[tuple[str, str, str]]:
    """
    Get column definitions for formatter, ordered by catalog order.

    Returns list of (col_key, col_label, col_key) tuples matching
    the old _COL_DEFS format.
    """
    return [(m.col_key, m.col_label, m.col_key) for m in _METRICS]
