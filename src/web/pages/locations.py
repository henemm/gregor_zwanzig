"""
Location management page.
"""
from __future__ import annotations

from nicegui import ui

from app.loader import (
    delete_location,
    load_all_locations,
    save_location,
)
from app.user import SavedLocation


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


def render_locations() -> None:
    """Render the locations page."""
    render_header()

    container = ui.column().classes("w-full max-w-4xl mx-auto p-4")

    def refresh_list() -> None:
        """Refresh the locations list."""
        container.clear()
        with container:
            render_content()

    def render_content() -> None:
        """Render page content."""
        ui.label("Locations").classes("text-h4 mb-4")

        def show_add_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Neue Location").classes("text-h6 mb-4")

                name_input = ui.input(
                    "Name",
                    placeholder="z.B. Stubaier Gletscher",
                ).classes("w-full")
                lat_input = ui.number(
                    "Breitengrad",
                    value=47.0,
                    format="%.4f",
                ).classes("w-full")
                lon_input = ui.number(
                    "Längengrad",
                    value=11.0,
                    format="%.4f",
                ).classes("w-full")
                elev_input = ui.number(
                    "Höhe (m)",
                    value=2000,
                ).classes("w-full")
                region_input = ui.input(
                    "Lawinenregion (optional)",
                    placeholder="z.B. AT-7",
                ).classes("w-full")

                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    ui.button("Abbrechen", on_click=dialog.close).props("flat")

                    def save() -> None:
                        if not name_input.value:
                            ui.notify("Name ist erforderlich", type="negative")
                            return

                        loc_id = name_input.value.lower().replace(" ", "-")
                        loc_id = "".join(c for c in loc_id if c.isalnum() or c == "-")

                        location = SavedLocation(
                            id=loc_id,
                            name=name_input.value,
                            lat=float(lat_input.value or 47.0),
                            lon=float(lon_input.value or 11.0),
                            elevation_m=int(elev_input.value or 2000),
                            region=region_input.value or None,
                        )
                        save_location(location)
                        ui.notify(f"Location '{location.name}' gespeichert", type="positive")
                        dialog.close()
                        refresh_list()

                    ui.button("Speichern", on_click=save).props("color=primary")

            dialog.open()

        ui.button(
            "Neue Location",
            on_click=show_add_dialog,
            icon="add_location",
        ).props("color=primary")

        # List existing locations
        locations = load_all_locations()

        if not locations:
            ui.label("Noch keine Locations gespeichert.").classes("text-gray-500 mt-4")
        else:
            ui.label(f"{len(locations)} Location(s)").classes("text-gray-500 mt-4 mb-2")

            for loc in locations:
                with ui.card().classes("w-full mb-2"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-0"):
                            ui.label(loc.name).classes("text-h6")
                            ui.label(
                                f"{loc.lat:.4f}°N, {loc.lon:.4f}°E, {loc.elevation_m}m"
                            ).classes("text-gray-500 text-sm")
                            if loc.region:
                                ui.badge(loc.region).props("color=blue")

                        def make_delete_handler(lid: str, lname: str):
                            def do_delete() -> None:
                                delete_location(lid)
                                ui.notify(f"'{lname}' gelöscht", type="warning")
                                refresh_list()
                            return do_delete

                        ui.button(
                            icon="delete",
                            on_click=make_delete_handler(loc.id, loc.name),
                        ).props("flat color=negative")

    render_content()
