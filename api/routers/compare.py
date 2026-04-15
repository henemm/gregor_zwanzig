"""
Compare API endpoint — runs ComparisonEngine and returns JSON.
"""
from fastapi import APIRouter, Query
from typing import Optional
from datetime import date, datetime

router = APIRouter(tags=["compare"])


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
    from app.user import LocationActivityProfile
    from web.pages.compare import ComparisonEngine

    all_locations = load_all_locations()

    if location_ids == '*':
        selected = all_locations
    else:
        ids = [id.strip() for id in location_ids.split(',')]
        selected = [loc for loc in all_locations if loc.id in ids]

    if not selected:
        return {"error": "no_locations_found", "locations": []}

    # Default: if before 14:00 → today, else tomorrow
    if target_date:
        td = date.fromisoformat(target_date)
    else:
        now = datetime.now()
        if now.hour < 14:
            td = date.today()
        else:
            from datetime import timedelta
            td = date.today() + timedelta(days=1)

    profile = None
    if activity_profile:
        try:
            profile = LocationActivityProfile(activity_profile)
        except ValueError:
            pass  # Invalid profile → default to allgemein

    result = ComparisonEngine.run(
        locations=selected,
        time_window=(time_window_start, time_window_end),
        target_date=td,
        forecast_hours=forecast_hours,
        profile=profile,
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
