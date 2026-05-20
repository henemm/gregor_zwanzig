"""
Regressions-Tests für Bug #226:
compute_extended_metrics() muss dominant_wmo_code + dni_avg_wm2 aus basis_summary durchreichen.

Spec: docs/specs/modules/bug_226_dni_wmo_passthrough.md
"""
from datetime import datetime, timezone

import pytest

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherSummary,
    ThunderLevel,
)
from services.weather_metrics import WeatherMetricsService


@pytest.fixture
def service():
    return WeatherMetricsService()


@pytest.fixture
def minimal_timeseries():
    """Minimale Timeseries — reicht für compute_extended_metrics()."""
    meta = ForecastMeta(
        provider=Provider.GEOSPHERE,
        model="test",
        run=datetime.now(timezone.utc),
        grid_res_km=1.0,
        interp="test",
    )
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
            t2m_c=15.0,
        )
    ]
    return NormalizedTimeseries(meta=meta, data=data)


@pytest.fixture
def basis_summary_with_dni_wmo():
    """Basis-Summary mit gesetztem dominant_wmo_code und dni_avg_wm2."""
    return SegmentWeatherSummary(
        temp_min_c=10.0,
        temp_max_c=20.0,
        temp_avg_c=15.0,
        wind_max_kmh=25.0,
        gust_max_kmh=35.0,
        precip_sum_mm=3.5,
        cloud_avg_pct=50,
        humidity_avg_pct=70,
        thunder_level_max=ThunderLevel.NONE,
        visibility_min_m=5000,
        dominant_wmo_code=80,
        dni_avg_wm2=250.0,
        aggregation_config={
            "temp_min_c": "min",
            "temp_max_c": "max",
            "temp_avg_c": "avg",
            "wind_max_kmh": "max",
            "gust_max_kmh": "max",
            "precip_sum_mm": "sum",
            "cloud_avg_pct": "avg",
            "humidity_avg_pct": "avg",
            "thunder_level_max": "max",
            "visibility_min_m": "min",
            "dominant_wmo_code": "max_wmo_severity",
            "dni_avg_wm2": "avg",
        },
    )


@pytest.fixture
def basis_summary_none():
    """Basis-Summary mit dominant_wmo_code=None und dni_avg_wm2=None (Standardfall)."""
    return SegmentWeatherSummary(
        temp_min_c=10.0,
        temp_max_c=20.0,
        temp_avg_c=15.0,
        wind_max_kmh=25.0,
        gust_max_kmh=35.0,
        precip_sum_mm=3.5,
        cloud_avg_pct=50,
        humidity_avg_pct=70,
        thunder_level_max=ThunderLevel.NONE,
        visibility_min_m=5000,
        dominant_wmo_code=None,
        dni_avg_wm2=None,
        aggregation_config={
            "temp_min_c": "min",
            "temp_max_c": "max",
            "temp_avg_c": "avg",
            "wind_max_kmh": "max",
            "gust_max_kmh": "max",
            "precip_sum_mm": "sum",
            "cloud_avg_pct": "avg",
            "humidity_avg_pct": "avg",
            "thunder_level_max": "max",
            "visibility_min_m": "min",
            "dominant_wmo_code": "max_wmo_severity",
            "dni_avg_wm2": "avg",
        },
    )


def test_ac1_dominant_wmo_code_passthrough(
    service, minimal_timeseries, basis_summary_with_dni_wmo
):
    """
    AC-1: GIVEN basis_summary mit dominant_wmo_code=80
    WHEN compute_extended_metrics() aufgerufen
    THEN gibt result.dominant_wmo_code == 80 zurück
    """
    result = service.compute_extended_metrics(
        minimal_timeseries, basis_summary_with_dni_wmo
    )
    assert result.dominant_wmo_code == 80, (
        f"Bug #226: dominant_wmo_code wurde nicht durchgereicht "
        f"(erwartet 80, bekommen {result.dominant_wmo_code})"
    )


def test_ac2_dni_avg_wm2_passthrough(
    service, minimal_timeseries, basis_summary_with_dni_wmo
):
    """
    AC-2: GIVEN basis_summary mit dni_avg_wm2=250.0
    WHEN compute_extended_metrics() aufgerufen
    THEN gibt result.dni_avg_wm2 == 250.0 zurück
    """
    result = service.compute_extended_metrics(
        minimal_timeseries, basis_summary_with_dni_wmo
    )
    assert result.dni_avg_wm2 == 250.0, (
        f"Bug #226: dni_avg_wm2 wurde nicht durchgereicht "
        f"(erwartet 250.0, bekommen {result.dni_avg_wm2})"
    )


def test_ac3_none_fields_remain_none(
    service, minimal_timeseries, basis_summary_none
):
    """
    AC-3: GIVEN basis_summary mit dominant_wmo_code=None + dni_avg_wm2=None
    WHEN compute_extended_metrics() aufgerufen
    THEN bleiben beide Felder None (kein Regression)
    """
    result = service.compute_extended_metrics(minimal_timeseries, basis_summary_none)
    assert result.dominant_wmo_code is None, (
        f"Bug #226: dominant_wmo_code sollte None bleiben, ist aber {result.dominant_wmo_code}"
    )
    assert result.dni_avg_wm2 is None, (
        f"Bug #226: dni_avg_wm2 sollte None bleiben, ist aber {result.dni_avg_wm2}"
    )
