---
entity_id: report_options_migration
type: module
created: 2026-02-19
updated: 2026-02-19
status: draft
version: "1.0"
tags: [migration, models, loader, ui, report_config, weather_config, refactor]
---

# Report Options Migration

## Approval

- [ ] Approved

## Purpose

Migrates two report-behaviour settings (`show_compact_summary`, `multi_day_trend_reports`)
from `UnifiedWeatherDisplayConfig` (weather metrics model) into `TripReportConfig`
(report scheduling model), where they conceptually belong.
Also fixes a serialization bug where `show_compact_summary` was never written to the
JSON file and was therefore silently lost on reload.

## Source

- **Models:** `src/app/models.py`
- **Loader:** `src/app/loader.py`
- **UI (source, checkboxes to remove):** `src/web/pages/weather_config.py`
- **UI (target, checkboxes to add):** `src/web/pages/report_config.py`
- **Scheduler consumer:** `src/services/trip_report_scheduler.py`
- **Formatter consumer:** `src/formatters/trip_report.py`
- **Test fixture:** `tests/integration/test_wind_exposition_pipeline.py`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `UnifiedWeatherDisplayConfig` | DTO | Source of migrated fields (kept deprecated) |
| `TripReportConfig` | DTO | Target for migrated fields |
| `loader._parse_trip` | function | Deserialization with migration fallback |
| `loader._trip_to_dict` | function | Serialization — bug fix + new fields |
| `loader._parse_display_config` | function | No change needed |
| `weather_config.show_weather_config_dialog` | UI | Remove 3 checkboxes + handler params |
| `weather_config.make_save_handler` | UI | Remove 3 params, stop writing to display_config |
| `report_config.show_report_config_dialog` | UI | Add "Report-Optionen" section with 3 checkboxes |
| `report_config.make_save_handler` | UI | Add 3 params, write to TripReportConfig |
| `TripReportSchedulerService._send_trip_report` | service | Read from report_config with fallback |
| `TripReportFormatter.format_email` | formatter | Read from display_config arg (no sig change) |
| `_FakeDisplayConfig` | test fixture | Remove `show_compact_summary`, `multi_day_trend_reports` |

## Data Model

### Changes to `TripReportConfig` (models.py)

Add two fields after `wind_exposition_min_elevation_m`:

```python
@dataclass
class TripReportConfig:
    ...
    wind_exposition_min_elevation_m: Optional[float] = None

    # Report-Optionen (migrated from UnifiedWeatherDisplayConfig)
    show_compact_summary: bool = True           # F2: Kompakt-Summary vor Detail-Tabellen
    multi_day_trend_reports: list[str] = field(
        default_factory=lambda: ["evening"]
    )                                           # F3: Etappen-Ausblick morning/evening

    updated_at: datetime = field(...)
```

### Changes to `UnifiedWeatherDisplayConfig` (models.py)

Keep both fields to avoid breaking existing code that already reads from them,
but mark them deprecated with a comment:

```python
show_compact_summary: bool = True  # DEPRECATED: use TripReportConfig.show_compact_summary
...
multi_day_trend_reports: list[str] = field(...)  # DEPRECATED: use TripReportConfig.multi_day_trend_reports
```

## Implementation Details

### 1) Loader — `_parse_trip` (deserialization with migration)

When loading `report_config` from JSON, read the two new fields with a fallback
to `display_config` values so existing trip JSON files continue to work:

```python
# After parsing display_config and report_config dicts from JSON:
dc_data = data.get("display_config", {})

report_config = TripReportConfig(
    ...
    show_compact_summary=rc_data.get(
        "show_compact_summary",
        dc_data.get("show_compact_summary", True),   # migration fallback
    ),
    multi_day_trend_reports=rc_data.get(
        "multi_day_trend_reports",
        dc_data.get("multi_day_trend_reports", ["evening"]),  # migration fallback
    ),
    ...
)
```

The fallback is only applied when building `TripReportConfig`; it reads from the
already-parsed raw `dc_data` dict (not from the `display_config` object) to keep
the parsing order simple and avoid circular dependency.

### 2) Loader — `_trip_to_dict` (serialization — bug fix + new fields)

**Bug fix:** `show_compact_summary` was previously omitted from the serialized
`display_config` dict. After migration it must be written to `report_config`.

Add the two fields to the `report_config` block:

```python
if trip.report_config:
    data["report_config"] = {
        ...
        "wind_exposition_min_elevation_m": trip.report_config.wind_exposition_min_elevation_m,
        "show_compact_summary": trip.report_config.show_compact_summary,          # NEW
        "multi_day_trend_reports": trip.report_config.multi_day_trend_reports,    # NEW
        "updated_at": trip.report_config.updated_at.isoformat(),
    }
```

