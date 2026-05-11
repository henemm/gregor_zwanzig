# Context: epic-191-state-migration

## Request Summary

Den zentralen `.claude/workflow_state.json` (Version 2.0, 108 Workflows, 153 KB) durch isolierte JSON-Dateien pro Workflow ersetzen (`.claude/workflows/<name>.json`). Aktiver Workflow wird per `.active`-Symlink markiert. Vorbild: `henemm/agent-os-openspec` v3.1.0 (`core/hooks/workflow.py` + `migrate_state.py`).

## Related Files

| File | Lines | Relevance |
|------|-------|-----------|
| `.claude/hooks/workflow_state_multi.py` | 750 | **Zu ersetzen** — aktuelles CLI, verwaltet zentralen State |
| `.claude/hooks/workflow_state_updater.py` | 201 | **Anpassen** — UserPromptSubmit-Hook, schreibt State |
| `.claude/hooks/workflow_gate.py` | 276 | **Anpassen** — PreToolUse-Gate, liest State |
| `.claude/hooks/config_loader.py` | — | **Zentraler Hebel** — `get_state_file_path()` ist Single Source of Truth für alle Hooks |
| `.claude/hooks/scope_guard.py` | — | Liest State |
| `.claude/hooks/red_test_gate.py` | — | Liest State |
| `.claude/hooks/post_implementation_gate.py` | — | Liest State |
| `.claude/hooks/tdd_enforcement.py` | — | Liest State |
| `.claude/hooks/ui_screenshot_gate.py` | — | Liest State |
| `.claude/hooks/qa_gate.py` | — | Liest+schreibt State (adversary_verdict) |
| `.claude/commands/3-write-spec.md` | — | Referenziert `active_workflow` |
| `.claude/commands/4-tdd-red.md` | — | Referenziert `active_workflow` |
| `.claude/commands/5-implement.md` | — | Referenziert `active_workflow` |
| `.claude/commands/workflow.md` | — | Referenziert `active_workflow` |
| `.claude/commands/add-artifact.md` | — | Referenziert `active_workflow` |
| `.claude/workflow_state.json` | 153 KB | **Zu migrieren** — 108 Workflows |

## Reference Implementation (agent-os-openspec)

| File | Lines | Purpose |
|------|-------|---------|
| `core/hooks/workflow.py` | 458 | Neues CLI mit isoliertem State, atomare Writes via tempfile+rename |
| `core/hooks/migrate_state.py` | 127 | One-Shot Migration v2 → v3, Dry-Run-Modus |

Heruntergeladen nach `/tmp/aos_workflow.py` und `/tmp/aos_migrate_state.py`.

## Existing Patterns

### Worktree-Routing (Issue #112, Spec: `worktree_state_routing.md`)

`config_loader.get_state_file_path()` ist der Hebel: Wenn ein Hook in einem git-Worktree läuft, wird der State-Pfad ins Hauptrepo umgeleitet (`find_main_repo_from_worktree`). **Diese Logik muss erhalten bleiben** — sie wird in v3 auf das Verzeichnis `.claude/workflows/` (statt `.claude/workflow_state.json`) angewendet.

### Pre-Snapshot bei Daten-Schema-Reworks (CLAUDE.md)

`data_schema_backup.py` erstellt automatisch `.backups/data-pre-rework-<ts>.tar.gz` bei Edits auf Schema-Dateien. **`workflow_state.json` zählt aktuell NICHT als Schema-Datei** — wir müssen für diese Migration einen expliziten Pre-Snapshot machen.

### Atomare Writes

agent-os-openspec nutzt `tempfile.mkstemp + os.rename`. Wir nutzen aktuell `fcntl.flock`. Beide funktionieren, aber tempfile+rename ist einfacher und vermeidet Lock-Datei-Reste.

## Dependencies

- **Upstream:** `pathlib.Path`, `tempfile`, `os.rename` (stdlib); `hook_utils.find_project_root` (existiert noch nicht bei uns — muss aus agent-os-openspec übernommen oder via `config_loader` bereitgestellt werden)
- **Downstream:** Alle 9 Hooks + 6 Commands + jeder zukünftige Hook im OpenSpec-Workflow

## Existing Specs

- `docs/specs/modules/worktree_state_routing.md` — **Muss erweitert/aktualisiert werden**, weil der Worktree-Pfad-Hebel von `workflow_state.json` auf `.claude/workflows/` umzieht

## Risks & Considerations

