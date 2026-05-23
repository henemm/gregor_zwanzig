"""
JSON loaders and savers for Trip and User configurations.

Provides functions to load and save Trip and User objects from/to JSON files
with validation and error handling.
"""
from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Union

from app.models import (
    AlertMetric,
    AlertRule,
    AlertRuleKind,
    AlertSeverity,
)
from app.trip import (
    ActivityProfile,
    AggregationConfig,
    AggregationFunc,
    Stage,
    TimeWindow,
    Trip,
    Waypoint,
)


# Mapping Legacy report_config -> AlertMetric + Unit (Issue #205)
_LEGACY_DELTA_MAPPING: list[tuple[str, AlertMetric, str]] = [
    ("change_threshold_temp_c", AlertMetric.TEMPERATURE_CHANGE, "°C"),
    ("change_threshold_wind_kmh", AlertMetric.WIND_CHANGE, "km/h"),
    ("change_threshold_precip_mm", AlertMetric.PRECIPITATION_CHANGE, "mm"),
]


def _alert_rule_from_dict(d: Dict[str, Any]) -> AlertRule:
    """Parse a single AlertRule from a JSON dict."""
    return AlertRule(
        id=d["id"],
        kind=AlertRuleKind(d["kind"]),
        metric=AlertMetric(d["metric"]),
        threshold=float(d["threshold"]),
        unit=d.get("unit", ""),
        severity=AlertSeverity(d["severity"]),
        enabled=bool(d["enabled"]),
    )


def _migrate_legacy_alert_rules(data: Dict[str, Any]) -> List[AlertRule]:
    """Generate AlertRule list from legacy report_config fields.

    If `data["alert_rules"]` exists, parse it 1:1 (no re-migration).
    Otherwise, derive Delta-Rules from `report_config.change_threshold_*`.
    `alert_on_changes=False` keeps rules but marks them disabled (preserves
    user thresholds — Datenverlust-Prinzip BUG-DATALOSS-GR221).
    Legacy fields stay in `report_config` as fallback.
    """
    existing = data.get("alert_rules")
    if existing is not None:
        return [_alert_rule_from_dict(r) for r in existing]

    report_config = data.get("report_config", {}) or {}
    enabled = bool(report_config.get("alert_on_changes", False))

    rules: List[AlertRule] = []
    for legacy_field, metric, unit in _LEGACY_DELTA_MAPPING:
        threshold = report_config.get(legacy_field)
        if threshold is None:
            continue
        rules.append(AlertRule(
            id=str(uuid.uuid4()),
            kind=AlertRuleKind.DELTA,
            metric=metric,
            threshold=float(threshold),
            unit=unit,
            severity=AlertSeverity.WARNING,
            enabled=enabled,
        ))
    return rules
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


_DATA_ROOT: str | None = None


