---
entity_id: bug_281_290_stagestrip_tests
type: tests
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [tests, frontend, svelte5, cockpit, stagestrip, pill, css-tokens, bug-281, bug-290]
parent: bug_281_290_stagestrip
phase: phase5_tdd_red
---

# Bug #281 + #290 — StageStrip Pill-Fix: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_281_290_stagestrip.md`.
Statische Quelltextprüfungen für alle 6 Acceptance Criteria.

Parent-Spec: `docs/specs/modules/bug_281_290_stagestrip.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_281_290_stagestrip.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_bug_281_290_stagestrip.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_no_blue_accent_fallback_in_stage_detail_row` | AC-1 | `var(--g-accent, #3b82f6)` kommt in StageDetailRow.svelte nicht vor |
| `test_stage_pill_has_label_wrapper_class` | AC-2 | `stage-pill__label` Klasse in StagePill.svelte vorhanden |
| `test_stage_pill_has_title_binding` | AC-3 | `title={label}` Binding in StagePill.svelte vorhanden |
| `test_stage_pill_active_has_bold_style` | AC-4 | `font-weight` + `active` in StagePill.svelte vorhanden |
| `test_stage_strip_has_fade_mask` | AC-5 | `strip-fade-right` in StageStrip.svelte vorhanden |
| `test_pill_global_css_has_whitespace_nowrap` | AC-2 | `white-space: nowrap` im `[data-slot="pill"]`-Block von app.css |

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_no_blue_accent_fallback_in_stage_detail_row` | FAIL | `var(--g-accent, #3b82f6)` existiert noch in StageDetailRow.svelte:230 |
| `test_stage_pill_has_label_wrapper_class` | FAIL | `stage-pill__label` fehlt in StagePill.svelte |
| `test_stage_pill_has_title_binding` | FAIL | `title={label}` fehlt in StagePill.svelte |
| `test_stage_pill_active_has_bold_style` | FAIL | `font-weight` fehlt in StagePill.svelte (kein `.active`-Style) |
| `test_stage_strip_has_fade_mask` | FAIL | `strip-fade-right` fehlt in StageStrip.svelte |
| `test_pill_global_css_has_whitespace_nowrap` | FAIL | `white-space: nowrap` fehlt im Pill-Block von app.css |

Alle 6 Tests müssen im RED-Zustand FAIL sein — das ist der RED-Beweis.

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_bug_281_290_stagestrip.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_bug_281_290_stagestrip.py -v
```

## Changelog

- 2026-05-20: Initial test manifest erstellt für Bug #281 + #290 (StageStrip Pill-Fix).
