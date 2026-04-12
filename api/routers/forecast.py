"""Forecast endpoint — returns NormalizedTimeseries as JSON."""
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


def _serialize(obj):
    """Custom serializer for dataclass fields."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        # F001 fix: Ensure timezone-aware ISO8601 output
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.isoformat()
    return obj


def _clean_dict(d: dict) -> dict:
    """Remove None values and serialize enums/datetimes."""
    result = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            result[k] = _clean_dict(v)
        elif isinstance(v, list):
            result[k] = [
                _clean_dict(i) if isinstance(i, dict) else _serialize(i)
                for i in v
            ]
        else:
            result[k] = _serialize(v)
    return result


@router.get("/forecast")
def get_forecast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    hours: int = Query(default=48, ge=1, le=168),
):
    from app.config import Location
    from providers.openmeteo import OpenMeteoProvider
    from services.forecast import ForecastService

    location = Location(latitude=lat, longitude=lon)
    service = ForecastService(OpenMeteoProvider())

    # F002 fix: Structured error response for provider failures
    try:
        ts = service.get_forecast(location, hours_ahead=hours)
    except Exception as e:
        raise HTTPException(status_code=502, detail={
            "error": "provider_error",
            "detail": str(e),
        })

    raw = asdict(ts)
    return _clean_dict(raw)
