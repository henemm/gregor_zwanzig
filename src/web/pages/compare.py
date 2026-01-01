"""
Forecast comparison page.

Use case: "Welches Skigebiet morgen?"
Compare multiple locations side-by-side with scoring.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from nicegui import ui

from app.config import Location, Settings
from app.loader import load_all_locations, load_compare_subscriptions
from app.models import ForecastDataPoint
from app.user import CompareSubscription, ComparisonResult, LocationResult, SavedLocation
from outputs.email import EmailOutput
from outputs.base import OutputConfigError, OutputError
from providers.geosphere import GeoSphereProvider
from services.forecast import ForecastService
from services.weather_metrics import CloudStatus, HourlyCell, WeatherMetricsService
from validation.ground_truth import BergfexScraper


def filter_data_by_hours(
    data: List[ForecastDataPoint],
    start_hour: int,
    end_hour: int,
) -> List[ForecastDataPoint]:
    """Filter forecast data to specific hours of the day.

    Args:
        data: List of ForecastDataPoint objects
        start_hour: Start hour (0-23), inclusive
        end_hour: End hour (0-23), exclusive

    Returns:
        Filtered list of data points within the time window
    """
    return [dp for dp in data if start_hour <= dp.ts.hour < end_hour]


def calculate_score(metrics: Dict[str, Any]) -> int:
    """
    Calculate a score for ski conditions (higher = better).

    Factors considered:
    - Schneehöhe: Basis für gutes Skifahren
    - Neuschnee: Frischer Powder
    - Sonnenstunden: Gute Sicht, angenehm
    - Wind/Böen: Liftbetrieb, Komfort
    - Wolken: Sicht, Stimmung
    - Temperatur: Ideale Kälte für guten Schnee
    - Niederschlag: Regen ist schlecht
    """
    score = 50  # Base score

    # Snow depth bonus (max +15)
    snow_depth = metrics.get("snow_depth_cm")
    if snow_depth:
        if snow_depth >= 100:
            score += 15
        elif snow_depth >= 50:
            score += 10
        elif snow_depth >= 30:
            score += 5

    # New snow bonus (max +25)
    snow_cm = metrics.get("snow_new_cm", 0)
    if snow_cm:
        snow_bonus = min(25, int(snow_cm * 2))
        score += snow_bonus

    # Sunny hours bonus (max +15)
    sunny_hours = metrics.get("sunny_hours")
    if sunny_hours is not None:
        if sunny_hours >= 6:
            score += 15
        elif sunny_hours >= 4:
            score += 10
        elif sunny_hours >= 2:
            score += 5

    # Wind penalty (max -20)
    wind_max = metrics.get("wind_max")
    if wind_max:
        if wind_max > 60:
            score -= 20
        elif wind_max > 40:
            score -= 12
        elif wind_max > 25:
            score -= 5

    # Gust penalty (max -10)
    gust_max = metrics.get("gust_max")
    if gust_max:
        if gust_max > 80:
            score -= 10
        elif gust_max > 60:
            score -= 5

    # Cloud penalty (max -10)
    cloud_avg = metrics.get("cloud_avg")
    if cloud_avg is not None:
        if cloud_avg > 80:
            score -= 10
        elif cloud_avg > 60:
            score -= 5

    # Temperature (ideal: -5 to -10)
    temp_min = metrics.get("temp_min")
    if temp_min is not None:
        if temp_min < -20:
            score -= 10  # Too cold
        elif temp_min > 5:
            score -= 10  # Too warm for good snow
        elif -10 <= temp_min <= -3:
            score += 5  # Ideal powder temperature

    # Precipitation penalty (rain during skiing)
    precip_mm = metrics.get("precip_mm", 0)
    if precip_mm > 0 and temp_min and temp_min > 0:
        score -= 15  # Rain is bad

    # Visibility bonus/penalty
    visibility_min = metrics.get("visibility_min")
    if visibility_min is not None:
        if visibility_min < 500:
            score -= 10  # Very poor visibility
        elif visibility_min < 1000:
            score -= 5  # Poor visibility
        elif visibility_min >= 10000:
            score += 5  # Excellent visibility

    return max(0, min(100, score))


def _format_score_cell(score: int, plain: bool) -> str:
    """Format score with or without emoji."""
    if plain:
        return str(score)
    if score >= 80:
        return f"🏆 {score}"
    elif score >= 60:
        return f"✅ {score}"
    elif score >= 40:
        return f"👌 {score}"
    return f"⚠️ {score}"


def _format_temp_cell(temp: float | None, plain: bool) -> str:
    """Format temperature with or without emoji."""
    if temp is None:
        return "-"
    temp_str = f"{temp:.0f}C"
    if plain:
        return temp_str
    if temp < -15:
        return f"🥶 {temp_str}"
    elif temp < 0:
        return f"❄️ {temp_str}"
    elif temp < 10:
        return f"🌡️ {temp_str}"
    return f"☀️ {temp_str}"


def _format_wind_cell(wind: float | None, plain: bool) -> str:
    """Format wind with or without emoji."""
    if wind is None:
        return "-"
    wind_str = f"{wind:.0f}km/h"
    if plain:
        return wind_str
    if wind < 15:
        return f"🍃 {wind_str}"
    elif wind < 30:
        return f"💨 {wind_str}"
    elif wind < 50:
        return f"🌬️ {wind_str}"
    return f"💪 {wind_str}"


def _degrees_to_compass(degrees: int | None) -> str:
    """Convert degrees (0-360) to compass direction."""
    if degrees is None:
        return "-"
    directions = ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]
    idx = int((degrees + 22.5) / 45) % 8
    return directions[idx]


# REMOVED: _calc_effective_cloud - now in WeatherMetricsService
# Use: WeatherMetricsService.calculate_effective_cloud()


def _format_wind_direction_cell(degrees: int | None, plain: bool) -> str:
    """Format wind direction with degrees and compass."""
    if degrees is None:
        return "-"
    compass = _degrees_to_compass(degrees)
    if plain:
        return f"{compass} ({degrees}°)"
    return f"🧭 {compass} ({degrees}°)"


def _format_snow_cell(snow_cm: float, plain: bool) -> str:
    """Format snow with or without emoji."""
    if not snow_cm:
        return "-"
    snow_str = f"+{snow_cm:.0f}cm"
    if plain:
        return snow_str
    if snow_cm >= 20:
        return f"❄️❄️ {snow_str}"
    elif snow_cm >= 10:
        return f"❄️ {snow_str}"
    return snow_str


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
        forecast_hours: int = 48,
    ) -> ComparisonResult:
        """
        Run comparison for given locations and time window.

        Args:
            locations: List of locations to compare
            time_window: (start_hour, end_hour) tuple
            target_date: Date to forecast for
            forecast_hours: Hours ahead to fetch

        Returns:
            ComparisonResult with all metrics for all locations
        """
        from datetime import date, datetime

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
                    clouds = [dp.cloud_total_pct for dp in filtered_data if dp.cloud_total_pct is not None]
                    if clouds:
                        metrics["cloud_avg"] = int(sum(clouds) / len(clouds))

                    # Sonnenstunden: Use WeatherMetricsService (Single Source of Truth)
                    metrics["sunny_hours"] = WeatherMetricsService.calculate_sunny_hours(
                        filtered_data, loc.elevation_m
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

                # Snow data
                snow_depth = raw_result.get("snow_depth_cm")
                snow_new = raw_result.get("snow_new_cm", 0)
                metrics["snow_depth_cm"] = snow_depth
                metrics["snow_new_cm"] = snow_new

                # Calculate score
                score = calculate_score(metrics)

                results.append(LocationResult(
                    location=loc,
                    score=score,
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
                    sunny_hours=metrics.get("sunny_hours"),
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


def render_comparison_html(result: ComparisonResult, top_n_details: int = 3) -> str:
    """
    Render ComparisonResult as HTML for email.

    This is the single HTML renderer - used by both direct email and subscriptions.
    Guarantees identical output for identical ComparisonResult.

    Args:
        result: ComparisonResult from ComparisonEngine
        top_n_details: Number of locations to show hourly details for

    Returns:
        HTML string for email
    """
    now = datetime.now()
    time_window = result.time_window
    target_date = result.target_date
    valid_locs = result.valid_locations

    # Helper to find best index
    def find_best(values: List, higher_is_better: bool = True) -> int:
        valid = [(i, v) for i, v in enumerate(values) if v is not None]
        if not valid:
            return -1
        if higher_is_better:
            return max(valid, key=lambda x: x[1])[0]
        return min(valid, key=lambda x: x[1])[0]

    # Extract data from LocationResult objects
    location_names = [loc.location.name for loc in valid_locs]
    scores = [loc.score for loc in valid_locs]
    snow_depths = [loc.snow_depth_cm for loc in valid_locs]
    snow_news = [loc.snow_new_cm for loc in valid_locs]
    winds = [loc.wind_max for loc in valid_locs]
    wind_directions = [loc.wind_direction_avg for loc in valid_locs]
    gusts = [loc.gust_max for loc in valid_locs]
    wind_chills = [loc.wind_chill_min for loc in valid_locs]
    sunny_hours_list = [loc.sunny_hours for loc in valid_locs]
    clouds = [loc.cloud_avg for loc in valid_locs]
    cloud_lows = [loc.cloud_low_avg for loc in valid_locs]
    cloud_mids = [loc.cloud_mid_avg for loc in valid_locs]
    cloud_highs = [loc.cloud_high_avg for loc in valid_locs]
    elevations = [loc.location.elevation_m for loc in valid_locs]

    # Find bests
    best_score = find_best(scores, True)
    best_snow_depth = find_best(snow_depths, True)
    best_snow_new = find_best(snow_news, True)
    best_wind = find_best(winds, False)
    best_gust = find_best(gusts, False)
    best_wc = find_best(wind_chills, True)
    best_sunny = find_best(sunny_hours_list, True)
    best_clouds = find_best(clouds, False)

    # CSS Styles
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #1976d2, #42a5f5); color: white; padding: 24px; }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 24px; }}
        .header p {{ margin: 4px 0; opacity: 0.9; font-size: 14px; }}
        .winner {{ background: #e8f5e9; padding: 20px; border-left: 4px solid #4caf50; margin: 20px; border-radius: 8px; }}
        .winner h2 {{ margin: 0 0 8px 0; color: #2e7d32; font-size: 18px; }}
        .winner p {{ margin: 0; color: #555; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #f5f5f5; padding: 12px 8px; text-align: center; font-weight: 600; border-bottom: 2px solid #ddd; }}
        th.label {{ text-align: left; width: 140px; }}
        td {{ padding: 10px 8px; text-align: center; border-bottom: 1px solid #eee; }}
        td.label {{ text-align: left; font-weight: 500; color: #555; }}
        td.best {{ background: #e8f5e9; font-weight: 600; color: #2e7d32; }}
        .section {{ padding: 0 20px; }}
        .section h3 {{ color: #333; border-bottom: 2px solid #1976d2; padding-bottom: 8px; }}
        .footer {{ background: #f5f5f5; padding: 16px; text-align: center; color: #888; font-size: 12px; }}
        .rank {{ background: #1976d2; color: white; border-radius: 4px; padding: 2px 6px; font-size: 11px; margin-right: 4px; }}
        .weather {{ font-size: 16px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⛷️ Skigebiete-Vergleich</h1>
            <p>📅 Forecast für: <strong>{target_date.strftime('%A, %d.%m.%Y')}</strong></p>
            <p>🕐 Zeitfenster: {time_window[0]:02d}:00 - {time_window[1]:02d}:00</p>
            <p>📝 Erstellt: {now.strftime('%d.%m.%Y %H:%M')}</p>
        </div>
"""

    # Winner recommendation
    winner = result.winner
    if winner:
        details = []
        if winner.snow_depth_cm:
            details.append(f"❄️ {winner.snow_depth_cm:.0f}cm Schnee")
        if winner.snow_new_cm:
            details.append(f"🆕 +{winner.snow_new_cm:.0f}cm Neuschnee")
        if winner.sunny_hours:
            details.append(f"☀️ ~{winner.sunny_hours}h Sonne")

        html += f"""
        <div class="winner">
            <h2>🏆 Empfehlung: {winner.location.name}</h2>
            <p>Score: <strong>{winner.score}</strong> | {' | '.join(details) if details else 'Keine Details'}</p>
        </div>
"""

    # Helper to create cell
    def cell(val, formatter, is_best):
        formatted = formatter(val)
        cls = ' class="best"' if is_best else ''
        return f'<td{cls}>{formatted}</td>'

    # Comparison table
    html += """
        <div class="section">
            <h3>📊 Vergleich</h3>
            <table>
                <tr>
                    <th class="label">Metrik</th>
"""
    for i, name in enumerate(location_names):
        html += f'                    <th><span class="rank">#{i+1}</span> {name}</th>\n'
    html += "                </tr>\n"

    # Score row
    html += "                <tr>\n                    <td class=\"label\">Score</td>\n"
    for i, v in enumerate(scores):
        html += f"                    {cell(v, lambda x: str(x) if x else '-', i == best_score)}\n"
    html += "                </tr>\n"

    # Snow depth row
    html += "                <tr>\n                    <td class=\"label\">Schneehöhe</td>\n"
    for i, v in enumerate(snow_depths):
        html += f"                    {cell(v, lambda x: f'{x:.0f}cm' if x else '-', i == best_snow_depth)}\n"
    html += "                </tr>\n"

    # New snow row
    html += "                <tr>\n                    <td class=\"label\">Neuschnee</td>\n"
    for i, v in enumerate(snow_news):
        is_best = i == best_snow_new and v and v > 0
        html += f"                    {cell(v, lambda x: f'+{x:.0f}cm' if x else '-', is_best)}\n"
    html += "                </tr>\n"

    # Wind/Böen combined row: "10/41 SW"
    html += "                <tr>\n                    <td class=\"label\">Wind/Böen</td>\n"
    for i, (wind, gust, direction) in enumerate(zip(winds, gusts, wind_directions)):
        compass = _degrees_to_compass(direction)
        if wind is not None and gust is not None:
            text = f"{wind:.0f}/{gust:.0f} {compass}"
        elif wind is not None:
            text = f"{wind:.0f}/- {compass}"
        else:
            text = "-"
        is_best = i == best_wind
        cls = ' class="best"' if is_best else ''
        html += f'                    <td{cls}>{text}</td>\n'
    html += "                </tr>\n"

    # Wind chill row
    html += "                <tr>\n                    <td class=\"label\">Temperatur (gefühlt)</td>\n"
    for i, v in enumerate(wind_chills):
        html += f"                    {cell(v, lambda x: f'{x:.0f}°C' if x is not None else '-', i == best_wc)}\n"
    html += "                </tr>\n"

    # Sunny hours row (0 shows "0h", not "~0h" per spec)
    html += "                <tr>\n                    <td class=\"label\">Sonnenstunden</td>\n"
    for i, v in enumerate(sunny_hours_list):
        is_best = i == best_sunny and v is not None and v > 0
        # Spec: "~[N]h" for N>0, "0h" for N=0, "-" for None
        html += f"                    {cell(v, lambda x: '0h' if x == 0 else f'~{x}h' if x is not None else '-', is_best)}\n"
    html += "                </tr>\n"

    # Clouds row
    html += "                <tr>\n                    <td class=\"label\">Bewölkung</td>\n"
    for i, v in enumerate(clouds):
        html += f"                    {cell(v, lambda x: f'{x}%' if x is not None else '-', i == best_clouds)}\n"
    html += "                </tr>\n"

    # Wolkenlage row - uses WeatherMetricsService (Single Source of Truth)
    html += "                <tr>\n                    <td class=\"label\">Wolkenlage</td>\n"
    time_window_hours = time_window[1] - time_window[0] + 1  # Total hours in window
    for i, (sunny, cloud_low, elev) in enumerate(zip(sunny_hours_list, cloud_lows, elevations)):
        cloud_status = WeatherMetricsService.calculate_cloud_status(
            sunny, time_window_hours, elev, cloud_low
        )
        emoji = WeatherMetricsService.get_cloud_status_emoji(cloud_status)
        text, style_str = WeatherMetricsService.format_cloud_status(cloud_status)
        style = f' style="{style_str}"' if style_str else ''
        html += f'                    <td{style}>{emoji} {text}</td>\n'
    html += "                </tr>\n"

    html += """            </table>
            <p style="font-size: 12px; color: #888;">🟢 Grün = bester Wert | Temperatur = gefühlt (Wind Chill)</p>
        </div>
"""

    # Hourly details for top N locations
    # SPEC: docs/specs/compare_email.md v4.2 - HourlyCell Single Source of Truth
    top_locs = valid_locs[:top_n_details]
    if top_locs and any(loc.hourly_data for loc in top_locs):
        hours = list(range(time_window[0], time_window[1] + 1))

        # Build data structure: hour -> location_idx -> HourlyCell
        hour_data_map: Dict[int, Dict[int, HourlyCell]] = {h: {} for h in hours}

        for idx, loc_result in enumerate(top_locs):
            elevation_m = loc_result.location.elevation_m
            for dp in loc_result.hourly_data:
                if dp.ts.date() != target_date:
                    continue
                h = dp.ts.hour
                if h not in hours:
                    continue

                # Use Single Source of Truth formatter
                cell = WeatherMetricsService.format_hourly_cell(dp, elevation_m)
                hour_data_map[h][idx] = cell

        html += f"""
        <div class="section">
            <h3>🕐 Stündliche Übersicht</h3>
            <p style="color: #666; margin-bottom: 12px;">📅 {target_date.strftime('%A, %d.%m.%Y')}</p>
            <table>
                <tr>
                    <th class="label">Zeit</th>
"""
        for i, loc_result in enumerate(top_locs):
            html += f'                    <th><span class="rank">#{i+1}</span> {loc_result.location.name}</th>\n'
        html += "                </tr>\n"

        for h in hours:
            html += f"                <tr>\n                    <td class=\"label\">{h:02d}:00</td>\n"
            for idx in range(len(top_locs)):
                cell = hour_data_map[h].get(idx)
                if cell:
                    # Use compact format from Single Source of Truth
                    compact = WeatherMetricsService.hourly_cell_to_compact(cell)
                    html += f'                    <td style="white-space: nowrap;">{compact}</td>\n'
                else:
                    html += "                    <td>-</td>\n"
            html += "                </tr>\n"

        html += """            </table>
            <p style="font-size: 11px; color: #888; margin-top: 8px;">
                <strong>Legende:</strong>
                ☀️ &lt;20% Wolken |
                🌤️ 20-50% |
                ⛅ 50-80% |
                ☁️ &gt;80% |
                🌧️ Regen |
                ❄️ Schnee
            </p>
        </div>
"""

    # Footer
    html += """
        <div class="footer">
            <p>Generiert von <strong>Gregor Zwanzig</strong> ⛷️</p>
        </div>
    </div>
</body>
</html>
"""

    return html


