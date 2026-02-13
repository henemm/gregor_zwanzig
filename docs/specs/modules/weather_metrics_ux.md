---
entity_id: weather_metrics_ux
type: module
created: 2026-02-13
updated: 2026-02-13
status: draft
version: "1.1"
tags: [formatter, ui, weather-config, trip-report]
---

# Weather Metrics UX

## Approval

- [x] Approved

## Purpose

Improve weather metrics user experience:
1. Readable English col_labels in table headers (v1.0 — DONE)
2. Level-based formatting for Cloud/CAPE/Visibility (v1.0 — DONE)
3. col_label visible in config UI checkboxes (v1.0 — DONE)
4. **Per-metric toggle: raw values vs. friendly formatting** (v1.1 — THIS UPDATE)

## Source

- **Files:**
  - `src/app/models.py` - MetricConfig: new `use_friendly_format` field
  - `src/app/metric_catalog.py` - MetricDefinition: new `has_friendly_format` flag
  - `src/formatters/trip_report.py` - `_fmt_val()`: respect toggle; `format_email()`: store config
  - `src/web/pages/weather_config.py` - Toggle widget per metric row
  - `src/app/loader.py` - Serialize/deserialize `use_friendly_format`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| MetricCatalog | upstream | `has_friendly_format` flag per MetricDefinition |
| MetricConfig | data | `use_friendly_format` per-metric preference |
| UnifiedWeatherDisplayConfig | data | Carries MetricConfig list to formatter |
| TripReportFormatter | consumer | `_fmt_val()` reads toggle, switches format |
| WeatherConfigUI | consumer | Shows toggle for eligible metrics |
| Loader | persistence | Serialize/deserialize new field |

## Implementation Details

### v1.0 Changes (ALREADY IMPLEMENTED)

- 13 col_label updates in MetricCatalog
- Cloud/CAPE/Visibility emoji/level formatting in `_fmt_val()`
- col_label shown next to label_de in config UI checkboxes

### v1.1 Change 4: Per-Metric Friendly Format Toggle

#### 4a) MetricDefinition: `friendly_label` field

**File:** `src/app/metric_catalog.py`, line 36 (after `default_enabled`)

```python
@dataclass(frozen=True)
class MetricDefinition:
    # ... existing fields ...
    default_enabled: bool = True
    friendly_label: str = ""  # NEW: toggle label in config UI; empty = no friendly format
```

**Derived property:** `has_friendly_format` = `bool(friendly_label)` (for backward compat in formatter/loader)

**Set `friendly_label` on these 6 metrics:**

| metric_id | col_key | friendly_label | Friendly format |
|-----------|---------|---------------|----------------|
| cloud_total | cloud | ☀️⛅☁️ | ☀️🌤️⛅🌥️☁️ |
| cloud_low | cloud_low | ☀️⛅☁️ | ☀️🌤️⛅🌥️☁️ |
| cloud_mid | cloud_mid | ☀️⛅☁️ | ☀️🌤️⛅🌥️☁️ |
| cloud_high | cloud_high | ☀️⛅☁️ | ☀️🌤️⛅🌥️☁️ |
| cape | cape | 🟢🟡🔴 | 🟢🟡🟠🔴 |
| visibility | visibility | good/fog | good/fair/poor/fog |

All other 13 metrics keep `friendly_label=""` (default).

#### 4b) MetricConfig: `use_friendly_format` preference

**File:** `src/app/models.py`, line 418 (after `evening_enabled`)

```python
@dataclass
class MetricConfig:
    metric_id: str
    enabled: bool = True
    aggregations: list[str] = field(default_factory=lambda: ["min", "max"])
    morning_enabled: Optional[bool] = None
    evening_enabled: Optional[bool] = None
    use_friendly_format: bool = True  # NEW: True=emoji/levels, False=raw values
```

**Default `True`** — existing reports keep current emoji behavior. User must explicitly opt out.

