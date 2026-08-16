"""
Compare API endpoint — runs ComparisonEngine and returns JSON.
"""
from fastapi import APIRouter, Query
from typing import Optional
from datetime import date, datetime

router = APIRouter(tags=["compare"])


@router.get("/api/compare/metrics")
def get_compare_metrics():
    """Backend-Katalog der 26 Ortsvergleich-Metriken (Issue #1350 Teil 1).

    Read-only, kein user_id-Bezug (statischer Katalog, analog /api/metrics).
    Teil 1 der Strangler-Migration: der Endpoint wird bereitgestellt, aber
    vom Frontend noch nicht konsumiert (compareMetricDefs.ts bleibt Quelle
    bis Teil 2).
    """
    from output.renderers.compare_metric_catalog import get_compare_metric_catalog

    return {"metrics": get_compare_metric_catalog()}


@router.get("/api/compare")
def run_comparison(
    location_ids: str = Query(..., description="Comma-separated location IDs, or '*' for all"),
    target_date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today/tomorrow based on time"),
    time_window_start: int = Query(9),
    time_window_end: int = Query(16),
    forecast_hours: int = Query(48),
    activity_profile: Optional[str] = Query(None, description="Activity profile: wintersport, wandern, allgemein"),
):
    from app.loader import load_all_locations
    from app.profile import ActivityProfile
    from services.comparison_parallel import run_comparison_parallel

    all_locations = load_all_locations()

    if location_ids == '*':
        selected = all_locations
    else:
        ids = [id.strip() for id in location_ids.split(',')]
        selected = [loc for loc in all_locations if loc.id in ids]

    if not selected:
        return {"error": "no_locations_found", "locations": []}

    # Default: if before 14:00 → today, else tomorrow (Issue #1727 S5c,
    # ADR-0044): "14:00" ist die ORTSZEIT des ersten aufloesbaren Orts, nicht
    # mehr die zonenlose Serveruhr — Stunde UND Tag kommen aus DERSELBEN
    # Aufloesung, sonst waere die Schwelle in sich widersprochen.
    if target_date:
        td = date.fromisoformat(target_date)
    else:
        from datetime import timedelta, timezone

        from utils.timezone import first_resolvable_tz, local_dt

        zone = first_resolvable_tz(selected, context_label="Sofort-Vergleich")
        local_now = local_dt(datetime.now(timezone.utc), zone)
        td = local_now.date() if local_now.hour < 14 else local_now.date() + timedelta(days=1)

    profile = None
    if activity_profile:
        try:
            profile = ActivityProfile(activity_profile)
        except ValueError:
            pass  # Invalid profile → default to allgemein

    # Issue #1765 Scheibe B1b: die Orte werden gleichzeitig statt nacheinander
    # gerechnet (ein Engine-Lauf JE ORT) -- sonst riss der Sofortvergleich ab
    # drei Orten die 60-Sekunden-Grenze zwischen Go-API und nginx. Alle uebrigen
    # Parameter unveraendert; ``comparison_engine.py`` bleibt unangetastet.
    # ``call_source`` MUSS ausdruecklich gesetzt werden: ein ThreadPoolExecutor
    # reicht den ContextVar-Kontext nicht an seine Arbeiter weiter.
    result = run_comparison_parallel(
        locations=selected,
        time_window=(time_window_start, time_window_end),
        target_date=td,
        forecast_hours=forecast_hours,
        profile=profile,
        call_source="vergleich",
    )

    # Convert to JSON-serializable dict
    locations_data = []
    for loc_result in result.locations:
        entry = {
            "id": loc_result.location.id,
            "name": loc_result.location.name,
            "elevation_m": loc_result.location.elevation_m,
            "score": loc_result.score,
            "error": loc_result.error,
            "snow_depth_cm": loc_result.snow_depth_cm,
            "snow_new_cm": loc_result.snow_new_cm,
            "temp_min": loc_result.temp_min,
            "temp_max": loc_result.temp_max,
            "wind_max": loc_result.wind_max,
            "wind_direction_avg": loc_result.wind_direction_avg,
            "gust_max": loc_result.gust_max,
            "wind_chill_min": loc_result.wind_chill_min,
            "cloud_avg": loc_result.cloud_avg,
            "sunny_hours": loc_result.sunny_hours,
            "above_low_clouds": loc_result.above_low_clouds,
        }
        # Include hourly data for top locations
        if loc_result.hourly_data:
            entry["hourly"] = [
                {
                    "ts": dp.ts.isoformat(),
                    "t2m_c": dp.t2m_c,
                    "wind10m_kmh": dp.wind10m_kmh,
                    "gust_kmh": dp.gust_kmh,
                    "precip_1h_mm": dp.precip_1h_mm,
                    "cloud_total_pct": dp.cloud_total_pct,
                    "wmo_code": dp.wmo_code,
                    # Issue #1475 S5a: Hagel-Kennzeichen im SELBEN hourly-
                    # Eintrag wie sein Rohwert-Ursprung `wmo_code` -- sonst
                    # stiller Feldverlust beim Serialisieren (Praezedenz
                    # #1265/#1349).
                    "hail_flag": dp.hail_flag,
                    "is_day": dp.is_day,
                }
                for dp in loc_result.hourly_data
            ]
        locations_data.append(entry)

    winner = result.winner
    return {
        "target_date": td.isoformat(),
        "time_window": [time_window_start, time_window_end],
        "created_at": result.created_at.isoformat(),
        "winner": {"id": winner.location.id, "name": winner.location.name, "score": winner.score} if winner else None,
        "locations": locations_data,
    }
