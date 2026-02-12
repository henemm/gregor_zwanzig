"""
Trip management page with nested Stage/Waypoint editing.

Includes GPX import at stage level (Feature: gpx_import_in_trip_dialog).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from nicegui import ui

from app.loader import delete_trip, load_all_trips, save_trip
from app.models import EtappenConfig
from app.trip import Stage, Trip, Waypoint
from web.pages.gpx_upload import (
    compute_full_segmentation,
    process_gpx_upload,
    segments_to_trip,
)
from web.pages.weather_config import show_weather_config_dialog
from web.pages.report_config import make_report_config_handler
from web.utils import parse_dms_coordinates


# Default upload directory for GPX files imported via trip dialog
_GPX_UPLOAD_DIR = Path("data/users/default/gpx")


def gpx_to_stage_data(
    content: bytes,
    filename: str,
    stage_date: Optional[date] = None,
    start_hour: int = 8,
    upload_dir: Path = _GPX_UPLOAD_DIR,
) -> dict:
    """Parse GPX file and return a single stage dict for the trip dialog.

    1 GPX file = 1 Stage with N Waypoints.

    Args:
        content: Raw GPX file bytes.
        filename: Original filename (must end with .gpx).
        stage_date: Date for the stage (defaults to today).
        start_hour: Start hour of the hike (0-23).
        upload_dir: Directory to save the GPX file.

    Returns:
        Dict with keys: name, date, waypoints[]
    """
    track = process_gpx_upload(content, filename, upload_dir=upload_dir)
    d = stage_date or date.today()

    config = EtappenConfig()
    start_time = datetime(d.year, d.month, d.day, start_hour, 0, 0,
                          tzinfo=timezone.utc)
    segments = compute_full_segmentation(track, config, start_time)
    trip = segments_to_trip(segments, track, d)

    stage = trip.stages[0]  # 1 GPX = 1 Stage
    return {
        "name": stage.name,
        "date": stage.date.isoformat(),
        "waypoints": [
            {
                "id": wp.id,
                "name": wp.name,
                "lat": wp.lat,
                "lon": wp.lon,
                "elevation_m": wp.elevation_m,
            }
            for wp in stage.waypoints
        ],
    }


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


def render_trips() -> None:
    """Render the trips page."""
    render_header()

    container = ui.column().classes("w-full max-w-4xl mx-auto p-4")

    def refresh_list() -> None:
        """Refresh the trips list."""
        container.clear()
        with container:
            render_content()

    def render_content() -> None:
        """Render page content."""
        ui.label("Trips").classes("text-h4 mb-4")

        def show_add_dialog() -> None:
            # State for stages and waypoints
            stages_data: List[Dict[str, Any]] = []

            with ui.dialog() as dialog, ui.card().classes("w-full max-w-5xl"):
                with ui.scroll_area().classes("w-full").style("height: 80vh"):
                    ui.label("New Trip").classes("text-h6 mb-4")

                    name_input = ui.input(
                        "Trip Name",
                        placeholder="e.g. Stubai Ski Tour",
                    ).classes("w-full")

                    regions_input = ui.input(
                        "Avalanche Regions (comma-separated)",
                        placeholder="e.g. AT-7, AT-5",
                    ).classes("w-full")

                    ui.separator().classes("my-4")

                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label("Stages").classes("text-h6")

                        def make_add_stage_handler():
                            def do_add() -> None:
                                stage_idx = len(stages_data)
                                stage_date = date.today() + timedelta(days=stage_idx)
                                stages_data.append({
                                    "name": f"Stage {stage_idx + 1}",
                                    "date": stage_date.isoformat(),
                                    "waypoints": [],
                                })
                                stages_ui.refresh()
                            return do_add

                        with ui.row().classes("gap-2"):
                            ui.button("Add Stage", on_click=make_add_stage_handler(), icon="add").props("outline size=sm")

                            def make_add_stage_gpx_handler():
                                """Factory: add new stage from GPX file."""
                                async def do_upload(e):
                                    content = e.content.read()
                                    filename = e.name
                                    if stages_data:
                                        last_date = date.fromisoformat(stages_data[-1]["date"])
                                        stage_date = last_date + timedelta(days=1)
                                    else:
                                        stage_date = date.today()
                                    try:
                                        stage_dict = gpx_to_stage_data(content, filename, stage_date)
                                        stages_data.append(stage_dict)
                                        stages_ui.refresh()
                                        n_wps = len(stage_dict["waypoints"])
                                        ui.notify(f"Stage '{stage_dict['name']}' aus GPX: {n_wps} Waypoints",
                                                  type="positive")
                                    except Exception as err:
                                        ui.notify(f"GPX-Fehler: {err}", type="negative")
                                return do_upload

                            ui.upload(
                                on_upload=make_add_stage_gpx_handler(),
                                auto_upload=True,
                                max_files=1,
                                label="Stage from GPX",
                            ).props('accept=".gpx" flat dense').classes("w-44")

                    @ui.refreshable
                    def stages_ui() -> None:
                        if not stages_data:
                            ui.label("No stages yet. Click 'Add Stage' or upload GPX.").classes("text-gray-400 my-4")
                            return

                        for idx, stage in enumerate(stages_data):
                            with ui.card().classes("w-full mb-3 bg-gray-50"):
                                with ui.row().classes("w-full items-center justify-between"):
                                    ui.label(f"T{idx + 1}").classes("text-h6 text-blue-600")

                                    def make_remove_stage(i: int):
                                        def remove() -> None:
                                            stages_data.pop(i)
                                            stages_ui.refresh()
                                        return remove

                                    ui.button(icon="delete", on_click=make_remove_stage(idx)).props("flat dense color=negative")

                                with ui.row().classes("w-full gap-2 mb-2"):
                                    ui.input("Name", value=stage["name"]).classes("flex-1").bind_value(stage, "name")
                                    ui.input("Datum (YYYY-MM-DD)", value=stage["date"]).classes("w-40").bind_value(stage, "date")

                                ui.label("Waypoints:").classes("text-sm font-medium")

                                # Waypoints for this stage
                                for wp_idx, wp in enumerate(stage["waypoints"]):
                                    with ui.card().classes("w-full mb-2 p-2"):
                                        with ui.row().classes("w-full gap-2 items-center"):
                                            ui.label(wp["id"]).classes("w-10 font-bold text-green-600")
                                            ui.input("Name", value=wp["name"]).classes("flex-1").bind_value(wp, "name")
                                            ui.number("Elevation (m)", value=wp["elevation_m"]).classes("w-24").bind_value(wp, "elevation_m")

                                            def make_remove_wp(s: Dict, wi: int):
                                                def remove() -> None:
                                                    s["waypoints"].pop(wi)
                                                    stages_ui.refresh()
                                                return remove

                                            ui.button(icon="close", on_click=make_remove_wp(stage, wp_idx)).props("flat dense round size=sm color=negative")

                                        with ui.row().classes("w-full gap-2 items-center mt-1"):
                                            dms_input = ui.input("Google Maps Koordinaten", placeholder="47°16'11\"N 11°50'50\"E").classes("flex-1")
                                            lat_num = ui.number("Lat", value=wp["lat"], format="%.6f").classes("w-28").bind_value(wp, "lat")
                                            lon_num = ui.number("Lon", value=wp["lon"], format="%.6f").classes("w-28").bind_value(wp, "lon")

                                            def make_convert_dms(w: Dict, lat_field, lon_field, dms_field):
                                                def convert() -> None:
                                                    val = dms_field.value
                                                    if not val:
                                                        return
                                                    result = parse_dms_coordinates(val)
                                                    if result:
                                                        w["lat"] = result[0]
                                                        w["lon"] = result[1]
                                                        lat_field.value = result[0]
                                                        lon_field.value = result[1]
                                                        dms_field.value = ""
                                                        ui.notify(f"Koordinaten: {result[0]:.4f}, {result[1]:.4f}", type="positive")
                                                return convert

                                            ui.button("OK", on_click=make_convert_dms(wp, lat_num, lon_num, dms_input)).props("dense size=sm")

                                def make_add_wp(s: Dict):
                                    def add() -> None:
                                        wp_idx = len(s["waypoints"])
                                        s["waypoints"].append({
                                            "id": f"G{wp_idx + 1}",
                                            "name": f"Point {wp_idx + 1}",
                                            "lat": 47.0,
                                            "lon": 11.0,
                                            "elevation_m": 2000,
                                        })
                                        stages_ui.refresh()
                                    return add

                                with ui.row().classes("gap-2 mt-1 items-center"):
                                    ui.button("Add Waypoint", on_click=make_add_wp(stage), icon="add_location").props("flat dense size=sm")

                                    def make_import_wp_gpx_handler(stage_dict):
                                        """Factory: replace waypoints of existing stage from GPX."""
                                        async def do_upload(e):
                                            content = e.content.read()
                                            filename = e.name
                                            stage_date_val = date.fromisoformat(stage_dict["date"])
                                            try:
                                                imported = gpx_to_stage_data(content, filename, stage_date_val)
                                                stage_dict["waypoints"] = imported["waypoints"]
                                                if stage_dict["name"].startswith("Stage "):
                                                    stage_dict["name"] = imported["name"]
                                                stages_ui.refresh()
                                                ui.notify(f"GPX importiert: {len(imported['waypoints'])} Waypoints",
                                                          type="positive")
                                            except Exception as err:
                                                ui.notify(f"GPX-Fehler: {err}", type="negative")
                                        return do_upload

                                    ui.upload(
                                        on_upload=make_import_wp_gpx_handler(stage),
                                        auto_upload=True,
                                        max_files=1,
                                        label="GPX Import",
                                    ).props('accept=".gpx" flat dense').classes("w-36")

                    stages_ui()

                    ui.separator().classes("my-4")

                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        def make_save_handler():
                            def do_save() -> None:
                                if not name_input.value:
                                    ui.notify("Name is required", type="negative")
                                    return

                                if not stages_data:
                                    ui.notify("At least one stage required", type="negative")
                                    return

                                trip_id = name_input.value.lower().replace(" ", "-")
                                trip_id = "".join(c for c in trip_id if c.isalnum() or c == "-")

                                # Build stages
                                stages = []
                                for idx, sd in enumerate(stages_data):
                                    if not sd["waypoints"]:
                                        ui.notify(f"Stage {idx + 1} needs at least one waypoint", type="negative")
                                        return

                                    waypoints = [
                                        Waypoint(
                                            id=wp["id"],
                                            name=wp["name"],
                                            lat=float(wp["lat"]),
                                            lon=float(wp["lon"]),
                                            elevation_m=int(wp["elevation_m"]),
                                        )
                                        for wp in sd["waypoints"]
                                    ]

                                    try:
                                        stage_date = date.fromisoformat(sd["date"])
                                    except ValueError:
                                        ui.notify(f"Invalid date in Stage {idx + 1}", type="negative")
                                        return

                                    stages.append(Stage(
                                        id=f"T{idx + 1}",
                                        name=sd["name"],
                                        date=stage_date,
                                        waypoints=waypoints,
                                    ))

                                # Parse regions
                                regions = []
                                if regions_input.value:
                                    regions = [r.strip() for r in regions_input.value.split(",")]

                                trip = Trip(
                                    id=trip_id,
                                    name=name_input.value,
                                    stages=stages,
                                    avalanche_regions=regions,
                                )

                                save_trip(trip)
                                ui.notify(f"Trip '{trip.name}' saved", type="positive")
                                dialog.close()
                                refresh_list()
                            return do_save

                        ui.button("Save", on_click=make_save_handler()).props("color=primary")

            dialog.open()

        def show_edit_dialog(trip: Trip) -> None:
            """Edit dialog for existing trip."""
            # Convert Trip -> stages_data Dictionary
            stages_data: List[Dict[str, Any]] = []
            for stage in trip.stages:
                stage_dict = {
                    "name": stage.name,
                    "date": stage.date.isoformat(),
                    "waypoints": [
                        {
                            "id": wp.id,
                            "name": wp.name,
                            "lat": wp.lat,
                            "lon": wp.lon,
                            "elevation_m": wp.elevation_m,
                        }
                        for wp in stage.waypoints
                    ],
                }
                stages_data.append(stage_dict)

            with ui.dialog() as dialog, ui.card().classes("w-full max-w-5xl"):
                with ui.scroll_area().classes("w-full").style("height: 80vh"):
                    ui.label("Edit Trip").classes("text-h6 mb-4")

                    name_input = ui.input(
                        "Trip Name",
                        value=trip.name,
                        placeholder="e.g. Stubai Ski Tour",
                    ).classes("w-full")

                    regions_value = ", ".join(trip.avalanche_regions) if trip.avalanche_regions else ""
                    regions_input = ui.input(
                        "Avalanche Regions (comma-separated)",
                        value=regions_value,
                        placeholder="e.g. AT-7, AT-5",
                    ).classes("w-full")

                    ui.separator().classes("my-4")

                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label("Stages").classes("text-h6")

                        def make_add_stage_edit_handler():
                            def do_add() -> None:
                                stage_idx = len(stages_data)
                                stage_date = date.today() + timedelta(days=stage_idx)
                                stages_data.append({
                                    "name": f"Stage {stage_idx + 1}",
                                    "date": stage_date.isoformat(),
                                    "waypoints": [],
                                })
                                stages_ui_edit.refresh()
                            return do_add

                        with ui.row().classes("gap-2"):
                            ui.button("Add Stage", on_click=make_add_stage_edit_handler(), icon="add").props("outline size=sm")

                            def make_add_stage_gpx_edit_handler():
                                """Factory: add new stage from GPX file (edit dialog)."""
                                async def do_upload(e):
                                    content = e.content.read()
                                    filename = e.name
                                    if stages_data:
                                        last_date = date.fromisoformat(stages_data[-1]["date"])
                                        stage_date = last_date + timedelta(days=1)
                                    else:
                                        stage_date = date.today()
                                    try:
                                        stage_dict = gpx_to_stage_data(content, filename, stage_date)
                                        stages_data.append(stage_dict)
                                        stages_ui_edit.refresh()
                                        n_wps = len(stage_dict["waypoints"])
                                        ui.notify(f"Stage '{stage_dict['name']}' aus GPX: {n_wps} Waypoints",
                                                  type="positive")
                                    except Exception as err:
                                        ui.notify(f"GPX-Fehler: {err}", type="negative")
                                return do_upload

                            ui.upload(
                                on_upload=make_add_stage_gpx_edit_handler(),
                                auto_upload=True,
                                max_files=1,
                                label="Stage from GPX",
                            ).props('accept=".gpx" flat dense').classes("w-44")

                    @ui.refreshable
                    def stages_ui_edit() -> None:
                        if not stages_data:
                            ui.label("No stages yet. Click 'Add Stage'.").classes("text-gray-400 my-4")
                            return

                        for idx, stage in enumerate(stages_data):
                            with ui.card().classes("w-full mb-3 bg-gray-50"):
                                with ui.row().classes("w-full items-center justify-between"):
                                    ui.label(f"T{idx + 1}").classes("text-h6 text-blue-600")

                                    def make_remove_stage_edit(i: int):
                                        def remove() -> None:
                                            stages_data.pop(i)
                                            stages_ui_edit.refresh()
                                        return remove

                                    ui.button(icon="delete", on_click=make_remove_stage_edit(idx)).props("flat dense color=negative")

                                with ui.row().classes("w-full gap-2 mb-2"):
                                    ui.input("Name", value=stage["name"]).classes("flex-1").bind_value(stage, "name")
                                    ui.input("Datum (YYYY-MM-DD)", value=stage["date"]).classes("w-40").bind_value(stage, "date")

                                ui.label("Waypoints:").classes("text-sm font-medium")

                                # Waypoints for this stage
                                for wp_idx, wp in enumerate(stage["waypoints"]):
                                    with ui.card().classes("w-full mb-2 p-2"):
                                        with ui.row().classes("w-full gap-2 items-center"):
                                            ui.label(wp["id"]).classes("w-10 font-bold text-green-600")
                                            ui.input("Name", value=wp["name"]).classes("flex-1").bind_value(wp, "name")
                                            ui.number("Elevation (m)", value=wp["elevation_m"]).classes("w-24").bind_value(wp, "elevation_m")

                                            def make_remove_wp_edit(s: Dict, wi: int):
                                                def remove() -> None:
                                                    s["waypoints"].pop(wi)
                                                    stages_ui_edit.refresh()
                                                return remove

                                            ui.button(icon="close", on_click=make_remove_wp_edit(stage, wp_idx)).props("flat dense round size=sm color=negative")

                                        with ui.row().classes("w-full gap-2 items-center mt-1"):
                                            dms_input = ui.input("Google Maps Koordinaten", placeholder="47°16'11\"N 11°50'50\"E").classes("flex-1")
                                            lat_num = ui.number("Lat", value=wp["lat"], format="%.6f").classes("w-28").bind_value(wp, "lat")
                                            lon_num = ui.number("Lon", value=wp["lon"], format="%.6f").classes("w-28").bind_value(wp, "lon")

                                            def make_convert_dms_edit(w: Dict, lat_field, lon_field, dms_field):
                                                def convert() -> None:
                                                    val = dms_field.value
                                                    if not val:
                                                        return
                                                    result = parse_dms_coordinates(val)
                                                    if result:
                                                        w["lat"] = result[0]
                                                        w["lon"] = result[1]
                                                        lat_field.value = result[0]
                                                        lon_field.value = result[1]
                                                        dms_field.value = ""
                                                        ui.notify(f"Koordinaten: {result[0]:.4f}, {result[1]:.4f}", type="positive")
                                                return convert

                                            ui.button("OK", on_click=make_convert_dms_edit(wp, lat_num, lon_num, dms_input)).props("dense size=sm")

                                def make_add_wp_edit(s: Dict):
                                    def add() -> None:
                                        wp_idx = len(s["waypoints"])
                                        s["waypoints"].append({
                                            "id": f"G{wp_idx + 1}",
                                            "name": f"Point {wp_idx + 1}",
                                            "lat": 47.0,
                                            "lon": 11.0,
                                            "elevation_m": 2000,
                                        })
                                        stages_ui_edit.refresh()
                                    return add

                                with ui.row().classes("gap-2 mt-1 items-center"):
                                    ui.button("Add Waypoint", on_click=make_add_wp_edit(stage), icon="add_location").props("flat dense size=sm")

                                    def make_import_wp_gpx_edit_handler(stage_dict):
                                        """Factory: replace waypoints of existing stage from GPX (edit dialog)."""
                                        async def do_upload(e):
                                            content = e.content.read()
                                            filename = e.name
                                            stage_date_val = date.fromisoformat(stage_dict["date"])
                                            try:
                                                imported = gpx_to_stage_data(content, filename, stage_date_val)
                                                stage_dict["waypoints"] = imported["waypoints"]
                                                if stage_dict["name"].startswith("Stage "):
                                                    stage_dict["name"] = imported["name"]
                                                stages_ui_edit.refresh()
                                                ui.notify(f"GPX importiert: {len(imported['waypoints'])} Waypoints",
                                                          type="positive")
                                            except Exception as err:
                                                ui.notify(f"GPX-Fehler: {err}", type="negative")
                                        return do_upload

                                    ui.upload(
                                        on_upload=make_import_wp_gpx_edit_handler(stage),
                                        auto_upload=True,
                                        max_files=1,
                                        label="GPX Import",
                                    ).props('accept=".gpx" flat dense').classes("w-36")

                    stages_ui_edit()

                    ui.separator().classes("my-4")

                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        def make_save_edit_handler():
                            def do_save() -> None:
                                if not name_input.value:
                                    ui.notify("Name is required", type="negative")
                                    return

                                if not stages_data:
                                    ui.notify("At least one stage required", type="negative")
                                    return

                                # Trip ID remains unchanged!
                                trip_id = trip.id

                                # Build stages
                                stages = []
                                for idx, sd in enumerate(stages_data):
                                    if not sd["waypoints"]:
                                        ui.notify(f"Stage {idx + 1} needs at least one waypoint", type="negative")
                                        return

                                    waypoints = [
                                        Waypoint(
                                            id=wp["id"],
                                            name=wp["name"],
                                            lat=float(wp["lat"]),
                                            lon=float(wp["lon"]),
                                            elevation_m=int(wp["elevation_m"]),
                                        )
                                        for wp in sd["waypoints"]
                                    ]

                                    try:
                                        stage_date = date.fromisoformat(sd["date"])
                                    except ValueError:
                                        ui.notify(f"Invalid date in Stage {idx + 1}", type="negative")
                                        return

                                    stages.append(Stage(
                                        id=f"T{idx + 1}",
                                        name=sd["name"],
                                        date=stage_date,
                                        waypoints=waypoints,
                                    ))

                                # Parse regions
                                regions = []
                                if regions_input.value:
                                    regions = [r.strip() for r in regions_input.value.split(",")]

                                updated_trip = Trip(
                                    id=trip_id,
                                    name=name_input.value,
                                    stages=stages,
                                    avalanche_regions=regions,
                                )

                                save_trip(updated_trip)
                                ui.notify(f"Trip '{updated_trip.name}' updated", type="positive")
                                dialog.close()
                                refresh_list()
                            return do_save

                        ui.button("Save Changes", on_click=make_save_edit_handler()).props("color=primary")

            dialog.open()

        def make_add_handler():
            def do_add() -> None:
                show_add_dialog()
            return do_add

        ui.button(
            "New Trip",
            on_click=make_add_handler(),
            icon="route",
        ).props("color=primary")

        # List existing trips
        trips = load_all_trips()

        if not trips:
            ui.label("No trips saved yet.").classes("text-gray-500 mt-4")
        else:
            ui.label(f"{len(trips)} Trip(s)").classes("text-gray-500 mt-4 mb-2")

            for trip in trips:
                with ui.card().classes("w-full mb-2"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-0"):
                            ui.label(trip.name).classes("text-h6")
                            ui.label(
                                f"{len(trip.stages)} stage(s), "
                                f"{len(trip.all_waypoints)} waypoints"
                            ).classes("text-gray-500 text-sm")

                            with ui.row().classes("gap-1 mt-1"):
                                for region in trip.avalanche_regions:
                                    ui.badge(region).props("color=blue")

                        def make_edit_handler(t: Trip):
                            def do_edit() -> None:
                                show_edit_dialog(t)
                            return do_edit

                        def make_delete_handler(tid: str, tname: str):
                            def do_delete() -> None:
                                delete_trip(tid)
                                ui.notify(f"'{tname}' deleted", type="warning")
                                refresh_list()
                            return do_delete

                        def make_weather_config_handler(t: Trip):
                            """Factory for weather config handler - Safari compatible!"""
                            def do_show_weather_config() -> None:
                                show_weather_config_dialog(t)
                            return do_show_weather_config

                        with ui.row().classes("gap-1"):
                            ui.button(
                                "Wetter-Metriken",
                                icon="settings",
                                on_click=make_weather_config_handler(trip),
                            ).props("flat color=primary")
                            ui.button(
                                "Reports",
                                icon="schedule",
                                on_click=make_report_config_handler(trip),
                            ).props("flat color=primary")
                            ui.button(
                                icon="edit",
                                on_click=make_edit_handler(trip),
                            ).props("flat color=primary")
                            ui.button(
                                icon="delete",
                                on_click=make_delete_handler(trip.id, trip.name),
                            ).props("flat color=negative")

    render_content()
