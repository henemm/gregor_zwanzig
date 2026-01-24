"""
Weather provider protocol and factory.

Defines the interface that all weather providers must implement,
enabling easy extension with new data sources.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.config import Location
    from app.models import NormalizedTimeseries


@runtime_checkable
class WeatherProvider(Protocol):
    """
    Protocol for weather data providers.

    All providers must implement this interface to be usable
    by the ForecastService. Uses structural subtyping (PEP 544).

    Example:
        >>> provider = get_provider("geosphere")
        >>> forecast = provider.fetch_forecast(location)
    """

    @property
    def name(self) -> str:
        """
        Provider identifier.

        Returns:
            Short name like "geosphere", "met", "slf"
        """
        ...

    def fetch_forecast(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> "NormalizedTimeseries":
        """
        Fetch weather forecast for a location.

        Args:
            location: Geographic location to query
            start: Forecast start time (default: now)
            end: Forecast end time (default: provider-specific)

        Returns:
            Normalized timeseries with forecast data

        Raises:
            ProviderError: If the request fails
        """
        ...


class ProviderError(Exception):
    """Base exception for provider errors."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ProviderNotFoundError(ProviderError):
    """Raised when an unknown provider is requested."""

    def __init__(self, name: str) -> None:
        super().__init__(name, f"Provider not found: {name}")


class ProviderRequestError(ProviderError):
    """Raised when a provider request fails."""

    pass


# Provider registry - lazy loading to avoid circular imports
_PROVIDER_FACTORIES: dict[str, type] = {}


def register_provider(name: str, factory: type) -> None:
    """
    Register a provider factory.

    Called by provider modules to register themselves.
    """
    _PROVIDER_FACTORIES[name] = factory


def get_provider(name: str) -> WeatherProvider:
    """
    Factory function to create provider instances.

    Args:
        name: Provider identifier (e.g., "geosphere", "met")

    Returns:
        Provider instance implementing WeatherProvider protocol

    Raises:
        ProviderNotFoundError: If provider is not registered

    Example:
        >>> provider = get_provider("geosphere")
        >>> print(provider.name)
        geosphere
    """
    # Lazy import providers to populate registry
    if not _PROVIDER_FACTORIES:
        _load_providers()

    if name not in _PROVIDER_FACTORIES:
        available = ", ".join(_PROVIDER_FACTORIES.keys()) or "none"
        raise ProviderNotFoundError(
            f"Unknown provider: {name}. Available: {available}"
        )

    return _PROVIDER_FACTORIES[name]()


def _load_providers() -> None:
    """Load all available providers."""
    # Import providers to trigger registration
    try:
        from providers.geosphere import GeoSphereProvider
        register_provider("geosphere", GeoSphereProvider)
    except ImportError:
        pass

    try:
        from providers.openmeteo import OpenMeteoProvider
        register_provider("openmeteo", OpenMeteoProvider)
    except ImportError:
        pass

    # Future providers:
    # from providers.met import METProvider
    # register_provider("met", METProvider)


def available_providers() -> list[str]:
    """Return list of available provider names."""
    if not _PROVIDER_FACTORIES:
        _load_providers()
    return list(_PROVIDER_FACTORIES.keys())
