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
from app.loader import load_all_locations
from app.user import SavedLocation
from outputs.email import EmailOutput
from outputs.base import OutputConfigError, OutputError
from providers.geosphere import GeoSphereProvider
from services.forecast import ForecastService
from validation.ground_truth import BergfexScraper


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


def format_compare_email(
    results: List[Dict[str, Any]],
    time_window: tuple[int, int],
    forecast_hours: int,
    hourly_data: List[Dict[str, Any]] | None = None,
    top_n_details: int = 3,
    plain_text: bool = True,
) -> str:
    """
    Format comparison results as email with transposed table layout.

    Layout: Locations as columns, metrics as rows (same as WebUI).
    """
    from datetime import date, timedelta

    lines = []
    now = datetime.now()

    # Filter valid results
    valid_results = [r for r in results if not r.get("error")]

    # Header
    if plain_text:
        lines.append("=" * 60)
        lines.append("  SKIGEBIETE-VERGLEICH")
    else:
        lines.append("🎿 " + "=" * 54 + " 🏔️")
        lines.append("  SKIGEBIETE-VERGLEICH")
    lines.append(f"  Datum: {now.strftime('%d.%m.%Y %H:%M')} | Forecast: {forecast_hours}h")
    lines.append(f"  Aktivzeit: {time_window[0]:02d}:00-{time_window[1]:02d}:00")
    lines.append("=" * 60)
    lines.append("")

    # Winner recommendation FIRST
    if valid_results:
        winner = valid_results[0]
        loc = winner["location"]
        if plain_text:
            lines.append(f"EMPFEHLUNG: {loc.name} (Score {winner.get('score', 0)})")
        else:
            lines.append(f"🏆 EMPFEHLUNG: {loc.name} (Score {winner.get('score', 0)})")

        details = []
        snow_depth = winner.get("snow_depth_cm")
        if snow_depth:
            details.append(f"Schneehoehe: {snow_depth:.0f}cm")
        snow_new = winner.get("snow_new_cm", 0)
        if snow_new:
            details.append(f"Neuschnee: +{snow_new:.0f}cm")
        sunny = winner.get("sunny_hours")
        if sunny:
            details.append(f"Sonne: ~{sunny}h")

        if details:
            lines.append(f"  {' | '.join(details)}")
        lines.append("")

    # Helper to find best index
    def find_best(values: List, higher_is_better: bool = True) -> int:
        valid = [(i, v) for i, v in enumerate(values) if v is not None]
        if not valid:
            return -1
        if higher_is_better:
            return max(valid, key=lambda x: x[1])[0]
        return min(valid, key=lambda x: x[1])[0]

    # Extract data
    locations = [r["location"].name for r in valid_results]
    scores = [r.get("score", 0) for r in valid_results]
    snow_depths = [r.get("snow_depth_cm") for r in valid_results]
    snow_news = [r.get("snow_new_cm", 0) for r in valid_results]
    winds = [r.get("wind_max") for r in valid_results]
    wind_chills = [r.get("wind_chill_min") for r in valid_results]
    sunny_hours = [r.get("sunny_hours") for r in valid_results]
    clouds = [r.get("cloud_avg") for r in valid_results]

    # Find bests
    best_score = find_best(scores, True)
    best_snow_depth = find_best(snow_depths, True)
    best_snow_new = find_best(snow_news, True)
    best_wind = find_best(winds, False)
    best_wc = find_best(wind_chills, True)
    best_sunny = find_best(sunny_hours, True)
    best_clouds = find_best(clouds, False)

    # Calculate column widths
    loc_width = max(len(loc) for loc in locations) if locations else 10
    loc_width = max(loc_width, 8)
    col_width = max(loc_width + 2, 12)

    # Build transposed table
    lines.append("VERGLEICH")
    lines.append("-" * (18 + col_width * len(locations)))

    # Header row
    header = f"{'':18}"
    for i, loc in enumerate(locations):
        rank = i + 1
        header += f"#{rank} {loc:<{col_width-3}}"
    lines.append(header)
    lines.append("-" * (18 + col_width * len(locations)))

    # Helper to format row
    def fmt_row(label: str, values: List, best_idx: int, formatter) -> str:
        row = f"{label:18}"
        for i, val in enumerate(values):
            cell = formatter(val)
            if i == best_idx and not plain_text:
                cell = "* " + cell
            elif i == best_idx:
                cell = "[" + cell + "]"
            row += f"{cell:<{col_width}}"
        return row

    # Score row
    lines.append(fmt_row("Score", scores, best_score,
                         lambda v: str(v) if v else "-"))

    # Snow depth row
    lines.append(fmt_row("Schneehoehe", snow_depths, best_snow_depth,
                         lambda v: f"{v:.0f}cm" if v else "n/a"))

    # New snow row
    lines.append(fmt_row("Neuschnee", snow_news, best_snow_new if any(s for s in snow_news) else -1,
                         lambda v: f"+{v:.0f}cm" if v else "-"))

    # Wind row
    lines.append(fmt_row("Wind (max)", winds, best_wind,
                         lambda v: f"{v:.0f}km/h" if v else "-"))

    # Wind chill row
    lines.append(fmt_row("Temp (gefuehlt)", wind_chills, best_wc,
                         lambda v: f"{v:.0f}C" if v is not None else "-"))

    # Sunny hours row
    lines.append(fmt_row("Sonne", sunny_hours, best_sunny if any(s for s in sunny_hours) else -1,
                         lambda v: f"~{v}h" if v else "-"))

    # Clouds row
    lines.append(fmt_row("Bewoelkung", clouds, best_clouds,
                         lambda v: f"{v}%" if v is not None else "-"))

    lines.append("-" * (18 + col_width * len(locations)))
    lines.append("")

    # Hourly details - TRANSPOSED (hours as rows, locations as columns)
    if hourly_data and valid_results:
        # Only show top locations
        top_locations = [r["location"] for r in valid_results[:top_n_details]]
        top_loc_ids = {loc.id for loc in top_locations}
        top_hourly = [e for e in hourly_data if e["location"].id in top_loc_ids]

        if top_hourly:
            days_ahead = top_hourly[0].get("days_ahead", 1)
            target_date = date.today() + timedelta(days=days_ahead)
            hours = list(range(time_window[0], time_window[1] + 1))

            lines.append("-" * (18 + col_width * len(top_locations)))
            if plain_text:
                lines.append("STUENDLICHE UEBERSICHT")
            else:
                lines.append("🕐 STUENDLICHE UEBERSICHT")
            lines.append(target_date.strftime("%a %d.%m."))
            lines.append("")

            # Sort by ranking
            sorted_entries = sorted(
                top_hourly,
                key=lambda e: next(
                    (i for i, r in enumerate(valid_results) if r["location"].id == e["location"].id),
                    999
                )
            )

            # Header row
            header = f"{'':10}"
            for i, entry in enumerate(sorted_entries):
                loc = entry["location"]
                rank = i + 1
                header += f"#{rank} {loc.name:<{col_width-3}}"
            lines.append(header)
            lines.append("-" * (10 + col_width * len(sorted_entries)))

            # Build data structure: hour -> location_id -> cell
            hour_data: Dict[int, Dict[str, str]] = {h: {} for h in hours}

            for entry in sorted_entries:
                loc = entry["location"]
                data_points = entry.get("data", [])

                for dp in data_points:
                    if dp.ts.date() != target_date:
                        continue
                    h = dp.ts.hour
                    if h not in hours:
                        continue

                    temp = dp.wind_chill_c if dp.wind_chill_c is not None else dp.t2m_c
                    temp_str = f"{temp:.0f}C" if temp is not None else "?"

                    if plain_text:
                        cell = temp_str
                    else:
                        symbol = get_weather_symbol(dp.cloud_total_pct, dp.precip_1h_mm, dp.t2m_c)
                        cell = f"{symbol} {temp_str}"

                    hour_data[h][loc.id] = cell

            # Data rows
            for h in hours:
                row = f"{h:02d}:00     "
                for entry in sorted_entries:
                    loc = entry["location"]
                    cell = hour_data[h].get(loc.id, "-")
                    row += f"{cell:<{col_width}}"
                lines.append(row)

            lines.append("")

    # Footer
    if plain_text:
        lines.append("[x] = bester Wert | Temp = gefuehlt (Wind Chill)")
    else:
        lines.append("* = bester Wert | Temp = gefuehlt (Wind Chill)")
    lines.append("")
    lines.append("=" * 50)
    if plain_text:
        lines.append("Generiert von Gregor Zwanzig")
    else:
        lines.append("🏔️ Generiert von Gregor Zwanzig")
    lines.append("=" * 50)

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

            # Sunshine estimate: hours with cloud cover < 30%
            if clouds:
                sunny_hours = sum(1 for c in clouds if c < 30)
                result["sunny_hours"] = sunny_hours

        result["score"] = calculate_score(result)

    except Exception as e:
        result["error"] = str(e)
        result["score"] = 0

    return result


