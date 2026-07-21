---
entity_id: issue_753_746_hygiene_tests
type: tests
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [tests, tooling, hygiene, issue-753, issue-746, doc-compliance]
parent: issue_753_746_test_hygiene_and_planner_checkpoint
phase: phase5_tdd_red
---

# Issue #753 + #746 — Test-Hygiene & Planner-Checkpoint: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_753_746_test_hygiene_and_planner_checkpoint.md`.
Alle Tests sind `# doc-compliance-test` (Workflow-Artefakte werden geprüft, kein Produktionscode).

Parent-Spec: `docs/specs/modules/issue_753_746_test_hygiene_and_planner_checkpoint.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_753_746_hygiene.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_forbidden_filecontent_test_removed` | AC-1 | `tests/tdd/test_issue_299_edit_report_config_polish.py` existiert nicht mehr |
| `test_no_test_reads_editreportconfig_source` | AC-1 | Kein Test in `tests/tdd/` liest `EditReportConfigSection.svelte` per `read_text()` |
| `test_obsolete_spec_removed` | AC-3 | `docs/specs/modules/issue_299_edit_report_config_section_polish.md` ist entfernt |
| `test_planner_has_po_checkpoint_before_phase5` | AC-4 | `user-story-planner.md` hat einen PFLICHT-Checkpoint mit Bestätigungs-Erwartung zwischen Phase 4 und Phase 5 |
| `test_planner_checkpoint_mandates_stop` | AC-5 | Der Checkpoint schreibt STOP vor (keine Issues / kein Dokument ohne Bestätigung) |

Hinweis: AC-2 (Suite läuft sauber) wird durch einen echten `uv run pytest`-Gesamtlauf in der Validierungsphase verifiziert, nicht durch einen Datei-Inhalt-Check.

## Test-Ausführung

```bash
uv run pytest tests/tdd/test_issue_753_746_hygiene.py -v
```

## Changelog

- 2026-06-11: Initial Test-Manifest — Issues #753, #746
