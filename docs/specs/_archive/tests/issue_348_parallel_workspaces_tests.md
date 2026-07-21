---
entity_id: issue_348_parallel_workspaces_tests
type: tests
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [tests, workflow, hooks, worktree, parallel-sessions, settings, tooling, issue-348]
parent: issue_348_parallel_workspaces
phase: phase5_tdd_red
---

# Issue #348 — Isolierte Parallel-Workspaces (Test-Manifest)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer die isolierten clone-basierten Parallel-Workspaces aus
`docs/specs/modules/issue_348_parallel_workspaces.md`. Jeder Test mappt 1:1 auf
ein Acceptance Criterion der Parent-Spec. KEINE Mocks — alle Workspace-Tests
fuehren ECHTE git-Operationen in `tmp_path` aus (Quell-Repo via `git init`,
Klon via `gz-workspace new`).

Parent-Spec: `docs/specs/modules/issue_348_parallel_workspaces.md` v1.0

## Source

- **File (Python):** `tests/tdd/test_issue_348_parallel_workspaces.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_issue_348_parallel_workspaces.py`)

| Test-Funktion | AC | Was geprueft wird |
|---|---|---|
| `test_settings_no_hardcoded_repo_path` | AC-1 | `.claude/settings.json` enthaelt keinen hardcoded Praefix `/home/hem/gregor_zwanzig/.claude/hooks` mehr. Bleibt ROT bis der Orchestrierer settings.json umstellt. |
| `test_settings_hooks_use_project_dir_var` | AC-1 | Jeder Hook-`command` mit `.claude/hooks/` nutzt `${CLAUDE_PROJECT_DIR}`. Bleibt ROT bis der Orchestrierer settings.json umstellt. |
| `test_settings_valid_json_and_mq_absolute` | AC-2 | `.claude/settings.json` parst als valides JSON; der SessionStart-claude-mq-`command` bleibt exakt `bash /home/hem/claude-mq/check-messages.sh`. |
| `test_new_creates_isolated_clone` | AC-3 | `gz-workspace new wstest` erzeugt `<ws-root>/wstest` mit eigenem `.git`, Branch `ws/wstest`; Quell-Working-Tree bleibt unveraendert. |
| `test_list_shows_workspace` | AC-4 | `gz-workspace list` zeigt Name `wstest` und Branch `ws/wstest`. |
| `test_clean_refuses_dirty_without_force` | AC-5 | `gz-workspace clean wstest` ohne `--force` bricht bei uncommitteten Aenderungen ab (exit != 0, Verzeichnis bleibt); mit `--force` wird entfernt. |
| `test_new_preserves_settings_verbatim` | AC-6 | Klon-`settings.json` ist zeichengleich zur Quelle; behaelt `${CLAUDE_PROJECT_DIR}`; zeigt nicht auf das Quell-Repo. |
| `test_only_tooling_layer` | AC-7 | Allowlist der #348-Dateien — kein Pfad beginnt mit `src/`/`api/`/`internal/`/`frontend/`. |

## RED-Erwartung

- AC-1 (`test_settings_no_hardcoded_repo_path`, `test_settings_hooks_use_project_dir_var`)
  bleibt ROT, bis der Orchestrierer `.claude/settings.json` umstellt
  (Lockout-Risiko, ausserhalb des Developer-Scopes).
- AC-3/4/5/6 sind ROT bis `.claude/tools/gz-workspace` existiert; nach GREEN
  sind sie gruen.
- AC-2/AC-7 sind unabhaengig vom Skript und sofort gruen.

## Changelog

- 2026-05-23: Initial test manifest fuer Issue #348.