def render_comparison_text(result: ComparisonResult, top_n_details: int = 3) -> str:
    """
    Render ComparisonResult as Plain-Text for email fallback.

    SPEC: docs/specs/compare_email.md v4.2 Zeile 274-327

    Uses HourlyCell Single Source of Truth for consistent formatting.

    Args:
        result: ComparisonResult from ComparisonEngine
        top_n_details: Number of locations to show hourly details for

    Returns:
        Plain-text string for email
    """
    from datetime import date

    time_window = result.time_window
    target_date = result.target_date
    created_at = result.created_at

    # Filter valid locations
    valid_locs = [loc for loc in result.locations if loc.score is not None]
    if not valid_locs:
        return "Keine Vergleichsdaten verfügbar."

    lines = []

    # Header
    lines.append("⛷️ SKIGEBIETE-VERGLEICH")
    lines.append("=" * 24)
    lines.append(f"📅 Forecast: {target_date.strftime('%A, %d.%m.%Y')}")
    lines.append(f"🕐 Zeitfenster: {time_window[0]:02d}:00 - {time_window[1]:02d}:00")
    lines.append(f"📝 Erstellt: {created_at.strftime('%d.%m.%Y %H:%M')}")
    lines.append("")

    # Winner
    winner = valid_locs[0]
    lines.append(f"🏆 EMPFEHLUNG: {winner.location.name}")
    snow = f"❄️ {winner.snow_depth_cm:.0f}cm" if winner.snow_depth_cm else "❄️ -"
    sunny = f"☀️ ~{winner.sunny_hours}h" if winner.sunny_hours is not None else "☀️ -"
    lines.append(f"   Score: {winner.score} | {snow} | {sunny}")
    lines.append("")

    # Comparison table (side by side, max 2 locations per row for readability)
    lines.append("-" * 50)
    for i, loc_result in enumerate(valid_locs):
        loc = loc_result.location
        lines.append(f"#{i+1} {loc.name}")
        lines.append(f"   Score: {loc_result.score}")
        lines.append(f"   Schnee: {loc_result.snow_depth_cm:.0f}cm" if loc_result.snow_depth_cm else "   Schnee: -")
        if loc_result.snow_new_cm and loc_result.snow_new_cm > 0:
            lines.append(f"   Neuschnee: +{loc_result.snow_new_cm:.0f}cm")
        else:
            lines.append("   Neuschnee: -")

        # Wind
        wind = loc_result.wind_max or 0
        gust = loc_result.gust_max or wind
        wind_dir = WeatherMetricsService.degrees_to_compass(loc_result.wind_direction_avg)
        lines.append(f"   Wind: {wind:.0f}/{gust:.0f} {wind_dir}")

        # Temperature
        temp = loc_result.wind_chill_min if loc_result.wind_chill_min is not None else loc_result.temp_min
        lines.append(f"   Temp: {temp:.0f}°C" if temp is not None else "   Temp: -")

        # Sunny hours
        sunny_h = loc_result.sunny_hours
        lines.append(f"   Sonne: ~{sunny_h}h" if sunny_h is not None else "   Sonne: -")

        # Cloud
        cloud = loc_result.cloud_avg
        lines.append(f"   Wolken: {cloud}%" if cloud is not None else "   Wolken: -")

        # Cloud status
        time_window_hours = time_window[1] - time_window[0]
        cloud_status = WeatherMetricsService.calculate_cloud_status(
            sunny_h, time_window_hours, loc.elevation_m, loc_result.cloud_low_avg
        )
        emoji = WeatherMetricsService.get_cloud_status_emoji(cloud_status)
        text, _ = WeatherMetricsService.format_cloud_status(cloud_status)
        lines.append(f"   Lage: {emoji} {text}")
        lines.append("")

    # Hourly details
    top_locs = valid_locs[:top_n_details]
    if top_locs and any(loc.hourly_data for loc in top_locs):
        lines.append("STUNDEN-DETAILS")
        lines.append("-" * 15)

        hours = list(range(time_window[0], time_window[1] + 1))

        # Header row
        header = "Zeit  |"
        for i, loc_result in enumerate(top_locs):
            name = loc_result.location.name[:14]
            header += f" #{i+1} {name:14} |"
        lines.append(header)

        # Data rows
        for h in hours:
            row = f"{h:02d}:00 |"
            for loc_result in top_locs:
                cell_text = "-"
                elevation_m = loc_result.location.elevation_m
                for dp in loc_result.hourly_data:
                    if dp.ts.date() == target_date and dp.ts.hour == h:
                        cell = WeatherMetricsService.format_hourly_cell(dp, elevation_m)
                        cell_text = WeatherMetricsService.hourly_cell_to_compact(cell)
                        break
                row += f" {cell_text:16} |"
            lines.append(row)

        lines.append("")

    # Footer
    lines.append("---")
    lines.append("Generiert von Gregor Zwanzig ⛷️")

    return "\n".join(lines)


