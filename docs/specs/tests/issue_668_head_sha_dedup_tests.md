---
entity_id: issue_668_head_sha_dedup_tests
type: tests
created: 2026-06-08
updated: 2026-06-08
status: active
version: "1.0"
tags: [tests, hooks, e2e, staging-gate]
parent: issue_668_head_sha_dedup
---

# Issue #668 — _head_sha Dedup Tests

## Approval

- [x] Approved

## Purpose

Test-Manifest für Issue #668: `staging_gate.write_verdict()` darf `git rev-parse HEAD`
nur einmal pro Aufruf ausführen (vorher zweimal). Mock-freier Nachweis über echte
Subprozess-Zählung via PATH-Shim-`git`.

## Source

- **File:** `tests/tdd/test_issue_668_head_sha_dedup.py`
- **Spec:** `docs/specs/modules/issue_668_head_sha_dedup.md` v1.0

## Test Inventory

### TDD (`tests/tdd/test_issue_668_head_sha_dedup.py`)

| Test | Asserts |
|---|---|
| test_ac1_head_sha_called_once_without_override | AC-1: `write_verdict` ohne Override führt `git rev-parse HEAD` genau 1× aus (vor Fix: 2×) — gezählt über echten PATH-Shim |
| test_ac2_verified_commit_matches_head | AC-2: geschriebene Attestation enthält `verified_commit == aktueller HEAD-SHA` (Regressionsschutz) |
| test_ac3_override_path_still_works | AC-3: mit `--e2e-path`-Override wird dorthin geschrieben, `verified_commit` korrekt, weiterhin genau 1× rev-parse |

## Fixtures

- `patched_repo`: Erzeugt unter `tmp_path` ein echtes Git-Repo (2 Commits, damit
  `HEAD~1` für die scope-Detektion existiert), patcht `staging_gate.REPO_DIR` +
  `CANONICAL_E2E_PATH` darauf, legt eine leere Findings-Datei an und installiert
  den zählenden `git`-Shim auf `PATH`.
- `_install_counting_git`: Schreibt ein echtes `git`-Bash-Skript, das nur
  `rev-parse HEAD` in eine Zählerdatei protokolliert und ansonsten an das echte
  `git` delegiert.

## Changelog

- 2026-06-08: Initiale Test-Spec für Issue #668 (Nebenbefund aus #665 F002).
