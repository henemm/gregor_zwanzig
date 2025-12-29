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


def format_compare_email(
    results: List[Dict[str, Any]],
    time_window: tuple[int, int],
    forecast_hours: int,
    hourly_data: List[Dict[str, Any]] | None = None,
    top_n_details: int = 3,
) -> str:
    """
    Format comparison results as plain-text email.

    Args:
        results: Sorted list of comparison results
        time_window: Tuple of (start_hour, end_hour)
        forecast_hours: Number of hours in forecast
        hourly_data: Optional hourly data for detailed view
        top_n_details: Number of top locations to show hourly details for

    Returns:
        Plain-text email body
    """
    from datetime import date, timedelta

    lines = []
    now = datetime.now()

    # Header
    lines.append("=" * 60)
    lines.append("  SKIGEBIETE-VERGLEICH")
    lines.append(f"  Datum: {now.strftime('%d.%m.%Y %H:%M')} | Forecast: {forecast_hours}h")
    lines.append(f"  Aktivzeit: {time_window[0]:02d}:00-{time_window[1]:02d}:00")
    lines.append("=" * 60)
    lines.append("")

    # Ranking table
    lines.append(f"RANKING ({len(results)} Locations)")
    lines.append("-" * 60)
    lines.append(f" {'#':>2}  {'Location':<24} {'Score':>5}   {'Schnee':>8} {'Wind':>8} {'Temp':>6}")
    lines.append("-" * 60)

    for i, r in enumerate(results):
        loc = r["location"]
        if r.get("error"):
            lines.append(f" {i+1:>2}  {loc.name:<24} {'Fehler':>5}")
            continue

        score = r.get("score", 0)
        snow_cm = r.get("snow_new_cm", 0)
        snow_str = f"+{snow_cm:.0f}cm" if snow_cm else "-"
        wind_max = r.get("wind_max")
        wind_str = f"{wind_max:.0f}km/h" if wind_max else "-"
        temp_min = r.get("temp_min")
        temp_str = f"{temp_min:.0f}C" if temp_min is not None else "-"

        lines.append(f" {i+1:>2}  {loc.name:<24} {score:>5}   {snow_str:>8} {wind_str:>8} {temp_str:>6}")

    lines.append("-" * 60)
    lines.append("")

    # Winner recommendation
    if results and not results[0].get("error"):
        winner = results[0]
        loc = winner["location"]
        lines.append(f"EMPFEHLUNG: {loc.name} (Score {winner.get('score', 0)})")

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

    # Hourly details for top locations
    if hourly_data:
        for entry in hourly_data[:top_n_details]:
            loc = entry["location"]
            data_points = entry.get("data", [])
            days_ahead = entry.get("days_ahead", 1)
            target_date = date.today() + timedelta(days=days_ahead)

            lines.append("-" * 60)
            lines.append(f"STUNDEN-DETAILS: {loc.name}")
            lines.append("-" * 60)
            lines.append(target_date.strftime("%a %d.%m."))

            for dp in data_points:
                if dp.ts.date() != target_date:
                    continue
                if not (time_window[0] <= dp.ts.hour <= time_window[1]):
                    continue

                temp = dp.t2m_c
                temp_str = f"{temp:.0f}C" if temp is not None else "?"
                wind = dp.wind10m_kmh
                wind_str = f"{wind:.0f}km/h" if wind is not None else "?"
                cloud = dp.cloud_total_pct
                cloud_str = f"{cloud}%" if cloud is not None else "?"
                precip = dp.precip_1h_mm
                precip_str = f"+{precip:.1f}mm" if precip and precip > 0 else "-"

                lines.append(f"  {dp.ts.strftime('%H:%M')}   {temp_str:>5}   {wind_str:>8}   {cloud_str:>4}   {precip_str}")

            lines.append("")

    # Footer
    lines.append("=" * 60)
    lines.append("Generiert von Gregor Zwanzig")
    lines.append("=" * 60)

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

            # Render hourly table first (new!)
            if state["hourly_data"]:
                render_hourly_table(
                    state["hourly_data"],
                    state["time_start"],
                    state["time_end"],
                )

            # Then render aggregate table
            render_results_table(state["results"])

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

                # Format email
                email_body = format_compare_email(
                    results=state["results"],
                    time_window=(state["time_start"], state["time_end"]),
                    forecast_hours=state["forecast_hours"],
                    hourly_data=state["hourly_data"],
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
) -> None:
    """Render hourly weather table for the selected time window."""
    if not hourly_data:
        return

    from datetime import date, timedelta

    with ui.card().classes("w-full mb-4"):
        ui.label("Stündliche Übersicht").classes("text-subtitle1 font-medium mb-2")

        # Build hours list
        hours = list(range(time_start, time_end + 1))

        # Build columns: Location + each hour
        columns = [{"name": "location", "label": "Location", "field": "location"}]
        for h in hours:
            columns.append({
                "name": f"h{h}",
                "label": f"{h:02d}:00",
                "field": f"h{h}",
                "align": "center",
            })

        rows = []
        for entry in hourly_data:
            loc = entry["location"]
            data_points = entry.get("data", [])
            days_ahead = entry.get("days_ahead", 1)

            # Calculate target date
            target_date = date.today() + timedelta(days=days_ahead)

            row = {"location": loc.name}

            for h in hours:
                # Find data point for this hour on target date
                cell = "-"
                for dp in data_points:
                    if dp.ts.date() == target_date and dp.ts.hour == h:
                        temp = dp.t2m_c
                        cloud = dp.cloud_total_pct
                        precip = dp.precip_1h_mm
                        symbol = get_weather_symbol(cloud, precip, temp)
                        temp_str = f"{temp:.0f}°" if temp is not None else "?"
                        cell = f"{symbol} {temp_str}"
                        break
                row[f"h{h}"] = cell

            rows.append(row)

        if rows:
            ui.table(columns=columns, rows=rows, row_key="location").classes("w-full")

        # Cloud layer details (expandable)
        with ui.expansion("Wolkenschichten Details", icon="cloud").classes("w-full mt-2"):
            ui.label("L = Low (0–3km) | M = Mid (3–8km) | H = High (>8km)").classes(
                "text-xs text-gray-500 mb-2"
            )
            detail_cols = [{"name": "location", "label": "Location", "field": "location"}]
            for h in hours:
                detail_cols.append({
                    "name": f"h{h}",
                    "label": f"{h:02d}:00",
                    "field": f"h{h}",
                    "align": "center",
                })

            detail_rows = []
            for entry in hourly_data:
                loc = entry["location"]
                data_points = entry.get("data", [])
                days_ahead = entry.get("days_ahead", 1)
                target_date = date.today() + timedelta(days=days_ahead)

                row = {"location": loc.name}
                for h in hours:
                    cell = "-"
                    for dp in data_points:
                        if dp.ts.date() == target_date and dp.ts.hour == h:
                            low = dp.cloud_low_pct
                            mid = dp.cloud_mid_pct
                            high = dp.cloud_high_pct
                            if low is not None:
                                cell = f"L{low}/M{mid}/H{high}"
                            break
                    row[f"h{h}"] = cell
                detail_rows.append(row)

            if detail_rows:
                ui.table(columns=detail_cols, rows=detail_rows, row_key="location").classes("w-full text-xs")


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