def fetch_forecast_for_location(loc: SavedLocation, hours: int = 48) -> Dict[str, Any]:
    """Fetch forecast for a location and extract all available metrics."""
    result: Dict[str, Any] = {
        "location": loc,
        "error": None,
        "forecast_hours": hours,
        "snow_source": None,  # Track where snow data comes from
    }

    try:
        provider = GeoSphereProvider()
        service = ForecastService(provider)

        location = Location(
            latitude=loc.lat,
            longitude=loc.lon,
            name=loc.name,
            elevation_m=loc.elevation_m,
        )

        forecast = service.get_forecast(location, hours_ahead=hours)
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
            result["sunny_hours"] = WeatherMetricsService.calculate_sunny_hours(
                forecast.data, loc.elevation_m
            )

        result["score"] = calculate_score(result)

    except Exception as e:
        result["error"] = str(e)
        result["score"] = 0

    return result


def run_comparison_for_subscription(
    sub: CompareSubscription,
    all_locations: List[SavedLocation] | None = None,
) -> tuple[str, str, str]:
    """
    Run a comparison for a subscription and generate email content.

    SPEC: docs/specs/compare_email.md v4.2 - Multipart Email

    Uses ComparisonEngine (single processor) and both renderers
    to ensure identical content in Web UI and Email.

    Args:
        sub: CompareSubscription configuration
        all_locations: Optional pre-loaded locations list

    Returns:
        Tuple of (subject, html_body, text_body) for the email
    """
    from datetime import date, datetime, timedelta

    # Load locations if not provided
    if all_locations is None:
        all_locations = load_all_locations()

    # Determine which locations to compare
    if sub.locations == ["*"] or not sub.locations:
        selected_locs = all_locations
    else:
        selected_locs = [loc for loc in all_locations if loc.id in sub.locations]

    if not selected_locs:
        raise ValueError("No locations found for subscription")

    # Calculate minimum forecast hours needed to cover tomorrow's time window
    now = datetime.now()
    hours_remaining_today = 24 - now.hour
    hours_tomorrow_needed = sub.time_window_end + 1  # +1 to include the end hour
    min_forecast_hours = hours_remaining_today + hours_tomorrow_needed

    # Use at least the configured hours, but ensure we have enough for the time window
    actual_forecast_hours = max(sub.forecast_hours, min_forecast_hours, 48)

    # Target date is tomorrow
    target_date = date.today() + timedelta(days=1)

    # Use ComparisonEngine (Single Processor Architecture)
    result = ComparisonEngine.run(
        locations=selected_locs,
        time_window=(sub.time_window_start, sub.time_window_end),
        target_date=target_date,
        forecast_hours=actual_forecast_hours,
    )

    # Use both renderers for Multipart Email (SPEC v4.2)
    html_body = render_comparison_html(result, top_n_details=sub.top_n)
    text_body = render_comparison_text(result, top_n_details=sub.top_n)

    subject = f"Skigebiete-Vergleich: {sub.name} ({now.strftime('%d.%m.%Y')})"
    return subject, html_body, text_body


