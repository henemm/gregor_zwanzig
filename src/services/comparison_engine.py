"""
Comparison Engine — extracted from the former NiceGUI compare page (Epic #129 Phase A.1; the source module was removed in Phase A.3).

Single processor for ski resort / location comparisons. Generates a
ComparisonResult that is consumed by both the Web UI and the email renderers,
guaranteeing identical content across all output formats.

No NiceGUI dependency.

SPEC: docs/specs/epic_129a_1_compare_helpers.md
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.config import Location
from app.user import ComparisonResult, LocationResult, SavedLocation
from services.comparison_scoring import calculate_score
from services.forecast import ForecastService
from services.weather_metrics import WeatherMetricsService
from validation.ground_truth import BergfexScraper

if TYPE_CHECKING:
    from datetime import date
    from app.profile import ActivityProfile
    from app.config import Settings

logger = logging.getLogger("comparison_engine")

# Issue #1305 (Scheibe A4 von Epic #1301): Vorhersagehorizont fuer den
# Ortsvergleich. Seit A2 (#1303) liefert OpenMeteo bis zu
# OPENMETEO_MAX_FORECAST_DAYS=15 Tage; 96h (4 Tage) deckt den spaeteren
# 3-Tage-Ausblick (Scheibe B4) ab und bleibt weit unter der API-Grenze.
# EINE Konstante fuer Versand + Vorschau + beide Engine-Defaults verhindert
# Drift zwischen den Pfaden (Fehlerklasse #1297).
COMPARE_FORECAST_HOURS = 96


class ComparisonEngine:
    """
    Single processor for ski resort comparisons.

    Generates ComparisonResult used by both Web UI and Email renderers.
    Guarantees identical content across all output formats.
    """

    @staticmethod
    def run(
        locations: List[SavedLocation],
        time_window: tuple[int, int],
        target_date: "date",
        forecast_hours: int = COMPARE_FORECAST_HOURS,
        profile: Optional["ActivityProfile"] = None,
        official_alerts_enabled: bool = True,
    ) -> ComparisonResult:
        """
        Run comparison for given locations and time window.

        Args:
            locations: List of locations to compare
            time_window: (start_hour, end_hour) tuple
            target_date: Date to forecast for
            forecast_hours: Hours ahead to fetch
            official_alerts_enabled: Issue #1040 — bei False werden die
                #1034-Official-Alert-Quellen fuer keinen der Orte abgefragt
                (strukturell kein Fetch, nicht nur Ausblenden im Rendering).

        Returns:
            ComparisonResult with all metrics for all locations
        """
        from app.config import Settings

        # Issue #347: configurable sunny-hours DNI band (GZ_SUNNY_* env overrides)
        settings = Settings()
        results: List[LocationResult] = []

        for loc in locations:
            try:
                # Fetch forecast
                raw_result = fetch_forecast_for_location(loc, forecast_hours)

                if raw_result.get("error"):
                    results.append(LocationResult(
                        location=loc,
                        error=raw_result["error"],
                    ))
                    continue

                # Get raw data
                raw_data = raw_result.get("raw_data", [])

                # Filter by target date and time window
                start_hour, end_hour = time_window
                # Window length (inclusive) drives the sunshine SHARE bonus (#366)
                window_hours = end_hour - start_hour + 1
                filtered_data = [
                    dp for dp in raw_data
                    if dp.ts.date() == target_date
                    and start_hour <= dp.ts.hour <= end_hour
                ]

                # Calculate metrics from filtered data
                metrics: Dict[str, Any] = {}

                if filtered_data:
                    # Temperature
                    temps = [dp.t2m_c for dp in filtered_data if dp.t2m_c is not None]
                    if temps:
                        metrics["temp_min"] = min(temps)
                        metrics["temp_max"] = max(temps)

                    # Wind
                    winds = [dp.wind10m_kmh for dp in filtered_data if dp.wind10m_kmh is not None]
                    if winds:
                        metrics["wind_max"] = max(winds)

                    # Gusts
                    gusts = [dp.gust_kmh for dp in filtered_data if dp.gust_kmh is not None]
                    if gusts:
                        metrics["gust_max"] = max(gusts)

                    # Wind direction (circular average)
                    wind_dirs = [dp.wind_direction_deg for dp in filtered_data if dp.wind_direction_deg is not None]
                    if wind_dirs:
                        # Circular mean for directions
                        import math
                        sin_sum = sum(math.sin(math.radians(d)) for d in wind_dirs)
                        cos_sum = sum(math.cos(math.radians(d)) for d in wind_dirs)
                        avg_dir = math.degrees(math.atan2(sin_sum, cos_sum))
                        metrics["wind_direction_avg"] = int(avg_dir) % 360

                    # Wind chill
                    wc = [dp.wind_chill_c for dp in filtered_data if dp.wind_chill_c is not None]
                    if wc:
                        metrics["wind_chill_min"] = min(wc)

                    # Clouds - use effective cloud for high elevations
                    # SPEC: docs/specs/cloud_cover_simplification.md
                    effective_clouds = []
                    for dp in filtered_data:
                        eff = WeatherMetricsService.calculate_effective_cloud(
                            elevation_m=loc.elevation_m,
                            cloud_total_pct=dp.cloud_total_pct,
                            cloud_mid_pct=getattr(dp, 'cloud_mid_pct', None),
                            cloud_high_pct=getattr(dp, 'cloud_high_pct', None),
                        )
                        if eff is not None:
                            effective_clouds.append(eff)
                    if effective_clouds:
                        metrics["cloud_avg"] = int(sum(effective_clouds) / len(effective_clouds))

                    # Flag: is location above low clouds? (elevation >= 2500m)
                    metrics["above_low_clouds"] = (
                        loc.elevation_m is not None
                        and loc.elevation_m >= WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M
                    )

                    # Sonnenstunden: Use WeatherMetricsService (Single Source of Truth)
                    metrics["sunny_hours"] = WeatherMetricsService.calculate_sunny_hours(
                        filtered_data, loc.elevation_m, settings=settings
                    )

                    # Cloud layers for "Wolkenlage" analysis
                    cloud_low = [dp.cloud_low_pct for dp in filtered_data if dp.cloud_low_pct is not None]
                    cloud_mid = [dp.cloud_mid_pct for dp in filtered_data if dp.cloud_mid_pct is not None]
                    cloud_high = [dp.cloud_high_pct for dp in filtered_data if dp.cloud_high_pct is not None]
                    if cloud_low:
                        metrics["cloud_low_avg"] = int(sum(cloud_low) / len(cloud_low))
                    if cloud_mid:
                        metrics["cloud_mid_avg"] = int(sum(cloud_mid) / len(cloud_mid))
                    if cloud_high:
                        metrics["cloud_high_avg"] = int(sum(cloud_high) / len(cloud_high))

                    # Issue #1285: Tages-Aggregate fuer Regen/Sicht/UV. Regeln
                    # kanonisch aus dem Trip-Pfad (WeatherMetricsService:
                    # Regen SUM, Sicht MIN, UV MAX) -- dieselbe Wetterlage muss
                    # im Vergleich denselben Tageswert ergeben wie im Briefing.
                    precips = [dp.precip_1h_mm for dp in filtered_data if dp.precip_1h_mm is not None]
                    if precips:
                        metrics["precip_sum_mm"] = sum(precips)
                    vis = [dp.visibility_m for dp in filtered_data if dp.visibility_m is not None]
                    if vis:
                        metrics["visibility_min_m"] = min(vis)
                    uvs = [dp.uv_index for dp in filtered_data if dp.uv_index is not None]
                    if uvs:
                        metrics["uv_index_max"] = max(uvs)

                # Snow data
                snow_depth = raw_result.get("snow_depth_cm")
                snow_new = raw_result.get("snow_new_cm", 0)
                metrics["snow_depth_cm"] = snow_depth
                metrics["snow_new_cm"] = snow_new

                # Thunder/CAPE/PoP for wandern scoring
                thunder_levels = [dp.thunder_level for dp in filtered_data if dp.thunder_level is not None]
                if thunder_levels:
                    level_rank = {"NONE": 0, "MED": 1, "HIGH": 2}
                    metrics["thunder_level"] = max(thunder_levels, key=lambda x: level_rank.get(x, 0))
                pops = [dp.pop_pct for dp in filtered_data if dp.pop_pct is not None]
                if pops:
                    metrics["pop_max_pct"] = max(pops)

                # Calculate score (profile-aware)
                effective_profile = profile or getattr(loc, 'activity_profile', None)
                score = calculate_score(metrics, profile=effective_profile, window_hours=window_hours)

                # Issue #1034 — amtliche Warnungen, additiv, nur im Erfolgszweig.
                # Issue #1040: strukturell kein Fetch bei official_alerts_enabled=False.
                if official_alerts_enabled:
                    try:
                        from services.official_alerts import get_official_alerts_for_location
                        official_alerts = get_official_alerts_for_location(loc.lat, loc.lon)
                    except Exception:
                        logger.warning(
                            "comparison_engine: official_alerts nicht ladbar — "
                            "Alerts fuer diesen Ort deaktiviert", exc_info=True,
                        )
                        official_alerts = []
                else:
                    official_alerts = []

                results.append(LocationResult(
                    location=loc,
                    score=score,
                    official_alerts=official_alerts,
                    snow_depth_cm=snow_depth,
                    snow_new_cm=snow_new,
                    temp_min=metrics.get("temp_min"),
                    temp_max=metrics.get("temp_max"),
                    wind_max=metrics.get("wind_max"),
                    wind_direction_avg=metrics.get("wind_direction_avg"),
                    gust_max=metrics.get("gust_max"),
                    wind_chill_min=metrics.get("wind_chill_min"),
                    cloud_avg=metrics.get("cloud_avg"),
                    cloud_low_avg=metrics.get("cloud_low_avg"),
                    cloud_mid_avg=metrics.get("cloud_mid_avg"),
                    cloud_high_avg=metrics.get("cloud_high_avg"),
                    above_low_clouds=metrics.get("above_low_clouds", False),
                    sunny_hours=metrics.get("sunny_hours"),
                    # Issue #1285: thunder_level und pop_max_pct wurden hier
                    # schon immer berechnet (s.o.), aber beim Bau des
                    # LocationResult verworfen -- reiner Verdrahtungs-Fix.
                    precip_sum_mm=metrics.get("precip_sum_mm"),
                    thunder_level_max=metrics.get("thunder_level"),
                    visibility_min_m=metrics.get("visibility_min_m"),
                    uv_index_max=metrics.get("uv_index_max"),
                    pop_max_pct=metrics.get("pop_max_pct"),
                    hourly_data=filtered_data,
                ))

            except Exception as e:
                results.append(LocationResult(
                    location=loc,
                    error=str(e),
                ))

        # Sort by score (descending)
        results.sort(key=lambda r: r.score if r.error is None else -1, reverse=True)

        return ComparisonResult(
            locations=results,
            time_window=time_window,
            target_date=target_date,
        )


def dict_to_comparison_result(
    results: List[Dict[str, Any]],
    time_window: tuple[int, int],
    target_date: Any,
) -> ComparisonResult:
    """
    Convert dict-based results from UI to ComparisonResult dataclass.

    This enables the UI button to use the same renderer as subscriptions.
    """
    from datetime import date

    if target_date is None:
        target_date = date.today()

    location_results = []
    for r in results:
        if r.get("error"):
            continue
        loc_result = LocationResult(
            location=r["location"],
            score=r.get("score", 0),
            snow_depth_cm=r.get("snow_depth_cm"),
            snow_new_cm=r.get("snow_new_cm"),
            temp_min=r.get("temp_min"),
            temp_max=r.get("temp_max"),
            wind_max=r.get("wind_max"),
            wind_direction_avg=r.get("wind_direction_avg"),
            gust_max=r.get("gust_max"),
            wind_chill_min=r.get("wind_chill_min"),
            cloud_avg=r.get("cloud_avg"),
            cloud_low_avg=r.get("cloud_low_avg"),
            cloud_mid_avg=r.get("cloud_mid_avg"),
            cloud_high_avg=r.get("cloud_high_avg"),
            sunny_hours=r.get("sunny_hours"),
            hourly_data=r.get("hourly_data", []),
        )
        location_results.append(loc_result)

    return ComparisonResult(
        locations=location_results,
        time_window=time_window,
        target_date=target_date,
    )


def fetch_forecast_for_location(
    loc: SavedLocation,
    hours: int = COMPARE_FORECAST_HOURS,
    settings: Optional["Settings"] = None,
) -> Dict[str, Any]:
    """Fetch forecast for a location and extract all available metrics.

    Issue #347: optional ``settings`` is passed through to
    ``calculate_sunny_hours`` so custom DNI bands can be used; ``None`` -> defaults.
    """
    result: Dict[str, Any] = {
        "location": loc,
        "error": None,
        "forecast_hours": hours,
        "snow_source": None,  # Track where snow data comes from
    }

    try:
        from providers.base import get_provider

        provider = get_provider("openmeteo")
        service = ForecastService(provider)

        location = Location(
            latitude=loc.lat,
            longitude=loc.lon,
            name=loc.name,
            elevation_m=loc.elevation_m,
        )

        forecast = service.get_forecast(location, hours_ahead=hours)
        if hasattr(provider, "close"):
            provider.close()

        # Fetch snow data from Bergfex if slug is available
        if loc.bergfex_slug:
            try:
                scraper = BergfexScraper()
                snow_report = scraper.get_snow_report(loc.bergfex_slug)
                if snow_report.snow_depth_mountain_cm is not None:
                    result["snow_depth_cm"] = snow_report.snow_depth_mountain_cm
                    result["snow_depth_valley_cm"] = snow_report.snow_depth_valley_cm
                    result["snow_condition"] = snow_report.snow_condition
                    result["snow_source"] = "bergfex"
            except Exception:
                pass  # Fall back to SNOWGRID if Bergfex fails

        # Extract all available metrics from forecast data
        if forecast.data:
            # Store raw data for hourly display
            result["raw_data"] = forecast.data

            # Time range
            timestamps = [dp.ts for dp in forecast.data]
            if timestamps:
                result["forecast_start"] = min(timestamps)
                result["forecast_end"] = max(timestamps)
                result["data_points"] = len(timestamps)

            # Temperature
            temps = [dp.t2m_c for dp in forecast.data if dp.t2m_c is not None]
            if temps:
                result["temp_min"] = min(temps)
                result["temp_max"] = max(temps)
                result["temp_avg"] = sum(temps) / len(temps)

            # Wind
            winds = [dp.wind10m_kmh for dp in forecast.data if dp.wind10m_kmh is not None]
            if winds:
                result["wind_min"] = min(winds)
                result["wind_max"] = max(winds)
                result["wind_avg"] = sum(winds) / len(winds)

            # Gusts
            gusts = [dp.gust_kmh for dp in forecast.data if dp.gust_kmh is not None]
            if gusts:
                result["gust_min"] = min(gusts)
                result["gust_max"] = max(gusts)

            # Clouds
            clouds = [dp.cloud_total_pct for dp in forecast.data if dp.cloud_total_pct is not None]
            if clouds:
                result["cloud_min"] = min(clouds)
                result["cloud_max"] = max(clouds)
                result["cloud_avg"] = int(sum(clouds) / len(clouds))

            # Cloud layers (from Open-Meteo)
            cloud_low = [dp.cloud_low_pct for dp in forecast.data if dp.cloud_low_pct is not None]
            cloud_mid = [dp.cloud_mid_pct for dp in forecast.data if dp.cloud_mid_pct is not None]
            cloud_high = [dp.cloud_high_pct for dp in forecast.data if dp.cloud_high_pct is not None]
            if cloud_low:
                result["cloud_low_avg"] = int(sum(cloud_low) / len(cloud_low))
            if cloud_mid:
                result["cloud_mid_avg"] = int(sum(cloud_mid) / len(cloud_mid))
            if cloud_high:
                result["cloud_high_avg"] = int(sum(cloud_high) / len(cloud_high))

            # Precipitation
            precips = [dp.precip_1h_mm for dp in forecast.data if dp.precip_1h_mm is not None]
            if precips:
                result["precip_mm"] = sum(precips)

            # Snow accumulation (max value = total new snow)
            snow_accs = [dp.snow_new_acc_cm for dp in forecast.data if dp.snow_new_acc_cm is not None]
            if snow_accs:
                result["snow_new_cm"] = max(snow_accs)
            else:
                result["snow_new_cm"] = 0

            # Current snow depth - use Bergfex if available, otherwise SNOWGRID
            if "snow_depth_cm" not in result:
                snow_depths = [dp.snow_depth_cm for dp in forecast.data if dp.snow_depth_cm is not None]
                if snow_depths:
                    result["snow_depth_cm"] = snow_depths[0]  # Current snapshot
                    result["snow_source"] = "snowgrid"

            # Snow Water Equivalent
            swe_values = [dp.swe_kgm2 for dp in forecast.data if dp.swe_kgm2 is not None]
            if swe_values:
                result["swe_kgm2"] = swe_values[0]

            # Snowfall limit (Schneefallgrenze)
            snowlimits = [dp.snowfall_limit_m for dp in forecast.data if dp.snowfall_limit_m is not None]
            if snowlimits:
                result["snowfall_limit_min"] = min(snowlimits)
                result["snowfall_limit_max"] = max(snowlimits)
                result["snowfall_limit_avg"] = int(sum(snowlimits) / len(snowlimits))

            # Wind chill (gefühlte Temperatur)
            wind_chills = [dp.wind_chill_c for dp in forecast.data if dp.wind_chill_c is not None]
            if wind_chills:
                result["wind_chill_min"] = min(wind_chills)
                result["wind_chill_max"] = max(wind_chills)
                result["wind_chill_avg"] = sum(wind_chills) / len(wind_chills)

            # Humidity
            humidities = [dp.humidity_pct for dp in forecast.data if dp.humidity_pct is not None]
            if humidities:
                result["humidity_min"] = min(humidities)
                result["humidity_max"] = max(humidities)
                result["humidity_avg"] = int(sum(humidities) / len(humidities))

            # Pressure
            pressures = [dp.pressure_msl_hpa for dp in forecast.data if dp.pressure_msl_hpa is not None]
            if pressures:
                result["pressure_min"] = min(pressures)
                result["pressure_max"] = max(pressures)
                result["pressure_avg"] = sum(pressures) / len(pressures)

            # Freezing level
            freezing = [dp.freezing_level_m for dp in forecast.data if dp.freezing_level_m is not None]
            if freezing:
                result["freezing_level_min"] = min(freezing)
                result["freezing_level_max"] = max(freezing)
                result["freezing_level_avg"] = int(sum(freezing) / len(freezing))

            # Visibility
            visibility = [dp.visibility_m for dp in forecast.data if dp.visibility_m is not None]
            if visibility:
                result["visibility_min"] = min(visibility)
                result["visibility_max"] = max(visibility)
                result["visibility_avg"] = int(sum(visibility) / len(visibility))

            # Sunny hours: Use WeatherMetricsService (Single Source of Truth)
            from app.config import Settings
            result["sunny_hours"] = WeatherMetricsService.calculate_sunny_hours(
                forecast.data, loc.elevation_m, settings=settings or Settings()
            )

        result["score"] = calculate_score(result, profile=getattr(loc, 'activity_profile', None) if 'loc' in dir() else None)

    except Exception as e:
        result["error"] = str(e)
        result["score"] = 0

    return result
