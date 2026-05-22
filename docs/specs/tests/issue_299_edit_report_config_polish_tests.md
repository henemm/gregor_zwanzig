---
entity_id: issue_299_edit_report_config_polish_tests
type: tests
created: 2026-05-22
updated: 2026-05-22
status: draft
version: "1.0"
tags: [tests, frontend, svelte, ui-polish, brand-tokens, issue-299]
parent: issue_299_edit_report_config_section_polish
phase: phase5_tdd_red
---

# Issue #299 — EditReportConfigSection Polish: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_299_edit_report_config_section_polish.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_299_edit_report_config_section_polish.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_299_edit_report_config_polish.py` (NEU)
- **Hauptdatei unter Test:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte`

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_quick_chips_no_raw_tailwind_hover_bg_accent` | AC-1 | Kein `hover:bg-accent` auf Quick-Chip-Buttons |
| `test_ac1_quick_chips_have_g_quick_chip_class` | AC-1 | Mindestens 4 Vorkommen von `g-quick-chip` im Template |
| `test_ac1_style_block_defines_g_quick_chip` | AC-1 | `<style>`-Block definiert `.g-quick-chip` mit `g-radius-pill` |
| `test_ac2_hint_links_no_hover_text_primary` | AC-2 | Kein `hover:text-primary` auf Channel-Hint-Links |
| `test_ac2_hint_links_use_g_accent` | AC-2 | Mindestens 3 Vorkommen von `g-accent` für Hint-Links |
| `test_ac3_advanced_toggle_no_plain_button_with_text_primary` | AC-3 | Kein `font-semibold text-primary hover:underline` auf Advanced-Toggle |
| `test_ac3_advanced_toggle_imports_btn` | AC-3 | `Btn` ist aus `$lib/components/ui/btn` importiert |
| `test_ac3_advanced_toggle_imports_chevron_down` | AC-3, AC-4 | `ChevronDown` ist aus `@lucide/svelte/icons/chevron-down` importiert |
| `test_ac5_wind_exposition_has_g_num_with_unit_wrapper` | AC-5 | `g-num-with-unit` ist als Label-Klasse vorhanden |
| `test_ac5_wind_exposition_has_m_unit_span` | AC-5 | `g-num-unit` ist als Span-Klasse vorhanden |
| `test_ac5_style_block_defines_g_num_unit` | AC-5 | `<style>`-Block definiert `.g-num-unit` und `.g-num-with-unit` |
| `test_ac6_no_section_with_border_input` | AC-6 | Keine `<section>` mit `border border-input` mehr vorhanden |
| `test_ac6_imports_card_component` | AC-6 | `Card` ist aus `$lib/components/ui/card` importiert |
| `test_ac6_card_root_present_at_least_3_times` | AC-6 | Mindestens 3 `<Card.Root>`-Elemente vorhanden |
| `test_ac7_morning_time_input_has_g_num_input` | AC-7 | Beide Zeit-Inputs haben Klasse `g-num-input` |
| `test_regression_all_required_testids_present` | AC-8 | Alle 20 data-testids aus dem E2E-Test bleiben erhalten |

## Acceptance Criteria (Referenz auf Parent-Spec)

Alle ACs sind in `docs/specs/modules/issue_299_edit_report_config_section_polish.md` definiert (AC-1 bis AC-8).

## Changelog

- 2026-05-22: Test-Manifest erstellt für Issue #299 TDD-RED-Phase