def render_header() -> None:
    """Render navigation header."""
    with ui.header().classes("items-center justify-between"):
        ui.label("Gregor Zwanzig").classes("text-h6")
        with ui.row():
            ui.link("Dashboard", "/").classes("text-white mx-2")
            ui.link("Locations", "/locations").classes("text-white mx-2")
            ui.link("Trips", "/trips").classes("text-white mx-2")
            ui.link("Vergleich", "/compare").classes("text-white mx-2")
            ui.link("Subscriptions", "/subscriptions").classes("text-white mx-2")
            ui.link("Settings", "/settings").classes("text-white mx-2")


def render_compare() -> None:
    """Render the forecast comparison page."""
    render_header()

    # State for the page
    state: Dict[str, Any] = {
        "results": [],
        "hourly_data": [],  # Raw hourly data for time window view
        "loading": False,
        "forecast_hours": 48,
        "time_start": 9,
        "time_end": 16,
        "target_date": None,  # The date we're forecasting for
    }

    with ui.column().classes("w-full max-w-6xl mx-auto p-4"):
        ui.label("Forecast-Vergleich").classes("text-h4 mb-4")
        ui.label("Welches Skigebiet hat die besten Bedingungen?").classes("text-gray-500 mb-4")

        locations = load_all_locations()

        if not locations:
            ui.label(
                "Keine Locations gespeichert. Bitte zuerst Locations anlegen."
            ).classes("text-gray-500")
            ui.button(
                "Locations verwalten",
                on_click=lambda: ui.navigate.to("/locations"),
            ).props("outline")
            return

        # Location selection
        with ui.card().classes("w-full mb-4"):
            ui.label("Locations auswählen").classes("text-h6 mb-2")

            location_options = {loc.id: f"{loc.name} ({loc.elevation_m}m)" for loc in locations}

            select = ui.select(
                options=location_options,
                multiple=True,
                label="Locations (Mehrfachauswahl)",
            ).classes("w-full").props("use-chips")

            with ui.row().classes("items-center gap-4 mt-2"):
                ui.label("Datum:")
                date_options = {
                    0: "Heute",
                    1: "Morgen",
                    2: "Übermorgen",
                }
                date_select = ui.select(
                    options=date_options,
                    value=1,
                    label="Tag",
                ).classes("w-32")

            with ui.row().classes("items-center gap-4 mt-2"):
                ui.label("Zeitfenster:")
                hour_options = {h: f"{h:02d}:00" for h in range(6, 22)}
                time_start_select = ui.select(
                    options=hour_options,
                    value=9,
                    label="Von",
                ).classes("w-28")
                ui.label("bis")
                time_end_select = ui.select(
                    options=hour_options,
                    value=16,
                    label="Bis",
                ).classes("w-28")

        # Results area with refreshable
        @ui.refreshable
        def results_ui() -> None:
            if state["loading"]:
                with ui.row().classes("items-center gap-2 mb-4"):
                    ui.spinner("dots", size="lg")
                    ui.label("Lade Forecasts...")
                return

            if not state["results"]:
                ui.label("Wähle Locations und klicke 'Vergleichen'").classes("text-gray-400 my-8")
                return

            # 1. Winner recommendation FIRST (answers "Welches Skigebiet?")
            render_winner_card(state["results"], target_date=state["target_date"])

            # 2. Comparison table (explains WHY - Score, Snow, Wind, etc.)
            render_results_table(state["results"])

            # 3. Hourly details LAST (deep dive for each hour)
            if state["hourly_data"]:
                render_hourly_table(
                    state["hourly_data"],
                    state["time_start"],
                    state["time_end"],
                    state["results"],  # Pass results for ranking
                )

        results_ui()

        async def run_comparison() -> None:
            if not select.value:
                ui.notify("Bitte mindestens eine Location auswählen", type="warning")
                return

            selected_locs = [loc for loc in locations if loc.id in select.value]
            days_ahead = date_select.value or 1
            time_start = time_start_select.value or 9
            time_end = time_end_select.value or 16

            # Calculate hours needed (from now until end of selected day)
            hours = (days_ahead + 1) * 24

            # Calculate target date
            from datetime import date, timedelta
            target_date = date.today() + timedelta(days=days_ahead)

            state["loading"] = True
            state["forecast_hours"] = hours
            state["time_start"] = time_start
            state["time_end"] = time_end
            state["target_date"] = target_date
            results_ui.refresh()

            # Fetch forecasts (run in background to not block UI)
            results: List[Dict[str, Any]] = []
            hourly_data: List[Dict[str, Any]] = []

            for loc in selected_locs:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda current_loc=loc: fetch_forecast_for_location(current_loc, hours)
                )
                results.append(result)

                # Extract hourly data for the selected day and time window
                if "raw_data" in result:
                    hourly_data.append({
                        "location": loc,
                        "data": result["raw_data"],
                        "days_ahead": days_ahead,
                    })

                    # Recalculate all metrics for selected day + time window only
                    from datetime import date, timedelta

                    target_date = date.today() + timedelta(days=days_ahead)
                    filtered_data = [
                        dp
                        for dp in result["raw_data"]
                        if dp.ts.date() == target_date
                        and time_start <= dp.ts.hour <= time_end
                    ]

                    if filtered_data:
                        # Temperature
                        temps = [dp.t2m_c for dp in filtered_data if dp.t2m_c is not None]
                        if temps:
                            result["temp_min"] = min(temps)
                            result["temp_max"] = max(temps)

                        # Wind
                        winds = [dp.wind10m_kmh for dp in filtered_data if dp.wind10m_kmh is not None]
                        if winds:
                            result["wind_min"] = min(winds)
                            result["wind_max"] = max(winds)

                        # Gusts
                        gusts = [dp.gust_kmh for dp in filtered_data if dp.gust_kmh is not None]
                        if gusts:
                            result["gust_max"] = max(gusts)

                        # Wind direction (circular average)
                        wind_dirs = [dp.wind_direction_deg for dp in filtered_data if dp.wind_direction_deg is not None]
                        if wind_dirs:
                            import math
                            sin_sum = sum(math.sin(math.radians(d)) for d in wind_dirs)
                            cos_sum = sum(math.cos(math.radians(d)) for d in wind_dirs)
                            avg_dir = math.degrees(math.atan2(sin_sum, cos_sum))
                            result["wind_direction_avg"] = int(avg_dir) % 360

                        # Wind chill
                        wc = [dp.wind_chill_c for dp in filtered_data if dp.wind_chill_c is not None]
                        if wc:
                            result["wind_chill_min"] = min(wc)
                            result["wind_chill_max"] = max(wc)

                        # Clouds
                        clouds = [dp.cloud_total_pct for dp in filtered_data if dp.cloud_total_pct is not None]
                        if clouds:
                            result["cloud_avg"] = int(sum(clouds) / len(clouds))

                        # Sunny hours: Use WeatherMetricsService (Single Source of Truth)
                        result["sunny_hours"] = WeatherMetricsService.calculate_sunny_hours(
                            filtered_data, loc.elevation_m
                        )

                        # Cloud layers
                        cl_low = [dp.cloud_low_pct for dp in filtered_data if dp.cloud_low_pct is not None]
                        cl_mid = [dp.cloud_mid_pct for dp in filtered_data if dp.cloud_mid_pct is not None]
                        cl_high = [dp.cloud_high_pct for dp in filtered_data if dp.cloud_high_pct is not None]
                        if cl_low:
                            result["cloud_low_avg"] = int(sum(cl_low) / len(cl_low))
                        if cl_mid:
                            result["cloud_mid_avg"] = int(sum(cl_mid) / len(cl_mid))
                        if cl_high:
                            result["cloud_high_avg"] = int(sum(cl_high) / len(cl_high))

                        # Precipitation
                        precips = [dp.precip_1h_mm for dp in filtered_data if dp.precip_1h_mm is not None]
                        if precips:
                            result["precip_mm"] = sum(precips)

                        # Recalculate score with filtered data
                        result["score"] = calculate_score(result)

            # Sort by score (highest first)
            results.sort(key=lambda r: r.get("score", 0), reverse=True)

            state["results"] = results
            state["hourly_data"] = hourly_data
            state["loading"] = False
            results_ui.refresh()

        async def send_email() -> None:
            """Send comparison results via email using single renderer."""
            if not state["results"]:
                ui.notify("Bitte zuerst einen Vergleich durchführen", type="warning")
                return

            try:
                settings = Settings()
                if not settings.can_send_email():
                    ui.notify(
                        "SMTP nicht konfiguriert. Bitte in Settings oder .env konfigurieren.",
                        type="negative",
                    )
                    return

                # Calculate target date based on days_ahead selection
                from datetime import date, timedelta
                days_ahead = state["hourly_data"][0].get("days_ahead", 1) if state["hourly_data"] else 1
                target_date = date.today() + timedelta(days=days_ahead)

                # Merge hourly_data into results for conversion
                results_with_hourly = []
                for i, r in enumerate(state["results"]):
                    r_copy = dict(r)
                    # Find matching hourly data by location object
                    for hd in state["hourly_data"]:
                        hd_loc = hd.get("location")
                        # Compare by object or by name (hd_loc can be SavedLocation or string)
                        if hd_loc == r["location"] or (hasattr(hd_loc, 'name') and hd_loc.name == r["location"].name):
                            r_copy["hourly_data"] = hd.get("data", [])
                            break
                    results_with_hourly.append(r_copy)

                # Convert to ComparisonResult and use single renderer
                # SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
                comparison_result = dict_to_comparison_result(
                    results=results_with_hourly,
                    time_window=(state["time_start"], state["time_end"]),
                    target_date=target_date,
                )
                email_html = render_comparison_html(comparison_result, top_n_details=3)
                email_text = render_comparison_text(comparison_result, top_n_details=3)

                # Send via SMTP with both HTML and Plain-Text
                email_output = EmailOutput(settings)
                subject = f"Skigebiete-Vergleich ({datetime.now().strftime('%d.%m.%Y')})"

                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: email_output.send(subject, email_html, plain_text_body=email_text)
                )

                ui.notify(f"E-Mail gesendet an {settings.mail_to}", type="positive")

            except OutputConfigError as e:
                ui.notify(f"SMTP-Konfigurationsfehler: {e}", type="negative")
            except OutputError as e:
                ui.notify(f"E-Mail-Versand fehlgeschlagen: {e}", type="negative")
            except Exception as e:
                ui.notify(f"Fehler: {e}", type="negative")

        # Check if email is configured
        settings = Settings()
        can_email = settings.can_send_email()

        with ui.row().classes("gap-2"):
            ui.button(
                "Vergleichen",
                on_click=run_comparison,
                icon="compare_arrows",
            ).props("color=primary size=lg")

            if can_email:
                ui.button(
                    "Per E-Mail senden",
                    on_click=send_email,
                    icon="email",
                ).props("outline size=lg")
            else:
                ui.button(
                    "E-Mail (nicht konfiguriert)",
                    icon="email",
                ).props("outline size=lg disabled").tooltip(
                    "SMTP in .env konfigurieren: GZ_SMTP_HOST, GZ_SMTP_USER, GZ_SMTP_PASS, GZ_MAIL_TO"
                )


