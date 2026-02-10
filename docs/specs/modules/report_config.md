---
entity_id: report_config
type: module
created: 2026-02-10
updated: 2026-02-10
status: draft
version: "1.0"
tags: [webui, config, report, nicegui, safari, story3]
---

# Report Config UI

## Approval

- [x] Approved

## Purpose

WebUI Dialog fuer Trip-Report-Einstellungen: Schedule-Zeiten, Channels (Email/SMS), und Alert-Thresholds.
Folgt dem Safari-kompatiblen Factory Pattern wie `weather_config.py`.

## Source

- **File:** `src/web/pages/report_config.py` (NEW)
- **Identifier:** `show_report_config_dialog()`, `make_save_handler()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/web/pages/weather_config.py` | module | Referenz-Pattern (Factory Pattern) |
| `src/web/pages/trips.py` | module | Integration (Button hinzufuegen) |
| `src/app/models.py` | module | TripReportConfig DTO hinzufuegen |
| `src/app/loader.py` | module | load/save TripReportConfig |
| `src/app/trip.py` | module | Trip.report_config Feld |
| `nicegui` | external | UI Framework |

## Architecture

```
trips.py
    |
    +-- render_trip_card(trip)
            |
            +-- ui.button("Report Settings", on_click=make_report_config_handler(trip))
                    |
                    +-- show_report_config_dialog(trip)
                            |
                            +-- Morning Time Picker (default 07:00)
                            +-- Evening Time Picker (default 18:00)
                            +-- Email Checkbox (default ON)
                            +-- SMS Checkbox (default OFF)
                            +-- Alert Checkbox (default ON)
                            +-- Temp Threshold Slider (1-10°C, default 5)
                            +-- Wind Threshold Slider (5-50 km/h, default 20)
                            +-- Precip Threshold Slider (1-20 mm, default 10)
                            |
                            +-- Save Button (Factory Pattern!)
                                    |
                                    +-- make_save_handler(trip_id, ...)
                                            |
                                            +-- validate (morning < evening)
                                            +-- save_trip()
                                            +-- ui.notify("Gespeichert!")
```

## Implementation Details

### 1. TripReportConfig DTO

```python
# src/app/models.py (ADD)

@dataclass
class TripReportConfig:
    """Configuration for trip weather reports (Feature 3.5)."""
    trip_id: str
    enabled: bool = True

    # Schedule
    morning_time: time = field(default_factory=lambda: time(7, 0))
    evening_time: time = field(default_factory=lambda: time(18, 0))

    # Channels
    send_email: bool = True
    send_sms: bool = False

    # Alerts
    alert_on_changes: bool = True
    change_threshold_temp_c: float = 5.0
    change_threshold_wind_kmh: float = 20.0
    change_threshold_precip_mm: float = 10.0

    # Metadata
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### 2. Trip Model Extension

```python
# src/app/trip.py (ADD)

@dataclass
class Trip:
    # ... existing fields ...
    weather_config: Optional["TripWeatherConfig"] = None  # Feature 2.6
    report_config: Optional["TripReportConfig"] = None    # Feature 3.5 NEW
```

### 3. Loader Extension

```python
# src/app/loader.py (ADD to _parse_trip)

if "report_config" in data:
    rc_data = data["report_config"]
    report_config = TripReportConfig(
        trip_id=rc_data["trip_id"],
        enabled=rc_data.get("enabled", True),
        morning_time=time.fromisoformat(rc_data["morning_time"]),
        evening_time=time.fromisoformat(rc_data["evening_time"]),
        send_email=rc_data.get("send_email", True),
        send_sms=rc_data.get("send_sms", False),
        alert_on_changes=rc_data.get("alert_on_changes", True),
        change_threshold_temp_c=rc_data.get("change_threshold_temp_c", 5.0),
        change_threshold_wind_kmh=rc_data.get("change_threshold_wind_kmh", 20.0),
        change_threshold_precip_mm=rc_data.get("change_threshold_precip_mm", 10.0),
        updated_at=datetime.fromisoformat(rc_data["updated_at"]),
    )
```

### 4. Report Config Dialog

```python
# src/web/pages/report_config.py (NEW)

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