Also remove `show_compact_summary` from the `display_config` block if it was
previously written there (it was NOT — this was the serialization bug — so no
removal is needed; the field simply was never in the JSON).

### 3) UI — `report_config.py` (add "Report-Optionen" section)

Add a new section below "Wind-Exposition" and before the buttons.
Read initial values from `config` (a `TripReportConfig` instance):

```python
# Report-Optionen Section
ui.label("Report-Optionen").classes("text-subtitle1 q-mt-md")

compact_summary_cb = ui.checkbox(
    "Kompakt-Summary (Zusammenfassung vor Tabellen)",
    value=config.show_compact_summary,
)

ui.label("Etappen-Ausblick").classes("text-caption q-mt-sm")
trend_reports = config.multi_day_trend_reports
with ui.row().classes("items-center"):
    trend_morning_cb = ui.checkbox(
        "Morning Report", value="morning" in trend_reports,
    )
    trend_evening_cb = ui.checkbox(
        "Evening Report", value="evening" in trend_reports,
    )
```

Pass the three new widgets through the factory:

```python
ui.button(
    "Speichern",
    on_click=make_save_handler(
        trip.id,
        morning_input, evening_input,
        email_checkbox, sms_checkbox, alert_checkbox,
        elev_input,
        compact_summary_cb, trend_morning_cb, trend_evening_cb,   # NEW
        dialog, user_id,
    )
).props("color=primary")
```

In `make_save_handler` / `do_save`, build `multi_day_trend_reports` and include
both fields when constructing `TripReportConfig`:

```python
trend_reports = []
if trend_morning_cb.value:
    trend_reports.append("morning")
if trend_evening_cb.value:
    trend_reports.append("evening")

config = TripReportConfig(
    ...
    show_compact_summary=compact_summary_cb.value,
    multi_day_trend_reports=trend_reports,
    ...
)
```

Safari factory-pattern naming: `make_save_handler()` returns `do_save()` —
this already follows the existing pattern in `report_config.py`.

### 4) UI — `weather_config.py` (remove checkboxes)

Remove the "Report-Optionen" section (lines ~285–305) from
`show_weather_config_dialog`. This includes:
- The `ui.separator()` + `ui.label("Report-Optionen")` header
- `compact_summary_cb` checkbox
- `ui.label("Etappen-Ausblick")` + `trend_morning_cb` + `trend_evening_cb` checkboxes

Remove the three params from the `make_save_handler` call:

```python
ui.button(
    "Speichern",
    on_click=make_save_handler(
        trip.id, metric_widgets, dialog, user_id,
        # trend_morning_cb, trend_evening_cb, compact_summary_cb  <- REMOVED
    ),
).props("color=primary")
```

Update `make_save_handler` signature accordingly (remove 3 optional params).
Remove the `trend_reports` build logic and remove
`show_compact_summary` / `multi_day_trend_reports` from the
`UnifiedWeatherDisplayConfig(...)` constructor call. Use existing `old.*` values
as pass-through instead:

```python
trip.display_config = UnifiedWeatherDisplayConfig(
    trip_id=trip_id,
    metrics=metric_configs,
    show_night_block=old.show_night_block if old else True,
    night_interval_hours=old.night_interval_hours if old else 2,
    thunder_forecast_days=old.thunder_forecast_days if old else 2,
    # show_compact_summary and multi_day_trend_reports no longer set here
    updated_at=datetime.now(timezone.utc),
)
```

### 5) Scheduler — `trip_report_scheduler.py`

Change the `multi_day_trend_reports` read location in `_send_trip_report`:

```python
# BEFORE:
dc = trip.display_config
trend_reports = dc.multi_day_trend_reports if dc else ["evening"]

# AFTER (read from report_config; fallback for trips without report_config):
rc = trip.report_config
dc = trip.display_config
trend_reports = (
    rc.multi_day_trend_reports
    if rc is not None
    else (dc.multi_day_trend_reports if dc else ["evening"])
)
```

### 6) Formatter — `trip_report.py`

`format_email` receives `display_config` as a parameter (type
`UnifiedWeatherDisplayConfig`). The `show_compact_summary` check at line 77 reads
`dc.show_compact_summary`. The `display_config` argument is built by the scheduler
from `trip.display_config`. After migration, the deprecated field on
`UnifiedWeatherDisplayConfig` still has its default value `True` unless the trip
JSON had it set — but that JSON was never written (the serialization bug).

