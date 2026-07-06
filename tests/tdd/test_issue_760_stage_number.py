"""
TDD tests for Issue #760 — Etappen-Nummer zwingend in der Briefing-E-Mail.

RED phase: numbered_stage_label() does not exist yet → all tests fail.
GREEN phase: method exists + 3 call-sites updated → all tests pass.

No mocks. Echte Trip/Stage-Objekte + echter TripReportFormatter-Aufruf.
"""
from __future__ import annotations

from datetime import date, datetime, timezone


from app.trip import Stage, Trip, Waypoint


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _waypoint(wp_id: str = "G1") -> Waypoint:
    return Waypoint(
        id=wp_id,
        name="Testpunkt",
        lat=47.0,
        lon=11.0,
        elevation_m=1000,
    )


def _stage(stage_id: str, name: str, d: date) -> Stage:
    return Stage(
        id=stage_id,
        name=name,
        date=d,
        waypoints=[_waypoint()],
    )


# ---------------------------------------------------------------------------
# AC-3 — Dedup-Tabelle: alle Fälle aus der Spec
# ---------------------------------------------------------------------------

class TestNumberedStageLabelDedup:
    """AC-3: Präfix wird genau einmal gesetzt, keine Verdopplung."""

    def test_no_prefix_gets_number(self):
        """Plain name → 'Etappe N: <name>'."""
        stage = _stage("T3", "von Sóller nach Tossals Verds", date(2026, 10, 3))
        trip = Trip(
            id="t",
            name="Mallorca",
            stages=[
                _stage("T1", "Erste", date(2026, 10, 1)),
                _stage("T2", "Zweite", date(2026, 10, 2)),
                stage,
            ],
        )
        result = trip.numbered_stage_label(stage)
        assert result == "Etappe 3: von Sóller nach Tossals Verds"

    def test_tag_prefix_replaced(self):
        """'Tag 1: von Valldemossa nach Deià' → 'Etappe 1: von Valldemossa nach Deià'."""
        stage = _stage("T1", "Tag 1: von Valldemossa nach Deià", date(2026, 10, 1))
        trip = Trip(id="t", name="Mallorca", stages=[stage])
        result = trip.numbered_stage_label(stage)
        assert result == "Etappe 1: von Valldemossa nach Deià"

    def test_etappe_bare_no_trailing_colon(self):
        """'Etappe 4' (no trailing rest) → 'Etappe 4' (no colon appended)."""
        stage = _stage("T4", "Etappe 4", date(2026, 10, 4))
        trip = Trip(
            id="t", name="Mallorca",
            stages=[
                _stage("T1", "a", date(2026, 10, 1)),
                _stage("T2", "b", date(2026, 10, 2)),
                _stage("T3", "c", date(2026, 10, 3)),
                stage,
            ],
        )
        result = trip.numbered_stage_label(stage)
        assert result == "Etappe 4"

    def test_etappe_with_name_kept(self):
        """'Etappe 2: Gipfeltour' → 'Etappe 2: Gipfeltour' (kein Duplikat)."""
        stage = _stage("T2", "Etappe 2: Gipfeltour", date(2026, 10, 2))
        trip = Trip(
            id="t", name="Mallorca",
            stages=[
                _stage("T1", "a", date(2026, 10, 1)),
                stage,
            ],
        )
        result = trip.numbered_stage_label(stage)
        assert result == "Etappe 2: Gipfeltour"

    def test_empty_name_yields_etappe_only(self):
        """Leerer Name → nur 'Etappe N' (kein hängender Doppelpunkt)."""
        stage = _stage("T5", "", date(2026, 10, 5))
        trip = Trip(
            id="t", name="Mallorca",
            stages=[
                _stage("T1", "a", date(2026, 10, 1)),
                _stage("T2", "b", date(2026, 10, 2)),
                _stage("T3", "c", date(2026, 10, 3)),
                _stage("T4", "d", date(2026, 10, 4)),
                stage,
            ],
        )
        result = trip.numbered_stage_label(stage)
        assert result == "Etappe 5"

    def test_tag_prefix_case_insensitive(self):
        """'tag 1: Foo' (lowercase) → dedup applies, yields 'Etappe 1: Foo'."""
        stage = _stage("T1", "tag 1: Foo", date(2026, 10, 1))
        trip = Trip(id="t", name="Mallorca", stages=[stage])
        result = trip.numbered_stage_label(stage)
        assert result == "Etappe 1: Foo"

    def test_etappe_with_dash_separator(self):
        """'Etappe 3 - Hochalm' → 'Etappe 3: Hochalm' (dash dedup)."""
        stage = _stage("T3", "Etappe 3 - Hochalm", date(2026, 10, 3))
        trip = Trip(
            id="t", name="Mallorca",
            stages=[
                _stage("T1", "a", date(2026, 10, 1)),
                _stage("T2", "b", date(2026, 10, 2)),
                stage,
            ],
        )
        result = trip.numbered_stage_label(stage)
        assert result == "Etappe 3: Hochalm"

    def test_no_double_number_tag_prefix(self):
        """'Tag 2: Gipfeltour' → 'Etappe 2: Gipfeltour', NOT 'Etappe 2: Tag 2: Gipfeltour'."""
        stage = _stage("T2", "Tag 2: Gipfeltour", date(2026, 10, 2))
        trip = Trip(
            id="t", name="Mallorca",
            stages=[
                _stage("T1", "a", date(2026, 10, 1)),
                stage,
            ],
        )
        result = trip.numbered_stage_label(stage)
        assert "Tag 2" not in result
        assert result == "Etappe 2: Gipfeltour"


