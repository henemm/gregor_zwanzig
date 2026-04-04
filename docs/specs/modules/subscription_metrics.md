---
entity_id: subscription_metrics
type: module
created: 2026-04-04
updated: 2026-04-04
status: draft
version: "1.0"
tags: [subscriptions, weather-config, metrics, compare]
---

# Subscription Metriken-Auswahl (F14a)

## Approval

- [ ] Approved

## Purpose

Adds per-subscription weather metric configuration via `UnifiedWeatherDisplayConfig` on `CompareSubscription`. This enables users to choose which metrics appear in comparison reports — making subscriptions activity-agnostic (hiking, skiing, general). F14b will make the renderer respect this config.

## Source

- **Files:**
  - `src/app/user.py` — `display_config` field on `CompareSubscription`
  - `src/app/loader.py` — Serialize/deserialize `display_config` on subscriptions
  - `src/web/pages/subscriptions.py` — "Wetter-Metriken" button + handler on subscription cards
  - `src/web/pages/weather_config.py` — `show_subscription_weather_config_dialog()` for subscriptions

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareSubscription` | Model | `src/app/user.py`; gains `display_config` field |
| `UnifiedWeatherDisplayConfig` | Model | `src/app/models.py`; reused as-is |
| `MetricConfig` | Model | `src/app/models.py`; per-metric config entries |
| `build_default_display_config()` | Function | `src/app/metric_catalog.py`; generates defaults |
| `_parse_display_config()` | Function | `src/app/loader.py` (line 186); existing deserializer |
| `load_compare_subscriptions()` | Function | `src/app/loader.py` (line 669); deserialize with new field |
| `save_compare_subscriptions()` | Function | `src/app/loader.py` (line 715); serialize with new field |
| `show_location_weather_config_dialog()` | Function | `src/web/pages/weather_config.py`; pattern reference for subscription dialog |

## Implementation Details

### 1. CompareSubscription Model (`src/app/user.py`)

Add one field after `send_signal`:

```python
display_config: Optional["UnifiedWeatherDisplayConfig"] = None
```

Requires adding `UnifiedWeatherDisplayConfig` to the TYPE_CHECKING import block.

### 2. Loader: Serialize/Deserialize (`src/app/loader.py`)

**Deserialization** — in `load_compare_subscriptions()` (line ~711), add after `send_signal`:

```python
display_config_data = sub_data.get("display_config")
display_config = _parse_display_config(display_config_data) if display_config_data else None
```

And pass to constructor:

```python
display_config=display_config,
```

**Serialization** — in `save_compare_subscriptions()` (line ~749), add to the dict:

```python
if sub.display_config is not None:
    dc = sub.display_config
    sub_dict["display_config"] = {
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
        "updated_at": dc.updated_at.isoformat(),
    }
```

Note: The serialization is inline in a list comprehension. The display_config must be added after the dict is built, not inside the comprehension. Restructure to build the sub dict first, then conditionally add display_config.

**Backward compat:** Existing JSON without `display_config` produces `None`.

### 3. Subscriptions UI — "Wetter-Metriken" Button (`src/web/pages/subscriptions.py`)

**Import:**

```python
from web.pages.weather_config import show_subscription_weather_config_dialog
```

**Factory handler** in `render_subscription_card()`:

```python
def make_metrics_handler(subscription):
    def do_show():
        show_subscription_weather_config_dialog(subscription)
    return do_show
```

**Button** in the card action row (before Edit button):

```python
ui.button(
    "Wetter-Metriken",
    icon="settings",
    on_click=make_metrics_handler(sub),
).props("flat color=primary dense")
```

### 4. Subscription Weather Config Dialog (`src/web/pages/weather_config.py`)

New function `show_subscription_weather_config_dialog(subscription, user_id="default")`. Follows the same pattern as `show_location_weather_config_dialog()` but:

- Uses `subscription.id` as entity ID
- All providers available (subscriptions span multiple locations, so offer all metrics)
- Initializes from `subscription.display_config` or `build_default_display_config(subscription.id)`
- Save handler loads subscriptions, finds matching, updates display_config, saves

```python
def show_subscription_weather_config_dialog(
    subscription: CompareSubscription,
    user_id: str = "default",
) -> None:
    subs = load_compare_subscriptions(user_id)
    sub = next((s for s in subs if s.id == subscription.id), subscription)

    if sub.display_config and sub.display_config.metrics:
        current_configs = {mc.metric_id: mc for mc in sub.display_config.metrics}
    else:
        default_config = build_default_display_config(sub.id)
        current_configs = {mc.metric_id: mc for mc in default_config.metrics}

    # Dialog with metric checkboxes + aggregation (same UI as location dialog)
    # Save handler: update subscription's display_config and save
