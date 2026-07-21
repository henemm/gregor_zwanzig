---
entity_id: issue_384_hook_fail_open_tests
type: tests
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [tests, bug, workflow, hooks, fail-open, issue-384]
parent: issue_384_hook_fail_open
phase: phase5_tdd_red
---

# Issue #384 — Hook fail-open: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_384_hook_fail_open.md`. Jeder Test
liest die **echten** `${CLAUDE_PROJECT_DIR}`-Command-Strings aus
`.claude/settings.json` und führt sie als echte Subprozesse aus, wobei
`${CLAUDE_PROJECT_DIR}` auf eine isolierte tmp-Sandbox zeigt (An-/Abwesenheit
der Hook-Datei wird gesteuert; Stub-Hooks `sys.exit(0/2)` ersetzen die echten
Gates). **Keine Mocks.**

Parent-Spec: `docs/specs/modules/issue_384_hook_fail_open.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_384_hook_fail_open.py` (NEU)

## Test → Acceptance-Criterion-Mapping

| Test-Funktion | AC | Verhalten |
|---------------|----|-----------|
| `test_settings_json_is_valid_json` | AC-6 | settings.json bleibt valides JSON (auch mit eingebettetem `if … fi`) |
| `test_found_project_dir_commands` | — | Sanity: das Parsing findet die zu härtenden Hook-Commands überhaupt (>=10) |
| `test_every_hook_is_fail_open_guarded` | AC-5 | JEDER `${CLAUDE_PROJECT_DIR}`-Command entspricht `if [ -f … ]; then python3 … ; fi` (RED solange ungehärtet) |
| `test_missing_hook_file_allows_tool` | AC-1/AC-3 | Fehlende Hook-Datei → Exit 0 (Tool erlaubt, kein Lockout) — RED solange ungehärtet (bare `python3` → Exit≠0) |
| `test_present_blocking_hook_still_blocks` | AC-2 | Vorhandener Hook mit Exit 2 → Exit 2 bleibt (fail-open weicht echte Blocks NICHT auf, No-Regression) |
| `test_present_ok_hook_allows` | AC-4 | Vorhandener Hook mit Exit 0 → Exit 0 (bestehende Gates unverändert, No-Regression) |

Die parametrisierten Tests (`test_every_hook_…`, `test_missing_…`,
`test_present_…`) laufen je einmal pro `${CLAUDE_PROJECT_DIR}`-Hook-Command der
settings.json (aktuell 24).

## RED-Erwartung (Phase 5)

Gegen die aktuelle (ungehärtete) `settings.json` schlagen fehl:
- `test_every_hook_is_fail_open_guarded` (alle Parametrisierungen — Commands sind
  bare `python3 …`, nicht gewrappt),
- `test_missing_hook_file_allows_tool` (alle Parametrisierungen — bare `python3`
  auf fehlende Datei endet mit Exit≠0 = Block statt Exit 0).

Bereits grün (No-Regression-Wächter): `test_settings_json_is_valid_json`,
`test_found_project_dir_commands`, `test_present_blocking_hook_still_blocks`,
`test_present_ok_hook_allows`. Nach dem Fix (Inline-Guard pro Command) müssen
**alle** grün sein.

## Changelog

- 2026-05-26: Initial test manifest (#384)