def load_trip(source: Union[str, Path, Dict[str, Any]]) -> Trip:
    """
    Load a Trip from a JSON file or a dict.

    Accepts either a filesystem path (str/Path) or a pre-parsed JSON dict
    (Issue #205 — Tests use the dict form directly).

    Args:
        source: Path to the JSON file or already-parsed trip dict

    Returns:
        Trip object

    Raises:
        LoaderError: If the file cannot be loaded or is invalid
    """
    if isinstance(source, dict):
        return _parse_trip(source.get("trip", source))

    path = Path(source)
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
                # Issue #296 — persistierte Naismith-Ankunftszeit erhalten (Datenverlust-Regel)
                arrival_calculated=wp_data.get("arrival_calculated"),
            )
            waypoints.append(waypoint)

        # Parse start_time if present
        start_time_val = None
        if "start_time" in stage_data:
            from datetime import time as _time
            start_time_val = _time.fromisoformat(stage_data["start_time"])

        stage = Stage(
            id=stage_data["id"],
            name=stage_data["name"],
            date=date.fromisoformat(stage_data["date"]),
            waypoints=waypoints,
            start_time=start_time_val,
        )
        stages.append(stage)

    # Parse aggregation config if present.
    # Default (kein aggregation-Block im JSON) ist ALLGEMEIN — Spec
    # docs/specs/modules/loader_display_config_default.md. Wir nutzen NICHT
    # den DTO-Default `AggregationConfig()` (= WINTERSPORT), weil dann der
    # else-Branch fuer den display_config-Default unten faelschlicherweise
    # ein wintersport-Template waehlen wuerde.
    aggregation = AggregationConfig.for_profile(ActivityProfile.ALLGEMEIN)
    if "aggregation" in data:
        agg_data = data["aggregation"]
        # Issue #111 Validator-Finding: agg_data.get("profile") kann None sein
        # (Key vorhanden, aber Wert null). Defensiv auf ALLGEMEIN mappen.
        profile_str = agg_data.get("profile") or "allgemein"
        try:
            profile = ActivityProfile(profile_str)
        except ValueError:
            # Unbekannter Profile-String -> ALLGEMEIN-Fallback (kein Crash)
            profile = ActivityProfile.ALLGEMEIN
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

    # Parse weather config if present (Feature 2.6 legacy)
    weather_config = None
    if "weather_config" in data:
        from app.models import TripWeatherConfig
        from datetime import datetime
        wc_data = data["weather_config"]
        weather_config = TripWeatherConfig(
            trip_id=wc_data["trip_id"],
            enabled_metrics=wc_data["enabled_metrics"],
            updated_at=datetime.fromisoformat(wc_data["updated_at"])
        )

    # Parse unified display config (Feature 2.6 v2) or migrate from old weather_config
    display_config = None
    if "display_config" in data:
        display_config = _parse_display_config(data["display_config"])
    elif weather_config is not None:
        display_config = _migrate_weather_config(weather_config)
    else:
        # Issue #111: kein display_config + kein weather_config -> profil-abhaengiger Default
        from app.metric_catalog import build_default_display_config_for_profile
        profile = (
            aggregation.profile
            if aggregation is not None and getattr(aggregation, "profile", None) is not None
            else ActivityProfile.ALLGEMEIN
        )
        display_config = build_default_display_config_for_profile(data["id"], profile)

    # Parse report config if present (Feature 3.5)
    report_config = None
    if "report_config" in data:
        from app.models import TripReportConfig
        from datetime import datetime, time
        rc_data = data["report_config"]
        dc_data = data.get("display_config", {})
        report_config = TripReportConfig(
            trip_id=rc_data.get("trip_id", data["id"]),
            enabled=rc_data.get("enabled", True),
            morning_time=time.fromisoformat(rc_data.get("morning_time", "07:00:00")),
            evening_time=time.fromisoformat(rc_data.get("evening_time", "18:00:00")),
            send_email=rc_data.get("send_email", True),
            send_sms=rc_data.get("send_sms", False),
            send_signal=rc_data.get("send_signal", False),
            send_telegram=rc_data.get("send_telegram", False),
            alert_on_changes=rc_data.get("alert_on_changes", True),
            change_threshold_temp_c=rc_data.get("change_threshold_temp_c", 5.0),
            change_threshold_wind_kmh=rc_data.get("change_threshold_wind_kmh", 20.0),
            change_threshold_precip_mm=rc_data.get("change_threshold_precip_mm", 10.0),
            wind_exposition_min_elevation_m=rc_data.get("wind_exposition_min_elevation_m"),
            show_compact_summary=rc_data.get(
                "show_compact_summary",
                dc_data.get("show_compact_summary", True),
            ),
            show_daylight=rc_data.get("show_daylight", True),
            multi_day_trend_reports=rc_data.get(
                "multi_day_trend_reports",
                dc_data.get("multi_day_trend_reports", ["evening"]),
            ),
            updated_at=datetime.fromisoformat(rc_data["updated_at"]) if "updated_at" in rc_data else datetime.now(),
        )

    # Issue #205: Alert Rules — either directly from JSON or migrated from legacy.
    alert_rules = _migrate_legacy_alert_rules(data)

    trip = Trip(
        id=data["id"],
        name=data["name"],
        stages=stages,
        avalanche_regions=data.get("avalanche_regions", []),
        aggregation=aggregation,
        weather_config=weather_config,
        display_config=display_config,
        report_config=report_config,
        alert_rules=alert_rules,
        alert_cooldown_minutes=data.get("alert_cooldown_minutes"),
        alert_quiet_from=data.get("alert_quiet_from"),
        alert_quiet_to=data.get("alert_quiet_to"),
    )
    return trip


