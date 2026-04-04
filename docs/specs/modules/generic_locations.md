---
entity_id: generic_locations
type: module
created: 2026-04-04
updated: 2026-04-04
status: draft
version: "1.0"
tags: [locations, activity-profile, weather-config, webui, safari, model]
---

# Generic Locations (F11a)

## Approval

- [x] Approved

## Purpose

Extends the `SavedLocation` model to support multiple activity types beyond ski touring by introducing an `ActivityProfile` enum and per-location `UnifiedWeatherDisplayConfig`. This enables wanderers, winter sports athletes, and general users to each receive weather metrics that are meaningful for their activity, reusing the same config infrastructure already built for Trips.

## Source

- **Files:**
  - `src/app/user.py` — `ActivityProfile` enum, new fields on `SavedLocation`
  - `src/app/metric_catalog.py` — `build_default_display_config_for_profile()` factory
  - `src/app/loader.py` — parse/serialize `activity_profile` + `display_config` on locations
  - `src/web/pages/weather_config.py` — `show_location_weather_config_dialog()`
  - `src/web/pages/locations.py` — profile dropdown, "Wetter-Metriken" button, profile badge

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `UnifiedWeatherDisplayConfig` | Model | Reused as-is from `src/app/models.py` for per-location metric config |
| `MetricConfig` | Model | Per-metric config entries inside `UnifiedWeatherDisplayConfig` |
| `MetricCatalog` | Module | Existing metric definitions; source for profile default sets |
| `build_default_display_config()` | Function | Existing factory in `metric_catalog.py`; Referenz für neue Profil-Factory |
| `_parse_display_config()` | Function | Existing deserializer in `loader.py` (Zeile 186-213); reused unchanged |
| `_trip_to_dict()` | Function | Existing display_config serializer in `loader.py` (Zeile 548-569); Pattern wird für Locations kopiert |
| `SavedLocation` | Model | Frozen dataclass in `src/app/user.py`; gains two new optional fields |
| `show_weather_config_dialog()` | Function | Existing Trip weather config dialog in `weather_config.py`; parallel function for locations |
| `trip.ActivityProfile` | Enum | Existiert bereits in `src/app/trip.py` (Zeile 29); **separate** Enum, nicht wiederverwenden |

## Implementation Details

### 1. LocationActivityProfile Enum (`src/app/user.py`)

**Hinweis:** In `src/app/trip.py` existiert bereits ein `ActivityProfile` Enum (WINTERSPORT, SUMMER_TREKKING, CUSTOM) für Trip-Aggregationsprofile. Das Location-Enum ist **separat**, da es andere Werte und einen anderen Zweck hat (UI-Default-Metriken vs. Aggregationsregeln).

```python
from enum import Enum

class LocationActivityProfile(str, Enum):
    WINTERSPORT = "wintersport"
    WANDERN = "wandern"
    ALLGEMEIN = "allgemein"
```

`str` mixin enables direct JSON serialization without a custom encoder. Der Name `LocationActivityProfile` vermeidet Verwechslung mit `trip.ActivityProfile`.

### 2. SavedLocation Model Changes (`src/app/user.py`)

`SavedLocation` is a frozen dataclass. Add two optional fields with defaults so existing instantiation sites require no changes:

```python
@dataclass(frozen=True)
class SavedLocation:
    # ... existing fields unchanged (id, name, lat, lon, elevation_m, region, bergfex_slug) ...
    activity_profile: LocationActivityProfile = LocationActivityProfile.ALLGEMEIN
    display_config: Optional["UnifiedWeatherDisplayConfig"] = None
```

`bergfex_slug` and `region` remain optional and are not removed or changed.

### 3. Profile-Based Default Metric Sets (`src/app/metric_catalog.py`)

New factory function that returns a `UnifiedWeatherDisplayConfig` pre-populated with the metric IDs appropriate for the given profile. Builds a `MetricConfig` list where `enabled=True` for the profile's set and `enabled=False` for all others.

Alle Metric-IDs in den Profil-Sets existieren im aktuellen MetricCatalog (verifiziert: `sunshine` = Zeile 254, `visibility` = Zeile 240, etc.).

```python
PROFILE_METRIC_IDS: dict[str, list[str]] = {
    "wintersport": [
        "temperature", "wind", "gust", "wind_chill",
        "precipitation", "cloud_total", "sunshine",
        "snow_depth", "fresh_snow", "snowfall_limit",
    ],
    "wandern": [
        "temperature", "wind", "gust",
        "precipitation", "thunder", "cloud_total", "sunshine",
        "rain_probability", "visibility",
    ],
    "allgemein": [
        "temperature", "wind", "gust",
        "precipitation", "cloud_total", "sunshine",
    ],
}

def build_default_display_config_for_profile(
    location_id: str,
    profile: "LocationActivityProfile",
) -> UnifiedWeatherDisplayConfig:
    """
    Build a UnifiedWeatherDisplayConfig with metrics enabled for the given profile.

    Args:
        location_id: Stable identifier for the location (used as trip_id equivalent).
        profile: ActivityProfile enum value.

    Returns:
        UnifiedWeatherDisplayConfig with profile-appropriate metrics enabled.
    """
    enabled_ids = set(PROFILE_METRIC_IDS.get(profile.value, PROFILE_METRIC_IDS["allgemein"]))
    metrics = []
    for metric_def in get_all_metrics():
        metrics.append(MetricConfig(
            metric_id=metric_def.id,
            enabled=metric_def.id in enabled_ids,
            aggregations=list(metric_def.default_aggregations),
        ))
    return UnifiedWeatherDisplayConfig(
        trip_id=location_id,
        metrics=metrics,
    )
```

