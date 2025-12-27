"""
Forecast service - orchestrates weather data fetching.

Provides a clean interface for retrieving weather forecasts,
abstracting away provider-specific details.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

from app.debug import DebugBuffer
from app.models import NormalizedTimeseries

if TYPE_CHECKING:
    from app.config import Location
    from providers.base import WeatherProvider


class ForecastService:
    """
    Service for fetching and processing weather forecasts.

    Orchestrates data retrieval from weather providers and
    handles cross-cutting concerns like debugging and timing.

    Example:
        >>> from providers.base import get_provider
        >>> provider = get_provider("geosphere")
        >>> service = ForecastService(provider)
        >>> forecast = service.get_forecast(location, hours_ahead=48)
    """

    def __init__(
        self,
        provider: "WeatherProvider",
        debug: Optional[DebugBuffer] = None,
    ) -> None:
        """
        Initialize ForecastService with a weather provider.

        Args:
            provider: Weather data provider implementing WeatherProvider protocol
            debug: Optional debug buffer for logging (creates one if not provided)
        """
        self._provider = provider
        self._debug = debug if debug is not None else DebugBuffer()

    @property
    def provider_name(self) -> str:
        """Name of the underlying weather provider."""
        return self._provider.name

    @property
    def debug(self) -> DebugBuffer:
        """Access to debug buffer for logging."""
        return self._debug

    def get_forecast(
        self,
        location: "Location",
        hours_ahead: int = 48,
    ) -> NormalizedTimeseries:
        """
        Fetch weather forecast for a location.

        Args:
            location: Geographic location to query
            hours_ahead: Number of hours to forecast (default: 48)

        Returns:
            NormalizedTimeseries containing forecast data points

        Raises:
            ProviderRequestError: If the underlying provider request fails
        """
        self._debug.add(f"provider: {self._provider.name}")
        self._debug.add(f"location: {location}")

        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=hours_ahead)

        self._debug.add(f"forecast.range: {now.isoformat()} to {end.isoformat()}")

        ts = self._provider.fetch_forecast(location, start=now, end=end)

        self._debug.add(f"forecast.points: {len(ts.data)}")
        self._debug.add(f"forecast.model: {ts.meta.model}")

        return ts

    def get_current(self, location: "Location") -> NormalizedTimeseries:
        """
        Fetch current weather conditions (short forecast).

        Convenience method that fetches only the next 3 hours.

        Args:
            location: Geographic location to query

        Returns:
            NormalizedTimeseries with current/near-term data
        """
        return self.get_forecast(location, hours_ahead=3)
