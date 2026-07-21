---
entity_id: issue_819_visibility_catalog_tests
type: tests
created: 2026-06-14
updated: 2026-06-14
status: draft
version: "1.0"
tags: [tests, metric-catalog, visibility, issue-819]
parent: issue_819_visibility_catalog_honesty
phase: phase5_tdd_red
---

# Issue #819 — Visibility-Katalog-Ehrlichkeit (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für die Katalog-Ehrlichkeits-Bereinigung aus
`docs/specs/modules/issue_819_visibility_catalog_honesty.md`. Jeder pytest-Test mappt
1:1 auf ein Acceptance Criterion. AC-4 (Render-Inertness) wird durch den bestehenden
mock-freien Matrix-Test abgedeckt, nicht dupliziert.

Parent-Spec: `docs/specs/modules/issue_819_visibility_catalog_honesty.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_819_visibility_catalog.py` (NEU — Katalog- und
  Loader-Asserts für visibility, mock-frei)
- **Mitbearbeitet (RED):** `tests/red/test_issue_435_format_modes.py`,
  `tests/unit/test_weather_metrics_ux.py` — bestehende Asserts auf den neuen
  Katalog-Stand umgestellt.

## Test Inventory

### Python (`tests/tdd/test_issue_819_visibility_catalog.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_visibility_has_no_friendly_format` | AC-1 | `get_metric("visibility").has_friendly_format` ist `False` (friendly_label leer). |
| `test_ac2_visibility_only_raw_mode` | AC-2 | `format_modes == ("raw",)` und `default_format_mode == "raw"`. |
| `test_ac3_loader_resolves_legacy_friendly_to_raw` | AC-3 | Bestands-Config `use_friendly_format=True` für visibility löst über `loader._resolve_format_mode` auf "raw" auf. |

### AC-4 (Render-Inertness — kein neuer Test)

Abgedeckt durch `tests/tdd/test_issue_811_mode_matrix.py::test_visibility_numeric_km_no_english_word`
(mock-freier `render_email`-Lauf, km-Zahl ohne englisches Wort in beiden Modi).
Dieser Test bleibt vor UND nach dem Fix grün → beweist die Verhaltens-Inertness.

## Changelog

- 2026-06-14: Initial test manifest (RED-Phase #819).
