"""
TDD Tests for F7: Wind-Exposition (Grat-Erkennung)

SPEC: docs/specs/modules/wind_exposition.md v1.0

Tests:
1. ExposedSection DTO exists
2. WIND_EXPOSITION RiskType exists
3. WindExpositionService.detect_exposed_sections() from GPXTrack
4. WindExpositionService.detect_exposed_from_segments() from segments
5. RiskEngine Rule 9: wind exposition escalation
6. MetricCatalog exposition_risk_thresholds
7. Formatter labels
"""

from datetime import datetime, timezone

import pytest


# --- 1. DTO & Enum ---

def test_exposed_section_dto_exists():
    """ExposedSection dataclass must exist with required fields."""
    from app.models import ExposedSection
    section = ExposedSection(
        start_km=5.0, end_km=5.6, max_elevation_m=2800.0, exposition_type="GRAT",
    )
    assert section.start_km == 5.0
    assert section.end_km == 5.6
    assert section.max_elevation_m == 2800.0
    assert section.exposition_type == "GRAT"


def test_wind_exposition_risk_type_exists():
    """RiskType.WIND_EXPOSITION must exist."""
    from app.models import RiskType
    assert RiskType.WIND_EXPOSITION == "wind_exposition"


# --- 2. MetricCatalog ---

def test_wind_exposition_thresholds_in_catalog():
    """Wind and gust metrics must have exposition_risk_thresholds."""
    from app.metric_catalog import get_metric
    wind = get_metric("wind")
    gust = get_metric("gust")
    assert wind.exposition_risk_thresholds == {"medium": 30, "high": 50}
    assert gust.exposition_risk_thresholds == {"medium": 40, "high": 60}


# --- 3. WindExpositionService ---

def test_detect_exposed_sections_from_gpx():
    """detect_exposed_sections finds peaks above min_elevation as exposed."""
    from app.models import GPXPoint, GPXTrack
    from services.wind_exposition import WindExpositionService

    # Build a simple track: valley -> peak (2500m) -> valley
    points = []
    for i in range(200):
        km = i * 0.05  # 0 to 10 km
        # Peak at km=5.0 (index 100), elevation 2500m
        if i < 80:
            elev = 1000.0 + (i / 80) * 1500  # 1000 -> 2500
        elif i <= 120:
            elev = 2500.0 - abs(i - 100) * 12.5  # Peak at 100
        else:
            elev = 1000.0
        points.append(GPXPoint(lat=47.0, lon=12.0 + km * 0.001, elevation_m=elev, distance_from_start_km=km))

    track = GPXTrack(
        name="Test", points=points, waypoints=[],
        total_distance_km=10.0, total_ascent_m=1500.0, total_descent_m=1500.0,
    )

    svc = WindExpositionService()
    sections = svc.detect_exposed_sections(track, min_elevation_m=2000.0)
    assert len(sections) >= 1
    # The peak area around km=5.0 should be exposed
    assert any(s.start_km <= 5.0 <= s.end_km for s in sections)
    assert sections[0].exposition_type in ("GRAT", "PASS")


def test_detect_exposed_sections_below_threshold():
    """Peaks below min_elevation_m are NOT exposed."""
    from app.models import GPXPoint, GPXTrack
    from services.wind_exposition import WindExpositionService

    # All points below 2000m
    points = [
        GPXPoint(lat=47.0, lon=12.0, elevation_m=float(800 + i * 10), distance_from_start_km=i * 0.1)
        for i in range(100)
    ]
    track = GPXTrack(
        name="Low", points=points, waypoints=[],
        total_distance_km=10.0, total_ascent_m=500.0, total_descent_m=0.0,
    )

    svc = WindExpositionService()
    sections = svc.detect_exposed_sections(track, min_elevation_m=2000.0)
    assert sections == []


def test_detect_exposed_from_segments():
    """Segment-based detection: high-elevation segments are exposed."""
    from app.models import ExposedSection, GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment
    from services.wind_exposition import WindExpositionService

    high_seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=12.0, elevation_m=2200.0, distance_from_start_km=3.0),
        end_point=GPXPoint(lat=47.01, lon=12.01, elevation_m=2600.0, distance_from_start_km=5.0),
        start_time=datetime(2026, 2, 18, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=2.0, ascent_m=400.0, descent_m=0.0,
    )
    low_seg = TripSegment(
        segment_id=2,
        start_point=GPXPoint(lat=47.01, lon=12.01, elevation_m=1200.0, distance_from_start_km=5.0),
        end_point=GPXPoint(lat=47.02, lon=12.02, elevation_m=1000.0, distance_from_start_km=7.0),
        start_time=datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=2.0, ascent_m=0.0, descent_m=200.0,
    )

    svc = WindExpositionService()
    sections = svc.detect_exposed_from_segments([high_seg, low_seg])

    # Only the high segment should produce an exposed section
    assert len(sections) == 1
    assert sections[0].max_elevation_m == 2600.0


# --- 4. RiskEngine Rule 9 ---

