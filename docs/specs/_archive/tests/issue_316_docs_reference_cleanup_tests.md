---
entity_id: issue_316_docs_reference_cleanup_tests
type: tests
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [tests, docs, reference, cleanup, nicegui-removal, issue-316]
parent: issue_316_docs_reference_cleanup
phase: phase5_tdd_red
---

# Issue #316 — docs/reference Cleanup: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_316_docs_reference_cleanup.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion der Parent-Spec. Die Tests
sind reine Datei-/Inhalts-Verifikation (kein Mock, keine API) und lesen die
echten Dateien im Repo.

Parent-Spec: `docs/specs/modules/issue_316_docs_reference_cleanup.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_316_docs_cleanup.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_all_component_category_dirs_documented` | AC-1 | Jedes Unterverzeichnis von `frontend/src/lib/components/` wird in `frontend_components.md` erwähnt |
| `test_ac1_named_components_documented` | AC-1 | Alle in #316 namentlich genannten Komponenten (MapCanvas, WaypointPin, …, Wordmark) stehen im Doc |
| `test_ac2_no_nicegui_reference_in_docs_reference` | AC-2 | Keine `.md`-Datei in `docs/reference/` enthält „nicegui" (case-insensitive) |
| `test_ac3_nicegui_doc_deleted` | AC-3 | `docs/reference/nicegui_best_practices.md` existiert nicht mehr |
| `test_ac4_no_dangling_nicegui_link_in_live_tooling` | AC-4 | Weder `feature-planner.md` noch `safari_compatibility.md` verweisen auf `nicegui_best_practices.md` (parametrisiert je Datei) |
| `test_ac5_updated_date_bumped` | AC-5 | Header von `frontend_components.md` trägt `**Updated:** 2026-05-25` |
| `test_ac5_wordmark_props_documented` | AC-5 | Wordmark ist mit einem Props-Interface (`WordmarkProps`) dokumentiert |
| `test_no_phantom_cockpit_components` | Guard | Doc listet keine nicht mehr existierenden _cockpit-Komponenten (F002) |

## Test-Ausführung

```bash
# RED-Phase (vor Implementation — alle Tests sollen FAIL sein)
uv run pytest tests/tdd/test_issue_316_docs_cleanup.py -v

# GREEN-Phase (nach Implementation)
uv run pytest tests/tdd/test_issue_316_docs_cleanup.py -v
```

## Changelog

- 2026-05-25: Test-Manifest erstellt für Issue #316 (docs/reference Cleanup)
