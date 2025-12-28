"""
TDD Validation Framework.

Provides ground truth data from external sources for test-driven development.
"""

from validation.geosphere_validator import GeoSphereValidator
from validation.ground_truth import BergfexScraper, GroundTruthFetcher, SnowReport
from validation.resort_mapping import RESORT_COORDINATES, all_resort_slugs, get_resort

__all__ = [
    "BergfexScraper",
    "GeoSphereValidator",
    "GroundTruthFetcher",
    "SnowReport",
    "RESORT_COORDINATES",
    "all_resort_slugs",
    "get_resort",
]
