"""
TDD Test Fixtures.

Provides ground truth fetcher for TDD tests.
"""

import sys
from pathlib import Path

import pytest

# .claude/hooks muss auf sys.path liegen, damit Hooks die importieren
# (z.B. staging_gate, prod_selftest) `import _e2e_paths` auflösen können —
# unabhängig von der Reihenfolge, in der Testdateien geladen werden.
_HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from validation import GroundTruthFetcher


@pytest.fixture(scope="session")
def ground_truth() -> GroundTruthFetcher:
    """Ground truth fetcher for TDD tests (cached per session)."""
    return GroundTruthFetcher()
