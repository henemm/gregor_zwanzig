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

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
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
# BUGFIX: Dedicated endpoints per model family (not generic /v1/forecast)
# See: docs/specs/bugfix/openmeteo_endpoint_routing.md
BASE_HOST = "https://api.open-meteo.com"
AIR_QUALITY_HOST = "https://air-quality-api.open-meteo.com"
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
        "endpoint": "/v1/meteofrance",
        "bounds": {"min_lat": 38.0, "max_lat": 53.0, "min_lon": -8.0, "max_lon": 10.0},
        "grid_res_km": 1.3,
        "priority": 1,  # Highest resolution first
    },
    {
        "id": "icon_d2",
        "name": "ICON-D2 (2 km)",
        "endpoint": "/v1/dwd-icon",
        "bounds": {"min_lat": 43.0, "max_lat": 56.0, "min_lon": 2.0, "max_lon": 18.0},
        "grid_res_km": 2.0,
        "priority": 2,
    },
    {
        "id": "metno_nordic",
        "name": "MetNo Nordic (1 km)",
        "endpoint": "/v1/metno",
        "bounds": {"min_lat": 53.0, "max_lat": 72.0, "min_lon": 3.0, "max_lon": 35.0},
        "grid_res_km": 1.0,
        "priority": 3,
    },
    {
        "id": "icon_eu",
        "name": "ICON-EU (7 km)",
        "endpoint": "/v1/dwd-icon",
        "bounds": {"min_lat": 29.0, "max_lat": 71.0, "min_lon": -24.0, "max_lon": 45.0},
        "grid_res_km": 7.0,
        "priority": 4,
    },
    {
        "id": "ecmwf_ifs04",
        "name": "ECMWF IFS (40 km)",
        "endpoint": "/v1/ecmwf",
        "bounds": {"min_lat": -90.0, "max_lat": 90.0, "min_lon": -180.0, "max_lon": 180.0},
        "grid_res_km": 40.0,
        "priority": 5,  # Global fallback - MANDATORY
    },
]

# Metric Availability Probe (WEATHER-05a)
AVAILABILITY_CACHE_PATH = Path("data/cache/model_availability.json")
AVAILABILITY_CACHE_TTL_DAYS = 7

PROBE_PARAMS = [
    "temperature_2m", "apparent_temperature", "relative_humidity_2m",
    "dewpoint_2m", "pressure_msl", "cloud_cover", "cloud_cover_low",
    "cloud_cover_mid", "cloud_cover_high", "wind_speed_10m",
    "wind_direction_10m", "wind_gusts_10m", "precipitation",
    "weather_code", "visibility", "precipitation_probability",
    "cape", "freezing_level_height", "uv_index",
]

