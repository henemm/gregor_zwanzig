---
entity_id: issue_334_triphero_cleanup_tests
type: tests
created: 2026-05-24
updated: 2026-05-24
status: draft
version: "1.0"
tags: [tests, cleanup, dead-code, frontend, trip-detail, issue-334]
parent: issue_334_triphero_cleanup
phase: phase5_tdd_red
---

# Issue #334 — TripHero Cleanup: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_334_triphero_cleanup.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec. Die
Tests sind grep-/Datei-Existenz-basiert: vor dem Cleanup ROT (toter Code
vorhanden), nach dem Cleanup GRÜN.

Parent-Spec: `docs/specs/modules/issue_334_triphero_cleanup.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_334_triphero_cleanup.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_triphero_svelte_file_removed` | AC-1 | `TripHero.svelte` existiert nicht mehr |
| `test_ac2_barrel_reexport_removed` | AC-2 | `index.ts` re-exportiert `TripHero` nicht mehr (0 Treffer) |
| `test_ac3_no_triphero_reference_anywhere_in_frontend` | AC-3 | kein `TripHero`-Bezeichner in `frontend/src` + `frontend/e2e` (case-sensitiv) |
| `test_ac4_dead_e2e_spec_removed` | AC-4 | `trip-detail-hero.spec.ts` existiert nicht mehr |
| `test_ac5_orphan_util_functions_removed` | AC-5 | `getActiveStageDisplay`/`getNextBriefing`/`parseHHMM`/`compareHHMM` aus `tripHero.ts` entfernt |
| `test_ac6_surviving_util_functions_intact` | AC-6 | `getDaysLabel` + `formatDateRange` bleiben in `tripHero.ts` (Über-Lösch-Guard) |
| `test_ac7_orphan_tests_removed_survivors_intact` | AC-7 | verwaiste Tests aus `tripHero.test.ts` entfernt, überlebende Tests intakt |

AC-8 (`npm run build`) und AC-9 (`node --test` der überlebenden Util-Tests) werden
bewusst als Befehls-Verifikation in Phase 6/Validate geprüft — nicht in der
pytest-Suite, um den `pre_commit_gate`-Volllauf nicht zu verlangsamen.

## Test-Ausführung

```bash
# RED-Phase (vor Cleanup — Lösch-Asserts sollen FAIL sein)
uv run pytest tests/tdd/test_issue_334_triphero_cleanup.py -v

# GREEN-Phase (nach Cleanup)
uv run pytest tests/tdd/test_issue_334_triphero_cleanup.py -v
```

## Changelog

- 2026-05-24: Test-Manifest erstellt für Issue #334 (Cleanup TripHero.svelte)
