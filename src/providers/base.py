"""
Weather provider protocol and factory.

Defines the interface that all weather providers must implement,
enabling easy extension with new data sources.
"""
from __future__ import annotations

import os
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
        enrich_ensemble: bool = True,
        enrich_snow: bool = True,
    ) -> "NormalizedTimeseries":
        """
        Fetch weather forecast for a location.

        Args:
            location: Geographic location to query
            start: Forecast start time (default: now)
            end: Forecast end time (default: provider-specific)
            enrich_ensemble: If True (default), enrich data points with
                ensemble-spread confidence; if False, skip ensemble-API call.
            enrich_snow: If True (default), enrich Alpen-Orte with SNOWGRID
                snow depth (Epic #1301 A3); if False, skip the SNOWGRID call.

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


class ProviderNotImplementedError(ProviderError):
    """Raised by stub direct providers (Issue #1141) that are registered but
    not yet technically wired up. NOT a `ProviderRequestError` — this lets
    callers distinguish "stub not implemented" from "direct provider failed".
    """

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(provider, message)


class ProviderRequestError(ProviderError):
    """Raised when a provider request fails.

    Carries an optional HTTP ``status_code`` so callers can distinguish
    transient server errors (5xx) from content errors (4xx) — the basis for
    the intra-Open-Meteo model fallback decision (Issue #1115).
    """

    def __init__(
        self, provider: str, message: str, status_code: Optional[int] = None
    ) -> None:
        self.status_code = status_code
        super().__init__(provider, message)


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
    # Offline test mode (Issue #346): when GZ_TEST_FIXTURE_DIR is set, serve
    # openmeteo requests from static fixtures instead of hitting the live API.
    # Lazy import keeps fixture.py out of the production import graph.
    fixture_dir = os.environ.get("GZ_TEST_FIXTURE_DIR", "").strip()
    if fixture_dir and name == "openmeteo":
        from providers.fixture import FixtureProvider
        return FixtureProvider(fixture_dir)

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

    try:
        from providers.brightsky import BrightSkyProvider
        register_provider("brightsky", BrightSkyProvider)
    except ImportError:
        pass

    try:
        from providers.regional_stubs import GeoSphereDirectProvider
        register_provider("at_direct", GeoSphereDirectProvider)
    except ImportError:
        pass

    try:
        from providers.meteofrance import MeteoFranceDirectProvider
        register_provider("fr_direct", MeteoFranceDirectProvider)
    except ImportError:
        pass

    try:
        from providers.dwd import DwdDirectProvider
        register_provider("de_direct", DwdDirectProvider)
    except ImportError:
        pass

    try:
        from providers.radar_dpc import RadarDPCProvider
        register_provider("radar_dpc", RadarDPCProvider)
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