def render_header() -> None:
    """Render navigation header."""
    with ui.header().classes("items-center justify-between"):
        ui.label("Gregor Zwanzig").classes("text-h6")
        with ui.row():
            ui.link("Dashboard", "/").classes("text-white mx-2")
            ui.link("Locations", "/locations").classes("text-white mx-2")
            ui.link("Trips", "/trips").classes("text-white mx-2")
            ui.link("Vergleich", "/compare").classes("text-white mx-2")
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
            render_winner_card(state["results"])

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

            state["loading"] = True
            state["forecast_hours"] = hours
            state["time_start"] = time_start
            state["time_end"] = time_end
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

                        # Wind chill
                        wc = [dp.wind_chill_c for dp in filtered_data if dp.wind_chill_c is not None]
                        if wc:
                            result["wind_chill_min"] = min(wc)
                            result["wind_chill_max"] = max(wc)

                        # Clouds
                        clouds = [dp.cloud_total_pct for dp in filtered_data if dp.cloud_total_pct is not None]
                        if clouds:
                            result["cloud_avg"] = int(sum(clouds) / len(clouds))
                            result["sunny_hours"] = sum(1 for c in clouds if c < 30)

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
            """Send comparison results via email."""
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

                # Read plain_text setting from .env
                from web.pages.settings import load_env_settings

                env_settings = load_env_settings()
                plain_text = env_settings.get("GZ_EMAIL_PLAIN_TEXT", "false").lower() == "true"

                # Format email
                email_body = format_compare_email(
                    results=state["results"],
                    time_window=(state["time_start"], state["time_end"]),
                    forecast_hours=state["forecast_hours"],
                    hourly_data=state["hourly_data"],
                    plain_text=plain_text,
                )

                # Send via SMTP
                email_output = EmailOutput(settings)
                subject = f"Skigebiete-Vergleich ({datetime.now().strftime('%d.%m.%Y')})"

                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: email_output.send(subject, email_body)
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


