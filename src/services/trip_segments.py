"""
Shared segment helper — extracts trip waypoints into TripSegment DTOs.

Issue #822: SSoT for segment conversion, shared between briefing
(TripReportSchedulerService) and radar alert (TripAlertService).

Extracted 1:1 from TripReportSchedulerService._convert_trip_to_segments
so that the briefing behaviour is bit-identical after the refactor.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, time, timedelta, timezone
from typing import TYPE_CHECKING, List, Optional

from app.models import GPXPoint, TripSegment
from utils.timezone import tz_for_coords

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger("trip_segments")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_hhmm(value: str) -> Optional[time]:
    """Parse 'HH:MM' to a time object; returns None on malformed input."""
    try:
        return time.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def convert_trip_to_segments(trip: "Trip", target_date: date) -> List[TripSegment]:
    """Convert Trip waypoints to TripSegment DTOs for a given date.

    Extracted 1:1 from TripReportSchedulerService._convert_trip_to_segments.
    Briefing behaviour is bit-identical (AC-1 roundtrip guarantee).

    Returns an empty list when:
    - No stage matches target_date
    - Stage has fewer than 2 waypoints
    """
    stage = trip.get_stage_for_date(target_date)
    if stage is None:
        return []

    if len(stage.waypoints) < 2:
        logger.warning(f"Stage {stage.id} has less than 2 waypoints")
        return []

    # Self-Heal: if all arrival_calculated are None, compute via Naismith.
    if all(wp.arrival_calculated is None for wp in stage.waypoints):
        from core.naismith import compute_stage_arrivals
        stage = compute_stage_arrivals(stage, trip.activity)

    segments: List[TripSegment] = []
    waypoints = stage.waypoints
    default_start = stage.start_time if stage.start_time else time(8, 0)
    cumulative_time = default_start
    cumulative_dist_km = 0.0

    for i in range(len(waypoints) - 1):
        wp1 = waypoints[i]
        wp2 = waypoints[i + 1]

        wp1_override_str = getattr(wp1, "arrival_override", None)
        wp1_override = _parse_hhmm(wp1_override_str) if wp1_override_str else None
        wp1_calculated_str = wp1.arrival_calculated
        wp1_calculated = _parse_hhmm(wp1_calculated_str) if wp1_calculated_str else None

        if wp1.time_window is not None:
            wp1_start = wp1.time_window.start
        elif wp1_override is not None:
            wp1_start = wp1_override
        elif i == 0 and stage.start_time:
            wp1_start = stage.start_time
        elif wp1_calculated is not None:
            wp1_start = wp1_calculated
        elif i == 0:
            wp1_start = default_start
        else:
            logger.warning(
                f"Kein arrival_calculated/time_window fuer {wp1.id}"
            )
            wp1_start = cumulative_time

        cumulative_time = wp1_start

        wp2_arrival_str = (
            getattr(wp2, "arrival_override", None) or wp2.arrival_calculated
        )
        wp2_arrival = _parse_hhmm(wp2_arrival_str) if wp2_arrival_str else None

        if wp2.time_window is not None:
            wp2_start = wp2.time_window.start
        elif wp2_arrival is not None:
            wp2_start = wp2_arrival
        else:
            logger.warning(
                f"Kein arrival_calculated/time_window fuer {wp2.id}"
            )
            wp2_start = wp1_start

        seg_tz = tz_for_coords(wp1.lat, wp1.lon)
        start_dt = (
            datetime.combine(target_date, wp1_start)
            .replace(tzinfo=seg_tz)
            .astimezone(timezone.utc)
        )
        end_dt = (
            datetime.combine(target_date, wp2_start)
            .replace(tzinfo=seg_tz)
            .astimezone(timezone.utc)
        )

        if end_dt <= start_dt:
            logger.warning(
                f"Invalid time window: {wp1.time_window} -> {wp2.time_window}"
            )
            continue

        duration_hours = (end_dt - start_dt).total_seconds() / 3600

        elev1 = wp1.elevation_m if wp1.elevation_m else 0
        elev2 = wp2.elevation_m if wp2.elevation_m else 0
        elev_diff = elev2 - elev1
        dist_km = _haversine_km(wp1.lat, wp1.lon, wp2.lat, wp2.lon)

        segment = TripSegment(
            segment_id=i + 1,
            start_point=GPXPoint(
                lat=wp1.lat,
                lon=wp1.lon,
                elevation_m=float(elev1),
                distance_from_start_km=cumulative_dist_km,
            ),
            end_point=GPXPoint(
                lat=wp2.lat,
                lon=wp2.lon,
                elevation_m=float(elev2),
                distance_from_start_km=cumulative_dist_km + round(dist_km, 1),
            ),
            start_time=start_dt,
            end_time=end_dt,
            duration_hours=duration_hours,
            distance_km=round(dist_km, 1),
            ascent_m=float(max(0, elev_diff)),
            descent_m=float(max(0, -elev_diff)),
        )
        cumulative_dist_km += round(dist_km, 1)
        segments.append(segment)

    # Destination segment (Zielort)
    if segments and waypoints:
        last_wp = waypoints[-1]
        arrival_time = segments[-1].end_time
        elev = float(last_wp.elevation_m) if last_wp.elevation_m else 0.0

        destination_segment = TripSegment(
            segment_id="Ziel",
            start_point=GPXPoint(
                lat=last_wp.lat,
                lon=last_wp.lon,
                elevation_m=elev,
                distance_from_start_km=cumulative_dist_km,
            ),
            end_point=GPXPoint(
                lat=last_wp.lat,
                lon=last_wp.lon,
                elevation_m=elev,
                distance_from_start_km=cumulative_dist_km,
            ),
            start_time=arrival_time,
            end_time=arrival_time + timedelta(hours=2),
            duration_hours=2.0,
            distance_km=0.0,
            ascent_m=0.0,
            descent_m=0.0,
        )
        segments.append(destination_segment)

    return segments
