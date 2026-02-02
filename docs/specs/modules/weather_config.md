---
entity_id: weather_config
type: module
created: 2026-02-02
updated: 2026-02-02
status: draft
version: "1.0"
tags: [story-2, webui, config, safari]
---

# Weather Config UI

## Approval

- [x] Approved

## Purpose

WebUI page for configuring which weather metrics are displayed per trip. Users can select from 13 available metrics (8 basis + 5 extended) via checkbox interface, with configuration persisted to trip JSON files for use in Story 3 weather reports.

## Source

- **File:** `src/web/pages/weather_config.py` (NEW)
- **Page:** Weather Metrics Configuration UI

## Dependencies

### Upstream Dependencies (what we USE)

| Entity | Type | Purpose |
|--------|------|------------|
| `Trip` | Model | Trip dataclass with weather_config field (src/app/trip.py) |
| `TripWeatherConfig` | DTO | Config data structure (src/app/models.py) |
| `load_trip` | Function | Load trip from JSON (src/app/loader.py) |
| `save_trip` | Function | Save trip to JSON (src/app/loader.py) |
| `SegmentWeatherSummary` | DTO | Defines all 13 metric names (src/app/models.py) |

### Downstream Dependencies (what USES us)

| Entity | Type | Purpose |
|--------|------|------------|
| Story 3 Report Formatters | Service | Will filter metrics based on this config (future) |
| Trip Details Page | WebUI | May display current config (future) |

## Implementation Details

### DTO Structure

**Add to `src/app/models.py`:**

```python
@dataclass
class TripWeatherConfig:
    """
    Weather metrics configuration per trip.

    Stores which of the 13 available metrics the user wants
    to see in their trip weather reports.

    Example:
        TripWeatherConfig(
            trip_id="gr20-etappe3",
            enabled_metrics=["temp_max_c", "wind_max_kmh", "precip_sum_mm"],
            updated_at=datetime.now(timezone.utc)
        )
    """
    trip_id: str
    enabled_metrics: list[str]  # Subset of 13 metric names
    updated_at: datetime
```

**Extend `src/app/trip.py`:**

```python
@dataclass
class Trip:
    id: str
    name: str
    stages: List[Stage]
    avalanche_regions: List[str] = field(default_factory=list)
    aggregation: AggregationConfig = field(default_factory=AggregationConfig)
    weather_config: Optional[TripWeatherConfig] = None  # NEW - Feature 2.6
```

### Available Metrics (13 total)

**Basis Metrics (8) - Default: Checked**
1. `temp_min_c` - Minimum temperature
2. `temp_max_c` - Maximum temperature
3. `temp_avg_c` - Average temperature
4. `wind_max_kmh` - Maximum wind speed
5. `gust_max_kmh` - Maximum wind gusts
6. `precip_sum_mm` - Total precipitation
7. `cloud_avg_pct` - Average cloud cover
8. `humidity_avg_pct` - Average humidity

**Extended Metrics (5) - Default: Unchecked**
9. `thunder_level_max` - Maximum thunderstorm risk
10. `visibility_min_m` - Minimum visibility
11. `dewpoint_avg_c` - Average dewpoint temperature
12. `pressure_avg_hpa` - Average air pressure
13. `wind_chill_min_c` - Minimum wind chill

*Note: `snow_depth_cm` and `freezing_level_m` from SegmentWeatherSummary not included in v1.0 (winter-specific, not core hiking metrics)*

### UI Structure

