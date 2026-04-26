---
entity_id: metricspec
type: module
created: 2026-04-26
updated: 2026-04-26
status: active
version: "1.0"
tags: [output, sms, token-builder, dto]
parent: output_token_builder
---

# MetricSpec (DTO)

## Approval

- [x] Approved

## Purpose

Frozen dataclass that mirrors the relevant fields of `MetricConfig` +
`MetricDefinition` for the β1 token builder, decoupling it from legacy models.

## Source

- **File:** `src/output/tokens/dto.py`
- **Identifier:** `class MetricSpec`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| build_token_line | consumer | Reads enabled / threshold / friendly fields |

## Implementation Details

```
@dataclass(frozen=True)
class MetricSpec:
    symbol: str               # 'N','D','R','PR','W','G','TH','TH+','HR'
    enabled: bool = True
    morning_enabled: bool = True
    evening_enabled: bool = True
    threshold: float | None = None
    use_friendly_format: bool = False
    friendly_label: str = ""
```

## Expected Behavior

- **Input:** Configured per metric by the caller.
- **Output:** Frozen DTO read during build_token_line() pipeline.
- **Side effects:** None.

## Known Limitations

- Pflicht-Tokens (N/D/R/PR/W/G/TH/TH+) are appended even if no MetricSpec
  exists, with implicit defaults.

## Changelog

- 2026-04-26: Initial spec for β1 token builder.
