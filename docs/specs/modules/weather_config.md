---
entity_id: weather_config
type: module
created: 2026-02-02
updated: 2026-02-13
status: draft
version: "2.3"
tags: [story-2, story-3, webui, config, safari, email, formatter, alerts]
---

# Unified Weather Metrics Configuration

## Approval

- [x] Approved

## Purpose

Unified configuration system that connects trip weather metric selection with email report output. Replaces two disconnected config systems (`TripWeatherConfig` for UI storage, `EmailReportDisplayConfig` for formatter defaults) with a single `UnifiedWeatherDisplayConfig` backed by a central `MetricCatalog`.

**Problem solved:** Weather config dialog at `/trips` saves metrics that the email formatter ignores. `EmailReportDisplayConfig` has no UI and always uses hardcoded defaults. This spec unifies both.

## Source

- **Files:**
  - `src/app/metric_catalog.py` (NEW) - Central metric definitions
  - `src/app/models.py` (MODIFY) - New DTOs
  - `src/app/trip.py` (MODIFY) - New field on Trip
  - `src/app/loader.py` (MODIFY) - Serialization + migration
  - `src/formatters/trip_report.py` (MODIFY) - Consume unified config
  - `src/services/trip_report_scheduler.py` (MODIFY) - Pass config
  - `src/web/pages/weather_config.py` (MODIFY Phase 2) - API-aware UI

## Dependencies

### Upstream Dependencies (what we USE)

| Entity | Type | Purpose |
|--------|------|---------|
| `Trip` | Model | Trip dataclass with display_config field (src/app/trip.py) |
| `ForecastDataPoint` | DTO | Weather data fields (src/app/models.py) |
| `load_trip` / `save_trip` | Function | Trip persistence (src/app/loader.py) |
| `TripReportFormatter` | Class | Email report generation (src/formatters/trip_report.py) |
| `TripReportSchedulerService` | Class | Report scheduling (src/services/trip_report_scheduler.py) |

### Downstream Dependencies (what USES us)

| Entity | Type | Purpose |
|--------|------|---------|
| Weather Config Dialog | WebUI | Displays available metrics per trip (Phase 2) |
| Future SMS Formatter | Service | Uses sms_metrics subset (Phase 3) |

## Phasing

### Phase 1: Foundation - Config Model + Formatter Fix (HOCH)

Connect weather config to email reports. ~540 LoC, 7 files.

### Phase 2: API-Aware UI (MITTEL)

Dialog shows provider-based metric availability. ~250 LoC, 2 files.

### Phase 3: Per-Report-Type + SMS (NIEDRIG)

Morning/evening customization, SMS character counter. ~190 LoC, 2 files.

---

## Implementation Details

### MetricCatalog (NEW: `src/app/metric_catalog.py`)

Single Source of Truth for all weather metrics.

```python
@dataclass(frozen=True)
class MetricDefinition:
    """Definition of a single weather metric."""
    id: str                          # Unique key, e.g. "temperature"
    label_de: str                    # UI label, e.g. "Temperatur"
    unit: str                        # Unit, e.g. "°C"
    dp_field: str                    # ForecastDataPoint field name, e.g. "t2m_c"
    category: str                    # Grouping: temperature, wind, precipitation, atmosphere
    default_aggregations: list[str]  # Default agg functions: ["min", "max", "avg"]
    compact_label: str               # SMS short form, e.g. "T"
    col_key: str                     # Column key for formatter row dicts
    col_label: str                   # Column header label
    providers: dict[str, bool]       # Provider availability
    default_enabled: bool = True     # Enabled by default in new configs
```

**~23 metrics defined:**

