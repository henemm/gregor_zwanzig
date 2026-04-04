---
entity_id: generic_locations_ui
type: module
created: 2026-04-04
updated: 2026-04-04
status: draft
version: "1.0"
tags: [locations, ui, weather-config, safari, nicegui]
---

# Generic Locations UI (F11b)

## Approval

- [ ] Approved

## Purpose

Adds the UI layer for per-location activity profiles and weather metric configuration. Builds on F11a (Core Model) by exposing `LocationActivityProfile` and `display_config` in the Locations web page and providing a weather metrics dialog for locations.

## Source

- **Files:**
  - `src/web/pages/locations.py` — Profile dropdown, badge, "Wetter-Metriken" button
  - `src/web/pages/weather_config.py` — `show_location_weather_config_dialog()` + `get_available_providers_for_location()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `LocationActivityProfile` | Enum | From `src/app/user.py` (F11a); values for dropdown |
| `SavedLocation` | Model | From `src/app/user.py`; has `activity_profile` + `display_config` fields |
| `build_default_display_config_for_profile()` | Function | From `src/app/metric_catalog.py` (F11a); generates defaults when no config exists |
| `save_location()` | Function | From `src/app/loader.py`; persists location with new fields |
| `load_all_locations()` | Function | From `src/app/loader.py`; loads locations with new fields |
| `show_weather_config_dialog()` | Function | Existing Trip dialog in `weather_config.py` (416 lines); pattern reference |
| `get_available_providers_for_trip()` | Function | Existing provider detection in `weather_config.py`; parallel function for locations |

## Implementation Details

### 1. Locations Page: Activity Profile Dropdown (`src/web/pages/locations.py`)

**Create dialog** — add after Bergfex Slug input (before buttons):

```python
from app.user import LocationActivityProfile

profile_select = ui.select(
    options={p.value: p.value.capitalize() for p in LocationActivityProfile},
    value=LocationActivityProfile.ALLGEMEIN.value,
    label="Aktivitätsprofil",
).classes("w-full")
```

**Save handler** (`make_save_handler`) — pass profile to SavedLocation:

```python
activity_profile=LocationActivityProfile(profile_select.value),
```

**Edit dialog** (`show_edit_dialog`) — add profile dropdown with current value:

```python
profile_select = ui.select(
    options={p.value: p.value.capitalize() for p in LocationActivityProfile},
    value=loc.activity_profile.value,
    label="Aktivitätsprofil",
).classes("w-full")
```

**Edit save handler** — pass profile from dropdown (instead of preserving old value):

```python
activity_profile=LocationActivityProfile(profile_select.value),
```

### 2. Locations Page: Profile Badge on Cards (`src/web/pages/locations.py`)

Add badge in the existing badge row (after region/bergfex badges):

```python
ui.badge(
    loc.activity_profile.value.capitalize(),
    color="blue-grey",
)
```

### 3. Locations Page: "Wetter-Metriken" Button (`src/web/pages/locations.py`)

**Import:**

```python
from web.pages.weather_config import show_location_weather_config_dialog
```

**Factory handler** (inside `render_content()`):

```python
def make_weather_config_handler(loc: SavedLocation):
    def do_show():
        show_location_weather_config_dialog(loc)
    return do_show
```

**Button** in location card (right button group, before Edit):

```python
ui.button(
    "Wetter-Metriken",
    icon="settings",
    on_click=make_weather_config_handler(loc),
).props("flat color=primary")
```

### 4. Provider Detection for Locations (`src/web/pages/weather_config.py`)

New function parallel to `get_available_providers_for_trip()`:

```python
def get_available_providers_for_location(location: SavedLocation) -> set[str]:
    providers = {"openmeteo"}
    if 46.0 <= location.lat <= 49.0 and 9.5 <= location.lon <= 17.0:
        providers.add("geosphere")
    return providers
