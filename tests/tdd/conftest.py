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


# Issue #638: Clean throttle files for test users before each test run.
# TripAlertService throttle files persist between runs; tdd-638-* users
# are synthetic test users whose throttle must reset each test invocation.
_TDD_638_USERS = ["tdd-638-ac1", "tdd-638-ac2", "tdd-638-ac3", "tdd-638-ac4",
                  "tdd-638-ac5", "tdd-638-userA", "tdd-638-userB",
                  "tdd-638-mixed", "tdd-638-f001", "tdd-638-legacy",
                  "tdd-638-alloff"]


@pytest.fixture(autouse=True)
def _clear_tdd_638_throttle():
    """Auto-reset alert throttle for synthetic #638 test users (runs before each test)."""
    data_root = Path(__file__).resolve().parents[2] / "data" / "users"
    for uid in _TDD_638_USERS:
        throttle = data_root / uid / "alert_throttle.json"
        if throttle.exists():
            throttle.unlink(missing_ok=True)
    yield
