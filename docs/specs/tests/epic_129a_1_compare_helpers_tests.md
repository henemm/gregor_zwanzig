---
entity_id: epic_129a_1_compare_helpers_tests
type: tests
created: 2026-05-12
updated: 2026-05-12
status: draft
version: "1.0"
tags: [tests, refactor, epic-129, services-extraction]
parent: epic_129a_1_compare_helpers
phase: phase5_tdd_red
---

# Epic #129 Phase A.1 — Compare-Helper-Extraktion (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer die Helper-Extraktion aus `src/web/pages/compare.py` nach
`src/services/`. Jeder Eintrag mappt einen pytest-Funktionsnamen auf das in der
Parent-Spec definierte Acceptance-Criterion.

Parent-Modul-Spec: `docs/specs/epic_129a_1_compare_helpers.md`.

## Source

- **Files:**
  - `tests/refactor/test_epic_129a_1_module_structure.py` (NEU — Modul-Struktur-Pruefung)
- **Spec:** `docs/specs/epic_129a_1_compare_helpers.md` v1.0

## Test Inventory

Die Test-Funktionsnamen verwenden Bezeichner aus der Parent-Spec, damit der
Spec-Enforcement-Hook sie aufloesen kann. Die Mapping-Tabelle dokumentiert,
welcher Test welches Acceptance-Criterion abdeckt.

### Refactor-Strukturpruefung (`tests/refactor/test_epic_129a_1_module_structure.py`)

| Test-Funktion | AC | Was geprueft wird |
|---------------|----|------------------|
| `test_compare_helpers` | AC-1 | grep auf `from web.pages.compare` in den 4 betroffenen externen Importeuren — keine Treffer mehr. |
| `test_comparison_scoring` | AC-2 (scoring) | `services.comparison_scoring` existiert und exportiert `calculate_score`. |
| `test_comparison_engine` | AC-2 (engine) | `services.comparison_engine` exportiert `ComparisonEngine`, `fetch_forecast_for_location`, `dict_to_comparison_result`. |
| `test_comparison_renderers` | AC-2 (renderers) | `services.comparison_renderers` exportiert `render_comparison_html` und `render_comparison_text`. |
| `test_compare_subscription` | AC-3 | `services.compare_subscription.run_comparison_for_subscription` ist callable und das umgebende Modul importiert NICHT mehr aus `web.pages.compare`. |
| `test_render_comparison_html` | AC-4 | `web.pages.compare` laedt ohne ImportError und exposed via Re-Imports `render_compare`, `ComparisonEngine`, `calculate_score`, `render_comparison_html`. |
| `test_calculate_score` | AC-5 | grep ueber das Repo: 6 tote Funktionen (`_format_score_cell`, `_format_temp_cell`, `_format_wind_cell`, `_format_wind_direction_cell`, `_format_snow_cell`, `filter_data_by_hours`) sind vollstaendig entfernt. |

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartung in Phase 5 (RED) | Begruendung |
|------|----------------------------|-------------|
| `test_compare_helpers` | kann GREEN sein | Externe Importe stehen heute noch in den 4 Dateien; Test wird nach Refactor GREEN. Aktuell FAIL erwartet. |
| `test_comparison_scoring` | FAIL | Modul existiert noch nicht. |
| `test_comparison_engine` | FAIL | Modul existiert noch nicht. |
| `test_comparison_renderers` | FAIL | Modul existiert noch nicht. |
| `test_compare_subscription` | FAIL | `compare_subscription.py` importiert heute aus `web.pages.compare`. |
| `test_render_comparison_html` | FAIL | Re-Imports existieren in `compare.py` noch nicht. |
| `test_calculate_score` | FAIL | Tote Funktionen sind heute noch in `compare.py` definiert. |

Mindestens AC-2, AC-3 und AC-5 muessen FAIL liefern — das ist der RED-Beweis.

## Verification

- **Scoped Run:** `uv run pytest tests/refactor/test_epic_129a_1_module_structure.py -v`
- **Phase 5 RED:** Alle 7 Tests rot (oder mit AC-1 als bereits grun, falls vor Test-Lauf schon umgezogen).
- **Phase 6 GREEN:** Alle 7 Tests gruen — kein Mock, keine Stubs, reale Imports + reale grep-Outputs.

## Out of Scope

- Funktionale Pruefung der extrahierten Helper (calculate_score-Logik, Renderer-HTML-Output) — wird durch die bestehenden TDD-Tests `test_compare_provider_routing.py` und `test_sport_aware_scoring.py` abgedeckt, die in der GREEN-Phase auf die neuen Modul-Pfade umgestellt werden.

## Changelog

- 2026-05-12: Initial test manifest for epic-129a-1 compare-helpers extraction.
