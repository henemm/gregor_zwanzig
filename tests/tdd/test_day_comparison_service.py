"""
TDD RED: DayComparisonService — Delta-Berechnung Vortag-Vergleich (Issue #748)

Kein Mock: Tests bauen echte SegmentWeatherData-Objekte.

AC-1: compare() gibt DayComparison mit einem Eintrag pro heutigem Segment zurück
AC-2: Niederschlag weniger = BETTER, delta = heute - gestern
AC-3: ThunderLevel-Ordinal-Vergleich (NONE=0, MED=1, HIGH=2)
AC-4: Segment-ID fehlt in yesterday-Liste → alle Directions MISSING
AC-5: Temperatur ist neutral → direction immer EQUAL, delta gesetzt

SPEC: docs/specs/modules/issue_748_day_comparison_service.md
"""
from datetime import datetime, timezone

import pytest


def _make_segment(segment_id: int, **summary_kwargs):
    """Minimales SegmentWeatherData für Tests."""
    from app.models import (
        GPXPoint,
        SegmentWeatherData,
        SegmentWeatherSummary,
        TripSegment,
    )

    segment = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=200.0),
        end_point=GPXPoint(lat=42.2, lon=9.2, elevation_m=300.0),
        start_time=datetime(2026, 6, 11, 7, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 11, 11, 0, tzinfo=timezone.utc),
        duration_hours=4.0,
        distance_km=15.0,
        ascent_m=600.0,
        descent_m=200.0,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=SegmentWeatherSummary(**summary_kwargs),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


class TestAC1_BasicStructure:
    """AC-1: compare() gibt DayComparison mit einem Eintrag pro heutigem Segment."""

    def test_compare_returns_day_comparison(self):
        """
        GIVEN zwei Listen mit je 2 identischen Segmenten
        WHEN compare(today, yesterday) aufgerufen wird
        THEN gibt DayComparison mit 2 DayComparisonEntry zurück
        """
        from services.day_comparison import DayComparison, DayComparisonService

        today = [
            _make_segment(1, precip_sum_mm=3.0),
            _make_segment(2, precip_sum_mm=1.0),
        ]
        yesterday = [
            _make_segment(1, precip_sum_mm=5.0),
            _make_segment(2, precip_sum_mm=4.0),
        ]

        svc = DayComparisonService()
        result = svc.compare(today, yesterday)

        assert isinstance(result, DayComparison)
        assert len(result.entries) == 2
        assert result.entries[0].segment_id == 1
        assert result.entries[1].segment_id == 2

    def test_compare_empty_lists(self):
        """
        GIVEN leere Listen
        WHEN compare([], []) aufgerufen wird
        THEN gibt DayComparison mit leerer entries-Liste zurück
        """
        from services.day_comparison import DayComparison, DayComparisonService

        result = DayComparisonService().compare([], [])

        assert isinstance(result, DayComparison)
        assert result.entries == []


class TestAC2_PrecipitationDirection:
    """AC-2: Niederschlag weniger = BETTER, mehr = WORSE."""

    def test_precip_less_today_is_better(self):
        """
        GIVEN gestern precip_sum_mm=8.0, heute precip_sum_mm=2.0
        WHEN compare()
        THEN direction=BETTER, delta=-6.0
        """
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, precip_sum_mm=2.0)]
        yesterday = [_make_segment(1, precip_sum_mm=8.0)]

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.precip_sum.direction == ComparisonDirection.BETTER
        assert abs(entry.precip_sum.delta - (-6.0)) < 0.01

    def test_precip_more_today_is_worse(self):
        """
        GIVEN gestern precip_sum_mm=2.0, heute precip_sum_mm=9.0
        WHEN compare()
        THEN direction=WORSE, delta=+7.0
        """
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, precip_sum_mm=9.0)]
        yesterday = [_make_segment(1, precip_sum_mm=2.0)]

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.precip_sum.direction == ComparisonDirection.WORSE
        assert abs(entry.precip_sum.delta - 7.0) < 0.01

    def test_precip_equal_is_equal(self):
        """
        GIVEN gestern und heute precip_sum_mm=4.0
        WHEN compare()
        THEN direction=EQUAL, delta=0.0
        """
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, precip_sum_mm=4.0)]
        yesterday = [_make_segment(1, precip_sum_mm=4.0)]

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.precip_sum.direction == ComparisonDirection.EQUAL

    def test_wind_less_today_is_better(self):
        """
        GIVEN gestern wind_max_kmh=45, heute 30
        WHEN compare()
        THEN direction=BETTER
        """
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, wind_max_kmh=30.0)]
        yesterday = [_make_segment(1, wind_max_kmh=45.0)]

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.wind_max.direction == ComparisonDirection.BETTER

    def test_gust_more_today_is_worse(self):
        """
        GIVEN gestern gust_max_kmh=50, heute 70
        WHEN compare()
        THEN direction=WORSE
        """
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, gust_max_kmh=70.0)]
        yesterday = [_make_segment(1, gust_max_kmh=50.0)]

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.gust_max.direction == ComparisonDirection.WORSE


