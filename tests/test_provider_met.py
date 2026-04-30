import json
import pytest
from pathlib import Path
from jsonschema import validate


@pytest.fixture
def met_api_response():
    """Load MET API fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures/providers/met_locationforecast_compact.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def expected_normalized():
    """Load expected normalized output fixture."""
    fixture_path = Path(__file__).parent.parent / "fixtures/providers/met_normalized_expected.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def schema():
    """Load JSON schema."""
    schema_path = Path(__file__).parent.parent / "schemas/normalized_timeseries.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_normalize_met_response(met_api_response, expected_normalized, schema):
    """Test normalization of MET API response to schema-compliant format."""
    from app.providers.met import normalize

    result = normalize(met_api_response)

    # Validate against schema
    validate(instance=result, schema=schema)

    # Check meta fields
    assert result["meta"]["provider"] == "MET"
    assert result["meta"]["model"] == "ECMWF"
    assert result["meta"]["run"] == "2025-08-29T06:15:00Z"
    assert result["meta"]["grid_res_km"] == 9
    assert result["meta"]["interp"] == "point_grid"

    # Check data length
    assert len(result["data"]) == 4

    # Check first data point in detail
    first = result["data"][0]
    expected_first = expected_normalized["data"][0]

    assert first["ts"] == expected_first["ts"]
    assert first["t2m_c"] == expected_first["t2m_c"]
    assert first["wind10m_kmh"] == pytest.approx(expected_first["wind10m_kmh"], abs=0.1)
    assert first["gust_kmh"] == pytest.approx(expected_first["gust_kmh"], abs=0.1)
    assert first["precip_rate_mmph"] == expected_first["precip_rate_mmph"]
    assert first["precip_1h_mm"] == expected_first["precip_1h_mm"]
    assert first["cloud_total_pct"] == expected_first["cloud_total_pct"]
    assert first["symbol"] == expected_first["symbol"]
    assert first["thunder_level"] == expected_first["thunder_level"]
    assert first["pressure_msl_hpa"] == expected_first["pressure_msl_hpa"]
    assert first["humidity_pct"] == expected_first["humidity_pct"]


def test_symbol_mapping():
    """Test MET symbol_code to normalized symbol mapping."""
    from app.providers.met import map_symbol

    # Direct mapping (no suffix)
    assert map_symbol("lightrain") == "lightrain"
    assert map_symbol("heavyrain") == "heavyrain"
    assert map_symbol("clearsky_day") == "clearsky"
    assert map_symbol("clearsky_night") == "clearsky"
    assert map_symbol("partlycloudy_day") == "partlycloudy"
    assert map_symbol("partlycloudy_night") == "partlycloudy"

    # Thunder variants
    assert map_symbol("lightrainandthunder") == "lightrainandthunder"
    assert map_symbol("heavyrainandthunder") == "heavyrainandthunder"


def test_thunder_level_detection():
    """Test thunder_level detection from symbol_code."""
    from app.providers.met import get_thunder_level

    # HIGH when symbol contains "thunder"
    assert get_thunder_level("lightrainandthunder") == "HIGH"
    assert get_thunder_level("heavyrainandthunder") == "HIGH"
    assert get_thunder_level("thunderstorm") == "HIGH"

    # NONE otherwise
    assert get_thunder_level("lightrain") == "NONE"
    assert get_thunder_level("heavyrain") == "NONE"
    assert get_thunder_level("clearsky_day") == "NONE"


def test_unit_conversions():
    """Test m/s to km/h conversions."""
    from app.providers.met import ms_to_kmh

    assert ms_to_kmh(6.1) == pytest.approx(22.0, abs=0.1)
    assert ms_to_kmh(10.6) == pytest.approx(38.2, abs=0.1)
    assert ms_to_kmh(0.0) == 0.0