Note: `sunshine` is listed in the profile sets but may not yet be in the MetricCatalog. If absent, it is silently skipped (the set intersection handles this).

### 4. Loader: Serialize/Deserialize (`src/app/loader.py`)

**Hinweis:** Location-Parsing und -Serialisierung sind aktuell **inline** in `load_all_locations()` (Zeile 417-425) und `save_location()` (Zeile 446-454). Es gibt keine separaten `_parse_location()` oder `_location_to_dict()` Funktionen. Die Änderungen erfolgen direkt in diesen bestehenden Funktionen.

**Deserialization** — `load_all_locations()` erweitern (Zeile 417-425):

```python
from src.app.user import LocationActivityProfile

# In load_all_locations(), innerhalb des try-Blocks nach data = json.load(f):
activity_profile_str = data.get("activity_profile", "allgemein")
display_config_data = data.get("display_config")
display_config = _parse_display_config(display_config_data) if display_config_data else None

locations.append(SavedLocation(
    id=data.get("id", path.stem),
    name=data["name"],
    lat=data["lat"],
    lon=data["lon"],
    elevation_m=data["elevation_m"],
    region=data.get("region"),
    bergfex_slug=data.get("bergfex_slug"),
    activity_profile=LocationActivityProfile(activity_profile_str),
    display_config=display_config,
))
```

`_parse_display_config()` ist der bestehende Deserializer (Zeile 186-213), der bereits für Trip display_configs genutzt wird — keine Änderung daran nötig.

**Serialization** — `save_location()` erweitern (Zeile 446-454):

```python
data = {
    "id": location.id,
    "name": location.name,
    "lat": location.lat,
    "lon": location.lon,
    "elevation_m": location.elevation_m,
    "region": location.region,
    "bergfex_slug": location.bergfex_slug,
    "activity_profile": location.activity_profile.value,
}
if location.display_config is not None:
    dc = location.display_config
    data["display_config"] = {
        "trip_id": dc.trip_id,
        "metrics": [
            {
                "metric_id": mc.metric_id,
                "enabled": mc.enabled,
                "aggregations": mc.aggregations,
                "use_friendly_format": mc.use_friendly_format,
                "alert_enabled": mc.alert_enabled,
                "alert_threshold": mc.alert_threshold,
            }
            for mc in dc.metrics
        ],
        "show_night_block": dc.show_night_block,
        "night_interval_hours": dc.night_interval_hours,
        "thunder_forecast_days": dc.thunder_forecast_days,
        "multi_day_trend_reports": dc.multi_day_trend_reports,
        "sms_metrics": dc.sms_metrics,
        "updated_at": dc.updated_at.isoformat(),
    }
```

Dieses Serialisierungs-Pattern ist identisch mit der Trip-Serialisierung in `_trip_to_dict()` (Zeile 548-569).

`display_config` wird aus dem JSON weggelassen wenn `None` (backward-kompatibel: alte Reader ignorieren die Abwesenheit).

**Backward-Kompatibilität:** Bestehende Location-JSON-Dateien ohne `activity_profile` bekommen Default `"allgemein"` via `.get("activity_profile", "allgemein")`. Dateien ohne `display_config` erzeugen `display_config=None` auf dem Model.

### 5. Location Weather Config Dialog (`src/web/pages/weather_config.py`)

New function parallel to the existing `show_weather_config_dialog(trip, user_id)`:

```python
def show_location_weather_config_dialog(
    location: SavedLocation,
    user_id: str = "default",
) -> None:
    """
    Show weather metrics configuration dialog for a saved location.

    Reuses the same category/metric UI as the Trip weather config dialog.
    Provider detection is skipped (all metrics shown as available).
    Saves updated display_config back to the location JSON via loader.

    Safari Compatible: all button handlers use make_<action>_handler() factory pattern.

    Args:
        location: SavedLocation to configure metrics for.
        user_id: User identifier for persistence (default: "default").
    """
```

**Provider detection:** Locations haben lat/lon; dieselbe Austria-Bounding-Box-Prüfung wie für Trips anwenden (in `weather_config.py` existiert `get_available_providers_for_trip()` — eine parallele Funktion `get_available_providers_for_location(loc: SavedLocation) -> set[str]` erstellen, die `loc.lat`/`loc.lon` gegen die Box 46.0-49.0°N, 9.5-17.0°E prüft). Nicht verfügbare Metriken werden identisch ausgegraut.

**Config initialization:**

