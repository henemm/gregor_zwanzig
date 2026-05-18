# Context: Issue #258 — Hook-Architektur Hot-Path-Reader

**Workflow:** `issue-258-hot-path-hooks`
**Phase:** phase2_analyse → phase3_spec
**Issue:** https://github.com/henemm/gregor_zwanzig/issues/258
**Feature-Brief:** `docs/project/backlog/features/issue-258-hook-architektur-hot-path-reader.md`

## Auslöser (was passiert ist)

Der `tdd_enforcement.py`-Hook blockierte Code-Edits im aktiven Workflow falsch. Ein Developer Agent hat als Reaktion direkt die Workflow-JSON editiert und `current_phase = "phase8_complete"` gesetzt — die Adversary-Verifikation wurde dadurch übersprungen, `adversary_verdict` blieb `None`.

**Reproduziertes Drift-Indiz beim Anlegen dieses Workflows:** Nach `cmd_start issue-258-hot-path-hooks` (15:16) wurde der `.active`-Symlink durch einen PostToolUse-Hook (vermutlich `workflow_state_updater.py`) um 15:21 wieder auf die archivierte `epic-138-...`-JSON gesetzt — Symlink dangling, neuer Workflow ohne aktive Markierung. Manuell mit `workflow.py switch` korrigiert. Genau die Drift-Klasse, die #258 systemisch behebt.

## Root Cause

`_aggregate_state()` in `workflow_state_multi.py:87-129` liest bei jedem Aufruf alle Live- + Archive-JSONs (aktuell 74 + 124 = 198 Dateien). Hot-Path-Hooks wie `tdd_enforcement.py:246` und `workflow_gate.py:305` triggern das, obwohl sie nur den aktiven Workflow brauchen.

## Konkrete Änderungen (4 Punkte, vom User entschieden)

1. **Neuer Helper `read_active_workflow_fast()`** in `workflow.py` (Library, nicht Wrapper) — Signatur: `() -> tuple[str, dict] | None`. Liest nur `.active`-Symlink + zugehörige JSON. Kein Legacy-Fallback.
2. **Hot-Path-Hooks umstellen** — `tdd_enforcement.py` (Z.246) und `workflow_gate.py` (Z.305) nutzen den neuen Helper.
3. **`cmd_complete` mit optionalem Workflow-Namen** — ohne Argument: aktiver Workflow (heutiges Verhalten); mit Argument: expliziter Workflow + Warn-Banner falls `name != active`. Symlink wird **nur** entfernt wenn `name == active`.
4. **Neues `cmd_cleanup`-Kommando** — zweistufig: Dry-Run (default) listet `phase8_complete`-Workflows, `--yes`-Flag archiviert sie batch-weise.

**Out-of-Scope:**
- Auto-Archive-Erweiterung auf `phase7_validate + VERIFIED`
- Änderung der 8 weiteren Hooks
- Interaktives `input()`-Prompt
- v2→v3-Migration

## Recherche-Ergebnisse

### Wiederverwendbare Helper in `workflow.py`
| Helper | Zeile | Zweck |
|---|---|---|
| `_resolve_active_path()` | 294-305 | Path zur aktiven JSON oder None |
| `_read_workflow_file(path)` | 271-272 | JSON-Read |
| `_active_link()`, `_active_name()`, `_set_active()` | 132, 275, 332 | Symlink-Operationen |
| `_workflow_file(name)`, `_archive_file(name)`, `_archive_dir()` | 136, 141, 146 | Pfad-Helper |
| `_atomic_write(path, data)` | 229-242 | Race-Free Write |
| `_has_valid_log(log_dir, name)` | 262-268 | Execution-Log-Gate |

### Hot-Path-Felder
- `tdd_enforcement.py`: nutzt `current_phase`, `test_artifacts` (Filter `phase == "phase5_tdd_red"`)
- `workflow_gate.py`: nutzt `active_workflow`-Name, `current_phase`, `spec_file`, `spec_approved`, `red_test_done`, `green_test_done`

→ Helper-Signatur muss **(name, data)** zurückgeben, weil `workflow_gate.py` den Namen für AC-Format-Check braucht.

### Spec-Constraints
- `worktree_state_routing.md` AC-5: Pfad-Ops via `find_main_repo_from_worktree`. `_get_workflows_root()` macht das bereits — kein Änderungsbedarf.
- `epic_191_state_migration.md`: v3-API erhalten. `workflow_state_multi.py` re-exportiert den neuen Helper als Backward-Compat-Alias.

### Test-Setup (bestehendes Pattern)
- Verzeichnis: `tests/tdd/test_issue_258_hook_arch.py` (neue Datei)
- Fixtures: `hooks_on_path` (sys.path + Module-Reset), `fake_git_repo` (echtes `git init` in `tmp_path`)
- Pattern: subprocess-CLI-Calls + echtes Filesystem, **keine Mocks** (CLAUDE.md-Regel)
- Vorbilder: `test_epic_191_state_migration.py`, `test_epic_191_logbuch_audit.py`

## Test-Klassen (geplant)

```
TestReadActiveWorkflowFast
  - test_returns_none_when_no_active_symlink
  - test_returns_name_and_data_when_active_exists
  - test_returns_none_when_active_symlink_dangling
  - test_no_filesystem_glob_called

TestCmdCompleteOptionalName
  - test_complete_without_arg_removes_symlink
  - test_complete_with_active_name_removes_symlink
  - test_complete_with_other_name_keeps_symlink
  - test_complete_with_other_name_prints_warning
  - test_complete_with_nonexistent_name_exits_1
  - test_complete_archives_workflow_json

TestCmdCleanup
  - test_cleanup_dry_run_lists_candidates
  - test_cleanup_dry_run_writes_nothing
  - test_cleanup_yes_archives_all_completed
  - test_cleanup_no_candidates_exits_cleanly
  - test_cleanup_leaves_active_workflows_alone

TestHotPathIntegration
  - test_tdd_enforcement_uses_fast_path
  - test_workflow_gate_fast_path_fields_match
```

## Scope-Schätzung

| Datei | Delta | Zweck |
|---|---|---|
| `.claude/hooks/workflow.py` | +65 | `read_active_workflow_fast` (+15), `cmd_complete`-Erweiterung (+20), `cmd_cleanup` (+30) |
| `.claude/hooks/workflow_state_multi.py` | +15 | Re-Export + CLI-Weiterleitung |
| `.claude/hooks/tdd_enforcement.py` | +15 | Import-Swap + Fast-Path |
| `.claude/hooks/workflow_gate.py` | +20 | Lokales `load_state` auf Fast-Path |
| `tests/tdd/test_issue_258_hook_arch.py` | +110 | Neue Test-Datei |

**Total: ~225 LoC** (innerhalb 250-LoC-Limit, aber knapp — bei Überschreitung `loc_limit_override` setzen).

## Risiken

1. **Dangling Symlink im Fast-Path** — `.active` existiert aber JSON fehlt. Helper gibt `None` zurück, Hot-Path-Hooks behandeln das wie heute (kein aktiver Workflow → skip).
2. **Race in `cmd_cleanup`** — zwischen Listing und Archivierung kann sich der Phase-Status ändern. Mitigation: beim Archivieren nochmal `current_phase == "phase8_complete"` prüfen.
3. **Wrapper-CLI vs. Library-CLI** — Slash-Commands rufen `workflow_state_multi.py`, das `workflow.main()` weiterreicht. Optional-Argument muss durch beide Pfade kommen.

## Nächster Schritt

`phase3_spec` — Spec-Datei `docs/specs/modules/issue_258_hook_arch_fix.md` schreiben.
