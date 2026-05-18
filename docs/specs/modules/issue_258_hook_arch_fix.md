---
entity_id: issue_258_hook_arch_fix
type: module
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
tags: hooks, workflow, infrastructure, drift-prevention
---

<!-- Issue #258 — Hook-Architektur: Hot-Path-Reader + cleanup-Kommando -->

# Issue 258 — Hook-Architektur: Fast-Path-Reader + cmd_cleanup

## Approval

- [ ] Approved

## Purpose

Hot-Path-Hooks (`tdd_enforcement.py`, `workflow_gate.py`) lesen bei jedem File-Edit über `_aggregate_state()` alle 198 Workflow-JSONs (Live + Archiv), obwohl sie nur den aktiven Workflow brauchen. Diese unnötige Breite erzeugt False-Positive-Blockaden, die Developer Agents zu direkten JSON-Edits als Workaround provozieren — mit der Konsequenz, dass Adversary-Verifikation übersprungen wird (`adversary_verdict` bleibt `None`). Zusätzlich fehlt ein kontrollierter Weg, fertige (`phase8_complete`) Workflows nachträglich in `_archive/` zu überführen, was das Workflows-Verzeichnis mit 74 unfertigen JSONs aufläuft.

## Source

- **File:** `.claude/hooks/workflow.py` — neue Funktion `read_active_workflow_fast()`, Erweiterung `cmd_complete`, neues `cmd_cleanup`
- **File:** `.claude/hooks/workflow_state_multi.py` — Re-Export des neuen Helpers, CLI-Weiterleitung für `complete <name>` und `cleanup`
- **File:** `.claude/hooks/tdd_enforcement.py` — Import-Swap auf Fast-Path (Z. 246)
- **File:** `.claude/hooks/workflow_gate.py` — lokales `load_state` auf Fast-Path (Z. 305)
- **File:** `tests/tdd/test_issue_258_hook_arch.py` — neue Test-Datei

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pathlib.Path` | stdlib | Symlink-Auflösung, JSON-Pfade |
| `_active_link()` | intern (workflow.py:132) | Pfad zum `.active`-Symlink |
| `_resolve_active_path()` | intern (workflow.py:294-305) | Auflösung Symlink → JSON-Pfad oder None |
| `_read_workflow_file(path)` | intern (workflow.py:271-272) | JSON-Read einer einzelnen Workflow-Datei |
| `_active_name()` | intern (workflow.py:275) | Name des aktiven Workflows aus Symlink |
| `_workflow_file(name)` | intern (workflow.py:136) | Pfad zu einer Live-Workflow-JSON |
| `_archive_file(name)` | intern (workflow.py:141) | Ziel-Pfad in `_archive/` |
| `_archive_dir()` | intern (workflow.py:146) | Pfad zum `_archive/`-Verzeichnis |
| `_get_workflows_root()` | intern (workflow.py) | Worktree-Routing via `find_main_repo_from_worktree` |
| `config_loader.find_main_repo_from_worktree()` | intern | Worktree-Routing — Pfad ins Hauptrepo |
| `workflow_state_multi.py` (v3 Thin-Wrapper) | intern | Backward-Compat-API (14 Funktionen, 5 Konstanten) |

## Implementation Details

### 1. Neue Funktion `read_active_workflow_fast()` in `workflow.py`

```python
def read_active_workflow_fast() -> tuple[str, dict] | None:
    """
    Liest nur die .active-Datei und deren JSON.
    Kein Legacy-v2-Fallback, kein Glob über alle Workflows.
    Returns (name, data) oder None wenn kein aktiver Workflow.
    """
    active_path = _resolve_active_path()   # Symlink-Auflösung, None bei fehlendem/dangling Symlink
    if active_path is None:
        return None
    data = _read_workflow_file(active_path)
    if data is None:
        return None
    name = active_path.stem                # Dateiname ohne .json
    return (name, data)
```

Wiederverwendet ausschließlich bestehende interne Helper. Kein eigener `open()`-Aufruf, kein `glob`. Exakt 1 JSON-Datei wird gelesen (nach Symlink-Auflösung).

### 2. Hot-Path-Hooks umstellen

**`tdd_enforcement.py` (Z. 246):** Ersetzt den `_aggregate_state()`-Aufruf durch:

```python
from workflow import read_active_workflow_fast
result = read_active_workflow_fast()
if result is None:
    # kein aktiver Workflow → skip (heutiges Verhalten)
    sys.exit(0)
active_name, state = result
# nutzt: state["current_phase"], state["test_artifacts"]
```

**`workflow_gate.py` (Z. 305):** Ersetzt lokales `load_state()` durch:

```python
from workflow import read_active_workflow_fast
result = read_active_workflow_fast()
if result is None:
    sys.exit(0)