```python
if location.display_config:
    current_metric_configs = {mc.metric_id: mc for mc in location.display_config.metrics}
else:
    default_config = build_default_display_config_for_profile(
        location_id=location.name,
        profile=location.activity_profile,
    )
    current_metric_configs = {mc.metric_id: mc for mc in default_config.metrics}
```

**Save handler factory:**

```python
def make_location_save_handler(location_name, metric_widgets, dialog, user_id):
    def do_save():
        # 1. Build MetricConfig list from UI
        # 2. Validate: at least 1 metric enabled
        # 3. Load all locations, replace matching location (frozen → rebuild), save
        # 4. ui.notify success + dialog.close()
    return do_save
```

Because `SavedLocation` is frozen, the save step reconstructs the dataclass:

```python
updated_location = SavedLocation(
    **{f.name: getattr(location, f.name) for f in fields(location)
       if f.name not in ("display_config",)},
    display_config=new_config,
)
```

**Cancel handler factory:**

```python
def make_location_cancel_handler(dialog):
    def do_cancel():
        dialog.close()
    return do_cancel
```

### 6. Locations Page UI Changes (`src/web/pages/locations.py`)

**Activity profile dropdown** in the create/edit location dialog:

```python
profile_select = ui.select(
    options={p.value: p.value.capitalize() for p in ActivityProfile},
    value=ActivityProfile.ALLGEMEIN.value,
    label="Aktivitätsprofil",
)
```

When saving a new or edited location, `activity_profile=ActivityProfile(profile_select.value)` is passed to the `SavedLocation` constructor.

**Profile badge** on each location card, positioned next to the location name:

```python
ui.badge(location.activity_profile.value.upper(), color="blue-grey")
```

**"Wetter-Metriken" button** on each location card, styled to match the existing button on Trip cards. Uses factory pattern:

```python
def make_open_weather_config_handler(loc, user_id):
    def do_open():
        show_location_weather_config_dialog(loc, user_id)
    return do_open

ui.button(
    "Wetter-Metriken",
    icon="tune",
    on_click=make_open_weather_config_handler(location, user_id),
).props("flat dense")
```

## Expected Behavior

### New location (no prior JSON)

- **Input:** User creates location, selects profile "Wandern"
- **Output:** Location saved with `activity_profile: "wandern"`, `display_config: null`
- **Side effects:** Profile badge "WANDERN" shown on card

### Opening Wetter-Metriken dialog for new location (no display_config)

- **Input:** User clicks "Wetter-Metriken" on a location with `display_config=None` and `activity_profile=WANDERN`
- **Output:** Dialog opens with WANDERN default metrics pre-checked (temp, wind, gust, precipitation, thunder, cloud_total, sunshine, rain_probability, visibility)
- **Side effects:** None until user saves

### Saving metric config for a location

- **Input:** User adjusts checkboxes in dialog and clicks "Speichern"
- **Output:** Location JSON updated with `display_config` containing new metric configs; `activity_profile` unchanged
- **Side effects:** `ui.notify` confirms save count; dialog closes

### Loading old location JSON (no activity_profile, no display_config)

- **Input:** Legacy `location.json` with only name/lat/lon/alt/bergfex_slug
- **Output:** `SavedLocation` with `activity_profile=ALLGEMEIN`, `display_config=None`
- **Side effects:** Profile badge shows "ALLGEMEIN"; no data loss

### Profile change (edit dialog)

- **Input:** User changes existing location from WINTERSPORT to WANDERN and saves
- **Output:** Location saved with new `activity_profile`; existing `display_config` is preserved (not reset to profile defaults)
- **Side effects:** Profile badge updates on card; weather metrics remain user-customized

## Known Limitations

- Changing activity profile does not auto-reset `display_config` to the new profile's defaults; user must manually open the dialog and reconfigure.
- F11b (ComparisonEngine profile-aware scoring) is out of scope for this spec; the `activity_profile` field is stored but not yet consumed by the comparison engine.
- No per-report-type (morning/evening) overrides for location metrics (same limitation as Trip config Phase 1).

## Files to Change

| # | File | Action | Est. LoC |
|---|------|--------|---------|
| 1 | `src/app/user.py` | ADD `LocationActivityProfile` enum; ADD 2 fields to `SavedLocation` | ~15 |
| 2 | `src/app/metric_catalog.py` | ADD `PROFILE_METRIC_IDS` dict + `build_default_display_config_for_profile()` | ~40 |
| 3 | `src/app/loader.py` | EXTEND `load_all_locations()` + `save_location()` inline für neue Felder + display_config Serialisierung | ~40 |
| 4 | `src/web/pages/weather_config.py` | ADD `get_available_providers_for_location()` + `show_location_weather_config_dialog()` + 2 factory handlers | ~90 |
| 5 | `src/web/pages/locations.py` | ADD profile dropdown, badge, "Wetter-Metriken" button + factory handler | ~45 |

**Total F11a:** ~230 LoC, 5 files

## Changelog

- 2026-04-04: v1.0 — Initial spec for Feature F11a (Model + UI). F11b (ComparisonEngine profile scoring) deferred.
