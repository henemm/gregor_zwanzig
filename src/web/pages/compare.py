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




# === Phase A.1 Refactor (Epic #129): Helpers extracted to services/ ===
# Until Phase A.3 (NiceGUI removal): Re-imports keep UI lauffaehig and other
# UI helpers below in this file working without changes.
from services.comparison_scoring import (
    calculate_score,
    _score_wintersport,
    _score_wandern,
    _score_allgemein,
)
from services.comparison_engine import (
    ComparisonEngine,
    dict_to_comparison_result,
    fetch_forecast_for_location,
    _select_provider_for_location,
)
from services.comparison_renderers import (
    render_comparison_html,
    render_comparison_text,
    _degrees_to_compass,
)




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

    from app.user import Schedule

    now = datetime.now()

    # Determine target date based on schedule type:
    # - DAILY_MORNING (07:00): Forecast for TODAY
    # - DAILY_EVENING (18:00) / WEEKLY: Forecast for TOMORROW
    if sub.schedule == Schedule.DAILY_MORNING:
        target_date = date.today()
        # For today: need hours from now until end of time window
        min_forecast_hours = max(0, sub.time_window_end - now.hour + 1)
    else:
        target_date = date.today() + timedelta(days=1)
        # For tomorrow: need remaining hours today + hours into tomorrow
        hours_remaining_today = 24 - now.hour
        hours_tomorrow_needed = sub.time_window_end + 1
        min_forecast_hours = hours_remaining_today + hours_tomorrow_needed

    # Use at least the configured hours, but ensure we have enough for the time window
    actual_forecast_hours = max(sub.forecast_hours, min_forecast_hours, 48)

    # Use ComparisonEngine (Single Processor Architecture)
    result = ComparisonEngine.run(
        locations=selected_locs,
        time_window=(sub.time_window_start, sub.time_window_end),
        target_date=target_date,
        forecast_hours=actual_forecast_hours,
    )

    # SPEC: docs/specs/modules/api_retry.md - Check for missing locations
    successful_loc_ids = {r.location.id for r in result.locations if r.score is not None}
    failed_locations = [loc for loc in selected_locs if loc.id not in successful_loc_ids]

    # Use both renderers for Multipart Email (SPEC v4.2)
    html_body = render_comparison_html(result, top_n_details=sub.top_n)
    text_body = render_comparison_text(result, top_n_details=sub.top_n)

    # Add warning banner if locations failed (API errors after retries)
    if failed_locations:
        failed_names = ", ".join(loc.name for loc in failed_locations[:3])
        if len(failed_locations) > 3:
            failed_names += f" (+{len(failed_locations) - 3} more)"

        warning_html = f'''
        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px 16px; margin: 0 20px 16px 20px; border-radius: 4px;">
            <strong>⚠️ Warning:</strong> {len(failed_locations)} location(s) unavailable due to API errors: {failed_names}
        </div>
'''
        # Insert after header div
        html_body = html_body.replace(
            '</div>\n\n        <div class="winner">',
            f'</div>\n{warning_html}\n        <div class="winner">'
        )

        warning_text = f"\n⚠️ WARNING: {len(failed_locations)} location(s) unavailable: {failed_names}\n"
        # Insert after header in text version
        text_body = text_body.replace("=" * 24, "=" * 24 + warning_text, 1)

    subject = f"Ski Resort Comparison: {sub.name} ({now.strftime('%d.%m.%Y')})"
    return subject, html_body, text_body


