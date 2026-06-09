---
entity_id: issue_648_scope_tests_neutral_tests
type: tests
created: 2026-06-08
updated: 2026-06-08
status: approved
version: "1.0"
tags: [tooling, hooks, scope-detection, guardrail]
---

# Wächter-Tests: `tests/` neutral in der Scope-Erkennung (#648)

## Approval

- [x] Approved

## Purpose

Mock-freie Tests, die beweisen, dass Dateien unter `tests/` von beiden
Scope-Erkennungs-Hooks als neutral (wie `docs/`) behandelt werden — ein reiner
Test-Commit ist `docs-only`, nicht `backend`. Verhindert die Regression der
Fehlklassifizierung aus Issue #648.

## Source

- **File:** `tests/tdd/test_scope_tests_neutral.py`
- **Implementation under test:** `.claude/hooks/e2e_commit_gate.py`
  (`detect_scope`) und `.claude/hooks/staging_gate.py`
  (`_detect_committed_scope`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| detect_scope | hook | Klassifiziert gestagte Dateien (informationell) |
| _detect_committed_scope | hook | Klassifiziert HEAD~1..HEAD (Deploy-Gate) |

## Test Cases

| # | Test | Erwartetes Verhalten |
|---|------|---------------------|
| 1 | `ac1_staged_tests_only_is_docs_only` | Nur `tests/` gestaged → `docs-only` |
| 2 | `ac2_staged_src_plus_tests_is_backend` | `src/`+`tests/` gestaged → `backend` |
| 3 | `ac3_staged_frontend_plus_tests_is_frontend_only` | `frontend/`+`tests/` → `frontend-only` |
| 4 | `ac4_staged_unknown_path_stays_backend` | `config.ini`/`.env` → `backend` |
| 5 | `ac1_committed_tests_only_is_docs_only` | Commit nur `tests/` → `docs-only` |
| 6 | `ac2_committed_src_plus_tests_is_backend` | Commit `src/`+`tests/` → `backend` |
| 7 | `ac5_both_hooks_consistent_for_tests_only` | Beide Hooks für `tests/`-only gleich (`docs-only`) |

## Test Strategy

Pro Fall ein echtes `git init`-Temp-Repo mit echten Dateien und echtem
`git add`/`commit`; die echte Funktion läuft gegen dieses Repo (CWD bzw.
`REPO_DIR`-Injektion). Keine `subprocess`-Mocks.
