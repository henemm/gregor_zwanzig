"""
WEATHER-06: UV-Index via Air Quality API
TDD RED - Tests for UV integration from OpenMeteo Air Quality API (CAMS).

All tests use REAL API calls (no mocks!) per CLAUDE.md.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest


class TestRequestBaseHostOverride:
    """Verify _request() accepts and uses optional base_host parameter."""

    def test_request_signature_accepts_base_host(self) -> None:
        """_request() must accept a base_host keyword argument (backward compat)."""
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        # base_host=None should fall back to BASE_HOST (weather API)
        result = provider._request(
            "/v1/dwd-icon",
            {"latitude": 50.0, "longitude": 10.0, "hourly": "temperature_2m", "timezone": "UTC"},
            base_host=None,
        )
        # If base_host param doesn't exist, this raises TypeError
        assert isinstance(result, dict)
        assert "hourly" in result

    def test_request_uses_custom_base_host(self) -> None:
        """_request() with base_host should call the AQ API, not weather API."""
        from providers.openmeteo import OpenMeteoProvider, AIR_QUALITY_HOST

        provider = OpenMeteoProvider()
        assert AIR_QUALITY_HOST == "https://air-quality-api.open-meteo.com"

        result = provider._request(
            "/v1/air-quality",
            {"latitude": 50.0, "longitude": 10.0, "hourly": "uv_index", "timezone": "UTC"},
            base_host=AIR_QUALITY_HOST,
        )
        assert "hourly" in result
        assert "uv_index" in result["hourly"]


class TestFetchUvData:
    """Verify _fetch_uv_data() helper method."""

    def test_fetch_uv_data_exists(self) -> None:
        """_fetch_uv_data() method must exist on OpenMeteoProvider."""
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        assert hasattr(provider, "_fetch_uv_data")
        assert callable(provider._fetch_uv_data)

    def test_fetch_uv_data_returns_dict(self) -> None:
        """_fetch_uv_data() returns dict with hourly.uv_index for valid coords."""
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        now = datetime.now(tz=timezone.utc)
        result = provider._fetch_uv_data(
            39.77, 2.71, now, now + timedelta(days=1),
        )

        assert result is not None
        assert "hourly" in result
        assert "uv_index" in result["hourly"]
        uv_vals = result["hourly"]["uv_index"]
        assert isinstance(uv_vals, list)
        assert len(uv_vals) > 0

    def test_fetch_uv_data_values_plausible(self) -> None:
        """UV values from AQ API must be in WHO range 0-15."""
        from providers.openmeteo import OpenMeteoProvider

        provider = OpenMeteoProvider()
        now = datetime.now(tz=timezone.utc)
        result = provider._fetch_uv_data(39.77, 2.71, now, now + timedelta(days=1))

        assert result is not None
        uv_vals = [v for v in result["hourly"]["uv_index"] if v is not None]
        assert len(uv_vals) > 0
        for v in uv_vals:
            assert 0.0 <= v <= 15.0, f"UV value {v} out of plausible range"


class TestFetchForecastUvIntegration:
    """Verify UV is populated in fetch_forecast() via AQ API."""

    def test_forecast_has_uv_values(self) -> None:
        """fetch_forecast() must return timeseries with UV populated from AQ API."""
        from providers.openmeteo import OpenMeteoProvider
        from app.config import Location

        provider = OpenMeteoProvider()
        location = Location(latitude=39.77, longitude=2.71, name="Mallorca")
        now = datetime.now(tz=timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        timeseries = provider.fetch_forecast(location, start, end)

        uv_vals = [dp.uv_index for dp in timeseries.data if dp.uv_index is not None]
        assert len(uv_vals) > 0, "UV should be populated from Air Quality API"

    def test_forecast_uv_plausible(self) -> None:
        """UV values in timeseries must be in range 0-15."""
        from providers.openmeteo import OpenMeteoProvider
        from app.config import Location

        provider = OpenMeteoProvider()
        location = Location(latitude=39.77, longitude=2.71, name="Mallorca")
        now = datetime.now(tz=timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        timeseries = provider.fetch_forecast(location, start, end)

        for dp in timeseries.data:
            if dp.uv_index is not None:
                assert 0.0 <= dp.uv_index <= 15.0, f"UV {dp.uv_index} out of range at {dp.ts}"

    def test_weather_05b_fallback_still_works_with_uv(self, tmp_path, monkeypatch) -> None:
        """WEATHER-05b fallback (visibility etc.) must still work alongside UV fetch."""
        import providers.openmeteo as om
        fake_cache = tmp_path / "model_availability.json"
        monkeypatch.setattr(om, "AVAILABILITY_CACHE_PATH", fake_cache)

        from providers.openmeteo import OpenMeteoProvider
        from app.config import Location

        cache = {
            "probe_date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
            "models": {
                "meteofrance_arome": {
                    "available": ["temperature_2m"],
                    "unavailable": ["visibility"],
                },
                "icon_eu": {
                    "available": ["temperature_2m", "visibility"],
                    "unavailable": [],
                },
            },
        }
        fake_cache.write_text(json.dumps(cache))

        provider = OpenMeteoProvider()
        location = Location(latitude=39.77, longitude=2.71, name="Mallorca")
        now = datetime.now(tz=timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        timeseries = provider.fetch_forecast(location, start, end)

        uv_vals = [dp.uv_index for dp in timeseries.data if dp.uv_index is not None]
        assert len(uv_vals) > 0, "UV should still work alongside fallback"

        assert timeseries.data is not None
        assert len(timeseries.data) > 0
