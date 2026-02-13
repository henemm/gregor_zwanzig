"""
Open-Meteo Weather Provider with Regional Model Selection.

Provides access to global weather data via Open-Meteo API with automatic
selection of best-resolution model based on geographic location:
- AROME France (1.3km): Mallorca, Corsica, Western Alps
- ICON-D2 (2km): Germany, Austria, Switzerland, Alps
- MetNo Nordic (1km): Scandinavia, Baltic
- ICON-EU (7km): Rest of Europe
- ECMWF IFS (40km): Global fallback (MANDATORY for all regions)

API Documentation: https://open-meteo.com/en/docs

SPEC: docs/specs/modules/provider_openmeteo.md v1.0
- Regional model selection based on lat/lon bounds
- MANDATORY: ECMWF global fallback ensures 100% coverage
- Approval condition: Exception if no model found (failsafe)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    ThunderLevel,
)
from providers.base import ProviderError, ProviderRequestError

if TYPE_CHECKING:
    from app.config import Location

# Logger
logger = logging.getLogger("openmeteo")

# API Configuration
BASE_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 30.0

# Retry Configuration (per docs/specs/modules/api_retry.md)
RETRY_ATTEMPTS = 5
RETRY_WAIT_MIN = 2  # seconds
RETRY_WAIT_MAX = 60  # seconds
RETRY_STATUS_CODES = {502, 503, 504}


# Regional Models Configuration
# CRITICAL: ECMWF global model MUST be last (priority 5) to guarantee coverage
REGIONAL_MODELS = [
    {
        "id": "meteofrance_arome",
        "name": "AROME France & Balearen (1.3 km)",
        "bounds": {"min_lat": 38.0, "max_lat": 53.0, "min_lon": -8.0, "max_lon": 10.0},
        "grid_res_km": 1.3,
        "priority": 1,  # Highest resolution first
    },
    {
        "id": "icon_d2",
        "name": "ICON-D2 (2 km)",
        "bounds": {"min_lat": 43.0, "max_lat": 56.0, "min_lon": 2.0, "max_lon": 18.0},
        "grid_res_km": 2.0,
        "priority": 2,
    },
    {
        "id": "metno_nordic",
        "name": "MetNo Nordic (1 km)",
        "bounds": {"min_lat": 53.0, "max_lat": 72.0, "min_lon": 3.0, "max_lon": 35.0},
        "grid_res_km": 1.0,
        "priority": 3,
    },
    {
        "id": "icon_eu",
        "name": "ICON-EU (7 km)",
        "bounds": {"min_lat": 29.0, "max_lat": 71.0, "min_lon": -24.0, "max_lon": 45.0},
        "grid_res_km": 7.0,
        "priority": 4,
    },
    {
        "id": "ecmwf_ifs04",
        "name": "ECMWF IFS (40 km)",
        "bounds": {"min_lat": -90.0, "max_lat": 90.0, "min_lon": -180.0, "max_lon": 180.0},
        "grid_res_km": 40.0,
        "priority": 5,  # Global fallback - MANDATORY
    },
]

# WMO Weather Code to Thunder Level mapping
# https://open-meteo.com/en/docs#weathervariables
THUNDER_CODES = {95, 96, 99}  # Thunderstorm codes


def _is_retryable_error(exception: Exception) -> bool:
    """Check if exception is retryable."""
    if isinstance(exception, httpx.HTTPStatusError):
        return exception.response.status_code in RETRY_STATUS_CODES
    if isinstance(exception, (httpx.ConnectError, httpx.ReadTimeout)):
        return True
    return False


class OpenMeteoProvider:
    """
    Open-Meteo weather provider with regional model selection.

    Automatically selects the best-resolution weather model based on
    location coordinates, with mandatory ECMWF global fallback.
    """

    def __init__(self):
        """Initialize provider with HTTP client."""
        self._client = httpx.Client(timeout=TIMEOUT)

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "openmeteo"

    def select_model(self, lat: float, lon: float) -> Tuple[str, float]:
        """
        Select best weather model based on coordinates.

        Iterates models by priority (highest resolution first) and returns
        first match. ECMWF global model (-90/90, -180/180) guarantees coverage.

        CRITICAL (APPROVAL CONDITION):
        - MUST always return a valid model
        - Raises ProviderError if no model found (should NEVER happen)

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)

        Returns:
            Tuple of (model_id, grid_res_km)

        Raises:
            ProviderError: If no model found (critical config error)
        """
        for model in sorted(REGIONAL_MODELS, key=lambda m: m["priority"]):
            bounds = model["bounds"]
            if (
                bounds["min_lat"] <= lat <= bounds["max_lat"]
                and bounds["min_lon"] <= lon <= bounds["max_lon"]
            ):
                logger.debug(
                    f"Selected model '{model['id']}' ({model['grid_res_km']}km) "
                    f"for lat={lat}, lon={lon}"
                )
                return model["id"], model["grid_res_km"]

        # FAILSAFE: Should NEVER be reached (ECMWF is global)
        raise ProviderError(
            "openmeteo",
            f"CRITICAL: No model found for lat={lat}, lon={lon}. "
            f"ECMWF global fallback failed - check REGIONAL_MODELS configuration!"
        )

    @retry(
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
        retry=retry_if_exception(_is_retryable_error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make HTTP request to Open-Meteo API with retry logic.

        Retries on:
        - HTTP 502, 503, 504 (transient server errors)
        - Connection errors
        - Read timeouts

        Args:
            params: Query parameters

        Returns:
            JSON response as dict

        Raises:
            ProviderRequestError: On non-retryable errors or after max retries
        """
        try:
            response = self._client.get(BASE_URL, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ProviderRequestError(
                "openmeteo",
                f"API error: {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise ProviderRequestError("openmeteo", f"Request failed: {e}") from e

    def _parse_thunder_level(self, weather_code: Optional[int]) -> ThunderLevel:
        """
        Parse WMO weather code to thunder level.

        WMO Codes:
        - 95: Thunderstorm
        - 96: Thunderstorm with slight hail
        - 99: Thunderstorm with heavy hail

        Args:
            weather_code: WMO weather code (0-99)

        Returns:
            ThunderLevel.HIGH if thunderstorm, else ThunderLevel.NONE
        """
        if weather_code in THUNDER_CODES:
            return ThunderLevel.HIGH
        return ThunderLevel.NONE

    def _parse_response(
        self, data: Dict[str, Any], model_id: str, grid_res_km: float
    ) -> NormalizedTimeseries:
        """
        Parse Open-Meteo JSON response to NormalizedTimeseries.

        Args:
            data: JSON response from API
            model_id: Selected model ID (e.g., "meteofrance_arome")
            grid_res_km: Grid resolution in km

        Returns:
            NormalizedTimeseries with parsed data

        Raises:
            ProviderError: If response format is invalid
        """
        try:
            hourly = data["hourly"]
            times = hourly["time"]

            # Extract model run time (from current_weather or use current time)
            run_time = datetime.now(timezone.utc)

            # Build metadata
            meta = ForecastMeta(
                provider=Provider.OPENMETEO,
                model=model_id,
                run=run_time,
                grid_res_km=grid_res_km,
                interp="grid_point",
                stations_used=[],
            )

            # Parse data points
            data_points: List[ForecastDataPoint] = []
            for i, time_str in enumerate(times):
                # Parse timestamp (ISO 8601 format)
                ts = datetime.fromisoformat(time_str.replace("Z", "+00:00"))

                # Extract values (handle None for missing data)
                def get_val(key: str, idx: int) -> Optional[float]:
                    arr = hourly.get(key, [])
                    if idx < len(arr):
                        val = arr[idx]
                        return float(val) if val is not None else None
                    return None

                def get_int(key: str, idx: int) -> Optional[int]:
                    arr = hourly.get(key, [])
                    if idx < len(arr):
                        val = arr[idx]
                        return int(val) if val is not None else None
                    return None

                # Build data point (parameter mapping per spec)
                point = ForecastDataPoint(
                    ts=ts,
                    # Base fields
                    t2m_c=get_val("temperature_2m", i),
                    wind10m_kmh=get_val("wind_speed_10m", i),
                    wind_direction_deg=get_int("wind_direction_10m", i),
                    gust_kmh=get_val("wind_gusts_10m", i),
                    precip_rate_mmph=None,  # Not available (Open-Meteo provides hourly totals, not rates)
                    precip_1h_mm=get_val("precipitation", i),
                    cloud_total_pct=get_int("cloud_cover", i),
                    symbol=None,  # Could map weather_code to symbol
                    thunder_level=self._parse_thunder_level(get_int("weather_code", i)),
                    cape_jkg=get_val("cape", i),
                    pop_pct=get_val("precipitation_probability", i),
                    pressure_msl_hpa=get_val("pressure_msl", i),
                    humidity_pct=get_int("relative_humidity_2m", i),
                    dewpoint_c=get_val("dewpoint_2m", i),
                    # Cloud layers
                    cloud_low_pct=get_int("cloud_cover_low", i),
                    cloud_mid_pct=get_int("cloud_cover_mid", i),
                    cloud_high_pct=get_int("cloud_cover_high", i),
                    # UV Index (Open-Meteo hourly)
                    uv_index=get_val("uv_index", i),
                    # Wintersport fields (not available in Open-Meteo)
                    snow_depth_cm=None,
                    snow_new_24h_cm=None,
                    snow_new_acc_cm=None,
                    snowfall_limit_m=None,
                    swe_kgm2=None,
                    precip_type=None,
                    freezing_level_m=get_val("freezing_level_height", i),
                    wind_chill_c=get_val("apparent_temperature", i),
                    visibility_m=get_val("visibility", i),
                )
                data_points.append(point)

            return NormalizedTimeseries(meta=meta, data=data_points)

        except (KeyError, IndexError, ValueError) as e:
            raise ProviderError("openmeteo", f"Failed to parse response: {e}") from e

    def fetch_forecast(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> NormalizedTimeseries:
        """
        Fetch weather forecast for a location.

        Automatically selects best regional model based on coordinates.

        Args:
            location: Location with latitude/longitude
            start: Start time (default: now)
            end: End time (default: now + 48h)

        Returns:
            NormalizedTimeseries with hourly forecast

        Raises:
            ProviderError: If model selection fails or response invalid
            ProviderRequestError: If API request fails
        """
        # Select best model for location
        model_id, grid_res_km = self.select_model(location.latitude, location.longitude)

        # Build request parameters
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "model": model_id,  # Dynamic model selection!
            "hourly": ",".join([
                "temperature_2m",
                "apparent_temperature",
                "relative_humidity_2m",
                "dewpoint_2m",
                "pressure_msl",
                "cloud_cover",
                "cloud_cover_low",
                "cloud_cover_mid",
                "cloud_cover_high",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
                "precipitation",
                "weather_code",
                "visibility",
                "precipitation_probability",
                "cape",
                "freezing_level_height",
                "uv_index",
            ]),
            "timezone": "UTC",
        }

        # Add time range if specified (both start and end required together)
        if start and end:
            params["start_date"] = start.strftime("%Y-%m-%d")
            params["end_date"] = end.strftime("%Y-%m-%d")
        elif end:
            # If only end specified, use today as start
            params["start_date"] = datetime.now().strftime("%Y-%m-%d")
            params["end_date"] = end.strftime("%Y-%m-%d")
        elif start:
            # If only start specified, fetch from start onwards (API default range)
            params["start_date"] = start.strftime("%Y-%m-%d")

        logger.info(
            f"Fetching Open-Meteo forecast for {location.name or 'location'} "
            f"({location.latitude}, {location.longitude}) using model '{model_id}'"
        )

        # Make request with retry logic
        response_data = self._request(params)

        # Parse and return
        return self._parse_response(response_data, model_id, grid_res_km)
