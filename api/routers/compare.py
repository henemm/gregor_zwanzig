"""
Compare API endpoint — runs ComparisonEngine and returns JSON.
"""
from fastapi import APIRouter, Query
from typing import Optional
from datetime import date, datetime

router = APIRouter(tags=["compare"])


@router.get("/api/compare/metrics")
def get_compare_metrics(lang: Optional[str] = Query(None, description="de|en, sonst de")):
    """Backend-Katalog der Ortsvergleich-Metriken (Issue #1350).

    #2751: ``lang`` waehlt die Sprache der Begruendung „stuendlich nicht
    waehlbar"; der Katalog ist statisch, daher Query statt Kontosprache.
    Unbekannte Werte ergeben ``de``.

    Read-only, kein user_id-Bezug (statischer Katalog, analog /api/metrics).
    Die Strangler-Migration ist mit #1350 Teil 3 abgeschlossen: das Frontend
    konsumiert diesen Endpoint produktiv ueber
    `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts`
    (`fetchCompareMetricCatalogOnce()`); der Backend-Katalog ist damit die
    Quelle, nicht mehr compareMetricDefs.ts.
    """
    from output.renderers.compare_metric_catalog import get_compare_metric_catalog

    return {"metrics": get_compare_metric_catalog(lang="en" if lang == "en" else "de")}


def _pruefe_eingaben(user_id: str, forecast_hours: int, start: int, ende: int,
                     target_date: Optional[str]) -> Optional[date]:
    """Issue #2961 (ADR-0117): Eingabegrenzen vor jedem Abruf. Obergrenze des
    Horizonts ist der groesste, den das Produkt selbst nutzt
    (``COMPARE_FORECAST_HOURS``, Versand und Vorschau); Stunden 0..23."""
    from api.fehler import api_fehler
    from services.comparison_engine import COMPARE_FORECAST_HOURS

    if not 1 <= forecast_hours <= COMPARE_FORECAST_HOURS:
        raise api_fehler(422, "vergleich_parameter_ungueltig", user_id,
                         parameter="forecast_hours", erlaubt=f"1-{COMPARE_FORECAST_HOURS}")
    for name, wert in (("time_window_start", start), ("time_window_end", ende)):
        if not 0 <= wert <= 23:
            raise api_fehler(422, "vergleich_parameter_ungueltig", user_id,
                             parameter=name, erlaubt="0-23")
    if not target_date:
        return None
    try:
        return date.fromisoformat(target_date)
    except ValueError:
        raise api_fehler(422, "vergleich_parameter_ungueltig", user_id,
                         parameter="target_date", erlaubt="YYYY-MM-DD") from None


def _kontingent_ganz_erschoepft(result, user_id: str) -> None:
    """Liefert KEIN Ort Daten, weil das interaktive Kontingent erschoepft ist,
    antwortet der Vergleich mit 429 statt einer Liste leerer Orte. Sonst
    bleibt der Hinweis je Ort (``error``/``error_code``) sichtbar."""
    from api.fehler import kontingent_erschoepft
    from services.comparison_engine import KONTINGENT_CODE

    orte = result.locations
    if orte and all(lr.error_code == KONTINGENT_CODE for lr in orte):
        raise kontingent_erschoepft(user_id)


@router.get("/api/compare")
def run_comparison(
    location_ids: str = Query(..., description="Comma-separated location IDs, or '*' for all"),
    user_id: str = Query(..., description="Session-User (vom Go-Proxy injiziert)"),
    target_date: Optional[str] = Query(None, description="YYYY-MM-DD, defaults to today/tomorrow based on time"),
    time_window_start: int = Query(9),
    time_window_end: int = Query(16),
    forecast_hours: int = Query(48),
    activity_profile: Optional[str] = Query(None, description="Activity profile: wintersport, wandern, allgemein"),
):
    from app.loader import load_all_locations
    from app.profile import ActivityProfile
    from services.comparison_parallel import run_comparison_parallel
    from services.forecast_budget import interaktiver_abruf

    gewaehltes_datum = _pruefe_eingaben(
        user_id, forecast_hours, time_window_start, time_window_end, target_date,
    )
    all_locations = load_all_locations(user_id=user_id)

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
    if gewaehltes_datum is not None:
        td = gewaehltes_datum
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
    # Issue #2961 (ADR-0117): der Sofortvergleich ist ein interaktiver
    # Ausloeser und bucht auf das interaktive Kontingent des Nutzers.
    with interaktiver_abruf(user_id):
        result = run_comparison_parallel(
            locations=selected,
            time_window=(time_window_start, time_window_end),
            target_date=td,
            forecast_hours=forecast_hours,
            profile=profile,
            call_source="vergleich",
            user_id=user_id,  # Issue #2234: Budget beim ausloesenden Nutzer
        )
    _kontingent_ganz_erschoepft(result, user_id)

    # Convert to JSON-serializable dict
    locations_data = []
    for loc_result in result.locations:
        entry = {
            "id": loc_result.location.id,
            "name": loc_result.location.name,
            "elevation_m": loc_result.location.elevation_m,
            "score": loc_result.score,
            "error": loc_result.error,
            "error_code": loc_result.error_code,
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
