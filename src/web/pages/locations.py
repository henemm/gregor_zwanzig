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
from web.utils import parse_dms_coordinates


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


def render_locations() -> None:
    """Render the locations page."""
    render_header()

    container = ui.column().classes("w-full max-w-4xl mx-auto p-4")

    def refresh_list() -> None:
        """Refresh the locations list."""
        container.clear()
        with container:
            render_content()

    def show_edit_dialog(loc: SavedLocation) -> None:
        """Show dialog to edit an existing location."""
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label(f"Edit Location: {loc.name}").classes("text-h6 mb-4")

            name_input = ui.input("Name", value=loc.name).classes("w-full")
            lat_input = ui.number("Latitude", value=loc.lat, format="%.6f").classes("w-full")
            lon_input = ui.number("Longitude", value=loc.lon, format="%.6f").classes("w-full")
            elev_input = ui.number("Elevation (m)", value=loc.elevation_m).classes("w-full")
            region_input = ui.input("Avalanche Region", value=loc.region or "").classes("w-full")
            bergfex_input = ui.input(
                "Bergfex Slug",
                value=loc.bergfex_slug or "",
                placeholder="e.g. hochfuegen",
            ).classes("w-full")
            ui.label("→ From bergfex.com/skigebiet/[SLUG]/schneewerte").classes("text-xs text-gray-400")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                def make_save_edit_handler():
                    def do_save() -> None:
                        updated = SavedLocation(
                            id=loc.id,
                            name=name_input.value or loc.name,
                            lat=float(lat_input.value or loc.lat),
                            lon=float(lon_input.value or loc.lon),
                            elevation_m=int(elev_input.value or loc.elevation_m),
                            region=region_input.value or None,
                            bergfex_slug=bergfex_input.value or None,
                        )
                        save_location(updated)
                        ui.notify(f"'{updated.name}' updated", type="positive")
                        dialog.close()
                        refresh_list()
                    return do_save

                ui.button("Save", on_click=make_save_edit_handler()).props("color=primary")

        dialog.open()

    def render_content() -> None:
        """Render page content."""
        ui.label("Locations").classes("text-h4 mb-4")

        def show_add_dialog() -> None:
            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("New Location").classes("text-h6 mb-4")

                name_input = ui.input(
                    "Name",
                    placeholder="e.g. Stubaier Gletscher",
                ).classes("w-full")

                # DMS input from Google Maps
                ui.label("Coordinates from Google Maps:").classes("text-sm text-gray-600 mt-2")
                dms_input = ui.input(
                    "Google Maps Coordinates",
                    placeholder="47°16'11.1\"N 11°50'50.2\"E",
                ).classes("w-full")

                lat_input = ui.number(
                    "Latitude",
                    value=47.0,
                    format="%.6f",
                ).classes("w-full")
                lon_input = ui.number(
                    "Longitude",
                    value=11.0,
                    format="%.6f",
                ).classes("w-full")

                def convert_dms() -> None:
                    if not dms_input.value:
                        return
                    result = parse_dms_coordinates(dms_input.value)
                    if result:
                        lat_input.value = result[0]
                        lon_input.value = result[1]
                        ui.notify("Coordinates applied", type="positive")
                    else:
                        ui.notify("Invalid format", type="negative")

                dms_input.on("keydown.enter", lambda: convert_dms())
                dms_input.on("blur", lambda: convert_dms() if dms_input.value else None)

                elev_input = ui.number(
                    "Elevation (m)",
                    value=2000,
                ).classes("w-full")
                region_input = ui.input(
                    "Avalanche Region (optional)",
                    placeholder="e.g. AT-7",
                ).classes("w-full")
                bergfex_input = ui.input(
                    "Bergfex Slug (for snow depth)",
                    placeholder="e.g. hochfuegen, zillertal-arena",
                ).classes("w-full")
                ui.label("→ From bergfex.com/skigebiet/[SLUG]/schneewerte").classes("text-xs text-gray-400")

                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def make_save_handler():
                        def do_save() -> None:
                            if not name_input.value:
                                ui.notify("Name is required", type="negative")
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
                                bergfex_slug=bergfex_input.value or None,
                            )
                            save_location(location)
                            ui.notify(f"Location '{location.name}' saved", type="positive")
                            dialog.close()
                            refresh_list()
                        return do_save

                    ui.button("Save", on_click=make_save_handler()).props("color=primary")

            dialog.open()

        def make_add_handler():
            def do_add() -> None:
                show_add_dialog()
            return do_add

        ui.button(
            "New Location",
            on_click=make_add_handler(),
            icon="add_location",
        ).props("color=primary")

        # List existing locations
        locations = load_all_locations()

        if not locations:
            ui.label("No locations saved yet.").classes("text-gray-500 mt-4")
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
                            with ui.row().classes("gap-2"):
                                if loc.region:
                                    ui.badge(loc.region).props("color=blue")
                                if loc.bergfex_slug:
                                    ui.badge(f"bergfex: {loc.bergfex_slug}").props("color=green")

                        with ui.row().classes("gap-1"):
                            def make_edit_handler(location: SavedLocation):
                                def do_edit() -> None:
                                    show_edit_dialog(location)
                                return do_edit

                            ui.button(
                                icon="edit",
                                on_click=make_edit_handler(loc),
                            ).props("flat")

                            def make_delete_handler(lid: str, lname: str):
                                def do_delete() -> None:
                                    delete_location(lid)
                                    ui.notify(f"'{lname}' deleted", type="warning")
                                    refresh_list()
                                return do_delete

                            ui.button(
                                icon="delete",
                                on_click=make_delete_handler(loc.id, loc.name),
                            ).props("flat color=negative")

    render_content()