def get_weather_symbol(cloud_total: Optional[int], precip: Optional[float], temp: Optional[float]) -> str:
    """Get weather symbol based on conditions."""
    if precip and precip > 0.5:
        if temp is not None and temp < 0:
            return "❄️"  # Snow
        return "🌧️"  # Rain
    if cloud_total is None:
        return "?"
    if cloud_total < 20:
        return "☀️"  # Sunny
    if cloud_total < 50:
        return "⛅"  # Partly cloudy
    if cloud_total < 80:
        return "🌥️"  # Mostly cloudy
    return "☁️"  # Overcast


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
        hour_data: Dict[int, Dict[str, str]] = {h: {} for h in hours}

        for entry in hourly_data:
            loc = entry["location"]
            data_points = entry.get("data", [])

            for h in hours:
                cell = "-"
                for dp in data_points:
                    if dp.ts.date() == target_date and dp.ts.hour == h:
                        temp = dp.t2m_c
                        feels_like = dp.wind_chill_c
                        cloud = dp.cloud_total_pct
                        precip = dp.precip_1h_mm
                        symbol = get_weather_symbol(cloud, precip, temp)
                        display_temp = feels_like if feels_like is not None else temp
                        temp_str = f"{display_temp:.0f}°" if display_temp is not None else "?"
                        cell = f"{symbol} {temp_str}"
                        break
                hour_data[h][loc.id] = cell

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

        # Cloud layer details (expandable) - ALSO transposed
        with ui.expansion("Wolkenschichten Details", icon="cloud").classes("w-full mt-2"):
            ui.label("L = Low (0–3km) | M = Mid (3–8km) | H = High (>8km)").classes(
                "text-xs text-gray-500 mb-2"
            )

            # Transposed cloud layer table
            with ui.element("div").classes("overflow-x-auto"):
                with ui.element("table").classes("w-full text-xs"):
                    # Header row with locations
                    with ui.element("tr").classes("border-b"):
                        ui.element("th").classes("p-2 text-left").text = ""
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


