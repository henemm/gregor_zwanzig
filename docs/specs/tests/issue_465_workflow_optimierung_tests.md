---
entity_id: issue_465_workflow_optimierung_tests
type: tests
created: 2026-05-30
updated: 2026-05-30
status: draft
version: "1.0"
tags: [tests, feature, workflow, infrastructure, hooks, issue-465]
parent: issue_465_workflow_optimierung
phase: phase5_tdd_red
---

# Issue #465 — Workflow-Optimierung: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_465_workflow_optimierung.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.
Subprocess-Tests gegen echte On-Disk-Workflow-JSON-Files. Keine Mocks.

Parent-Spec: `docs/specs/modules/issue_465_workflow_optimierung.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_465_workflow_optimierung.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_start_type_bugfix_sets_phase4_approved` | AC-1 | `start --type bugfix` setzt workflow_type=bugfix, current_phase=phase4_approved, Skip-Transitions für Phase 1–3 |
| `test_ac2_start_type_docs_sets_phase3_spec` | AC-2 | `start --type docs` setzt workflow_type=docs, current_phase=phase3_spec, Skips für Phase 1+2+5+6b+7 |
| `test_ac3_start_type_invalid_exits_with_error` | AC-3 | `start --type invalid` liefert Exit-Code != 0 |
| `test_ac4_stats_shows_verdict_distribution` | AC-4 | `stats` zeigt VERIFIED/BROKEN/AMBIGUOUS mit Zahlen |
| `test_ac5_stats_json_flag_outputs_valid_json` | AC-5 | `stats --json` liefert valides JSON mit total_workflows, verdicts, verdict_rate |
| `test_ac6_auto_advance_spec_advances_from_phase1` | AC-6 | `auto-advance-spec` bei phase1_context + Flag=true → phase2_analyse + trigger=auto:spec_advance |
| `test_ac7_auto_advance_spec_noop_when_flag_false` | AC-7 | `auto-advance-spec` bei Flag=false → kein-op, Phase bleibt |
| `test_ac9_write_log_contains_phase_durations` | AC-9 | `write-log` schreibt phase_durations-Dict und workflow_type ins YAML |
| `test_ac10_email_validator_creates_yaml_log` | AC-10 | `_write_validation_log()` erstellt YAML in _log/ mit korrekten Feldern |

## Ausgelassene ACs

- **AC-8** (Parallel-Session-Info): Benötigt echte Session-Registry mit laufendem Prozess — manueller Staging-Test.
