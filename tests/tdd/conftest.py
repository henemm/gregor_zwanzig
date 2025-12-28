"""
TDD Test Fixtures.

Provides ground truth fetcher for TDD tests.
"""

import pytest

from validation import GroundTruthFetcher


@pytest.fixture(scope="session")
def ground_truth() -> GroundTruthFetcher:
    """Ground truth fetcher for TDD tests (cached per session)."""
    return GroundTruthFetcher()