#### 4c) Loader: Serialize/Deserialize

**File:** `src/app/loader.py`

**Deserialization** (line 181-187, `_parse_display_config`):

```python
metrics.append(MetricConfig(
    metric_id=mc_data["metric_id"],
    enabled=mc_data.get("enabled", True),
    aggregations=mc_data.get("aggregations", ["min", "max"]),
    morning_enabled=mc_data.get("morning_enabled"),
    evening_enabled=mc_data.get("evening_enabled"),
    use_friendly_format=mc_data.get("use_friendly_format", True),  # NEW
))
```

**Serialization** (line 531-537, `_trip_to_dict`):

```python
{
    "metric_id": mc.metric_id,
    "enabled": mc.enabled,
    "aggregations": mc.aggregations,
    "use_friendly_format": mc.use_friendly_format,  # NEW
}
```

**Backward compatibility:** Old configs without `use_friendly_format` default to `True` via `.get("use_friendly_format", True)`.

#### 4d) Formatter: Config-aware `_fmt_val()`

**File:** `src/formatters/trip_report.py`

**Step 1: Store config on formatter instance** (in `format_email()`, line ~40)

```python
def format_email(self, segments, trip_name, report_type,
                 display_config=None, ...):
    dc = display_config or build_default_display_config()
    self._friendly_keys = self._build_friendly_keys(dc)  # NEW
    # ... rest unchanged
```

**Step 2: Helper to build set of col_keys that want friendly format**

```python
def _build_friendly_keys(self, dc: UnifiedWeatherDisplayConfig) -> set[str]:
    """Build set of col_keys where user wants friendly formatting."""
    from app.metric_catalog import get_metric
    keys = set()
    for mc in dc.metrics:
        if mc.use_friendly_format:
            try:
                metric_def = get_metric(mc.metric_id)
                if metric_def.has_friendly_format:
                    keys.add(metric_def.col_key)
            except KeyError:
                pass
    return keys
```

**Step 3: Update `_fmt_val()` signature** (line 278)

```python
def _fmt_val(self, key: str, val, html: bool = False) -> str:
    """Format a single cell value. Respects per-metric friendly format toggle."""
    if val is None:
        return "–"

    use_friendly = key in getattr(self, '_friendly_keys', set())

    # ... rest of method
```

**Step 4: Conditional formatting for the 3 metric groups**

Cloud (line 307):
```python
if key in ("cloud", "cloud_low", "cloud_mid", "cloud_high"):
    if not use_friendly:
        return f"{val:.0f}"
    # ... emoji logic → returns ONLY emoji (no numeric value, even in HTML)
    return emoji
```

CAPE (line 330):
```python
if key == "cape":
    if not use_friendly:
        s = f"{val:.0f}"
        if html and val is not None and val >= 1000:
            return f'<span style="background:#fff9c4;color:#f57f17;padding:2px 4px;border-radius:3px">{s}</span>'
        return s
    # ... emoji logic → returns ONLY emoji (no numeric value, even in HTML)
    return emoji
```

**Friendly format shows ONLY symbol/category, never the numeric value alongside it.**

Visibility (line 342):
```python
if key == "visibility":
    if not use_friendly:
        if val >= 10000:
            return f"{val / 1000:.0f}k"
        elif val >= 1000:
            return f"{val / 1000:.1f}k"
        else:
            s = f"{val:.0f}"
            if html and val < 500:
                return f'<span style="background:#fff3e0;color:#e65100;padding:2px 4px;border-radius:3px">{s}</span>'
            return s
    # ... existing level logic unchanged
```

**Raw format for CAPE/Visibility** restores the ORIGINAL formatting that existed before v1.0 (with HTML highlights).

**Call sites unchanged:** `_render_html_table` (line 500) and `_render_text_table` (line 590/603) still call `self._fmt_val(key, val, html)` — no signature change needed. The friendly-key lookup uses the instance variable `self._friendly_keys`.

