---
entity_id: bug_272_ios_input_font_size_tests
type: tests
created: 2026-05-20
updated: 2026-05-20
status: draft
version: "1.0"
tags: [tests, bugfix, ios, safari, mobile, font-size, zoom, frontend, issue-272]
parent: bug_272_ios_input_font_size
phase: phase5_tdd_red
---

# Bug #272 — iOS-Auto-Zoom: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_272_ios_input_font_size.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_272_ios_input_font_size.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_272_ios_input_font_size.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_files_exist` | Struktur | `app.css` und `SavePresetDialog.svelte` existieren im Repo |
| `test_ac1_app_css_contains_mobile_media_query` | AC-1/AC-2 | `app.css` enthält `@media (max-width: 767px)` |
| `test_ac1_app_css_mobile_query_sets_input_font_size_16px` | AC-1/AC-2/AC-5 | `@media (max-width: 767px) { input, select, textarea { font-size: 16px } }` in `app.css` |
| `test_ac3_app_css_mobile_rule_is_unlayered` | AC-3 | iOS-Fix-Regel steht nach letztem `@layer` in `app.css` (unlayered = übersteuert Tailwind) |
| `test_ac4_save_preset_dialog_has_mobile_textarea_override` | AC-4 | `SavePresetDialog.svelte` enthält Scoped Override `@media (max-width: 767px) { .field textarea { font-size: 16px } }` |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_bug_272_ios_input_font_size.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_bug_272_ios_input_font_size.py -v
```

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_files_exist` | PASS | Dateien existieren bereits |
| `test_ac1_app_css_contains_mobile_media_query` | FAIL | `@media (max-width: 767px)` noch nicht in `app.css` |
| `test_ac1_app_css_mobile_query_sets_input_font_size_16px` | FAIL | Regel noch nicht vorhanden |
| `test_ac3_app_css_mobile_rule_is_unlayered` | FAIL | Regel fehlt, Assertion über Position schlägt fehl |
| `test_ac4_save_preset_dialog_has_mobile_textarea_override` | FAIL | Scoped Override noch nicht in `SavePresetDialog.svelte` |

Mindestens 4 von 5 Tests müssen FAIL liefern — das ist der RED-Beweis.

## Changelog

- 2026-05-20: Initial test manifest erstellt für Bug #272 (iOS-Auto-Zoom Font-Size-Fix).
