"""Geographic utilities — single source of truth for haversine and compass.

Issue #1027: degrees_to_compass and haversine_km were duplicated across the
codebase with minor differences. This module provides one canonical
implementation for each.
"""
from __future__ import annotations

import math

_EARTH_KM = 6371.0088  # identical to Go earthRadiusKm

_COMPASS_LABELS = {
    "en": ["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
    "de": ["N", "NO", "O", "SO", "S", "SW", "W", "NW"],
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points in kilometres."""
    rad = math.pi / 180.0
    d_lat = (lat2 - lat1) * rad
    d_lon = (lon2 - lon1) * rad
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_KM * c


def degrees_to_compass(
    degrees: int | float | None,
    *,
    language: str = "en",
    none_label: str = "",
) -> str:
    """Convert wind direction in degrees (0-360) to an 8-point compass label.

    Args:
        degrees: Wind direction in degrees (0=N, 90=E, 180=S, 270=W).
        language: "en" or "de".
        none_label: Value returned when ``degrees`` is None.

    Returns:
        Compass direction string or ``none_label`` when the input is None.
    """
    if degrees is None:
        return none_label
    degrees = int(degrees) % 360
    directions = _COMPASS_LABELS.get(language, _COMPASS_LABELS["en"])
    return directions[round(degrees / 45) % 8]
