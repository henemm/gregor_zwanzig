---
entity_id: epic_191_state_migration
type: module
created: 2026-05-11
updated: 2026-05-11
status: draft
version: "1.0"
tags: [hooks, infrastructure, workflow, migration]
---

<!-- Issue #192 — Epic #191: Workflow-State v2 → v3 Migration -->

# Epic 191 — Workflow-State Migration (v2 → v3)

## Approval

- [ ] Approved

## Purpose

Den zentralen `.claude/workflow_state.json` (v2.0, 108 Workflows, 153 KB) durch
isolierte JSON-Dateien pro Workflow in `.claude/workflows/<name>.json` mit
`.active`-Symlink zu ersetzen. Das eliminiert Merge-Konflikte und ermöglicht
gezielten Zugriff auf einzelne Workflows ohne das gesamte State-File laden zu
müssen — analog zu `henemm/agent-os-openspec` v3.1.0.

## Source

- **File:** `.claude/hooks/workflow.py` (NEU, ~200 LoC) — zentrales CLI, ersetzt die State-Verwaltung von `workflow_state_multi.py`
- **File:** `.claude/hooks/migrate_v2_to_v3.py` (NEU, Einmal-Skript, ~150 LoC) — One-Shot-Migration mit Dry-Run-Modus und Rollback-Anker
- **File:** `.claude/hooks/workflow_state_multi.py` (UMBAU zu Thin-Wrapper, -200/+80 LoC) — bestehende öffentliche API bleibt vollständig erhalten, delegiert intern auf `workflow.py`
- **File:** `.claude/hooks/config_loader.py` (ERWEITERT um `get_workflows_dir()`, +15 LoC)
- **File:** `.claude/hooks/workflow_gate.py` (R5-Patch, +5 LoC) — lokales `load_state()` durch `from workflow_state_multi import load_state` ersetzen
- **File:** `.claude/hooks/workflow_state_updater.py` (R5-Patch, +5 LoC) — dito

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pathlib.Path` | stdlib | Pfad-Operationen, Verzeichnis-Erstellung, Symlink |
| `tempfile.mkstemp` | stdlib | Atomare Writes: temporäre Datei vor Rename |
| `os.rename` | stdlib | Atomares Ersetzen der Zieldatei nach erfolgreichem Schreiben |
| `config_loader.find_main_repo_from_worktree()` | intern | Worktree-Routing — bestehende Logik aus Issue #112, läuft auf `.claude/workflows/` um statt auf `workflow_state.json` |
| `config_loader.find_project_root()` | intern | Fallback wenn kein Worktree erkannt wird |
| `worktree_state_routing` Spec (`docs/specs/modules/worktree_state_routing.md`) | Spec | Beschreibt den Worktree-Routing-Mechanismus, der in v3 auf das Workflows-Verzeichnis angewendet wird |

## Implementation Details

### Verzeichnisstruktur nach Migration

```
.claude/
├── workflow_state.json.bak       (Rollback-Anker, bleibt nach Migration erhalten)
└── workflows/
    ├── .active                   (Symlink → <aktiver_workflow>.json, relativ)
    ├── <workflow_name>.json      (ein File pro laufendem Workflow)
    └── _archive/
        └── <workflow_name>.json  (abgeschlossene Workflows)
```

### Pro-Workflow-JSON-Schema (Top-Level-Keys)

```json
{
  "name": "...",
  "current_phase": 0,
  "created": "ISO-8601",
  "last_updated": "ISO-8601",
  "spec_file": "...",
  "spec_approved": false,
  "context_file": "...",
  "affected_files": [],
  "test_artifacts": [],
  "is_new_ui": false,
  "red_test_done": false,
  "ui_test_red_done": false,
  "green_approved": false,
  "adversary_verdict": null,
  "adversary_ambiguous_override": false,
  "phase_transitions": [],
  "fix_loop_iterations": 0
}
```

`phase_transitions` und `fix_loop_iterations` sind Schema-Platzhalter für
Epic B und werden bei der Migration aus v2 leer initialisiert.

### Worktree-Routing in `workflow.py`

```python
def _get_workflows_root() -> Path:
    from config_loader import find_main_repo_from_worktree, find_project_root
    cwd = Path.cwd()
    main = find_main_repo_from_worktree(cwd)
    root = main if main is not None else find_project_root()
    return root / ".claude" / "workflows"