| id | dp_field | category | providers (openmeteo/geosphere) |
|----|----------|----------|---------------------------------|
| temperature | t2m_c | temperature | yes/yes |
| wind_chill | wind_chill_c | temperature | yes/yes |
| wind | wind10m_kmh | wind | yes/yes |
| gust | gust_kmh | wind | yes/yes |
| precipitation | precip_1h_mm | precipitation | yes/yes |
| thunder | thunder_level | precipitation | yes (weather_code)/no |
| snowfall_limit | snowfall_limit_m | precipitation | no/yes |
| rain_probability | pop_pct | precipitation | yes/no |
| cape | cape_jkg | precipitation | yes/no |
| cloud_total | cloud_total_pct | atmosphere | yes/yes |
| cloud_low | cloud_low_pct | atmosphere | yes/no |
| cloud_mid | cloud_mid_pct | atmosphere | yes/no |
| cloud_high | cloud_high_pct | atmosphere | yes/no |
| humidity | humidity_pct | atmosphere | yes/yes |
| dewpoint | dewpoint_c | atmosphere | yes/yes (computed) |
| pressure | pressure_msl_hpa | atmosphere | yes/yes |
| visibility | visibility_m | atmosphere | yes/no |
| snow_depth | snow_depth_cm | winter | no/yes (SNOWGRID) |
| freezing_level | freezing_level_m | winter | yes/no |
| uv_index | uv_index | atmosphere | yes/no |
| fresh_snow | snow_new_24h_cm | winter | no/yes (SNOWGRID) |
| wind_direction | wind_direction_deg | wind | yes/yes |
| precip_type | precip_type | precipitation | no/yes |

**Key functions:**

```python
def get_metric(metric_id: str) -> MetricDefinition
def get_all_metrics() -> list[MetricDefinition]
def get_metrics_by_category(category: str) -> list[MetricDefinition]
def get_default_enabled_metrics() -> list[str]  # Returns metric IDs
def build_default_display_config(trip_id: str) -> "UnifiedWeatherDisplayConfig"
```

### UnifiedWeatherDisplayConfig DTO (replaces TripWeatherConfig + EmailReportDisplayConfig)

```python
@dataclass
class MetricConfig:
    """Per-metric configuration."""
    metric_id: str              # Reference to MetricDefinition.id
    enabled: bool = True
    aggregations: list[str] = field(default_factory=lambda: ["min", "max"])
    # Phase 3: per-report-type overrides
    morning_enabled: Optional[bool] = None   # None = follows global enabled
    evening_enabled: Optional[bool] = None
    use_friendly_format: bool = True
    # Per-metric alert configuration (v2.3)
    alert_enabled: bool = False              # Metric triggers alerts when True
    alert_threshold: Optional[float] = None  # None = use MetricCatalog default

@dataclass
class UnifiedWeatherDisplayConfig:
    """Unified weather display configuration per trip."""
    trip_id: str
    metrics: list[MetricConfig]      # Per-metric config
    show_night_block: bool = True
    night_interval_hours: int = 2
    thunder_forecast_days: int = 2
    # Phase 3: SMS
    sms_metrics: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

**Helper methods on UnifiedWeatherDisplayConfig:**

```python
def is_metric_enabled(self, metric_id: str) -> bool
    """Check if metric is enabled."""

def get_enabled_metric_ids(self) -> list[str]
    """Return list of enabled metric IDs."""

def to_row_keys(self) -> list[str]
    """Return ordered list of col_keys for enabled metrics (for formatter)."""

def get_alert_enabled_metrics(self) -> list[MetricConfig]
    """Return metrics with alert_enabled=True."""
```

### Trip Model Change

```python
@dataclass
class Trip:
    # ... existing fields ...
    weather_config: Optional["TripWeatherConfig"] = None  # KEPT for migration
    display_config: Optional["UnifiedWeatherDisplayConfig"] = None  # NEW
    report_config: Optional["TripReportConfig"] = None
