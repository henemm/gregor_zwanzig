---
entity_id: bug_600_tdd_verhaltenstest_tests
type: tests
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [tests, workflow, tdd, documentation]
parent: bug_600_tdd_verhaltenstest
phase: phase5_tdd_red
---

# Bug #600 — TDD Verhaltenstest-Pflicht (Test-Manifest)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `tests/tdd/test_bug_600_tdd_verhaltenstest.py`.
Mappt die drei Test-Funktionen auf die Acceptance Criteria der Parent-Spec.

Parent-Spec: `docs/specs/modules/bug_600_tdd_verhaltenstest.md`

## Source

- **File:** `tests/tdd/test_bug_600_tdd_verhaltenstest.py`

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `claude_md_verbietet_dateiinhalt_checks` | AC-1 | CLAUDE.md enthält `file.read_text()`, `Verhaltensnachweis`/`Verhaltenstest` und `Playwright` im KEINE-MOCKED-TESTS-Block |
| `tdd_red_skill_verhaltenstest_pflicht` | AC-2 | `.claude/commands/4-tdd-red.md` enthält `Verhaltenstest-Pflicht` und `file.read_text()` nach dem MUST-BE-RED-Block |
| `spec_template_dateiinhalt_check_warnung` | AC-3 | `docs/specs/_template.md` enthält `Dateiinhalt` im Acceptance-Criteria-Block |

## Expected RED-State (vor Implementierung)

| Test | Erwartung (RED) | Begründung |
|---|---|---|
| `claude_md_verbietet_dateiinhalt_checks` | FAIL | `file.read_text()` steht noch nicht in CLAUDE.md |
| `tdd_red_skill_verhaltenstest_pflicht` | FAIL | `Verhaltenstest-Pflicht` steht noch nicht in 4-tdd-red.md |
| `spec_template_dateiinhalt_check_warnung` | FAIL | `Dateiinhalt` steht noch nicht im AC-Block von _template.md |
