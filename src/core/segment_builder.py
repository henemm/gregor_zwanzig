"""
Zeit-Segment-Bildung (Feature 1.4).

Teilt GPX-Tracks in ~2h-Wanderabschnitte basierend auf
Gehgeschwindigkeit und Steig-/Abstiegsgeschwindigkeit.
Nutzt angepasste Naismith's Rule fuer Gehzeit-Berechnung.

Spec: docs/specs/modules/segment_builder.md
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models import EtappenConfig, GPXPoint, GPXTrack, TripSegment


def compute_hiking_time(
    distance_km: float,
    ascent_m: float,
    descent_m: float,
    config: EtappenConfig,
) -> float:
    """Compute hiking time in hours using adapted Naismith's Rule.

    time = distance / speed_flat
         + ascent / speed_ascent
         + descent / speed_descent

    Args:
        distance_km: Horizontal distance in km.
        ascent_m: Total ascent in meters.
        descent_m: Total descent in meters.
        config: Hiking speed configuration.

    Returns:
        Estimated hiking time in hours.
    """
    time_h = 0.0
    if config.speed_flat_kmh > 0:
        time_h += distance_km / config.speed_flat_kmh
    if config.speed_ascent_mh > 0 and ascent_m > 0:
        time_h += ascent_m / config.speed_ascent_mh
    if config.speed_descent_mh > 0 and descent_m > 0:
        time_h += descent_m / config.speed_descent_mh
    return time_h


def build_segments(
    track: GPXTrack,
    config: EtappenConfig,
    start_time: datetime,
) -> list[TripSegment]:
    """Split GPX track into ~2h hiking segments.

    Iterates over consecutive point pairs, accumulates hiking time.
    When target_duration is reached, creates a segment boundary.
    Last segment may be shorter than target.

    Args:
        track: Parsed GPX track from Feature 1.2.
        config: Hiking speed and target duration configuration.
        start_time: Start time of the hike (UTC).

    Returns:
        List of TripSegment objects with seamless time windows.
    """
    if len(track.points) < 2:
        return []

    segments: list[TripSegment] = []
    points = track.points

    # Current segment tracking
    seg_start_idx = 0
    seg_time_h = 0.0
    seg_distance_km = 0.0
    seg_ascent_m = 0.0
    seg_descent_m = 0.0
    cumulative_time_h = 0.0

    for i in range(1, len(points)):
        prev = points[i - 1]
        curr = points[i]

        # Distance delta between consecutive points
        dist_delta = curr.distance_from_start_km - prev.distance_from_start_km

        # Elevation delta
        ascent_delta = 0.0
        descent_delta = 0.0
        if prev.elevation_m is not None and curr.elevation_m is not None:
            ele_delta = curr.elevation_m - prev.elevation_m
            if ele_delta > 0:
                ascent_delta = ele_delta
            else:
                descent_delta = abs(ele_delta)

        # Time for this point pair
        pair_time = compute_hiking_time(dist_delta, ascent_delta, descent_delta, config)

        seg_time_h += pair_time
        seg_distance_km += dist_delta
        seg_ascent_m += ascent_delta
        seg_descent_m += descent_delta

        # Check if segment target reached (or last point)
        is_last_point = i == len(points) - 1
        target_reached = seg_time_h >= config.target_duration_hours

        if target_reached or is_last_point:
            seg_start_time = start_time + timedelta(hours=cumulative_time_h)
            cumulative_time_h += seg_time_h
            seg_end_time = start_time + timedelta(hours=cumulative_time_h)

            segments.append(TripSegment(
                segment_id=len(segments) + 1,
                start_point=points[seg_start_idx],
                end_point=curr,
                start_time=seg_start_time,
                end_time=seg_end_time,
                duration_hours=round(seg_time_h, 3),
                distance_km=round(seg_distance_km, 3),
                ascent_m=round(seg_ascent_m, 1),
                descent_m=round(seg_descent_m, 1),
            ))

            # Reset for next segment
            seg_start_idx = i
            seg_time_h = 0.0
            seg_distance_km = 0.0
            seg_ascent_m = 0.0
            seg_descent_m = 0.0

    return segments
