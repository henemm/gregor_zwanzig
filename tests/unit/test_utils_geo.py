"""Unit tests for utils.geo — degrees_to_compass + haversine_km.

Issue #1027: These helpers are the single source of truth; tests document the
language/none_label variants so every caller keeps its previous behaviour.
"""
from __future__ import annotations

import pytest

from utils.geo import degrees_to_compass, haversine_km


class TestDegreesToCompass:
    """8-point compass conversion with language and none_label support."""

    @pytest.mark.parametrize(
        "degrees,expected",
        [
            (0, "N"),
            (45, "NE"),
            (90, "E"),
            (135, "SE"),
            (180, "S"),
            (225, "SW"),
            (270, "W"),
            (315, "NW"),
            (360, "N"),
        ],
    )
    def test_english_default(self, degrees, expected):
        assert degrees_to_compass(degrees) == expected

    @pytest.mark.parametrize(
        "degrees,expected",
        [
            (0, "N"),
            (45, "NO"),
            (90, "O"),
            (135, "SO"),
            (180, "S"),
            (225, "SW"),
            (270, "W"),
            (315, "NW"),
            (360, "N"),
        ],
    )
    def test_german_labels(self, degrees, expected):
        assert degrees_to_compass(degrees, language="de") == expected

    def test_english_none_returns_empty_by_default(self):
        assert degrees_to_compass(None) == ""

    def test_english_none_with_custom_label(self):
        assert degrees_to_compass(None, none_label="-") == "-"

    def test_german_none_with_dash(self):
        assert degrees_to_compass(None, language="de", none_label="-") == "-"


class TestHaversineKm:
    """Great-circle distance in kilometres."""

    def test_zero_distance(self):
        assert haversine_km(47.0, 11.0, 47.0, 11.0) == 0.0

    def test_known_distance_roughly(self):
        # Innsbruck ~ Bregenz is roughly 130 km
        dist = haversine_km(47.2682, 11.3923, 47.5034, 9.7448)
        assert 120 < dist < 140
