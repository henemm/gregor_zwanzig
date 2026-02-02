"""
Segment weather service - fetches weather for GPX trip segments.

Wraps ForecastService to provide weather data for TripSegment objects
from Story 1 (GPX Upload & Segment-Planung).

SPEC: docs/specs/modules/segment_weather.md v1.0
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from app.config import Location
from app.debug import DebugBuffer
from app.models import SegmentWeatherData, SegmentWeatherSummary, TripSegment

if TYPE_CHECKING:
    from providers.base import WeatherProvider
    from services.weather_cache import WeatherCacheService


class SegmentWeatherService:
    """
    Service for fetching weather forecasts for trip segments.

    Wraps existing provider infrastructure to fetch weather data
    for segment coordinates and time windows.

    Example:
        >>> from providers.base import get_provider
        >>> provider = get_provider("geosphere")
        >>> service = SegmentWeatherService(provider)
        >>> segment = TripSegment(...)  # From Story 1
        >>> weather = service.fetch_segment_weather(segment)
        >>> print(f"Provider: {weather.provider}")
    """

    def __init__(
        self,
        provider: "WeatherProvider",
        cache: Optional["WeatherCacheService"] = None,
        debug: Optional[DebugBuffer] = None,
    ) -> None:
        """
        Initialize with a weather provider.

        Args:
            provider: Weather data provider
            cache: Optional weather cache (default: create new)
            debug: Optional debug buffer for logging
        """
        self._provider = provider
        self._debug = debug if debug is not None else DebugBuffer()
        
        # Initialize cache (Feature 2.4)
        if cache is None:
            from services.weather_cache import WeatherCacheService
            cache = WeatherCacheService()
        self._cache = cache

    @property
    def provider_name(self) -> str:
        """Name of the underlying weather provider."""
        return self._provider.name

    def fetch_segment_weather(
        self,
        segment: TripSegment,
    ) -> SegmentWeatherData:
        """
        Fetch weather forecast for a trip segment.

        Algorithm (updated for Feature 2.4):
        0. Check cache first (Feature 2.4)
        1. Validate segment time window (start < end)
        2. Extract coordinates from segment.start_point
        3. Create Location object
        4. Call provider.fetch_forecast(location, start, end)
        5. Compute metrics (2.2a + 2.2b)
        6. Store in cache (Feature 2.4)
        7. Return SegmentWeatherData

        Args:
            segment: Trip segment with coordinates and time window

        Returns:
            SegmentWeatherData with populated metrics

        Raises:
            ProviderRequestError: If the provider request fails
            ValueError: If segment time window is invalid
        """
        # Step 0: Check cache first (Feature 2.4)
        cached = self._cache.get(segment)
        if cached is not None:
            self._debug.add("weather.cache: HIT")
            return cached
        
        self._debug.add("weather.cache: MISS - fetching from provider")
        
        # Step 1: Validate time window
        self._validate_segment(segment)

        # Step 2 & 3: Log segment info and create Location
        self._debug.add(f"segment: {segment.segment_id}")
        self._debug.add(
            f"coords: {segment.start_point.lat:.4f}N, {segment.start_point.lon:.4f}E"
        )
        self._debug.add(
            f"time: {segment.start_time.isoformat()} - {segment.end_time.isoformat()}"
        )
        self._debug.add(f"duration: {segment.duration_hours:.1f}h")

        # Create Location from segment start_point
        location = Location(
            latitude=segment.start_point.lat,
            longitude=segment.start_point.lon,
            name=f"Segment {segment.segment_id}",
            elevation_m=round(segment.start_point.elevation_m)
            if segment.start_point.elevation_m is not None
            else None,
        )

        # Step 4: Fetch weather data
        timeseries = self._provider.fetch_forecast(
            location,
            start=segment.start_time,
            end=segment.end_time,
        )

        # Step 5: Log provider response
        self._debug.add(f"forecast.points: {len(timeseries.data)}")
        self._debug.add(f"forecast.model: {timeseries.meta.model}")

        # Step 6: Compute basis metrics (Feature 2.2a)
        from services.weather_metrics import WeatherMetricsService

        metrics_service = WeatherMetricsService(debug=self._debug)
        basis_summary = metrics_service.compute_basis_metrics(timeseries)

        # Step 6b: Compute extended metrics (Feature 2.2b)
        extended_summary = metrics_service.compute_extended_metrics(timeseries, basis_summary)

        # Step 7: Wrap in SegmentWeatherData
        data = SegmentWeatherData(
            segment=segment,
            timeseries=timeseries,
            aggregated=extended_summary,
            fetched_at=datetime.now(timezone.utc),
            provider=self._provider.name,
        )
        
        # Step 8: Store in cache (Feature 2.4)
        self._cache.put(segment, data)
        
        return data

    def _validate_segment(self, segment: TripSegment) -> None:
        """
        Validate segment data.

        Checks:
        - start_time and end_time are timezone-aware UTC (ERROR if not)
        - start_time < end_time (ERROR if not)
        - coordinates in valid ranges (ERROR if not)
        - elevation in valid ranges (ERROR if not)
        - end_time in future (WARNING if past, but allow)

        Raises:
            ValueError: If segment data is invalid
        """
        # Validate timezone-aware UTC datetimes
        if segment.start_time.tzinfo is None:
            raise ValueError(
                f"start_time must be timezone-aware, got naive datetime: "
                f"{segment.start_time}"
            )
        if segment.start_time.tzinfo != timezone.utc:
            raise ValueError(
                f"start_time must be UTC, got: {segment.start_time.tzinfo}"
            )
        if segment.end_time.tzinfo is None:
            raise ValueError(
                f"end_time must be timezone-aware, got naive datetime: "
                f"{segment.end_time}"
            )
        if segment.end_time.tzinfo != timezone.utc:
            raise ValueError(
                f"end_time must be UTC, got: {segment.end_time.tzinfo}"
            )

        # Validate time window order
        if segment.start_time >= segment.end_time:
            raise ValueError(
                f"Invalid segment time window: "
                f"start ({segment.start_time}) >= end ({segment.end_time})"
            )

        # Validate coordinates (geographic ranges)
        for point_name, point in [
            ("start_point", segment.start_point),
            ("end_point", segment.end_point),
        ]:
            if not (-90.0 <= point.lat <= 90.0):
                raise ValueError(
                    f"Invalid {point_name} latitude: {point.lat} "
                    f"(must be -90.0 to 90.0)"
                )
            if not (-180.0 <= point.lon <= 180.0):
                raise ValueError(
                    f"Invalid {point_name} longitude: {point.lon} "
                    f"(must be -180.0 to 180.0)"
                )

        # Validate elevation (if provided)
        for point_name, point in [
            ("start_point", segment.start_point),
            ("end_point", segment.end_point),
        ]:
            if point.elevation_m is not None:
                if point.elevation_m < -500.0:
                    raise ValueError(
                        f"Invalid {point_name} elevation: {point.elevation_m}m "
                        f"(must be >= -500m, Dead Sea is lowest at -430m)"
                    )
                if point.elevation_m > 9000.0:
                    raise ValueError(
                        f"Invalid {point_name} elevation: {point.elevation_m}m "
                        f"(exceeds Mt. Everest at 8848m)"
                    )

        # Optional: Warn if time window is in the past
        now = datetime.now(timezone.utc)
        if segment.end_time < now:
            self._debug.add(
                f"WARNING: Segment time window is in the past "
                f"(end: {segment.end_time}, now: {now})"
            )
