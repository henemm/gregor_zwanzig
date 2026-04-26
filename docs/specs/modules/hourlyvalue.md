---
entity_id: hourlyvalue
type: module
created: 2026-04-26
updated: 2026-04-26
status: active
version: "1.0"
tags: [output, sms, token-builder, dto]
parent: output_token_builder
---

# HourlyValue (DTO)

## Approval

- [x] Approved

## Purpose

Frozen dataclass holding one hourly sample (hour 0-23 + value) for any metric
consumed by the token builder.

## Source

- **File:** `src/output/tokens/dto.py`
- **Identifier:** `class HourlyValue`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| DailyForecast | sibling | Holds tuples of HourlyValue per metric |

## Implementation Details

```
@dataclass(frozen=True)
class HourlyValue:
    hour: int    # 0..23
    value: float # numeric or thunder-level mapping
```

## Expected Behavior

- **Input:** hour 0-23, value (numeric)
- **Output:** Frozen DTO
- **Side effects:** None

## Known Limitations

- Thunder values are encoded as 0=none, 1=L, 2=M, 3=H to allow numeric MAX.

## Changelog

- 2026-04-26: Initial spec for β1 token builder.
