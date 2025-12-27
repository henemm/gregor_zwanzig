"""Tests for provider base module."""
import pytest

from providers.base import (
    WeatherProvider,
    ProviderError,
    ProviderNotFoundError,
    ProviderRequestError,
    get_provider,
    available_providers,
)
from providers.geosphere import GeoSphereProvider


class TestWeatherProviderProtocol:
    """Tests for WeatherProvider protocol compliance."""

    def test_geosphere_implements_protocol(self):
        """GeoSphereProvider implements WeatherProvider protocol."""
        provider = GeoSphereProvider()
        assert isinstance(provider, WeatherProvider)

    def test_geosphere_has_name_property(self):
        """GeoSphereProvider has name property."""
        provider = GeoSphereProvider()
        assert provider.name == "geosphere"

    def test_geosphere_has_fetch_forecast_method(self):
        """GeoSphereProvider has fetch_forecast method."""
        provider = GeoSphereProvider()
        assert hasattr(provider, "fetch_forecast")
        assert callable(provider.fetch_forecast)


class TestProviderFactory:
    """Tests for provider factory function."""

    def test_get_provider_geosphere(self):
        """get_provider returns GeoSphereProvider for 'geosphere'."""
        provider = get_provider("geosphere")
        assert isinstance(provider, GeoSphereProvider)
        assert provider.name == "geosphere"

    def test_get_provider_unknown_raises(self):
        """get_provider raises for unknown provider."""
        with pytest.raises(ProviderNotFoundError) as exc_info:
            get_provider("unknown")
        assert "unknown" in str(exc_info.value).lower()

    def test_available_providers(self):
        """available_providers returns list of provider names."""
        providers = available_providers()
        assert isinstance(providers, list)
        assert "geosphere" in providers


class TestProviderErrors:
    """Tests for provider error classes."""

    def test_provider_error_formatting(self):
        """ProviderError formats message with provider name."""
        error = ProviderError("test", "Something went wrong")
        assert "[test]" in str(error)
        assert "Something went wrong" in str(error)

    def test_provider_not_found_error(self):
        """ProviderNotFoundError message."""
        error = ProviderNotFoundError("unknown")
        assert "unknown" in str(error).lower()

    def test_provider_request_error(self):
        """ProviderRequestError inherits from ProviderError."""
        error = ProviderRequestError("geosphere", "HTTP 500")
        assert isinstance(error, ProviderError)
        assert "[geosphere]" in str(error)
