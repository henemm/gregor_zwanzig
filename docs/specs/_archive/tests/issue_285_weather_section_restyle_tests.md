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
| `test_ac4c_no_bg_primary_in_weather_config_dialog` | AC-4 | `WeatherConfigDialog.svelte` enthält kein `bg-primary` |
| `test_ac4d_no_text_primary_foreground_in_weather_config_dialog` | AC-4 | `WeatherConfigDialog.svelte` enthält kein `text-primary-foreground` |
| `test_segmented_svelte_exists` | Neu | `Segmented.svelte` unter `ui/segmented/` existiert |
| `test_segmented_index_exists` | Neu | `index.ts` unter `ui/segmented/` existiert |
| `test_segmented_svelte_uses_data_slot` | AC-1/AC-2 | `Segmented.svelte` hat `data-slot="segmented"` und `data-slot="segmented-item"` |
| `test_segmented_svelte_uses_data_active` | AC-6 | `Segmented.svelte` setzt `data-active` Attribut |
| `test_app_css_has_segmented_slot` | CSS | `app.css` enthält `[data-slot="segmented"]` Block |
| `test_app_css_has_segmented_item_slot` | CSS | `app.css` enthält `[data-slot="segmented-item"]` Block |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests außer AC-5 sollen FAIL sein)
uv run pytest tests/tdd/test_issue_285_weather_section_restyle.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_285_weather_section_restyle.py -v
```

## Expected RED-State (vor GREEN-Phase)

Der ursprüngliche RED-Nachweis (vor #285-Implementierung) ist historisch; die
#285-Implementierung ist längst grün. Diese Tabelle bleibt als Referenz für die
weiterhin gültigen Tests bestehen.

| Test | Status nach #285 + #345 |
|------|--------------------------|
| `test_ac4c_no_bg_primary_in_weather_config_dialog` | PASS |
| `test_ac4d_no_text_primary_foreground_in_weather_config_dialog` | PASS |
| `test_segmented_svelte_exists` | PASS |
| `test_segmented_index_exists` | PASS |
| `test_segmented_svelte_uses_data_slot` | PASS |
| `test_segmented_svelte_uses_data_active` | PASS |
| `test_app_css_has_segmented_slot` | PASS |
| `test_app_css_has_segmented_item_slot` | PASS |

## Changelog

- 2026-05-21: Initial test manifest erstellt für Issue #285 (Weather Section Restyle).
- 2026-05-25: Issue #345 — `EditWeatherSection.svelte` gelöscht (Wetter-Editor-
  Konsolidierung). Die 5 Tests gegen `EditWeatherSection.svelte` entfernt
  (`test_ac4a`/`test_ac4b`/`test_ac3`/`test_ac5_testids_preserved`/
  `test_edit_weather_section_imports_segmented`). WeatherConfigDialog- und
  Segmented-/app.css-Tests unverändert. Die Brand-Token-Compliance der neuen
  read-only `WeatherSummaryCard.svelte` ist durch deren Implementierung
  (ausschließlich `var(--g-*)`, keine Hex, keine verbotenen Tailwind-Klassen)
  sowie die TS-Tests `weatherSummary.test.ts` abgedeckt.