def render_winner_card(results: List[Dict[str, Any]]) -> None:
    """Render the winner recommendation card at the top."""
    if not results or results[0].get("error"):
        return

    winner = results[0]
    loc = winner["location"]
    with ui.card().classes("w-full mb-4 bg-green-50"):
        with ui.row().classes("items-center gap-4"):
            ui.icon("emoji_events", color="amber", size="xl")
            with ui.column().classes("gap-0"):
                ui.label(f"Empfehlung: {loc.name}").classes("text-h6")
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
    wind_chills = [r.get("wind_chill_min") for r in valid_results]
    sunny_hours = [r.get("sunny_hours") for r in valid_results]
    clouds = [r.get("cloud_avg") for r in valid_results]

    # Find best indices
    best_score = find_best_idx(scores, higher_is_better=True)
    best_snow_depth = find_best_idx(snow_depths, higher_is_better=True)
    best_snow_new = find_best_idx(snow_news, higher_is_better=True)
    best_wind = find_best_idx(winds, higher_is_better=False)  # Less wind = better
    best_wind_chill = find_best_idx(wind_chills, higher_is_better=True)  # Warmer = better
    best_sunny = find_best_idx(sunny_hours, higher_is_better=True)
    best_clouds = find_best_idx(clouds, higher_is_better=False)  # Less clouds = better

    with ui.card().classes("w-full mb-4"):
        ui.label("Vergleich").classes("text-subtitle1 font-medium mb-2")

        with ui.element("div").classes("overflow-x-auto"):
            with ui.element("table").classes("w-full text-sm border-collapse"):
                # Header row with location names
                with ui.element("tr").classes("border-b-2 border-gray-300"):
                    ui.element("th").classes("p-2 text-left font-medium bg-gray-50").text = ""
                    for i, loc in enumerate(locations):
                        rank = i + 1
                        with ui.element("th").classes("p-2 text-center font-medium bg-gray-50 min-w-24"):
                            ui.label(f"#{rank} {loc}").classes("text-xs" if len(loc) > 12 else "")

                # Score row
                with ui.element("tr").classes("border-b"):
                    ui.element("td").classes("p-2 font-medium").text = "Score"
                    for i, score in enumerate(scores):
                        is_best = i == best_score
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            ui.label(f"{'🏆 ' if is_best else ''}{score}")

                # Snow depth row
                with ui.element("tr").classes("border-b"):
                    ui.element("td").classes("p-2 font-medium").text = "Schneehöhe"
                    for i, depth in enumerate(snow_depths):
                        is_best = i == best_snow_depth
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"{depth:.0f}cm" if depth else "n/a"
                            ui.label(text)

                # New snow row
                with ui.element("tr").classes("border-b"):
                    ui.element("td").classes("p-2 font-medium").text = "Neuschnee"
                    for i, snow in enumerate(snow_news):
                        is_best = i == best_snow_new and snow and snow > 0
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"+{snow:.0f}cm" if snow else "-"
                            ui.label(text)

                # Wind row
                with ui.element("tr").classes("border-b"):
                    ui.element("td").classes("p-2 font-medium").text = "Wind (max)"
                    for i, wind in enumerate(winds):
                        is_best = i == best_wind
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"{wind:.0f}km/h" if wind else "-"
                            ui.label(text)

                # Wind chill row
                with ui.element("tr").classes("border-b"):
                    ui.element("td").classes("p-2 font-medium").text = "Temperatur (gefühlt)"
                    for i, wc in enumerate(wind_chills):
                        is_best = i == best_wind_chill
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"{wc:.0f}°C" if wc is not None else "-"
                            ui.label(text)

                # Sunny hours row
                with ui.element("tr").classes("border-b"):
                    ui.element("td").classes("p-2 font-medium").text = "Sonne"
                    for i, sunny in enumerate(sunny_hours):
                        is_best = i == best_sunny and sunny
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"~{sunny}h" if sunny is not None else "-"
                            ui.label(text)

                # Clouds row
                with ui.element("tr").classes("border-b"):
                    ui.element("td").classes("p-2 font-medium").text = "Bewölkung"
                    for i, cloud in enumerate(clouds):
                        is_best = i == best_clouds
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"{cloud}%" if cloud is not None else "-"
                            ui.label(text)

    # Legend
    ui.label(
        "Grün = bester Wert | Temperatur = gefühlt (Wind Chill)"
    ).classes("text-xs text-gray-400 mt-2")