active_name, state = result
# nutzt: active_name, state["current_phase"], state["spec_file"],
#         state["spec_approved"], state["red_test_done"], state["green_test_done"]
```

### 3. `cmd_complete` mit optionalem Workflow-Namen

Signatur-Erweiterung: `workflow.py complete [<name>]`

Verhalten:
- **Kein Argument:** heutiges Verhalten — aktiven Workflow archivieren, `.active`-Symlink entfernen.
- **Argument == aktiver Workflow:** identisch zu ohne Argument.
- **Argument != aktiver Workflow (aber existent):** Workflow archivieren, `.active`-Symlink bleibt erhalten, Warn-Banner auf stderr: `WARNING: Completing '<name>' but active workflow is '<active>'`.
- **Argument nennt nicht-existenten Workflow:** exit 1 mit `ERROR: Workflow '<name>' not found`.

### 4. Neues `cmd_cleanup`-Kommando

```
workflow.py cleanup [--yes]
```

- **Default (Dry-Run):** listet alle Live-Workflows mit `current_phase == "phase8_complete"`. Keine Datei-Operationen.
- **`--yes`:** archiviert alle gefundenen Kandidaten nach `_archive/`. Race-safe: beim Archivieren wird `current_phase` nochmals aus der JSON gelesen — nur wenn noch `phase8_complete`, wird verschoben.
- **Keine Kandidaten:** exit 0, Meldung `Nothing to clean up`.
- Kein `input()`-Prompt (nicht interaktiv).

### 5. Re-Export in `workflow_state_multi.py`

```python
from workflow import read_active_workflow_fast  # Re-Export für Backward-Compat
```

CLI-Weiterleitung: `workflow_state_multi.py complete <name>` → `workflow.main(["complete", name])`, analog für `cleanup`.

### Worktree-Routing

Keine Änderung an `_get_workflows_root()` oder `find_main_repo_from_worktree`. Der Fast-Path-Reader nutzt `_resolve_active_path()`, das intern `_get_workflows_root()` verwendet — Worktree-Routing ist automatisch korrekt.

## Expected Behavior

- **Input:** Aufruf von `read_active_workflow_fast()` aus einem Hot-Path-Hook
- **Output:** `(name: str, data: dict)` bei aktivem Workflow; `None` wenn kein `.active`-Symlink, Symlink dangling, oder JSON unlesbar
- **Side effects:** Exakt 1 Datei-Read pro Aufruf (statt 198). Kein Schreiben, kein Locking, kein Legacy-Fallback.

## Acceptance Criteria

- **AC-1:** Given ein aktiver Workflow existiert und `.active` zeigt auf eine valide JSON / When `read_active_workflow_fast()` aufgerufen wird / Then liest die Funktion exakt 1 JSON-Datei und gibt `(name, data)` zurück — verifizierbar durch Zählen der Filesystem-Operationen im Test (kein Glob, kein weiterer `open`-Aufruf)

- **AC-2:** Given kein `.active`-Symlink existiert im Workflows-Verzeichnis / When `read_active_workflow_fast()` aufgerufen wird / Then gibt die Funktion `None` zurück ohne Exception oder Fehlerausgabe

- **AC-3:** Given `.active`-Symlink existiert aber die Ziel-JSON fehlt (dangling Symlink) / When `read_active_workflow_fast()` aufgerufen wird / Then gibt die Funktion `None` zurück — kein Crash, kein Traceback

- **AC-4:** Given `tdd_enforcement.py` prüft eine Code-Datei bei aktivem Workflow / When der Hook ausgeführt wird / Then liest er den Workflow-Status ausschließlich über `read_active_workflow_fast()` und nicht über `_aggregate_state` oder ein direktes `glob` auf alle Workflow-JSONs

- **AC-5:** Given `workflow_gate.py` prüft eine Code-Datei bei aktivem Workflow / When der Hook ausgeführt wird / Then nutzt er `read_active_workflow_fast()` und hat Zugriff auf Workflow-Name sowie alle benötigten Felder (`current_phase`, `spec_file`, `spec_approved`, `red_test_done`, `green_test_done`)

- **AC-6:** Given `workflow.py complete` wird ohne Argument aufgerufen und ein aktiver Workflow existiert / When der Workflow archiviert wird / Then wandert die JSON nach `_archive/` und der `.active`-Symlink wird entfernt

- **AC-7:** Given `workflow.py complete <name>` wird mit dem Namen des aktuell aktiven Workflows aufgerufen / When der Workflow archiviert wird / Then ist das Verhalten identisch zu ohne Argument — JSON in `_archive/`, `.active`-Symlink entfernt

- **AC-8:** Given `workflow.py complete <name>` wird mit einem Workflow-Namen aufgerufen, der existiert aber nicht aktiv ist / When der Workflow archiviert wird / Then bleibt der `.active`-Symlink unverändert erhalten und auf stderr erscheint `WARNING: Completing '<name>' but active workflow is '<active>'`

- **AC-9:** Given `workflow.py complete <name>` wird mit einem nicht-existenten Workflow-Namen aufgerufen / When das Kommando läuft / Then ist der Exit-Code 1 und stderr enthält `ERROR: Workflow '<name>' not found`

- **AC-10:** Given `workflow.py cleanup` wird ohne Flags aufgerufen und fertige (`phase8_complete`) Workflows existieren / When der Befehl ausgeführt wird / Then werden die Kandidaten auf stdout gelistet und KEINE Dateien werden verschoben oder verändert (Dry-Run)

- **AC-11:** Given `workflow.py cleanup --yes` wird aufgerufen und fertige Workflows existieren / When der Befehl ausgeführt wird / Then werden alle Workflows mit `current_phase == "phase8_complete"` nach `_archive/` verschoben

- **AC-12:** Given `workflow.py cleanup` wird aufgerufen (mit oder ohne `--yes`) und keine `phase8_complete`-Workflows existieren / When der Befehl ausgeführt wird / Then ist der Exit-Code 0 und die Ausgabe enthält `Nothing to clean up`

- **AC-13:** Given `workflow.py cleanup --yes` wird aufgerufen und zwischen Listing und Archivierung ändert sich der Phase-Status eines Kandidaten / When dieser Workflow archiviert werden soll / Then wird sein `current_phase` zum Archivierungs-Zeitpunkt nochmals aus der JSON gelesen — nur bei noch `phase8_complete` wird er verschoben (race-safe)

- **AC-14:** Given `workflow_state_multi.py` wird als Wrapper-CLI mit `complete <name>` aufgerufen / When das Argument übergeben wird / Then leitet der Wrapper das Argument korrekt an `workflow.py complete <name>` weiter

## Known Limitations

- `read_active_workflow_fast()` hat keinen Legacy-v2-Fallback: Hooks, die in einer v2-Umgebung (ohne `.active`-Symlink) laufen, erhalten `None` und verhalten sich wie bei fehlendem Workflow (skip). Da v2 migriert ist, kein Handlungsbedarf.
- `cmd_cleanup` ist nicht idempotent bei parallelen Aufrufen: zwei gleichzeitige `--yes`-Läufe würden denselben Workflow doppelt zu archivieren versuchen. Race-safe durch `current_phase`-Recheck, aber `os.rename` auf bereits verschobene Datei schlägt mit `FileNotFoundError` fehl. Mitigation: Fehler pro Datei abfangen und überspringen.
- Interaktives Bestätigungs-Prompt (`input()`) ist explizit Out-of-Scope — `--yes`-Flag ist die einzige Bestätigung.

## Test Coverage

Tests in `tests/tdd/test_issue_258_hook_arch.py` — Fixtures nach Pattern `test_epic_191_state_migration.py` (`hooks_on_path`, `fake_git_repo`), keine Mocks, echte Temp-Dirs, subprocess-CLI-Calls:

**Klasse `TestReadActiveWorkflowFast`:**
- `test_returns_name_and_data_when_active_exists` — AC-1
- `test_returns_none_when_no_active_symlink` — AC-2
- `test_returns_none_when_active_symlink_dangling` — AC-3
- `test_no_filesystem_glob_called` — AC-1 (File-Count-Assertion)

**Klasse `TestCmdCompleteOptionalName`:**
- `test_complete_without_arg_removes_symlink` — AC-6
- `test_complete_with_active_name_removes_symlink` — AC-7
- `test_complete_archives_workflow_json` — AC-6/7
- `test_complete_with_other_name_keeps_symlink` — AC-8
- `test_complete_with_other_name_prints_warning` — AC-8
- `test_complete_with_nonexistent_name_exits_1` — AC-9

**Klasse `TestCmdCleanup`:**
- `test_cleanup_dry_run_lists_candidates` — AC-10
- `test_cleanup_dry_run_writes_nothing` — AC-10
- `test_cleanup_yes_archives_all_completed` — AC-11
- `test_cleanup_no_candidates_exits_cleanly` — AC-12
- `test_cleanup_leaves_active_workflows_alone` — AC-11 (nur phase8_complete archiviert)
- `test_cleanup_race_safe_recheck` — AC-13

**Klasse `TestHotPathIntegration`:**
- `test_tdd_enforcement_uses_fast_path` — AC-4
- `test_workflow_gate_fast_path_fields_match` — AC-5
- `test_wrapper_cli_forwards_complete_name_arg` — AC-14

## Changelog

- 2026-05-18: Initial spec erstellt — Issue #258