```python
# src/web/pages/weather_config.py

from datetime import datetime, timezone
from typing import Dict

from nicegui import ui
from app.trip import Trip
from app.models import TripWeatherConfig
from app.loader import load_trip, save_trip


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


def show_weather_config_dialog(trip: Trip) -> None:
    """
    Show weather metrics configuration dialog.

    Factory Pattern (Safari compatible):
    - All handlers use make_<action>_handler() pattern
    - Closures bind immutable trip_id, not mutable checkbox dict

    Args:
        trip: Trip to configure weather metrics for
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
                on_click=make_save_handler(trip.id, checkboxes, dialog)
            )

    dialog.open()


def make_save_handler(trip_id: str, checkboxes: Dict[str, ui.checkbox], dialog):
    """
    Factory for save handler - Safari compatible!

    Pattern: make_<action>_handler() returns do_<action>()

    Args:
        trip_id: Immutable trip ID (safe for closure)
        checkboxes: Checkbox dictionary (captured at factory time)
        dialog: Dialog to close after save

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
        trip = load_trip(f"data/trips/{trip_id}.json")
        trip.weather_config = TripWeatherConfig(
            trip_id=trip_id,
            enabled_metrics=selected,
            updated_at=datetime.now(timezone.utc)
        )
        save_trip(trip, f"data/trips/{trip_id}.json")

        # Success feedback
        ui.notify(
            f"{len(selected)} Metriken gespeichert!",
            color="positive"
        )
        dialog.close()

    return do_save
```

### Loader Integration

**Modify `src/app/loader.py`:**

```python
def _parse_trip(data: Dict[str, Any]) -> Trip:
    """Parse trip data from dictionary."""
    # ... existing stage parsing ...

    # Parse weather config if present (Feature 2.6)
    weather_config = None
    if "weather_config" in data:
        wc_data = data["weather_config"]
        weather_config = TripWeatherConfig(
            trip_id=wc_data["trip_id"],
            enabled_metrics=wc_data["enabled_metrics"],
            updated_at=datetime.fromisoformat(wc_data["updated_at"])
        )

    return Trip(
        id=data["id"],
        name=data["name"],
        stages=stages,
        avalanche_regions=data.get("avalanche_regions", []),
        aggregation=aggregation,
        weather_config=weather_config  # NEW
    )


def save_trip(trip: Trip, path: Union[str, Path]) -> None:
    """Save a Trip to a JSON file."""
    data = {
        "id": trip.id,
        "name": trip.name,
        "stages": [...],  # existing serialization
        "avalanche_regions": trip.avalanche_regions,
        "aggregation": {...},  # existing serialization
    }

    # Serialize weather config (Feature 2.6)
    if trip.weather_config:
        data["weather_config"] = {
            "trip_id": trip.weather_config.trip_id,
            "enabled_metrics": trip.weather_config.enabled_metrics,
            "updated_at": trip.weather_config.updated_at.isoformat()
        }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
```

## Expected Behavior

### Initial Load
- **Given:** Trip without weather_config
- **When:** Dialog opened
- **Then:** All 8 basis metrics checked, 5 extended unchecked

### Save Flow
- **Given:** User selects 5 metrics
- **When:** "Speichern" clicked
- **Then:**
  - Config saved to trip JSON file
  - Notification: "5 Metriken gespeichert!"
  - Dialog closes

### Reload Persistence
- **Given:** Trip with saved config (3 metrics)
- **When:** Dialog re-opened
- **Then:** Previously saved 3 metrics checked, others unchecked

### Validation
- **Given:** User unchecks all metrics
- **When:** "Speichern" clicked
- **Then:**
  - Error notification: "Mindestens 1 Metrik muss ausgewählt sein!"
  - Dialog stays open

## Test Scenarios

### E2E Browser Test (Safari Mandatory!)

**File:** `tests/e2e/test_weather_config.py`

