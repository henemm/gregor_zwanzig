---
entity_id: epic_129a_2_gpx_helpers_tests
type: tests
created: 2026-05-12
updated: 2026-05-12
status: draft
version: "1.0"
tags: [tests, refactor, epic-129, services-extraction]
parent: epic_129a_2_gpx_helpers
phase: phase5_tdd_red
---

# Epic #129 Phase A.2 — GPX-Helper + Coordinates (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer die GPX-Helper- und Coordinates-Extraktion aus
`src/web/pages/gpx_upload.py`, `src/web/pages/trips.py` und `src/web/utils.py`
nach `src/services/`. Jeder Eintrag mappt einen pytest-Funktionsnamen auf das
in der Parent-Spec definierte Acceptance-Criterion.

Parent-Modul-Spec: `docs/specs/epic_129a_2_gpx_helpers.md`.

## Source

- **Files:**
  - `tests/refactor/test_epic_129a_2_module_structure.py` (NEU — Modul-Struktur-Pruefung)
- **Spec:** `docs/specs/epic_129a_2_gpx_helpers.md` v1.0

## Test Inventory

Die Test-Funktionsnamen verwenden Bezeichner aus der Parent-Spec, damit der
Spec-Enforcement-Hook sie aufloesen kann. Die Mapping-Tabelle dokumentiert,
welcher Test welches Acceptance-Criterion abdeckt.

### Refactor-Strukturpruefung (`tests/refactor/test_epic_129a_2_module_structure.py`)

| Test-Funktion | AC | Was geprueft wird |
|---------------|----|------------------|
| `test_gpx_helpers_externals_clean` | AC-1 | grep auf `from web.pages.trips`, `from web.pages.gpx_upload`, `from web.utils` (und `src.`-Varianten) in den 5 betroffenen externen Importeuren — keine Treffer mehr. |
| `test_coordinates_module` | AC-2 (coordinates) | `services.coordinates` existiert und exportiert `parse_dms_coordinates`. |
| `test_gpx_processing_module` | AC-2 (gpx_processing) | `services.gpx_processing` exportiert `process_gpx_upload`, `compute_full_segmentation`, `segments_to_trip`, `gpx_to_stage_data`, `process_bulk_gpx_uploads`, `compute_default_start_date`. |
| `test_gpx_to_stage_data_signature` | AC-3 | `inspect.signature(services.gpx_processing.gpx_to_stage_data)` enthaelt die Parameter `content`, `filename`, `stage_date`, `start_hour`, `upload_dir` (API-Contract stabil). |
| `test_pages_loadable` | AC-4 | `web.pages.gpx_upload` und `web.pages.trips` laden ohne ImportError und exposen via Re-Imports `render_gpx_upload`, `render_trips`, `process_gpx_upload`, `gpx_to_stage_data`, `parse_dms_coordinates`. |
| `test_dead_format_decimal_to_dms_removed` | AC-5 (dead-fn) | grep ueber das Repo: `def format_decimal_to_dms` ist vollstaendig entfernt. |
| `test_web_utils_file_removed` | AC-5 (utils-file) | `src/web/utils.py` existiert nicht mehr (oder ist leer). |

## Expected RED-State (vor GREEN-Phase)

| Test | Erwartung in Phase 5 (RED) | Begruendung |
|------|----------------------------|-------------|
| `test_gpx_helpers_externals_clean` | FAIL | Externe Importe stehen heute noch in den 5 Dateien. |
| `test_coordinates_module` | FAIL | Modul `services.coordinates` existiert noch nicht. |
| `test_gpx_processing_module` | FAIL | Modul `services.gpx_processing` existiert noch nicht. |
| `test_gpx_to_stage_data_signature` | FAIL | Funktion existiert nur unter `web.pages.trips`, nicht unter `services.gpx_processing`. |
| `test_pages_loadable` | gemischt — `render_*` ist GREEN, `parse_dms_coordinates`-Re-Import in `gpx_upload.py` ist FAIL | Aktuell exposed `gpx_upload.py` zwar `process_gpx_upload`, aber `parse_dms_coordinates` fehlt als Re-Import. `trips.py` importiert es zwar via `web.utils`, aber Test prueft den neuen Pfad. |
| `test_dead_format_decimal_to_dms_removed` | FAIL | `def format_decimal_to_dms` ist heute noch in `src/web/utils.py` definiert. |
| `test_web_utils_file_removed` | FAIL | `src/web/utils.py` existiert heute. |

Mindestens AC-2, AC-3 und AC-5 muessen FAIL liefern — das ist der RED-Beweis.

## Verification

- **Scoped Run:** `uv run pytest tests/refactor/test_epic_129a_2_module_structure.py -v`
- **Phase 5 RED:** Alle 7 Tests rot (oder mit Teil-GREEN bei `test_pages_loadable`, falls Re-Imports zufaellig schon stehen).
- **Phase 6 GREEN:** Alle 7 Tests gruen — kein Mock, keine Stubs, reale Imports + reale grep-Outputs.

## Out of Scope

- Funktionale Pruefung der extrahierten Helper (GPX-Parsing-Logik, Segmentation-Korrektheit) — wird durch die bestehenden TDD-/Unit-Tests `test_gpx_upload_page.py`, `test_gpx_import_in_trip_dialog.py`, `test_etappen_config.py`, `test_trips_time_window_bugfix.py` abgedeckt, die in der GREEN-Phase auf die neuen Modul-Pfade umgestellt werden.

## Changelog

- 2026-05-12: Initial test manifest for epic-129a-2 gpx-helpers extraction.
