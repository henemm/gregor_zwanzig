---
entity_id: issue_379_session_self_isolate_tests
type: tests
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [tests, hooks, infrastructure, session, worktree, parallel-sessions]
parent: issue_379_session_self_isolate
phase: phase5_tdd_red
---

# Issue 379 — Selbst-Isolierung + Leichen-Bug (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/issue_379_session_self_isolate.md`. Jeder
pytest-Test mappt 1:1 auf ein Acceptance Criterion (AC-1..AC-9) der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_379_session_self_isolate.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_379_session_self_isolate.py` (NEU) — KEINE Mocks.
  Echte tote/lebende PIDs (`subprocess.Popen` + `terminate`, `os.getpid()`),
  echte temporäre Registry-Dateien (`tmp_path`), echtes `git check-ignore`. Das
  Hook-Modul `session_singleton_guard` wird direkt importiert (`.claude/hooks`
  via `sys.path`).

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_dead_pid_with_fresh_last_seen_is_dead` | AC-1 | Eintrag mit toter PID + frischem `last_seen` → `_is_alive()` liefert `False` (Leichen-Bug behoben). |
| `test_ac2_live_pid_is_alive` | AC-2 | Eintrag mit lebender PID (`os.getpid()`) + altem `last_seen` → `_is_alive()` liefert `True`. |
| `test_ac3_no_pid_uses_last_seen_fallback` | AC-3 | Eintrag ohne `pid` → Fallback auf `last_seen`-Fenster (frisch=True, alt=False). |
| `test_ac4_reap_removes_dead_pid_corpse` | AC-4 | `_reap_dead()` entfernt die tote-PID-Leiche; `_owner_sid()` benennt den lebenden Eintrag als Inhaber. |
| `test_ac5_enterworktree_is_rescue` | AC-5 | `_is_rescue_command("EnterWorktree", …)` → `True` (Selbst-Isolierung erlaubt). |
| `test_ac6_exitworktree_is_not_rescue` | AC-6 | `_is_rescue_command("ExitWorktree", …)` → `False` (kein Rückweg). |
| `test_ac7_worktree_cwd_detected` | AC-7 | `_is_worktree_cwd()` erkennt Pfade unter `.claude/worktrees/` (True) vs. normale Pfade (False). |
| `test_ac8_gz_workspace_rescue_still_works` | AC-8 | Reiner `gz-workspace`-Bash-Aufruf bleibt Rettungsweg; verkettete Kommandos bleiben blockiert (Regression). |
| `test_ac9_worktreeinclude_only_gitignored` | AC-9 | `.worktreeinclude` enthält `.env` + `.claude/validator.env`, alle Einträge sind gitignored, kein `node_modules/`/`.venv/`. |

## Known Limitations

- PID-Recycling im Testfenster (zwischen `wait()` und Assertion) theoretisch
  möglich, praktisch vernachlässigbar — siehe Parent-Spec „Known Limitations".

## Changelog

- 2026-05-25: Initial test manifest (Issue #379)