def _render_cloud_bar(pct: int, color: str, label: str) -> None:
    """Render a small visual bar for cloud coverage."""
    with ui.row().classes("gap-0.5 items-center"):
        ui.label(label).classes("text-xs text-gray-400 w-3")
        with ui.element("div").classes("h-2 w-10 bg-gray-200 rounded"):
            ui.element("div").classes(f"h-2 bg-{color} rounded").style(f"width: {pct}%")


# REMOVED: get_weather_symbol - now in WeatherMetricsService
# Use: WeatherMetricsService.get_weather_symbol()


def render_hourly_table(
    hourly_data: List[Dict[str, Any]],
    time_start: int,
    time_end: int,
    results: List[Dict[str, Any]] | None = None,
) -> None:
    """
    Render hourly weather table with TRANSPOSED layout.

    Layout: Hours as rows, Locations as columns (consistent with comparison table).
    """
    if not hourly_data:
        return

    from datetime import date, timedelta

    # Get ranking from results (sorted by score)
    ranking = {}
    if results:
        for i, r in enumerate(results):
            if not r.get("error"):
                ranking[r["location"].id] = i + 1

    with ui.card().classes("w-full mb-4"):
        ui.label("Stündliche Übersicht").classes("text-subtitle1 font-medium mb-2")
        ui.label("Temperatur = gefühlt (Wind Chill)").classes("text-xs text-gray-500 mb-2")

        # Build hours list
        hours = list(range(time_start, time_end + 1))

        # Get target date from first entry
        days_ahead = hourly_data[0].get("days_ahead", 1) if hourly_data else 1
        target_date = date.today() + timedelta(days=days_ahead)

        # Build data structure: hour -> location -> cell_data
        # SPEC: docs/specs/compare_email.md v4.2 - HourlyCell Single Source of Truth
        hour_data: Dict[int, Dict[str, str]] = {h: {} for h in hours}

        for entry in hourly_data:
            loc = entry["location"]
            data_points = entry.get("data", [])
            elevation_m = loc.elevation_m

            for h in hours:
                cell_text = "-"
                for dp in data_points:
                    if dp.ts.date() == target_date and dp.ts.hour == h:
                        # Use Single Source of Truth formatter
                        cell = WeatherMetricsService.format_hourly_cell(dp, elevation_m)
                        cell_text = WeatherMetricsService.hourly_cell_to_compact(cell)
                        break
                hour_data[h][loc.id] = cell_text

        # Render transposed table
        with ui.element("div").classes("overflow-x-auto"):
            with ui.element("table").classes("w-full text-sm border-collapse"):
                # Header row with location names (sorted by ranking)
                sorted_entries = sorted(
                    hourly_data,
                    key=lambda e: ranking.get(e["location"].id, 999)
                )

                with ui.element("tr").classes("border-b-2 border-gray-300"):
                    with ui.element("th").classes("p-2 text-left font-medium"):
                        ui.label(target_date.strftime("%a %d.%m.")).classes("text-gray-600")
                    for entry in sorted_entries:
                        loc = entry["location"]
                        rank = ranking.get(loc.id, "")
                        with ui.element("th").classes("p-2 text-center font-medium min-w-20"):
                            label = f"#{rank} {loc.name}" if rank else loc.name
                            ui.label(label).classes("text-xs" if len(loc.name) > 12 else "")

                # Data rows (one per hour)
                for h in hours:
                    with ui.element("tr").classes("border-b"):
                        with ui.element("td").classes("p-2 font-medium text-gray-600"):
                            ui.label(f"{h:02d}:00")
                        for entry in sorted_entries:
                            loc = entry["location"]
                            cell_text = hour_data[h].get(loc.id, "-")
                            with ui.element("td").classes("p-2 text-center"):
                                ui.label(cell_text)

        # Cloud layer details - ALWAYS visible (not in expansion)
        with ui.card().classes("w-full mt-4"):
            with ui.row().classes("items-center gap-2 mb-2"):
                ui.icon("cloud", color="gray")
                ui.label("Wolkenschichten Details").classes("text-subtitle1 font-medium")
            ui.label("L = Low (0–3km) | M = Mid (3–8km) | H = High (>8km)").classes(
                "text-xs text-gray-500 mb-2"
            )

            # Transposed cloud layer table
            with ui.element("div").classes("overflow-x-auto"):
                with ui.element("table").classes("w-full text-xs"):
                    # Header row with locations
                    with ui.element("tr").classes("border-b"):
                        with ui.element("th").classes("p-2 text-left"):
                            ui.label("")
                        for entry in sorted_entries:
                            loc = entry["location"]
                            rank = ranking.get(loc.id, "")
                            with ui.element("th").classes("p-2 text-center min-w-16"):
                                label = f"#{rank} {loc.name}" if rank else loc.name
                                ui.label(label)

                    # Data rows (one per hour)
                    for h in hours:
                        with ui.element("tr").classes("border-b"):
                            with ui.element("td").classes("p-2 font-medium"):
                                ui.label(f"{h:02d}:00")

                            for entry in sorted_entries:
                                loc = entry["location"]
                                data_points = entry.get("data", [])

                                with ui.element("td").classes("p-2 text-center"):
                                    low, mid, high = 0, 0, 0
                                    for dp in data_points:
                                        if dp.ts.date() == target_date and dp.ts.hour == h:
                                            low = dp.cloud_low_pct or 0
                                            mid = dp.cloud_mid_pct or 0
                                            high = dp.cloud_high_pct or 0
                                            break

                                    if low < 10 and mid < 10 and high < 10:
                                        ui.label("☀️").classes("text-base")
                                    else:
                                        with ui.column().classes("gap-0.5"):
                                            if high > 0:
                                                _render_cloud_bar(high, "blue-200", "H")
                                            if mid > 0:
                                                _render_cloud_bar(mid, "blue-400", "M")
                                            if low > 0:
                                                _render_cloud_bar(low, "gray-500", "L")


