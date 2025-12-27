"""Tests for service layer."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.config import Location
from app.debug import DebugBuffer
from app.models import ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider
from services.forecast import ForecastService


class TestForecastService:
    """Tests for ForecastService."""

    def _create_mock_provider(self):
        """Create a mock weather provider."""
        provider = MagicMock()
        provider.name = "mock"
        provider.fetch_forecast.return_value = NormalizedTimeseries(
            meta=ForecastMeta(
                provider=Provider.GEOSPHERE,
                model="TEST",
                run=datetime.now(timezone.utc),
                grid_res_km=1.0,
                interp="bilinear",
            ),
            data=[
                ForecastDataPoint(
                    ts=datetime.now(timezone.utc),
                    t2m_c=5.0,
                    wind10m_kmh=10.0,
                )
            ],
        )
        return provider

    def test_service_init(self):
        """ForecastService can be initialized with provider."""
        provider = self._create_mock_provider()
        service = ForecastService(provider)
        assert service.provider_name == "mock"

    def test_service_init_with_debug(self):
        """ForecastService accepts optional debug buffer."""
        provider = self._create_mock_provider()
        debug = DebugBuffer()
        service = ForecastService(provider, debug)
        assert service.debug is debug

    def test_service_creates_debug_if_none(self):
        """ForecastService creates debug buffer if not provided."""
        provider = self._create_mock_provider()
        service = ForecastService(provider)
        assert isinstance(service.debug, DebugBuffer)

    def test_get_forecast(self):
        """get_forecast calls provider and returns data."""
        provider = self._create_mock_provider()
        service = ForecastService(provider)
        location = Location(latitude=47.0, longitude=11.5)

        result = service.get_forecast(location, hours_ahead=24)

        provider.fetch_forecast.assert_called_once()
        assert isinstance(result, NormalizedTimeseries)
        assert len(result.data) == 1

    def test_get_forecast_logs_debug(self):
        """get_forecast logs to debug buffer."""
        provider = self._create_mock_provider()
        debug = DebugBuffer()
        service = ForecastService(provider, debug)
        location = Location(latitude=47.0, longitude=11.5)

        service.get_forecast(location)

        debug_text = debug.as_text()
        assert "mock" in debug_text  # provider name
        assert "47.0" in debug_text  # location

    def test_get_current(self):
        """get_current is shorthand for 3-hour forecast."""
        provider = self._create_mock_provider()
        service = ForecastService(provider)
        location = Location(latitude=47.0, longitude=11.5)

        result = service.get_current(location)

        assert isinstance(result, NormalizedTimeseries)
        # Verify it was called with short range
        call_args = provider.fetch_forecast.call_args
        assert call_args is not None
