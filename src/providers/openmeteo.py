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
import statistics
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
from providers import call_log
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
ENSEMBLE_BASE_HOST = "https://ensemble-api.open-meteo.com"
TIMEOUT = 30.0
ENSEMBLE_TIMEOUT = 15.0  # Issue #121: shorter timeout for ensemble (best-effort)

# Issue #338: Diagnose-Zähler — append-only JSONL für jeden ausgehenden Abruf.
# Reine Observability, fail-soft. In .gitignore (data/diagnostics/).
DIAGNOSTICS_PATH = Path("data/diagnostics/openmeteo_calls.jsonl")


def compute_confidence_pct(
    spread_t2m_k: float, spread_precip_mm: float, lead_time_hours: float
) -> int:
    """
    Compute confidence percentage from ensemble spread with lead-time cap.

    Returns int in [0, 100]. See docs/specs/modules/forecast_confidence.md AC-4, AC-5.

    Formula:
        raw = clamp(100 - spread_t2m_k * 15 - spread_precip_mm * 10, 0, 100)
        cap = 95 (T+0-24h), 80 (T+24-48h), 60 (T+48-72h), 40 (T+72h+)
        result = min(raw, cap)

    Lead-Time-Cap is enforced even at zero spread (critical case AC-4).
    """
    raw = 100.0 - (spread_t2m_k * 15.0) - (spread_precip_mm * 10.0)
    raw = max(0.0, min(100.0, raw))
    if lead_time_hours <= 24:
        cap = 95
    elif lead_time_hours <= 48:
        cap = 80
    elif lead_time_hours <= 72:
        cap = 60
    else:
        cap = 40
    return int(round(min(raw, cap)))

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

# Bug #353: Open-Meteo Vorhersagehorizont.
# Empirisch (2026-05-25, echte Diagnose-Calls): /v1/meteofrance, /v1/dwd-icon,
# /v1/ecmwf, /v1/gfs erlauben start_date nur bis today+15; +16 → HTTP 400
# ("start_date out of allowed range"). Die Grenze ist modell-/endpoint-
# übergreifend identisch (Open-Meteo validiert vor dem Modell-Processing).
OPENMETEO_MAX_FORECAST_DAYS = 15


def is_within_forecast_horizon(stage_date: date, reference_date: date) -> bool:
    """True, wenn stage_date <= reference_date + OPENMETEO_MAX_FORECAST_DAYS.

    Jenseits davon liefert KEIN Open-Meteo-Modell Daten (Bug #353).
    Reine Funktion, deterministisch testbar (keine API, keine Mocks).
    """
    return (stage_date - reference_date).days <= OPENMETEO_MAX_FORECAST_DAYS


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
    if isinstance(exception, ProviderRequestError):
        if exception.status_code in RETRY_STATUS_CODES:
            return True
        if isinstance(exception.__cause__, (httpx.ConnectError, httpx.ReadTimeout)):
            return True
    return False


