---
entity_id: issue_445_metric_entry_cleanup_tests
type: tests
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [tests, rework, typescript, frontend, metric-entry, issue-445]
parent: issue_445_metric_entry_cleanup
phase: phase5_tdd_red
---

# Issue #445 — MetricEntry-Duplikate konsolidieren: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_445_metric_entry_cleanup.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec. Die Tests lesen
die echten Svelte-Dateien (keine Mocks, statische Analyse).

Parent-Spec: `docs/specs/modules/issue_445_metric_entry_cleanup.md` v1.0

## Source

- **File:** `tests/tdd/test_metric_entry_cleanup.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_save_preset_dialog_no_local_metric_entry` | AC-1 | SavePresetDialog.svelte enthält keine lokale `interface MetricEntry` |
| `test_table_preview_no_local_metric_entry` | AC-1 | TablePreview.svelte enthält keine lokale `interface MetricEntry` |
| `test_metric_checkbox_no_local_metric_entry` | AC-1 | MetricCheckbox.svelte enthält keine lokale `interface MetricEntry` |
| `test_save_preset_dialog_imports_metric_entry_from_types` | AC-2 | SavePresetDialog.svelte importiert MetricEntry aus `$lib/types` |
| `test_table_preview_imports_metric_entry_from_types` | AC-2 | TablePreview.svelte importiert MetricEntry aus `$lib/types` |
| `test_metric_checkbox_imports_metric_entry_from_types` | AC-2 | MetricCheckbox.svelte importiert MetricEntry aus `$lib/types` |
| `test_score_toggle_helpers_not_importing_metric_entry_from_lib_types` | AC-5 | scoreToggleHelpers.ts bleibt unverändert (lokaler Typ, kein $lib/types-Import) |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — Assertions sollen FAIL sein)
uv run pytest tests/tdd/test_metric_entry_cleanup.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_metric_entry_cleanup.py -v
```

## Expected RED-State (vor Implementation)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_save_preset_dialog_no_local_metric_entry` | FAIL | Lokale Definition existiert noch in Zeile 17 |
| `test_table_preview_no_local_metric_entry` | FAIL | Lokale Definition existiert noch in Zeile 12 |
| `test_metric_checkbox_no_local_metric_entry` | FAIL | Lokale Definition existiert noch in Zeile 13 |
| `test_save_preset_dialog_imports_metric_entry_from_types` | FAIL | Import fehlt noch |
| `test_table_preview_imports_metric_entry_from_types` | FAIL | Import fehlt noch |
| `test_metric_checkbox_imports_metric_entry_from_types` | FAIL | Import fehlt noch |
| `test_score_toggle_helpers_not_importing_metric_entry_from_lib_types` | PASS | scoreToggleHelpers.ts ist unverändert |

6 Tests sollen RED sein — das ist der TDD-RED-Beweis.
1 Test ist bereits grün (Regressions-Schutz: scoreToggleHelpers.ts darf nicht angefasst werden).

## Changelog

- 2026-05-29: Initial test manifest erstellt für Issue #445.
