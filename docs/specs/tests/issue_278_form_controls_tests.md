---
entity_id: issue_278_form_controls_tests
type: tests
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [tests, frontend, svelte5, ui-primitive, checkbox, select, design-system, issue-278]
parent: issue_278_form_controls
phase: phase5_tdd_red
---

# Issue #278 — Gebrandete Form-Controls: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_278_form_controls.md`.
Da Issue #278 rein Frontend ist (Svelte-Komponenten, kein Python-Code),
prüfen die Tests Datei-Existenz und Inhalts-Invarianten der Svelte-Dateien
sowie die vollständige Migration aller nativen Checkboxen und Selects.

Parent-Spec: `docs/specs/modules/issue_278_form_controls.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_278_form_controls.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_issue_278_form_controls.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_checkbox_svelte_exists` | AC-1 | `ui/checkbox/Checkbox.svelte` existiert |
| `test_ac1_checkbox_index_exists` | AC-1 | `ui/checkbox/index.ts` existiert und exportiert Checkbox |
| `test_ac1_checkbox_has_bindable_checked` | AC-1 | Checkbox.svelte enthält `$bindable()` für checked-Prop |
| `test_ac1_checkbox_has_rest_props` | AC-1 | Checkbox.svelte leitet `...restProps` an nativen Input weiter |
| `test_ac1_checkbox_native_input_is_opacity_zero` | AC-1 | input ist `opacity: 0`, KEIN `pointer-events: none` (Playwright-Kompatibilität) |
| `test_ac1_checkbox_checked_state_uses_ink_token` | AC-1 | checked-State nutzt `--g-ink` (kein system-blau) |
| `test_ac1_checkbox_focus_ring_uses_accent_token` | AC-1/AC-7 | Focus-Ring nutzt `--g-accent` |
| `test_ac2_select_svelte_exists` | AC-2 | `ui/select/Select.svelte` existiert |
| `test_ac2_select_index_exists` | AC-2 | `ui/select/index.ts` existiert und exportiert Select |
| `test_ac2_select_has_bindable_value` | AC-2 | Select.svelte enthält `$bindable()` für value-Prop |
| `test_ac2_select_has_appearance_none` | AC-2/AC-8 | Select hat `appearance: none` (entfernt System-Chevron) |
| `test_ac2_select_has_custom_chevron` | AC-2/AC-8 | Select enthält SVG-Chevron-Element |
| `test_ac2_select_uses_design_tokens` | AC-2 | Select nutzt `--g-ink-faint`, `--g-paper`, `--g-radius-sm` |
| `test_ac3_no_native_checkboxes_outside_component` | AC-3 | `rg 'type="checkbox"'` findet Treffer NUR in `Checkbox.svelte` |
| `test_ac4_no_native_selects_outside_component` | AC-4 | `rg '<select\b'` findet Treffer NUR in `Select.svelte` |
| `test_ac6_checkbox_restprops_on_native_input` | AC-6 | restProps landen auf `<input>` in Checkbox.svelte |
| `test_ac6_select_restprops_on_native_select` | AC-6 | restProps landen auf `<select>` in Select.svelte |
| `test_ac8_select_native_has_appearance_none_not_only_vendor` | AC-8 | `appearance: none` (Standard + ggf. -webkit-) vorhanden |
| `test_key_files_import_checkbox` | AC-3 | Schlüsseldateien (EditReportConfigSection, EditWeather, AlertRuleRow, LocationsRail, SubscriptionForm) importieren Checkbox |
| `test_key_files_import_select` | AC-4 | Schlüsseldateien (AlertRuleRow, AlertMetricRow, EditWeather, PresetHeader, SubscriptionForm) importieren Select |

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_ac1_checkbox_svelte_exists` | FAIL | Datei existiert noch nicht |
| `test_ac1_checkbox_index_exists` | FAIL | Datei existiert noch nicht |
| `test_ac1_checkbox_has_bindable_checked` | FAIL | Datei existiert noch nicht |
| `test_ac1_checkbox_has_rest_props` | FAIL | Datei existiert noch nicht |
| `test_ac1_checkbox_native_input_is_opacity_zero` | FAIL | Datei existiert noch nicht |
| `test_ac1_checkbox_checked_state_uses_ink_token` | FAIL | Datei existiert noch nicht |
| `test_ac1_checkbox_focus_ring_uses_accent_token` | FAIL | Datei existiert noch nicht |
| `test_ac2_select_svelte_exists` | FAIL | Datei existiert noch nicht |
| `test_ac2_select_index_exists` | FAIL | Datei existiert noch nicht |
| `test_ac2_select_has_bindable_value` | FAIL | Datei existiert noch nicht |
| `test_ac2_select_has_appearance_none` | FAIL | Datei existiert noch nicht |
| `test_ac2_select_has_custom_chevron` | FAIL | Datei existiert noch nicht |
| `test_ac2_select_uses_design_tokens` | FAIL | Datei existiert noch nicht |
| `test_ac3_no_native_checkboxes_outside_component` | FAIL | 35+ native Checkboxen in 11 Dateien |
| `test_ac4_no_native_selects_outside_component` | FAIL | ~20 native Selects in 10 Dateien |
| `test_ac6_checkbox_restprops_on_native_input` | FAIL | Datei existiert noch nicht |
| `test_ac6_select_restprops_on_native_select` | FAIL | Datei existiert noch nicht |
| `test_ac8_select_native_has_appearance_none_not_only_vendor` | FAIL | Datei existiert noch nicht |
| `test_key_files_import_checkbox` | FAIL | Kein Import in Zieldateien vorhanden |
| `test_key_files_import_select` | FAIL | Kein Import in Zieldateien vorhanden |

Alle 20 Tests müssen im RED-Zustand FAIL sein — das ist der RED-Beweis.

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_issue_278_form_controls.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_278_form_controls.py -v
```

## Changelog

- 2026-05-20: Initial test manifest erstellt für Issue #278 (Checkbox + Select UI-Primitive).
