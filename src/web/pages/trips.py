"""
Trip management page with nested Stage/Waypoint editing.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

from nicegui import ui

from app.loader import delete_trip, load_all_trips, save_trip
from app.trip import Stage, Trip, Waypoint
from web.utils import parse_dms_coordinates


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

            with ui.dialog() as dialog, ui.card().classes("w-full max-w-3xl max-h-screen"):
                with ui.scroll_area().classes("w-full"):
                    ui.label("Neuer Trip").classes("text-h6 mb-4")

                    name_input = ui.input(
                        "Trip Name",
                        placeholder="z.B. Stubaier Skitour",
                    ).classes("w-full")

                    regions_input = ui.input(
                        "Lawinenregionen (kommagetrennt)",
                        placeholder="z.B. AT-7, AT-5",
                    ).classes("w-full")

                    ui.separator().classes("my-4")

                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label("Etappen").classes("text-h6")

                        def add_stage() -> None:
                            stage_idx = len(stages_data)
                            stage_date = date.today() + timedelta(days=stage_idx)
                            stages_data.append({
                                "name": f"Etappe {stage_idx + 1}",
                                "date": stage_date.isoformat(),
                                "waypoints": [],
                            })
                            stages_ui.refresh()

                        ui.button("Etappe hinzufügen", on_click=add_stage, icon="add").props("outline size=sm")

                    @ui.refreshable
                    def stages_ui() -> None:
                        if not stages_data:
                            ui.label("Noch keine Etappen. Klicke 'Etappe hinzufügen'.").classes("text-gray-400 my-4")
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

                                ui.label("Wegpunkte:").classes("text-sm font-medium")

                                # Waypoints for this stage
                                for wp_idx, wp in enumerate(stage["waypoints"]):
                                    with ui.card().classes("w-full mb-2 p-2"):
                                        with ui.row().classes("w-full gap-2 items-center"):
                                            ui.label(wp["id"]).classes("w-10 font-bold text-green-600")
                                            ui.input("Name", value=wp["name"]).classes("flex-1").bind_value(wp, "name")
                                            ui.number("Höhe (m)", value=wp["elevation_m"]).classes("w-24").bind_value(wp, "elevation_m")

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
                                            "name": f"Punkt {wp_idx + 1}",
                                            "lat": 47.0,
                                            "lon": 11.0,
                                            "elevation_m": 2000,
                                        })
                                        stages_ui.refresh()
                                    return add

                                ui.button("Wegpunkt hinzufügen", on_click=make_add_wp(stage), icon="add_location").props("flat dense size=sm").classes("mt-1")

                    stages_ui()

                    ui.separator().classes("my-4")

                    with ui.row().classes("w-full justify-end gap-2"):
                        ui.button("Abbrechen", on_click=dialog.close).props("flat")

                        def save() -> None:
                            if not name_input.value:
                                ui.notify("Name ist erforderlich", type="negative")
                                return

                            if not stages_data:
                                ui.notify("Mindestens eine Etappe erforderlich", type="negative")
                                return

                            trip_id = name_input.value.lower().replace(" ", "-")
                            trip_id = "".join(c for c in trip_id if c.isalnum() or c == "-")

                            # Build stages
                            stages = []
                            for idx, sd in enumerate(stages_data):
                                if not sd["waypoints"]:
                                    ui.notify(f"Etappe {idx + 1} braucht mindestens einen Wegpunkt", type="negative")
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
                                    ui.notify(f"Ungültiges Datum in Etappe {idx + 1}", type="negative")
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
                            ui.notify(f"Trip '{trip.name}' gespeichert", type="positive")
                            dialog.close()
                            refresh_list()

                        ui.button("Speichern", on_click=save).props("color=primary")

            dialog.open()

        ui.button(
            "Neuer Trip",
            on_click=show_add_dialog,
            icon="route",
        ).props("color=primary")

        # List existing trips
        trips = load_all_trips()

        if not trips:
            ui.label("Noch keine Trips gespeichert.").classes("text-gray-500 mt-4")
        else:
            ui.label(f"{len(trips)} Trip(s)").classes("text-gray-500 mt-4 mb-2")

            for trip in trips:
                with ui.card().classes("w-full mb-2"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-0"):
                            ui.label(trip.name).classes("text-h6")
                            ui.label(
                                f"{len(trip.stages)} Etappe(n), "
                                f"{len(trip.all_waypoints)} Wegpunkte"
                            ).classes("text-gray-500 text-sm")

                            with ui.row().classes("gap-1 mt-1"):
                                for region in trip.avalanche_regions:
                                    ui.badge(region).props("color=blue")

                        def make_delete_handler(tid: str, tname: str):
                            def do_delete() -> None:
                                delete_trip(tid)
                                ui.notify(f"'{tname}' gelöscht", type="warning")
                                refresh_list()
                            return do_delete

                        ui.button(
                            icon="delete",
                            on_click=make_delete_handler(trip.id, trip.name),
                        ).props("flat color=negative")

    render_content()