def show_report_config_dialog(trip: Trip, user_id: str = "default") -> None:
    """
    Show report configuration dialog.

    Factory Pattern (Safari compatible):
    - All handlers use make_<action>_handler() pattern

    Args:
        trip: Trip to configure reports for
        user_id: User identifier for saving
    """
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Report-Einstellungen").classes("text-h6")

        # Get current config or defaults
        config = trip.report_config or TripReportConfig(trip_id=trip.id)

        # Schedule Section
        ui.label("Zeitplan").classes("text-subtitle1 q-mt-md")

        with ui.row().classes("w-full"):
            morning_input = ui.time(
                "Morgen-Report",
                value=config.morning_time.strftime("%H:%M")
            )
            evening_input = ui.time(
                "Abend-Report",
                value=config.evening_time.strftime("%H:%M")
            )

        # Channels Section
        ui.label("Kanäle").classes("text-subtitle1 q-mt-md")

        email_checkbox = ui.checkbox("E-Mail senden", value=config.send_email)
        sms_checkbox = ui.checkbox("SMS senden", value=config.send_sms)

        # Alerts Section
        ui.label("Wetter-Alerts").classes("text-subtitle1 q-mt-md")

        alert_checkbox = ui.checkbox(
            "Bei Änderungen benachrichtigen",
            value=config.alert_on_changes
        )

        ui.label("Schwellenwerte").classes("text-subtitle2 q-mt-sm")

        temp_slider = ui.slider(
            min=1, max=10, step=1, value=config.change_threshold_temp_c
        ).props("label-always")
        ui.label(f"Temperatur: {temp_slider.value}°C")

        wind_slider = ui.slider(
            min=5, max=50, step=5, value=config.change_threshold_wind_kmh
        ).props("label-always")
        ui.label(f"Wind: {wind_slider.value} km/h")

        precip_slider = ui.slider(
            min=1, max=20, step=1, value=config.change_threshold_precip_mm
        ).props("label-always")
        ui.label(f"Niederschlag: {precip_slider.value} mm")

        # Buttons (Factory Pattern!)
        with ui.row():
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
            change_threshold_temp_c=temp_slider.value,
            change_threshold_wind_kmh=wind_slider.value,
            change_threshold_precip_mm=precip_slider.value,
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
```

### 5. Trips Page Integration

```python
# src/web/pages/trips.py (ADD button in trip card)

def make_report_config_handler(trip: Trip):
    """Factory for report config button (Safari compatibility)."""
    def do_open():
        from web.pages.report_config import show_report_config_dialog
        show_report_config_dialog(trip)
    return do_open

# In render_trip_card():
ui.button(
    icon="schedule",
    on_click=make_report_config_handler(trip)
).tooltip("Report-Einstellungen")
```

## Configuration

| Element | Default | Range | Beschreibung |
|---------|---------|-------|--------------|
| morning_time | 07:00 | 00:00-23:59 | Morgen-Report Zeit |
| evening_time | 18:00 | 00:00-23:59 | Abend-Report Zeit |
| send_email | true | bool | Email senden |
| send_sms | false | bool | SMS senden |
| alert_on_changes | true | bool | Alerts aktiviert |
| change_threshold_temp_c | 5.0 | 1-10 | Temp-Schwelle |
| change_threshold_wind_kmh | 20.0 | 5-50 | Wind-Schwelle |
| change_threshold_precip_mm | 10.0 | 1-20 | Niederschlag-Schwelle |

## Files to Create/Modify

| File | Action | LOC |
|------|--------|-----|
| `src/web/pages/report_config.py` | NEW | ~100 |
| `src/app/models.py` | ADD | ~20 |
| `src/app/trip.py` | ADD | ~5 |
| `src/app/loader.py` | ADD | ~25 |
| `src/web/pages/trips.py` | MOD | ~10 |
| `tests/integration/test_report_config.py` | NEW | ~60 |

**Total: ~220 LOC** (unter 250 Limit)

## Testing Strategy

### Unit Tests

```python
def test_validation_morning_before_evening():
    """Morning time must be before evening time."""

def test_default_config_values():
    """Default values should match spec."""

def test_config_serialization():
    """Config should serialize/deserialize correctly."""
```

### Integration Tests

```python
def test_save_and_load_report_config():
    """Save config, reload trip, verify config persisted."""

def test_trip_without_report_config():
    """Trip without config should use defaults."""
```

## Known Limitations

- SMS Channel ist UI-only (SMS-Versand nicht implementiert)
- Zeiten sind nur zur vollen Stunde waehlbar (UI Limitation)
- Keine Timezone-Auswahl (fest Europe/Vienna)

## Error Handling

```python
# Validation in do_save()
if morning >= evening:
    ui.notify("Morgen-Zeit muss vor Abend-Zeit liegen!", color="negative")
    return  # Don't save

# At least one channel required
if not email_checkbox.value and not sms_checkbox.value:
    ui.notify("Mindestens ein Kanal muss aktiv sein!", color="negative")
    return
```

## Changelog

- 2026-02-10: v1.0 Initial spec created (Feature 3.5)