def render_header() -> None:
    """Render navigation header."""
    with ui.header().classes("items-center justify-between"):
        ui.label("Gregor Zwanzig").classes("text-h6")
        with ui.row():
            ui.link("Dashboard", "/").classes("text-white mx-2")
            ui.link("Locations", "/locations").classes("text-white mx-2")
            ui.link("Trips", "/trips").classes("text-white mx-2")
            ui.link("Compare", "/compare").classes("text-white mx-2")
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
        "selected_locations": [],  # Safari fix: explicit state for select
    }

    def on_location_change(e) -> None:
        """Handle location selection change - Safari fix."""
        state["selected_locations"] = e.value if e.value else []

    def make_location_change_handler():
        """Factory function for location select onChange (Safari compatibility)."""
        def do_change(e) -> None:
            on_location_change(e)
        return do_change

    with ui.column().classes("w-full max-w-6xl mx-auto p-4"):
        ui.label("Forecast Comparison").classes("text-h4 mb-4")
        ui.label("Which ski resort has the best conditions?").classes("text-gray-500 mb-4")

        locations = load_all_locations()

        if not locations:
            ui.label(
                "No locations saved. Please create locations first."
            ).classes("text-gray-500")
            ui.button(
                "Manage Locations",
                on_click=lambda: ui.navigate.to("/locations"),
            ).props("outline")
            return

        # Location selection
        with ui.card().classes("w-full mb-4"):
            ui.label("Select Locations").classes("text-h6 mb-2")

            location_options = {loc.id: f"{loc.name} ({loc.elevation_m}m)" for loc in locations}

            select = ui.select(
                options=location_options,
                multiple=True,
                label="Locations (multiple)",
                on_change=make_location_change_handler(),
            ).classes("w-full").props("use-chips")

            with ui.row().classes("items-center gap-4 mt-2"):
                ui.label("Date:")
                date_options = {
                    0: "Today",
                    1: "Tomorrow",
                    2: "Day after tomorrow",
                }
                date_select = ui.select(
                    options=date_options,
                    value=1,
                    label="Day",
                ).classes("w-32")

            with ui.row().classes("items-center gap-4 mt-2"):
                ui.label("Time Window:")
                hour_options = {h: f"{h:02d}:00" for h in range(6, 22)}
                time_start_select = ui.select(
                    options=hour_options,
                    value=9,
                    label="From",
                ).classes("w-28")
                ui.label("to")
                time_end_select = ui.select(
                    options=hour_options,
                    value=16,
                    label="To",
                ).classes("w-28")

        # Results area with refreshable
        @ui.refreshable
        def results_ui() -> None:
            if state["loading"]:
                with ui.row().classes("items-center gap-2 mb-4"):
                    ui.spinner("dots", size="lg")
                    ui.label("Loading Forecasts...")
                return

            if not state["results"]:
                ui.label("Select locations and click 'Compare'").classes("text-gray-400 my-8")
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
            if not state["selected_locations"]:
                ui.notify("Please select at least one location", type="warning")
                return

            selected_locs = [loc for loc in locations if loc.id in state["selected_locations"]]
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
                            result["cloud_avg"] = int(sum(effective_clouds) / len(effective_clouds))

                        # Flag: is location above low clouds? (elevation >= 2500m)
                        result["above_low_clouds"] = (
                            loc.elevation_m is not None
                            and loc.elevation_m >= WeatherMetricsService.HIGH_ELEVATION_THRESHOLD_M
                        )

                        # Sunny hours: Use WeatherMetricsService (Single Source of Truth)
                        result["sunny_hours"] = WeatherMetricsService.calculate_sunny_hours(
                            filtered_data, loc.elevation_m
                        )

                        # Precipitation
                        precips = [dp.precip_1h_mm for dp in filtered_data if dp.precip_1h_mm is not None]
                        if precips:
                            result["precip_mm"] = sum(precips)

                        # Recalculate score with filtered data
                        result["score"] = calculate_score(result, profile=getattr(loc, 'activity_profile', None) if 'loc' in dir() else None)

            # Sort by score (highest first)
            results.sort(key=lambda r: r.get("score", 0), reverse=True)

            state["results"] = results
            state["hourly_data"] = hourly_data
            state["loading"] = False
            results_ui.refresh()

        async def send_email() -> None:
            """Send comparison results via email using single renderer."""
            if not state["results"]:
                ui.notify("Please run a comparison first", type="warning")
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
                subject = f"Ski Resort Comparison ({datetime.now().strftime('%d.%m.%Y')})"

                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: email_output.send(subject, email_html, plain_text_body=email_text)
                )

                ui.notify(f"E-Mail gesendet an {settings.mail_to}", type="positive")

                # Also send via Telegram if configured
                if settings.can_send_telegram():
                    try:
                        from outputs.telegram import TelegramOutput
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: TelegramOutput(settings).send(subject, email_text)
                        )
                        ui.notify("Telegram gesendet", type="positive")
                    except Exception as tg_err:
                        logger.error(f"Telegram failed: {tg_err}")

            except OutputConfigError as e:
                ui.notify(f"SMTP-Konfigurationsfehler: {e}", type="negative")
            except OutputError as e:
                ui.notify(f"E-Mail-Versand fehlgeschlagen: {e}", type="negative")
            except Exception as e:
                ui.notify(f"Fehler: {e}", type="negative")

        def make_comparison_handler():
            """Factory function for comparison button (Safari compatibility)."""
            async def do_compare() -> None:
                await run_comparison()
            return do_compare

        def make_email_handler():
            """Factory function for email button (Safari compatibility)."""
            async def do_email() -> None:
                await send_email()
            return do_email

        # Check if email is configured
        settings = Settings()
        can_email = settings.can_send_email()

        with ui.row().classes("gap-2"):
            ui.button(
                "Compare",
                on_click=make_comparison_handler(),
                icon="compare_arrows",
            ).props("color=primary size=lg")

            if can_email:
                ui.button(
                    "Per E-Mail senden",
                    on_click=make_email_handler(),
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
        ui.label("Hourly Overview").classes("text-subtitle1 font-medium mb-2")
        ui.label("Temperature = felt (Wind Chill)").classes("text-xs text-gray-500 mb-2")

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
                ui.label("Cloud Layers Details").classes("text-subtitle1 font-medium")
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
                date_str = target_date.strftime('%A, %d.%m.%Y') if target_date else "Tomorrow"
                ui.label(f"Recommendation for {date_str}:").classes("text-sm text-green-700")
                ui.label(f"🏆 {loc.name}").classes("text-h6")
                snow_depth = winner.get("snow_depth_cm")
                snow_new = winner.get("snow_new_cm", 0)
                sunny = winner.get("sunny_hours", 0)

                details = f"Score: {winner.get('score', 0)}"
                if snow_depth:
                    details += f" | Snow Depth: {snow_depth:.0f}cm"
                if snow_new:
                    details += f" | New Snow: +{snow_new:.0f}cm"
                if sunny:
                    details += f" | Sun: ~{sunny}h"
                ui.label(details).classes("text-gray-600")


def render_results_table(results: List[Dict[str, Any]]) -> None:
    """Render comparison table with locations as columns, metrics as rows."""
    if not results:
        ui.label("No results").classes("text-gray-500")
        return

    # Filter out error results for comparison
    valid_results = [r for r in results if not r.get("error")]
    if not valid_results:
        ui.label("All requests failed").classes("text-red-500")
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
    above_low_clouds_flags = [r.get("above_low_clouds", False) for r in valid_results]

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
        ui.label("Comparison").classes("text-subtitle1 font-medium mb-2")

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
                        ui.label("Snow Depth")
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
                        ui.label("New Snow")
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
                        ui.label("Wind/Gusts")
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
                        ui.label("Temperature (felt)")
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
                        ui.label("Sunny Hours")
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

                # Clouds row - SPEC: docs/specs/cloud_cover_simplification.md
                # Uses effective cloud (elevation-aware) with "*" marker for high elevations
                with ui.element("tr").classes("border-b"):
                    with ui.element("td").classes("p-2 font-medium bg-gray-50"):
                        ui.label("Cloud Cover")
                    for i, (cloud, above_low) in enumerate(zip(clouds, above_low_clouds_flags)):
                        is_best = i == best_clouds
                        marker = "*" if above_low else ""
                        with ui.element("td").classes("p-2 text-center").style(
                            "background-color: #dcfce7; font-weight: bold" if is_best else ""
                        ):
                            text = f"{cloud}%{marker}" if cloud is not None else "-"
                            ui.label(text)

    # Legend
    with ui.column().classes("mt-2 gap-0"):
        ui.label(
            "Green = best value | Temperature = felt (Wind Chill) | * lower clouds ignored"
        ).classes("text-xs text-gray-400")
        ui.label(
            "☀️ <20% clouds | 🌤️ 20-50% | ⛅ 50-80% | ☁️ >80% | 🌧️ rain | ❄️ snow"
        ).classes("text-xs text-gray-400")
