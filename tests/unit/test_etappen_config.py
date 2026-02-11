"""
Tests for Etappen-Config integration (Feature 1.6).

Tests the compute_full_segmentation() pipeline with REAL GPX files.
NO MOCKS!

Spec: docs/specs/modules/etappen_config.md
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models import EtappenConfig
from core.gpx_parser import parse_gpx
from web.pages.gpx_upload import compute_full_segmentation

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
GPX_TAG4 = DATA_DIR / "2026-01-17_2753228656_Tag 4_ von Tossals Verds nach Lluc.gpx"

START_TIME = datetime(2026, 1, 17, 8, 0, 0, tzinfo=timezone.utc)
DEFAULT_CONFIG = EtappenConfig()


# --- Test 1: Correct segment count ---

class TestSegmentCount:
    """GIVEN Tag 4 + Default-Config WHEN compute THEN mehrere Segmente."""

    def test_produces_segments(self):
        track = parse_gpx(GPX_TAG4)
        segments = compute_full_segmentation(track, DEFAULT_CONFIG, START_TIME)
        assert len(segments) >= 2
        assert len(segments) <= 10


# --- Test 2: At least one adjusted to waypoint ---

class TestWaypointAdjustment:
    """GIVEN Tag 4 WHEN compute THEN mind. 1 adjusted_to_waypoint."""

    def test_has_adjusted_segment(self):
        track = parse_gpx(GPX_TAG4)
        segments = compute_full_segmentation(track, DEFAULT_CONFIG, START_TIME)
        adjusted = [s for s in segments if s.adjusted_to_waypoint]
        assert len(adjusted) >= 1


# --- Test 3: Distance sum matches total ---

class TestDistanceConsistency:
    """GIVEN Segmente WHEN summiere THEN == track.total_distance_km."""

    def test_distance_sum(self):
        track = parse_gpx(GPX_TAG4)
        segments = compute_full_segmentation(track, DEFAULT_CONFIG, START_TIME)
        total = sum(s.distance_km for s in segments)
        assert abs(total - track.total_distance_km) < 0.1


# --- Test 4: Seamless times from start ---

class TestSeamlessTimes:
    """GIVEN Segmente WHEN pruefe Zeiten THEN lueckenlos ab Startzeit."""

    def test_times_seamless(self):
        track = parse_gpx(GPX_TAG4)
        segments = compute_full_segmentation(track, DEFAULT_CONFIG, START_TIME)
        assert segments[0].start_time == START_TIME
        for i in range(1, len(segments)):
            assert segments[i].start_time == segments[i - 1].end_time
