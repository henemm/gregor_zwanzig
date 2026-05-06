"""MET Norway LocationForecast provider adapter."""

from typing import Any


def ms_to_kmh(value: float) -> float:
    """Convert m/s to km/h."""
    return round(value * 3.6, 1)


def map_symbol(symbol_code: str) -> str:
    """
    Map MET symbol_code to normalized symbol.

    MET symbols may have suffixes like _day/_night/_polartwilight.
    We strip these and normalize to the canonical symbol set.
    """
    # Strip time-of-day suffixes
    base_symbol = symbol_code.replace("_day", "").replace("_night", "").replace("_polartwilight", "")

    # Direct mapping for known symbols
    # MET symbols align well with our canonical set
    return base_symbol


def get_thunder_level(symbol_code: str) -> str:
    """
    Determine thunder_level from symbol_code.

    According to api_contract.md:
    - MET: symbol_code contains "thunder" => HIGH, else NONE
    """
    if "thunder" in symbol_code.lower():
        return "HIGH"
    return "NONE"


def normalize(api_response: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize MET Norway LocationForecast API response to schema format.

    Args:
        api_response: Raw MET API response (GeoJSON format)

    Returns:
        Normalized forecast timeseries conforming to normalized_timeseries.schema.json
    """
    properties = api_response["properties"]
    meta_data = properties["meta"]
    timeseries = properties["timeseries"]

    # Build meta
    meta = {
        "provider": "MET",
        "model": "ECMWF",  # MET uses ECMWF for most forecasts
        "run": meta_data["updated_at"],
        "grid_res_km": 9,  # MET Norway uses ~9km grid resolution
        "interp": "point_grid",  # Point forecast, no station interpolation
        "stations_used": []
    }

    # Build data array
    data = []
    for item in timeseries:
        instant = item["data"]["instant"]["details"]
        next_1h = item["data"].get("next_1_hours", {})
        next_1h_details = next_1h.get("details", {})
        next_1h_summary = next_1h.get("summary", {})

        # Get precipitation (from next_1_hours)
        precip_1h = next_1h_details.get("precipitation_amount", 0.0)

        # Get symbol (from next_1_hours summary)
        symbol_code = next_1h_summary.get("symbol_code", "clearsky")

        # Required fields
        data_point = {
            "ts": item["time"],
            "t2m_c": instant["air_temperature"],
            "wind10m_kmh": ms_to_kmh(instant["wind_speed"]),
            "precip_rate_mmph": precip_1h,  # 1h amount = rate in mm/h
            "cloud_total_pct": int(instant["cloud_area_fraction"]),
            "symbol": map_symbol(symbol_code),
            "thunder_level": get_thunder_level(symbol_code),
        }

        # Optional fields (only add if not None)
        gust = instant.get("wind_speed_of_gust")
        if gust is not None:
            data_point["gust_kmh"] = ms_to_kmh(gust)

        if precip_1h is not None:
            data_point["precip_1h_mm"] = precip_1h

        data_point["pressure_msl_hpa"] = instant["air_pressure_at_sea_level"]
        data_point["humidity_pct"] = int(instant["relative_humidity"])

        # Fields MET does not provide: cape_jkg, pop_pct, dewpoint_c
        # We omit them entirely rather than setting to None
        data.append(data_point)

    return {
        "meta": meta,
        "data": data
    }