```

### 5. Location Weather Config Dialog (`src/web/pages/weather_config.py`)

New function `show_location_weather_config_dialog(location, user_id="default")` that follows the same structure as `show_weather_config_dialog()` but:

- Uses `location.id` instead of `trip.id`
- Uses `get_available_providers_for_location()` instead of `get_available_providers_for_trip()`
- Initializes config from `location.display_config` or `build_default_display_config_for_profile(location.id, location.activity_profile)`
- Save handler loads location, rebuilds frozen dataclass with new `display_config`, calls `save_location()`
- Simplified: no alert thresholds (Phase 1), only enable/disable + aggregation selection

**Dialog structure:**

```
Wetter-Metriken: {location.name}
├─ Header row: Metrik | Aggregation
├─ Per category:
│  ├─ Category separator + label
│  └─ Per metric:
│     ├─ Checkbox (enabled/disabled, grayed if provider unavailable)
│     └─ Aggregation multi-select (Min/Max/Avg/Sum)
└─ Buttons: Cancel | Save (factory pattern)
```

**Save handler:**

```python
def make_location_save_handler(location_id, metric_widgets, dialog, user_id):
    def do_save():
        locations = load_all_locations(user_id)
        loc = next((l for l in locations if l.id == location_id), None)
        if not loc:
            ui.notify("Location nicht gefunden", type="negative")
            return

        metrics = []
        for metric_id, widgets in metric_widgets.items():
            metrics.append(MetricConfig(
                metric_id=metric_id,
                enabled=widgets["checkbox"].value,
                aggregations=[a.lower() for a in (widgets["agg"].value or [])],
            ))

        enabled_count = sum(1 for m in metrics if m.enabled)
        if enabled_count == 0:
            ui.notify("Mindestens 1 Metrik aktivieren!", type="warning")
            return

        new_config = UnifiedWeatherDisplayConfig(
            trip_id=location_id,
            metrics=metrics,
        )

        updated = SavedLocation(
            id=loc.id, name=loc.name, lat=loc.lat, lon=loc.lon,
            elevation_m=loc.elevation_m, region=loc.region,
            bergfex_slug=loc.bergfex_slug,
            activity_profile=loc.activity_profile,
            display_config=new_config,
        )
        save_location(updated, user_id)
        ui.notify(f"{enabled_count} Metriken gespeichert", type="positive")
        dialog.close()
    return do_save
```

## Expected Behavior

### New location with profile selection

- **Input:** User creates location, selects "Wandern" from dropdown
- **Output:** Location saved with `activity_profile: "wandern"`
- **Side effects:** Badge "Wandern" shown on card

### Opening Wetter-Metriken dialog (no existing config)

- **Input:** User clicks "Wetter-Metriken" on a WANDERN location without display_config
- **Output:** Dialog shows WANDERN defaults pre-checked (9 metrics)
- **Side effects:** None until save

### Saving metric config

- **Input:** User toggles checkboxes and clicks Speichern
- **Output:** Location JSON updated with display_config
- **Side effects:** Notification confirms save; dialog closes

### Editing profile via Edit dialog

- **Input:** User changes profile from WINTERSPORT to WANDERN in edit dialog
- **Output:** Location saved with new activity_profile; display_config preserved
- **Side effects:** Badge updates on card

### Provider detection (Austria vs global)

- **Input:** Location at lat=47.3, lon=11.4 (Innsbruck)
- **Output:** GeoSphere metrics available (snow_depth, fresh_snow, etc.)
- **Side effects:** Winter metrics NOT grayed out

### Provider detection (non-Austria)

- **Input:** Location at lat=42.0, lon=9.0 (Corsica)
- **Output:** Only OpenMeteo metrics available
- **Side effects:** GeoSphere-only metrics grayed out with tooltip

## Known Limitations

- No alert thresholds in location weather config (Phase 1, simplified dialog)
- No friendly format toggle for location metrics
- Changing profile does not auto-reset display_config
- Location weather config dialog does not auto-refresh the card list (user must navigate away and back)

## Files to Change

| # | File | Action | Est. LoC |
|---|------|--------|---------|
| 1 | `src/web/pages/locations.py` | ADD profile dropdown (create+edit), badge, Wetter-Metriken button + handler | ~50 |
| 2 | `src/web/pages/weather_config.py` | ADD `get_available_providers_for_location()` + `show_location_weather_config_dialog()` | ~120 |

**Total F11b:** ~170 LoC, 2 files

## Changelog

- 2026-04-04: v1.0 — Initial spec for F11b (UI layer). Builds on F11a (Core).
