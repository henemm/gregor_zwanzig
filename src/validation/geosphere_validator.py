"""
GeoSphere API Response Validator.

Makes raw API calls and validates that our parser extracts values correctly.
This is the TDD ground truth: raw JSON response vs parsed output.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import httpx


@dataclass
class RawSnowgridData:
    """Raw SNOWGRID data extracted directly from API response."""

    snow_depth_m: Optional[float]  # Raw value in meters
    snow_depth_cm: Optional[float]  # Converted to cm
    swe_tot: Optional[float]  # Snow water equivalent
    timestamps: List[str]
    raw_json: Dict[str, Any]  # Full response for debugging


@dataclass
class RawNwpData:
    """Raw NWP data extracted directly from API response."""

    timestamps: List[str]
    t2m: List[Optional[float]]  # Temperature in Kelvin or Celsius
    u10m: List[Optional[float]]  # Wind U component m/s
    v10m: List[Optional[float]]  # Wind V component m/s
    tcc: List[Optional[float]]  # Cloud cover 0-1
    sp: List[Optional[float]]  # Surface pressure Pa
    raw_json: Dict[str, Any]


class GeoSphereValidator:
    """
    Validates GeoSphere API responses by making raw calls.

    Used in TDD to verify our parser extracts values correctly.
    """

    BASE_URL = "https://dataset.api.hub.geosphere.at/v1"
    TIMEOUT = 30.0

    def __init__(self) -> None:
        self._client = httpx.Client(timeout=self.TIMEOUT)

    def fetch_raw_snowgrid(
        self, lat: float, lon: float, days_back: int = 7
    ) -> RawSnowgridData:
        """
        Fetch raw SNOWGRID response without any parsing.

        Returns the exact values from the API for validation.
        """
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days_back)

        params = {
            "lat_lon": f"{lat},{lon}",
            "parameters": "snow_depth,swe_tot",
            "output_format": "geojson",
            "start": start.strftime("%Y-%m-%dT%H:%M"),
            "end": end.strftime("%Y-%m-%dT%H:%M"),
        }

        url = f"{self.BASE_URL}/timeseries/historical/snowgrid_cl-v2-1d-1km"
        response = self._client.get(f"{url}?{urlencode(params)}")
        response.raise_for_status()
        data = response.json()

        # Extract raw values without transformation
        timestamps = data.get("timestamps", [])
        features = data.get("features", [])

        snow_depth_m = None
        swe_tot = None

        if features:
            props = features[0].get("properties", {})
            params_data = props.get("parameters", {})

            snow_depth_list = params_data.get("snow_depth", {}).get("data", [])
            swe_list = params_data.get("swe_tot", {}).get("data", [])

            # Get latest non-null value
            if snow_depth_list:
                snow_depth_m = snow_depth_list[-1]
            if swe_list:
                swe_tot = swe_list[-1]

        return RawSnowgridData(
            snow_depth_m=snow_depth_m,
            snow_depth_cm=round(snow_depth_m * 100, 1) if snow_depth_m else None,
            swe_tot=swe_tot,
            timestamps=timestamps,
            raw_json=data,
        )

    def fetch_raw_nwp(
        self, lat: float, lon: float
    ) -> RawNwpData:
        """
        Fetch raw NWP (AROME) response without parsing.

        Returns exact values from API for validation.
        """
        params = {
            "lat_lon": f"{lat},{lon}",
            "parameters": "t2m,u10m,v10m,tcc,sp",
            "output_format": "geojson",
        }

        url = f"{self.BASE_URL}/timeseries/forecast/nwp-v1-1h-2500m"
        response = self._client.get(f"{url}?{urlencode(params)}")
        response.raise_for_status()
        data = response.json()

        timestamps = data.get("timestamps", [])
        features = data.get("features", [])

        t2m: List[Optional[float]] = []
        u10m: List[Optional[float]] = []
        v10m: List[Optional[float]] = []
        tcc: List[Optional[float]] = []
        sp: List[Optional[float]] = []

        if features:
            props = features[0].get("properties", {})
            params_data = props.get("parameters", {})

            t2m = params_data.get("t2m", {}).get("data", [])
            u10m = params_data.get("u10m", {}).get("data", [])
            v10m = params_data.get("v10m", {}).get("data", [])
            tcc = params_data.get("tcc", {}).get("data", [])
            sp = params_data.get("sp", {}).get("data", [])

        return RawNwpData(
            timestamps=timestamps,
            t2m=t2m,
            u10m=u10m,
            v10m=v10m,
            tcc=tcc,
            sp=sp,
            raw_json=data,
        )

    def validate_snowgrid_parsing(
        self, lat: float, lon: float
    ) -> Dict[str, Any]:
        """
        Validate that our GeoSphereProvider parses SNOWGRID correctly.

        Returns comparison of raw API values vs parsed values.
        """
        from providers.geosphere import GeoSphereProvider

        # Get raw data
        raw = self.fetch_raw_snowgrid(lat, lon)

        # Get parsed data from our provider
        provider = GeoSphereProvider()
        parsed_depth, parsed_swe = provider.fetch_snowgrid(lat, lon)

        # Compare
        depth_match = (
            raw.snow_depth_cm == parsed_depth
            if raw.snow_depth_cm is not None and parsed_depth is not None
            else raw.snow_depth_cm is None and parsed_depth is None
        )

        return {
            "coordinates": {"lat": lat, "lon": lon},
            "raw_api": {
                "snow_depth_m": raw.snow_depth_m,
                "snow_depth_cm": raw.snow_depth_cm,
                "swe_tot": raw.swe_tot,
            },
            "parsed": {
                "snow_depth_cm": parsed_depth,
                "swe_kgm2": parsed_swe,
            },
            "validation": {
                "depth_matches": depth_match,
                "difference_cm": (
                    abs((raw.snow_depth_cm or 0) - (parsed_depth or 0))
                    if raw.snow_depth_cm is not None and parsed_depth is not None
                    else None
                ),
            },
        }

    def validate_nwp_parsing(
        self, lat: float, lon: float
    ) -> Dict[str, Any]:
        """
        Validate that our GeoSphereProvider parses NWP correctly.

        Compares first data point raw vs parsed.
        """
        import math

        from providers.geosphere import GeoSphereProvider

        # Get raw data
        raw = self.fetch_raw_nwp(lat, lon)

        # Get parsed data
        provider = GeoSphereProvider()
        parsed = provider.fetch_nwp_forecast(lat, lon)

        if not parsed.data or not raw.timestamps:
            return {"error": "No data available"}

        # Compare first data point
        first_parsed = parsed.data[0]
        idx = 0

        # Raw values
        raw_temp = raw.t2m[idx] if idx < len(raw.t2m) else None
        raw_u = raw.u10m[idx] if idx < len(raw.u10m) else None
        raw_v = raw.v10m[idx] if idx < len(raw.v10m) else None
        raw_tcc = raw.tcc[idx] if idx < len(raw.tcc) else None
        raw_sp = raw.sp[idx] if idx < len(raw.sp) else None

        # Expected transformations
        expected_wind_kmh = (
            round(math.sqrt((raw_u or 0) ** 2 + (raw_v or 0) ** 2) * 3.6, 1)
            if raw_u is not None and raw_v is not None
            else None
        )
        expected_cloud_pct = int(raw_tcc * 100) if raw_tcc is not None else None
        expected_pressure_hpa = round(raw_sp / 100, 1) if raw_sp else None

        return {
            "coordinates": {"lat": lat, "lon": lon},
            "timestamp": raw.timestamps[idx] if raw.timestamps else None,
            "raw_api": {
                "t2m": raw_temp,
                "u10m": raw_u,
                "v10m": raw_v,
                "tcc": raw_tcc,
                "sp": raw_sp,
            },
            "expected_after_transform": {
                "t2m_c": round(raw_temp, 1) if raw_temp is not None else None,
                "wind10m_kmh": expected_wind_kmh,
                "cloud_total_pct": expected_cloud_pct,
                "pressure_msl_hpa": expected_pressure_hpa,
            },
            "parsed": {
                "t2m_c": first_parsed.t2m_c,
                "wind10m_kmh": first_parsed.wind10m_kmh,
                "cloud_total_pct": first_parsed.cloud_total_pct,
                "pressure_msl_hpa": first_parsed.pressure_msl_hpa,
            },
            "validation": {
                "temp_matches": first_parsed.t2m_c == (
                    round(raw_temp, 1) if raw_temp is not None else None
                ),
                "wind_matches": first_parsed.wind10m_kmh == expected_wind_kmh,
                "cloud_matches": first_parsed.cloud_total_pct == expected_cloud_pct,
                "pressure_matches": first_parsed.pressure_msl_hpa == expected_pressure_hpa,
            },
        }
