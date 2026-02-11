"""
GPX Upload page (Feature 1.1 + 1.6 + 1.7).

Upload-Widget fuer GPX-Dateien mit Validierung, Track-Zusammenfassung,
Etappen-Konfiguration, Segment-Vorschau und Trip-Speicherung.

Specs: docs/specs/modules/gpx_upload.md, etappen_config.md
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import List, Optional

from nicegui import events, ui

from app.loader import save_trip
from app.models import EtappenConfig, GPXTrack, TripSegment
from app.trip import ActivityProfile, AggregationConfig, Stage, TimeWindow, Trip, Waypoint
from core.elevation_analysis import detect_waypoints
from core.gpx_parser import GPXParseError, parse_gpx
from core.hybrid_segmentation import optimize_segments
from core.segment_builder import build_segments


# Default upload directory
_DEFAULT_UPLOAD_DIR = Path("data/users/default/gpx")


def process_gpx_upload(
    content: bytes,
    filename: str,
    upload_dir: Path = _DEFAULT_UPLOAD_DIR,
) -> GPXTrack:
    """Validate, save, and parse an uploaded GPX file.

    Args:
        content: Raw file content bytes.
        filename: Original filename (must end with .gpx).
        upload_dir: Directory to save the file to.

    Returns:
        Parsed GPXTrack object.

    Raises:
        ValueError: If filename does not end with .gpx.
        GPXParseError: If GPX content is invalid.
    """
    if not filename.lower().endswith(".gpx"):
        raise ValueError(f"Nur .gpx Dateien erlaubt, nicht '{filename}'")

    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / filename

    saved_path.write_bytes(content)

    try:
        return parse_gpx(saved_path)
    except Exception:
        # Clean up saved file on parse error
        if saved_path.exists():
            saved_path.unlink()
        raise


def compute_full_segmentation(
    track: GPXTrack,
    config: EtappenConfig,
    start_time: datetime,
) -> List[TripSegment]:
    """Run complete segmentation pipeline.

    Combines build_segments (1.4) + detect_waypoints (1.3) +
    optimize_segments (1.5) into a single call.

    Args:
        track: Parsed GPX track.
        config: Hiking speed and duration configuration.
        start_time: Start time of the hike (UTC).

    Returns:
        List of optimized TripSegment objects.
    """
    segments = build_segments(track, config, start_time)
    waypoints = detect_waypoints(track)
    return optimize_segments(segments, waypoints, track, config)


def segments_to_trip(
    segments: List[TripSegment],
    track: GPXTrack,
    trip_date: date,
    trip_name: Optional[str] = None,
) -> Trip:
    """Convert computed segments to a Trip object for weather/reports.

    Creates N+1 Waypoints for N segments (one at each boundary).
    Each waypoint gets a TimeWindow so the trip_report_scheduler
    can create weather segments between consecutive waypoints.

    Args:
        segments: Computed TripSegment list.
        track: Original GPX track (for name).
        trip_date: Date of the hike.
        trip_name: Optional override for trip name.

    Returns:
        Trip object ready for save_trip().
    """
    name = trip_name or track.name
    trip_id = name.lower().replace(" ", "-")
    trip_id = "".join(c for c in trip_id if c.isalnum() or c == "-")

    waypoints: List[Waypoint] = []

    for i, seg in enumerate(segments):
        # Waypoint at segment start
        wp_name = f"Seg {seg.segment_id} Start"
        if i == 0:
            wp_name = "Start"
        elif seg.adjusted_to_waypoint and seg.waypoint:
            wp_name = seg.waypoint.name or seg.waypoint.type.value

        tw = TimeWindow(
            start=seg.start_time.time(),
            end=seg.start_time.time(),
        )
        waypoints.append(Waypoint(
            id=f"G{i + 1}",
            name=wp_name,
            lat=seg.start_point.lat,
            lon=seg.start_point.lon,
            elevation_m=int(seg.start_point.elevation_m),
            time_window=tw,
        ))

    # Last waypoint: end of last segment
    last = segments[-1]
    tw_end = TimeWindow(
        start=last.end_time.time(),
        end=last.end_time.time(),
    )
    waypoints.append(Waypoint(
        id=f"G{len(segments) + 1}",
        name="Ziel",
        lat=last.end_point.lat,
        lon=last.end_point.lon,
        elevation_m=int(last.end_point.elevation_m),
        time_window=tw_end,
    ))

    stage = Stage(
        id="T1",
        name=name,
        date=trip_date,
        waypoints=waypoints,
    )

    return Trip(
        id=trip_id,
        name=name,
        stages=[stage],
        aggregation=AggregationConfig.for_profile(ActivityProfile.SUMMER_TREKKING),
    )


def render_header() -> None:
    """Render navigation header."""
    with ui.header().classes("items-center justify-between"):
        ui.label("Gregor Zwanzig").classes("text-h6")
        with ui.row():
            ui.link("Dashboard", "/").classes("text-white mx-2")
            ui.link("Locations", "/locations").classes("text-white mx-2")
            ui.link("Trips", "/trips").classes("text-white mx-2")
            ui.link("GPX Upload", "/gpx-upload").classes("text-white mx-2")
            ui.link("Vergleich", "/compare").classes("text-white mx-2")
            ui.link("Subscriptions", "/subscriptions").classes("text-white mx-2")
            ui.link("Settings", "/settings").classes("text-white mx-2")


def render_gpx_upload() -> None:
    """Render the GPX upload page."""
    render_header()

    container = ui.column().classes("w-full max-w-4xl mx-auto p-4")

    with container:
        ui.label("GPX Upload").classes("text-h4 mb-4")
        ui.label(
            "GPX-Datei hochladen um Track zu analysieren und Segmente zu berechnen."
        ).classes("text-gray-600 mb-4")

        summary_container = ui.column().classes("w-full")

        def make_upload_handler():
            """Factory function (Safari compatibility)."""
            async def do_upload(e: events.UploadEventArguments):
                try:
                    content = await e.file.read()
                    filename = e.file.name
                    track = process_gpx_upload(content, filename)
                    _show_track_summary(summary_container, track, filename)
                    ui.notify(
                        f"GPX geladen: {track.name}",
                        type="positive",
                    )
                except ValueError as err:
                    ui.notify(str(err), type="negative")
                except GPXParseError as err:
                    ui.notify(f"Ungueltige GPX-Datei: {err}", type="negative")
            return do_upload

        ui.upload(
            on_upload=make_upload_handler(),
            max_file_size=10_000_000,
            max_files=1,
            auto_upload=True,
            label="GPX-Datei hochladen",
        ).props('accept=".gpx"').classes("w-full max-w-lg")


def _show_track_summary(
    container: ui.column, track: GPXTrack, filename: str,
) -> None:
    """Display parsed track summary in the container."""
    container.clear()
    with container:
        ui.separator().classes("my-4")
        ui.label("Track-Zusammenfassung").classes("text-h5 mb-2")

        with ui.card().classes("w-full"):
            with ui.grid(columns=2).classes("w-full gap-2"):
                ui.label("Name:").classes("font-bold")
                ui.label(track.name)

                ui.label("Datei:").classes("font-bold")
                ui.label(filename)

                ui.label("Distanz:").classes("font-bold")
                ui.label(f"{track.total_distance_km:.1f} km")

                ui.label("Aufstieg:").classes("font-bold")
                ui.label(f"{track.total_ascent_m:.0f} m")

                ui.label("Abstieg:").classes("font-bold")
                ui.label(f"{track.total_descent_m:.0f} m")

                ui.label("Trackpunkte:").classes("font-bold")
                ui.label(str(len(track.points)))

                ui.label("Waypoints:").classes("font-bold")
                ui.label(str(len(track.waypoints)))

        _show_config_and_segments(container, track)


def _show_config_and_segments(parent_container, track: GPXTrack) -> None:
    """Show configuration inputs and segment preview table."""
    ui.separator().classes("my-4")
    ui.label("Etappen-Konfiguration").classes("text-h5 mb-2")

    # Mutable state to hold computed segments for save button
    state = {"segments": None, "track": track}

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full gap-4 items-end flex-wrap"):
            date_input = ui.input(
                "Datum (YYYY-MM-DD)",
                value=date.today().isoformat(),
            ).classes("w-40")
            start_hour = ui.number(
                "Startzeit (Uhr)", value=8, min=0, max=23, step=1,
            ).classes("w-32")
            speed_flat = ui.number(
                "Gehgeschw. (km/h)", value=4.0, min=1.0, max=8.0, step=0.5,
            ).classes("w-40")
            speed_ascent = ui.number(
                "Aufstieg (Hm/h)", value=300, min=100, max=600, step=50,
            ).classes("w-36")
            speed_descent = ui.number(
                "Abstieg (Hm/h)", value=500, min=200, max=800, step=50,
            ).classes("w-36")

    segment_container = ui.column().classes("w-full mt-4")
    save_container = ui.column().classes("w-full mt-2")

    def make_compute_handler():
        """Factory function (Safari compatibility)."""
        def do_compute():
            config = EtappenConfig(
                speed_flat_kmh=float(speed_flat.value),
                speed_ascent_mh=float(speed_ascent.value),
                speed_descent_mh=float(speed_descent.value),
            )
            hour = int(start_hour.value)

            try:
                trip_date = date.fromisoformat(str(date_input.value))
            except (ValueError, TypeError):
                ui.notify("Ungueltiges Datum (YYYY-MM-DD)", type="negative")
                return

            start_time = datetime(
                trip_date.year, trip_date.month, trip_date.day,
                hour, 0, 0, tzinfo=timezone.utc,
            )
            segments = compute_full_segmentation(track, config, start_time)
            state["segments"] = segments
            state["date"] = trip_date
            _show_segment_table(segment_container, segments)
            _show_save_button(save_container, state)
            ui.notify(f"{len(segments)} Segmente berechnet", type="positive")
        return do_compute

    ui.button(
        "Segmente berechnen",
        on_click=make_compute_handler(),
        icon="calculate",
    ).props("color=primary").classes("mt-2")


def _show_segment_table(container, segments: List[TripSegment]) -> None:
    """Display segment preview as a table."""
    container.clear()
    with container:
        columns = [
            {"name": "nr", "label": "Seg", "field": "nr", "align": "center"},
            {"name": "start", "label": "Start", "field": "start"},
            {"name": "end", "label": "Ende", "field": "end"},
            {"name": "duration", "label": "Dauer", "field": "duration"},
            {"name": "distance", "label": "Distanz", "field": "distance"},
            {"name": "ascent", "label": "Aufstieg", "field": "ascent"},
            {"name": "descent", "label": "Abstieg", "field": "descent"},
            {"name": "waypoint", "label": "Waypoint", "field": "waypoint"},
        ]

        rows = []
        for s in segments:
            wp_label = ""
            if s.adjusted_to_waypoint and s.waypoint:
                wp_label = s.waypoint.name or s.waypoint.type.value
            rows.append({
                "nr": s.segment_id,
                "start": s.start_time.strftime("%H:%M"),
                "end": s.end_time.strftime("%H:%M"),
                "duration": f"{s.duration_hours:.1f}h",
                "distance": f"{s.distance_km:.1f} km",
                "ascent": f"{s.ascent_m:.0f} m",
                "descent": f"{s.descent_m:.0f} m",
                "waypoint": wp_label,
            })

        # Summary row
        rows.append({
            "nr": "Σ",
            "start": "",
            "end": "",
            "duration": f"{sum(s.duration_hours for s in segments):.1f}h",
            "distance": f"{sum(s.distance_km for s in segments):.1f} km",
            "ascent": f"{sum(s.ascent_m for s in segments):.0f} m",
            "descent": f"{sum(s.descent_m for s in segments):.0f} m",
            "waypoint": "",
        })

        ui.table(
            columns=columns,
            rows=rows,
            row_key="nr",
        ).classes("w-full")


def _show_save_button(container, state: dict) -> None:
    """Show 'Als Trip speichern' button after segment computation."""
    container.clear()
    with container:
        def make_save_handler():
            """Factory function (Safari compatibility)."""
            def do_save():
                segments = state.get("segments")
                track = state.get("track")
                trip_date = state.get("date")

                if not segments or not track or not trip_date:
                    ui.notify("Bitte zuerst Segmente berechnen", type="negative")
                    return

                trip = segments_to_trip(segments, track, trip_date)
                save_trip(trip)
                ui.notify(
                    f"Trip '{trip.name}' gespeichert mit "
                    f"{len(trip.all_waypoints)} Waypoints. "
                    f"Oeffne /trips fuer Wetter & Reports.",
                    type="positive",
                )
            return do_save

        ui.button(
            "Als Trip speichern",
            on_click=make_save_handler(),
            icon="save",
        ).props("color=positive").classes("mt-2")
