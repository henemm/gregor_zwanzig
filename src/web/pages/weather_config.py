"""
Weather Config UI - Feature 2.6 (Story 2)

WebUI page for configuring which weather metrics are displayed per trip.
Users can select from 13 available metrics (8 basis + 5 extended) via checkbox interface.

SPEC: docs/specs/modules/weather_config.md v1.0
"""
from datetime import datetime, timezone
from typing import Dict

from pathlib import Path

from nicegui import ui

from app.loader import get_trips_dir, load_trip, save_trip
from app.models import TripWeatherConfig
from app.trip import Trip


# Metric definitions
BASIS_METRICS = {
    "temp_min_c": "Temperatur (Min)",
    "temp_max_c": "Temperatur (Max)",
    "temp_avg_c": "Temperatur (Durchschnitt)",
    "wind_max_kmh": "Wind (Max)",
    "gust_max_kmh": "Böen (Max)",
    "precip_sum_mm": "Niederschlag (Summe)",
    "cloud_avg_pct": "Bewölkung (Durchschnitt)",
    "humidity_avg_pct": "Luftfeuchtigkeit (Durchschnitt)",
}

EXTENDED_METRICS = {
    "thunder_level_max": "Gewitter (Max Stufe)",
    "visibility_min_m": "Sichtweite (Min)",
    "dewpoint_avg_c": "Taupunkt (Durchschnitt)",
    "pressure_avg_hpa": "Luftdruck (Durchschnitt)",
    "wind_chill_min_c": "Windchill (Min)",
}


def show_weather_config_dialog(trip: Trip, user_id: str = "default") -> None:
    """
    Show weather metrics configuration dialog.

    Factory Pattern (Safari compatible):
    - All handlers use make_<action>_handler() pattern
    - Closures bind immutable trip_id, not mutable checkbox dict

    Args:
        trip: Trip to configure weather metrics for
        user_id: User identifier for saving
    """
    with ui.dialog() as dialog, ui.card():
        ui.label("Wetter-Metriken konfigurieren").classes("text-h6")

        # Get current config or use defaults
        current_metrics = set()
        if trip.weather_config:
            current_metrics = set(trip.weather_config.enabled_metrics)
        else:
            # Default: all basis metrics checked
            current_metrics = set(BASIS_METRICS.keys())

        # Checkboxes dictionary
        checkboxes: Dict[str, ui.checkbox] = {}

        # Basis metrics section
        ui.label("Basis-Metriken").classes("text-subtitle1 q-mt-md")
        for metric_id, metric_label in BASIS_METRICS.items():
            checkboxes[metric_id] = ui.checkbox(
                metric_label,
                value=(metric_id in current_metrics)
            )

        # Extended metrics section
        ui.label("Erweiterte Metriken").classes("text-subtitle1 q-mt-md")
        for metric_id, metric_label in EXTENDED_METRICS.items():
            checkboxes[metric_id] = ui.checkbox(
                metric_label,
                value=(metric_id in current_metrics)
            )

        # Buttons (Factory Pattern!)
        with ui.row():
            ui.button("Abbrechen", on_click=dialog.close)
            ui.button(
                "Speichern",
                on_click=make_save_handler(trip.id, checkboxes, dialog, user_id)
            )

    dialog.open()


def make_save_handler(trip_id: str, checkboxes: Dict[str, ui.checkbox], dialog, user_id: str):
    """
    Factory for save handler - Safari compatible!

    Pattern: make_<action>_handler() returns do_<action>()

    Args:
        trip_id: Immutable trip ID (safe for closure)
        checkboxes: Checkbox dictionary (captured at factory time)
        dialog: Dialog to close after save
        user_id: User identifier for loading/saving

    Returns:
        Save handler function
    """
    def do_save():
        # Collect selected metrics
        selected = [name for name, cb in checkboxes.items() if cb.value]

        # Validation: Minimum 1 metric
        if len(selected) == 0:
            ui.notify(
                "Mindestens 1 Metrik muss ausgewählt sein!",
                color="negative"
            )
            return

        # Load trip, update config, save
        trip_path = get_trips_dir(user_id) / f"{trip_id}.json"
        trip = load_trip(trip_path)
        trip.weather_config = TripWeatherConfig(
            trip_id=trip_id,
            enabled_metrics=selected,
            updated_at=datetime.now(timezone.utc)
        )
        save_trip(trip, user_id=user_id)

        # Success feedback
        ui.notify(
            f"{len(selected)} Metriken gespeichert!",
            color="positive"
        )
        dialog.close()

    return do_save
