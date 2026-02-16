"""
Unit Tests: OpenMeteo Endpoint Routing

SPEC: docs/specs/bugfix/openmeteo_endpoint_routing.md v1.0
PHASE: TDD RED — all tests MUST FAIL with current (buggy) code.

Tests verify that OpenMeteo provider uses dedicated model-specific endpoints
instead of the generic /v1/forecast endpoint which ignores the model parameter.

Dedicated endpoints:
- /v1/meteofrance → AROME (Mallorca, France, Western Alps)
- /v1/dwd-icon   → ICON-D2/ICON-EU (Germany, Alps, Europe)
- /v1/metno      → MetNo Nordic (Scandinavia)
- /v1/ecmwf      → ECMWF IFS (global fallback)
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "src")


class TestSelectModelReturnsCorrectEndpoint:
    """Test 1: select_model() must return (model_id, grid_res_km, endpoint)."""

    def test_mallorca_returns_meteofrance_endpoint(self):
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        result = provider.select_model(39.77, 2.72)

        # Must return 3-tuple (not 2-tuple as current buggy code)
        assert len(result) == 3, (
            f"select_model() returned {len(result)}-tuple, expected 3-tuple "
            f"(model_id, grid_res_km, endpoint)"
        )
        model_id, grid_res, endpoint = result
        assert model_id == "meteofrance_arome"
        assert endpoint == "/v1/meteofrance"
        assert grid_res == 1.3

    def test_munich_returns_dwd_icon_endpoint(self):
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        model_id, grid_res, endpoint = provider.select_model(48.14, 11.58)
        assert model_id == "icon_d2"
        assert endpoint == "/v1/dwd-icon"
        assert grid_res == 2.0

    def test_oslo_returns_metno_endpoint(self):
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        model_id, grid_res, endpoint = provider.select_model(59.91, 10.75)
        assert model_id == "metno_nordic"
        assert endpoint == "/v1/metno"
        assert grid_res == 1.0

    def test_athens_returns_icon_eu_endpoint(self):
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        model_id, grid_res, endpoint = provider.select_model(37.98, 23.73)
        assert model_id == "icon_eu"
        assert endpoint == "/v1/dwd-icon"
        assert grid_res == 7.0

    def test_tokyo_returns_ecmwf_endpoint(self):
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        model_id, grid_res, endpoint = provider.select_model(35.68, 139.69)
        assert model_id == "ecmwf_ifs04"
        assert endpoint == "/v1/ecmwf"
        assert grid_res == 40.0


class TestDedicatedEndpointReturnsValidData:
    """Test 2: Real API call to dedicated endpoint must return valid data."""

    def test_meteofrance_endpoint_returns_hourly_data(self):
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        params = {
            "latitude": 39.77,
            "longitude": 2.72,
            "hourly": "temperature_2m,wind_gusts_10m,cloud_cover",
            "timezone": "UTC",
        }

        # Real API call to dedicated meteofrance endpoint
        data = provider._request("/v1/meteofrance", params)

        assert "hourly" in data
        assert "temperature_2m" in data["hourly"]
        assert "wind_gusts_10m" in data["hourly"]
        assert len(data["hourly"]["temperature_2m"]) >= 24


class TestModelDataDiffersBetweenEndpoints:
    """Test 3: CRITICAL REGRESSION TEST.

    Dedicated endpoints must return different model data.
    If /v1/forecast is accidentally reintroduced, this catches it because
    all models would return identical (wrong) data.
    """

    def test_arome_differs_from_icon(self):
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        params = {
            "latitude": 39.77,
            "longitude": 2.72,
            "hourly": "temperature_2m,wind_gusts_10m,cloud_cover",
            "timezone": "UTC",
        }

        # Fetch from two different dedicated endpoints
        data_france = provider._request("/v1/meteofrance", params)
        data_icon = provider._request("/v1/dwd-icon", params)

        # Compare first 12 hours of temperature
        t_france = data_france["hourly"]["temperature_2m"][:12]
        t_icon = data_icon["hourly"]["temperature_2m"][:12]

        g_france = data_france["hourly"]["wind_gusts_10m"][:12]
        g_icon = data_icon["hourly"]["wind_gusts_10m"][:12]

        # At least one metric MUST differ (different models, different data)
        assert t_france != t_icon or g_france != g_icon, (
            "REGRESSION: /v1/meteofrance and /v1/dwd-icon return identical data! "
            "Likely using generic /v1/forecast instead of dedicated endpoints."
        )


class TestBaseHostHasNoPath:
    """Test 4: BASE_HOST must be host-only, no API path."""

    def test_no_forecast_path_in_base(self):
        """After fix: BASE_HOST = 'https://api.open-meteo.com' (no /v1/...)."""
        try:
            from providers.openmeteo import BASE_HOST
        except ImportError:
            # Current buggy code exports BASE_URL, not BASE_HOST
            pytest.fail(
                "BASE_HOST not found in providers.openmeteo. "
                "Still using BASE_URL with hardcoded /v1/forecast path?"
            )

        assert BASE_HOST == "https://api.open-meteo.com", (
            f"BASE_HOST should be host-only, got: {BASE_HOST}"
        )
        assert "/v1/" not in BASE_HOST, (
            "REGRESSION: BASE_HOST contains API path! "
            "Use dedicated endpoints via REGIONAL_MODELS."
        )


class TestAllRegionalModelsHaveEndpoint:
    """Test 5: Every REGIONAL_MODELS entry must have a valid endpoint field."""

    def test_endpoint_field_exists(self):
        from providers.openmeteo import REGIONAL_MODELS

        for model in REGIONAL_MODELS:
            assert "endpoint" in model, (
                f"Model '{model['id']}' missing 'endpoint' field"
            )

    def test_endpoint_starts_with_v1(self):
        from providers.openmeteo import REGIONAL_MODELS

        for model in REGIONAL_MODELS:
            if "endpoint" not in model:
                pytest.skip("endpoint field missing (tested separately)")
            assert model["endpoint"].startswith("/v1/"), (
                f"Model '{model['id']}' has invalid endpoint: {model['endpoint']}"
            )

    def test_endpoint_not_generic_forecast(self):
        from providers.openmeteo import REGIONAL_MODELS

        for model in REGIONAL_MODELS:
            if "endpoint" not in model:
                pytest.skip("endpoint field missing (tested separately)")
            assert model["endpoint"] != "/v1/forecast", (
                f"Model '{model['id']}' uses generic /v1/forecast endpoint! "
                f"Use dedicated endpoint (e.g., /v1/meteofrance, /v1/dwd-icon)."
            )