def _parse_display_config(data: Dict[str, Any]) -> "UnifiedWeatherDisplayConfig":
    """Parse UnifiedWeatherDisplayConfig from dict."""
    from datetime import datetime as _dt
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    metrics = []
    for mc_data in data.get("metrics", []):
        metrics.append(MetricConfig(
            metric_id=mc_data["metric_id"],
            enabled=mc_data.get("enabled", True),
            aggregations=mc_data.get("aggregations", ["min", "max"]),
            morning_enabled=mc_data.get("morning_enabled"),
            evening_enabled=mc_data.get("evening_enabled"),
            use_friendly_format=mc_data.get("use_friendly_format", True),
            alert_enabled=mc_data.get("alert_enabled", False),
            alert_threshold=mc_data.get("alert_threshold"),
            horizons=mc_data.get("horizons"),
        ))

    return UnifiedWeatherDisplayConfig(
        trip_id=data.get("trip_id", ""),
        metrics=metrics,
        preset_name=data.get("preset_name"),
        show_night_block=data.get("show_night_block", True),
        night_interval_hours=data.get("night_interval_hours", 2),
        thunder_forecast_days=data.get("thunder_forecast_days", 2),
        multi_day_trend_reports=data.get("multi_day_trend_reports", ["evening"] if data.get("show_multi_day_trend", True) else []),
        sms_metrics=data.get("sms_metrics", []),
        updated_at=_dt.fromisoformat(data["updated_at"]) if "updated_at" in data else _dt.now(),
    )


# Migration map: old metric name -> (new metric_id, aggregation)
_OLD_METRIC_MAP: Dict[str, tuple] = {
    "temp_min_c": ("temperature", "min"),
    "temp_max_c": ("temperature", "max"),
    "temp_avg_c": ("temperature", "avg"),
    "wind_max_kmh": ("wind", "max"),
    "gust_max_kmh": ("gust", "max"),
    "precip_sum_mm": ("precipitation", "sum"),
    "cloud_avg_pct": ("cloud_total", "avg"),
    "humidity_avg_pct": ("humidity", "avg"),
    "thunder_level_max": ("thunder", "max"),
    "dewpoint_avg_c": ("dewpoint", "avg"),
    "pressure_avg_hpa": ("pressure", "avg"),
    "wind_chill_min_c": ("wind_chill", "min"),
}