```

### Loader Migration

When loading a trip JSON:
1. If `display_config` key present → load as `UnifiedWeatherDisplayConfig`
2. Else if `weather_config` key present → migrate old format:
   - Map old metric names to new metric IDs:
     - `temp_min_c` → metric_id `"temperature"`, aggregation `["min"]`
     - `temp_max_c` → metric_id `"temperature"`, aggregation `["max"]`
     - `temp_avg_c` → metric_id `"temperature"`, aggregation `["avg"]`
     - `wind_max_kmh` → metric_id `"wind"`, aggregation `["max"]`
     - `gust_max_kmh` → metric_id `"gust"`, aggregation `["max"]`
     - `precip_sum_mm` → metric_id `"precipitation"`, aggregation `["sum"]`
     - `cloud_avg_pct` → metric_id `"cloud_total"`, aggregation `["avg"]`
     - `humidity_avg_pct` → metric_id `"humidity"`, aggregation `["avg"]`
     - `thunder_level_max` → metric_id `"thunder"`, aggregation `["max"]`
     - `visibility_min_m` → metric_id `"visibility"` (NOT in catalog, skipped)
     - `dewpoint_avg_c` → metric_id `"dewpoint"`, aggregation `["avg"]`
     - `pressure_avg_hpa` → metric_id `"pressure"`, aggregation `["avg"]`
     - `wind_chill_min_c` → metric_id `"wind_chill"`, aggregation `["min"]`
   - Build MetricConfig list from mapped entries
   - Keep old `weather_config` in JSON for transition
3. Else → no config, formatter uses defaults from MetricCatalog

When saving: serialize `display_config` as new format. Old `weather_config` preserved if present.

### Formatter Changes (`src/formatters/trip_report.py`)

**Current flow:** `_dp_to_row()` checks `dc.show_temp_measured`, `dc.show_wind`, etc. (hardcoded booleans)

**New flow:** `_dp_to_row()` iterates over enabled metrics from `UnifiedWeatherDisplayConfig` using `MetricCatalog` to map metric_id → dp_field → col_key.

```python
def _dp_to_row(self, dp: ForecastDataPoint, config: UnifiedWeatherDisplayConfig) -> dict:
    row = {"time": f"{dp.ts.hour:02d}"}
    for mc in config.metrics:
        if not mc.enabled:
            continue
        metric_def = get_metric(mc.metric_id)
        value = getattr(dp, metric_def.dp_field, None)
        row[metric_def.col_key] = value
    return row
```

**Backward compatibility:** If no `UnifiedWeatherDisplayConfig` provided, build default from `MetricCatalog.build_default_display_config()` which produces identical output to current `_DEFAULT_DISPLAY`.

**_COL_DEFS update:** Column definitions derived from MetricCatalog instead of hardcoded list.

### Scheduler Changes

```python
# In _send_trip_report():
report = self._formatter.format_email(
    segments=segment_weather,
    trip_name=trip.name,
    report_type=report_type,
    display_config=trip.display_config,  # NEW: pass unified config
    night_weather=night_weather,
    thunder_forecast=thunder_forecast,
    stage_name=stage_name,
    stage_stats=stage_stats,
)
```

---

## Phase 2: API-Aware UI (MITTEL)

**Scope:** Rewrite weather config dialog to be API-aware with provider detection and metric availability.

**Estimate:** ~240 LoC across 2 files.

### Overview

Replace hardcoded metric checkboxes with dynamic UI that:
- Detects available providers from trip waypoint coordinates
- Shows metrics grouped by 5 categories from MetricCatalog
- Grays out unavailable metrics with tooltip
- Provides per-metric aggregation selection (Min/Max/Avg/Sum)
- Saves as UnifiedWeatherDisplayConfig (not legacy TripWeatherConfig)
- Uses Safari Factory Pattern for all handlers

### Provider Detection

**Helper Function:** `get_available_providers_for_trip(trip: Trip) -> set[str]`

```python
def get_available_providers_for_trip(trip: Trip) -> set[str]:
    """
    Detect which weather providers can serve this trip based on waypoint coordinates.

    Logic:
    - OpenMeteo: Always available (global coverage)
    - GeoSphere: Available if ANY waypoint is in Austria bounding box:
      - Latitude: 46.0° to 49.0° N
      - Longitude: 9.5° to 17.0° E

    Args:
        trip: Trip with stages containing waypoints

    Returns:
        Set of provider names: {"openmeteo"} or {"openmeteo", "geosphere"}
    """
    providers = {"openmeteo"}  # Always available

    for stage in trip.stages:
        for waypoint in stage.waypoints:
            if 46.0 <= waypoint.lat <= 49.0 and 9.5 <= waypoint.lon <= 17.0:
                providers.add("geosphere")
                return providers  # Early exit once Austria detected

    return providers
```

**Location:** `src/web/pages/weather_config.py` (top-level function)

### Metric Availability Check

**Per-Metric Logic:**

```python
available_providers = get_available_providers_for_trip(trip)
metric_def = get_metric(metric_id)

