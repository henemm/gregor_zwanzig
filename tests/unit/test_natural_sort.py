"""
Tests for natural_sort_key helper.

Pure-function tests, no UI context. Covers numeric-aware sorting for filenames
like KHW_00a, KHW_10, KHW_11 (Issue #127).

Spec: docs/specs/modules/gpx_multi_import.md

EXPECTED at TDD RED: All tests FAIL with ImportError because
`src/core/natural_sort.py` does not exist yet.
"""
from __future__ import annotations


class TestNaturalSortKey:
    """GIVEN a string WHEN natural_sort_key THEN sortable key with numeric tokens."""

    def test_khw_pattern_natural_sort(self):
        """
        GIVEN: KHW filenames with mixed alpha/numeric suffixes
        WHEN: sorted with natural_sort_key
        THEN: KHW_00a < KHW_00b < KHW_10 < KHW_11

        EXPECTED: FAIL - src.core.natural_sort doesn't exist yet
        """
        from core.natural_sort import natural_sort_key

        names = ["KHW_11", "KHW_00a", "KHW_10", "KHW_00b"]
        result = sorted(names, key=natural_sort_key)
        assert result == ["KHW_00a", "KHW_00b", "KHW_10", "KHW_11"]

    def test_pure_numeric_filenames(self):
        """
        GIVEN: Filenames with pure numeric prefixes that lex-sort wrong
        WHEN: sorted with natural_sort_key
        THEN: Numeric order (1, 2, 10) not lex order (1, 10, 2)
        """
        from core.natural_sort import natural_sort_key

        names = ["10.gpx", "2.gpx", "1.gpx"]
        result = sorted(names, key=natural_sort_key)
        assert result == ["1.gpx", "2.gpx", "10.gpx"]

    def test_alphanumeric_mix(self):
        """
        GIVEN: Mixed alphanumeric tokens
        WHEN: sorted with natural_sort_key
        THEN: Numeric chunks compared as ints, text chunks as strings
        """
        from core.natural_sort import natural_sort_key

        names = ["file_2a", "file_10", "file_2b", "file_1"]
        result = sorted(names, key=natural_sort_key)
        assert result == ["file_1", "file_2a", "file_2b", "file_10"]

    def test_empty_list(self):
        """
        GIVEN: Empty list
        WHEN: sorted with natural_sort_key
        THEN: Empty list (no exceptions)
        """
        from core.natural_sort import natural_sort_key

        assert sorted([], key=natural_sort_key) == []

    def test_single_element(self):
        """
        GIVEN: Single-element list
        WHEN: sorted with natural_sort_key
        THEN: List unchanged
        """
        from core.natural_sort import natural_sort_key

        assert sorted(["only_one"], key=natural_sort_key) == ["only_one"]

    def test_identical_strings(self):
        """
        GIVEN: List with identical strings
        WHEN: sorted with natural_sort_key
        THEN: Stable order, all elements present
        """
        from core.natural_sort import natural_sort_key

        result = sorted(["a", "a"], key=natural_sort_key)
        assert result == ["a", "a"]

    def test_real_khw_filenames(self):
        """
        GIVEN: 13 real KHW filenames in randomized order
        WHEN: sorted with natural_sort_key
        THEN: Order is 00a, 00b, 01, 02, ..., 11

        This is the exact use case from Issue #127 (Trip 5f534011,
        Kaiser-Hirsch-Weg, 13 etappen).
        """
        from core.natural_sort import natural_sort_key

        names = [
            "KHW_11: von Dolinza Alm nach Nötsch im Gailtal",
            "KHW_00a: Von Troblach Bhf nach Helmhotel",
            "KHW_10: von Egger Alm nach Dolinza Alm",
            "KHW_02: von Obstansersee-Hütte nach Porzehütte",
            "KHW_00b: Von Helmhotel nach Sillianer Hütte",
            "KHW_01: Sillianer Hütte nach Obstansersee-Hütte",
            "KHW_09: von Nassfeld nach Egger Alm",
            "KHW_03: von Porzehütte nach Hochweißsteinhaus",
            "KHW_07: von Zollnersee Hütte nach Straniger Alm",
            "KHW_05: von Wolayersee-Hütte nach Almgasthof Valentinalm",
            "KHW_04: von Hochweißsteinhaus nach Wolayersee-Hütte",
            "KHW_08: von Straniger Alm nach Nassfeld",
            "KHW_06: von Almgasthof Valentinalm nach Zollnersee Hütte",
        ]
        result = sorted(names, key=natural_sort_key)

        # Extract just the KHW_XX part for assertion clarity
        prefixes = [r.split(":")[0] for r in result]
        assert prefixes == [
            "KHW_00a",
            "KHW_00b",
            "KHW_01",
            "KHW_02",
            "KHW_03",
            "KHW_04",
            "KHW_05",
            "KHW_06",
            "KHW_07",
            "KHW_08",
            "KHW_09",
            "KHW_10",
            "KHW_11",
        ]