#### 4e) Config UI: Collapsible table layout with per-metric toggle

**File:** `src/web/pages/weather_config.py`

Replace the current inline-row layout with a **collapsible table** per category.

**Layout:** `ui.expansion` (initially collapsed) containing a table with 3 columns:

| Column | Header | Content |
|--------|--------|---------|
| 1 | Metrik | Checkbox + metric name (label_de + col_label) |
| 2 | Wert | Aggregation multi-select (Min/Max/Avg/Sum) |
| 3 | Label | Friendly-format toggle (only for eligible metrics) |

**Metric-specific toggle labels:**

| metric_id | Toggle label | Tooltip |
|-----------|-------------|---------|
| cloud_total, cloud_low, cloud_mid, cloud_high | ☀️⛅☁️ | Emoji statt Prozent |
| cape | 🟢🟡🔴 | Emoji statt J/kg |
| visibility | good/fog | Stufen statt Meter |

Metrics without `has_friendly_format` show no toggle in column 3.

**MetricDefinition: `friendly_label` field**

Add to `MetricDefinition` in `metric_catalog.py`:

```python
friendly_label: str = ""  # Toggle label in config UI, empty = no friendly format
```

Set on 6 metrics:

| metric_id | friendly_label |
|-----------|---------------|
| cloud_total | ☀️⛅☁️ |
| cloud_low | ☀️⛅☁️ |
| cloud_mid | ☀️⛅☁️ |
| cloud_high | ☀️⛅☁️ |
| cape | 🟢🟡🔴 |
| visibility | good/fog |

`has_friendly_format` is then derived: `bool(friendly_label)` — no separate flag needed.

**Widget structure:**

```python
for category in CATEGORY_ORDER:
    metrics = get_metrics_by_category(category)
    with ui.expansion(CATEGORY_LABELS[category], icon="cloud").classes("q-mb-sm"):
        for metric_def in metrics:
            with ui.row().classes("items-center q-mb-xs"):
                cb = ui.checkbox(f"{metric_def.label_de} ({metric_def.col_label})", ...)
                agg_select = ui.select(...)
                friendly_toggle = None
                if metric_def.friendly_label:
                    friendly_toggle = ui.checkbox(metric_def.friendly_label, ...)
                        .tooltip(...)
```

**Save handler** (unchanged logic):

```python
friendly_toggle = widgets.get("friendly_toggle")
use_friendly = friendly_toggle.value if friendly_toggle else True

metric_configs.append(MetricConfig(
    metric_id=metric_id,
    enabled=cb.value,
    aggregations=aggregations,
    use_friendly_format=use_friendly,
))
```

## Expected Behavior

### v1.0 Behavior (ALREADY TESTED — 46 tests)

See Changelog v1.0.

### v1.1: Friendly format toggle

#### Given: Cloud with use_friendly_format=True (default)
**When:** _fmt_val("cloud", 50, html=False) called
**Then:** Returns "⛅" (emoji — unchanged from v1.0)

#### Given: Cloud with use_friendly_format=False
**When:** _fmt_val("cloud", 50, html=False) called
**Then:** Returns "50" (raw percentage)

**When:** _fmt_val("cloud", 50, html=True) called
**Then:** Returns "50" (raw percentage, no emoji)

#### Given: CAPE with use_friendly_format=True (default)
**When:** _fmt_val("cape", 800, html=False) called
**Then:** Returns "🟡" (emoji — unchanged from v1.0)

#### Given: CAPE with use_friendly_format=False
**When:** _fmt_val("cape", 800, html=False) called
**Then:** Returns "800" (raw J/kg value)

**When:** _fmt_val("cape", 1200, html=True) called
**Then:** Returns highlighted "1200" (original v1.0-pre HTML highlighting for >=1000)

#### Given: Visibility with use_friendly_format=True (default)
**When:** _fmt_val("visibility", 5000, html=False) called
**Then:** Returns "fair" (level text — unchanged from v1.0)

