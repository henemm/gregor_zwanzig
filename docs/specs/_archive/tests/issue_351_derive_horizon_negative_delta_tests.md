---
entity_id: issue_351_derive_horizon_negative_delta_tests
type: tests
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [tests, backend, python, horizon-filter, issue-351]
parent: issue_351_derive_horizon_negative_delta
phase: phase5_tdd_red
---

# Issue #351 — derive_horizon negativer Delta (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer den expliziten Guard in `derive_horizon()` aus
`docs/specs/bugfix/issue_351_derive_horizon_negative_delta.md`.

Parent-Spec: `docs/specs/bugfix/issue_351_derive_horizon_negative_delta.md` v1.0

## Source

- **File:** `tests/tdd/test_horizon_filter.py`
- **Identifier:** `test_derive_horizon_negative_delta`

## Tests

### test_derive_horizon_negative_delta (AC-1)

```python
def test_derive_horizon_negative_delta():
    report = date(2026, 5, 10)
    assert derive_horizon(report, date(2026, 5, 9)) is None    # delta = -1
    assert derive_horizon(report, date(2026, 5, 1)) is None    # delta = -9
    assert derive_horizon(report, date(2025, 12, 31)) is None  # delta = -130
```

Prueft AC-1: vergangene Etappen (delta < 0) geben None zurueck.
