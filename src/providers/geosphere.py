"""
GeoSphere Austria Weather Provider.

Provides access to Austrian weather data via the GeoSphere Data Hub API:
- AROME (NWP): High-resolution forecast (2.5km, 60h)
- SNOWGRID: Daily snow depth analysis (1km)
- NOWCAST: Short-term forecast (1km, 3h)

API Documentation: https://dataset.api.hub.geosphere.at/v1/docs/
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    PrecipType,
    Provider,
)
from providers.base import ProviderRequestError

if TYPE_CHECKING:
    from app.config import Location

# API Configuration
BASE_URL = "https://dataset.api.hub.geosphere.at/v1"
TIMEOUT = 30.0

# Endpoints - using timeseries for point queries (grid requires bbox)
ENDPOINTS = {
    "nwp": "/timeseries/forecast/nwp-v1-1h-2500m",
    "snowgrid": "/timeseries/historical/snowgrid_cl-v2-1d-1km",
    "nowcast": "/timeseries/forecast/nowcast-v1-15min-1km",
}

# Parameter mappings for NWP (AROME)
NWP_PARAMS = [
    "t2m",       # Temperature 2m
    "u10m",      # Wind U component
    "v10m",      # Wind V component
    "ugust",     # Gust U component
    "vgust",     # Gust V component
    "rr_acc",    # Precipitation accumulated
    "snow_acc",  # Snow accumulated
    "snowlmt",   # Snowfall limit
    "tcc",       # Total cloud cover
    "rh2m",      # Relative humidity
    "sp",        # Surface pressure
]

# Snowgrid parameters
SNOWGRID_PARAMS = ["snow_depth", "swe_tot"]

# Nowcast parameters
NOWCAST_PARAMS = ["t2m", "ff", "fx", "rr", "pt", "rh2m"]


def _vector_to_speed_kmh(u: float, v: float) -> float:
    """Convert U/V wind components (m/s) to speed (km/h)."""
    speed_ms = math.sqrt(u**2 + v**2)
    return round(speed_ms * 3.6, 1)


def _calculate_wind_chill(temp_c: float, wind_kmh: float) -> float:
    """
    Calculate wind chill temperature using the North American formula.
    Valid for temperatures <= 10C and wind >= 4.8 km/h.
    """
    if temp_c > 10 or wind_kmh < 4.8:
        return temp_c
    wc = (
        13.12
        + 0.6215 * temp_c
        - 11.37 * (wind_kmh**0.16)
        + 0.3965 * temp_c * (wind_kmh**0.16)
    )
    return round(wc, 1)


def _precip_type_from_code(code: Optional[int]) -> Optional[PrecipType]:
    """Convert GeoSphere precipitation type code to enum."""
    if code is None:
        return None
    # GeoSphere pt codes (approximate mapping)
    if code == 0:
        return None  # No precipitation
    elif code == 1:
        return PrecipType.RAIN
    elif code == 2:
        return PrecipType.SNOW
    elif code == 3:
        return PrecipType.MIXED
    elif code == 4:
        return PrecipType.FREEZING_RAIN
    return None


class GeoSphereProvider:
    """
    Provider for GeoSphere Austria weather data.

    Supports:
    - AROME (NWP) forecast: 60h ahead, 2.5km resolution
    - SNOWGRID: Current snow depth, 1km resolution
    - NOWCAST: 3h ahead, 1km resolution (optional)

    Implements WeatherProvider protocol for use with ForecastService.
    """

    def __init__(self, client: Optional[httpx.Client] = None):
        self._client = client or httpx.Client(timeout=TIMEOUT)

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "geosphere"

    def fetch_forecast(
        self,
        location: "Location",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> NormalizedTimeseries:
        """
        Fetch weather forecast for a location.

        Implements WeatherProvider protocol. Delegates to fetch_combined()
        which merges AROME forecast with SNOWGRID snow data.

        Args:
            location: Geographic location to query
            start: Forecast start time (default: now)
            end: Forecast end time (default: +60h)

        Returns:
            NormalizedTimeseries with forecast data

        Raises:
            ProviderRequestError: If the request fails
        """
        try:
            return self.fetch_combined(
                lat=location.latitude,
                lon=location.longitude,
                start=start,
                end=end,
                include_snow=True,
            )
        except httpx.HTTPStatusError as e:
            raise ProviderRequestError(
                self.name, f"HTTP {e.response.status_code}: {e.response.text}"
            )
        except httpx.RequestError as e:
            raise ProviderRequestError(self.name, f"Request failed: {e}")

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "GeoSphereProvider":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _request(
        self,
        endpoint: str,
        lat: float,
        lon: float,
        parameters: List[str],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Make a request to the GeoSphere timeseries API."""
        params: Dict[str, Any] = {
            "lat_lon": f"{lat},{lon}",
            "parameters": ",".join(parameters),
            "output_format": "geojson",
        }
        if start:
            params["start"] = start.strftime("%Y-%m-%dT%H:%M")
        if end:
            params["end"] = end.strftime("%Y-%m-%dT%H:%M")

        url = f"{BASE_URL}{endpoint}?{urlencode(params)}"
        response = self._client.get(url)
        response.raise_for_status()
        return response.json()

    def fetch_nwp_forecast(
        self,
        lat: float,
        lon: float,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> NormalizedTimeseries:
        """
        Fetch AROME (NWP) forecast data.

        Args:
            lat: Latitude
            lon: Longitude
            start: Start time (default: now)
            end: End time (default: +60h)

        Returns:
            NormalizedTimeseries with forecast data
        """
        data = self._request(ENDPOINTS["nwp"], lat, lon, NWP_PARAMS, start, end)
        return self._parse_nwp_response(data)

    def fetch_snowgrid(
        self,
        lat: float,
        lon: float,
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Fetch current snow depth from SNOWGRID.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Tuple of (snow_depth_cm, swe_kgm2) or (None, None) if unavailable
        """
        try:
            # SNOWGRID requires start/end dates - fetch last 7 days
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=7)
            data = self._request(
                ENDPOINTS["snowgrid"], lat, lon, SNOWGRID_PARAMS,
                start=start, end=end
            )
            return self._parse_snowgrid_response(data)
        except httpx.HTTPStatusError:
            return None, None

    def fetch_nowcast(
        self,
        lat: float,
        lon: float,
    ) -> Optional[NormalizedTimeseries]:
        """
        Fetch NOWCAST short-term forecast (3h ahead).

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            NormalizedTimeseries or None if unavailable
        """
        try:
            data = self._request(ENDPOINTS["nowcast"], lat, lon, NOWCAST_PARAMS)
            return self._parse_nowcast_response(data)
        except httpx.HTTPStatusError:
            return None

    def fetch_combined(
        self,
        lat: float,
        lon: float,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        include_snow: bool = True,
    ) -> NormalizedTimeseries:
        """
        Fetch combined forecast with optional snow data.

        Combines AROME forecast with current SNOWGRID snow depth.

        Args:
            lat: Latitude
            lon: Longitude
            start: Start time
            end: End time
            include_snow: Whether to include SNOWGRID data

        Returns:
            NormalizedTimeseries with all available data
        """
        # Get main forecast
        ts = self.fetch_nwp_forecast(lat, lon, start, end)

        # Enrich with snow data if requested
        if include_snow and ts.data:
            snow_depth_cm, swe_kgm2 = self.fetch_snowgrid(lat, lon)
            if snow_depth_cm is not None:
                # Add snow depth to all data points (it's a snapshot)
                for dp in ts.data:
                    dp.snow_depth_cm = snow_depth_cm
                    dp.swe_kgm2 = swe_kgm2

        return ts

    def _parse_nwp_response(self, data: Dict[str, Any]) -> NormalizedTimeseries:
        """Parse NWP (AROME) API response into NormalizedTimeseries."""
        timestamps = data.get("timestamps", [])
        features = data.get("features", [])

        if not features:
            raise ValueError("No data in GeoSphere NWP response")

        feature = features[0]
        props = feature.get("properties", {})
        params = props.get("parameters", {})

        # Build metadata
        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="AROME",
            run=datetime.now(timezone.utc),  # API doesn't provide run time directly
            grid_res_km=2.5,
            interp="bilinear",
        )

        # Extract parameter data arrays
        t2m = params.get("t2m", {}).get("data", [])
        u10m = params.get("u10m", {}).get("data", [])
        v10m = params.get("v10m", {}).get("data", [])
        ugust = params.get("ugust", {}).get("data", [])
        vgust = params.get("vgust", {}).get("data", [])
        rr_acc = params.get("rr_acc", {}).get("data", [])
        snow_acc = params.get("snow_acc", {}).get("data", [])
        snowlmt = params.get("snowlmt", {}).get("data", [])
        tcc = params.get("tcc", {}).get("data", [])
        rh2m = params.get("rh2m", {}).get("data", [])
        sp = params.get("sp", {}).get("data", [])

        # Build data points
        data_points: List[ForecastDataPoint] = []
        prev_rr = 0.0
        prev_snow = 0.0

        for i, ts_str in enumerate(timestamps):
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

            # Get values with safe indexing
            temp = t2m[i] if i < len(t2m) else None
            u = u10m[i] if i < len(u10m) else 0
            v = v10m[i] if i < len(v10m) else 0
            ug = ugust[i] if i < len(ugust) else 0
            vg = vgust[i] if i < len(vgust) else 0
            rr = rr_acc[i] if i < len(rr_acc) else 0
            snow = snow_acc[i] if i < len(snow_acc) else 0
            slmt = snowlmt[i] if i < len(snowlmt) else None
            cloud = tcc[i] if i < len(tcc) else None
            rh = rh2m[i] if i < len(rh2m) else None
            pressure = sp[i] if i < len(sp) else None

            # Calculate derived values
            wind_kmh = _vector_to_speed_kmh(u or 0, v or 0)
            gust_kmh = _vector_to_speed_kmh(ug or 0, vg or 0)

            # Precipitation rate (difference from previous accumulated)
            precip_1h = (rr or 0) - prev_rr
            prev_rr = rr or 0

            # Snow accumulation (difference)
            snow_new = (snow or 0) - prev_snow
            prev_snow = snow or 0
            # Convert kg/m² to cm (approximate: 10 kg/m² ≈ 1 cm fresh snow)
            snow_new_cm = round(snow_new / 10, 1) if snow_new > 0 else 0

            # Wind chill
            wind_chill = None
            if temp is not None and wind_kmh > 0:
                wind_chill = _calculate_wind_chill(temp, wind_kmh)

            # Pressure conversion Pa -> hPa
            pressure_hpa = round(pressure / 100, 1) if pressure else None

            # Cloud cover: API returns 0-1, convert to 0-100
            cloud_pct = int(cloud * 100) if cloud is not None else None

            dp = ForecastDataPoint(
                ts=ts,
                t2m_c=round(temp, 1) if temp is not None else None,
                wind10m_kmh=wind_kmh,
                gust_kmh=gust_kmh,
                precip_1h_mm=round(precip_1h, 1) if precip_1h > 0 else 0,
                precip_rate_mmph=round(precip_1h, 1) if precip_1h > 0 else 0,
                cloud_total_pct=cloud_pct,
                humidity_pct=int(rh) if rh is not None else None,
                pressure_msl_hpa=pressure_hpa,
                snow_new_acc_cm=round((snow or 0) / 10, 1),
                snowfall_limit_m=int(slmt) if slmt is not None else None,
                wind_chill_c=wind_chill,
            )
            data_points.append(dp)

        return NormalizedTimeseries(meta=meta, data=data_points)

    def _parse_snowgrid_response(
        self, data: Dict[str, Any]
    ) -> Tuple[Optional[float], Optional[float]]:
        """Parse SNOWGRID response for snow depth and SWE."""
        features = data.get("features", [])
        if not features:
            return None, None

        props = features[0].get("properties", {})
        params = props.get("parameters", {})

        # Get latest values
        snow_depth_data = params.get("snow_depth", {}).get("data", [])
        swe_data = params.get("swe_tot", {}).get("data", [])

        snow_depth_m = snow_depth_data[-1] if snow_depth_data else None
        swe = swe_data[-1] if swe_data else None

        # Convert m to cm
        snow_depth_cm = round(snow_depth_m * 100, 1) if snow_depth_m else None

        return snow_depth_cm, swe

    def _parse_nowcast_response(self, data: Dict[str, Any]) -> NormalizedTimeseries:
        """Parse NOWCAST API response."""
        timestamps = data.get("timestamps", [])
        features = data.get("features", [])

        if not features:
            raise ValueError("No data in GeoSphere NOWCAST response")

        feature = features[0]
        props = feature.get("properties", {})
        params = props.get("parameters", {})

        meta = ForecastMeta(
            provider=Provider.GEOSPHERE,
            model="NOWCAST",
            run=datetime.now(timezone.utc),
            grid_res_km=1.0,
            interp="bilinear",
        )

        t2m = params.get("t2m", {}).get("data", [])
        ff = params.get("ff", {}).get("data", [])
        fx = params.get("fx", {}).get("data", [])
        rr = params.get("rr", {}).get("data", [])
        pt = params.get("pt", {}).get("data", [])
        rh = params.get("rh2m", {}).get("data", [])

        data_points: List[ForecastDataPoint] = []

        for i, ts_str in enumerate(timestamps):
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

            temp = t2m[i] if i < len(t2m) else None
            wind = ff[i] if i < len(ff) else None
            gust = fx[i] if i < len(fx) else None
            precip = rr[i] if i < len(rr) else None
            ptype = pt[i] if i < len(pt) else None
            humidity = rh[i] if i < len(rh) else None

            wind_kmh = round(wind * 3.6, 1) if wind else None
            gust_kmh = round(gust * 3.6, 1) if gust else None

            dp = ForecastDataPoint(
                ts=ts,
                t2m_c=round(temp, 1) if temp is not None else None,
                wind10m_kmh=wind_kmh,
                gust_kmh=gust_kmh,
                precip_1h_mm=round(precip, 1) if precip else None,
                humidity_pct=int(humidity) if humidity is not None else None,
                precip_type=_precip_type_from_code(ptype),
            )
            data_points.append(dp)

        return NormalizedTimeseries(meta=meta, data=data_points)
