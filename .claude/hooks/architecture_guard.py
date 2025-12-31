#!/usr/bin/env python3
"""
Architecture Guard Hook - Enforces Single Source of Truth

Blocks Edit/Write operations that violate the WeatherMetricsService architecture.
All weather calculations MUST go through WeatherMetricsService.

Exit Codes:
- 0: Allowed
- 2: Blocked (stderr shown to Claude)
"""

import json
import re
import sys
from pathlib import Path

# Files that ARE allowed to contain weather calculations
ALLOWED_FILES = {
    "weather_metrics.py",  # The Single Source of Truth
    "test_weather_metrics_spec.py",  # Tests for the service
    "test_architecture_violations.py",  # Architecture tests
    "architecture_guard.py",  # This file
}

# Patterns that indicate architecture violations
VIOLATION_PATTERNS = [
    # Direct sunny hour calculations
    (
        r"cloud_pct\s*[<>=]+\s*\d+.*sunny|sunny.*cloud_pct\s*[<>=]+\s*\d+",
        "Direct sunny hour calculation using cloud_pct threshold",
        "Use WeatherMetricsService.calculate_sunny_hours() instead",
    ),
    (
        r"sunshine_duration.*\s*/\s*\d+|sunshine_duration.*//\s*\d+",
        "Direct sunshine_duration division",
        "Use WeatherMetricsService.calculate_sunny_hours() instead",
    ),
    # Direct cloud status calculations
    (
        r"cloud_low_avg\s*>\s*\d+.*(?:ueber|above|klar|wolken)",
        "Direct cloud_low_avg comparison for Wolkenlage",
        "Use WeatherMetricsService.calculate_cloud_status() instead",
    ),
    # Hardcoded Wolkenlage strings (outside of formatting)
    (
        r'["\'].*(?:ueber|above)\s*[Ww]olken["\']',
        "Hardcoded 'ueber Wolken' string",
        "Use WeatherMetricsService.format_cloud_status() instead",
    ),
    # Local function definitions that duplicate service
    (
        r"def\s+_?calc_effective_cloud\s*\(",
        "Local effective_cloud calculation function",
        "Use WeatherMetricsService.calculate_effective_cloud() instead",
    ),
    (
        r"def\s+_?get_weather_symbol\s*\((?!.*WeatherMetricsService)",
        "Local get_weather_symbol function",
        "Use WeatherMetricsService.get_weather_symbol() instead",
    ),
    (
        r"def\s+_?calculate_sunny_hours\s*\(",
        "Local sunny_hours calculation function",
        "Use WeatherMetricsService.calculate_sunny_hours() instead",
    ),
    (
        r"def\s+_?calculate_cloud_status\s*\(",
        "Local cloud_status calculation function",
        "Use WeatherMetricsService.calculate_cloud_status() instead",
    ),
    # Direct effective cloud math
    (
        r"\(\s*cloud_mid.*\+.*cloud_high\s*\)\s*/\s*2",
        "Direct effective cloud calculation (mid + high) / 2",
        "Use WeatherMetricsService.calculate_effective_cloud() instead",
    ),
    # Weather symbol emoji assignments based on cloud thresholds
    (
        r'cloud.*[<>=]+\s*\d+.*["\'][^\'"]*[\u2600-\u26FF\u2700-\u27BF]["\']',
        "Direct weather symbol assignment based on cloud threshold",
        "Use WeatherMetricsService.get_weather_symbol() instead",
    ),
]


def is_allowed_file(file_path: str) -> bool:
    """Check if file is in the allowed list."""
    file_name = Path(file_path).name
    return file_name in ALLOWED_FILES


def is_python_file(file_path: str) -> bool:
    """Check if file is a Python file."""
    return file_path.endswith(".py")


def check_content_for_violations(content: str) -> list[tuple[str, str]]:
    """Check content for architecture violations.

    Returns list of (violation_description, fix_suggestion).
    """
    violations = []

    for line in content.split("\n"):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for pattern, description, fix in VIOLATION_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append((description, fix))
                break  # One violation per line is enough

    return violations


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    # Only check Edit and Write tools
    if tool_name not in ("Edit", "Write"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")

    # Only check Python files
    if not is_python_file(file_path):
        sys.exit(0)

    # Allow the service file and tests
    if is_allowed_file(file_path):
        sys.exit(0)

    # Get content to check
    content = tool_input.get("content", "") or tool_input.get("new_string", "")
    if not content:
        sys.exit(0)

    # Check for violations
    violations = check_content_for_violations(content)

    if violations:
        print("=" * 70, file=sys.stderr)
        print("BLOCKED - Architecture Violation Detected!", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print("Weather calculations must use WeatherMetricsService!", file=sys.stderr)
        print("Single Source of Truth: src/services/weather_metrics.py", file=sys.stderr)
        print(file=sys.stderr)
        print("VIOLATIONS FOUND:", file=sys.stderr)
        print("-" * 40, file=sys.stderr)

        # Deduplicate violations
        seen = set()
        for desc, fix in violations:
            if desc not in seen:
                seen.add(desc)
                print(f"  - {desc}", file=sys.stderr)
                print(f"    FIX: {fix}", file=sys.stderr)
                print(file=sys.stderr)

        print("-" * 40, file=sys.stderr)
        print("Import the service:", file=sys.stderr)
        print("  from services.weather_metrics import WeatherMetricsService", file=sys.stderr)
        print(file=sys.stderr)
        print("Available methods:", file=sys.stderr)
        print("  - WeatherMetricsService.calculate_sunny_hours(data, elevation_m)", file=sys.stderr)
        print("  - WeatherMetricsService.calculate_cloud_status(...)", file=sys.stderr)
        print("  - WeatherMetricsService.calculate_effective_cloud(...)", file=sys.stderr)
        print("  - WeatherMetricsService.get_weather_symbol(...)", file=sys.stderr)
        print("  - WeatherMetricsService.format_cloud_status(status)", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
