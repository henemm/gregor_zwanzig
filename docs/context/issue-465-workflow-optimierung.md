# Context: Issue #465 — Workflow-Optimierung (Typen, Auto-Advance, Observability)

## Request Summary

8 konkrete Verbesserungen am OpenSpec-Workflow-System in drei Bereichen:
weniger unnötige User-Unterbrechungen, bessere Qualitätskontrolle zur Laufzeit,
und Datenbasis für zukünftige Analyse der Workflow-Effizienz.

## Änderungen im Überblick

| # | Änderung | Betroffene Dateien |
|---|----------|-------------------|
| 1 | Workflow-Typen (`--type feature\|bugfix\|docs`) | `workflow.py` (cmd_start, _new_workflow, cmd_status) |
| 2 | Spec Auto-Advance (Phasen 1–3 ohne User-Break) | `workflow.py`, `workflow_state_updater.py`, `settings.json` |
| 3 | LoC-Schätzung Pflichtfeld in Spec | `docs/specs/_template.md` |
| 4 | Adversary-Scope erzwingen (`test_files:`) | `.claude/agents/implementation-validator.md` |
| 5 | Parallel-Session-Info beim Session-Start | `session_singleton_guard.py` (_do_register) |
| 6 | Phasen-Dauern messen | `workflow.py` (cmd_phase, cmd_advance, cmd_write_log) |
| 7 | Adversary-Verdict-Rate tracken (`workflow.py stats`) | `workflow.py` (neuer cmd_stats) |
| 8 | Validierungs-Qualität maschinenlesbar ins Log | `email_spec_validator.py`, `workflow.py` (cmd_write_log) |

## Related Files

| Datei | Relevanz |
|-------|----------|
| `.claude/hooks/workflow.py` | Kern: cmd_start, _new_workflow, cmd_phase, cmd_write_log, cmd_status — alle 8 Punkte berühren es |
| `.claude/hooks/workflow_state_updater.py` | Punkt 2: UserPromptSubmit-Hook für Auto-Advance und Keyword-Erkennung |
| `.claude/hooks/session_singleton_guard.py` | Punkt 5: _do_register schreibt Session-Eintrag, dort Parallel-Info ergänzen |
| `.claude/hooks/email_spec_validator.py` | Punkt 8: schreibt aktuell nur Exit-Code, kein strukturiertes Ergebnis |
| `.claude/agents/implementation-validator.md` | Punkt 4: Adversary-Briefing-Template erweitern |
| `docs/specs/_template.md` | Punkt 3: Pflichtfeld `## Geschätzte Implementierungsgröße (LoC)` |
| `.claude/settings.json` | Punkt 2: Feature-Flag `spec_auto_advance` (default: true) |

## Existing Patterns

### Workflow-State-Struktur (_new_workflow)
```python
{
  "name": name,
  "current_phase": "phase1_context",
  "adversary_verdict": None,
  "phase_transitions": [],   # [{from, to, at, trigger}]
  "fix_loop_iterations": 0,
  "phases_completed": [],
  ...
}
```
→ Neue Felder für Typ und LoC-Schätzung fügen sich hier ein.

### Phase-Transitions-Tracking
`cmd_phase` schreibt bereits `{from, to, at, trigger}` in `phase_transitions[]`.
Daraus lässt sich Dauer ableiten: `transitions[i+1].at - transitions[i].at`.
Kein neues Feld im JSON nötig — Berechnung beim Lesen (in cmd_write_log und cmd_stats).

### Execution-Log Format
`_log/<date>_<name>.yaml` enthält bereits: phases_completed, adversary_verdict,
adversary_fix_loop_iterations, outcome. Punkt 6+7+8 ergänzen weitere Felder.

### UserPromptSubmit-Hook (workflow_state_updater.py)
Erkennt bereits: `approved` → phase4, `go` → green_approved, `deployed` → complete.
Punkt 2 ergänzt: auto-advance beim Erreichen von phase3 ohne PO-Entscheidungs-Marker.

### LoC-Tracking (scope_guard)
`scope_guard._get_loc_delta()` + `cfg["max_loc_delta"]` bereits vorhanden.
`loc_limit_override` per `set-field` setzbar. Punkt 3 ergänzt nur das Spec-Template.

### Adversary-Scope (implementation-validator.md)
Aktuell: `pytest tests/` (global). Punkt 4: `test_files: [...]` als Pflichtfeld
im Briefing, Validator-Prompt auf „führe NUR diese Dateien aus" verschärfen.

## Dependencies

- **Upstream:** Python 3.x, PyYAML (für `_atomic_write_yaml`)
- **Downstream:** Alle Hooks die `workflow_state_multi.py` importieren (`workflow_gate`, `scope_guard`, `tdd_enforcement`, `red_test_gate`, `post_implementation_gate`)

## Bestehende Specs

- `docs/specs/modules/session_singleton_guard.md` — Spec für Singleton-Guard (Punkt 5)
- Kein eigenes Spec für workflow.py — es ist selbst Infrastruktur

## Risiken & Betrachtungen

- **Punkt 2 (Auto-Advance):** Das `approved`-Keyword bleibt erhalten — Breaking-Change-Risiko minimal. Feature-Flag `spec_auto_advance: false` in `settings.json` als Rückfall.
- **Punkt 1 (Typen):** `bugfix`-Typ überspringt Phase 1–2 — nur wenn Kontext-Dok vorhanden. Reversibel via `set-type feature`.
- **Punkt 6 (Dauern):** Berechnung aus bestehenden `phase_transitions[].at` — kein Breaking Change am JSON-Schema.
- **Punkt 7 (Stats):** Nur lesend aus `_log/*.yaml` — safe.
- **Punkt 8 (Validator-Log):** `email_spec_validator.py` endet mit `sys.exit(0/1)` — strukturiertes Ergebnis muss vor dem Exit geschrieben werden, nicht danach.
- **LoC-Counter:** Phasen 1–3 und Spec-Dateien zählen nicht gegen LoC-Limit. Diese Änderungen sind reine Infrastruktur (`.claude/hooks/`, `docs/`, `.claude/agents/`) und landen nicht im Source-LoC-Counter.
