---
entity_id: token
type: module
created: 2026-04-26
updated: 2026-04-26
status: active
version: "1.0"
tags: [output, sms, token-builder]
parent: output_token_builder
---

# Token (DTO)

## Approval

- [x] Approved

## Purpose

Frozen dataclass that represents a single token in the canonical SMS line.
Defined in `src/output/tokens/dto.py`. Master spec: `output_token_builder.md` v1.1.

## Source

- **File:** `src/output/tokens/dto.py`
- **Identifier:** `class Token`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| TokenLine | sibling | Aggregates Token instances in §2 POSITIONAL order |

## Implementation Details

See parent spec `output_token_builder.md` §"TokenLine DTO" and `sms_format.md` §3.

## Expected Behavior

- **Input:** symbol, value, category, priority, morning_visible, evening_visible
- **Output:** `Token.render() -> str` returns wire format ('{symbol}{value}' or '{symbol}-')
- **Side effects:** None (frozen dataclass)

## Known Limitations

- Vigilance HR/TH symbols already include the trailing colon ('HR:'/'TH:').

## Changelog

- 2026-04-26: Initial spec, defines DTO surface for β1 token builder.
