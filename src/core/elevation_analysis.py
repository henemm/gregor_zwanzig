"""
Hoehenprofil-Analyse (Feature 1.3).

Erkennt markante Wegpunkte (Gipfel, Taeler) aus dem Hoehenprofil
eines GPX-Tracks mittels Sliding-Window-Algorithmus.

Spec: docs/specs/modules/elevation_analysis.md
"""
from __future__ import annotations

from app.models import DetectedWaypoint, GPXPoint, GPXTrack, WaypointType


def detect_waypoints(
    track: GPXTrack,
    min_prominence_m: float = 80.0,
    window_size: int = 50,
    min_distance_km: float = 0.5,
) -> list[DetectedWaypoint]:
    """Detect peaks and valleys from elevation profile.

    Uses sliding window to find local maxima (GIPFEL) and minima (TAL).
    Filters by minimum prominence and minimum distance between waypoints.
    Optionally matches detected waypoints with named GPX waypoints.

    Args:
        track: Parsed GPX track with elevation data.
        min_prominence_m: Minimum height difference to surrounding terrain.
        window_size: Number of points left/right for local max/min detection.
        min_distance_km: Minimum distance between two detected waypoints.

    Returns:
        List of DetectedWaypoint sorted by distance from start.
    """
    points = track.points
    if len(points) < window_size * 2 + 1:
        return []

    candidates: list[DetectedWaypoint] = []

    for i in range(window_size, len(points) - window_size):
        pt = points[i]
        if pt.elevation_m is None:
            continue

        # Get elevations in window
        window_elevations = [
            p.elevation_m for p in points[i - window_size : i + window_size + 1]
            if p.elevation_m is not None
        ]
        if not window_elevations:
            continue

        window_min = min(window_elevations)
        window_max = max(window_elevations)
        elev = pt.elevation_m

        # Check for local maximum (GIPFEL)
        if elev == window_max and elev != window_min:
            prominence = elev - window_min
            if prominence >= min_prominence_m:
                candidates.append(DetectedWaypoint(
                    type=WaypointType.GIPFEL,
                    point=pt,
                    prominence_m=round(prominence, 1),
                ))

        # Check for local minimum (TAL)
        elif elev == window_min and elev != window_max:
            prominence = window_max - elev
            if prominence >= min_prominence_m:
                candidates.append(DetectedWaypoint(
                    type=WaypointType.TAL,
                    point=pt,
                    prominence_m=round(prominence, 1),
                ))

    # Filter by minimum distance
    filtered = _filter_by_distance(candidates, min_distance_km)

    # Match with GPX waypoints
    _match_gpx_waypoints(filtered, track.waypoints)

    return filtered


def _filter_by_distance(
    candidates: list[DetectedWaypoint],
    min_distance_km: float,
) -> list[DetectedWaypoint]:
    """Keep only waypoints with sufficient distance between them.

    When two candidates are too close, keep the one with higher prominence.
    """
    if not candidates:
        return []

    # Sort by distance from start
    candidates.sort(key=lambda w: w.point.distance_from_start_km)

    result: list[DetectedWaypoint] = [candidates[0]]
    for candidate in candidates[1:]:
        last = result[-1]
        dist = candidate.point.distance_from_start_km - last.point.distance_from_start_km
        if dist >= min_distance_km:
            result.append(candidate)
        elif candidate.prominence_m > last.prominence_m:
            # Replace last with higher-prominence candidate
            result[-1] = candidate

    return result


def _match_gpx_waypoints(
    detected: list[DetectedWaypoint],
    gpx_waypoints: list,
    max_distance_km: float = 0.5,
) -> None:
    """Match detected waypoints with named GPX waypoints by proximity.

    Modifies detected waypoints in-place, setting the name field.
    """
    for det in detected:
        for wpt in gpx_waypoints:
            # Simple distance check using cumulative track distance
            # For GPX waypoints we need to find the closest track point
            dist = _point_distance_approx(det.point, wpt.lat, wpt.lon)
            if dist < max_distance_km:
                det.name = wpt.name
                break


def _point_distance_approx(point: GPXPoint, lat: float, lon: float) -> float:
    """Approximate distance in km between a GPXPoint and a lat/lon coordinate.

    Uses simple equirectangular approximation (sufficient for <10km distances).
    """
    import math
    lat1_rad = math.radians(point.lat)
    dlat = math.radians(lat - point.lat)
    dlon = math.radians(lon - point.lon) * math.cos(lat1_rad)
    return math.sqrt(dlat ** 2 + dlon ** 2) * 6371.0