The correct fix: the scheduler must pass the effective value into the formatter.
Two options:

**Option A (preferred, minimal change):** Pass a patched `display_config` object
where `show_compact_summary` is overridden from `report_config` before calling
`format_email`:

```python
# In _send_trip_report, after obtaining display_config:
if trip.display_config and trip.report_config:
    trip.display_config.show_compact_summary = trip.report_config.show_compact_summary
```

This requires no signature change to `format_email`.

**Option B (cleaner but larger change):** Add `show_compact_summary` as an explicit
parameter to `format_email`. Out of scope for this migration.

Use **Option A**.

### 7) Tests — `test_wind_exposition_pipeline.py`

`_FakeDisplayConfig` currently carries both deprecated fields. After migration,
`show_compact_summary` and `multi_day_trend_reports` should be removed from this
fake if the formatter no longer reads them from `display_config`. However, since
the deprecated fields remain on `UnifiedWeatherDisplayConfig` for backward compat
and the formatter still reads `dc.show_compact_summary` (via Option A), the fake
must still provide `show_compact_summary`.

Remove `multi_day_trend_reports` from `_FakeDisplayConfig` only if the scheduler
path under test does not reach the trend-report branch. Since the pipeline test
likely bypasses the scheduler, `multi_day_trend_reports` can be removed from the
fake without breaking anything.

Minimal safe change: remove `multi_day_trend_reports` from `_FakeDisplayConfig`,
keep `show_compact_summary: bool = False`.

## Expected Behavior

- **Old trip JSON (no `report_config` section):** Trip loads with `report_config = None`;
  all fields use their `TripReportConfig` defaults (`show_compact_summary=True`,
  `multi_day_trend_reports=["evening"]`).
- **Old trip JSON (has `report_config` without the two new fields):** Loader falls
  back to `display_config` values; if `display_config` also lacks them, defaults apply.
- **New trip JSON (has `report_config` with both fields):** Values are read directly
  from `report_config`.
- **Save round-trip:** After the user opens the Report-Einstellungen dialog and saves,
  both fields are written into `report_config` in the JSON file.
- **UI:** "Report-Optionen" section appears in the Report-Einstellungen dialog
  (report_config.py), not in Wetter-Metriken (weather_config.py).
- **F2 Kompakt-Summary:** Controlled by `TripReportConfig.show_compact_summary`;
  formatter reads effective value via Option A (patched onto `display_config` before
  `format_email` call).
- **F3 Etappen-Ausblick:** Controlled by `TripReportConfig.multi_day_trend_reports`;
  scheduler reads from `report_config` with fallback.

## Known Limitations

- `UnifiedWeatherDisplayConfig.show_compact_summary` and
  `UnifiedWeatherDisplayConfig.multi_day_trend_reports` remain in the model as
  deprecated fields for backward compatibility. They should be removed in a future
  cleanup once no existing JSON data references them.
- Option A (patching `display_config` in the scheduler) mutates the in-memory object.
  This is acceptable because the object is not reused after `format_email` returns.
- Trips that have never been opened in the new UI will have `report_config = None`
  until the user saves any report config setting; defaults apply in the meantime.

## Scope

| File | Change | LoC (est.) |
|------|--------|-----------|
| `src/app/models.py` | Add 2 fields to `TripReportConfig`; deprecation comments on `UnifiedWeatherDisplayConfig` | ~8 |
| `src/app/loader.py` | `_parse_trip`: migration fallback for 2 fields; `_trip_to_dict`: serialize 2 new fields to `report_config` | ~12 |
| `src/web/pages/report_config.py` | Add "Report-Optionen" section (3 checkboxes); extend `make_save_handler` | ~35 |
| `src/web/pages/weather_config.py` | Remove "Report-Optionen" section (3 checkboxes + label + separator); simplify `make_save_handler` | ~-20 |
| `src/services/trip_report_scheduler.py` | Read `multi_day_trend_reports` from `report_config` with fallback; patch `display_config.show_compact_summary` | ~10 |
| `src/formatters/trip_report.py` | No change (reads `dc.show_compact_summary` — satisfied via scheduler patch) | 0 |
| `tests/integration/test_wind_exposition_pipeline.py` | Remove `multi_day_trend_reports` from `_FakeDisplayConfig` | ~-2 |
| **Total** | | **~43 net** |

### Out of Scope

- Removing deprecated fields from `UnifiedWeatherDisplayConfig` (future cleanup)
- Adding `show_compact_summary` as an explicit parameter to `TripReportFormatter.format_email` (Option B)
- SMS config migration

## Changelog

- 2026-02-19: Initial spec v1.0 created