class OpenMeteoProvider:
    """
    Open-Meteo weather provider with regional model selection.

    Automatically selects the best-resolution weather model based on
    location coordinates, with mandatory ECMWF global fallback.
    """

    def __init__(self, ensemble_base_host: Optional[str] = None):
        """Initialize provider with HTTP client.

        Args:
            ensemble_base_host: Override for ensemble API host (Issue #121).
                Default: production ENSEMBLE_BASE_HOST. Tests inject a
                closed local port for fault-injection (AC-6).
        """
        self._client = httpx.Client(timeout=TIMEOUT)
        self._ensemble_host = ensemble_base_host or ENSEMBLE_BASE_HOST

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

    def _candidate_models(
        self, lat: float, lon: float
    ) -> List[Tuple[str, float, str]]:
        """All models covering (lat, lon), sorted by priority (finest first).

        Issue #1115: candidate chain for the intra-Open-Meteo model fallback.
        The first entry is exactly what ``select_model`` would return (same
        bounds-filter logic, Z.393-398); further entries are the next-best
        covering models down to the mandatory global ECMWF fallback.

        Returns:
            List of (model_id, grid_res_km, endpoint_path) ordered by priority.
        """
        candidates: List[Tuple[str, float, str]] = []
        for model in sorted(REGIONAL_MODELS, key=lambda m: m["priority"]):
            bounds = model["bounds"]
            if (
                bounds["min_lat"] <= lat <= bounds["max_lat"]
                and bounds["min_lon"] <= lon <= bounds["max_lon"]
            ):
                candidates.append(
                    (model["id"], model["grid_res_km"], model["endpoint"])
                )
        return candidates

    # Issue #338: Mapping Aufrufer-Funktionsname (im Stack) -> Diagnose-Quelle.
    # Konsolidiert nach providers.call_log (DRY). Klassen-Attribut bleibt als
    # Alias für Rückwärtskompatibilität bestehender Referenzen.
    _CALL_SOURCE_MARKERS = call_log._CALL_SOURCE_MARKERS

    def _resolve_call_source(self) -> str:
        """Issue #338: Thin-Wrapper auf call_log.resolve_call_source()."""
        return call_log.resolve_call_source()

    def _log_api_call(
        self, endpoint: str, status: Optional[int], error: Optional[str] = None
    ) -> None:
        """
        Issue #338: Thin-Wrapper auf call_log.log_api_call() (fail-soft).

        Die bestehenden Tests konfigurieren providers.openmeteo.DIAGNOSTICS_PATH
        um; damit diese Umkonfiguration weiter greift, wird der hier gültige
        DIAGNOSTICS_PATH vor dem Delegieren an call_log gespiegelt. Verhalten
        unverändert gegenüber bd8e1e2.
        """
        import providers.openmeteo as _om

        prev = call_log.DIAGNOSTICS_PATH
        call_log.DIAGNOSTICS_PATH = _om.DIAGNOSTICS_PATH
        try:
            call_log.log_api_call(endpoint, status, error)
        finally:
            call_log.DIAGNOSTICS_PATH = prev

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
        url = f"{host}{endpoint}"  # host+path ohne Query (params separat)
        try:
            response = self._client.get(url, params=params)
            # Issue #338: Genau eine Zeile pro get() — der echte Status (inkl.
            # 429) ist hier bekannt; im HTTPStatusError-Zweig NICHT erneut loggen.
            self._log_api_call(url, response.status_code)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise ProviderRequestError(
                "openmeteo",
                f"API error: {e.response.status_code} - {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            # Issue #338: kein Response → eigener Log-Eintrag mit Fehlertext.
            self._log_api_call(url, None, error=str(e))
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

    def _fetch_ensemble_spread(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[datetime, Tuple[Optional[float], Optional[float]]]:
        """
        Fetch ensemble spread from OpenMeteo Ensemble API. Best-effort.

        Issue #121 / AC-3, AC-6: Returns dict mapping timestamp -> (spread_t2m_k,
        spread_precip_mm). On ANY failure (HTTP error, timeout, connection error,
        malformed response) returns {} - never raises to caller (AC-6).

        Spread is computed as stdev across ensemble members. Requires >=5 valid
        members per hour; otherwise that hour's spread is None.
        """
        params = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "hourly": "temperature_2m,precipitation",
            "models": "ecmwf_ifs04,icon_seamless,gfs_seamless",
            "timezone": "UTC",
        }
        if start and end:
            params["start_date"] = start.strftime("%Y-%m-%d")
            params["end_date"] = end.strftime("%Y-%m-%d")

        url = f"{self._ensemble_host}/v1/ensemble"  # host+path ohne Query
        try:
            response = self._client.get(url, params=params, timeout=ENSEMBLE_TIMEOUT)
            self._log_api_call(url, response.status_code)  # Issue #338
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as e:
            # Issue #338: bereits nach get() protokolliert (kein Doppel-Eintrag).
            logger.warning("Ensemble fetch failed: %s", e)
            return {}
        except Exception as e:
            self._log_api_call(url, None, error=str(e))  # Issue #338
            logger.warning("Ensemble fetch failed: %s", e)
            return {}

        try:
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            if not times:
                return {}

            # Collect all member keys for temperature_2m and precipitation.
            temp_keys = [k for k in hourly.keys() if k.startswith("temperature_2m")]
            precip_keys = [k for k in hourly.keys() if k.startswith("precipitation")]

            result: Dict[datetime, Tuple[Optional[float], Optional[float]]] = {}
            for i, time_str in enumerate(times):
                try:
                    ts = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                temp_vals: List[float] = []
                for k in temp_keys:
                    arr = hourly.get(k, [])
                    if i < len(arr) and arr[i] is not None:
                        try:
                            temp_vals.append(float(arr[i]))
                        except (ValueError, TypeError):
                            pass

                precip_vals: List[float] = []
                for k in precip_keys:
                    arr = hourly.get(k, [])
                    if i < len(arr) and arr[i] is not None:
                        try:
                            precip_vals.append(float(arr[i]))
                        except (ValueError, TypeError):
                            pass

                spread_t = statistics.stdev(temp_vals) if len(temp_vals) >= 5 else None
                spread_p = statistics.stdev(precip_vals) if len(precip_vals) >= 5 else None
                result[ts] = (spread_t, spread_p)

            return result
        except Exception as e:
            logger.warning("Ensemble parse failed: %s", e)
            return {}

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
        enrich_ensemble: bool = True,
    ) -> NormalizedTimeseries:
        """
        Fetch weather forecast for a location.

        Automatically selects best regional model based on coordinates.

        Args:
            location: Location with latitude/longitude
            start: Start time (default: now)
            end: End time (default: now + 48h)
            enrich_ensemble: If True (default), enrich data points with
                ensemble-spread confidence (Issue #121); if False, skip the
                ensemble-API call entirely. Bug #288 reduces calls to 1/report.

        Returns:
            NormalizedTimeseries with hourly forecast

        Raises:
            ProviderError: If model selection fails or response invalid
            ProviderRequestError: If API request fails
        """
        # Issue #1115: candidate chain (finest resolution first, down to global
        # ECMWF) for the intra-Open-Meteo model fallback on 5xx/timeout of a
        # single model endpoint. candidates[0] is exactly what select_model
        # would have returned (the primary model).
        candidates = self._candidate_models(location.latitude, location.longitude)
        if not candidates:
            # Failsafe: should never happen (ECMWF is global). Preserve the
            # original select_model semantics (raises ProviderError).
            candidates = [self.select_model(location.latitude, location.longitude)]
        primary_id = candidates[0][0]

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

        # Issue #1115: try each covering model in priority order. params are
        # model-independent and identical across all attempts. On a 5xx/timeout
        # we advance to the next endpoint; on a 4xx content error we re-raise
        # immediately (no source roulette, AC-2).
        response_data: Optional[Dict[str, Any]] = None
        model_id = grid_res_km = None
        seen_endpoints: set = set()
        last_error: Optional[ProviderRequestError] = None
        for cand_id, cand_res, cand_endpoint in candidates:
            if cand_endpoint in seen_endpoints:
                continue  # icon_d2 & icon_eu share /v1/dwd-icon → dedup
            seen_endpoints.add(cand_endpoint)
            logger.info(
                f"Fetching Open-Meteo forecast for {location.name or 'location'} "
                f"({location.latitude}, {location.longitude}) "
                f"using model '{cand_id}' via endpoint '{cand_endpoint}'"
            )
            try:
                response_data = self._request(cand_endpoint, params)
            except ProviderRequestError as e:
                status = e.status_code
                if status is not None and 400 <= status < 500:
                    raise  # 4xx content error → no fallback (AC-2)
                # 5xx server error OR transient request error (timeout/connect,
                # status_code None) → advance to next covering model (AC-1).
                logger.warning(
                    "Model fallback: '%s' (%s) unavailable → next endpoint",
                    cand_id, status if status is not None else "transient",
                )
                last_error = e
                continue
            # Success: this candidate's model_id/grid_res are authoritative and
            # must be used by _parse_response AND the WEATHER-05b block below.
            model_id, grid_res_km = cand_id, cand_res
            break

        if response_data is None:
            # Issue #1141: Open-Meteo als Verteiler komplett ausgefallen (alle
            # Modelle inkl. ECMWF mit 5xx/Timeout). Cross-Provider-Weiche
            # NACH dem #1115-Fallback (kein frueherer Eingriff moeglich).
            from providers.region_routing import direct_provider_for
            from providers.base import ProviderNotImplementedError, get_provider
            direct_name = direct_provider_for(location.latitude, location.longitude)
            if direct_name is not None:
                try:
                    ts = get_provider(direct_name).fetch_forecast(
                        location, start, end, enrich_ensemble
                    )
                    ts.meta.fallback_reason = "cross_provider_total_outage"
                    ts.meta.fallback_model = direct_name
                    return ts
                except ProviderNotImplementedError:
                    pass  # Stub noch nicht angebunden → Original-Fehler (AC-5)
            # All covering models failed with 5xx/timeout → surface the last
            # error so the segment is marked has_error (unchanged behavior).
            raise last_error

        # Parse result from the model that actually succeeded.
        timeseries = self._parse_response(response_data, model_id, grid_res_km)

        # Non-concealment (AC-3): record the model that stepped in on 5xx.
        if model_id != primary_id:
            timeseries.meta.fallback_model = model_id
            timeseries.meta.fallback_reason = "model_5xx"

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

        # Issue #121: Enrich with ensemble spread + lead-time-capped confidence.
        # Best-effort: any failure leaves the three new fields at None (AC-6).
        # Bug #288: enrich_ensemble=False skips the ensemble call (alert-checks).
        if enrich_ensemble:
            try:
                spreads = self._fetch_ensemble_spread(location, start, end)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("Ensemble spread enrichment crashed: %s", e)
                spreads = {}

            if spreads:
                now_utc = datetime.now(timezone.utc)
                # Build a lookup with naive UTC ts to match primary timeseries.
                spreads_naive: Dict[datetime, Tuple[Optional[float], Optional[float]]] = {}
                for k, v in spreads.items():
                    k_naive = k.replace(tzinfo=None) if k.tzinfo is not None else k
                    spreads_naive[k_naive] = v

                for dp in timeseries.data:
                    dp_ts_naive = dp.ts.replace(tzinfo=None) if dp.ts.tzinfo else dp.ts
                    spread = spreads_naive.get(dp_ts_naive)
                    if spread is None:
                        continue
                    s_t, s_p = spread
                    dp.spread_t2m_k = s_t
                    dp.spread_precip_mm = s_p
                    if s_t is not None and s_p is not None:
                        # Lead-time = hours from now to forecast ts.
                        dp_ts_utc = dp.ts if dp.ts.tzinfo else dp.ts.replace(tzinfo=timezone.utc)
                        lead_h = max(0.0, (dp_ts_utc - now_utc).total_seconds() / 3600.0)
                        dp.confidence_pct = compute_confidence_pct(s_t, s_p, lead_h)

        # WEATHER-05b: Check for missing metrics and fetch fallback
        cache = self._load_availability_cache()
        if cache is None:
            try:
                logger.info("Availability cache missing/expired — auto-probing...")
                cache = self.probe_model_availability()
            except Exception as e:
                logger.warning("Auto-probe failed: %s", e)
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
                                # Issue #1115: don't clobber an endpoint-level
                                # 5xx fallback marker — keep that model_id, only
                                # record which metrics this gap-fill supplied.
                                if timeseries.meta.fallback_reason != "model_5xx":
                                    timeseries.meta.fallback_model = fb_id
                                    timeseries.meta.fallback_reason = "metric_gap"
                                timeseries.meta.fallback_metrics = filled
                                logger.info("Fallback %s filled: %s", fb_id, ", ".join(filled))
                        except Exception as e:
                            logger.warning("Fallback %s failed: %s", fb_id, e)

        return timeseries
