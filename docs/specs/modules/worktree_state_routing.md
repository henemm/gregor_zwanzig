---
entity_id: worktree_state_routing
type: module
created: 2026-05-02
updated: 2026-05-02
status: approved
version: "1.0"
tags: [hooks, infrastructure, worktree]
---

# Worktree State Routing

## Approval

- [x] Approved (Hot-Fix fuer Issue #112, im Auftrag des Product Owners)

## Purpose

Verhindert, dass `.claude/`-Hooks ihre State-Dateien (insbesondere
`workflow_state.json`) in git-Worktrees schreiben. Stattdessen werden alle
Schreibzugriffe konsistent ins Hauptrepo geleitet, sodass Workflow-State auch
bei Developer-Agent-Worktrees zentral erhalten bleibt.

## Source

- **File:** `.claude/hooks/config_loader.py` (Single Source of Truth)
- **Identifier:** `find_project_root`, `get_state_file_path`, neue Helper `find_main_repo_from_worktree`
- **File:** `.claude/hooks/workflow_state_multi.py` (Konsolidierung)
- **Identifier:** `get_state_file` — wird zu Thin-Wrapper, der `config_loader.get_state_file_path()` zurueckgibt

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `pathlib.Path` | stdlib | Pfad-Operationen, Worktree-Erkennung via `.git`-Marker |
| Git Worktree Format | extern | `.git` ist Datei mit `gitdir: <pfad>`-Inhalt |

## Implementation Details

```
1. Worktree-Erkennung:
   - Falls `<cwd>/.git` eine Datei ist: Worktree.
   - Inhalt parsen ("gitdir: <pfad>") -> Pfad zeigt auf
     <main_repo>/.git/worktrees/<worktree-name>.
   - Hauptrepo-Pfad = parent.parent von gitdir.

2. find_project_root() in config_loader.py:
   - Ruft zuerst find_main_repo_from_worktree(cwd).
   - Liefert es ein Hauptrepo, wird dieses zurueckgegeben.
   - Sonst: bestehende Suche nach config-Dateien / .git-Verzeichnis.

3. get_state_file() in workflow_state_multi.py:
   - Wird zu Thin-Wrapper: `from config_loader import get_state_file_path`
     (mit sys.path-Fallback wie in anderen Hooks) und delegiert direkt.
   - Damit Single Source of Truth in config_loader, keine Logik-Drift moeglich.
```

## Expected Behavior

- **Input:** Aktuelles Arbeitsverzeichnis (`Path.cwd()`).
- **Output:**
  - Im normalen Hauptrepo: unveraendert (Pfad zum Hauptrepo).
  - Im Worktree (`.git` ist Datei): Pfad zum verlinkten Hauptrepo.
- **Side effects:** Keine (reine Pfad-Berechnung).

## Known Limitations

- Wenn der `.git`-Datei-Inhalt kein gueltiges `gitdir:` enthaelt, faellt die
  Funktion auf den Worktree-Pfad zurueck (defensiv, kein Crash).
- `lru_cache` auf `find_project_root` muss in Tests via `cache_clear()` zurueckgesetzt
  werden, da sich `cwd` zwischen Tests aendert.

## Test Coverage

Tests in `tests/tdd/test_worktree_state_routing.py`:

- `find_project_root_in_worktree_returns_main_repo` - prueft dass `find_project_root()`
  aufgerufen aus einem Worktree den Hauptrepo-Pfad zurueckgibt.
- `get_state_file_path_in_worktree_routes_to_main` - prueft dass `get_state_file_path()`
  im Worktree auf `<main>/.claude/workflow_state.json` zeigt.
- `workflow_state_multi_get_state_file_in_worktree_routes_to_main` - prueft das
  Duplikat in `workflow_state_multi.py:get_state_file()` mit derselben Erwartung.
- `find_project_root_in_main_repo_unchanged` - Sanity-Check: im normalen Hauptrepo
  bleibt das Verhalten unveraendert.

## Changelog

- 2026-05-02: Initial spec - Hot-Fix fuer Issue #112 (Worktree-Hook-Kollision).
