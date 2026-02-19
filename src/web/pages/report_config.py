"""
Report Config UI - Feature 3.5 (Story 3)

WebUI dialog for configuring trip report settings:
- Schedule times (morning/evening)
- Channels (email/SMS)
- Alert thresholds

IMPORTANT: Safari Compatibility
- All ui.button() handlers MUST use factory pattern
- Pattern: make_<action>_handler() returns do_<action>()
- See: docs/reference/nicegui_best_practices.md

SPEC: docs/specs/modules/report_config.md v1.0
"""
from datetime import datetime, time, timezone

from nicegui import ui

from app.loader import get_trips_dir, load_trip, save_trip
from app.models import TripReportConfig
from app.trip import Trip


def show_report_config_dialog(trip: Trip, user_id: str = "default") -> None:
    """
    Show report configuration dialog.

    Factory Pattern (Safari compatible):
    - All handlers use make_<action>_handler() pattern

    Args:
        trip: Trip to configure reports for
        user_id: User identifier for saving
    """
    with ui.dialog() as dialog, ui.card().classes("w-full max-w-lg"):
        ui.label("Report-Einstellungen").classes("text-h6")

        # Load fresh from disk to avoid stale in-memory state
        trip_path = get_trips_dir(user_id) / f"{trip.id}.json"
        fresh_trip = load_trip(trip_path)
        config = fresh_trip.report_config or TripReportConfig(trip_id=trip.id)

        # Schedule Section
        ui.label("Zeitplan").classes("text-subtitle1 q-mt-md")

        with ui.row().classes("w-full gap-4"):
            with ui.column():
                ui.label("Morgen").classes("text-caption")
                morning_input = ui.time(
                    value=config.morning_time.strftime("%H:%M")
                ).classes("w-32")
            with ui.column():
                ui.label("Abend").classes("text-caption")
                evening_input = ui.time(
                    value=config.evening_time.strftime("%H:%M")
                ).classes("w-32")

        # Channels Section
        ui.label("Kanäle").classes("text-subtitle1 q-mt-md")

        email_checkbox = ui.checkbox("E-Mail senden", value=config.send_email)
        sms_checkbox = ui.checkbox("SMS senden (coming soon)", value=config.send_sms)

        # Alerts Section
        ui.label("Wetter-Alerts").classes("text-subtitle1 q-mt-md")

        alert_checkbox = ui.checkbox(
            "Bei Änderungen benachrichtigen",
            value=config.alert_on_changes
        )

        ui.label(
            "Alert-Schwellen pro Metrik unter 'Wetter-Metriken' konfigurieren."
        ).classes("text-caption text-grey q-mt-sm")

        # Wind-Exposition Section (F7c)
        ui.label("Wind-Exposition").classes("text-subtitle1 q-mt-md")

        elev_input = ui.number(
            label="Wind-Exposition ab Höhe (m)",
            value=config.wind_exposition_min_elevation_m,
            placeholder="1500",
            min=500,
            max=4000,
            step=100,
        ).classes("w-48")

        # Buttons (Factory Pattern!)
        with ui.row().classes("q-mt-md"):
            ui.button("Abbrechen", on_click=dialog.close)
            ui.button(
                "Speichern",
                on_click=make_save_handler(
                    trip.id,
                    morning_input,
                    evening_input,
                    email_checkbox,
                    sms_checkbox,
                    alert_checkbox,
                    elev_input,
                    dialog,
                    user_id
                )
            ).props("color=primary")

    dialog.open()


def make_save_handler(
    trip_id: str,
    morning_input,
    evening_input,
    email_checkbox,
    sms_checkbox,
    alert_checkbox,
    elev_input,
    dialog,
    user_id: str
):
    """
    Factory for save handler - Safari compatible!

    Pattern: make_<action>_handler() returns do_<action>()

    Args:
        trip_id: Immutable trip ID (safe for closure)
        morning_input: Morning time input
        evening_input: Evening time input
        email_checkbox: Email channel checkbox
        sms_checkbox: SMS channel checkbox
        alert_checkbox: Alert enabled checkbox
        elev_input: Wind exposition min elevation input (F7c)
        dialog: Dialog to close after save
        user_id: User identifier for loading/saving

    Returns:
        Save handler function
    """
    def do_save():
        # Parse times
        morning = time.fromisoformat(morning_input.value)
        evening = time.fromisoformat(evening_input.value)

        # Validation: morning < evening
        if morning >= evening:
            ui.notify(
                "Morgen-Zeit muss vor Abend-Zeit liegen!",
                color="negative"
            )
            return

        # Load existing config to preserve threshold values (deprecated but kept for compatibility)
        trip_path = get_trips_dir(user_id) / f"{trip_id}.json"
        existing_trip = load_trip(trip_path)
        old_rc = existing_trip.report_config

        # Wind exposition elevation (F7c): None if empty
        min_elev = float(elev_input.value) if elev_input.value else None

        # Build config (preserve legacy threshold fields from existing config)
        config = TripReportConfig(
            trip_id=trip_id,
            enabled=True,
            morning_time=morning,
            evening_time=evening,
            send_email=email_checkbox.value,
            send_sms=sms_checkbox.value,
            alert_on_changes=alert_checkbox.value,
            change_threshold_temp_c=old_rc.change_threshold_temp_c if old_rc else 5.0,
            change_threshold_wind_kmh=old_rc.change_threshold_wind_kmh if old_rc else 20.0,
            change_threshold_precip_mm=old_rc.change_threshold_precip_mm if old_rc else 10.0,
            wind_exposition_min_elevation_m=min_elev,
            updated_at=datetime.now(timezone.utc),
        )

        # Update and save
        existing_trip.report_config = config
        save_trip(existing_trip, user_id=user_id)

        # Success feedback
        ui.notify("Report-Einstellungen gespeichert!", color="positive")
        dialog.close()

    return do_save


def make_report_config_handler(trip: Trip, user_id: str = "default"):
    """
    Factory for report config button - Safari compatible!

    Use this in trips.py to open the config dialog.

    Args:
        trip: Trip to configure
        user_id: User identifier

    Returns:
        Handler function to open dialog
    """
    def do_open():
        show_report_config_dialog(trip, user_id)
    return do_open
