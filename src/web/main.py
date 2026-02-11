"""
Main entry point for the Gregor Zwanzig Web UI.

Run with: python -m src.web.main
"""
from __future__ import annotations

from pathlib import Path

from nicegui import app, ui

# Data directory for user files
DATA_DIR = Path("data/users/default")


def ensure_data_dirs() -> None:
    """Create data directories if they don't exist."""
    (DATA_DIR / "trips").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "locations").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "gpx").mkdir(parents=True, exist_ok=True)


@ui.page("/")
def dashboard_page() -> None:
    """Dashboard with overview and quick links."""
    from web.pages.dashboard import render_dashboard
    render_dashboard()


@ui.page("/locations")
def locations_page() -> None:
    """Location management page."""
    from web.pages.locations import render_locations
    render_locations()


@ui.page("/trips")
def trips_page() -> None:
    """Trip management page."""
    from web.pages.trips import render_trips
    render_trips()


@ui.page("/compare")
def compare_page() -> None:
    """Forecast comparison page."""
    from web.pages.compare import render_compare
    render_compare()


@ui.page("/settings")
def settings_page() -> None:
    """Settings page."""
    from web.pages.settings import render_settings
    render_settings()


@ui.page("/subscriptions")
def subscriptions_page() -> None:
    """Compare subscriptions management page."""
    from web.pages.subscriptions import render_subscriptions
    render_subscriptions()


@ui.page("/gpx-upload")
def gpx_upload_page() -> None:
    """GPX upload and track analysis page."""
    from web.pages.gpx_upload import render_gpx_upload
    render_gpx_upload()


def create_header() -> None:
    """Create consistent navigation header."""
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


# Prevent Safari from caching HTML pages (fixes dead WebSocket on revisit)
# See: https://github.com/zauberzeug/nicegui/issues/5468
@app.middleware("http")
async def no_cache_headers(request, call_next):
    response = await call_next(request)
    if "text/html" in response.headers.get("content-type", ""):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Register startup handlers
app.on_startup(ensure_data_dirs)

# Initialize background scheduler for subscriptions
from web.scheduler import init_scheduler, shutdown_scheduler
app.on_startup(init_scheduler)
app.on_shutdown(shutdown_scheduler)


def run() -> None:
    """Start the web UI server."""
    ui.run(
        title="Gregor Zwanzig",
        port=8080,
        reload=False,
        show=True,
        # Keep session alive for 4 hours when tab is in background
        # Default is 3 seconds which causes reset when switching apps
        reconnect_timeout=14400,
    )


if __name__ == "__main__":
    run()
