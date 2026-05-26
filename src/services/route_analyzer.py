"""Thin adapter: maps DetectedWaypoint results to Waypoint-Dict enrichment.

Issue #303 — keine eigene Detektionslogik. Greift NICHT in die
Segmentierungspipeline ein; arbeitet ausschließlich auf der Dict-Schicht
nach segments_to_trip(). Proximity-Matching nutzt dieselbe equirektanguläre
Näherung wie elevation_analysis._point_distance_approx.
"""
from __future__ import annotations

from app.models import DetectedWaypoint, GPXTrack, WaypointType
from core.elevation_analysis import _point_distance_approx

PROXIMITY_THRESHOLD_KM = 0.5  # identisch zu _match_gpx_waypoints

WAYPOINT_TYPE_TO_REASON = {
    WaypointType.GIPFEL: "detected_peak",
    WaypointType.TAL: "detected_valley",
    WaypointType.PASS: "detected_pass",
}


def enrich_waypoints_from_detected(
    waypoint_dicts: list[dict],
    detected: list[DetectedWaypoint],
    track: GPXTrack,
) -> list[dict]:
    """Reichere Waypoint-Dicts an, die nahe einem DetectedWaypoint liegen.

    Für jeden Dict mit einem DetectedWaypoint innerhalb PROXIMITY_THRESHOLD_KM:
      - origin = "algorithmic"
      - confirmed = False
      - suggestion_reason = WAYPOINT_TYPE_TO_REASON[detected.type]
    Kein Treffer → Dict unverändert. Gibt eine neue Liste zurück (keine
    In-place-Mutation).
    """
    result = []
    for wp in waypoint_dicts:
        wp_copy = dict(wp)
        for det in detected:
            dist = _point_distance_approx(det.point, wp_copy["lat"], wp_copy["lon"])
            if dist <= PROXIMITY_THRESHOLD_KM:
                wp_copy["origin"] = "algorithmic"
                wp_copy["confirmed"] = False
                wp_copy["suggestion_reason"] = WAYPOINT_TYPE_TO_REASON.get(
                    det.type, "detected_peak"
                )
                break
        result.append(wp_copy)
    return result