# ---------------------------------------------------------------------------
# AC-4 — Chronologische Sortierung
# ---------------------------------------------------------------------------

class TestNumberedStageLabelChronological:
    """AC-4: Nummer folgt Datum, nicht Listenposition."""

    def test_reverse_list_order_uses_date_rank(self):
        """Etappen in umgekehrter Listenreihenfolge → Nummer nach Datum."""
        s3 = _stage("T3", "Dritte nach Datum", date(2026, 10, 3))
        s1 = _stage("T1", "Erste nach Datum", date(2026, 10, 1))
        s2 = _stage("T2", "Zweite nach Datum", date(2026, 10, 2))
        # Deliberately reversed in list: s3 is at index 0
        trip = Trip(id="t", name="Mallorca", stages=[s3, s1, s2])

        assert trip.numbered_stage_label(s1) == "Etappe 1: Erste nach Datum"
        assert trip.numbered_stage_label(s2) == "Etappe 2: Zweite nach Datum"
        assert trip.numbered_stage_label(s3) == "Etappe 3: Dritte nach Datum"

    def test_list_position_not_used(self):
        """[s2, s1] in list → s1 must still be 'Etappe 1' (date wins over index)."""
        s1 = _stage("T1", "Frühstart", date(2026, 10, 1))
        s2 = _stage("T2", "Folgetag", date(2026, 10, 2))
        trip = Trip(id="t", name="Mallorca", stages=[s2, s1])
        assert trip.numbered_stage_label(s1) == "Etappe 1: Frühstart"
        assert trip.numbered_stage_label(s2) == "Etappe 2: Folgetag"


# ---------------------------------------------------------------------------
# AC-1 + AC-2 — Integration: Formatter erzeugt Betreff + Body mit Etappen-Nummer
# ---------------------------------------------------------------------------

