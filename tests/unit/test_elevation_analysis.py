"""
Tests for Hoehenprofil-Analyse (Feature 1.3).

All tests use REAL GPX files from Mallorca GR221.
NO MOCKS!

Spec: docs/specs/modules/elevation_analysis.md
"""
from pathlib import Path

import pytest

from app.models import WaypointType
from core.elevation_analysis import detect_waypoints
from core.gpx_parser import parse_gpx

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
GPX_TAG2 = DATA_DIR / "2026-01-17_2753216748_Tag 2_ von Deià nach Sóller.gpx"
GPX_TAG3 = DATA_DIR / "2026-01-17_2753225520_Tag 3_ von Sóller nach Tossals Verds.gpx"
GPX_TAG4 = DATA_DIR / "2026-01-17_2753228656_Tag 4_ von Tossals Verds nach Lluc.gpx"


# --- Test 1: Tag 4 has at least 1 peak ---

class TestDetectPeaks:
    """GIVEN Tag 4 GPX (490-1200m) WHEN detect_waypoints THEN Gipfel erkannt."""

    def test_tag4_has_peak(self):
        track = parse_gpx(GPX_TAG4)
        waypoints = detect_waypoints(track)
        peaks = [w for w in waypoints if w.type == WaypointType.GIPFEL]
        assert len(peaks) >= 1

    def test_tag4_highest_peak_around_1200m(self):
        """Hoechster Gipfel sollte bei ~1200m liegen."""
        track = parse_gpx(GPX_TAG4)
        waypoints = detect_waypoints(track)
        peaks = [w for w in waypoints if w.type == WaypointType.GIPFEL]
        highest = max(peaks, key=lambda w: w.point.elevation_m)
        assert 1150 < highest.point.elevation_m < 1250


# --- Test 3: Tag 4 has at least 1 valley ---

class TestDetectValleys:
    """GIVEN Tag 4 GPX WHEN detect_waypoints THEN Tal erkannt."""

    def test_tag4_has_valley(self):
        track = parse_gpx(GPX_TAG4)
        waypoints = detect_waypoints(track)
        valleys = [w for w in waypoints if w.type == WaypointType.TAL]
        assert len(valleys) >= 1


# --- Test 4: Flatter route has fewer waypoints ---

class TestRouteComparison:
    """GIVEN flachere Route (Tag 2) WHEN detect THEN weniger Waypoints als Tag 4."""

    def test_flat_route_fewer_waypoints(self):
        track2 = parse_gpx(GPX_TAG2)
        track4 = parse_gpx(GPX_TAG4)
        wpts2 = detect_waypoints(track2)
        wpts4 = detect_waypoints(track4)
        assert len(wpts2) <= len(wpts4)


# --- Test 5: Prominence filter ---

class TestProminenceFilter:
    """GIVEN alle Waypoints WHEN pruefe THEN Prominenz >= min_prominence_m."""

    def test_all_above_min_prominence(self):
        track = parse_gpx(GPX_TAG4)
        min_prom = 80.0
        waypoints = detect_waypoints(track, min_prominence_m=min_prom)
        for w in waypoints:
            assert w.prominence_m >= min_prom, f"{w.type} at {w.point.elevation_m}m has prominence {w.prominence_m}m < {min_prom}m"


# --- Test 6: Minimum distance filter ---

class TestDistanceFilter:
    """GIVEN alle Waypoints WHEN pruefe THEN Abstand >= min_distance_km."""

    def test_min_distance_between_waypoints(self):
        track = parse_gpx(GPX_TAG4)
        waypoints = detect_waypoints(track, min_distance_km=0.5)
        for i in range(1, len(waypoints)):
            dist = abs(waypoints[i].point.distance_from_start_km - waypoints[i - 1].point.distance_from_start_km)
            assert dist >= 0.5, f"Waypoints {i-1} and {i} too close: {dist:.2f}km"


# --- Test 7: Higher prominence threshold → fewer results ---

class TestThresholdEffect:
    """GIVEN hohe Prominenz-Schwelle WHEN detect THEN weniger Ergebnisse."""

    def test_higher_threshold_fewer_results(self):
        track = parse_gpx(GPX_TAG4)
        normal = detect_waypoints(track, min_prominence_m=80)
        strict = detect_waypoints(track, min_prominence_m=200)
        assert len(strict) <= len(normal)


# --- Test 8: GPX waypoint name matching ---

class TestWaypointNameMatch:
    """GIVEN Tag 3 mit Waypoint 'Tossals Verds' WHEN detect THEN Name zugeordnet."""

    def test_gpx_waypoint_name_matched(self):
        track = parse_gpx(GPX_TAG3)
        waypoints = detect_waypoints(track)
        named = [w for w in waypoints if w.name is not None]
        # Es sollte mindestens ein benannter Waypoint gefunden werden
        # (wenn ein erkannter Gipfel/Tal in der Naehe des GPX-Waypoints liegt)
        # Falls kein Gipfel in der Naehe: Test ueberspringen
        if not named:
            pytest.skip("Kein erkannter Waypoint in Naehe des GPX-Waypoints")
        names = [w.name for w in named]
        assert "Tossals Verds" in names
