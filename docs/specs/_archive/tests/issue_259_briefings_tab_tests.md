---
entity_id: issue_259_briefings_tab_tests
type: tests
created: 2026-05-19
updated: 2026-05-19
status: draft
version: "1.0"
tags: [tests, briefings, frontend, svelte, issue-259, epic-135]
parent: issue_259_briefings_tab
phase: phase5_tdd_red
---

# Issue #259 — Briefing-Zeitplan-Tab (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/issue_259_briefings_tab.md`.
Da Issue #259 rein Frontend ist (Svelte-Komponenten, kein Python-Code),
prüfen die Tests Datei-Existenz und Inhalts-Invarianten der Svelte-Dateien.

## Source

- **File:** `tests/tdd/test_issue_259_briefings_tab.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_issue_259_briefings_tab.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_briefings_tab_svelte_exists` | AC-1 | `briefings-tab/BriefingsTab.svelte` existiert |
| `test_ac1_trip_tabs_has_briefings_branch` | AC-1 | TripTabs.svelte hat `briefings`-Branch mit `BriefingsTab` |
| `test_ac1_placeholder_removed_from_trip_tabs` | AC-1 | Platzhalter-Text "Inhalt folgt mit Issue #159" entfernt |
| `test_ac2_briefings_tab_imports_edit_report_config` | AC-2 | BriefingsTab.svelte importiert `EditReportConfigSection` |
| `test_ac2_briefings_tab_binds_report_config` | AC-2 | BriefingsTab.svelte bindet `reportConfig` per `bind:reportConfig` |
| `test_ac3_briefings_tab_calls_api_put` | AC-3 | BriefingsTab.svelte enthält `api.put` |
| `test_ac3_briefings_tab_puts_report_config` | AC-3 | BriefingsTab.svelte enthält `report_config` im PUT-Payload |
| `test_ac3_briefings_tab_uses_trip_id` | AC-3 | BriefingsTab.svelte baut PUT-URL mit `trip.id` |
| `test_ac4_briefings_tab_has_save_success_testid` | AC-4 | BriefingsTab.svelte enthält `data-testid='briefings-tab-save-success'` |
| `test_ac4_briefings_tab_has_save_success_state` | AC-4 | BriefingsTab.svelte hat `saveSuccess`-State |
| `test_ac5_briefings_tab_has_save_error_testid` | AC-5 | BriefingsTab.svelte enthält `data-testid='briefings-tab-save-error'` |
| `test_ac5_briefings_tab_has_save_error_state` | AC-5 | BriefingsTab.svelte hat `saveError`-State |
| `test_ac6_briefings_tab_has_save_button_testid` | AC-6 | BriefingsTab.svelte enthält `data-testid='briefings-tab-save'` |
| `test_ac6_briefings_tab_button_disabled_while_saving` | AC-6 | BriefingsTab.svelte setzt `disabled={saving}` am Button |

## Implementation Details

Tests im RED-Modus schlagen fehl, weil:
- `BriefingsTab.svelte` noch nicht existiert
  → `FileNotFoundError` bei `BRIEFINGS_TAB.exists()` (returns False) → AssertionError
- `TripTabs.svelte` enthält noch keinen `briefings`-Branch mit `BriefingsTab`
  → Assertion `'BriefingsTab' in content` schlägt fehl
- Platzhalter-Text noch in `TripTabs.svelte` vorhanden
  → Assertion `'Inhalt folgt mit Issue #159' not in content` schlägt fehl

In GREEN-Phase bestehen alle Tests, wenn:
- `BriefingsTab.svelte` mit den erwarteten Inhalten erstellt wurde
- `TripTabs.svelte` den `briefings`-Branch enthält und den Platzhalter entfernt hat

## Acceptance Criteria

- **AC-T1:** Given die Implementierung fehlt /
  When `pytest tests/tdd/test_issue_259_briefings_tab.py -v` läuft /
  Then schlagen alle 14 Tests fehl (RED-Phase).

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When `pytest tests/tdd/test_issue_259_briefings_tab.py -v` läuft /
  Then sind alle 14 Tests grün.

## Changelog

- 2026-05-19: Initial — Test-Manifest für Issue #259.
