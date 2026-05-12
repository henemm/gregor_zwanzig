"""
Coordinate parsing utilities.

Pure functions for parsing geographic coordinates between formats.
Extracted from src/web/utils.py (Epic #129 Phase A.2) to live in the
services layer (UI-frei, server-side reuse durch API + UI).
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