def format_time_range(result: Dict[str, Any]) -> str:
    """Format the forecast time range for display."""
    start = result.get("forecast_start")
    end = result.get("forecast_end")
    if not start or not end:
        return "-"

    # Format as "28.12. 14:00 - 30.12. 14:00"
    start_str = start.strftime("%d.%m. %H:%M")
    end_str = end.strftime("%d.%m. %H:%M")
    return f"{start_str} - {end_str}"


def render_winner_card(results: List[Dict[str, Any]], target_date: Any = None) -> None:
    """Render the winner recommendation card at the top."""
    if not results or results[0].get("error"):
        return

    winner = results[0]
    loc = winner["location"]
    with ui.card().classes("w-full mb-4 bg-green-50"):
        with ui.row().classes("items-center gap-4"):
            ui.icon("emoji_events", color="amber", size="xl")
            with ui.column().classes("gap-1"):
                # Show date in title
                date_str = target_date.strftime('%A, %d.%m.%Y') if target_date else "Morgen"
                ui.label(f"Empfehlung für {date_str}:").classes("text-sm text-green-700")
                ui.label(f"🏆 {loc.name}").classes("text-h6")
                snow_depth = winner.get("snow_depth_cm")
                snow_new = winner.get("snow_new_cm", 0)
                sunny = winner.get("sunny_hours", 0)

                details = f"Score: {winner.get('score', 0)}"
                if snow_depth:
                    details += f" | Schneehöhe: {snow_depth:.0f}cm"
                if snow_new:
                    details += f" | Neuschnee: +{snow_new:.0f}cm"
                if sunny:
                    details += f" | Sonne: ~{sunny}h"
                ui.label(details).classes("text-gray-600")


