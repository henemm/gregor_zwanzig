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

        # Get current config or defaults
        config = trip.report_config or TripReportConfig(trip_id=trip.id)

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

        ui.label("Schwellenwerte für Alerts:").classes("text-subtitle2 q-mt-sm")

        # Temperature threshold
        with ui.row().classes("w-full items-center"):
            ui.label("Temperatur:").classes("w-24")
            temp_slider = ui.slider(
                min=1, max=10, step=1, value=config.change_threshold_temp_c
            ).classes("w-40")
            temp_label = ui.label(f"{config.change_threshold_temp_c:.0f}°C")
            temp_slider.on("update:model-value", lambda e: temp_label.set_text(f"{e.args:.0f}°C"))

        # Wind threshold
        with ui.row().classes("w-full items-center"):
            ui.label("Wind:").classes("w-24")
            wind_slider = ui.slider(
                min=5, max=50, step=5, value=config.change_threshold_wind_kmh
            ).classes("w-40")
            wind_label = ui.label(f"{config.change_threshold_wind_kmh:.0f} km/h")
            wind_slider.on("update:model-value", lambda e: wind_label.set_text(f"{e.args:.0f} km/h"))

        # Precipitation threshold
        with ui.row().classes("w-full items-center"):
            ui.label("Niederschlag:").classes("w-24")
            precip_slider = ui.slider(
                min=1, max=20, step=1, value=config.change_threshold_precip_mm
            ).classes("w-40")
            precip_label = ui.label(f"{config.change_threshold_precip_mm:.0f} mm")
            precip_slider.on("update:model-value", lambda e: precip_label.set_text(f"{e.args:.0f} mm"))

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
                    temp_slider,
                    wind_slider,
                    precip_slider,
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
    temp_slider,
    wind_slider,
    precip_slider,
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
        temp_slider: Temperature threshold slider
        wind_slider: Wind threshold slider
        precip_slider: Precipitation threshold slider
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

        # Build config
        config = TripReportConfig(
            trip_id=trip_id,
            enabled=True,
            morning_time=morning,
            evening_time=evening,
            send_email=email_checkbox.value,
            send_sms=sms_checkbox.value,
            alert_on_changes=alert_checkbox.value,
            change_threshold_temp_c=float(temp_slider.value),
            change_threshold_wind_kmh=float(wind_slider.value),
            change_threshold_precip_mm=float(precip_slider.value),
            updated_at=datetime.now(timezone.utc),
        )

        # Load trip, update, save
        trip_path = get_trips_dir(user_id) / f"{trip_id}.json"
        trip = load_trip(trip_path)
        trip.report_config = config
        save_trip(trip, user_id=user_id)

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
