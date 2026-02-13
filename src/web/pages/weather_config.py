"""
Weather Config UI - Feature 2.6 Phase 2 (Story 2)

API-aware weather metrics configuration dialog.
Shows metrics from MetricCatalog grouped by category with provider-based availability.

IMPORTANT: Safari Compatibility
- All ui.button() handlers MUST use factory pattern
- Pattern: make_<action>_handler() returns do_<action>()
- See: docs/reference/nicegui_best_practices.md

SPEC: docs/specs/modules/weather_config.md v2.1
"""
from datetime import datetime, timezone

from nicegui import ui

from app.loader import get_trips_dir, load_trip, save_trip
from app.metric_catalog import (
    get_all_metrics,
    get_metrics_by_category,
    build_default_display_config,
)
from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from app.trip import Trip


# Category display order and German labels
CATEGORY_ORDER = ["temperature", "wind", "precipitation", "atmosphere", "winter"]

CATEGORY_LABELS = {
    "temperature": "Temperatur",
    "wind": "Wind",
    "precipitation": "Niederschlag",
    "atmosphere": "Atmosphäre",
    "winter": "Winter",
}

# Aggregation UI labels
AGG_LABELS = {"min": "Min", "max": "Max", "avg": "Avg", "sum": "Sum"}


def get_available_providers_for_trip(trip: Trip) -> set[str]:
    """
    Detect which weather providers can serve this trip based on waypoint coordinates.

    - OpenMeteo: Always available (global coverage)
    - GeoSphere: Available if ANY waypoint is in Austria bounding box
      (46.0-49.0 N, 9.5-17.0 E)

    Args:
        trip: Trip with stages containing waypoints

    Returns:
        Set of provider names, e.g. {"openmeteo"} or {"openmeteo", "geosphere"}
    """
    providers = {"openmeteo"}

    for stage in trip.stages:
        for waypoint in stage.waypoints:
            if 46.0 <= waypoint.lat <= 49.0 and 9.5 <= waypoint.lon <= 17.0:
                providers.add("geosphere")
                return providers  # Early exit

    return providers


def show_weather_config_dialog(trip: Trip, user_id: str = "default") -> None:
    """
    Show API-aware weather metrics configuration dialog.

    Features:
    - Provider detection from trip waypoints
    - Grouped metrics by category (Temperatur, Wind, etc.)
    - Grayed-out unavailable metrics with tooltip
    - Per-metric aggregation selection (Min/Max/Avg/Sum)
    - Saves as UnifiedWeatherDisplayConfig

    Safari Compatible:
    - All handlers use make_<action>_handler() factory pattern

    Args:
        trip: Trip to configure weather metrics for
        user_id: User identifier for saving (default: "default")
    """
    # Reload trip from disk to get latest saved config
    trip_path = get_trips_dir(user_id) / f"{trip.id}.json"
    if trip_path.exists():
        trip = load_trip(trip_path)

    # Detect available providers
    available_providers = get_available_providers_for_trip(trip)
    provider_names = ", ".join(sorted(p.capitalize() for p in available_providers))

    # Load current config or build default
    if trip.display_config:
        current_configs = {mc.metric_id: mc for mc in trip.display_config.metrics}
    else:
        default_config = build_default_display_config(trip.id)
        current_configs = {mc.metric_id: mc for mc in default_config.metrics}

    # Widget tracking: {metric_id: {"checkbox": ..., "agg_select": ..., "available": bool}}
    metric_widgets: dict = {}

    with ui.dialog() as dialog, ui.card().style(
        "max-height: 80vh; overflow-y: auto; min-width: 600px"
    ):
        ui.label("Wetter-Metriken konfigurieren").classes("text-h6")

        # Trip + Provider info header
        ui.label(f"Trip: {trip.name}").classes("text-caption")
        ui.label(f"Provider: {provider_names}").classes("text-caption")

        # Table header
        with ui.row().classes("items-center text-caption text-grey q-mb-xs"):
            ui.label("Metrik").style("width: 260px; font-weight: 600")
            ui.label("Wert").style("width: 160px; font-weight: 600")
            ui.label("Label").style("width: 100px; font-weight: 600")

        # Render metrics grouped by category as table rows
        for category in CATEGORY_ORDER:
            metrics = get_metrics_by_category(category)
            if not metrics:
                continue

            # Category separator row
            ui.separator()
            ui.label(CATEGORY_LABELS[category]).classes(
                "text-subtitle2 text-grey-8 q-mt-xs q-mb-xs"
            )

            for metric_def in metrics:
                # Check provider availability
                is_available = any(
                    metric_def.providers.get(p, False) for p in available_providers
                )

                # Get current state from config
                mc = current_configs.get(metric_def.id)
                if mc:
                    initial_enabled = mc.enabled and is_available
                    initial_aggs = [AGG_LABELS[a] for a in mc.aggregations
                                    if a in AGG_LABELS]
                else:
                    initial_enabled = metric_def.default_enabled and is_available
                    initial_aggs = [AGG_LABELS[a] for a in metric_def.default_aggregations
                                    if a in AGG_LABELS]

                # Allowed aggregation options for this metric
                allowed_options = [AGG_LABELS[a] for a in metric_def.default_aggregations
                                   if a in AGG_LABELS]

                with ui.row().classes("items-center q-mb-xs"):
                    # Column 1: Metric checkbox
                    cb = ui.checkbox(
                        f"{metric_def.label_de} ({metric_def.col_label})",
                        value=initial_enabled,
                    ).style("width: 260px")
                    if not is_available:
                        cb.disable()
                        cb.tooltip("Nicht verfügbar für diese Route")

                    # Column 2: Aggregation dropdown
                    agg_select = ui.select(
                        options=allowed_options,
                        value=initial_aggs,
                        multiple=True,
                        label="Agg",
                    ).style("width: 160px")
                    if not is_available:
                        agg_select.disable()

                    # Column 3: Friendly format toggle
                    friendly_toggle = None
                    if metric_def.friendly_label:
                        initial_friendly = True
                        if mc and hasattr(mc, 'use_friendly_format'):
                            initial_friendly = mc.use_friendly_format
                        friendly_toggle = ui.checkbox(
                            metric_def.friendly_label,
                            value=initial_friendly,
                        ).style("width: 100px").tooltip(
                            "Benutzerfreundliche Darstellung (Emoji/Stufen)"
                        )
                        if not is_available:
                            friendly_toggle.disable()

                metric_widgets[metric_def.id] = {
                    "checkbox": cb,
                    "agg_select": agg_select,
                    "friendly_toggle": friendly_toggle,
                    "available": is_available,
                }

        # Buttons (Factory Pattern!)
        with ui.row().classes("q-mt-md"):
            ui.button("Abbrechen", on_click=make_cancel_handler(dialog))
            ui.button(
                "Speichern",
                on_click=make_save_handler(trip.id, metric_widgets, dialog, user_id),
            ).props("color=primary")

    dialog.open()


