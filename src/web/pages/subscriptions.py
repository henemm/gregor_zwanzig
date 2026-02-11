"""
Compare Subscriptions management page.

Allows users to create, edit, and manage scheduled email
subscriptions for ski resort comparisons.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any, Dict, List

from nicegui import ui

from app.config import Settings
from app.loader import (
    load_all_locations,
    load_compare_subscriptions,
    save_compare_subscription,
    delete_compare_subscription,
)
from app.user import CompareSubscription, Schedule
from outputs.email import EmailOutput
from outputs.base import OutputConfigError, OutputError


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


def render_subscriptions() -> None:
    """Render the subscriptions management page."""
    render_header()

    state: Dict[str, Any] = {
        "editing": None,  # ID of subscription being edited, or "new" for new
    }

    with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
        ui.label("Email Subscriptions").classes("text-h4 mb-4")
        ui.label(
            "Automatic ski resort comparison via email at scheduled times."
        ).classes("text-gray-500 mb-4")

        # Check SMTP
        settings = Settings()
        if not settings.can_send_email():
            with ui.card().classes("w-full mb-4 bg-yellow-50"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning", color="orange")
                    ui.label(
                        "SMTP not configured. Please configure in Settings first."
                    )
                    ui.button(
                        "Settings",
                        on_click=lambda: ui.navigate.to("/settings"),
                    ).props("outline size=sm")

        locations = load_all_locations()
        if not locations:
            with ui.card().classes("w-full mb-4 bg-yellow-50"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("place", color="orange")
                    ui.label("No locations available. Please create locations first.")
                    ui.button(
                        "Locations",
                        on_click=lambda: ui.navigate.to("/locations"),
                    ).props("outline size=sm")
            return

        @ui.refreshable
        def subscription_list() -> None:
            subscriptions = load_compare_subscriptions()

            if not subscriptions:
                ui.label(
                    "No subscriptions yet. Create a new subscription."
                ).classes("text-gray-400 my-4")
            else:
                for sub in subscriptions:
                    render_subscription_card(sub, state, subscription_list)

        subscription_list()

        # New subscription button
        def make_new_handler():
            def do_new() -> None:
                show_subscription_dialog(None, locations, subscription_list)
            return do_new

        ui.button(
            "New Subscription",
            on_click=make_new_handler(),
            icon="add",
        ).props("color=primary")


def render_subscription_card(
    sub: CompareSubscription,
    state: Dict[str, Any],
    refresh_fn,
) -> None:
    """Render a single subscription card."""
    locations = load_all_locations()
    loc_names = {loc.id: loc.name for loc in locations}

    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def get_schedule_label(subscription: CompareSubscription) -> str:
        if subscription.schedule == Schedule.DAILY_MORNING:
            return "07:00 (today)"
        elif subscription.schedule == Schedule.DAILY_EVENING:
            return "18:00 (tomorrow)"
        elif subscription.schedule == Schedule.WEEKLY:
            day = weekday_names[subscription.weekday] if 0 <= subscription.weekday <= 6 else "?"
            return f"{day} 18:00 (tomorrow)"
        elif subscription.schedule == Schedule.BEFORE_TRIP:
            return "Before trip"
        return subscription.schedule.value

    with ui.card().classes("w-full mb-2"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-0"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(sub.name).classes(
                        "text-subtitle1 font-medium"
                        if sub.enabled
                        else "text-subtitle1 text-gray-400"
                    )
                    if not sub.enabled:
                        ui.chip("Disabled", color="gray").props("dense")

                # Details
                loc_str = (
                    "All locations"
                    if sub.locations == ["*"] or not sub.locations
                    else ", ".join(loc_names.get(l, l) for l in sub.locations[:3])
                )
                if len(sub.locations) > 3:
                    loc_str += f" +{len(sub.locations) - 3}"

                ui.label(
                    f"{get_schedule_label(sub)} | "
                    f"{sub.time_window_start:02d}:00-{sub.time_window_end:02d}:00 | "
                    f"{sub.forecast_hours}h Forecast"
                ).classes("text-xs text-gray-500")

                ui.label(f"Locations: {loc_str}").classes("text-xs text-gray-400")

            with ui.row().classes("gap-1"):
                # Toggle enable/disable
                def make_toggle_handler(subscription):
                    def do_toggle() -> None:
                        updated = CompareSubscription(
                            id=subscription.id,
                            name=subscription.name,
                            enabled=not subscription.enabled,
                            locations=subscription.locations,
                            forecast_hours=subscription.forecast_hours,
                            time_window_start=subscription.time_window_start,
                            time_window_end=subscription.time_window_end,
                            schedule=subscription.schedule,
                            include_hourly=subscription.include_hourly,
                            top_n=subscription.top_n,
                        )
                        save_compare_subscription(updated)
                        refresh_fn.refresh()
                    return do_toggle

                ui.button(
                    icon="play_arrow" if not sub.enabled else "pause",
                    on_click=make_toggle_handler(sub),
                ).props("flat dense").tooltip(
                    "Enable" if not sub.enabled else "Disable"
                )

                # Run now
                def make_run_now_handler(subscription):
                    async def do_run_now() -> None:
                        from web.pages.compare import run_comparison_for_subscription

                        settings = Settings()
                        if not settings.can_send_email():
                            ui.notify("SMTP not configured", type="negative")
                            return

                        ui.notify(f"Running '{subscription.name}'...", type="info")
                        try:
                            # SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
                            all_locs = load_all_locations()
                            subject, html_body, text_body = await asyncio.get_event_loop().run_in_executor(
                                None,
                                lambda: run_comparison_for_subscription(subscription, all_locs),
                            )

                            email_output = EmailOutput(settings)
                            await asyncio.get_event_loop().run_in_executor(
                                None, lambda: email_output.send(subject, html_body, plain_text_body=text_body)
                            )

                            ui.notify(f"Email sent: {subject}", type="positive")
                        except Exception as e:
                            ui.notify(f"Error: {e}", type="negative")
                    return do_run_now

                ui.button(
                    icon="send",
                    on_click=make_run_now_handler(sub),
                ).props("flat dense").tooltip("Run now")

                # Edit
                def make_edit_handler(subscription):
                    def do_edit() -> None:
                        locs = load_all_locations()
                        show_subscription_dialog(subscription, locs, refresh_fn)
                    return do_edit

                ui.button(
                    icon="edit",
                    on_click=make_edit_handler(sub),
                ).props("flat dense")

                # Delete
                def make_delete_handler(subscription):
                    def do_delete() -> None:
                        delete_compare_subscription(subscription.id)
                        refresh_fn.refresh()
                        ui.notify(f"Subscription '{subscription.name}' deleted", type="info")
                    return do_delete

                ui.button(
                    icon="delete",
                    on_click=make_delete_handler(sub),
                ).props("flat dense color=red")


def show_subscription_dialog(
    sub: CompareSubscription | None,
    locations: List,
    refresh_fn,
) -> None:
    """Show dialog for creating/editing a subscription."""
    is_new = sub is None

    with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
        ui.label("New Subscription" if is_new else "Edit Subscription").classes(
            "text-h6 mb-4"
        )

        # Form fields
        name_input = ui.input(
            "Name",
            value="" if is_new else sub.name,
            placeholder="e.g. Weekend Check",
        ).classes("w-full")

        location_options = {loc.id: f"{loc.name} ({loc.elevation_m}m)" for loc in locations}
        location_options["*"] = "All locations"

        initial_locs = ["*"] if is_new else (sub.locations or ["*"])
        location_select = ui.select(
            options=location_options,
            multiple=True,
            value=initial_locs,
            label="Locations",
        ).classes("w-full").props("use-chips")

        schedule_options = {
            "daily_morning": "Daily 07:00 (forecast: today)",
            "daily_evening": "Daily 18:00 (forecast: tomorrow)",
            "weekly": "Weekly 18:00 (forecast: tomorrow)",
        }
        schedule_select = ui.select(
            options=schedule_options,
            value="weekly" if is_new else sub.schedule.value,
            label="Schedule",
        ).classes("w-full")

        weekday_options = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        }
        weekday_row = ui.row().classes("w-full")
        weekday_select = None

        with weekday_row:
            weekday_select = ui.select(
                options=weekday_options,
                value=4 if is_new else sub.weekday,
                label="Weekday",
            ).classes("w-full")

        # Show/hide weekday based on schedule
        def update_weekday_visibility() -> None:
            weekday_row.set_visibility(schedule_select.value == "weekly")

        schedule_select.on_value_change(lambda _: update_weekday_visibility())
        update_weekday_visibility()

        with ui.row().classes("gap-4 w-full"):
            hour_options = {h: f"{h:02d}:00" for h in range(6, 22)}
            time_start = ui.select(
                options=hour_options,
                value=9 if is_new else sub.time_window_start,
                label="Time Window Start",
            ).classes("flex-1")
            time_end = ui.select(
                options=hour_options,
                value=16 if is_new else sub.time_window_end,
                label="Time Window End",
            ).classes("flex-1")

        forecast_options = {24: "24h", 48: "48h", 72: "72h"}
        forecast_select = ui.select(
            options=forecast_options,
            value=48 if is_new else sub.forecast_hours,
            label="Forecast Period",
        ).classes("w-full")

        include_hourly = ui.checkbox(
            "Hourly details in email",
            value=True if is_new else sub.include_hourly,
        )

        top_n = ui.number(
            "Top N for details",
            value=3 if is_new else sub.top_n,
            min=1,
            max=10,
        ).classes("w-full")

        enabled = ui.checkbox(
            "Enabled",
            value=True if is_new else sub.enabled,
        )

        # Actions
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            def make_save_handler():
                def do_save() -> None:
                    if not name_input.value:
                        ui.notify("Name is required", type="warning")
                        return

                    # Generate ID from name if new
                    sub_id = (
                        re.sub(r"[^a-z0-9]", "-", name_input.value.lower())
                        if is_new
                        else sub.id
                    )

                    # Handle locations
                    selected_locs = list(location_select.value) if location_select.value else ["*"]
                    if "*" in selected_locs and len(selected_locs) > 1:
                        selected_locs = ["*"]  # If "all" is selected, ignore others

                    new_sub = CompareSubscription(
                        id=sub_id,
                        name=name_input.value,
                        enabled=enabled.value,
                        locations=selected_locs,
                        forecast_hours=forecast_select.value or 48,
                        time_window_start=time_start.value or 9,
                        time_window_end=time_end.value or 16,
                        schedule=Schedule(schedule_select.value or "weekly"),
                        weekday=weekday_select.value if weekday_select else 4,
                        include_hourly=include_hourly.value,
                        top_n=int(top_n.value or 3),
                    )

                    save_compare_subscription(new_sub)
                    dialog.close()
                    refresh_fn.refresh()
                    ui.notify(
                        f"Subscription '{new_sub.name}' saved",
                        type="positive",
                    )
                return do_save

            ui.button("Save", on_click=make_save_handler()).props("color=primary")

    dialog.open()