# Check if metric is available for at least one of trip's providers
is_available = any(metric_def.providers.get(p, False) for p in available_providers)
```

**UI Rendering:**
- Available: Normal checkbox + aggregation dropdown
- Unavailable: Grayed-out checkbox (disabled) + tooltip "(Nicht verfügbar für diese Route)"

### Dialog UI Structure

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│ Wetter-Metriken konfigurieren                       │
│                                                      │
│ Trip: [Trip Name]                                   │
│ Provider: OpenMeteo + GeoSphere                     │
│                                                      │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ Temperatur                                          │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ ☑ Temperatur         [Min][Max][Avg]               │
│ ☑ Gefühlte Temp      [Min]                          │
│                                                      │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ Wind                                                │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ ☑ Wind               [Max]                          │
│ ☑ Böen               [Max]                          │
│                                                      │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ Niederschlag                                        │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ ☑ Niederschlag       [Sum]                          │
│ ☑ Gewitter           [Max]                          │
│ ☐ Schneefallgrenze   [Min][Max]  ⓘ (Grayed out)   │
│                                                      │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ Atmosphäre                                          │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ ☑ Bewölkung          [Avg]                          │
│ ☐ Luftfeuchtigkeit   [Avg]                          │
│ ☐ Taupunkt           [Avg]                          │
│ ... (more metrics)                                  │
│                                                      │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ Winter                                              │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ ☐ Schneehöhe         [Max]  ⓘ (Grayed out)         │
│                                                      │
│                              [Abbrechen] [Speichern]│
└─────────────────────────────────────────────────────┘
```

**Dialog Container:**
- `ui.dialog()` + `ui.card()`
- `.style("max-height: 80vh; overflow-y: auto")` for scrolling
- `.style("min-width: 600px")` for consistent width

### Category Grouping

**German Labels:**

```python
CATEGORY_LABELS = {
    "temperature": "Temperatur",
    "wind": "Wind",
    "precipitation": "Niederschlag",
    "atmosphere": "Atmosphäre",
    "winter": "Winter",
}
```

**Rendering Order:**

```python
CATEGORY_ORDER = ["temperature", "wind", "precipitation", "atmosphere", "winter"]

for category in CATEGORY_ORDER:
    ui.separator()
    ui.label(CATEGORY_LABELS[category]).classes("text-subtitle1 q-mt-md")

    metrics = get_metrics_by_category(category)
    for metric in metrics:
        # Render metric row
```

### Per-Metric Row Structure

**Component Structure:**

```python
with ui.row().classes("items-center q-mb-sm"):
    # 1. Checkbox (enabled/disabled based on availability)
    checkbox = ui.checkbox(
        metric_def.label_de,
        value=(metric_def.id in current_enabled_ids)
    )

    if not is_available:
        checkbox.disable()
        checkbox.tooltip("Nicht verfügbar für diese Route")

    # 2. Aggregation multi-select dropdown
    agg_select = ui.select(
        options=["Min", "Max", "Avg", "Sum"],
        value=current_aggregations,  # From existing config
        multiple=True,
    ).classes("q-ml-md").style("min-width: 150px")

    # Filter options based on metric's default_aggregations
    allowed_aggs = [a.capitalize() for a in metric_def.default_aggregations]
    agg_select.options = allowed_aggs

    if not is_available:
        agg_select.disable()
```

**Data Storage:**

```python
# Track checkboxes and aggregation selects
metric_widgets = {}  # {metric_id: {"checkbox": ui.checkbox, "agg_select": ui.select}}

for metric in all_metrics:
    metric_widgets[metric.id] = {
        "checkbox": checkbox,
        "agg_select": agg_select,
        "available": is_available,
    }
```

### Save Logic

**Handler Function:** `make_save_handler(trip_id, metric_widgets, dialog, user_id)`

