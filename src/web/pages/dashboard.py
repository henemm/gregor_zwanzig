"""
Dashboard page - overview and quick actions.
"""
from __future__ import annotations

from pathlib import Path

from nicegui import ui

DATA_DIR = Path("data/users/default")


def count_files(directory: Path, pattern: str = "*.json") -> int:
    """Count JSON files in a directory."""
    if not directory.exists():
        return 0
    return len(list(directory.glob(pattern)))


def render_dashboard() -> None:
    """Render the dashboard page."""
    with ui.header().classes("items-center justify-between"):
        ui.label("Gregor Zwanzig").classes("text-h6")
        with ui.row():
            ui.link("Dashboard", "/").classes("text-white mx-2")
            ui.link("Locations", "/locations").classes("text-white mx-2")
            ui.link("Trips", "/trips").classes("text-white mx-2")
            ui.link("Compare", "/compare").classes("text-white mx-2")
            ui.link("Subscriptions", "/subscriptions").classes("text-white mx-2")
            ui.link("Settings", "/settings").classes("text-white mx-2")

    with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
        ui.label("Dashboard").classes("text-h4 mb-4")

        # Stats cards
        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("flex-1"):
                ui.label("Locations").classes("text-h6")
                location_count = count_files(DATA_DIR / "locations")
                ui.label(str(location_count)).classes("text-h3")
                ui.button(
                    "Manage",
                    on_click=lambda: ui.navigate.to("/locations"),
                ).props("flat")

            with ui.card().classes("flex-1"):
                ui.label("Trips").classes("text-h6")
                trip_count = count_files(DATA_DIR / "trips")
                ui.label(str(trip_count)).classes("text-h3")
                ui.button(
                    "Manage",
                    on_click=lambda: ui.navigate.to("/trips"),
                ).props("flat")

        # Quick actions
        ui.label("Quick Actions").classes("text-h5 mt-6 mb-2")

        with ui.row().classes("gap-4"):
            ui.button(
                "Compare Forecast",
                on_click=lambda: ui.navigate.to("/compare"),
                icon="compare",
            ).props("color=primary")

            ui.button(
                "New Location",
                on_click=lambda: ui.navigate.to("/locations"),
                icon="add_location",
            ).props("color=secondary")

            ui.button(
                "New Trip",
                on_click=lambda: ui.navigate.to("/trips"),
                icon="route",
            ).props("color=secondary")
