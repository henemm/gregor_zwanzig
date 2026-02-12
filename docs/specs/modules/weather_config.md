---
entity_id: weather_config
type: module
created: 2026-02-02
updated: 2026-02-12
status: draft
version: "2.0"
tags: [story-2, story-3, webui, config, safari, email, formatter]
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

**~15 metrics defined:**

| id | dp_field | category | providers (openmeteo/geosphere) |
|----|----------|----------|---------------------------------|
| temperature | t2m_c | temperature | yes/yes |
| wind_chill | wind_chill_c | temperature | yes/yes |
| wind | wind10m_kmh | wind | yes/yes |
| gust | gust_kmh | wind | yes/yes |
| precipitation | precip_1h_mm | precipitation | yes/yes |
| thunder | thunder_level | precipitation | yes (weather_code)/no |
| snowfall_limit | snowfall_limit_m | precipitation | no/yes |
| cloud_total | cloud_total_pct | atmosphere | yes/yes |
| cloud_low | cloud_low_pct | atmosphere | yes/no |
| cloud_mid | cloud_mid_pct | atmosphere | yes/no |
| cloud_high | cloud_high_pct | atmosphere | yes/no |
| humidity | humidity_pct | atmosphere | yes/yes |
| dewpoint | dewpoint_c | atmosphere | yes/yes (computed) |
| pressure | pressure_msl_hpa | atmosphere | yes/yes |
| snow_depth | snow_depth_cm | winter | no/yes (SNOWGRID) |

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

## Phase 2: API-Aware UI (Specification Only)

### Weather Config Dialog Rewrite

Dialog shows metrics grouped by category with provider-based availability:

1. **Header:** Trip name, current provider info
2. **Categories:** Temperature, Wind, Precipitation, Atmosphere, Winter
3. **Per metric:**
   - Checkbox (enabled/disabled)
   - Grayed out if not available for trip's provider
   - Aggregation dropdown (Min/Max/Avg/Sum) based on `default_aggregations`
   - Tooltip with metric description
4. **Footer:** Save/Cancel buttons (Factory Pattern!)

Provider detection: Based on trip waypoint coordinates, determine which provider serves data (OpenMeteo always available, GeoSphere for Austria region).

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
