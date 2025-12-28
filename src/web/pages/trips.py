"""
Trip management page with nested Stage/Waypoint editing.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List

from nicegui import ui

from app.loader import delete_trip, load_all_trips, save_trip
from app.trip import Stage, Trip, Waypoint


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

            with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl"):
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
                ui.label("Etappen").classes("text-h6")

                stages_container = ui.column().classes("w-full")

                def add_stage() -> None:
                    stage_idx = len(stages_data)
                    stage_date = date.today() + timedelta(days=stage_idx)
                    stage_data = {
                        "name": f"Etappe {stage_idx + 1}",
                        "date": stage_date.isoformat(),
                        "waypoints": [],
                    }
                    stages_data.append(stage_data)
                    render_stages()

                def render_stages() -> None:
                    stages_container.clear()
                    with stages_container:
                        for idx, stage in enumerate(stages_data):
                            render_stage_card(idx, stage)

                def render_stage_card(idx: int, stage: Dict[str, Any]) -> None:
                    with ui.card().classes("w-full mb-2 bg-gray-50"):
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label(f"T{idx + 1}").classes("text-h6")

                            def remove_stage(i: int = idx) -> None:
                                stages_data.pop(i)
                                render_stages()

                            ui.button(
                                icon="delete",
                                on_click=remove_stage,
                            ).props("flat dense color=negative")

                        with ui.row().classes("w-full gap-2"):
                            stage_name = ui.input(
                                "Name",
                                value=stage["name"],
                            ).classes("flex-1")
                            stage_name.on_value_change(
                                lambda e, s=stage: s.update({"name": e.value})
                            )

                            stage_date_input = ui.input(
                                "Datum",
                                value=stage["date"],
                            ).classes("w-32")
                            stage_date_input.on_value_change(
                                lambda e, s=stage: s.update({"date": e.value})
                            )

                        # Waypoints
                        ui.label("Wegpunkte").classes("text-sm mt-2")
                        wp_container = ui.column().classes("w-full pl-4")

                        def add_waypoint(s: Dict = stage) -> None:
                            wp_idx = len(s["waypoints"])
                            s["waypoints"].append({
                                "id": f"G{wp_idx + 1}",
                                "name": f"Punkt {wp_idx + 1}",
                                "lat": 47.0,
                                "lon": 11.0,
                                "elevation_m": 2000,
                            })
                            render_stages()

                        with wp_container:
                            for wp_idx, wp in enumerate(stage["waypoints"]):
                                with ui.row().classes("w-full gap-2 items-center"):
                                    ui.label(wp["id"]).classes("w-8")

                                    wp_name = ui.input(
                                        "Name",
                                        value=wp["name"],
                                    ).classes("flex-1")
                                    wp_name.on_value_change(
                                        lambda e, w=wp: w.update({"name": e.value})
                                    )

                                    wp_lat = ui.number(
                                        "Lat",
                                        value=wp["lat"],
                                        format="%.4f",
                                    ).classes("w-24")
                                    wp_lat.on_value_change(
                                        lambda e, w=wp: w.update({"lat": float(e.value) if e.value else 0})
                                    )

                                    wp_lon = ui.number(
                                        "Lon",
                                        value=wp["lon"],
                                        format="%.4f",
                                    ).classes("w-24")
                                    wp_lon.on_value_change(
                                        lambda e, w=wp: w.update({"lon": float(e.value) if e.value else 0})
                                    )

                                    wp_elev = ui.number(
                                        "Höhe",
                                        value=wp["elevation_m"],
                                    ).classes("w-20")
                                    wp_elev.on_value_change(
                                        lambda e, w=wp: w.update({"elevation_m": int(e.value) if e.value else 0})
                                    )

                                    def remove_wp(s: Dict = stage, wi: int = wp_idx) -> None:
                                        s["waypoints"].pop(wi)
                                        render_stages()

                                    ui.button(
                                        icon="close",
                                        on_click=remove_wp,
                                    ).props("flat dense round size=sm")

                        ui.button(
                            "Wegpunkt hinzufügen",
                            on_click=add_waypoint,
                            icon="add",
                        ).props("flat dense size=sm").classes("mt-1")

                ui.button(
                    "Etappe hinzufügen",
                    on_click=add_stage,
                    icon="add",
                ).props("outline").classes("mt-2")

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
                                ui.notify(
                                    f"Etappe {idx + 1} braucht mindestens einen Wegpunkt",
                                    type="negative",
                                )
                                return

                            waypoints = [
                                Waypoint(
                                    id=wp["id"],
                                    name=wp["name"],
                                    lat=wp["lat"],
                                    lon=wp["lon"],
                                    elevation_m=wp["elevation_m"],
                                )
                                for wp in sd["waypoints"]
                            ]

                            stages.append(Stage(
                                id=f"T{idx + 1}",
                                name=sd["name"],
                                date=date.fromisoformat(sd["date"]),
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
