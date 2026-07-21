---
entity_id: issue_583_archive_demo_data_tests
type: tests
created: 2026-06-04
updated: 2026-06-05
status: draft
version: "1.1"
tags: [tests, design-fidelity, issue-583, issue-611, epic-575]
parent: issue_583_archiv_1to1
phase: phase5_tdd_red
---

# Issue #583/#611 — Demo-Archiv-Trips + Compare-Presets Seed-Tests

## Approval

- [x] Approved

## Purpose

Test-Manifest für AC-1 von Issue #583 und AC-2 von Issue #611. Validiert dass das Seed-Script
für den Validator-Account existiert, die richtigen 8 Trips schreibt, idempotent ist und
archivierte Orts-Vergleiche (ComparePresets) mit `archived_at` + `location_ids` anlegt.

Parent-Specs: `docs/specs/modules/issue_583_archiv_1to1.md`,
`docs/specs/modules/issue_611_archiv_entruempeln.md`.

## Source

- **File:** `tests/tdd/test_issue_583_archive_demo_data.py`

## Test → AC Mapping

| Test-Funktion-Entity | AC | Was wird geprüft |
|---------------------|----|------------------|
| `issue_583_ac1_script_exists` | AC-1.1 | `scripts/seed_validator_archive.py` existiert |
| `issue_583_ac1_creates_8_archived_trips` | AC-1.2 | Script schreibt 8 Trip-JSONs mit Pflichtfeldern (name, archived_at) — ohne Analytik-Felder (#611 AC-9) |
| `issue_583_ac1_idempotent` | AC-1.3 | Mehrfach-Ausführung erzeugt genau 8 Trips (kein Duplikat-Fehler) |
| `issue_611_seeds_archived_compare_presets` | AC-2 | Script schreibt compare_presets.json mit ≥2 Einträgen, jeder mit archived_at + nicht-leerer location_ids |

## Test-Strategie

- Echte Subprocess-Aufrufe gegen das Seed-Script (kein Mock).
- Tmp-Verzeichnis als data-Root (`--data-dir` Flag), kein Eingriff in echte Daten.
- JSON-Strukturprüfung auf real geschriebenen Dateien.

## TDD-RED-Erwartung

Tests schlagen fehl bis `scripts/seed_validator_archive.py` existiert
und die in den Parent-Specs definierten Daten ablegt.