```python
def make_save_handler(trip_id: str, metric_widgets: dict, dialog, user_id: str):
    """
    Factory for save handler - Safari compatible!

    Args:
        trip_id: Trip identifier
        metric_widgets: Dict mapping metric_id to {checkbox, agg_select, available}
        dialog: Dialog to close after save
        user_id: User identifier for loading/saving

    Returns:
        Save handler function
    """
    def do_save():
        # 1. Build list of MetricConfig from UI state
        metric_configs = []
        for metric_id, widgets in metric_widgets.items():
            checkbox = widgets["checkbox"]
            agg_select = widgets["agg_select"]

            # Convert UI aggregation labels to lowercase
            aggregations = [a.lower() for a in agg_select.value]

            metric_configs.append(MetricConfig(
                metric_id=metric_id,
                enabled=checkbox.value,
                aggregations=aggregations,
            ))

        # 2. Validate: At least 1 metric enabled
        enabled_count = sum(1 for mc in metric_configs if mc.enabled)
        if enabled_count == 0:
            ui.notify("Mindestens 1 Metrik muss ausgewählt sein!", color="negative")
            return

        # 3. Load trip, update display_config, save
        trip_path = get_trips_dir(user_id) / f"{trip_id}.json"
        trip = load_trip(trip_path)

        # Preserve existing config values
        old_config = trip.display_config

        trip.display_config = UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=metric_configs,
            show_night_block=old_config.show_night_block if old_config else True,
            night_interval_hours=old_config.night_interval_hours if old_config else 2,
            thunder_forecast_days=old_config.thunder_forecast_days if old_config else 2,
            updated_at=datetime.now(timezone.utc),
        )

        save_trip(trip, user_id=user_id)

        # 4. Success feedback
        ui.notify(f"{enabled_count} Metriken gespeichert!", color="positive")
        dialog.close()

    return do_save
```

### All Factory Pattern Handlers

**List of Required Factories:**

1. **`make_save_handler(trip_id, metric_widgets, dialog, user_id)`**
   - Purpose: Save metric configuration to trip
   - Returns: `do_save()` function
   - Used by: "Speichern" button

2. **`make_cancel_handler(dialog)`**
   - Purpose: Close dialog without saving
   - Returns: `do_cancel()` function
   - Used by: "Abbrechen" button

**Implementation:**

```python
def make_cancel_handler(dialog):
    """Factory for cancel button (Safari compatibility)."""
    def do_cancel():
        dialog.close()
    return do_cancel

# Usage:
ui.button("Abbrechen", on_click=make_cancel_handler(dialog))
ui.button("Speichern", on_click=make_save_handler(trip_id, metric_widgets, dialog, user_id))
```

### Main Function Signature

```python
def show_weather_config_dialog(trip: Trip, user_id: str = "default") -> None:
    """
    Show API-aware weather metrics configuration dialog.

    Features:
    - Provider detection from trip waypoints
    - Grouped metrics by category (Temperature, Wind, etc.)
    - Grayed-out unavailable metrics with tooltip
    - Per-metric aggregation selection (Min/Max/Avg/Sum)
    - Saves as UnifiedWeatherDisplayConfig

    Safari Compatible:
    - All handlers use make_<action>_handler() factory pattern
    - Closures bind immutable trip_id and widget dict

    Args:
        trip: Trip to configure weather metrics for
        user_id: User identifier for saving (default: "default")
    """
```

### Load Current Config

**Logic:**

```python
# Get current config or build default
if trip.display_config:
    # Use existing unified config
    current_metric_configs = {mc.metric_id: mc for mc in trip.display_config.metrics}
else:
    # Build default from MetricCatalog
    default_config = build_default_display_config(trip.id)
    current_metric_configs = {mc.metric_id: mc for mc in default_config.metrics}

# For each metric, determine initial state
for metric in get_all_metrics():
    metric_config = current_metric_configs.get(metric.id)

    if metric_config:
        initial_enabled = metric_config.enabled
        initial_aggregations = metric_config.aggregations
    else:
        # Fallback to defaults if not in config
        initial_enabled = metric.default_enabled
        initial_aggregations = list(metric.default_aggregations)
```

### Aggregation Dropdown Details

**Option Mapping:**

```python
# Map MetricDefinition.default_aggregations to UI labels
AGG_LABELS = {
    "min": "Min",
    "max": "Max",
    "avg": "Avg",
    "sum": "Sum",
}

# For each metric, only show allowed aggregations
allowed_options = [AGG_LABELS[agg] for agg in metric_def.default_aggregations]

# Multi-select dropdown
agg_select = ui.select(
    options=allowed_options,
    value=[AGG_LABELS[a] for a in initial_aggregations],
    multiple=True,
    label="Aggregationen",
).style("min-width: 150px")
```

**Validation:**
- At least 1 aggregation must be selected per enabled metric
- Disabled metrics can have empty aggregations (ignored)

### Files to Change (Phase 2)

| # | File | Action | LoC |
|---|------|--------|-----|
| 1 | `src/web/pages/weather_config.py` | REWRITE | ~190 |
| 2 | `tests/e2e/test_weather_config.py` | UPDATE | ~50 |

**Total Phase 2:** ~240 LoC, 2 files

