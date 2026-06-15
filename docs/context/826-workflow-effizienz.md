# Context: #826 Workflow-Effizienz (Express-Pfad + Verdict-Pflicht + Token-Logging)

## Request Summary
Den 8-Phasen-Workflow für triviale Issues entschlacken (Express-Pfad), die Verdict-Lücke beim Abschluss schließen und Token-Verbrauch pro Workflow protokollieren.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `.claude/hooks/workflow.py:1142-1180` (`cmd_complete`) | Abschluss; prüft heute NUR Execution-Log, KEIN Verdict → AC-2 |
| `.claude/hooks/workflow.py:1032-1106` (`cmd_write_log`) | YAML-Log pro Workflow (phase_durations, gate_history); Andockpunkt AC-3 |
| `.claude/hooks/pre_commit_gate.py:276-308` | `_phase6b_was_run` + `_check_none_verdict_block` — Verdict-Logik existiert (Commit), wiederverwendbar für AC-2 |
| `.claude/hooks/staging_gate.py:102-145` (`_detect_committed_scope`) | Scope docs-only/frontend-only/backend/full-stack — Andockpunkt AC-1 |
| `.claude/hooks/scope_guard.py:66-108` (`_get_loc_delta`) | LoC-Delta berechenbar; `estimated_loc` (workflow.py:489) ist leerer Placeholder |
| `.claude/hooks/workflow.py:713-747` (`cmd_start`) | `workflow_type` feature/bugfix/docs; `docs` skippt phase6b bereits |

## Existing Patterns
- **Verdict-Tri-State:** `None | VERIFIED:.. | BROKEN:.. | AMBIGUOUS:..`, gesetzt von `qa_gate.py::_set_verdict`.
- **Phasen-Skip per workflow_type:** `docs` überspringt Adversary komplett, `bugfix` überspringt Phasen 1-3 — Express-Pfad kann an dieses Muster andocken.
- **Scope-basierter Gate-Skip:** `docs-only` überspringt Staging-Gate bereits (`staging_gate.py:256`).

## Dependencies
- Upstream: openspec.yaml (`max_loc_delta` Default 250), Session-Registry.
- Downstream: `pre_commit_gate`, `staging_gate`, `deploy-gregor-prod.sh` (Hard-Gate auf `e2e_verified.json`).

## Risks & Considerations
- **AC-1 schwächt Gates** — Express-Pfad darf nur für echt triviale Diffs greifen, sonst Gate-Erosion (genau das Gegenteil des Issue-Ziels). Stichprobe statt bedingungslosem Skip.
- **AC-3 Feasibility-Risiko** — Harness exponiert Token-Usage NICHT als Hook-ENV. Quelle wäre Session-Transcript (`~/.claude/projects/.../*.jsonl`); ob dort pro-Turn-`usage` steht, ist unbestätigt → Spike nötig.
- **LoC-Limit:** Drei ACs zusammen sprengen 250 LoC → spricht für Sequenzierung in getrennte Workflows.