class TestAC3_ThunderOrdinal:
    """AC-3: ThunderLevel-Ordinal-Vergleich."""

    def test_thunder_high_to_none_is_better(self):
        """
        GIVEN gestern ThunderLevel.HIGH, heute ThunderLevel.NONE
        WHEN compare()
        THEN direction=BETTER, delta=-2 (ordinal)
        """
        from app.models import ThunderLevel
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, thunder_level_max=ThunderLevel.NONE)]
        yesterday = [_make_segment(1, thunder_level_max=ThunderLevel.HIGH)]

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.thunder.direction == ComparisonDirection.BETTER
        assert entry.thunder.delta == -2

    def test_thunder_none_to_med_is_worse(self):
        """
        GIVEN gestern ThunderLevel.NONE, heute ThunderLevel.MED
        WHEN compare()
        THEN direction=WORSE, delta=+1
        """
        from app.models import ThunderLevel
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, thunder_level_max=ThunderLevel.MED)]
        yesterday = [_make_segment(1, thunder_level_max=ThunderLevel.NONE)]

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.thunder.direction == ComparisonDirection.WORSE
        assert entry.thunder.delta == 1

    def test_thunder_same_level_is_equal(self):
        """
        GIVEN gestern und heute ThunderLevel.MED
        WHEN compare()
        THEN direction=EQUAL, delta=0
        """
        from app.models import ThunderLevel
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, thunder_level_max=ThunderLevel.MED)]
        yesterday = [_make_segment(1, thunder_level_max=ThunderLevel.MED)]

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.thunder.direction == ComparisonDirection.EQUAL
        assert entry.thunder.delta == 0


class TestAC4_MissingSegment:
    """AC-4: Segment fehlt in yesterday → alle Directions MISSING."""

    def test_segment_missing_in_yesterday(self):
        """
        GIVEN heute 3 Segmente, gestern nur Segmente 1+2 (Segment 3 fehlt)
        WHEN compare()
        THEN Segment 3 hat alle Directions MISSING, Segmente 1+2 normal berechnet
        """
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [
            _make_segment(1, precip_sum_mm=2.0),
            _make_segment(2, precip_sum_mm=1.0),
            _make_segment(3, precip_sum_mm=5.0),
        ]
        yesterday = [
            _make_segment(1, precip_sum_mm=4.0),
            _make_segment(2, precip_sum_mm=3.0),
        ]

        result = DayComparisonService().compare(today, yesterday)

        assert len(result.entries) == 3

        # Segment 3 vollständig MISSING
        seg3 = next(e for e in result.entries if e.segment_id == 3)
        assert seg3.precip_sum.direction == ComparisonDirection.MISSING
        assert seg3.wind_max.direction == ComparisonDirection.MISSING
        assert seg3.thunder.direction == ComparisonDirection.MISSING

        # Segmente 1+2 normal
        seg1 = next(e for e in result.entries if e.segment_id == 1)
        assert seg1.precip_sum.direction == ComparisonDirection.BETTER

    def test_missing_metric_in_yesterday(self):
        """
        GIVEN gestern precip_sum_mm=None (Metrik fehlt), heute 3.0
        WHEN compare()
        THEN precip_sum.direction=MISSING, delta=None
        """
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, precip_sum_mm=3.0)]
        yesterday = [_make_segment(1)]  # precip_sum_mm bleibt None

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.precip_sum.direction == ComparisonDirection.MISSING
        assert entry.precip_sum.delta is None


class TestAC5_TemperatureNeutral:
    """AC-5: Temperatur ist neutral — direction immer EQUAL."""

    def test_temp_max_higher_today_still_equal(self):
        """
        GIVEN gestern temp_max_c=15.0, heute 22.0
        WHEN compare()
        THEN temp_max.direction=EQUAL, delta=+7.0
        """
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, temp_max_c=22.0)]
        yesterday = [_make_segment(1, temp_max_c=15.0)]

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.temp_max.direction == ComparisonDirection.EQUAL
        assert abs(entry.temp_max.delta - 7.0) < 0.01

    def test_temp_min_lower_today_still_equal(self):
        """
        GIVEN gestern temp_min_c=10.0, heute 4.0
        WHEN compare()
        THEN temp_min.direction=EQUAL, delta=-6.0
        """
        from services.day_comparison import ComparisonDirection, DayComparisonService

        today = [_make_segment(1, temp_min_c=4.0)]
        yesterday = [_make_segment(1, temp_min_c=10.0)]

        entry = DayComparisonService().compare(today, yesterday).entries[0]

        assert entry.temp_min.direction == ComparisonDirection.EQUAL
        assert abs(entry.temp_min.delta - (-6.0)) < 0.01
