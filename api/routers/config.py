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


@router.get("/templates")
def get_templates() -> list[dict]:
    """Return all weather activity templates."""
    from app.metric_catalog import get_all_templates
    return get_all_templates()


@router.get("/sms-symbols")
def get_sms_symbols():
    """Read-only Serialisierung der SMS-Kuerzel-Kataloge (Issue #1318 AC-9).

    Eigener Endpoint statt Erweiterung von `/metrics`: dessen Antwort ist ein
    `Record<Kategorie, Metrik[]>`, in das die 9 Gefahrenarten nur als
    Pseudo-Kategorie passten — sie wuerden dann von jedem Katalog-Konsumenten
    (autoAssign, allCatalogIds) als waehlbare Metriken missverstanden. Ein
    schreibgeschuetzter Endpoint schafft weniger Flaeche als dieser Umbau.
    Quelle bleibt allein das Backend: `hazard_symbols.py` (Gefahren) und
    `sms_trip.py` (Metriken) — das Frontend fuehrt keine zweite Liste.
    """
    from output.renderers.alert.official_alerts import _HAZARD_LABELS
    from output.renderers.sms_trip import SMS_SYMBOL_BY_METRIC
    from output.tokens.hazard_symbols import HAZARD_SMS_SYMBOLS

    return {
        "metrics": [
            {"metric_id": mid, "sms_symbol": sym.rstrip(":")}
            for mid, sym in SMS_SYMBOL_BY_METRIC.items()
        ],
        "hazards": [
            {"hazard": h, "sms_symbol": sym, "label": _HAZARD_LABELS.get(h, h)}
            for h, sym in HAZARD_SMS_SYMBOLS.items()
        ],
    }


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
            "has_friendly_format": m.has_friendly_format,
            # Issue #435: Format-Modi pro Metrik (raw/scale/simplified/symbol)
            "format_modes": list(m.format_modes),
            "default_format_mode": m.default_format_mode,
            "col_label": m.col_label,
            # Issue #914 Slice 1: Alert-Render-Stammdaten
            "sms_code": m.sms_code,
            "decimals": m.decimals,
            "cmp": m.cmp,
        })
    return result