### Import Changes

**New Imports:**

```python
from app.metric_catalog import (
    get_all_metrics,
    get_metrics_by_category,
    build_default_display_config,
)
from app.models import UnifiedWeatherDisplayConfig, MetricConfig
```

**Removed Imports:**

```python
# No longer needed:
# BASIS_METRICS, EXTENDED_METRICS hardcoded dicts
# TripWeatherConfig (replaced by UnifiedWeatherDisplayConfig)
```

---

## Phase 3: Per-Report-Type + SMS (Specification Only)

### Morning/Evening Tabs

- Tab control: "Alle" / "Morning" / "Evening"
- "Alle" tab: global config (current behavior)
- Morning/Evening tabs: override `morning_enabled`/`evening_enabled` per metric
- Unconfigured overrides = follow global

### SMS Metric Subset

- Separate section: "SMS-Metriken"
- Subset of enabled metrics for SMS channel
- Live character counter (max 160)
- Uses `compact_label` from MetricCatalog

---

## Expected Behavior

### Phase 1: Default Config (no display_config set)

- **Given:** Trip without display_config
- **When:** Report generated
- **Then:** Default metrics from MetricCatalog used:
  - temperature (as temp), wind_chill (as felt), wind, gust, precipitation, thunder, snowfall_limit, cloud_total, humidity (if show_humidity default=False in catalog)
  - Output identical to current EmailReportDisplayConfig defaults

### Phase 1: Custom Config

- **Given:** Trip with display_config (temperature, wind, precipitation enabled)
- **When:** Report generated
- **Then:** Only Temp, Wind, Rain columns in email tables

### Phase 1: Migration from old weather_config

- **Given:** Trip JSON with old `weather_config.enabled_metrics: ["temp_max_c", "wind_max_kmh"]`
- **When:** Trip loaded
- **Then:** `display_config` created with temperature (max) + wind (max) enabled

### Phase 1: Night block respects config

- **Given:** `show_night_block: false`
- **When:** Evening report generated
- **Then:** No night block in email

## Known Limitations

### Phase 1
1. UI dialog still uses old checkbox format (Phase 2 rewrites it)
2. No per-report-type customization (Phase 3)
3. No SMS subset (Phase 3)
4. Aggregation selection not yet in UI (stored in config, used by formatter)

### General
1. Provider detection is static (based on catalog definition, not runtime API check)
2. No metric reordering in UI
3. No preview of report with selected metrics

## Files to Change (Phase 1 Implementation)

| # | File | Action | LoC |
|---|------|--------|-----|
| 1 | `src/app/metric_catalog.py` | CREATE | ~120 |
| 2 | `src/app/models.py` | MODIFY | ~50 |
| 3 | `src/app/trip.py` | MODIFY | ~5 |
| 4 | `src/app/loader.py` | MODIFY | ~50 |
| 5 | `src/formatters/trip_report.py` | MODIFY | ~100 |
| 6 | `src/services/trip_report_scheduler.py` | MODIFY | ~15 |
| 7 | `docs/specs/modules/weather_config.md` | REWRITE | ~200 |

**Total Phase 1:** ~540 LoC, 7 files

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Formatter regression | HIGH | Default config produces identical output to current defaults |
| Migration data loss | MEDIUM | Old weather_config preserved in JSON |
| Safari UI bugs | MEDIUM | Factory Pattern, Safari-first testing (Phase 2) |

## Standards Compliance

- Safari Compatible (Factory Pattern for Phase 2 UI)
- No Mocked Tests (real E2E)
- Spec-first workflow (this spec before code)
- Backward compatible defaults

## Changelog

- 2026-02-02: v1.0 - Initial spec for Feature 2.6 (UI only)
- 2026-02-12: v2.0 - Rewrite: Unified config, MetricCatalog, formatter integration (3 phases)
- 2026-02-12: v2.1 - Phase 2 fully specified: Provider detection, category grouping, aggregation UI, save logic
- 2026-02-12: v2.2 - Metric table updated: 15 -> 19 metrics (visibility, rain_probability, cape, freezing_level)
- 2026-02-13: v2.3 - Per-metric alert config: alert_enabled + alert_threshold on MetricConfig, 4 new metrics (uv_index, fresh_snow, wind_direction, precip_type), Alert-Spalte in Dialog UI, Slider aus Report Config entfernt