def _make_segment_weather(wind_max=35.0, gust_max=45.0, elev_start=2200.0, elev_end=2600.0):
    """Helper to build a SegmentWeatherData with given wind/elevation."""
    from app.models import GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment

    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=12.0, elevation_m=elev_start, distance_from_start_km=3.0),
        end_point=GPXPoint(lat=47.01, lon=12.01, elevation_m=elev_end, distance_from_start_km=5.0),
        start_time=datetime(2026, 2, 18, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc),
        duration_hours=2.0, distance_km=2.0, ascent_m=400.0, descent_m=0.0,
    )
    agg = SegmentWeatherSummary(wind_max_kmh=wind_max, gust_max_kmh=gust_max)
    return SegmentWeatherData(
        segment=seg, timeseries=None, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def test_risk_engine_exposed_wind_moderate():
    """Wind 35 km/h on exposed ridge -> WIND_EXPOSITION MODERATE."""
    from app.models import ExposedSection, RiskLevel, RiskType
    from services.risk_engine import RiskEngine

    seg = _make_segment_weather(wind_max=35.0, gust_max=35.0)
    exposed = [ExposedSection(start_km=2.0, end_km=6.0, max_elevation_m=2600.0, exposition_type="GRAT")]

    engine = RiskEngine()
    assessment = engine.assess_segment(seg, exposed_sections=exposed)

    wind_expo_risks = [r for r in assessment.risks if r.type == RiskType.WIND_EXPOSITION]
    assert len(wind_expo_risks) == 1
    assert wind_expo_risks[0].level == RiskLevel.MODERATE


def test_risk_engine_exposed_wind_high():
    """Wind 55 km/h on exposed ridge -> WIND_EXPOSITION HIGH."""
    from app.models import ExposedSection, RiskLevel, RiskType
    from services.risk_engine import RiskEngine

    seg = _make_segment_weather(wind_max=55.0, gust_max=55.0)
    exposed = [ExposedSection(start_km=2.0, end_km=6.0, max_elevation_m=2600.0, exposition_type="GRAT")]

    engine = RiskEngine()
    assessment = engine.assess_segment(seg, exposed_sections=exposed)

    wind_expo_risks = [r for r in assessment.risks if r.type == RiskType.WIND_EXPOSITION]
    assert len(wind_expo_risks) == 1
    assert wind_expo_risks[0].level == RiskLevel.HIGH


def test_risk_engine_no_overlap_no_risk():
    """Segment does NOT overlap exposed section -> no WIND_EXPOSITION risk."""
    from app.models import ExposedSection, RiskType
    from services.risk_engine import RiskEngine

    seg = _make_segment_weather(wind_max=55.0, gust_max=55.0)
    # Exposed section is far away (km 10-12), segment is at km 3-5
    exposed = [ExposedSection(start_km=10.0, end_km=12.0, max_elevation_m=2600.0, exposition_type="GRAT")]

    engine = RiskEngine()
    assessment = engine.assess_segment(seg, exposed_sections=exposed)

    wind_expo_risks = [r for r in assessment.risks if r.type == RiskType.WIND_EXPOSITION]
    assert len(wind_expo_risks) == 0


def test_risk_engine_low_wind_no_exposition_risk():
    """Wind 20 km/h on exposed ridge -> no WIND_EXPOSITION (below 30 threshold)."""
    from app.models import ExposedSection, RiskType
    from services.risk_engine import RiskEngine

    seg = _make_segment_weather(wind_max=20.0, gust_max=20.0)
    exposed = [ExposedSection(start_km=2.0, end_km=6.0, max_elevation_m=2600.0, exposition_type="GRAT")]

    engine = RiskEngine()
    assessment = engine.assess_segment(seg, exposed_sections=exposed)

    wind_expo_risks = [r for r in assessment.risks if r.type == RiskType.WIND_EXPOSITION]
    assert len(wind_expo_risks) == 0


def test_risk_engine_without_exposed_sections_unchanged():
    """Without exposed_sections, RiskEngine behaves as before."""
    from app.models import RiskType
    from services.risk_engine import RiskEngine

    seg = _make_segment_weather(wind_max=35.0, gust_max=35.0)
    engine = RiskEngine()
    assessment = engine.assess_segment(seg)

    # 35 km/h is below normal wind threshold (50), so no wind risk
    wind_risks = [r for r in assessment.risks if r.type in (RiskType.WIND, RiskType.WIND_EXPOSITION)]
    assert len(wind_risks) == 0


# --- 5. Formatter Labels ---

def test_trip_report_wind_exposition_labels():
    """TripReportFormatter must have WIND_EXPOSITION labels."""
    from app.models import RiskLevel, RiskType
    from formatters.trip_report import TripReportFormatter

    labels = TripReportFormatter._RISK_LABELS
    assert (RiskType.WIND_EXPOSITION, RiskLevel.HIGH) in labels
    assert (RiskType.WIND_EXPOSITION, RiskLevel.MODERATE) in labels


def test_sms_trip_wind_exposition_labels():
    """SMSTripFormatter must have WIND_EXPOSITION labels."""
    from app.models import RiskLevel, RiskType
    from formatters.sms_trip import _SMS_RISK_LABELS

    assert (RiskType.WIND_EXPOSITION, RiskLevel.HIGH) in _SMS_RISK_LABELS
    assert (RiskType.WIND_EXPOSITION, RiskLevel.MODERATE) in _SMS_RISK_LABELS
    assert _SMS_RISK_LABELS[(RiskType.WIND_EXPOSITION, RiskLevel.HIGH)] == "GratSturm"
    assert _SMS_RISK_LABELS[(RiskType.WIND_EXPOSITION, RiskLevel.MODERATE)] == "GratWind"
