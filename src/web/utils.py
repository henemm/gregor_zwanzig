"""
Utility functions for the web UI.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple


def parse_dms_coordinates(dms_string: str) -> Optional[Tuple[float, float]]:
    """
    Parse DMS (Degrees Minutes Seconds) coordinate string to decimal.

    Supports formats like:
    - 47°16'11.1"N 11°50'50.2"E
    - 47°16'11.1"N, 11°50'50.2"E
    - 47°16'11.1" N 11°50'50.2" E

    Args:
        dms_string: DMS coordinate string from Google Maps

    Returns:
        Tuple of (latitude, longitude) in decimal degrees, or None if invalid
    """
    if not dms_string:
        return None

    # Pattern for DMS: degrees°minutes'seconds"direction
    pattern = r"(\d+)°(\d+)'([\d.]+)\"?\s*([NSEW])"

    matches = re.findall(pattern, dms_string.upper())

    if len(matches) != 2:
        return None

    lat = None
    lon = None

    for degrees, minutes, seconds, direction in matches:
        decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600

        if direction in ('S', 'W'):
            decimal = -decimal

        if direction in ('N', 'S'):
            lat = round(decimal, 6)
        else:
            lon = round(decimal, 6)

    if lat is None or lon is None:
        return None

    return (lat, lon)


def format_decimal_to_dms(lat: float, lon: float) -> str:
    """
    Convert decimal coordinates to DMS string.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees

    Returns:
        DMS string like "47°16'11.1"N 11°50'50.2"E"
    """
    def to_dms(decimal: float, is_lat: bool) -> str:
        direction = ('N' if decimal >= 0 else 'S') if is_lat else ('E' if decimal >= 0 else 'W')
        decimal = abs(decimal)
        degrees = int(decimal)
        minutes = int((decimal - degrees) * 60)
        seconds = round((decimal - degrees - minutes / 60) * 3600, 1)
        return f"{degrees}°{minutes}'{seconds}\"{direction}"

    return f"{to_dms(lat, True)} {to_dms(lon, False)}"
