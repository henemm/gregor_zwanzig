---
entity_id: epic_191_logbuch_audit
type: module
created: 2026-05-11
updated: 2026-05-11
status: draft
version: "1.0"
tags: [hooks, workflow, logging, audit]
---

<!-- Issue #193 — Epic #191: Workflow Execution Log + Phase Transition Audit Trail -->

# Epic 191 — Logbuch & Audit Trail (Workflow B)

## Approval

- [ ] Approved

## Purpose

Nach jedem abgeschlossenen Workflow ein YAML-Logbuch in
`.claude/workflows/_log/YYYY-MM-DD_<name>.yaml` schreiben, das
Phasen-Verlauf, Adversary-Ergebnis, Fix-Loop-Iterationen und Scope-Delta
dokumentiert. `cmd_complete` blockiert ohne vorhandenes Log, und
Phase-Transitions werden mit `from/to/at/trigger` festgehalten — so
entsteht ein manipulationssicherer Audit-Trail der gesamten
Workflow-Ausführung.

## Source

- **File:** `.claude/hooks/workflow.py` — neue Subcommands `cmd_write_log`, erweiterte `cmd_complete`, `cmd_phase`, `cmd_status`
- **File:** `.claude/hooks/workflow_state_updater.py` — Patch: `set_phase()` statt direktem Dict-Edit + auto-`write_log` vor `complete`
- **File:** `.claude/hooks/workflow_state_multi.py` — Thin-Wrapper-Erweiterung: `set_phase()` delegiert mit explizitem `trigger`-Argument an `cmd_phase`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pathlib.Path` | stdlib | Pfad-Operationen, `_log/`-Verzeichnis-Erstellung |
| `datetime` | stdlib | ISO-8601-Timestamps für `completed_at` und `phase_transitions[].at` |
| `yaml` (PyYAML 6.0.1) | third-party | YAML-Serialisierung der Logbuch-Dateien |
| `epic_191_state_migration` Spec (`docs/specs/modules/epic_191_state_migration.md`) | Spec | `phase_transitions[]` und `fix_loop_iterations` Felder existieren bereits im State-Schema (Issue #192) |
| `_atomic_write` in `workflow.py` | intern | Atomares Schreiben der YAML-Logbuch-Dateien (wiederverwendet aus Workflow A) |
| `_get_workflows_root()` in `workflow.py` | intern | Worktree-sicherer Pfad zum `workflows/`-Verzeichnis |

## Implementation Details

### Log-Verzeichnis

```
.claude/workflows/
├── .active                                         (Symlink, Workflow A)
├── <name>.json                                     (aktiver Workflow)
└── _log/
    ├── 2026-05-11_epic-191-state-migration.yaml
    ├── 2026-05-11_epic-191-logbuch-audit.yaml
    └── ...
```

### YAML-Schema pro Logbuch-Datei

```yaml
workflow_id: epic-191-logbuch-audit
project: gregor_zwanzig
completed_at: 2026-05-11T13:45:00.000000
phases_completed:
  - phase1_context
  - phase2_analyse
  - phase3_spec
  - phase4_approved
  - phase5_tdd_red
  - phase6_implement
  - phase6b_adversary
  - phase7_validate
  - phase8_complete
phases_skipped: []
override_used: false
tdd_red_confirmed: true
adversary_verdict: VERIFIED
adversary_findings_total: 0
adversary_fix_loop_iterations: 0
scope_files_changed: 4
scope_loc_delta: "+360"
outcome: success
```

`phases_completed` wird aus `phase_transitions[].to` aggregiert.
`phases_skipped` enthält alle kanonischen Phasen, die in keiner
Transition als Ziel vorkommen. `scope_loc_delta` ist ein freier
String-Wert, der beim `write-log`-Aufruf als optionales Argument
übergeben werden kann.

### Neue und erweiterte CLI-Subcommands

```python
def cmd_write_log(args: list[str]) -> None:
    """workflow.py write-log [outcome] [--loc-delta '+360'] [--files-changed 4]"""
    outcome = args[0] if args else "success"
    # Liest aktiven Workflow-State
    # Aggregiert phases_completed aus phase_transitions
    # Schreibt YAML via _atomic_write nach _log/YYYY-MM-DD_<name>.yaml