```

**Save handler:**

```python
def make_subscription_save_handler(sub_id, metric_widgets, dialog, user_id):
    def do_save():
        subs = load_compare_subscriptions(user_id)
        target = next((s for s in subs if s.id == sub_id), None)
        if not target:
            ui.notify("Subscription nicht gefunden", type="negative")
            return

        metrics = [
            MetricConfig(
                metric_id=mid,
                enabled=widgets["checkbox"].value,
                aggregations=[a.lower() for a in (widgets["agg"].value or [])],
            )
            for mid, widgets in metric_widgets.items()
        ]

        if sum(1 for m in metrics if m.enabled) == 0:
            ui.notify("Mindestens 1 Metrik!", type="warning")
            return

        target.display_config = UnifiedWeatherDisplayConfig(
            trip_id=sub_id, metrics=metrics,
        )
        save_compare_subscription(target, user_id)
        ui.notify(f"{sum(1 for m in metrics if m.enabled)} Metriken gespeichert", type="positive")
        dialog.close()
    return do_save
```

Note: CompareSubscription is a regular (non-frozen) dataclass, so `target.display_config = ...` works directly — no rebuild needed.

### 5. Toggle Handler Preservation (`src/web/pages/subscriptions.py`)

The existing `make_toggle_handler()` reconstructs `CompareSubscription` manually. Add `display_config`:

```python
display_config=subscription.display_config,
```

## Expected Behavior

### New subscription (no display_config)

- **Input:** User creates subscription without opening metrics dialog
- **Output:** Subscription saved with `display_config: null`
- **Side effects:** Reports use default metrics (current behavior preserved)

### Opening Wetter-Metriken dialog

- **Input:** User clicks "Wetter-Metriken" on a subscription
- **Output:** Dialog shows all metrics with defaults pre-checked
- **Side effects:** None until save

### Saving metric config

- **Input:** User enables only hiking metrics, disables snow
- **Output:** Subscription JSON updated with `display_config` containing selected metrics
- **Side effects:** Notification confirms; dialog closes

### Legacy subscription JSON (no display_config)

- **Input:** Existing `compare_subscriptions.json` without `display_config`
- **Output:** Loaded with `display_config=None`
- **Side effects:** No behavior change

### Toggle preserves display_config

- **Input:** User clicks pause/play on subscription with custom display_config
- **Output:** `enabled` toggled, `display_config` preserved
- **Side effects:** Metric config not lost

## Known Limitations

- F14a only stores the config — the renderer (compare.py) does NOT yet respect it (F14b scope)
- All metrics shown as available (no provider-based graying) since subscriptions span multiple locations
- No activity profile on subscriptions (unlike locations) — defaults are the standard catalog defaults

## Files to Change

| # | File | Action | Est. LoC |
|---|------|--------|---------|
| 1 | `src/app/user.py` | ADD `display_config` field to `CompareSubscription` | ~3 |
| 2 | `src/app/loader.py` | EXTEND serialize/deserialize for `display_config` | ~20 |
| 3 | `src/web/pages/subscriptions.py` | ADD "Wetter-Metriken" button + handler, update toggle | ~15 |
| 4 | `src/web/pages/weather_config.py` | ADD `show_subscription_weather_config_dialog()` | ~80 |

**Total F14a:** ~118 LoC, 4 files

## Changelog

- 2026-04-04: v1.0 — Initial spec for F14a (Model + UI). F14b (Renderer) deferred.
