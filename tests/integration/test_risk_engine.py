"""
F8: Risk Engine (Daten-Layer) v2.0 — Integration Tests

SPEC: docs/specs/modules/risk_engine.md v2.0

Tests verify that RiskEngine.assess_segment() correctly classifies
weather risks using MetricCatalog thresholds. No mocks — uses real
DTOs and real MetricCatalog.
"""

from datetime import datetime, timezone

import pytest

from app.models import (
    GPXPoint,
    Risk,
    RiskAssessment,
    RiskLevel,
    RiskType,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from services.risk_engine import RiskEngine


# --- Helpers ---

def _make_segment_weather(
    thunder_level_max: ThunderLevel | None = None,
    wind_max_kmh: float | None = None,
    gust_max_kmh: float | None = None,
    precip_sum_mm: float | None = None,
    pop_max_pct: int | None = None,
    cape_max_jkg: float | None = None,
    wind_chill_min_c: float | None = None,
    visibility_min_m: int | None = None,
) -> SegmentWeatherData:
    """Create a minimal SegmentWeatherData for risk testing."""
    point = GPXPoint(lat=47.0, lon=13.0, elevation_m=1500, distance_from_start_km=0.0)
    segment = TripSegment(
        segment_id=1,
        start_point=point,
        end_point=point,
        start_time=datetime(2026, 2, 18, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=6.0,
        ascent_m=400,
        descent_m=200,
    )
    summary = SegmentWeatherSummary(
        thunder_level_max=thunder_level_max,
        wind_max_kmh=wind_max_kmh,
        gust_max_kmh=gust_max_kmh,
        precip_sum_mm=precip_sum_mm,
        pop_max_pct=pop_max_pct,
        cape_max_jkg=cape_max_jkg,
        wind_chill_min_c=wind_chill_min_c,
        visibility_min_m=visibility_min_m,
    )
    return SegmentWeatherData(
        segment=segment,
        timeseries=None,
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


# --- Tests ---

class TestRiskEngineAssessSegment:
    """Test RiskEngine.assess_segment() risk classification."""

    def test_no_risks_calm_weather(self):
        """Calm weather → empty RiskAssessment."""
        seg = _make_segment_weather(
            thunder_level_max=ThunderLevel.NONE,
            wind_max_kmh=20,
            gust_max_kmh=30,
            precip_sum_mm=2.0,
            visibility_min_m=10000,
            wind_chill_min_c=5.0,
            cape_max_jkg=200,
        )
        engine = RiskEngine()
        assessment = engine.assess_segment(seg)
        assert isinstance(assessment, RiskAssessment)
        assert len(assessment.risks) == 0

    def test_thunder_high(self):
        """ThunderLevel.HIGH → Risk(THUNDERSTORM, HIGH)."""
        seg = _make_segment_weather(thunder_level_max=ThunderLevel.HIGH)
        assessment = RiskEngine().assess_segment(seg)
        assert len(assessment.risks) >= 1
        thunder = [r for r in assessment.risks if r.type == RiskType.THUNDERSTORM]
        assert len(thunder) == 1
        assert thunder[0].level == RiskLevel.HIGH

    def test_thunder_medium(self):
        """ThunderLevel.MED → Risk(THUNDERSTORM, MODERATE)."""
        seg = _make_segment_weather(thunder_level_max=ThunderLevel.MED)
        assessment = RiskEngine().assess_segment(seg)
        thunder = [r for r in assessment.risks if r.type == RiskType.THUNDERSTORM]
        assert len(thunder) == 1
        assert thunder[0].level == RiskLevel.MODERATE

    def test_wind_high(self):
        """wind_max > 70 → Risk(WIND, HIGH)."""
        seg = _make_segment_weather(wind_max_kmh=75, gust_max_kmh=90)
        assessment = RiskEngine().assess_segment(seg)
        wind = [r for r in assessment.risks if r.type == RiskType.WIND]
        assert len(wind) == 1
        assert wind[0].level == RiskLevel.HIGH

    def test_wind_moderate(self):
        """wind_max > 50 but <= 70 → Risk(WIND, MODERATE)."""
        seg = _make_segment_weather(wind_max_kmh=55, gust_max_kmh=45)
        assessment = RiskEngine().assess_segment(seg)
        wind = [r for r in assessment.risks if r.type == RiskType.WIND]
        assert len(wind) == 1
        assert wind[0].level == RiskLevel.MODERATE

    def test_gust_overrides_wind(self):
        """Gust HIGH + Wind MODERATE → deduplicated to single WIND HIGH."""
        seg = _make_segment_weather(wind_max_kmh=55, gust_max_kmh=82)
        assessment = RiskEngine().assess_segment(seg)
        wind = [r for r in assessment.risks if r.type == RiskType.WIND]
        assert len(wind) == 1  # Deduplicated
        assert wind[0].level == RiskLevel.HIGH  # Gust wins

    def test_precipitation_moderate(self):
        """precip > 20mm → Risk(RAIN, MODERATE)."""
        seg = _make_segment_weather(precip_sum_mm=25.0)
        assessment = RiskEngine().assess_segment(seg)
        rain = [r for r in assessment.risks if r.type == RiskType.RAIN]
        assert len(rain) == 1
        assert rain[0].level == RiskLevel.MODERATE

    def test_visibility_inverted(self):
        """visibility < 100m → Risk(POOR_VISIBILITY, HIGH)."""
        seg = _make_segment_weather(visibility_min_m=50)
        assessment = RiskEngine().assess_segment(seg)
        vis = [r for r in assessment.risks if r.type == RiskType.POOR_VISIBILITY]
        assert len(vis) == 1
        assert vis[0].level == RiskLevel.HIGH

    def test_wind_chill_inverted(self):
        """wind_chill < -20 → Risk(WIND_CHILL, HIGH)."""
        seg = _make_segment_weather(wind_chill_min_c=-25.0)
        assessment = RiskEngine().assess_segment(seg)
        wc = [r for r in assessment.risks if r.type == RiskType.WIND_CHILL]
        assert len(wc) == 1
        assert wc[0].level == RiskLevel.HIGH

    def test_multiple_risks_sorted(self):
        """Thunder HIGH + Wind MODERATE → sorted HIGH first."""
        seg = _make_segment_weather(
            thunder_level_max=ThunderLevel.HIGH,
            wind_max_kmh=55,
        )
        assessment = RiskEngine().assess_segment(seg)
        assert len(assessment.risks) >= 2
        assert assessment.risks[0].level == RiskLevel.HIGH

    def test_deduplication(self):
        """Wind MODERATE + Gust HIGH → one WIND entry with HIGH."""
        seg = _make_segment_weather(wind_max_kmh=55, gust_max_kmh=82)
        assessment = RiskEngine().assess_segment(seg)
        wind_risks = [r for r in assessment.risks if r.type == RiskType.WIND]
        assert len(wind_risks) == 1
        assert wind_risks[0].level == RiskLevel.HIGH

    def test_none_values_skipped(self):
        """All None metrics → no risks."""
        seg = _make_segment_weather()  # All defaults = None
        assessment = RiskEngine().assess_segment(seg)
        assert len(assessment.risks) == 0

    def test_cape_high(self):
        """CAPE >= 2000 → Risk(THUNDERSTORM, HIGH)."""
        seg = _make_segment_weather(cape_max_jkg=2500)
        assessment = RiskEngine().assess_segment(seg)
        thunder = [r for r in assessment.risks if r.type == RiskType.THUNDERSTORM]
        assert len(thunder) == 1
        assert thunder[0].level == RiskLevel.HIGH

    def test_cape_moderate(self):
        """CAPE >= 1000 but < 2000 → Risk(THUNDERSTORM, MODERATE)."""
        seg = _make_segment_weather(cape_max_jkg=1500)
        assessment = RiskEngine().assess_segment(seg)
        thunder = [r for r in assessment.risks if r.type == RiskType.THUNDERSTORM]
        assert len(thunder) == 1
        assert thunder[0].level == RiskLevel.MODERATE


class TestRiskEngineAssessSegments:
    """Test batch assessment."""

    def test_assess_multiple_segments(self):
        """assess_segments() returns one RiskAssessment per segment."""
        segs = [
            _make_segment_weather(wind_max_kmh=75),
            _make_segment_weather(wind_max_kmh=20),
        ]
        engine = RiskEngine()
        results = engine.assess_segments(segs)
        assert len(results) == 2
        assert len(results[0].risks) >= 1  # Wind HIGH
        assert len(results[1].risks) == 0  # Calm


class TestGetMaxRiskLevel:
    """Test max risk level extraction."""

    def test_max_level_high(self):
        """Assessment with HIGH risk → returns HIGH."""
        seg = _make_segment_weather(thunder_level_max=ThunderLevel.HIGH)
        engine = RiskEngine()
        assessment = engine.assess_segment(seg)
        assert engine.get_max_risk_level(assessment) == RiskLevel.HIGH

    def test_max_level_empty(self):
        """Empty assessment → returns LOW."""
        engine = RiskEngine()
        assessment = RiskAssessment(risks=[])
        assert engine.get_max_risk_level(assessment) == RiskLevel.LOW