def cmd_complete(args: list[str]) -> None:
    """Blockiert ohne Logbuch; danach bestehende Archive-Logik"""
    log_dir = _get_workflows_root() / "_log"
    name = _get_active_workflow_name()
    if not any(log_dir.glob(f"*_{name}.yaml")):
        sys.exit(
            "BLOCKED: No execution log. Run: workflow.py write-log [outcome]"
        )
    # ... bestehende Archive-Logik aus Workflow A


def cmd_phase(args: list[str]) -> None:
    """Bestehende Logik + Bypass-Schutz für direkten Sprung zu phase8_complete"""
    target = args[0]
    if target == "phase8_complete":
        log_dir = _get_workflows_root() / "_log"
        name = _get_active_workflow_name()
        if not any(log_dir.glob(f"*_{name}.yaml")):
            sys.exit(
                "BLOCKED: Direct jump to phase8_complete requires write-log first"
            )
    # ... bestehende Transition-Logik (phase_transitions, fix_loop_iterations)


def cmd_status(args: list[str]) -> None:
    """Bestehende Ausgabe + drei neue Zeilen"""
    # ... bestehende Felder
    data = _load_active_workflow()
    print(f"Fix-Loop-Iterations: {data.get('fix_loop_iterations', 0)}")
    print(f"Phase-Transitions: {len(data.get('phase_transitions', []))}")
    log_dir = _get_workflows_root() / "_log"
    name = data.get("name", "")
    log_status = "written" if any(log_dir.glob(f"*_{name}.yaml")) else "pending"
    print(f"Execution Log: {log_status}")
```

### Trigger-Vokabular für `phase_transitions[].trigger`

| Wert | Bedeutet |
|------|----------|
| `command` | Direkter CLI-Aufruf `workflow.py phase ...` |
| `advance` | Aufruf über `workflow.py advance` |
| `user_keyword` | UserPromptSubmit-Hook erkannte "approved", "deployed" o.ä. |
| `manual` | Direktes State-Dict-Edit (Fallback, sollte selten auftreten) |

### Patch `workflow_state_updater.py`

`phase4_approved` Setter setzt derzeit `workflow["current_phase"] = "phase4_approved"` direkt (ca. Z. 120). Neu: Aufruf von `set_phase(name, "phase4_approved", trigger="user_keyword")` aus `workflow_state_multi`, damit die Transition korrekt protokolliert wird.

Vor `complete_workflow()` im "deployed"-Zweig: erst `write_log(outcome="user_keyword:deployed")` aufrufen, danach `complete_workflow()`. Die Log-Pflicht greift so transparent ohne manuelle Nutzeraktion.

### Erweiterung `workflow_state_multi.py`

```python
def set_phase(workflow_name: str, phase: str, trigger: str = "manual") -> bool:
    """Delegiert an workflow.py cmd_phase mit explizitem Trigger.

    Bisher: nur Phase-Update im State-Dict.
    Neu: Transition wird mit from/to/at/trigger protokolliert.
    """
    # Intern: aktiven Workflow laden, Transition anhängen, State speichern
    # via workflow.py cmd_phase --trigger <trigger>
