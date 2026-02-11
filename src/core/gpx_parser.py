"""
GPX Parser & Validation (Feature 1.2).

Parses GPX files (Komoot GPX 1.0/1.1) using gpxpy library.
Extracts track points with coordinates, elevation, and cumulative distances.
Validates file structure and data quality.

Spec: docs/specs/modules/gpx_parser.md
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import gpxpy
import gpxpy.gpx

from app.models import GPXPoint, GPXTrack, GPXWaypoint


class GPXParseError(ValueError):
    """Raised when GPX file is invalid or cannot be parsed."""


# Default elevation threshold (meters) - like Strava/Garmin
ELEVATION_THRESHOLD_M = 5.0


def parse_gpx(
    file_path: str | Path,
    elevation_threshold_m: Optional[float] = None,
) -> GPXTrack:
    """Parse GPX file and return track with computed distances.

    Uses gpxpy for XML parsing and distance calculation.
    Elevation gain/loss computed with threshold-based filter.

    Args:
        file_path: Path to .gpx file.
        elevation_threshold_m: Minimum elevation change to count (default: 5m).
            Set to 0.0 to disable filtering.

    Returns:
        GPXTrack with all points, computed distances and elevation gain/loss.

    Raises:
        GPXParseError: On invalid format, too few points, missing elevation,
            or invalid coordinates.
    """
    if elevation_threshold_m is None:
        elevation_threshold_m = ELEVATION_THRESHOLD_M

    file_path = Path(file_path)

    # Parse GPX file
    gpx = _parse_file(file_path)

    # Validate structure
    _validate_structure(gpx)

    # Extract track name
    name = _extract_name(gpx)

    # Extract waypoints
    waypoints = _extract_waypoints(gpx)

    # Extract track points with cumulative distances
    points = _extract_points(gpx)

    # Validate points
    _validate_points(points)

    # Compute elevation gain/loss
    total_ascent, total_descent = _compute_elevation_gain(points, elevation_threshold_m)

    # Total distance = last point's cumulative distance
    total_distance_km = points[-1].distance_from_start_km if points else 0.0

    return GPXTrack(
        name=name,
        points=points,
        waypoints=waypoints,
        total_distance_km=round(total_distance_km, 3),
        total_ascent_m=total_ascent,
        total_descent_m=total_descent,
    )


def _parse_file(file_path: Path) -> gpxpy.gpx.GPX:
    """Parse GPX file with gpxpy. Raises GPXParseError on failure."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, IOError) as e:
        raise GPXParseError(f"Datei nicht lesbar: {file_path} ({e})")

    if not content.strip():
        raise GPXParseError(f"Datei ist leer: {file_path}")

    try:
        return gpxpy.parse(content)
    except Exception as e:
        raise GPXParseError(f"Ungueltiges GPX-Format: {e}")


def _validate_structure(gpx: gpxpy.gpx.GPX) -> None:
    """Validate GPX has at least one track with segments."""
    if not gpx.tracks:
        raise GPXParseError("Keine Tracks in GPX-Datei gefunden")
    has_segments = any(track.segments for track in gpx.tracks)
    if not has_segments:
        raise GPXParseError("Keine Track-Segmente gefunden")


def _extract_name(gpx: gpxpy.gpx.GPX) -> str:
    """Extract track name from metadata or first track."""
    if gpx.tracks and gpx.tracks[0].name:
        return gpx.tracks[0].name
    if gpx.name:
        return gpx.name
    return "Unnamed Track"


def _extract_waypoints(gpx: gpxpy.gpx.GPX) -> list[GPXWaypoint]:
    """Extract named waypoints from GPX."""
    waypoints = []
    for wpt in gpx.waypoints:
        waypoints.append(GPXWaypoint(
            name=wpt.name or "Unnamed",
            lat=wpt.latitude,
            lon=wpt.longitude,
            elevation_m=wpt.elevation,
        ))
    return waypoints


def _extract_points(gpx: gpxpy.gpx.GPX) -> list[GPXPoint]:
    """Extract all track points from all segments with cumulative distances."""
    points: list[GPXPoint] = []
    cumulative_distance_m = 0.0

    for track in gpx.tracks:
        for segment in track.segments:
            prev_gpxpy_point = None
            for pt in segment.points:
                if prev_gpxpy_point is not None:
                    dist = pt.distance_2d(prev_gpxpy_point)
                    if dist is not None:
                        cumulative_distance_m += dist

                points.append(GPXPoint(
                    lat=pt.latitude,
                    lon=pt.longitude,
                    elevation_m=pt.elevation,
                    distance_from_start_km=round(cumulative_distance_m / 1000.0, 4),
                ))
                prev_gpxpy_point = pt

    return points


def _validate_points(points: list[GPXPoint]) -> None:
    """Validate extracted track points."""
    if len(points) < 10:
        raise GPXParseError(
            f"Zu wenige Track-Points: {len(points)} (Minimum: 10)"
        )

    for i, pt in enumerate(points):
        if not (-90 <= pt.lat <= 90):
            raise GPXParseError(
                f"Ungueltiger Breitengrad bei Punkt {i}: {pt.lat}"
            )
        if not (-180 <= pt.lon <= 180):
            raise GPXParseError(
                f"Ungueltiger Laengengrad bei Punkt {i}: {pt.lon}"
            )
        if pt.elevation_m is None:
            raise GPXParseError(
                f"Fehlende Elevation bei Punkt {i} (lat={pt.lat}, lon={pt.lon})"
            )


def _compute_elevation_gain(
    points: list[GPXPoint],
    threshold_m: float,
) -> tuple[float, float]:
    """Threshold-based elevation gain calculation (like Strava/Garmin).

    Only counts elevation changes >= threshold from the last counted point.
    Eliminates GPS noise that would otherwise inflate totals by up to 115%.

    Returns: (total_ascent_m, total_descent_m)
    """
    if not points or points[0].elevation_m is None:
        return 0.0, 0.0

    ascent = 0.0
    descent = 0.0
    last_elevation = points[0].elevation_m

    for point in points[1:]:
        if point.elevation_m is None:
            continue
        delta = point.elevation_m - last_elevation
        if threshold_m == 0.0 or abs(delta) >= threshold_m:
            if delta > 0:
                ascent += delta
            elif delta < 0:
                descent += abs(delta)
            last_elevation = point.elevation_m

    return round(ascent, 1), round(descent, 1)
