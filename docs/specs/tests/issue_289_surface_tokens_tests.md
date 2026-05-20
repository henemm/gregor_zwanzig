---
entity_id: issue_289_surface_tokens_tests
type: tests
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [tests, bugfix, css, tokens, design-system, frontend, issue-289]
parent: issue_289_surface_tokens
phase: phase5_tdd_red
---

# Issue #289 — CSS-Surface-Token: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_289_surface_tokens.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_289_surface_tokens.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_289_surface_tokens.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_no_undefined_g_surface_token` | AC-1 | `grep var(--g-surface` ohne Suffix → 0 Treffer in `frontend/src/lib/` |
| `test_no_g_surface_alt_token` | AC-2 | `grep var(--g-surface-alt` → 0 Treffer in `frontend/src/lib/` |
| `test_metric_checkbox_uses_paper_token` | AC-3 | `MetricCheckbox.svelte` nutzt `--g-paper`, kein `--g-surface` mehr |
| `test_preset_row_color_mix_uses_surface0` | AC-4 | `PresetRow.svelte` nutzt `--g-surface-0` in `color-mix`, kein `--g-surface` mehr |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_issue_289_surface_tokens.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_289_surface_tokens.py -v
```

## Expected RED-State (vor GREEN-Phase)

Alle 4 Tests schlagen fehl, weil `--g-surface` und `--g-surface-alt` noch in den Komponenten stehen.

## Changelog

- 2026-05-20: Test-Manifest erstellt (Issue #289)
