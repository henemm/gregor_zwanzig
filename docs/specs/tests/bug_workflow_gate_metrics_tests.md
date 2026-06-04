---
entity_id: bug_workflow_gate_metrics_tests
type: tests
created: 2026-06-04
updated: 2026-06-04
status: draft
version: "1.0"
tags: [tests, bug, workflow, metrics, debug, gate-history]
parent: bug_workflow_gate_metrics
phase: phase5_tdd_red
---

# bug-workflow-gate-metrics — Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/bug_workflow_gate_metrics.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec.
Subprocess-Tests gegen echte On-Disk-Workflow-JSON-Files. Keine Mocks.

Parent-Spec: `docs/specs/modules/bug_workflow_gate_metrics.md` v1.0

## Source

- **File:** `tests/tdd/test_bug_workflow_gate_metrics.py` (NEU)

## Test-Tabelle

| Test-Funktion | AC | Beschreibung |
|--------------|-----|-------------|
| `test_ac1_gate_history_user_approved_in_log` | AC-1 | write-log mit user_keyword-Transition → gate_history.spec_approval=user_approved |
| `test_ac2_gate_history_bypassed_when_command_trigger` | AC-2 | phase3→phase5 direkt per command → spec_approval=bypassed, gate_anomalies=1 |
| `test_ac3_gates_command_shows_all_three_gates` | AC-3 | `workflow.py gates` gibt alle 3 Gate-Punkte mit Status aus |
| `test_ac4_debug_output_when_go_has_no_effect` | AC-4 | "go" ohne Gate-Effekt → stderr [DEBUG go]-Zeile in workflow_state_updater.py |

## Annahmen

- Tests laufen gegen echte On-Disk-JSON-Dateien in `tmp_path`
- Keine Mocks, keine Patches
- `_inject_transitions()` Helper überschreibt phase_transitions direkt in JSON
