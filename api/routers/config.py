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


@router.get("/metrics")
def get_metrics():
    from app.metric_catalog import get_all_metrics
    metrics = get_all_metrics()
    result = {}
    for m in metrics:
        cat = m.category
        if cat not in result:
            result[cat] = []
        result[cat].append({
            "id": m.id,
            "label": m.label_de,
            "unit": m.display_unit if m.display_unit else m.unit,
            "category": m.category,
            "default_enabled": m.default_enabled,
        })
    return result