```

## Acceptance Criteria

- **AC-1:** Given ein Workflow steht kurz vor `phase8_complete` / When `workflow.py write-log success` läuft / Then existiert `.claude/workflows/_log/YYYY-MM-DD_<name>.yaml` mit den Feldern `phases_completed`, `tdd_red_confirmed`, `adversary_verdict`, `fix_loop_iterations`, `scope_loc_delta` und `outcome` als gültiges YAML

- **AC-2:** Given kein Logbuch existiert / When `workflow.py complete` läuft / Then wird die Operation blockiert mit Fehlermeldung "BLOCKED: No execution log. Run: workflow.py write-log [outcome]" und Exit Code 1

- **AC-3:** Given eine Phasen-Transition / When `workflow.py phase <target>` läuft / Then wird `phase_transitions[]` mit `from`, `to`, `at`, `trigger: "command"` ergänzt (bereits implementiert in Workflow A — Test stellt sicher, dass der Bestand erhalten bleibt)

- **AC-4:** Given Adversary geht von `phase6b_adversary` zurück nach `phase6_implement` / When `workflow.py phase phase6_implement` läuft / Then wird `fix_loop_iterations` um 1 inkrementiert (bereits implementiert in Workflow A — Test stellt sicher, dass der Bestand erhalten bleibt)

- **AC-5:** Given ein Workflow mit Logbuch, Transitions und Fix-Loop-Iterationen / When `workflow.py status` läuft / Then werden zusätzlich angezeigt: `Fix-Loop-Iterations: N`, `Phase-Transitions: N`, `Execution Log: written/pending`

- **AC-6:** Given UserPromptSubmit-Hook erkennt "approved" / When er die Phase setzt / Then wird die Transition mit `trigger: "user_keyword"` in `phase_transitions[]` geloggt — nicht mehr `trigger: "command"` oder gar kein Eintrag

- **AC-7:** Given UserPromptSubmit-Hook erkennt "deployed" / When er auf `phase7_validate` steht / Then wird automatisch `write_log(outcome="user_keyword:deployed")` aufgerufen und danach `complete_workflow()` — die Log-Pflicht greift transparent ohne manuelle Nutzeraktion

- **AC-8:** Given ein direkter Sprung-Versuch `workflow.py phase phase8_complete` ohne vorhandenes Logbuch / When er ausgeführt wird / Then blockiert der Hook mit Fehlermeldung und Exit Code 1 — Bypass-Schutz

- **AC-9:** Given `workflow_state_multi.set_phase(name, phase, trigger="manual")` / When der Wrapper aufgerufen wird / Then wird eine Transition mit dem übergebenen `trigger`-Wert protokolliert (bisher: nur Phase-Update; neu: Transition wird ebenfalls geloggt)

## Expected Behavior

- **Input:** Workflow-State mit `phase_transitions[]` und `fix_loop_iterations` (beide Felder aus Workflow A / Issue #192 vorhanden)
- **Output:** YAML-Logbuch im `_log/`-Verzeichnis, erweiterte `status`-Ausgabe mit Fix-Loop und Log-Status, blockierende `complete`-CLI bei fehlendem Log
- **Side effects:** Atomare YAML-Writes via `_atomic_write` (wiederverwendet), keine Änderungen am Workflow-State-Schema (alle benötigten Felder existieren bereits)

## Known Limitations

- YAML-File-Naming nach Datum: zwei gleichnamige Workflows am selben Tag würden dasselbe Logbuch-File erzeugen (Edge-Case — `complete` archiviert den Workflow danach, sodass kein zweiter gleichnamiger Workflow am selben Tag im aktiven Zustand existieren kann)
- Bestehende archivierte Workflows (~45 Stück) haben kein nachträgliches Logbuch; Migration älterer Archive ist nicht vorgesehen
- Log-Erzeugung läuft im UserPromptSubmit-Hook — PyYAML-Dump ist <50 ms, akzeptabel im Hook-Kontext

## Test Coverage

Tests in `tests/tdd/test_epic_191_logbuch_audit.py`:

- `test_write_log_creates_yaml_file` — prüft dass `write-log success` eine YAML-Datei im `_log/`-Verzeichnis anlegt
- `test_write_log_yaml_contains_required_fields` — prüft `phases_completed`, `tdd_red_confirmed`, `adversary_verdict`, `fix_loop_iterations`, `outcome`
- `test_complete_blocked_without_log` — prüft Exit Code 1 und Fehlermeldung bei fehlendem Logbuch
- `test_complete_succeeds_with_log` — prüft dass `complete` nach `write-log` durchläuft und archiviert
- `test_phase_transition_trigger_command` — prüft `trigger: "command"` bei direktem `workflow.py phase`-Aufruf (Bestand-Test)
- `test_fix_loop_increments_on_adversary_return` — prüft Inkrement von `fix_loop_iterations` beim Rücksprung (Bestand-Test)
- `test_status_shows_fix_loop_and_log_status` — prüft die drei neuen Statuszeilen in `cmd_status`-Ausgabe
- `test_status_log_status_pending_without_log` — prüft `Execution Log: pending` wenn noch kein Logbuch existiert
- `test_status_log_status_written_after_write_log` — prüft `Execution Log: written` nach `write-log`
- `test_phase8_direct_jump_blocked_without_log` — prüft Bypass-Schutz bei direktem `phase phase8_complete` ohne Log
- `test_user_keyword_trigger_logged_for_approved` — prüft `trigger: "user_keyword"` bei "approved"-Erkennung im Updater
- `test_auto_write_log_on_deployed_keyword` — prüft automatische Log-Erzeugung beim "deployed"-Zweig im Updater
- `test_set_phase_wrapper_logs_transition_with_trigger` — prüft dass `workflow_state_multi.set_phase(..., trigger="manual")` eine Transition mit korrektem Trigger-Wert protokolliert

## Changelog

- 2026-05-11: Initial spec erstellt — Issue #193, Epic #191. Baut auf #192 (epic_191_state_migration) auf.
