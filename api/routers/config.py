"""Config endpoint — exposes non-sensitive settings."""
from fastapi import APIRouter

router = APIRouter()

# Fields safe to expose (no secrets)
SAFE_FIELDS = {
    "latitude", "longitude", "location_name", "elevation_m",
    "provider", "report_type", "channel", "debug_level",
    "dry_run", "forecast_hours", "include_snow",
}


@router.get("/config")
def get_config():
    from app.config import Settings

    settings = Settings()
    full = settings.model_dump()
    return {k: v for k, v in full.items() if k in SAFE_FIELDS}