def render_results_table(results: List[Dict[str, Any]]) -> None:
    """Render comparison table with locations as columns, metrics as rows."""
    if not results:
        ui.label("Keine Ergebnisse").classes("text-gray-500")
        return

    # Filter out error results for comparison
    valid_results = [r for r in results if not r.get("error")]
    if not valid_results:
        ui.label("Alle Abfragen fehlgeschlagen").classes("text-red-500")
        return

    # Helper to find best value index (for highlighting)
    def find_best_idx(values: List, higher_is_better: bool = True) -> int:
        """Find index of best value. Returns -1 if no valid values."""
        valid = [(i, v) for i, v in enumerate(values) if v is not None]
        if not valid:
            return -1
        if higher_is_better:
            return max(valid, key=lambda x: x[1])[0]
        return min(valid, key=lambda x: x[1])[0]

    # Extract metrics for each location
    locations = [r["location"].name for r in valid_results]
    scores = [r.get("score", 0) for r in valid_results]
    snow_depths = [r.get("snow_depth_cm") for r in valid_results]
    snow_news = [r.get("snow_new_cm", 0) for r in valid_results]
    winds = [r.get("wind_max") for r in valid_results]
    wind_directions = [r.get("wind_direction_avg") for r in valid_results]
    gusts = [r.get("gust_max") for r in valid_results]
    wind_chills = [r.get("wind_chill_min") for r in valid_results]
    sunny_hours = [r.get("sunny_hours") for r in valid_results]
    clouds = [r.get("cloud_avg") for r in valid_results]

    # Find best indices
    best_score = find_best_idx(scores, higher_is_better=True)
    best_snow_depth = find_best_idx(snow_depths, higher_is_better=True)
    best_snow_new = find_best_idx(snow_news, higher_is_better=True)
    best_wind = find_best_idx(winds, higher_is_better=False)  # Less wind = better
    best_gust = find_best_idx(gusts, higher_is_better=False)  # Less gusts = better
    best_wind_chill = find_best_idx(wind_chills, higher_is_better=True)  # Warmer = better
    best_sunny = find_best_idx(sunny_hours, higher_is_better=True)
    best_clouds = find_best_idx(clouds, higher_is_better=False)  # Less clouds = better

    with ui.card().classes("w-full mb-4"):
        ui.label("Vergleich").classes("text-subtitle1 font-medium mb-2")

        with ui.element("div").classes("overflow-x-auto"):
            with ui.element("table").classes("w-full text-sm border-collapse"):
                # Header row with location names
                with ui.element("tr").classes("border-b-2 border-gray-300"):
                    with ui.element("th").classes("p-2 text-left font-medium bg-gray-50 min-w-28"):
                        ui.label("")
                    for i, loc in enumerate(locations):
                        rank = i + 1
                        with ui.element("th").classes("p-2 text-center font-medium bg-gray-50 min-w-24"):
                            ui.label(f"#{rank} {loc}").classes("text-xs" if len(loc) > 12 else "")

                # Score row
                with ui.element("tr").classes("border-b"):
                    with ui.element("td").classes("p-2 font-medium bg-gray-50"):
                        ui.label("Score")
                    for i, score in enumerate(scores):
                        is_best = i == best_score
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            ui.label(f"{'🏆 ' if is_best else ''}{score}")

                # Snow depth row
                with ui.element("tr").classes("border-b"):
                    with ui.element("td").classes("p-2 font-medium bg-gray-50"):
                        ui.label("Schneehöhe")
                    for i, depth in enumerate(snow_depths):
                        is_best = i == best_snow_depth
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"{depth:.0f}cm" if depth else "n/a"
                            ui.label(text)

                # New snow row
                with ui.element("tr").classes("border-b"):
                    with ui.element("td").classes("p-2 font-medium bg-gray-50"):
                        ui.label("Neuschnee")
                    for i, snow in enumerate(snow_news):
                        is_best = i == best_snow_new and snow and snow > 0
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"+{snow:.0f}cm" if snow else "-"
                            ui.label(text)

                # Wind/Böen combined row: "10/41 SW"
                with ui.element("tr").classes("border-b"):
                    with ui.element("td").classes("p-2 font-medium bg-gray-50"):
                        ui.label("Wind/Böen")
                    for i, (wind, gust, wind_dir) in enumerate(zip(winds, gusts, wind_directions)):
                        is_best = i == best_wind
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            compass = _degrees_to_compass(wind_dir)
                            if wind is not None and gust is not None:
                                text = f"{wind:.0f}/{gust:.0f} {compass}"
                            elif wind is not None:
                                text = f"{wind:.0f}/- {compass}"
                            else:
                                text = "-"
                            ui.label(text)

                # Wind chill row
                with ui.element("tr").classes("border-b"):
                    with ui.element("td").classes("p-2 font-medium bg-gray-50"):
                        ui.label("Temperatur (gefühlt)")
                    for i, wc in enumerate(wind_chills):
                        is_best = i == best_wind_chill
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"{wc:.0f}°C" if wc is not None else "-"
                            ui.label(text)

                # Sunny hours row (0 shows "0h", not "~0h" per spec)
                with ui.element("tr").classes("border-b"):
                    with ui.element("td").classes("p-2 font-medium bg-gray-50"):
                        ui.label("Sonnenstunden")
                    for i, sunny in enumerate(sunny_hours):
                        is_best = i == best_sunny and sunny is not None and sunny > 0
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            # Spec: "~[N]h" for N>0, "0h" for N=0, "-" for None
                            if sunny is None:
                                text = "-"
                            elif sunny == 0:
                                text = "0h"
                            else:
                                text = f"~{sunny}h"
                            ui.label(text)

                # Clouds row
                with ui.element("tr").classes("border-b"):
                    with ui.element("td").classes("p-2 font-medium bg-gray-50"):
                        ui.label("Bewölkung")
                    for i, cloud in enumerate(clouds):
                        is_best = i == best_clouds
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"{cloud}%" if cloud is not None else "-"
                            ui.label(text)

                # Cloud situation row - uses WeatherMetricsService (Single Source of Truth)
                cloud_lows = [r.get("cloud_low_avg") for r in valid_results]
                sunny_hours_list = [r.get("sunny_hours") for r in valid_results]
                elevations = [r["location"].elevation_m for r in valid_results]
                # Calculate time window hours (default 8 if not available)
                time_window_hours = 8  # Default: 09:00-16:00
                with ui.element("tr").classes("border-b"):
                    with ui.element("td").classes("p-2 font-medium bg-gray-50"):
                        ui.label("Wolkenlage")
                    for i, (sunny, cloud_low, elev) in enumerate(zip(sunny_hours_list, cloud_lows, elevations)):
                        with ui.element("td").classes("p-2 text-center"):
                            cloud_status = WeatherMetricsService.calculate_cloud_status(
                                sunny, time_window_hours, elev, cloud_low
                            )
                            emoji = WeatherMetricsService.get_cloud_status_emoji(cloud_status)
                            text, _ = WeatherMetricsService.format_cloud_status(cloud_status)
                            # Apply appropriate styling based on status
                            if cloud_status == CloudStatus.ABOVE_CLOUDS:
                                ui.label(f"{emoji} {text}").classes("text-green-600 font-medium text-xs")
                            elif cloud_status == CloudStatus.CLEAR:
                                ui.label(f"{emoji} {text}").classes("text-green-600 text-xs")
                            elif cloud_status == CloudStatus.IN_CLOUDS:
                                ui.label(f"{emoji} {text}").classes("text-gray-500 text-xs")
                            else:
                                ui.label(f"{emoji} {text}").classes("text-xs")

    # Legend
    with ui.column().classes("mt-2 gap-0"):
        ui.label(
            "Grün = bester Wert | Temperatur = gefühlt (Wind Chill)"
        ).classes("text-xs text-gray-400")
        ui.label(
            "☀️ <20% Wolken | 🌤️ 20-50% | ⛅ 50-80% | ☁️ >80% | 🌧️ Regen | ❄️ Schnee"
        ).classes("text-xs text-gray-400")
