"""
Tests for GPX Parser & Validation (Feature 1.2).

All tests use REAL GPX files from Mallorca GR221 (Komoot export).
NO MOCKS! Tests must FAIL in TDD RED phase (src.core.gpx_parser doesn't exist yet).

Spec: docs/specs/modules/gpx_parser.md
"""
from pathlib import Path

import pytest

from core.gpx_parser import GPXParseError, parse_gpx

# Real GPX test files (Mallorca GR221, Komoot export)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

GPX_TAG1 = DATA_DIR / "2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx"
GPX_TAG2 = DATA_DIR / "2026-01-17_2753216748_Tag 2_ von Deià nach Sóller.gpx"
GPX_TAG3 = DATA_DIR / "2026-01-17_2753225520_Tag 3_ von Sóller nach Tossals Verds.gpx"
GPX_TAG4 = DATA_DIR / "2026-01-17_2753228656_Tag 4_ von Tossals Verds nach Lluc.gpx"

ALL_GPX = [GPX_TAG1, GPX_TAG2, GPX_TAG3, GPX_TAG4]


# --- Test 1: Tag 1 basic parsing ---

class TestParseGpxBasic:
    """GIVEN Tag 1 GPX WHEN parse_gpx THEN correct point count, name, distance."""

    def test_tag1_point_count(self):
        track = parse_gpx(GPX_TAG1)
        assert len(track.points) == 458

    def test_tag1_name(self):
        track = parse_gpx(GPX_TAG1)
        assert track.name == "Tag 1: von Valldemossa nach Deià"

    def test_tag1_distance_positive(self):
        track = parse_gpx(GPX_TAG1)
        assert track.total_distance_km > 0


# --- Test 2: Tag 3 with waypoint ---

class TestParseGpxWaypoints:
    """GIVEN Tag 3 GPX WHEN parse_gpx THEN correct points + waypoint extracted."""

    def test_tag3_point_count(self):
        track = parse_gpx(GPX_TAG3)
        assert len(track.points) == 811

    def test_tag3_waypoint_extracted(self):
        track = parse_gpx(GPX_TAG3)
        assert len(track.waypoints) == 1

    def test_tag3_waypoint_name(self):
        track = parse_gpx(GPX_TAG3)
        assert track.waypoints[0].name == "Tossals Verds"


# --- Test 3: All 4 files parse successfully ---

class TestParseAllFiles:
    """GIVEN alle 4 GPX-Dateien WHEN parse_gpx THEN alle erfolgreich mit plausiblen Werten."""

    @pytest.mark.parametrize("gpx_file", ALL_GPX, ids=lambda p: p.stem.split("_")[-1])
    def test_parses_successfully(self, gpx_file):
        track = parse_gpx(gpx_file)
        assert len(track.points) > 10
        assert track.total_distance_km > 0
        assert track.total_ascent_m > 0
        assert track.total_descent_m > 0


# --- Test 4: Cumulative distance consistency ---

class TestCumulativeDistance:
    """GIVEN Tag 1 GPX WHEN parse_gpx THEN last point cumulative distance == total_distance_km."""

    def test_last_point_distance_equals_total(self):
        track = parse_gpx(GPX_TAG1)
        last_point_distance = track.points[-1].distance_from_start_km
        assert abs(last_point_distance - track.total_distance_km) < 0.01


# --- Test 5: Elevation plausibility ---

class TestElevationPlausibility:
    """GIVEN Tag 1 GPX WHEN parse_gpx THEN ascent/descent ratio plausible."""

    def test_ascent_descent_ratio(self):
        """Fuer eine Punkt-zu-Punkt Wanderung: Aufstieg und Abstieg in aehnlicher Groessenordnung."""
        track = parse_gpx(GPX_TAG1)
        ratio = track.total_ascent_m / track.total_descent_m if track.total_descent_m > 0 else float("inf")
        assert 0.3 < ratio < 3.0


# --- Test 6-8: Validation errors ---

class TestValidationErrors:
    """GIVEN ungueltige GPX-Dateien WHEN parse_gpx THEN GPXParseError."""

    def test_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.gpx"
        empty_file.write_text("")
        with pytest.raises(GPXParseError):
            parse_gpx(empty_file)

    def test_invalid_xml(self, tmp_path):
        bad_file = tmp_path / "bad.gpx"
        bad_file.write_text("<not><valid><gpx>")
        with pytest.raises(GPXParseError):
            parse_gpx(bad_file)

    def test_too_few_points(self, tmp_path):
        """GPX mit nur 3 Track-Points -> GPXParseError (Minimum: 10)."""
        gpx_content = """<?xml version='1.0' encoding='UTF-8'?>
        <gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
          <trk><name>Too Short</name><trkseg>
            <trkpt lat="39.71" lon="2.62"><ele>400</ele></trkpt>
            <trkpt lat="39.72" lon="2.63"><ele>410</ele></trkpt>
            <trkpt lat="39.73" lon="2.64"><ele>420</ele></trkpt>
          </trkseg></trk>
        </gpx>"""
        short_file = tmp_path / "short.gpx"
        short_file.write_text(gpx_content)
        with pytest.raises(GPXParseError):
            parse_gpx(short_file)


# --- Test 9: Elevation threshold effect ---

class TestElevationThreshold:
    """GIVEN Tag 1 GPX WHEN Threshold=0 vs Threshold=5 THEN Threshold=0 liefert mehr Hoehenmeter."""

    def test_threshold_reduces_elevation_gain(self):
        track_default = parse_gpx(GPX_TAG1)  # Default threshold (5m)
        track_no_filter = parse_gpx(GPX_TAG1, elevation_threshold_m=0.0)

        # Ohne Filter muss mehr Aufstieg rauskommen (GPS-Rauschen wird mitgezaehlt)
        assert track_no_filter.total_ascent_m > track_default.total_ascent_m