```python
def test_weather_config_saves_and_loads(page):
    """
    GIVEN: Trip without weather config
    WHEN: User selects metrics and saves
    THEN: Config persists and reloads correctly

    Safari test: Factory pattern ensures button works!
    """
    # Navigate to trips page
    page.goto("http://localhost:8080/trips")

    # Open weather config for test trip
    page.click('button:has-text("Wetter-Metriken")')

    # Verify default state (8 basis checked)
    assert page.locator('input[type="checkbox"]:checked').count() == 8

    # Uncheck 5 metrics, keep 3
    page.click('text=Temperatur (Durchschnitt)')  # uncheck
    page.click('text=Luftfeuchtigkeit')  # uncheck
    page.click('text=Böen (Max)')  # uncheck
    page.click('text=Bewölkung')  # uncheck
    page.click('text=Gewitter')  # uncheck

    # Save
    page.click('button:has-text("Speichern")')

    # Verify notification
    assert page.locator('text=3 Metriken gespeichert!').is_visible()

    # Reload page
    page.reload()

    # Re-open config
    page.click('button:has-text("Wetter-Metriken")')

    # Verify 3 metrics still checked
    assert page.locator('input[type="checkbox"]:checked').count() == 3


def test_weather_config_validation_minimum_one(page):
    """
    GIVEN: User unchecks all metrics
    WHEN: Save clicked
    THEN: Validation error shown, dialog stays open
    """
    page.goto("http://localhost:8080/trips")
    page.click('button:has-text("Wetter-Metriken")')

    # Uncheck all 8 basis metrics
    for i in range(8):
        checkboxes = page.locator('input[type="checkbox"]:checked')
        checkboxes.first.click()

    # Try to save
    page.click('button:has-text("Speichern")')

    # Verify error notification
    assert page.locator('text=Mindestens 1 Metrik').is_visible()

    # Dialog still open
    assert page.locator('text=Wetter-Metriken konfigurieren').is_visible()
```

## Known Limitations

1. **No Metric Descriptions** - Checkboxes show only names, no explanations
2. **No Metric Grouping** - Could group by category (temp, wind, precip, etc.)
3. **No Preview** - Can't see how selected metrics look in report
4. **No Metric Reordering** - Display order is fixed
5. **Winter Metrics Excluded** - snow_depth_cm and freezing_level_m not in v1.0 (can add later if needed)

## Integration with Story 3

**Usage in Trip Report Formatters:**

```python
# Story 3: Email/SMS Trip-Formatter
def format_trip_report(trip: Trip, segment_weather_data: List[SegmentWeatherData]):
    # Get enabled metrics from config
    enabled_metrics = set(trip.weather_config.enabled_metrics) if trip.weather_config else set(BASIS_METRICS.keys())

    # Only include configured metrics in report
    for segment_data in segment_weather_data:
        summary = segment_data.aggregated

        if "temp_max_c" in enabled_metrics:
            report += f"Temp: {summary.temp_max_c}°C\n"
        if "wind_max_kmh" in enabled_metrics:
            report += f"Wind: {summary.wind_max_kmh} km/h\n"
        # ... etc for all metrics
```

## Safari Compatibility

**CRITICAL: Factory Pattern Mandatory!**

All button handlers MUST use the factory pattern to avoid Safari closure binding bugs.

**Pattern:**
```python
def make_<action>_handler(immutable_args...):
    """Factory returns handler function."""
    def do_<action>():
        # Use immutable_args (safe in Safari)
        pass
    return do_<action>

button = ui.button("Label", on_click=make_handler(...))
```

**Reference:** `docs/reference/nicegui_best_practices.md`

## Standards Compliance

- ✅ Safari Compatible (Factory Pattern)
- ✅ No Mocked Tests (Real browser E2E)
- ✅ User Feedback (Notifications)
- ✅ Validation (Minimum 1 metric)
- ✅ Persistence (JSON file storage)
- ✅ API Contract (TripWeatherConfig documented)

## Files to Change

1. **src/app/models.py** (MODIFY, +15 LOC)
   - Add `TripWeatherConfig` dataclass

2. **src/app/trip.py** (MODIFY, +10 LOC)
   - Add `weather_config` field to `Trip`

3. **src/app/loader.py** (MODIFY, +20 LOC)
   - Parse/serialize `weather_config` in JSON

4. **src/web/pages/weather_config.py** (CREATE, ~80 LOC)
   - Weather config UI with checkboxes
   - Factory pattern save handler

5. **tests/e2e/test_weather_config.py** (CREATE, ~100 LOC)
   - Safari browser test
   - Save/load flow test
   - Validation test

**Total:** 5 files, ~225 LOC

## Changelog

- 2026-02-02: Initial spec created for Feature 2.6
