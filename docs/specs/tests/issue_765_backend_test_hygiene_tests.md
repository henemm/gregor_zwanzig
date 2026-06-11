---
entity_id: issue_765_backend_test_hygiene_tests
type: tests
created: 2026-06-11
updated: 2026-06-11
status: draft
version: "1.0"
tags: [tests, hygiene, backend, cleanup, gate, issue-765]
parent: issue_765_backend_test_hygiene
phase: phase5_tdd_red
---

# Issue #765 — Backend-Test-Hygiene-Sweep: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_765_backend_test_hygiene.md`.
Das Detektor-Gate prüft die Test-Artefakte selbst (Compliance-Test, kein
Produkt-Verhalten) und verhindert Regress des Backend-Datei-Inhalt-Anti-Patterns.

Parent-Spec: `docs/specs/modules/issue_765_backend_test_hygiene.md` v1.0

## Source

- **File:** `tests/tdd/test_765_backend_hygiene_compliance.py` (NEU, `# doc-compliance-test`)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_765_no_product_source_read` | AC-1, AC-2, AC-4 | Parametrisiert über alle `tests/**.py`: keine `read_text()`/grep-Reads auf Produkt-`.py`/`.go`-Quelltext (`src`/`api`/`internal`/`cmd`); echte Pfad-Auflösung statt Datei-Namen-Substring; `# doc-compliance-test`-Markierung schützt nicht vor Produkt-Quelltext-Reads (Bypass-Schutz). |
| `test_alert_segment_times_render_in_local_time` | AC-3 | Ersatz für `test_bug_400_alert_tz`: echte Alert-Mail rendern, Segment-Zeit erscheint in Lokalzeit (Europe/Paris → 10:00–14:00) in HTML + Plain. |
| `test_alert_local_time_differs_from_utc` | AC-3 | Alert-Mail-Render unter tz=UTC vs. Europe/Paris unterscheidet sich; Lokalzeit verschiebt das UTC-Fenster (Bug #400-Kern). |

## Mapping zu Acceptance Criteria

- **AC-1:** Gate listet vor dem Sweep ≥14 Offender, grün danach — via Pfad-Auflösung.
- **AC-2:** Keine Offender-Datei liest noch Produkt-`.py`/`.go`-Inhalt; gemischte Dateien behalten behaviorale Asserts.
- **AC-3:** Rein source-inspizierende Dateien gelöscht (anderswo gedeckt) oder auf echten Verhaltenstest umgestellt — ohne neue Mocks.
- **AC-4:** `# doc-compliance-test` rechtfertigt nur Doku-/Tooling-/Daten-Reads, niemals Produkt-Quelltext.
- **AC-5:** Diff berührt nur `tests/`/`docs/`/`.claude/`, kein Produktcode, kein neuer Mock.
