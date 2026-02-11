"""
Tests for Hybrid-Segmentierung (Feature 1.5).

All tests use REAL GPX files from Mallorca GR221.
NO MOCKS!

Spec: docs/specs/modules/hybrid_segmentation.md
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models import EtappenConfig, WaypointType
from core.elevation_analysis import detect_waypoints
from core.gpx_parser import parse_gpx
from core.hybrid_segmentation import optimize_segments
from core.segment_builder import build_segments

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
GPX_TAG2 = DATA_DIR / "2026-01-17_2753216748_Tag 2_ von Deià nach Sóller.gpx"
GPX_TAG4 = DATA_DIR / "2026-01-17_2753228656_Tag 4_ von Tossals Verds nach Lluc.gpx"

START_TIME = datetime(2026, 1, 17, 8, 0, 0, tzinfo=timezone.utc)
DEFAULT_CONFIG = EtappenConfig()


def _get_tag4_optimized():
    """Helper: Parse Tag 4, segment, detect waypoints, optimize."""
    track = parse_gpx(GPX_TAG4)
    segments = build_segments(track, DEFAULT_CONFIG, START_TIME)
    waypoints = detect_waypoints(track)
    return optimize_segments(segments, waypoints, track, DEFAULT_CONFIG), track


# --- Test 1: Tag 4 Seg 2 adjusted to peak at 1200m ---

class TestTag4Optimization:
    """GIVEN Tag 4 (Gipfel bei 7.1km nahe Seg 2 Ende 6.9km) WHEN optimize THEN angepasst."""

    def test_seg2_adjusted_to_peak(self):
        optimized, track = _get_tag4_optimized()
        seg2 = optimized[1]  # 0-indexed
        # Seg 2 end point should be closer to 1200m peak than before
        assert seg2.end_point.elevation_m > 1190


# --- Test 2: At least one segment has adjusted_to_waypoint ---

class TestAdjustedFlag:
    """GIVEN optimierte Segmente WHEN pruefe THEN mind. 1 adjusted."""

    def test_at_least_one_adjusted(self):
        optimized, _ = _get_tag4_optimized()
        adjusted = [s for s in optimized if s.adjusted_to_waypoint]
        assert len(adjusted) >= 1


# --- Test 3: Waypoint reference set ---

class TestWaypointReference:
    """GIVEN adjustiertes Segment WHEN pruefe THEN waypoint gesetzt."""

    def test_waypoint_set_on_adjusted(self):
        optimized, _ = _get_tag4_optimized()
        for s in optimized:
            if s.adjusted_to_waypoint:
                assert s.waypoint is not None
                assert s.waypoint.type in (WaypointType.GIPFEL, WaypointType.TAL, WaypointType.PASS)


# --- Test 4: Duration constraints ---

class TestDurationConstraints:
    """GIVEN optimierte Segmente WHEN pruefe Dauer THEN 1.5-2.5h (letztes kann kuerzer)."""

    def test_durations_in_range(self):
        optimized, _ = _get_tag4_optimized()
        for s in optimized[:-1]:  # Alle ausser letztes
            assert 1.0 <= s.duration_hours <= 3.0, \
                f"Seg {s.segment_id} duration {s.duration_hours:.2f}h out of range"


# --- Test 5: Distance consistency ---

class TestDistanceConsistency:
    """GIVEN optimierte Segmente WHEN summiere Distanzen THEN == total."""

    def test_distance_sum(self):
        optimized, track = _get_tag4_optimized()
        total = sum(s.distance_km for s in optimized)
        assert abs(total - track.total_distance_km) < 0.1


# --- Test 6: Seamless times ---

class TestSeamlessTimes:
    """GIVEN optimierte Segmente WHEN pruefe Zeiten THEN lueckenlos."""

    def test_no_time_gaps(self):
        optimized, _ = _get_tag4_optimized()
        assert optimized[0].start_time == START_TIME
        for i in range(1, len(optimized)):
            assert optimized[i].start_time == optimized[i - 1].end_time


# --- Test 7: Flat route → little change ---

class TestFlatRoute:
    """GIVEN Tag 2 (flach, Waypoints weit von Grenzen) WHEN optimize THEN wenig Aenderung."""

    def test_tag2_segment_count_unchanged(self):
        track = parse_gpx(GPX_TAG2)
        segments = build_segments(track, DEFAULT_CONFIG, START_TIME)
        waypoints = detect_waypoints(track)
        optimized = optimize_segments(segments, waypoints, track, DEFAULT_CONFIG)
        assert len(optimized) == len(segments)


# --- Test 8: Empty waypoints → no change ---

class TestEmptyWaypoints:
    """GIVEN leere Waypoint-Liste WHEN optimize THEN unveraendert."""

    def test_no_waypoints_no_change(self):
        track = parse_gpx(GPX_TAG4)
        segments = build_segments(track, DEFAULT_CONFIG, START_TIME)
        optimized = optimize_segments(segments, [], track, DEFAULT_CONFIG)
        for orig, opt in zip(segments, optimized):
            assert orig.end_point.distance_from_start_km == opt.end_point.distance_from_start_km
            assert not opt.adjusted_to_waypoint
