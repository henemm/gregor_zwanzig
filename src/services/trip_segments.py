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
from utils.geo import haversine_km
from utils.timezone import tz_for_coords

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger("trip_segments")


def _parse_hhmm(value: str) -> Optional[time]:
    """Parse 'HH:MM' to a time object; returns None on malformed input."""
    try:
        return time.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _known_time_for_index(
    waypoints: List, idx: int, stage, default_start: time
) -> Optional[time]:
    """Massgebliche Startzeit eines Wegpunkts nach der #1004-Prioritaetskette
    (arrival_override > stage.start_time bei idx==0 > arrival_calculated >
    Default bei idx==0) — ``None`` wenn keine dieser Quellen greift."""
    wp = waypoints[idx]
    override_str = getattr(wp, "arrival_override", None)
    override = _parse_hhmm(override_str) if override_str else None
    if override is not None:
        return override
    if idx == 0 and stage.start_time:
        return stage.start_time
    calculated_str = wp.arrival_calculated
    calculated = _parse_hhmm(calculated_str) if calculated_str else None
    if calculated is not None:
        return calculated
    if idx == 0:
        return default_start
    return None


def _interpolate_missing_times(known_times: List[Optional[time]]) -> List[Optional[time]]:
    """Issue #1004/F001: lineare Interpolation fuer Wegpunkte ohne
    ``arrival_override``/``arrival_calculated`` zwischen zwei bekannten
    Zeitpunkten. Bei k aufeinanderfolgenden Unbekannten wird das Intervall
    gleichmaessig in k+1 Schritte geteilt (monotone Zeitfolge statt stiller
    Duplikat-Startzeit). Fehlt ein bekannter Zeitpunkt danach, bleibt die
    Luecke offen — der bestehende cumulative_time-Fallback greift dann."""
    result = list(known_times)
    n = len(result)
    i = 1
    while i < n:
        if result[i] is not None:
            i += 1
            continue
        gap_start = i
        while i < n and result[i] is None:
            i += 1
        gap_end = i
        prev_time = result[gap_start - 1]
        if gap_end < n and prev_time is not None:
            next_time = result[gap_end]
            prev_minutes = prev_time.hour * 60 + prev_time.minute
            next_minutes = next_time.hour * 60 + next_time.minute
            span = next_minutes - prev_minutes
            steps = gap_end - gap_start + 1
            # F002: kaufmaennische Rundung statt Python-Banker's-Rounding —
            # round(0.5) wuerde auf 0 abrunden und den interpolierten Punkt
            # auf die Vorgaengerzeit kollabieren lassen. Bei span < steps
            # (mehr Luecken als Minuten Spanne) sind Duplikate in Minuten-
            # aufloesung unvermeidbar; die betroffenen Segmente kollabieren
            # dann geloggt am end_dt<=start_dt-Guard (Grenzverhalten wie
            # die Mitternachts-Klemme in AC-5), nicht still.
            for offset, idx in enumerate(range(gap_start, gap_end), start=1):
                minutes = prev_minutes + math.floor(span * offset / steps + 0.5)
                result[idx] = time(minutes // 60, minutes % 60)
    return result


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

    # Issue #1004/F001: die massgebliche Startzeit pro Wegpunkt wird VORAB
    # fuer die ganze Etappe bestimmt und Luecken (weder arrival_override
    # noch arrival_calculated) linear zwischen den umgebenden bekannten
    # Zeitpunkten interpoliert — verhindert, dass ein unbekannter Zwischen-
    # Wegpunkt zwei Segmente auf denselben Zeitpunkt kollabieren laesst.
    known_times = [
        _known_time_for_index(waypoints, idx, stage, default_start)
        for idx in range(len(waypoints))
    ]
    wp_times = _interpolate_missing_times(known_times)

    cumulative_time = default_start
    cumulative_dist_km = 0.0

    for i in range(len(waypoints) - 1):
        wp1 = waypoints[i]
        wp2 = waypoints[i + 1]

        wp1_start = wp_times[i]
        if wp1_start is None:
            logger.warning(
                f"Kein arrival_calculated fuer {wp1.id}, verwende letzten bekannten Zeitpunkt"
            )
            wp1_start = cumulative_time

        cumulative_time = wp1_start

        wp2_start = wp_times[i + 1]
        if wp2_start is None:
            logger.warning(f"Kein arrival_calculated/override fuer {wp2.id}")
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
            # Issue #1004/AC-5: haeufigste Ursache ist die Mitternachts-Klemme
            # in core/naismith.py (_format_hhmm clamped auf 23:59) — bei sehr
            # spaeter stage.start_time kollabieren geklemmte Folgesegmente auf
            # denselben Zeitpunkt. Sie werden hier bewusst uebersprungen statt
            # die komplette Etappe stumm zum Verschwinden zu bringen.
            logger.warning(
                f"Segment {wp1.id}->{wp2.id} kollabiert (wp1_start={wp1_start}, "
                f"wp2_start={wp2_start}) — vermutlich Mitternachts-Klemme (23:59), "
                "wird uebersprungen"
            )
            continue

        duration_hours = (end_dt - start_dt).total_seconds() / 3600

        elev1 = wp1.elevation_m if wp1.elevation_m else 0
        elev2 = wp2.elevation_m if wp2.elevation_m else 0
        elev_diff = elev2 - elev1
        dist_km = haversine_km(wp1.lat, wp1.lon, wp2.lat, wp2.lon)

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
