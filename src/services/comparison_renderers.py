"""
Comparison Renderers — extracted from web.pages.compare (Epic #129 Phase A.1).

Pure-function renderers that turn ComparisonResult into HTML / Plain-Text for
email delivery. No NiceGUI dependency.

SPEC: docs/specs/epic_129a_1_compare_helpers.md
SPEC (HTML/Text): docs/specs/compare_email.md v4.2
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from app.user import ComparisonResult
from services.weather_metrics import HourlyCell, WeatherMetricsService


def _degrees_to_compass(degrees: int | None) -> str:
    """Convert degrees (0-360) to compass direction."""
    if degrees is None:
        return "-"
    directions = ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]
    idx = int((degrees + 22.5) / 45) % 8
    return directions[idx]


def render_comparison_html(result: ComparisonResult, top_n_details: int = 3, enabled_metrics: set | None = None) -> str:
    """
    Render ComparisonResult as HTML for email.

    This is the single HTML renderer - used by both direct email and subscriptions.
    If enabled_metrics is provided, only rows for those metric_ids are rendered.
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
    above_low_clouds_flags = [loc.above_low_clouds for loc in valid_locs]
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
            <p>📅 Forecast for: <strong>{target_date.strftime('%A, %d.%m.%Y')}</strong></p>
            <p>🕐 Time Window: {time_window[0]:02d}:00 - {time_window[1]:02d}:00</p>
            <p>📝 Created: {now.strftime('%d.%m.%Y %H:%M')}</p>
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
            <p>Score: <strong>{winner.score}</strong> | {' | '.join(details) if details else '-'}</p>
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

    # Helper: check if metric should be rendered based on display_config
    def show(metric_id: str) -> bool:
        if enabled_metrics is None:
            return True
        return metric_id in enabled_metrics

    # Score row (always shown)
    html += "                <tr>\n                    <td class=\"label\">Score</td>\n"
    for i, v in enumerate(scores):
        html += f"                    {cell(v, lambda x: str(x) if x else '-', i == best_score)}\n"
    html += "                </tr>\n"

    # Snow depth row
    if show("snow_depth"):
        html += "                <tr>\n                    <td class=\"label\">Schneehöhe</td>\n"
        for i, v in enumerate(snow_depths):
            html += f"                    {cell(v, lambda x: f'{x:.0f}cm' if x else '-', i == best_snow_depth)}\n"
        html += "                </tr>\n"

    # New snow row
    if show("fresh_snow"):
        html += "                <tr>\n                    <td class=\"label\">Neuschnee</td>\n"
        for i, v in enumerate(snow_news):
            is_best = i == best_snow_new and v and v > 0
            html += f"                    {cell(v, lambda x: f'+{x:.0f}cm' if x else '-', is_best)}\n"
        html += "                </tr>\n"

    # Wind/Böen combined row: "10/41 SW"
    if not show("wind") and not show("gust"):
        pass  # skip entire row if both wind and gust disabled
    elif True:  # wind row
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
    if show("wind_chill"):
        html += "                <tr>\n                    <td class=\"label\">Temperatur (gefühlt)</td>\n"
        for i, v in enumerate(wind_chills):
            html += f"                    {cell(v, lambda x: f'{x:.0f}°C' if x is not None else '-', i == best_wc)}\n"
        html += "                </tr>\n"

    # Sunny hours row (0 shows "0h", not "~0h" per spec)
    if show("sunshine"):
        html += "                <tr>\n                    <td class=\"label\">Sonnenstunden</td>\n"
        for i, v in enumerate(sunny_hours_list):
            is_best = i == best_sunny and v is not None and v > 0
            # Spec: "~[N]h" for N>0, "0h" for N=0, "-" for None
            html += f"                    {cell(v, lambda x: '0h' if x == 0 else f'~{x}h' if x is not None else '-', is_best)}\n"
        html += "                </tr>\n"

    # Clouds row - SPEC: docs/specs/cloud_cover_simplification.md
    if show("cloud_total"):
        html += "                <tr>\n                    <td class=\"label\">Bewölkung</td>\n"
        for i, (v, above_low) in enumerate(zip(clouds, above_low_clouds_flags)):
            marker = "*" if above_low else ""
            html += f"                    {cell(v, lambda x, m=marker: f'{x}%{m}' if x is not None else '-', i == best_clouds)}\n"
        html += "                </tr>\n"

    # Wolkenlage row - SPEC: docs/specs/compare_email.md Zeile 366-372
    if show("cloud_low"):
        html += "                <tr>\n                    <td class=\"label\">Wolkenlage</td>\n"
    for loc in valid_locs:
        elev = loc.location.elevation_m or 0
        cl = loc.cloud_low_avg
        if elev >= 2500 and cl is not None and cl > 30:
            wl = '☀️ über Wolken'
            cls = ' class="best"'
        elif cl is not None and cl > 50:
            wl = '☁️ in Wolken'
            cls = ''
        elif cl is not None and cl < 20:
            wl = '✨ klar'
            cls = ' class="best"'
        else:
            wl = '🌤️ leicht'
            cls = ''
        html += f'                    <td{cls}>{wl}</td>\n'
    html += "                </tr>\n"

    html += """            </table>
            <p style="font-size: 12px; color: #888;">🟢 Grün = bester Wert | Temperatur = gefühlt (Wind Chill) | * tiefe Wolken ignoriert</p>
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
            <h3>🕐 Stunden-Übersicht</h3>
            <p style="color: #666; margin-bottom: 12px;">📅 {target_date.strftime('%A, %d.%m.%Y')}</p>
            <table>
                <tr>
                    <th class="label">Time</th>
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
                <strong>Legend:</strong>
                ☀️ &lt;20% clouds |
                🌤️ 20-50% |
                ⛅ 50-80% |
                ☁️ &gt;80% |
                🌧️ rain |
                ❄️ snow
            </p>
        </div>
"""

    # Footer
    html += """
        <div class="footer">
            <p>Generated by <strong>Gregor Zwanzig</strong> ⛷️</p>
        </div>
    </div>
</body>
</html>
"""

    return html