class TestFormatterIncludesStageNumber:
    """AC-1 + AC-2: format_email produziert Subject + HTML/Plain mit 'Etappe N: …'."""

    def _make_segment_weather(self, day: int = 3):
        """Build a minimal SegmentWeatherData for formatter integration tests."""
        from app.models import (
            ForecastDataPoint,
            ForecastMeta,
            GPXPoint,
            NormalizedTimeseries,
            Provider,
            SegmentWeatherData,
            SegmentWeatherSummary,
            TripSegment,
            ThunderLevel,
        )
        seg = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=39.8, lon=2.7, elevation_m=500),
            end_point=GPXPoint(lat=39.9, lon=2.8, elevation_m=600),
            start_time=datetime(2026, 10, day, 8, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 10, day, 14, 0, tzinfo=timezone.utc),
            duration_hours=6.0,
            distance_km=12.0,
            ascent_m=300.0,
            descent_m=100.0,
        )
        dp = ForecastDataPoint(
            ts=datetime(2026, 10, day, 9, 0, tzinfo=timezone.utc),
            t2m_c=18.0,
            wind10m_kmh=15.0,
            gust_kmh=25.0,
            precip_1h_mm=0.0,
            cloud_total_pct=30,
            thunder_level=ThunderLevel.NONE,
            humidity_pct=60,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO,
            model="test",
            run=datetime(2026, 10, day, 0, 0, tzinfo=timezone.utc),
            grid_res_km=1.0,
            interp="point_grid",
        )
        ts = NormalizedTimeseries(meta=meta, data=[dp])
        summary = SegmentWeatherSummary(
            temp_min_c=15.0,
            temp_max_c=22.0,
            temp_avg_c=18.0,
            wind_max_kmh=20.0,
            gust_max_kmh=30.0,
            precip_sum_mm=0.0,
            cloud_avg_pct=30,
            humidity_avg_pct=60,
            thunder_level_max=ThunderLevel.NONE,
            wind_chill_min_c=14.0,
        )
        return SegmentWeatherData(
            segment=seg,
            timeseries=ts,
            aggregated=summary,
            fetched_at=datetime.now(timezone.utc),
            provider="openmeteo",
        )

    def test_subject_contains_stage_number(self):
        """AC-2: Subject enthält 'Etappe 3' wenn Etappe an chronolog. Position 3."""
        from output.renderers.trip_report import TripReportFormatter

        s1 = _stage("T1", "Erste", date(2026, 10, 1))
        s2 = _stage("T2", "Zweite", date(2026, 10, 2))
        s3 = _stage("T3", "von Sóller nach Tossals Verds", date(2026, 10, 3))
        trip = Trip(id="t", name="Mallorca GR", stages=[s1, s2, s3])

        stage_name = trip.numbered_stage_label(s3)
        assert stage_name == "Etappe 3: von Sóller nach Tossals Verds"

        seg_weather = self._make_segment_weather(day=3)
        report = TripReportFormatter().format_email(
            segments=[seg_weather],
            trip_name=trip.name,
            report_type="morning",
            stage_name=stage_name,
        )

        assert "Etappe 3" in report.email_subject, (
            f"Subject enthält keine Etappen-Nummer: {report.email_subject!r}"
        )

    def test_html_body_contains_stage_number(self):
        """AC-1: HTML-Body enthält 'Etappe 3: von Sóller nach Tossals Verds'."""
        from output.renderers.trip_report import TripReportFormatter

        s1 = _stage("T1", "Erste", date(2026, 10, 1))
        s2 = _stage("T2", "Zweite", date(2026, 10, 2))
        s3 = _stage("T3", "von Sóller nach Tossals Verds", date(2026, 10, 3))
        trip = Trip(id="t", name="Mallorca GR", stages=[s1, s2, s3])

        stage_name = trip.numbered_stage_label(s3)
        seg_weather = self._make_segment_weather(day=3)

        report = TripReportFormatter().format_email(
            segments=[seg_weather],
            trip_name=trip.name,
            report_type="morning",
            stage_name=stage_name,
        )

        assert "Etappe 3" in report.email_html, (
            "HTML-Body enthält keine Etappen-Nummer 'Etappe 3'"
        )

    def test_plain_body_contains_stage_number(self):
        """AC-1: Plain-Text-Body enthält 'Etappe 3'."""
        from output.renderers.trip_report import TripReportFormatter

        s1 = _stage("T1", "Erste", date(2026, 10, 1))
        s2 = _stage("T2", "Zweite", date(2026, 10, 2))
        s3 = _stage("T3", "von Sóller nach Tossals Verds", date(2026, 10, 3))
        trip = Trip(id="t", name="Mallorca GR", stages=[s1, s2, s3])

        stage_name = trip.numbered_stage_label(s3)
        seg_weather = self._make_segment_weather(day=3)

        report = TripReportFormatter().format_email(
            segments=[seg_weather],
            trip_name=trip.name,
            report_type="morning",
            stage_name=stage_name,
        )

        assert "Etappe 3" in report.email_plain, (
            "Plain-Text-Body enthält keine Etappen-Nummer 'Etappe 3'"
        )