def _migrate_weather_config(old_config) -> "UnifiedWeatherDisplayConfig":
    """
    Migrate old TripWeatherConfig to UnifiedWeatherDisplayConfig.

    Groups old metric names by new metric_id and builds MetricConfig entries.
    Metrics not in old config are set to disabled.
    """
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from app.metric_catalog import get_all_metrics

    # Collect enabled metric IDs with their aggregations from old config
    enabled_metrics: Dict[str, list] = {}
    for old_name in old_config.enabled_metrics:
        if old_name in _OLD_METRIC_MAP:
            metric_id, agg = _OLD_METRIC_MAP[old_name]
            if metric_id not in enabled_metrics:
                enabled_metrics[metric_id] = []
            enabled_metrics[metric_id].append(agg)

    # Build MetricConfig list for all catalog metrics
    metrics = []
    for m in get_all_metrics():
        if m.id in enabled_metrics:
            metrics.append(MetricConfig(
                metric_id=m.id,
                enabled=True,
                aggregations=enabled_metrics[m.id],
            ))
        else:
            metrics.append(MetricConfig(
                metric_id=m.id,
                enabled=False,
                aggregations=list(m.default_aggregations),
            ))

    return UnifiedWeatherDisplayConfig(
        trip_id=old_config.trip_id,
        metrics=metrics,
        updated_at=old_config.updated_at,
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


def get_snapshots_dir(user_id: str = "default") -> Path:
    """Get the weather snapshots directory for a user."""
    return get_data_dir(user_id) / "weather_snapshots"


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
            from app.profile import ActivityProfile
            activity_profile_str = data.get("activity_profile", "allgemein")
            display_config_data = data.get("display_config")
            display_config = _parse_display_config(display_config_data) if display_config_data else None
            locations.append(SavedLocation(
                id=data.get("id", path.stem),
                name=data["name"],
                lat=data["lat"],
                lon=data["lon"],
                elevation_m=data["elevation_m"],
                region=data.get("region"),
                bergfex_slug=data.get("bergfex_slug"),
                activity_profile=ActivityProfile(activity_profile_str),
                display_config=display_config,
            ))
        except (json.JSONDecodeError, KeyError, ValueError):
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
        "activity_profile": location.activity_profile.value,
    }
    if location.display_config is not None:
        dc = location.display_config
        data["display_config"] = {
            "trip_id": dc.trip_id,
            "metrics": [
                {
                    "metric_id": mc.metric_id,
                    "enabled": mc.enabled,
                    "aggregations": mc.aggregations,
                    "morning_enabled": mc.morning_enabled,
                    "evening_enabled": mc.evening_enabled,
                    "use_friendly_format": mc.use_friendly_format,
                    "alert_enabled": mc.alert_enabled,
                    "alert_threshold": mc.alert_threshold,
                }
                for mc in dc.metrics
            ],
            "show_night_block": dc.show_night_block,
            "night_interval_hours": dc.night_interval_hours,
            "thunder_forecast_days": dc.thunder_forecast_days,
            "multi_day_trend_reports": dc.multi_day_trend_reports,
            "sms_metrics": dc.sms_metrics,
            "updated_at": dc.updated_at.isoformat(),
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
        except Exception as e:
            # Issue #111 Validator-Finding: ein einzelner kaputter Trip darf
            # NICHT den gesamten Load fuer alle anderen Trips desselben Users
            # blockieren. Frueher fing das `except LoaderError:` nur einen Teil
            # ab — generische Exceptions (z.B. ValueError aus
            # ActivityProfile(None)) propagierten als HTTP 500.
            import logging
            logging.getLogger(__name__).warning(
                "Skipping corrupt trip %s: %s", path.name, e
            )
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
            # Issue #296 — persistierte Naismith-Ankunftszeit erhalten (omitempty-Äquivalent)
            if wp.arrival_calculated:
                wp_dict["arrival_calculated"] = wp.arrival_calculated
            waypoints_data.append(wp_dict)

        stage_dict = {
            "id": stage.id,
            "name": stage.name,
            "date": stage.date.isoformat(),
            "waypoints": waypoints_data,
        }
        if stage.start_time is not None:
            stage_dict["start_time"] = stage.start_time.isoformat()
        stages_data.append(stage_dict)

    data = {
        "id": trip.id,
        "name": trip.name,
        "stages": stages_data,
        "avalanche_regions": trip.avalanche_regions,
        "aggregation": {
            "profile": trip.aggregation.profile.value,
        },
    }

    # Serialize weather config (Feature 2.6 legacy, preserved for migration)
    if trip.weather_config:
        data["weather_config"] = {
            "trip_id": trip.weather_config.trip_id,
            "enabled_metrics": trip.weather_config.enabled_metrics,
            "updated_at": trip.weather_config.updated_at.isoformat()
        }

    # Serialize unified display config (Feature 2.6 v2)
    if trip.display_config:
        dc = trip.display_config
        data["display_config"] = {
            "trip_id": dc.trip_id,
            "metrics": [
                {
                    "metric_id": mc.metric_id,
                    "enabled": mc.enabled,
                    "aggregations": mc.aggregations,
                    "morning_enabled": mc.morning_enabled,
                    "evening_enabled": mc.evening_enabled,
                    "use_friendly_format": mc.use_friendly_format,
                    "alert_enabled": mc.alert_enabled,
                    "alert_threshold": mc.alert_threshold,
                }
                for mc in dc.metrics
            ],
            "show_night_block": dc.show_night_block,
            "night_interval_hours": dc.night_interval_hours,
            "thunder_forecast_days": dc.thunder_forecast_days,
            "multi_day_trend_reports": dc.multi_day_trend_reports,
            "sms_metrics": dc.sms_metrics,
            "updated_at": dc.updated_at.isoformat(),
            **({"preset_name": dc.preset_name} if dc.preset_name is not None else {}),
        }

    # Serialize alert cooldown and quiet hours (Issue #181)
    if trip.alert_cooldown_minutes is not None:
        data["alert_cooldown_minutes"] = trip.alert_cooldown_minutes
    if trip.alert_quiet_from is not None:
        data["alert_quiet_from"] = trip.alert_quiet_from
    if trip.alert_quiet_to is not None:
        data["alert_quiet_to"] = trip.alert_quiet_to

    # Serialize alert_rules (Issue #205) — always emit, even if empty
    data["alert_rules"] = [
        {
            "id": r.id,
            "kind": r.kind.value,
            "metric": r.metric.value,
            "threshold": r.threshold,
            "unit": r.unit,
            "severity": r.severity.value,
            "enabled": r.enabled,
        }
        for r in trip.alert_rules
    ]

    # Serialize report config (Feature 3.5)
    if trip.report_config:
        data["report_config"] = {
            "trip_id": trip.report_config.trip_id,
            "enabled": trip.report_config.enabled,
            "morning_time": trip.report_config.morning_time.isoformat(),
            "evening_time": trip.report_config.evening_time.isoformat(),
            "send_email": trip.report_config.send_email,
            "send_sms": trip.report_config.send_sms,
            "send_signal": trip.report_config.send_signal,
            "send_telegram": trip.report_config.send_telegram,
            "alert_on_changes": trip.report_config.alert_on_changes,
            "change_threshold_temp_c": trip.report_config.change_threshold_temp_c,
            "change_threshold_wind_kmh": trip.report_config.change_threshold_wind_kmh,
            "change_threshold_precip_mm": trip.report_config.change_threshold_precip_mm,
            "wind_exposition_min_elevation_m": trip.report_config.wind_exposition_min_elevation_m,
            "show_compact_summary": trip.report_config.show_compact_summary,
            "show_daylight": trip.report_config.show_daylight,
            "multi_day_trend_reports": trip.report_config.multi_day_trend_reports,
            "updated_at": trip.report_config.updated_at.isoformat(),
        }

    return data


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
    """Get the compare subscriptions file path for a user.

    Honors module-level _DATA_ROOT override (used in tests). When set, the
    path becomes `{_DATA_ROOT}/users/{user_id}/compare_subscriptions.json`.
    """
    import sys as _sys
    _root = getattr(_sys.modules[__name__], "_DATA_ROOT", None)
    if _root:
        return Path(_root) / "users" / user_id / "compare_subscriptions.json"
    return get_data_dir(user_id) / "compare_subscriptions.json"


def _parse_activity_profile(value: str | None):
    """Parse activity_profile string to enum, returns None if missing/invalid."""
    if not value:
        return None
    from app.profile import ActivityProfile
    try:
        return ActivityProfile(value)
    except ValueError:
        return None


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
            send_email=sub_data.get("send_email", True),
            send_signal=sub_data.get("send_signal", False),
            send_telegram=sub_data.get("send_telegram", False),
            display_config=_parse_display_config(sub_data["display_config"]) if sub_data.get("display_config") else None,
            activity_profile=_parse_activity_profile(sub_data.get("activity_profile")),
            recipients=sub_data.get("recipients", []),
            last_run=sub_data.get("last_run"),
            last_status=sub_data.get("last_status"),
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

    sub_list = []
    for sub in subscriptions:
        sub_dict = {
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
            "send_email": sub.send_email,
            "send_signal": sub.send_signal,
            "send_telegram": sub.send_telegram,
        }
        if sub.activity_profile is not None:
            sub_dict["activity_profile"] = sub.activity_profile.value
        # Issue #252 — Empfaenger und Lauf-Status (omitempty-Semantik)
        if sub.recipients:
            sub_dict["recipients"] = list(sub.recipients)
        if sub.last_run is not None:
            sub_dict["last_run"] = sub.last_run
        if sub.last_status is not None:
            sub_dict["last_status"] = sub.last_status
        if sub.display_config is not None:
            dc = sub.display_config
            sub_dict["display_config"] = {
                "trip_id": dc.trip_id,
                "metrics": [
                    {
                        "metric_id": mc.metric_id,
                        "enabled": mc.enabled,
                        "aggregations": mc.aggregations,
                        "morning_enabled": mc.morning_enabled,
                        "evening_enabled": mc.evening_enabled,
                        "use_friendly_format": mc.use_friendly_format,
                        "alert_enabled": mc.alert_enabled,
                        "alert_threshold": mc.alert_threshold,
                    }
                    for mc in dc.metrics
                ],
                "updated_at": dc.updated_at.isoformat(),
            }
        sub_list.append(sub_dict)

    data = {"subscriptions": sub_list}

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