def make_cancel_handler(dialog):
    """Factory for cancel button (Safari compatibility)."""
    def do_cancel():
        dialog.close()
    return do_cancel


def make_save_handler(trip_id: str, metric_widgets: dict, dialog, user_id: str):
    """
    Factory for save handler - Safari compatible!

    Args:
        trip_id: Immutable trip ID (safe for closure)
        metric_widgets: Dict mapping metric_id to {checkbox, agg_select, available}
        dialog: Dialog to close after save
        user_id: User identifier for loading/saving

    Returns:
        Save handler function
    """
    def do_save():
        # Build MetricConfig list from UI state
        metric_configs = []
        enabled_count = 0
        for metric_id, widgets in metric_widgets.items():
            cb = widgets["checkbox"]
            agg_select = widgets["agg_select"]

            # Convert UI labels back to lowercase keys
            agg_values = agg_select.value if agg_select.value else []
            label_to_key = {v: k for k, v in AGG_LABELS.items()}
            aggregations = [label_to_key[a] for a in agg_values if a in label_to_key]

            friendly_toggle = widgets.get("friendly_toggle")
            use_friendly = friendly_toggle.value if friendly_toggle else True

            metric_configs.append(MetricConfig(
                metric_id=metric_id,
                enabled=cb.value,
                aggregations=aggregations,
                use_friendly_format=use_friendly,
            ))
            if cb.value:
                enabled_count += 1

        # Validation: minimum 1 metric
        if enabled_count == 0:
            ui.notify(
                "Mindestens 1 Metrik muss ausgewählt sein!",
                color="negative",
            )
            return

        # Load trip, update display_config, save
        trip_path = get_trips_dir(user_id) / f"{trip_id}.json"
        trip = load_trip(trip_path)

        # Preserve existing config values or use defaults
        old = trip.display_config

        trip.display_config = UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=metric_configs,
            show_night_block=old.show_night_block if old else True,
            night_interval_hours=old.night_interval_hours if old else 2,
            thunder_forecast_days=old.thunder_forecast_days if old else 2,
            updated_at=datetime.now(timezone.utc),
        )

        save_trip(trip, user_id=user_id)

        ui.notify(
            f"{enabled_count} Metriken gespeichert!",
            color="positive",
        )
        dialog.close()

    return do_save
