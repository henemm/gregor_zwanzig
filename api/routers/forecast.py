"""Forecast endpoint — returns NormalizedTimeseries as JSON."""
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from i18n import t

router = APIRouter()
logger = logging.getLogger(__name__)


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
    # Issue #1991: optionaler Hoehen-Override fuer diesen ad-hoc
    # Koordinaten-Endpunkt (kein Wegpunkt-Objekt vorhanden, aus dem sich
    # die Hoehe ableiten liesse). Ohne Angabe unveraendertes Verhalten
    # (Open-Meteo ermittelt die Hoehe selbst aus dem DEM).
    elevation_m: Optional[int] = Query(default=None),
):
    from app.config import Location
    from providers.openmeteo import OpenMeteoProvider
    from services.forecast import ForecastService

    location = Location(latitude=lat, longitude=lon, elevation_m=elevation_m)
    service = ForecastService(OpenMeteoProvider())

    # F002 fix: Structured error response for provider failures
    try:
        ts = service.get_forecast(location, hours_ahead=hours)
    except Exception as e:
        # #2961: Ausnahmetext (Hosts, Pfade) nur ins Log, nach aussen Katalogtext.
        logger.warning("Forecast-Abruf fehlgeschlagen (%s): %s", type(e).__name__, e)  # i18n-log
        raise HTTPException(status_code=502, detail={
            "error": "provider_error",
            "detail": t("api.fehler.wetterdienst_fehler", "de"),
        })

    raw = asdict(ts)
    return _clean_dict(raw)
