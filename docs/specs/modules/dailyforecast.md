---
entity_id: dailyforecast
type: module
created: 2026-04-26
updated: 2026-04-26
status: active
version: "1.0"
tags: [output, sms, token-builder, dto]
parent: output_token_builder
---

# DailyForecast (DTO)

## Approval

- [x] Approved

## Purpose

Frozen dataclass with normalized weather data for one day, used as input
to `build_token_line()`.

## Source

- **File:** `src/output/tokens/dto.py`
- **Identifier:** `class DailyForecast`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| HourlyValue | embedded | Provides per-hour samples for R/PR/W/G/TH |
| NormalizedForecast | parent | Aggregates DailyForecast tuples |

## Implementation Details

```
@dataclass(frozen=True)
class DailyForecast:
    temp_min_c: float | None
    temp_max_c: float | None
    rain_hourly / pop_hourly / wind_hourly / gust_hourly / thunder_hourly: tuple[HourlyValue, ...]
    snow_depth_cm / snow_new_24h_cm / snowfall_limit_m / avalanche_level / wind_chill_c
```

## Expected Behavior

- **Input:** Normalized values per metric.
- **Output:** Frozen DTO consumed by `metrics.py`.
- **Side effects:** None.

## Known Limitations

- Wintersport fields are optional; missing -> token suppressed.

## Changelog

- 2026-04-26: Initial spec for β1 token builder.
