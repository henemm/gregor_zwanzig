"""
Usable daylight calculation for hikers (F11).

Combines astronomical twilight (astral), terrain heuristics (GPX elevation),
and weather corrections (cloud cover, precipitation) into a practical
"headlamp-free" time window.

SPEC: docs/specs/modules/daylight_service.md v1.0
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.models import ForecastDataPoint

logger = logging.getLogger("daylight_service")


@dataclass
class DaylightWindow:
    """Effective daylight window for a hiking day."""

    civil_dawn: datetime
    civil_dusk: datetime
    sunrise: datetime
    sunset: datetime
    usable_start: datetime
    usable_end: datetime
    duration_minutes: int
    terrain_dawn_penalty_min: int = 0
    terrain_dusk_penalty_min: int = 0
    weather_dawn_penalty_min: int = 0
    weather_dusk_penalty_min: int = 0
    notes: list[str] = field(default_factory=list)


def compute_usable_daylight(
    lat: float,
    lon: float,
    target_date: date,
    elevation_m: float,
    route_max_elevation_m: float,
    forecast_data: list[ForecastDataPoint],
) -> Optional[DaylightWindow]:
    """Compute usable daylight window for a hiking day.

    Args:
        lat: Latitude of segment start
        lon: Longitude of segment start
        target_date: Date to compute daylight for
        elevation_m: Elevation at segment start (meters)
        route_max_elevation_m: Maximum elevation across all waypoints
        forecast_data: Hourly forecast data for weather corrections

    Returns:
        DaylightWindow or None (polar edge cases where sun doesn't rise/set)
    """
    from astral import Observer
    from astral.sun import dawn, dusk, sunrise, sunset

    obs = Observer(latitude=lat, longitude=lon, elevation=elevation_m)

    try:
        civil_dawn = dawn(obs, date=target_date, depression=6.0, tzinfo=timezone.utc)
        civil_dusk = dusk(obs, date=target_date, depression=6.0, tzinfo=timezone.utc)
        sun_rise = sunrise(obs, date=target_date, tzinfo=timezone.utc)
        sun_set = sunset(obs, date=target_date, tzinfo=timezone.utc)
    except ValueError:
        # Polar edge case: sun doesn't rise or set
        logger.warning(f"No sunrise/sunset at {lat},{lon} on {target_date}")
        return None

    # --- Schicht 2: Tal-Heuristik ---
    terrain_dawn_penalty = 0
    terrain_dusk_penalty = 0
    notes: list[str] = []

    elevation_diff = route_max_elevation_m - elevation_m
    if elevation_diff > 300:
        # Scale penalty: 300m diff = ~6min, 1250m diff = 25min (capped)
        penalty = min(25, int(elevation_diff / 50))
        terrain_dawn_penalty = penalty
        terrain_dusk_penalty = penalty
        notes.append(f"Tal-Lage +{penalty}min")

    # --- Schicht 3: Wetter-Korrektur ---
    weather_dawn_penalty = 0
    weather_dusk_penalty = 0

    dawn_weather = _find_weather_near_time(forecast_data, civil_dawn)
    dusk_weather = _find_weather_near_time(forecast_data, civil_dusk)

    if dawn_weather:
        cloud = dawn_weather.cloud_total_pct
        precip = dawn_weather.precip_1h_mm
        if cloud is not None and cloud > 80:
            # Heavy clouds: twilight is useless, shift to sunrise
            diff_to_sunrise = int((sun_rise - civil_dawn).total_seconds() / 60)
            weather_dawn_penalty += diff_to_sunrise
            notes.append(f"Wolken +{diff_to_sunrise}min")
        if precip is not None and precip > 2.0:
            weather_dawn_penalty += 15
            notes.append("Niederschlag +15min")

    if dusk_weather:
        cloud = dusk_weather.cloud_total_pct
        precip = dusk_weather.precip_1h_mm
        if cloud is not None and cloud > 80:
            diff_to_sunset = int((civil_dusk - sun_set).total_seconds() / 60)
            weather_dusk_penalty += diff_to_sunset
        if precip is not None and precip > 2.0:
            weather_dusk_penalty += 15

    # --- Effektives Fenster ---
    usable_start = civil_dawn + timedelta(minutes=terrain_dawn_penalty + weather_dawn_penalty)
    usable_end = civil_dusk - timedelta(minutes=terrain_dusk_penalty + weather_dusk_penalty)

    # Sanity: usable_end must be after usable_start
    if usable_end <= usable_start:
        usable_start = sun_rise
        usable_end = sun_set
        notes.append("Korrekturen ueberschritten, Fallback auf Sunrise/Sunset")

    duration_min = int((usable_end - usable_start).total_seconds() / 60)

    return DaylightWindow(
        civil_dawn=civil_dawn,
        civil_dusk=civil_dusk,
        sunrise=sun_rise,
        sunset=sun_set,
        usable_start=usable_start,
        usable_end=usable_end,
        duration_minutes=duration_min,
        terrain_dawn_penalty_min=terrain_dawn_penalty,
        terrain_dusk_penalty_min=terrain_dusk_penalty,
        weather_dawn_penalty_min=weather_dawn_penalty,
        weather_dusk_penalty_min=weather_dusk_penalty,
        notes=notes,
    )


def _find_weather_near_time(
    data: list[ForecastDataPoint],
    target: datetime,
) -> Optional[ForecastDataPoint]:
    """Find the forecast data point closest to target time (within 1h)."""
    if not data:
        return None
    # Ensure target is timezone-aware for comparison
    if target.tzinfo is not None:
        target_utc = target
    else:
        target_utc = target.replace(tzinfo=timezone.utc)

    best = None
    best_diff = timedelta(hours=2)
    for dp in data:
        # Make dp.ts timezone-aware if needed
        dp_ts = dp.ts if dp.ts.tzinfo is not None else dp.ts.replace(tzinfo=timezone.utc)
        diff = abs(dp_ts - target_utc)
        if diff < best_diff:
            best_diff = diff
            best = dp
    if best_diff > timedelta(hours=1):
        return None
    return best