# Reference coordinates per model (center of bounding box)
_PROBE_COORDS = {
    "meteofrance_arome": (45.5, 1.0),
    "icon_d2": (49.5, 10.0),
    "metno_nordic": (62.5, 19.0),
    "icon_eu": (50.0, 10.5),
    "ecmwf_ifs04": (0.0, 0.0),
}

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

    # --- Metric Availability Probe (WEATHER-05a) ---

    def _load_availability_cache(self) -> Optional[dict]:
        """Load availability cache, return None if expired or missing."""
        if not AVAILABILITY_CACHE_PATH.exists():
            return None
        try:
            data = json.loads(AVAILABILITY_CACHE_PATH.read_text())
            probe_date = date.fromisoformat(data["probe_date"])
            if (date.today() - probe_date).days >= AVAILABILITY_CACHE_TTL_DAYS:
                return None
            return data
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _save_availability_cache(self, result: dict) -> None:
        """Save probe result as JSON cache."""
        AVAILABILITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        AVAILABILITY_CACHE_PATH.write_text(json.dumps(result, indent=2))

    def probe_model_availability(self) -> dict:
        """
        Probe all REGIONAL_MODELS for actual metric availability.

        Makes one API call per model with reference coordinates (center of
        bounding box), requesting all PROBE_PARAMS. Checks which hourly
        arrays contain at least one non-null value.

        Returns:
            Dict with probe_date and per-model available/unavailable lists.
        """
        logger.info("Probing %d OpenMeteo models for metric availability...", len(REGIONAL_MODELS))
        result: dict = {"probe_date": date.today().isoformat(), "models": {}}

        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

        for model in sorted(REGIONAL_MODELS, key=lambda m: m["priority"]):
            model_id = model["id"]
            coords = _PROBE_COORDS.get(model_id)
            if not coords:
                continue

            params = {
                "latitude": coords[0],
                "longitude": coords[1],
                "hourly": ",".join(PROBE_PARAMS),
                "timezone": "UTC",
                "start_date": tomorrow,
                "end_date": tomorrow,
            }

            try:
                data = self._request(model["endpoint"], params)
                hourly = data.get("hourly", {})

                available = []
                unavailable = []
                for param in PROBE_PARAMS:
                    values = hourly.get(param, [])
                    if any(v is not None for v in values):
                        available.append(param)
                    else:
                        unavailable.append(param)

                result["models"][model_id] = {
                    "available": available,
                    "unavailable": unavailable,
                }
                logger.info("  %s: %d available, %d unavailable", model_id, len(available), len(unavailable))

            except Exception as e:
                logger.warning("  %s: probe failed (%s), skipping", model_id, e)

        self._save_availability_cache(result)
        logger.info("Probe complete. Cache saved to %s", AVAILABILITY_CACHE_PATH)
        return result

    # --- Model-Metric-Fallback (WEATHER-05b) ---

    # Mapping: OpenMeteo API param → ForecastDataPoint field
    _PARAM_TO_FIELD = {
        "temperature_2m": "t2m_c",
        "apparent_temperature": "wind_chill_c",
        "relative_humidity_2m": "humidity_pct",
        "dewpoint_2m": "dewpoint_c",
        "pressure_msl": "pressure_msl_hpa",
        "cloud_cover": "cloud_total_pct",
        "cloud_cover_low": "cloud_low_pct",
        "cloud_cover_mid": "cloud_mid_pct",
        "cloud_cover_high": "cloud_high_pct",
        "wind_speed_10m": "wind10m_kmh",
        "wind_direction_10m": "wind_direction_deg",
        "wind_gusts_10m": "gust_kmh",
        "precipitation": "precip_1h_mm",
        "visibility": "visibility_m",
        "precipitation_probability": "pop_pct",
        "cape": "cape_jkg",
        "freezing_level_height": "freezing_level_m",
        "uv_index": "uv_index",
    }

    def _find_fallback_model(
        self, primary_id: str, lat: float, lon: float, missing_params: List[str]
    ) -> Optional[Tuple[str, float, str]]:
        """Find best fallback model that covers the coordinates and has missing metrics."""
        cache = self._load_availability_cache()
        if cache is None:
            return None

        for model in sorted(REGIONAL_MODELS, key=lambda m: m["priority"]):
            if model["id"] == primary_id:
                continue
            bounds = model["bounds"]
            if not (bounds["min_lat"] <= lat <= bounds["max_lat"]
                    and bounds["min_lon"] <= lon <= bounds["max_lon"]):
                continue
            model_info = cache["models"].get(model["id"])
            if model_info is None:
                continue
            available = set(model_info.get("available", []))
            if available & set(missing_params):
                return model["id"], model["grid_res_km"], model["endpoint"]

        return None

    def _merge_fallback(
        self, primary: "NormalizedTimeseries", fallback: "NormalizedTimeseries",
        missing_params: List[str]
    ) -> List[str]:
        """Fill None fields in primary from fallback for missing_params only."""
        fb_by_ts = {dp.ts: dp for dp in fallback.data}
        filled: set = set()

        for dp in primary.data:
            fb_dp = fb_by_ts.get(dp.ts)
            if fb_dp is None:
                continue
            for param in missing_params:
                field_name = self._PARAM_TO_FIELD.get(param)
                if field_name is None:
                    continue
                if getattr(dp, field_name, None) is None:
                    fb_val = getattr(fb_dp, field_name, None)
                    if fb_val is not None:
                        setattr(dp, field_name, fb_val)
                        filled.add(param)

        return sorted(filled)

    def select_model(self, lat: float, lon: float) -> Tuple[str, float, str]:
        """
        Select best weather model based on coordinates.

        Iterates models by priority (highest resolution first) and returns
        first match with dedicated API endpoint. ECMWF global model guarantees coverage.

        CRITICAL (APPROVAL CONDITION):
        - MUST always return a valid model
        - Raises ProviderError if no model found (should NEVER happen)

        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)

        Returns:
            Tuple of (model_id, grid_res_km, endpoint_path)

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
                    f"endpoint='{model['endpoint']}' for lat={lat}, lon={lon}"
                )
                return model["id"], model["grid_res_km"], model["endpoint"]

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
    def _request(
        self, endpoint: str, params: Dict[str, Any], base_host: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Open-Meteo API with retry logic.

        Retries on:
        - HTTP 502, 503, 504 (transient server errors)
        - Connection errors
        - Read timeouts

        Args:
            endpoint: API endpoint path (e.g., "/v1/meteofrance")
            params: Query parameters
            base_host: Override BASE_HOST (e.g., AIR_QUALITY_HOST)

        Returns:
            JSON response as dict

        Raises:
            ProviderRequestError: On non-retryable errors or after max retries
        """
        host = base_host or BASE_HOST
        url = f"{host}{endpoint}"
        try:
            response = self._client.get(url, params=params)
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

    def _fetch_uv_data(
        self, lat: float, lon: float, start: datetime, end: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch UV-Index from Air Quality API (CAMS).

        UV is unavailable from all weather models; CAMS provides global hourly data.

        Returns:
            AQ API response dict with hourly.uv_index, or None on failure.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "uv_index",
            "timezone": "UTC",
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
        }
        try:
            logger.debug("Fetching UV from Air Quality API (CAMS)")
            return self._request("/v1/air-quality", params, base_host=AIR_QUALITY_HOST)
        except Exception as e:
            logger.warning("UV fetch from AQ API failed: %s", e)
            return None

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
                    symbol=None,
                    thunder_level=self._parse_thunder_level(get_int("weather_code", i)),
                    wmo_code=get_int("weather_code", i),
                    is_day=get_int("is_day", i),
                    dni_wm2=get_val("direct_normal_irradiance", i),
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
        # Select best model for location (includes dedicated API endpoint)
        model_id, grid_res_km, endpoint = self.select_model(location.latitude, location.longitude)

        # Build request parameters (no "model" param needed — endpoint determines model)
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
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
                "direct_normal_irradiance",
                "is_day",
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
            f"({location.latitude}, {location.longitude}) "
            f"using model '{model_id}' via endpoint '{endpoint}'"
        )

        # Make request with retry logic (dedicated endpoint per model)
        response_data = self._request(endpoint, params)

        # Parse primary result
        timeseries = self._parse_response(response_data, model_id, grid_res_km)

        # WEATHER-06: Fetch UV from Air Quality API (no weather model provides UV)
        if start and end:
            uv_data = self._fetch_uv_data(location.latitude, location.longitude, start, end)
            if uv_data:
                uv_times = uv_data.get("hourly", {}).get("time", [])
                uv_values = uv_data.get("hourly", {}).get("uv_index", [])
                uv_by_ts = {}
                for t, v in zip(uv_times, uv_values):
                    if v is not None:
                        uv_by_ts[datetime.fromisoformat(t)] = v
                filled_count = 0
                for dp in timeseries.data:
                    ts_naive = dp.ts.replace(tzinfo=None) if dp.ts.tzinfo else dp.ts
                    if ts_naive in uv_by_ts:
                        dp.uv_index = uv_by_ts[ts_naive]
                        filled_count += 1
                if filled_count:
                    logger.info("UV merged from AQ API: %d values", filled_count)

        # WEATHER-05b: Check for missing metrics and fetch fallback
        cache = self._load_availability_cache()
        if cache is not None:
            primary_info = cache["models"].get(model_id)
            if primary_info:
                missing = primary_info.get("unavailable", [])
                if missing:
                    fallback = self._find_fallback_model(
                        model_id, location.latitude, location.longitude, missing
                    )
                    if fallback:
                        fb_id, fb_res, fb_endpoint = fallback
                        fb_params = {
                            "latitude": location.latitude,
                            "longitude": location.longitude,
                            "hourly": ",".join(missing),
                            "timezone": "UTC",
                        }
                        if start and end:
                            fb_params["start_date"] = start.strftime("%Y-%m-%d")
                            fb_params["end_date"] = end.strftime("%Y-%m-%d")
                        try:
                            fb_data = self._request(fb_endpoint, fb_params)
                            fb_ts = self._parse_response(fb_data, fb_id, fb_res)
                            filled = self._merge_fallback(timeseries, fb_ts, missing)
                            if filled:
                                timeseries.meta.fallback_model = fb_id
                                timeseries.meta.fallback_metrics = filled
                                logger.info("Fallback %s filled: %s", fb_id, ", ".join(filled))
                        except Exception as e:
                            logger.warning("Fallback %s failed: %s", fb_id, e)

        return timeseries