def render_comparison_text(result: ComparisonResult, top_n_details: int = 3, enabled_metrics: set | None = None) -> str:
    """
    Render ComparisonResult as Plain-Text for email fallback.
    If enabled_metrics is provided, only metrics in the set are rendered.

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
        return "No comparison data available."

    lines = []

    # Header
    lines.append("⛷️ SKIGEBIETE-VERGLEICH")
    lines.append("=" * 24)
    lines.append(f"📅 Forecast: {target_date.strftime('%A, %d.%m.%Y')}")
    lines.append(f"🕐 Time Window: {time_window[0]:02d}:00 - {time_window[1]:02d}:00")
    lines.append(f"📝 Created: {created_at.strftime('%d.%m.%Y %H:%M')}")
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
        lines.append(f"   Snow: {loc_result.snow_depth_cm:.0f}cm" if loc_result.snow_depth_cm else "   Snow: -")
        if loc_result.snow_new_cm and loc_result.snow_new_cm > 0:
            lines.append(f"   New Snow: +{loc_result.snow_new_cm:.0f}cm")
        else:
            lines.append("   New Snow: -")

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
        lines.append(f"   Sun: ~{sunny_h}h" if sunny_h is not None else "   Sun: -")

        # Cloud
        cloud = loc_result.cloud_avg
        lines.append(f"   Clouds: {cloud}%" if cloud is not None else "   Clouds: -")

        # Cloud layer status (elevation + mid clouds)
        cloud_status = WeatherMetricsService.calculate_cloud_status(
            elevation_m=loc.elevation_m,
            cloud_low_pct=loc_result.cloud_low_avg,
            cloud_mid_pct=loc_result.cloud_mid_avg,
        )
        emoji = WeatherMetricsService.get_cloud_status_emoji(cloud_status)
        text, _ = WeatherMetricsService.format_cloud_status(cloud_status)
        layer_str = f"{emoji} {text}".strip() if text else "-"
        lines.append(f"   Layer: {layer_str}")
        lines.append("")

    # Hourly details
    top_locs = valid_locs[:top_n_details]
    if top_locs and any(loc.hourly_data for loc in top_locs):
        lines.append("HOURLY DETAILS")
        lines.append("-" * 15)

        hours = list(range(time_window[0], time_window[1] + 1))

        # Header row
        header = "Time  |"
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
    lines.append("Generated by Gregor Zwanzig ⛷️")

    return "\n".join(lines)
