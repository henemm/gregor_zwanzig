"""
Forecast comparison page.

Use case: "Welches Skigebiet morgen?"
Compare multiple locations side-by-side with scoring.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from nicegui import ui

from app.config import Location
from app.loader import load_all_locations
from app.user import SavedLocation
from providers.geosphere import GeoSphereProvider
from services.forecast import ForecastService


def calculate_score(metrics: Dict[str, Any]) -> int:
    """
    Calculate a score for ski conditions (higher = better).

    Weights:
    - Neuschnee: 30% (mehr = besser)
    - Wind: 25% (weniger = besser)
    - Sicht/Wolken: 15% (weniger Wolken = besser)
    - Temperatur: 15% (moderate Kälte = besser)
    - Niederschlag: 15% (weniger = besser während Skifahren)
    """
    score = 50  # Base score

    snow_cm = metrics.get("snow_new_cm", 0)
    wind_max = metrics.get("wind_max")
    gust_max = metrics.get("gust_max")
    cloud_avg = metrics.get("cloud_avg")
    temp_min = metrics.get("temp_min")
    precip_mm = metrics.get("precip_mm", 0)

    # Snow bonus (max +30)
    if snow_cm:
        snow_bonus = min(30, int(snow_cm * 2))
        score += snow_bonus

    # Wind penalty (max -25)
    if wind_max:
        if wind_max > 60:
            score -= 25
        elif wind_max > 40:
            score -= 15
        elif wind_max > 25:
            score -= 5

    # Gust penalty
    if gust_max and gust_max > 70:
        score -= 10

    # Cloud/visibility (max -15)
    if cloud_avg is not None:
        if cloud_avg > 80:
            score -= 15
        elif cloud_avg > 50:
            score -= 5

    # Temperature (ideal: -5 to -10)
    if temp_min is not None:
        if temp_min < -20:
            score -= 10  # Too cold
        elif temp_min > 5:
            score -= 10  # Too warm for good snow
        elif -10 <= temp_min <= -3:
            score += 5  # Ideal

    # Precipitation penalty (rain during skiing)
    if precip_mm > 0 and temp_min and temp_min > 0:
        score -= 10  # Rain is bad

    return max(0, min(100, score))


def fetch_forecast_for_location(loc: SavedLocation) -> Dict[str, Any]:
    """Fetch forecast for a location and extract metrics."""
    result: Dict[str, Any] = {
        "location": loc,
        "error": None,
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

        forecast = service.get_forecast(location, hours_ahead=48)
        provider.close()

        # Extract metrics from forecast data
        if forecast.data:
            temps = [dp.t2m_c for dp in forecast.data if dp.t2m_c is not None]
            winds = [dp.wind10m_kmh for dp in forecast.data if dp.wind10m_kmh is not None]
            gusts = [dp.gust_kmh for dp in forecast.data if dp.gust_kmh is not None]
            clouds = [dp.cloud_total_pct for dp in forecast.data if dp.cloud_total_pct is not None]
            precips = [dp.precip_1h_mm for dp in forecast.data if dp.precip_1h_mm is not None]

            if temps:
                result["temp_min"] = min(temps)
                result["temp_max"] = max(temps)
            if winds:
                result["wind_max"] = max(winds)
            if gusts:
                result["gust_max"] = max(gusts)
            if clouds:
                result["cloud_avg"] = int(sum(clouds) / len(clouds))
            if precips:
                result["precip_mm"] = sum(precips)

            # Snow accumulation (last value of accumulated)
            snow_accs = [dp.snow_new_acc_cm for dp in forecast.data if dp.snow_new_acc_cm is not None]
            if snow_accs:
                result["snow_new_cm"] = max(snow_accs)
            else:
                result["snow_new_cm"] = 0

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

        # Results container
        results_container = ui.column().classes("w-full")

        async def run_comparison() -> None:
            if not select.value:
                ui.notify("Bitte mindestens eine Location auswählen", type="warning")
                return

            selected_locs = [loc for loc in locations if loc.id in select.value]

            results_container.clear()
            with results_container:
                with ui.row().classes("items-center gap-2 mb-4"):
                    ui.spinner("dots", size="lg")
                    ui.label(f"Lade Forecasts für {len(selected_locs)} Location(s)...")

            # Fetch forecasts (run in background to not block UI)
            results: List[Dict[str, Any]] = []
            for loc in selected_locs:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, fetch_forecast_for_location, loc
                )
                results.append(result)

            # Sort by score (highest first)
            results.sort(key=lambda r: r.get("score", 0), reverse=True)

            # Display results
            results_container.clear()
            with results_container:
                render_results_table(results)

        ui.button(
            "Vergleichen",
            on_click=run_comparison,
            icon="compare_arrows",
        ).props("color=primary size=lg")


def render_results_table(results: List[Dict[str, Any]]) -> None:
    """Render the comparison results table."""
    if not results:
        ui.label("Keine Ergebnisse").classes("text-gray-500")
        return

    ui.label("Ergebnisse (sortiert nach Score)").classes("text-h6 mb-2")

    # Header row
    columns = [
        {"name": "rank", "label": "#", "field": "rank", "align": "center"},
        {"name": "location", "label": "Location", "field": "location"},
        {"name": "score", "label": "Score", "field": "score", "align": "center"},
        {"name": "snow", "label": "Neuschnee", "field": "snow", "align": "center"},
        {"name": "temp", "label": "Temp", "field": "temp", "align": "center"},
        {"name": "wind", "label": "Wind", "field": "wind", "align": "center"},
        {"name": "clouds", "label": "Wolken", "field": "clouds", "align": "center"},
    ]

    rows = []
    for i, r in enumerate(results):
        loc = r["location"]
        if r.get("error"):
            rows.append({
                "rank": i + 1,
                "location": loc.name,
                "score": "Fehler",
                "snow": "-",
                "temp": "-",
                "wind": "-",
                "clouds": str(r["error"])[:30],
            })
        else:
            temp_min = r.get("temp_min")
            temp_max = r.get("temp_max")
            temp_str = f"{temp_min:.0f} / {temp_max:.0f}°C" if temp_min is not None else "-"

            wind_max = r.get("wind_max")
            wind_str = f"{wind_max:.0f} km/h" if wind_max else "-"

            cloud_avg = r.get("cloud_avg")
            cloud_str = f"{cloud_avg}%" if cloud_avg is not None else "-"

            snow_cm = r.get("snow_new_cm", 0)
            snow_str = f"{snow_cm:.0f} cm" if snow_cm else "0 cm"

            rows.append({
                "rank": i + 1,
                "location": loc.name,
                "score": r.get("score", 0),
                "snow": snow_str,
                "temp": temp_str,
                "wind": wind_str,
                "clouds": cloud_str,
            })

    ui.table(columns=columns, rows=rows, row_key="location").classes("w-full")

    # Winner highlight
    if results and not results[0].get("error"):
        winner = results[0]
        loc = winner["location"]
        with ui.card().classes("w-full mt-4 bg-green-50"):
            with ui.row().classes("items-center gap-4"):
                ui.icon("emoji_events", color="amber", size="xl")
                with ui.column().classes("gap-0"):
                    ui.label(f"Empfehlung: {loc.name}").classes("text-h6")
                    snow = winner.get("snow_new_cm", 0)
                    ui.label(f"Score: {winner.get('score', 0)} | Neuschnee: {snow:.0f}cm").classes("text-gray-600")
