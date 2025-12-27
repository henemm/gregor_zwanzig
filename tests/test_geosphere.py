"""Tests for GeoSphere provider."""
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from app.models import PrecipType, Provider
from providers.geosphere import (
    GeoSphereProvider,
    _calculate_wind_chill,
    _precip_type_from_code,
    _vector_to_speed_kmh,
)


# --- Unit tests for helper functions ---

def test_vector_to_speed_kmh():
    """Test wind vector to speed conversion."""
    # Pure east wind 10 m/s = 36 km/h
    assert _vector_to_speed_kmh(10, 0) == 36.0
    # Pure north wind 10 m/s = 36 km/h
    assert _vector_to_speed_kmh(0, 10) == 36.0
    # Diagonal wind (should be sqrt(2) * 10 * 3.6)
    speed = _vector_to_speed_kmh(10, 10)
    assert 50.0 < speed < 51.0  # ~50.9 km/h
    # Zero wind
    assert _vector_to_speed_kmh(0, 0) == 0.0


def test_calculate_wind_chill():
    """Test wind chill calculation."""
    # No wind chill above 10C
    assert _calculate_wind_chill(15.0, 20.0) == 15.0
    # No wind chill with low wind
    assert _calculate_wind_chill(5.0, 3.0) == 5.0
    # Typical winter conditions
    wc = _calculate_wind_chill(-5.0, 30.0)
    assert wc < -5.0  # Should feel colder
    assert -15.0 < wc < -10.0  # Reasonable range
    # Extreme cold
    wc_extreme = _calculate_wind_chill(-20.0, 50.0)
    assert wc_extreme < -30.0


def test_precip_type_from_code():
    """Test precipitation type code conversion."""
    assert _precip_type_from_code(None) is None
    assert _precip_type_from_code(0) is None
    assert _precip_type_from_code(1) == PrecipType.RAIN
    assert _precip_type_from_code(2) == PrecipType.SNOW
    assert _precip_type_from_code(3) == PrecipType.MIXED
    assert _precip_type_from_code(4) == PrecipType.FREEZING_RAIN
    assert _precip_type_from_code(99) is None  # Unknown code


# --- Mock response data ---

MOCK_NWP_RESPONSE = {
    "timestamps": [
        "2025-12-27T12:00+00:00",
        "2025-12-27T13:00+00:00",
    ],
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [11.5, 47.0]},
            "properties": {
                "parameters": {
                    "t2m": {"data": [-5.0, -4.5]},
                    "u10m": {"data": [2.0, 2.5]},
                    "v10m": {"data": [3.0, 3.5]},
                    "ugust": {"data": [5.0, 6.0]},
                    "vgust": {"data": [7.0, 8.0]},
                    "rr_acc": {"data": [0.0, 0.5]},
                    "snow_acc": {"data": [0.0, 5.0]},
                    "snowlmt": {"data": [1500, 1400]},
                    "tcc": {"data": [0.8, 0.9]},
                    "rh2m": {"data": [85, 90]},
                    "sp": {"data": [85000, 84900]},
                }
            },
        }
    ],
}

MOCK_SNOWGRID_RESPONSE = {
    "timestamps": ["2025-12-27T00:00+00:00"],
    "features": [
        {
            "properties": {
                "parameters": {
                    "snow_depth": {"data": [1.2]},  # 1.2m = 120cm
                    "swe_tot": {"data": [250.0]},
                }
            }
        }
    ],
}


# --- Integration tests with mocked HTTP ---

@pytest.fixture
def mock_client():
    """Create a mock HTTP client."""
    return Mock()


def test_parse_nwp_response():
    """Test parsing of NWP response."""
    provider = GeoSphereProvider()
    ts = provider._parse_nwp_response(MOCK_NWP_RESPONSE)

    assert ts.meta.provider == Provider.GEOSPHERE
    assert ts.meta.model == "AROME"
    assert ts.meta.grid_res_km == 2.5
    assert len(ts.data) == 2

    # Check first data point
    dp0 = ts.data[0]
    assert dp0.t2m_c == -5.0
    assert dp0.wind10m_kmh > 0  # Calculated from u/v
    assert dp0.gust_kmh > dp0.wind10m_kmh  # Gusts should be higher
    assert dp0.snowfall_limit_m == 1500
    assert dp0.cloud_total_pct == 80  # 0.8 * 100
    assert dp0.humidity_pct == 85
    assert dp0.pressure_msl_hpa == 850.0  # 85000 Pa / 100

    # Check wind chill calculated
    assert dp0.wind_chill_c is not None
    assert dp0.wind_chill_c < dp0.t2m_c  # Should feel colder

    provider.close()


def test_parse_snowgrid_response():
    """Test parsing of SNOWGRID response."""
    provider = GeoSphereProvider()
    snow_depth, swe = provider._parse_snowgrid_response(MOCK_SNOWGRID_RESPONSE)

    assert snow_depth == 120.0  # 1.2m * 100
    assert swe == 250.0

    provider.close()


def test_parse_empty_response():
    """Test handling of empty response."""
    provider = GeoSphereProvider()

    with pytest.raises(ValueError, match="No data"):
        provider._parse_nwp_response({"features": []})

    snow_depth, swe = provider._parse_snowgrid_response({"features": []})
    assert snow_depth is None
    assert swe is None

    provider.close()


@patch("providers.geosphere.httpx.Client")
def test_fetch_nwp_forecast(mock_client_class):
    """Test fetch_nwp_forecast with mocked HTTP."""
    mock_response = Mock()
    mock_response.json.return_value = MOCK_NWP_RESPONSE
    mock_response.raise_for_status = Mock()

    mock_client = Mock()
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client

    with GeoSphereProvider() as provider:
        provider._client = mock_client
        ts = provider.fetch_nwp_forecast(47.0, 11.5)

        assert ts.meta.provider == Provider.GEOSPHERE
        assert len(ts.data) == 2
        mock_client.get.assert_called_once()


@patch("providers.geosphere.httpx.Client")
def test_fetch_combined(mock_client_class):
    """Test fetch_combined merges NWP and SNOWGRID data."""
    mock_client = Mock()

    # First call: NWP, Second call: SNOWGRID
    mock_nwp_response = Mock()
    mock_nwp_response.json.return_value = MOCK_NWP_RESPONSE
    mock_nwp_response.raise_for_status = Mock()

    mock_snow_response = Mock()
    mock_snow_response.json.return_value = MOCK_SNOWGRID_RESPONSE
    mock_snow_response.raise_for_status = Mock()

    mock_client.get.side_effect = [mock_nwp_response, mock_snow_response]
    mock_client_class.return_value = mock_client

    with GeoSphereProvider() as provider:
        provider._client = mock_client
        ts = provider.fetch_combined(47.0, 11.5, include_snow=True)

        assert len(ts.data) == 2
        # Snow depth should be added to all data points
        assert ts.data[0].snow_depth_cm == 120.0
        assert ts.data[1].snow_depth_cm == 120.0
        assert ts.data[0].swe_kgm2 == 250.0
