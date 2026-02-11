"""
Hybrid-Segmentierung (Feature 1.5).

Post-Processing: Verschiebt Zeit-basierte Segment-Grenzen
an erkannte Gipfel/Taeler, wenn diese nahe genug liegen.

Spec: docs/specs/modules/hybrid_segmentation.md
"""
from __future__ import annotations

from datetime import timedelta

from app.models import (
    DetectedWaypoint,
    EtappenConfig,
    GPXPoint,
    GPXTrack,
    TripSegment,
    WaypointType,
)
from core.segment_builder import compute_hiking_time

_PRIORITY = {WaypointType.GIPFEL: 0, WaypointType.PASS: 1, WaypointType.TAL: 2}


def optimize_segments(
    segments: list[TripSegment],
    waypoints: list[DetectedWaypoint],
    track: GPXTrack,
    config: EtappenConfig,
    proximity_minutes: float = 20.0,
    min_duration_hours: float = 1.5,
    max_duration_hours: float = 2.5,
) -> list[TripSegment]:
    """Shift segment boundaries to nearby waypoints if duration constraints allow.

    For each internal segment boundary, looks for detected waypoints
    within ±proximity_minutes hiking time. If found, shifts the boundary
    to the waypoint location, provided both adjacent segments stay within
    [min_duration_hours, max_duration_hours] (last segment may be shorter).

    Args:
        segments: Time-based segments from build_segments().
        waypoints: Detected peaks/valleys from detect_waypoints().
        track: Full GPX track with all points.
        config: Hiking speed configuration.
        proximity_minutes: Max distance in hiking minutes to search for waypoints.
        min_duration_hours: Minimum allowed segment duration after shift.
        max_duration_hours: Maximum allowed segment duration after shift.

    Returns:
        List of TripSegment with possibly shifted boundaries.
    """
    if not waypoints or len(segments) <= 1:
        return _copy_segments(segments)

    points = track.points
    proximity_km = (proximity_minutes / 60.0) * config.speed_flat_kmh

    # Find boundary point indices in track
    boundaries = _find_boundaries(segments, points)

    used_waypoints: set[int] = set()
    adjusted_map: dict[int, DetectedWaypoint] = {}

    for b in range(1, len(boundaries) - 1):
        boundary_dist = points[boundaries[b]].distance_from_start_km

        # Find candidate waypoints within proximity
        candidates = []
        for wi, wp in enumerate(waypoints):
            if wi in used_waypoints:
                continue
            if abs(wp.point.distance_from_start_km - boundary_dist) <= proximity_km:
                candidates.append((wi, wp))

        if not candidates:
            continue

        # Sort: GIPFEL > PASS > TAL, then closest to boundary
        candidates.sort(key=lambda x: (
            _PRIORITY.get(x[1].type, 99),
            abs(x[1].point.distance_from_start_km - boundary_dist),
        ))

        wi, best = candidates[0]
        new_idx = _find_point_index(points, best.point)
        if new_idx == boundaries[b]:
            continue

        # Check duration constraints for affected segments
        curr_dur = _segment_duration(points, boundaries[b - 1], new_idx, config)
        next_dur = _segment_duration(points, new_idx, boundaries[b + 1], config)

        if not (min_duration_hours <= curr_dur <= max_duration_hours):
            continue

        is_last_seg = (b + 1 == len(boundaries) - 1)
        if not is_last_seg and not (min_duration_hours <= next_dur <= max_duration_hours):
            continue

        # Accept shift
        boundaries[b] = new_idx
        used_waypoints.add(wi)
        adjusted_map[b] = best

    return _rebuild(points, boundaries, adjusted_map, config, segments[0].start_time)


def _copy_segments(segments: list[TripSegment]) -> list[TripSegment]:
    """Return segments with same data, no adjustment flags."""
    return [
        TripSegment(
            segment_id=s.segment_id,
            start_point=s.start_point,
            end_point=s.end_point,
            start_time=s.start_time,
            end_time=s.end_time,
            duration_hours=s.duration_hours,
            distance_km=s.distance_km,
            ascent_m=s.ascent_m,
            descent_m=s.descent_m,
            adjusted_to_waypoint=False,
            waypoint=None,
        )
        for s in segments
    ]


def _find_boundaries(
    segments: list[TripSegment], points: list[GPXPoint],
) -> list[int]:
    """Find track point indices for segment start/end boundaries."""
    indices = [_find_point_index(points, segments[0].start_point)]
    for seg in segments:
        indices.append(_find_point_index(points, seg.end_point))
    return indices


def _find_point_index(points: list[GPXPoint], target: GPXPoint) -> int:
    """Find index of target GPXPoint in points list by distance."""
    target_dist = target.distance_from_start_km
    best_idx = 0
    best_diff = abs(points[0].distance_from_start_km - target_dist)
    for i, p in enumerate(points):
        diff = abs(p.distance_from_start_km - target_dist)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    return best_idx


def _segment_duration(
    points: list[GPXPoint], start_idx: int, end_idx: int, config: EtappenConfig,
) -> float:
    """Compute hiking time for a sub-track between two point indices."""
    dist = 0.0
    ascent = 0.0
    descent = 0.0
    for i in range(start_idx + 1, end_idx + 1):
        prev = points[i - 1]
        curr = points[i]
        dist += curr.distance_from_start_km - prev.distance_from_start_km
        if prev.elevation_m is not None and curr.elevation_m is not None:
            delta = curr.elevation_m - prev.elevation_m
            if delta > 0:
                ascent += delta
            else:
                descent += abs(delta)
    return compute_hiking_time(dist, ascent, descent, config)


def _rebuild(
    points: list[GPXPoint],
    boundaries: list[int],
    adjusted_map: dict[int, DetectedWaypoint],
    config: EtappenConfig,
    start_time,
) -> list[TripSegment]:
    """Build TripSegment list from boundary indices."""
    segments = []
    cumulative_h = 0.0

    for k in range(len(boundaries) - 1):
        s_idx = boundaries[k]
        e_idx = boundaries[k + 1]

        dist = 0.0
        ascent = 0.0
        descent = 0.0
        for i in range(s_idx + 1, e_idx + 1):
            prev = points[i - 1]
            curr = points[i]
            dist += curr.distance_from_start_km - prev.distance_from_start_km
            if prev.elevation_m is not None and curr.elevation_m is not None:
                delta = curr.elevation_m - prev.elevation_m
                if delta > 0:
                    ascent += delta
                else:
                    descent += abs(delta)

        duration = compute_hiking_time(dist, ascent, descent, config)
        t_start = start_time + timedelta(hours=cumulative_h)
        cumulative_h += duration
        t_end = start_time + timedelta(hours=cumulative_h)

        b_key = k + 1  # boundary index after this segment
        is_adj = b_key in adjusted_map
        wp = adjusted_map.get(b_key)

        segments.append(TripSegment(
            segment_id=k + 1,
            start_point=points[s_idx],
            end_point=points[e_idx],
            start_time=t_start,
            end_time=t_end,
            duration_hours=round(duration, 3),
            distance_km=round(dist, 3),
            ascent_m=round(ascent, 1),
            descent_m=round(descent, 1),
            adjusted_to_waypoint=is_adj,
            waypoint=wp if is_adj else None,
        ))

    return segments
