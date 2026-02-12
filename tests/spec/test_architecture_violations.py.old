"""
Architecture Violation Detection Tests.

These tests enforce the Single Source of Truth architecture for weather metrics.
All weather calculations MUST go through WeatherMetricsService.

FORBIDDEN outside of src/services/weather_metrics.py:
- Direct sunny_hours calculations (cloud thresholds, sunshine_duration math)
- Direct cloud_status calculations (cloud_low_avg comparisons)
- Direct effective_cloud calculations
- Local get_weather_symbol functions

Run with: uv run pytest tests/spec/test_architecture_violations.py -v
"""

import re
from pathlib import Path

import pytest

# Files that ARE allowed to contain weather calculations
ALLOWED_FILES = {
    "src/services/weather_metrics.py",  # The Single Source of Truth
    "tests/spec/test_weather_metrics_spec.py",  # Tests for the service
    "tests/spec/test_architecture_violations.py",  # This file
}

# Directories to scan
SCAN_DIRS = ["src/"]

# Patterns that indicate architecture violations
VIOLATION_PATTERNS = [
    # Direct sunny hour calculations
    (
        r"cloud_pct\s*[<>=]+\s*\d+.*sunny|sunny.*cloud_pct\s*[<>=]+\s*\d+",
        "Direct sunny hour calculation using cloud_pct threshold",
    ),
    (
        r"sunshine_duration.*\s*/\s*\d+|sunshine_duration.*//\s*\d+",
        "Direct sunshine_duration division (should use WeatherMetricsService)",
    ),
    # Direct cloud status calculations (outside service)
    (
        r"cloud_low_avg\s*>\s*\d+.*CloudStatus|CloudStatus.*cloud_low_avg\s*>\s*\d+",
        "Direct cloud_low_avg comparison for CloudStatus",
    ),
    (
        r'["\'](ueber|ueber|above).*[Ww]olken["\']|["\'][Ii]n\s*[Ww]olken["\']',
        "Hardcoded Wolkenlage strings (should use WeatherMetricsService.format_cloud_status)",
    ),
    # Local function definitions that duplicate service
    (
        r"def\s+_?calc_effective_cloud\s*\(",
        "Local effective_cloud calculation function",
    ),
    (
        r"def\s+_?get_weather_symbol\s*\(",
        "Local get_weather_symbol function (should use WeatherMetricsService)",
    ),
    (
        r"def\s+_?calculate_sunny_hours\s*\(",
        "Local sunny_hours calculation function",
    ),
    # Direct effective cloud math
    (
        r"\(\s*cloud_mid.*\+.*cloud_high\s*\)\s*/\s*2",
        "Direct effective cloud calculation (mid + high) / 2",
    ),
]


def get_python_files() -> list[Path]:
    """Get all Python files in scan directories, excluding allowed files."""
    root = Path(__file__).parent.parent.parent
    files = []
    for scan_dir in SCAN_DIRS:
        dir_path = root / scan_dir
        if dir_path.exists():
            for py_file in dir_path.rglob("*.py"):
                rel_path = str(py_file.relative_to(root))
                if rel_path not in ALLOWED_FILES:
                    files.append(py_file)
    return files


def check_file_for_violations(file_path: Path) -> list[tuple[int, str, str]]:
    """Check a file for architecture violations.

    Returns list of (line_number, line_content, violation_description).
    """
    violations = []
    try:
        content = file_path.read_text()
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Skip comments and docstrings
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue

            for pattern, description in VIOLATION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append((line_num, line.strip(), description))

    except Exception as e:
        pytest.fail(f"Could not read {file_path}: {e}")

    return violations


class TestArchitectureViolations:
    """Enforce Single Source of Truth architecture."""

    def test_no_direct_weather_calculations(self):
        """No direct weather calculations outside WeatherMetricsService."""
        all_violations = []

        for py_file in get_python_files():
            violations = check_file_for_violations(py_file)
            if violations:
                for line_num, line, desc in violations:
                    all_violations.append(
                        f"{py_file.name}:{line_num} - {desc}\n  {line}"
                    )

        if all_violations:
            violation_report = "\n\n".join(all_violations)
            pytest.fail(
                f"Architecture violations found!\n\n"
                f"All weather calculations must use WeatherMetricsService.\n"
                f"See: src/services/weather_metrics.py\n\n"
                f"Violations:\n{violation_report}"
            )

    def test_weather_metrics_service_exists(self):
        """WeatherMetricsService must exist as Single Source of Truth."""
        service_path = Path(__file__).parent.parent.parent / "src/services/weather_metrics.py"
        assert service_path.exists(), (
            "WeatherMetricsService not found!\n"
            "Expected: src/services/weather_metrics.py\n"
            "This is the Single Source of Truth for all weather calculations."
        )

    def test_service_has_required_methods(self):
        """WeatherMetricsService must have all required methods."""
        from services.weather_metrics import WeatherMetricsService

        required_methods = [
            "calculate_sunny_hours",
            "calculate_cloud_status",
            "calculate_effective_cloud",
            "get_weather_symbol",
            "format_cloud_status",
            "get_cloud_status_emoji",
        ]

        for method in required_methods:
            assert hasattr(WeatherMetricsService, method), (
                f"WeatherMetricsService missing required method: {method}"
            )


class TestImportEnforcement:
    """Ensure files that need weather metrics import the service."""

    def test_compare_imports_service(self):
        """compare.py must import WeatherMetricsService."""
        compare_path = Path(__file__).parent.parent.parent / "src/web/pages/compare.py"
        content = compare_path.read_text()

        assert "from services.weather_metrics import" in content, (
            "compare.py must import WeatherMetricsService!\n"
            "Expected: from services.weather_metrics import WeatherMetricsService"
        )
