---
entity_id: issue_583_archive_demo_data_tests
type: tests
created: 2026-06-04
status: draft
version: "1.0"
tags: [tests, design-fidelity, issue-583, epic-575]
parent: issue_583_archiv_1to1
phase: phase5_tdd_red
---

# Issue #583 — Demo-Archiv-Trips Seed-Tests

## Approval

- [x] Approved

## Purpose

Test-Manifest für AC-1 von Issue #583. Validiert dass das Seed-Script
für die Validator-Account-Demo-Daten existiert, die richtigen 8 Trips
schreibt und idempotent ist.

Parent-Spec: `docs/specs/modules/issue_583_archiv_1to1.md`.

## Source

- **File:** `tests/tdd/test_issue_583_archive_demo_data.py`

## Test → AC Mapping

| Test-Funktion-Entity | AC | Was wird geprüft |
|---------------------|----|------------------|
| `issue_583_ac1_script_exists` | AC-1.1 | `scripts/seed_validator_archive.py` existiert |
| `issue_583_ac1_creates_8_archived_trips` | AC-1.2 | Script schreibt 8 Trip-JSONs mit allen Pflichtfeldern (name, accuracy_pct, headline, archived_at) |
| `issue_583_ac1_idempotent` | AC-1.3 | Mehrfach-Ausführung erzeugt genau 8 Trips (kein Duplikat-Fehler) |

## Test-Strategie

- Echte Subprocess-Aufrufe gegen das Seed-Script (kein Mock).
- Tmp-Verzeichnis als data-Root (`--data-dir` Flag), kein Eingriff in echte Daten.
- JSON-Strukturprüfung auf real geschriebenen Dateien.

## TDD-RED-Erwartung

Alle 3 Tests schlagen fehl bis `scripts/seed_validator_archive.py` existiert
und die in der Parent-Spec definierte `ARCHIVE_LIST`-Daten ablegt.