def render_results_table(results: List[Dict[str, Any]]) -> None:
    """Render the comparison results table with all available metrics."""
    if not results:
        ui.label("Keine Ergebnisse").classes("text-gray-500")
        return

    # Show time range info
    first_result = results[0] if results else {}
    time_range = format_time_range(first_result)
    hours = first_result.get("forecast_hours", 48)
    data_points = first_result.get("data_points", 0)

    with ui.row().classes("items-center gap-4 mb-4"):
        ui.icon("schedule", color="blue")
        ui.label(f"Forecast: {time_range} ({hours}h, {data_points} Datenpunkte)").classes("text-gray-600")

    ui.label("Ergebnisse (sortiert nach Score)").classes("text-h6 mb-2")

    # Main comparison table - Snow & Conditions
    with ui.card().classes("w-full mb-4"):
        ui.label("Schnee & Bedingungen").classes("text-subtitle1 font-medium mb-2")

        columns = [
            {"name": "rank", "label": "#", "field": "rank", "align": "center"},
            {"name": "location", "label": "Location", "field": "location"},
            {"name": "score", "label": "Score", "field": "score", "align": "center"},
            {"name": "snow_depth", "label": "Schneehöhe", "field": "snow_depth", "align": "center"},
            {"name": "snow_new", "label": "Neuschnee", "field": "snow_new", "align": "center"},
            {"name": "sunny", "label": "Sonne", "field": "sunny", "align": "center"},
            {"name": "cloud_layers", "label": "Wolken (L/M/H)", "field": "cloud_layers", "align": "center"},
        ]

        rows = []
        for i, r in enumerate(results):
            loc = r["location"]
            if r.get("error"):
                rows.append({
                    "rank": i + 1,
                    "location": loc.name,
                    "score": "Fehler",
                    "snow_depth": "-",
                    "snow_new": "-",
                    "sunny": "-",
                    "clouds": str(r["error"])[:30],
                })
            else:
                # Snow depth
                snow_depth = r.get("snow_depth_cm")
                snow_depth_str = f"{snow_depth:.0f} cm" if snow_depth else "n/a"

                # New snow
                snow_cm = r.get("snow_new_cm", 0)
                snow_str = f"+{snow_cm:.0f} cm" if snow_cm else "-"

                # Sunny hours
                sunny = r.get("sunny_hours")
                sunny_str = f"~{sunny}h" if sunny is not None else "-"

                # Cloud layers (L/M/H)
                cloud_low = r.get("cloud_low_avg")
                cloud_mid = r.get("cloud_mid_avg")
                cloud_high = r.get("cloud_high_avg")
                if cloud_low is not None:
                    cloud_str = f"{cloud_low}/{cloud_mid}/{cloud_high}%"
                else:
                    # Fallback to total cloud
                    cloud_avg = r.get("cloud_avg")
                    cloud_str = f"{cloud_avg}%" if cloud_avg is not None else "-"

                rows.append({
                    "rank": i + 1,
                    "location": loc.name,
                    "score": r.get("score", 0),
                    "snow_depth": snow_depth_str,
                    "snow_new": snow_str,
                    "sunny": sunny_str,
                    "cloud_layers": cloud_str,
                })

        ui.table(columns=columns, rows=rows, row_key="location").classes("w-full")

    # Temperature & Wind table
    with ui.card().classes("w-full mb-4"):
        ui.label("Temperatur & Wind").classes("text-subtitle1 font-medium mb-2")

        temp_columns = [
            {"name": "location", "label": "Location", "field": "location"},
            {"name": "temp", "label": "Temp (min/max)", "field": "temp", "align": "center"},
            {"name": "wind_chill", "label": "Gefühlt (min/max)", "field": "wind_chill", "align": "center"},
            {"name": "wind", "label": "Wind (min/max)", "field": "wind", "align": "center"},
            {"name": "gust", "label": "Böen (max)", "field": "gust", "align": "center"},
        ]

        temp_rows = []
        for r in results:
            loc = r["location"]
            if r.get("error"):
                continue

            # Temperature
            temp_min = r.get("temp_min")
            temp_max = r.get("temp_max")
            temp_str = f"{temp_min:.0f}°C / {temp_max:.0f}°C" if temp_min is not None else "-"

            # Wind chill
            wc_min = r.get("wind_chill_min")
            wc_max = r.get("wind_chill_max")
            wc_str = f"{wc_min:.0f}°C / {wc_max:.0f}°C" if wc_min is not None else "-"

            # Wind
            wind_min = r.get("wind_min")
            wind_max = r.get("wind_max")
            wind_str = f"{wind_min:.0f} / {wind_max:.0f} km/h" if wind_min is not None else "-"

            # Gusts
            gust_max = r.get("gust_max")
            gust_str = f"{gust_max:.0f} km/h" if gust_max else "-"

            temp_rows.append({
                "location": loc.name,
                "temp": temp_str,
                "wind_chill": wc_str,
                "wind": wind_str,
                "gust": gust_str,
            })

        if temp_rows:
            ui.table(columns=temp_columns, rows=temp_rows, row_key="location").classes("w-full")

    # Additional details table
    with ui.card().classes("w-full mb-4"):
        ui.label("Weitere Details").classes("text-subtitle1 font-medium mb-2")

        detail_columns = [
            {"name": "location", "label": "Location", "field": "location"},
            {"name": "snowfall_limit", "label": "Schneefallgrenze", "field": "snowfall_limit", "align": "center"},
            {"name": "humidity", "label": "Feuchte (min/max)", "field": "humidity", "align": "center"},
            {"name": "precip", "label": "Niederschlag", "field": "precip", "align": "center"},
            {"name": "pressure", "label": "Druck (min/max)", "field": "pressure", "align": "center"},
        ]

        detail_rows = []
        for r in results:
            loc = r["location"]
            if r.get("error"):
                continue

            # Snowfall limit - show average, explain meaning
            sl_avg = r.get("snowfall_limit_avg")
            elevation = loc.elevation_m
            if sl_avg is not None:
                sl_str = f"~{sl_avg}m"
            else:
                sl_str = "-"

            # Humidity
            hum_min = r.get("humidity_min")
            hum_max = r.get("humidity_max")
            humidity_str = f"{hum_min}% / {hum_max}%" if hum_min is not None else "-"

            # Precipitation with snow/rain indicator
            precip = r.get("precip_mm")
            if precip and precip > 0:
                # Determine if snow or rain based on snowfall limit vs elevation
                if sl_avg is not None:
                    if elevation >= sl_avg + 200:
                        precip_type = "❄️"  # Clearly above snowfall limit → snow
                    elif elevation <= sl_avg - 200:
                        precip_type = "🌧️"  # Clearly below → rain
                    else:
                        precip_type = "❄️/🌧️"  # Mixed zone
                else:
                    # No snowfall limit data - guess from temperature
                    temp_avg = r.get("temp_avg")
                    if temp_avg is not None and temp_avg < 0:
                        precip_type = "❄️"
                    elif temp_avg is not None and temp_avg > 3:
                        precip_type = "🌧️"
                    else:
                        precip_type = "?"
                precip_str = f"{precip:.1f} mm {precip_type}"
            else:
                precip_str = "0 mm"

            # Pressure
            pres_min = r.get("pressure_min")
            pres_max = r.get("pressure_max")
            pressure_str = f"{pres_min:.0f} / {pres_max:.0f} hPa" if pres_min else "-"

            detail_rows.append({
                "location": loc.name,
                "snowfall_limit": sl_str,
                "humidity": humidity_str,
                "precip": precip_str,
                "pressure": pressure_str,
            })

        if detail_rows:
            ui.table(columns=detail_columns, rows=detail_rows, row_key="location").classes("w-full")

    # Winner highlight
    if results and not results[0].get("error"):
        winner = results[0]
        loc = winner["location"]
        with ui.card().classes("w-full mt-4 bg-green-50"):
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

    # Legend
    ui.label(
        "Schneefallgrenze = Höhe, ab der Niederschlag als Schnee fällt. "
        "❄️ = Schnee, 🌧️ = Regen, ❄️/🌧️ = Grenzbereich"
    ).classes("text-xs text-gray-400 mt-4")