| Risiko | Mitigation |
|--------|-----------|
| **Datenverlust der 108 Workflows** (BUG-DATALOSS-GR221) | Pre-Snapshot tar.gz vor Migration; Roundtrip-Test (alle 108 v2 → v3 → re-read → count == 108); Migration läuft erst nach `--apply`, default Dry-Run |
| **9 Hooks brechen wenn API ändert** | API-Kompatibilität: `workflow_state_multi.py` bleibt als Thin-Wrapper für eine Übergangsphase, leitet auf `workflow.py` um; alternativ alle 9 Hooks gleichzeitig migrieren (sauberer, aber höheres Big-Bang-Risiko) |
| **Worktree-Routing bricht** | `config_loader.get_state_file_path()` wird ersetzt durch `get_workflows_dir()` — Logik identisch, nur Zielpfad anders |
| **Worktree-Kopien in `.claude/worktrees/agent-*/` haben veraltete Hooks** | Diese Worktrees sind kurzlebig (Developer-Agent-Worktrees). Vor Migration prüfen und ggf. löschen, sonst lesen sie nach Migration ins Leere |
| **108 Einzeldateien sind viele** | Archive-Verzeichnis `_archive/` aufnimmt abgeschlossene → laufender Workflow-Ordner bleibt überschaubar |
| **Migration ist irreversibel** | `workflow_state.json.bak` als Rollback-Anker, plus Pre-Snapshot tar.gz |

## Out of Scope

- Hook-Konsolidierung 30→4 (Epic-Notiz: bewusst aufgeschoben)
- API-Änderungen am Workflow-CLI über das Notwendige hinaus
- Migration der `.claude/worktrees/*` (kurzlebig, werden bei nächstem Developer-Agent-Lauf neu erstellt)

## Analyse-Ergebnisse (Phase 2)

### Strategie: Wrapper-Phase (nicht Big-Bang)

`workflow_state_multi.py` wird zum Thin-Wrapper, alle Funktionen delegieren auf neue `workflow.py`. Vorteil: Die 9 Hooks und ihre API-Aufrufe bleiben unberührt — kein Big-Bang-Risiko bei 108 live Workflows. Rollback = `workflow.py` löschen, Wrapper zurückdrehen.

### Worktree-Konflikt → eigene Routing-Wrapper-Funktion

`workflow.py` bekommt eine eigene `_get_workflows_root()`, die unsere bestehende `config_loader.find_main_repo_from_worktree()`-Logik nutzt. Wir übernehmen NICHT v3's `hook_utils.find_project_root()` — das würde Issue #112 (Worktree-Routing) brechen.

### Kritisches Risiko R5 (vom Plan-Agent identifiziert)

`workflow_gate.py` und `workflow_state_updater.py` haben **eigene lokale** `load_state()`-Funktionen, die direkt `workflow_state.json` lesen — nicht über `workflow_state_multi.py`. **Nach Migration würden sie die alte (eingefrorene) Datei weiterlesen** → zwei inkonsistente State-Stores parallel. **Entscheidung:** Diese beiden Hooks müssen in Issue #192 mit angepasst werden (kleiner 5-Zeilen-Patch: lokale `load_state()` durch `from workflow_state_multi import load_state` ersetzen). Nicht als Follow-up — sonst funktioniert die Migration nicht.

### Scope-Schätzung (revidiert nach R5)

| Datei | Typ | LoC ca. |
|-------|-----|---------|
| `.claude/hooks/workflow.py` | Neu | ~200 |
| `.claude/hooks/migrate_v2_to_v3.py` | Neu (Einmal-Skript) | ~150 |
| `.claude/hooks/workflow_state_multi.py` | Umbau zu Wrapper | -200 / +80 (netto -120) |
| `.claude/hooks/workflow_gate.py` | R5-Patch | +5 |
| `.claude/hooks/workflow_state_updater.py` | R5-Patch | +5 |
| `.claude/hooks/config_loader.py` | Helper `get_workflows_dir()` | +15 |
| `tests/.claude/test_workflow_v3.py` | Neu | ~180 |
| **Gesamt** | | **~635 LoC neu/geändert** |

Nettoeffekt im Repo: ~+450 LoC (durch -120 Reduktion im Wrapper).

### Test-Strategie (TDD-Red)

Vier Testklassen:
1. **Roundtrip** — 108 Workflows v2 → v3 → re-read, alle Felder erhalten
2. **Atomare Writes** — Concurrent Writes auf zwei Workflows, kein Datenverlust
3. **Worktree-Routing** — Mock `find_main_repo_from_worktree` → Pfad zeigt ins Hauptrepo, nicht CWD
4. **API-Kompatibilität** — Alle 14 öffentlichen Funktionen liefern identische Ergebnisse wie v2

### Eskalations-Punkt für User

Vor `migrate_v2_to_v3.py --apply`: **Pre-Snapshot tar.gz bestätigen lassen, Dry-Run-Output zeigen**, dann erst echte Migration.
