---
entity_id: worktree_state_routing_tests
type: tests
created: 2026-05-02
updated: 2026-05-02
status: active
version: "1.0"
tags: [tests, hooks, worktree]
parent: worktree_state_routing
---

# Worktree State Routing Tests

## Approval

- [x] Approved

## Purpose

Test entity manifest fuer den Hot-Fix aus Issue #112. Stellt sicher, dass die
Hooks aus einem git worktree heraus ihren State zentral ins Hauptrepo schreiben
statt lokal in den Worktree.

## Source

- **File:** `tests/tdd/test_worktree_state_routing.py`
- **Spec:** `docs/specs/modules/worktree_state_routing.md` v1.0

## Test Inventory

### TDD (`tests/tdd/test_worktree_state_routing.py`)

| Test | Asserts |
|---|---|
| find_project_root_in_worktree_returns_main_repo | `config_loader.find_project_root()` aus einem Worktree gibt den Hauptrepo-Pfad zurueck |
| get_state_file_path_in_worktree_routes_to_main | `config_loader.get_state_file_path()` zeigt im Worktree auf `<main>/.claude/workflow_state.json` |
| workflow_state_multi_get_state_file_in_worktree_routes_to_main | `workflow_state_multi.get_state_file()` (Duplikat-Funktion) leitet ebenfalls ins Hauptrepo |
| find_project_root_in_main_repo_unchanged | Sanity-Check: Im normalen Hauptrepo bleibt `find_project_root()` unveraendert |

## Fixtures

- `fake_worktree`: Erzeugt unter `tmp_path` ein Hauptrepo (mit `.git/` als Verzeichnis und
  `.git/worktrees/agent-test/`) plus einen Worktree-Pfad (mit `.git` als Datei,
  Inhalt `gitdir: <main>/.git/worktrees/agent-test`). Wechselt `cwd` in den Worktree.
- `hooks_on_path`: Stellt sicher, dass `.claude/hooks/` im `sys.path` liegt und
  raeumt geladene Hook-Module nach jedem Test wieder ab (wegen `lru_cache`).

## Changelog

- 2026-05-02: Initial test spec - Hot-Fix Issue #112.
