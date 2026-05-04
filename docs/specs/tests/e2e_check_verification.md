---
entity_id: e2e_check_verification
type: tests
created: 2026-04-24
updated: 2026-04-24
status: draft
version: "1.0"
tags: [e2e, commit-gate, scope, tdd, tests]
---

# Tests: E2E Commit Gate — check_verification() Scope-Based Logic (#86)

## Approval

- [x] Approved

## Purpose

TDD-Tests fuer die `check_verification()` Funktion in `.claude/hooks/e2e_commit_gate.py`.
Validiert die scope-basierte Verifikationslogik: automatische Scope-Erkennung,
Scope-Hierarchie-Vergleich und Backward-Kompatibilitaet.

## Source

- **File:** `tests/tdd/test_e2e_check_verification.py`
- **Identifier:** alle `test_check_verification_*` Funktionen

## Test-Uebersicht

### Covered Test Functions

- `check_verification_docs_only_skips_gate`
- `check_verification_no_json_returns_false`
- `check_verification_stale_timestamp_returns_false`
- `check_verification_corrupt_json_returns_false`
- `check_verification_missing_timestamp_returns_false`
- `check_verification_missing_required_field_backend`
- `check_verification_frontend_only_missing_server_restart_blocks`
- `check_verification_no_scope_field_backward_compat`
- `check_verification_frontend_only_passes_with_server_restart_only`
- `check_verification_backend_passes_with_all_fields`
- `check_verification_full_stack_verified_covers_backend_commit`
- `check_verification_scope_too_low_full_stack_blocked`
- `check_verification_scope_too_low_backend_vs_frontend_blocked`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `e2e_commit_gate` | Hook-Modul | Modul unter Test |
| `e2e_scope_detection` | Spec | Uebergeordnete Feature-Spec |
| `pytest` | Test-Framework | monkeypatch, tmp_path Fixtures |

## Implementation Details

Tests nutzen zwei Monkeypatches:
- `e2e_commit_gate.detect_scope` → gibt definierten Scope zurueck
- `e2e_commit_gate.find_project_root` → zeigt auf `tmp_path`

Damit wird kein echter git-Zustand benoetigt. `e2e_verified.json` wird
direkt in `tmp_path/.claude/` geschrieben.

## Expected Behavior

- **GRUENE Tests** (8): Bestehende Logik unveraendert — docs-only, kein JSON, Timestamp, korrupt etc.
- **ROTE Tests** (5): Schlagen fehl bis Implementierung — frontend-only Scope, Scope-Hierarchie, Message mit Scope

## Known Limitations

- Tests mocken `detect_scope()` direkt, nicht `subprocess.run` — sauberere Isolation
- Keine Integration mit echtem git-Index (kein `git add` noetig)

## Changelog

- 2026-04-24: Initial spec fuer TDD RED Phase (#86)
