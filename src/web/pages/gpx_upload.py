"""
GPX Upload page (Feature 1.1).

Upload-Widget fuer GPX-Dateien mit Validierung und Track-Zusammenfassung.

Spec: docs/specs/modules/gpx_upload.md
"""
from __future__ import annotations

from pathlib import Path

from nicegui import events, ui

from app.models import GPXTrack
from core.gpx_parser import GPXParseError, parse_gpx


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


def render_gpx_upload() -> None:
    """Render the GPX upload page."""
    from web.main import create_header
    create_header()

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
                    content = e.content.read()
                    track = process_gpx_upload(content, e.name)
                    _show_track_summary(summary_container, track, e.name)
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

        ui.button(
            "Weiter zur Konfiguration",
            icon="arrow_forward",
        ).props("color=primary disable").classes("mt-4")
