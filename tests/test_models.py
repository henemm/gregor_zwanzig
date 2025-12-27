"""Tests for data models."""
from datetime import datetime, timezone

from app.models import (
    AvalancheDanger,
    AvalancheProblem,
    AvalancheProblemInfo,
    AvalancheReport,
    AvalancheReportMeta,
    DangerTrend,
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    PrecipType,
    Provider,
    Risk,
    RiskAssessment,
    RiskLevel,
    RiskType,
    ThunderLevel,
)


def test_provider_enum():
    """Test Provider enum includes all expected values."""
    assert Provider.MOSMIX.value == "MOSMIX"
    assert Provider.GEOSPHERE.value == "GEOSPHERE"
    assert Provider.SLF.value == "SLF"
    assert Provider.EUREGIO.value == "EUREGIO"


def test_forecast_data_point_base_fields():
    """Test ForecastDataPoint with base fields."""
    ts = datetime(2025, 12, 27, 12, 0, tzinfo=timezone.utc)
    dp = ForecastDataPoint(
        ts=ts,
        t2m_c=5.0,
        wind10m_kmh=20.0,
        gust_kmh=35.0,
    )
    assert dp.ts == ts
    assert dp.t2m_c == 5.0
    assert dp.wind10m_kmh == 20.0
    assert dp.snow_depth_cm is None  # Optional field


def test_forecast_data_point_wintersport_fields():
    """Test ForecastDataPoint with wintersport fields."""
    ts = datetime(2025, 12, 27, 12, 0, tzinfo=timezone.utc)
    dp = ForecastDataPoint(
        ts=ts,
        t2m_c=-5.0,
        snow_depth_cm=120.0,
        snow_new_24h_cm=25.0,
        snowfall_limit_m=1800,
        precip_type=PrecipType.SNOW,
        wind_chill_c=-15.0,
    )
    assert dp.snow_depth_cm == 120.0
    assert dp.snow_new_24h_cm == 25.0
    assert dp.snowfall_limit_m == 1800
    assert dp.precip_type == PrecipType.SNOW
    assert dp.wind_chill_c == -15.0


def test_normalized_timeseries():
    """Test NormalizedTimeseries creation."""
    meta = ForecastMeta(
        provider=Provider.GEOSPHERE,
        model="AROME",
        run=datetime(2025, 12, 27, 6, 0, tzinfo=timezone.utc),
        grid_res_km=2.5,
        interp="bilinear",
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2025, 12, 27, 12, 0, tzinfo=timezone.utc),
            t2m_c=-3.0,
        ),
        ForecastDataPoint(
            ts=datetime(2025, 12, 27, 13, 0, tzinfo=timezone.utc),
            t2m_c=-2.0,
        ),
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)

    assert ts.meta.provider == Provider.GEOSPHERE
    assert ts.meta.model == "AROME"
    assert len(ts.data) == 2


def test_avalanche_report():
    """Test AvalancheReport creation."""
    meta = AvalancheReportMeta(
        provider=Provider.EUREGIO,
        region_id="AT-07",
        region_name="Tirol",
        valid_from=datetime(2025, 12, 27, 17, 0, tzinfo=timezone.utc),
        valid_to=datetime(2025, 12, 28, 17, 0, tzinfo=timezone.utc),
        published=datetime(2025, 12, 27, 16, 0, tzinfo=timezone.utc),
    )
    danger = AvalancheDanger(
        level=3,
        level_text="erheblich",
        elevation_above_m=2000,
        level_below=2,
        trend=DangerTrend.STEADY,
    )
    problems = [
        AvalancheProblemInfo(
            type=AvalancheProblem.WIND_SLAB,
            aspects=["N", "NE", "NW"],
            elevation_from_m=2000,
            elevation_to_m=3000,
        )
    ]
    report = AvalancheReport(meta=meta, danger=danger, problems=problems)

    assert report.meta.region_id == "AT-07"
    assert report.danger.level == 3
    assert report.danger.trend == DangerTrend.STEADY
    assert len(report.problems) == 1
    assert report.problems[0].type == AvalancheProblem.WIND_SLAB


def test_risk_assessment():
    """Test RiskAssessment with multiple risks."""
    risks = [
        Risk(
            type=RiskType.AVALANCHE,
            level=RiskLevel.HIGH,
            danger_level=4,
            problems=["wind_slab", "new_snow"],
        ),
        Risk(
            type=RiskType.WIND_CHILL,
            level=RiskLevel.MODERATE,
            feels_like_c=-18.0,
        ),
        Risk(
            type=RiskType.SNOWFALL,
            level=RiskLevel.MODERATE,
            amount_cm=25.0,
            from_time=datetime(2025, 12, 27, 18, 0, tzinfo=timezone.utc),
        ),
    ]
    assessment = RiskAssessment(risks=risks)

    assert len(assessment.risks) == 3
    assert assessment.risks[0].type == RiskType.AVALANCHE
    assert assessment.risks[0].danger_level == 4
    assert assessment.risks[1].feels_like_c == -18.0
