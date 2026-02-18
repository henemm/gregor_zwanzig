"""
F7: Wind-Exposition (Grat-Erkennung)

Detects exposed ridge sections from GPX elevation profile and
from segment elevation data. Exposed sections have lower wind
thresholds for risk assessment.

SPEC: docs/specs/modules/wind_exposition.md v1.0
"""

import logging
from typing import Optional

from app.models import ExposedSection, GPXTrack, TripSegment, WaypointType
from core.elevation_analysis import detect_waypoints

logger = logging.getLogger(__name__)


class WindExpositionService:
    """Detects exposed ridge sections from GPX elevation profile."""

    def detect_exposed_sections(
        self,
        track: GPXTrack,
        radius_km: float = 0.3,
        min_elevation_m: float = 2000.0,
    ) -> list[ExposedSection]:
        """Find exposed sections near detected peaks/passes.

        Algorithm:
        1. Run detect_waypoints() on the track
        2. For each GIPFEL/PASS waypoint above min_elevation_m:
           - Create ExposedSection from (waypoint_km - radius_km) to (waypoint_km + radius_km)
        3. Merge overlapping sections
        4. Return sorted by start_km
        """
        waypoints = detect_waypoints(track)

        sections: list[ExposedSection] = []
        for wp in waypoints:
            if wp.type not in (WaypointType.GIPFEL, WaypointType.PASS):
                continue
            elev = wp.point.elevation_m or 0.0
            if elev < min_elevation_m:
                continue

            wp_km = wp.point.distance_from_start_km
            expo_type = "GRAT" if wp.type == WaypointType.GIPFEL else "PASS"
            sections.append(ExposedSection(
                start_km=max(0.0, wp_km - radius_km),
                end_km=wp_km + radius_km,
                max_elevation_m=elev,
                exposition_type=expo_type,
            ))

        return self._merge_sections(sections)

    def detect_exposed_from_segments(
        self,
        segments: list[TripSegment],
        min_elevation_m: float = 2000.0,
    ) -> list[ExposedSection]:
        """Detect exposed sections from segment elevation data.

        Simpler approach for when no GPXTrack is available:
        if max(start_elev, end_elev) >= min_elevation_m, the segment
        is treated as exposed.
        """
        sections: list[ExposedSection] = []
        for seg in segments:
            start_elev = seg.start_point.elevation_m or 0.0
            end_elev = seg.end_point.elevation_m or 0.0
            max_elev = max(start_elev, end_elev)
            if max_elev < min_elevation_m:
                continue

            start_km = seg.start_point.distance_from_start_km
            end_km = seg.end_point.distance_from_start_km
            if end_km <= start_km:
                end_km = start_km + seg.distance_km

            sections.append(ExposedSection(
                start_km=start_km,
                end_km=end_km,
                max_elevation_m=max_elev,
                exposition_type="GRAT",
            ))

        return self._merge_sections(sections)

    @staticmethod
    def _merge_sections(sections: list[ExposedSection]) -> list[ExposedSection]:
        """Merge overlapping sections, sorted by start_km."""
        if not sections:
            return []

        sorted_sections = sorted(sections, key=lambda s: s.start_km)
        merged: list[ExposedSection] = [sorted_sections[0]]

        for current in sorted_sections[1:]:
            prev = merged[-1]
            if current.start_km <= prev.end_km:
                # Overlap: merge
                merged[-1] = ExposedSection(
                    start_km=prev.start_km,
                    end_km=max(prev.end_km, current.end_km),
                    max_elevation_m=max(prev.max_elevation_m, current.max_elevation_m),
                    exposition_type=prev.exposition_type,
                )
            else:
                merged.append(current)

        return merged
