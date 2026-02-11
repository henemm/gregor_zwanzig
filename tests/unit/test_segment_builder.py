"""
Tests for Zeit-Segment-Bildung (Feature 1.4).

All tests use REAL GPX files from Mallorca GR221 (Komoot export).
NO MOCKS! Tests must FAIL in TDD RED phase (src.core.segment_builder doesn't exist yet).

Spec: docs/specs/modules/segment_builder.md
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models import EtappenConfig
from core.gpx_parser import parse_gpx
from core.segment_builder import build_segments, compute_hiking_time

# Real GPX test files
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
GPX_TAG1 = DATA_DIR / "2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx"
GPX_TAG3 = DATA_DIR / "2026-01-17_2753225520_Tag 3_ von Sóller nach Tossals Verds.gpx"

START_TIME = datetime(2026, 1, 17, 8, 0, 0, tzinfo=timezone.utc)
DEFAULT_CONFIG = EtappenConfig()


# --- Tests 1-3: compute_hiking_time ---

class TestComputeHikingTime:
    """Naismith's Rule: time = dist/speed + ascent/ascent_speed + descent/descent_speed."""

    def test_flat_terrain(self):
        """GIVEN 4km flach WHEN compute THEN 1.0h."""
        t = compute_hiking_time(distance_km=4.0, ascent_m=0, descent_m=0, config=DEFAULT_CONFIG)
        assert abs(t - 1.0) < 0.01

    def test_pure_ascent(self):
        """GIVEN 0km + 300Hm Aufstieg WHEN compute THEN 1.0h."""
        t = compute_hiking_time(distance_km=0, ascent_m=300, descent_m=0, config=DEFAULT_CONFIG)
        assert abs(t - 1.0) < 0.01

    def test_combined(self):
        """GIVEN 4km + 300Hm auf + 500Hm ab WHEN compute THEN 3.0h."""
        t = compute_hiking_time(distance_km=4.0, ascent_m=300, descent_m=500, config=DEFAULT_CONFIG)
        assert abs(t - 3.0) < 0.01


# --- Tests 4-5: build_segments with real data ---

class TestBuildSegmentsRealData:
    """GIVEN echte GPX-Dateien WHEN build_segments THEN plausible Segment-Anzahl."""

    def test_tag1_segment_count(self):
        """Tag 1: ~5.5h Gehzeit → 2-4 Segmente."""
        track = parse_gpx(GPX_TAG1)
        segments = build_segments(track, DEFAULT_CONFIG, START_TIME)
        assert 2 <= len(segments) <= 4

    def test_tag3_more_segments(self):
        """Tag 3 (laengste Etappe, 20km): > 4 Segmente."""
        track = parse_gpx(GPX_TAG3)
        segments = build_segments(track, DEFAULT_CONFIG, START_TIME)
        assert len(segments) > 4


# --- Test 6: Distance consistency ---

class TestSegmentConsistency:
    """Segment-Distanzen summieren sich zur Gesamt-Distanz."""

    def test_distance_sum_equals_total(self):
        track = parse_gpx(GPX_TAG1)
        segments = build_segments(track, DEFAULT_CONFIG, START_TIME)
        total = sum(s.distance_km for s in segments)
        assert abs(total - track.total_distance_km) < 0.1


# --- Test 7: Seamless times ---

class TestSeamlessTimes:
    """Segmente sind zeitlich lueckenlos."""

    def test_no_time_gaps(self):
        track = parse_gpx(GPX_TAG1)
        segments = build_segments(track, DEFAULT_CONFIG, START_TIME)
        assert segments[0].start_time == START_TIME
        for i in range(1, len(segments)):
            assert segments[i].start_time == segments[i - 1].end_time


# --- Test 8: Short route → 1 segment ---

class TestShortRoute:
    """GIVEN kurze Route (<2h) WHEN build_segments THEN 1 Segment."""

    def test_single_segment(self):
        """Simuliere kurze Route mit hoher Geschwindigkeit."""
        track = parse_gpx(GPX_TAG1)
        fast_config = EtappenConfig(
            speed_flat_kmh=20.0,
            speed_ascent_mh=1500.0,
            speed_descent_mh=2500.0,
        )
        segments = build_segments(track, fast_config, START_TIME)
        assert len(segments) == 1


# --- Test 9: Slower config → more segments ---

class TestConfigEffect:
    """GIVEN langsame Config WHEN build_segments THEN mehr Segmente."""

    def test_slow_config_more_segments(self):
        track = parse_gpx(GPX_TAG1)
        default_segments = build_segments(track, DEFAULT_CONFIG, START_TIME)
        slow_config = EtappenConfig(speed_flat_kmh=2.0, speed_ascent_mh=150.0, speed_descent_mh=250.0)
        slow_segments = build_segments(track, slow_config, START_TIME)
        assert len(slow_segments) > len(default_segments)