#### Given: Visibility with use_friendly_format=False
**When:** _fmt_val("visibility", 5000, html=False) called
**Then:** Returns "5.0k" (original km suffix format from before v1.0)

**When:** _fmt_val("visibility", 300, html=True) called
**Then:** Returns highlighted "300" (original HTML highlighting for <500m)

#### Given: Metric without has_friendly_format (e.g. temperature)
**When:** MetricConfig has use_friendly_format=False
**Then:** No effect — temperature always shows raw value (no friendly format exists)

#### Given: Old trip config without use_friendly_format field
**When:** Trip loaded from JSON
**Then:** use_friendly_format defaults to True — existing behavior preserved

#### Given: Config UI for cloud_total
**When:** User opens "Atmosphäre" expansion
**Then:** Row shows: [x] Bewölkung (Cloud) | [Avg] | [x] ☀️⛅☁️

#### Given: Config UI for cape
**When:** User opens "Niederschlag" expansion
**Then:** Row shows: [x] Gewitterenergie (Thndr%) | [Max] | [x] 🟢🟡🔴

#### Given: Config UI for visibility
**When:** User opens "Atmosphäre" expansion
**Then:** Row shows: [x] Sichtweite (Visib) | [Min] | [x] good/fog

#### Given: Config UI for temperature
**When:** User opens "Temperatur" expansion
**Then:** Row shows: [x] Temperatur (Temp) | [Min][Max][Avg] | (no toggle — no friendly_label)

#### Given: User unchecks friendly toggle for cloud and saves
**When:** Test report sent
**Then:** Cloud column shows raw "75" instead of "🌥️"

## Files to Change

| # | File | Change | LoC |
|---|------|--------|-----|
| 1 | `src/app/metric_catalog.py` | Replace `has_friendly_format` with `friendly_label` field + set on 6 metrics | ~8 |
| 2 | `src/app/models.py` | Add `use_friendly_format: bool = True` to MetricConfig | ~1 |
| 3 | `src/app/loader.py` | Serialize + deserialize `use_friendly_format` | ~3 |
| 4 | `src/formatters/trip_report.py` | `_build_friendly_keys()` + conditional in `_fmt_val()` for 3 groups | ~30 |
| 5 | `src/web/pages/weather_config.py` | Collapsible table layout + metric-specific toggle labels + save handler | ~40 |
| 6 | `tests/unit/test_weather_metrics_ux.py` | Tests for raw vs friendly toggle | ~40 |

**Total v1.1:** ~97 LoC, 6 files

## Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Existing reports change behavior | NONE | Default True preserves current emoji behavior |
| Old configs missing field | NONE | `.get("use_friendly_format", True)` defaults safely |
| _fmt_val() signature change | NONE | No signature change — uses instance variable `_friendly_keys` |
| Raw CAPE/Visibility format unclear | LOW | Restores original pre-v1.0 formatting (km suffix, HTML highlights) |
| SMS formatter affected | NONE | SMS uses compact_label, not `_fmt_val()` |

## Related Specs

- `docs/specs/modules/weather_config.md` (v2.2) - MetricDefinition structure
- `docs/specs/modules/trip_report_formatter_v2.md` - _fmt_val() method spec
- `docs/specs/modules/openmeteo_additional_metrics.md` - Original CAPE/Visibility formatting

## Known Limitations

- Toggle is per-metric, not per-report-type (morning/evening share same setting)
- Only 6 metrics support friendly format (cloud x4, cape, visibility)
- SMS formatter always uses compact format (unaffected by toggle)
- Emoji rendering depends on email client font support

## Changelog

- 2026-02-13: v1.0 - col_label updates, emoji/level formatting, config UI col_label (IMPLEMENTED)
- 2026-02-13: v1.1 - Per-metric friendly format toggle: MetricConfig.use_friendly_format, MetricDefinition.has_friendly_format, Config UI toggle, formatter respects setting
