"""Natural sort key helper.

Splits a string into numeric and non-numeric chunks so that "KHW_10" sorts
after "KHW_2" (instead of lexicographically before it).

Spec: docs/specs/modules/gpx_multi_import.md (Issue #127).
"""
from __future__ import annotations

import re

_NUM_RE = re.compile(r"(\d+)")


def natural_sort_key(s: str) -> list:
    """Return a sort key that orders embedded integers numerically.

    Examples:
        sorted(["KHW_11", "KHW_00a", "KHW_10"], key=natural_sort_key)
            == ["KHW_00a", "KHW_10", "KHW_11"]
        sorted(["10.gpx", "2.gpx", "1.gpx"], key=natural_sort_key)
            == ["1.gpx", "2.gpx", "10.gpx"]

    Implementation:
        re.split with a capture group keeps numeric tokens as separate
        list elements (alternating with text). Even indices are text
        (lower-cased for case-insensitive ordering), odd indices are
        numeric tokens converted to int for numeric ordering.
    """
    parts = _NUM_RE.split(s)
    return [
        int(p) if i % 2 == 1 else p.lower()
        for i, p in enumerate(parts)
    ]