```

Diese Funktion ersetzt `config_loader.get_state_file_path()` als Pfad-Hebel.
Die bestehende Worktree-Erkennungslogik (Issue #112) bleibt identisch —
nur der Zielpfad ändert sich von `workflow_state.json` auf das
`workflows/`-Verzeichnis.

### Atomare Writes

```python
def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.rename(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
```

Ersetzt das bisherige `fcntl.flock`-Muster. `tempfile + os.rename` ist
atomar auf POSIX und hinterlässt keine Lock-Datei-Reste bei Absturz.

### CLI-Subcommands von `workflow.py`

Alle Bestand-Calls müssen unterstützt werden:

| Subcommand | Beschreibung |
|------------|-------------|
| `start <name>` | Neuen Workflow anlegen, `.active`-Symlink setzen |
| `switch <name>` | `.active`-Symlink auf anderen Workflow umsetzen |
| `status` | Aktiven Workflow anzeigen (Phase, Felder) |
| `list` | Alle Workflows auflisten (aktiv, backlog, _archive) |
| `phase <phase>` | Phase direkt setzen |
| `advance` | Zur nächsten Phase wechseln |
| `set-field <key> <value>` | Beliebiges Feld im aktiven Workflow setzen |
| `set-affected-files` | `affected_files`-Liste aus stdin/Argument setzen |
| `backlog <status>` | Backlog-Status setzen |
| `pause` | Aktiven Workflow pausieren |
| `reset` | Aktiven Workflow zurücksetzen |
| `add-artifact <type> <path> <desc> <phase>` | Test-Artefakt anhängen |
| `mark-red <result>` | TDD-Red-Phase markieren |
| `mark-ui-red <result>` | UI-TDD-Red-Phase markieren |
| `complete` | Workflow abschließen und nach `_archive/` verschieben |

### API-Surface von `workflow_state_multi.py` als Thin-Wrapper

14 öffentliche Funktionen und 5 Konstanten bleiben vollständig erhalten:

**Lese-Funktionen:**
- `load_state()`, `get_active_workflow()`, `get_workflow_status()`
- `list_workflows()`, `get_tdd_status()`, `get_backlog_status()`, `can_modify_code()`

**Schreib-Funktionen:**
- `save_state()`, `set_phase()`, `advance_phase()`, `add_test_artifact()`
- `mark_red_test_done()`, `mark_green_test_done()`, `set_backlog_status()`
- `complete_workflow()`, `pause_workflow()`, `sync_backlog_status_from_phase()`

**Konstanten:**
- `PHASES`, `PHASE_NAMES`, `PHASE_TO_BACKLOG_STATUS`, `TEST_REQUIRED_PHASES`, `CODE_MODIFY_PHASES`

Alle Funktionen delegieren intern auf `workflow.py`. Kein aufrufender Hook
muss geändert werden (außer R5-Patch für `workflow_gate.py` und
`workflow_state_updater.py`).

### R5-Patch: Direkte `load_state()`-Aufrufe ersetzen

`workflow_gate.py` und `workflow_state_updater.py` haben eigene lokale
`load_state()`-Implementierungen, die direkt `workflow_state.json` lesen.
Nach der Migration würden sie die eingefrorene `.bak`-Datei weiterlesen.

Patch (je ~5 Zeilen):
```python
# Vorher (lokale Implementierung):
def load_state():
    with open(STATE_FILE) as f:
        return json.load(f)

# Nachher (Delegation):
from workflow_state_multi import load_state
```

### Migrations-Protokoll (`migrate_v2_to_v3.py`)

1. **Pre-Snapshot:** `tar -czf .backups/state-migration-pre-<ts>.tar.gz .claude/workflow_state.json .claude/workflows/` (falls Verzeichnis schon existiert)
2. **Idempotenz-Check:** Falls `.claude/workflows/` bereits existiert → Abbruch mit Fehlerhinweis (nicht idempotent)
3. **Dry-Run default:** Gibt alle 108 Workflows mit Zieldateipfaden, Symlink-Ziel und geschätzter Größe aus — kein Filesystem-Write
4. **`--apply` Flag:** Führt tatsächlich aus
5. **Schreibt `workflow_state.json.bak`** (Rollback-Anker, bleibt dauerhaft erhalten)
6. **Für jeden Workflow:** schreibt `.claude/workflows/<name>.json` mit allen v2-Feldern plus neuen Schema-Platzhaltern
7. **Aktiver Workflow:** `.active`-Symlink (relativ) auf `<name>.json` setzen
8. **Roundtrip-Validation:** Liest alle frisch geschriebenen JSON-Dateien ein, prüft `count == 108` und alle wichtigen Felder erhalten (`current_phase`, `spec_file`, `test_artifacts`, `adversary_verdict`)
9. **Bei Validation-Fail:** Rollback aus `.bak` (alten `workflow_state.json` wiederherstellen, `workflows/`-Verzeichnis entfernen), Exit mit Fehler

## Acceptance Criteria

- **AC-1:** Given ein bestehender `workflow_state.json` v2 mit 108 Workflows / When `migrate_v2_to_v3.py --apply` läuft / Then liegen 108 JSON-Dateien in `.claude/workflows/<name>.json`, der aktive Workflow hat einen `.active`-Symlink, und der Roundtrip-Test bestätigt 108 Workflows mit allen erhaltenen Feldern (`current_phase`, `spec_file`, `test_artifacts`, `adversary_verdict`)

- **AC-2:** Given die Migration läuft / When sie startet / Then existiert `.backups/state-migration-pre-<ts>.tar.gz` mit dem alten `workflow_state.json`, und `workflow_state.json.bak` bleibt nach der Migration erhalten

- **AC-3:** Given v3 ist aktiv / When zwei `workflow.py status`-Aufrufe parallel laufen / Then keine Race Condition — beide liefern korrekten State, da atomare `tempfile + os.rename`-Writes keine partiellen Zustände hinterlassen

- **AC-4:** Given ein abgeschlossener Workflow / When `workflow.py complete` läuft / Then wandert die JSON nach `.claude/workflows/_archive/<name>.json`, der `.active`-Symlink wird gelöscht

- **AC-5:** Given ein Hook läuft in einem git-Worktree / When er State liest oder schreibt / Then verwendet `_get_workflows_root()` den Pfad ins Hauptrepo via `find_main_repo_from_worktree()` — Issue #112 (Worktree-Routing) funktioniert weiterhin korrekt

- **AC-6:** Given `workflow_state_multi.py` als Thin-Wrapper / When ein Bestands-Hook (z.B. `qa_gate.py`) `from workflow_state_multi import save_state, load_state, get_active_workflow` importiert / Then sind alle 14 öffentlichen Funktionen und 5 Konstanten verfügbar und verhalten sich identisch zur v2-API

- **AC-7:** Given `workflow_gate.py` oder `workflow_state_updater.py` nach der Migration / When sie laufen / Then lesen sie über `workflow_state_multi.load_state()` (nicht mehr über lokale Implementierungen direkt aus `workflow_state.json`) — R5-Patch ist appliziert

- **AC-8:** Given alle 6 Slash-Commands (`3-write-spec`, `4-tdd-red`, `5-implement`, `workflow`, `add-artifact`, `0-reset`) / When sie nach der Migration ausgeführt werden / Then funktionieren alle ihre CLI-Aufrufe (`status`, `phase`, `list`, `start`, `switch`, `advance`, `backlog`, `pause`, `reset`, `set-field`)

- **AC-9:** Given der Dry-Run-Modus / When `migrate_v2_to_v3.py` ohne `--apply` läuft / Then werden keine Files erstellt oder verändert, aber ein vollständiger Plan ausgegeben (Workflow-Namen, Zielpfade, Symlink-Ziel, geschätzte Größe)

## Expected Behavior

- **Input:** Existierende `.claude/workflow_state.json` v2 mit `workflows`-Dictionary (108 Einträge)
- **Output:** `.claude/workflows/`-Verzeichnis mit je einer JSON-Datei pro Workflow und `.active`-Symlink auf den aktiven Workflow; `workflow_state.json` zu `workflow_state.json.bak` umbenannt
- **Side effects:** Pre-Snapshot `tar.gz` in `.backups/`; alle Hooks, die `from workflow_state_multi import ...` verwenden, sehen identisches Verhalten ohne eigene Änderungen (außer R5-Patch für zwei Hooks)

## Known Limitations

- Symlink-Erstellung schlägt auf nicht-POSIX-Filesystemen fehl (irrelevant für den Linux-Server; Fallback wäre ein `active_workflow`-Feld in einer Meta-Datei, aber nicht implementiert)
- Migration ist nicht idempotent: Wenn `.claude/workflows/` bereits existiert, bricht das Skript mit Fehlerhinweis ab
- 108 Einzeldateien erhöhen die Verzeichnis-Unübersichtlichkeit; `_archive/` nimmt abgeschlossene Workflows auf — bei Bedarf kann in einem Follow-up aggressiveres Archivieren eingeführt werden
- Worktrees in `.claude/worktrees/agent-*/` haben nach der Migration möglicherweise veraltete Hook-Kopien; da diese Worktrees kurzlebig sind, werden sie beim nächsten Developer-Agent-Lauf neu erstellt

## Test Coverage

Tests in `tests/tdd/test_epic_191_state_migration.py`:

- `test_migration_dry_run_writes_no_files` — prüft dass ohne `--apply` kein File-System-Write erfolgt, aber ein Aktionsplan ausgegeben wird
- `test_migration_creates_per_workflow_json` — prüft dass nach `--apply` 108 JSON-Dateien in `.claude/workflows/` liegen
- `test_migration_roundtrip_all_fields_preserved` — lädt alle frisch geschriebenen JSONs und prüft erhaltene Felder gegen v2-Original
- `test_migration_creates_active_symlink` — prüft dass `.active` Symlink auf den aktiven Workflow zeigt
- `test_migration_creates_pre_snapshot` — prüft dass `.backups/state-migration-pre-<ts>.tar.gz` vor Migration existiert
- `test_migration_leaves_bak_file` — prüft dass `workflow_state.json.bak` nach Migration erhalten bleibt
- `test_atomic_write_no_partial_state` — prüft via parallelem Lesen dass kein partieller JSON entsteht
- `test_worktree_routing_uses_main_repo` — prüft dass `_get_workflows_root()` aus einem Worktree das Hauptrepo zurückgibt
- `test_complete_workflow_moves_to_archive` — prüft dass `workflow.py complete` die JSON nach `_archive/` verschiebt und `.active` entfernt
- `test_thin_wrapper_api_surface_complete` — importiert alle 14 Funktionen und 5 Konstanten aus `workflow_state_multi` und prüft Nicht-None
- `test_r5_patch_workflow_gate_uses_wrapper` — prüft dass `workflow_gate.py` kein direktes `workflow_state.json`-Read mehr hat
- `test_r5_patch_workflow_state_updater_uses_wrapper` — analog für `workflow_state_updater.py`

## Changelog

- 2026-05-11: Initial spec erstellt — Issue #192, Epic #191
