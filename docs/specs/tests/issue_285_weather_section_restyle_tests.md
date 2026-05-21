---
entity_id: issue_285_weather_section_restyle_tests
type: tests
created: 2026-05-21
updated: 2026-05-21
status: draft
version: "1.0"
tags: [tests, frontend, restyle, segmented-control, brand-tokens, issue-285]
parent: issue_285_weather_section_restyle
phase: phase5_tdd_red
---

# Issue #285 — Weather Section Restyle: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_285_weather_section_restyle.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_285_weather_section_restyle.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_285_weather_section_restyle.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac4a_no_bg_primary_in_edit_weather_section` | AC-4 | `EditWeatherSection.svelte` enthält kein `bg-primary` |
| `test_ac4b_no_text_primary_foreground_in_edit_weather_section` | AC-4 | `EditWeatherSection.svelte` enthält kein `text-primary-foreground` |
| `test_ac4c_no_bg_primary_in_weather_config_dialog` | AC-4 | `WeatherConfigDialog.svelte` enthält kein `bg-primary` |
| `test_ac4d_no_text_primary_foreground_in_weather_config_dialog` | AC-4 | `WeatherConfigDialog.svelte` enthält kein `text-primary-foreground` |
| `test_ac3_no_hover_bg_muted_in_edit_weather_section` | AC-3 | `EditWeatherSection.svelte` enthält kein `hover:bg-muted` |
| `test_segmented_svelte_exists` | Neu | `Segmented.svelte` unter `ui/segmented/` existiert |
| `test_segmented_index_exists` | Neu | `index.ts` unter `ui/segmented/` existiert |
| `test_segmented_svelte_uses_data_slot` | AC-1/AC-2 | `Segmented.svelte` hat `data-slot="segmented"` und `data-slot="segmented-item"` |
| `test_segmented_svelte_uses_data_active` | AC-6 | `Segmented.svelte` setzt `data-active` Attribut |
| `test_app_css_has_segmented_slot` | CSS | `app.css` enthält `[data-slot="segmented"]` Block |
| `test_app_css_has_segmented_item_slot` | CSS | `app.css` enthält `[data-slot="segmented-item"]` Block |
| `test_ac5_testids_preserved_in_edit_weather_section` | AC-5 | Alle 3 Testids erhalten: `edit-weather-section`, `weather-template-select`, `metric-checkbox-` |
| `test_edit_weather_section_imports_segmented` | Impl | `EditWeatherSection.svelte` importiert `segmented` |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests außer AC-5 sollen FAIL sein)
uv run pytest tests/tdd/test_issue_285_weather_section_restyle.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_285_weather_section_restyle.py -v
```

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartetes Ergebnis | Grund |
|------|---------------------|-------|
| `test_ac4a_no_bg_primary_in_edit_weather_section` | FAIL | `bg-primary` noch in EditWeatherSection.svelte (Zeilen 213, 218) |
| `test_ac4b_no_text_primary_foreground_in_edit_weather_section` | FAIL | `text-primary-foreground` noch vorhanden |
| `test_ac4c_no_bg_primary_in_weather_config_dialog` | FAIL | `bg-primary` noch in WeatherConfigDialog.svelte (Zeilen 210, 215) |
| `test_ac4d_no_text_primary_foreground_in_weather_config_dialog` | FAIL | `text-primary-foreground` noch vorhanden |
| `test_ac3_no_hover_bg_muted_in_edit_weather_section` | FAIL | `hover:bg-muted/50` noch vorhanden (Zeile 201) |
| `test_segmented_svelte_exists` | FAIL | Datei existiert noch nicht |
| `test_segmented_index_exists` | FAIL | Datei existiert noch nicht |
| `test_segmented_svelte_uses_data_slot` | FAIL | Datei existiert noch nicht |
| `test_segmented_svelte_uses_data_active` | FAIL | Datei existiert noch nicht |
| `test_app_css_has_segmented_slot` | FAIL | CSS-Block noch nicht in `app.css` |
| `test_app_css_has_segmented_item_slot` | FAIL | CSS-Block noch nicht in `app.css` |
| `test_ac5_testids_preserved_in_edit_weather_section` | PASS | Testids schon vorhanden (Regression Guard) |
| `test_edit_weather_section_imports_segmented` | FAIL | Import noch nicht ergänzt |

Mindestens 12 von 13 Tests müssen FAIL liefern — das ist der RED-Beweis.

## Changelog

- 2026-05-21: Initial test manifest erstellt für Issue #285 (Weather Section Restyle).
