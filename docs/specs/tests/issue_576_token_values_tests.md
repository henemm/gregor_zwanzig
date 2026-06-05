---
entity_id: issue_576_token_values_tests
type: tests
created: 2026-06-05
status: draft
version: "1.0"
tags: [tests, design-fidelity, issue-576, epic-575, foundation]
parent: issue_576_tokens_sync_v2
phase: phase5_tdd_red
---

# Issue #576 — Token-Werte computed-style-Tests (Playwright)

## Approval

- [x] Approved

## Purpose

Verhaltensbasierter Test der 3 driftenden Token-Werte. Injiziert auf einer
authentifizierten Staging-Seite Test-DIVs mit `var(--g-r-3)`, `var(--g-r-4)`,
`var(--g-info)`, liest den computed style. Prüft dass die Effektivwerte
den JSX-Vorgaben entsprechen.

Parent-Spec: `docs/specs/modules/issue_576_tokens_sync_v2.md`.

## Source

- **File:** `tests/tdd/test_issue_576_token_values.py`

## Test → AC Mapping

| Test-Funktion-Entity | AC | Was wird geprüft |
|---------------------|----|------------------|
| `issue_576_g_r_3_is_6px` | AC-1 | computed style `border-radius` mit `var(--g-r-3)` == `6px` |
| `issue_576_g_r_4_is_10px` | AC-2 | computed style `border-radius` mit `var(--g-r-4)` == `10px` |
| `issue_576_g_info_is_2c5a8c` | AC-3 | computed style `background-color` mit `var(--g-info)` == `rgb(44, 90, 140)` (= `#2c5a8c`) |

## Test-Strategie

- Echter Browser via Playwright (Chromium headless).
- Login mit Validator-Credentials auf Staging.
- Navigate auf `/archiv` (lädt `app.css` über die App).
- Pro Test: dynamisch DIV mit CSS-Variable injizieren, computed style lesen.
- Keine Mocks, keine Dateiinhalt-Checks — echter Browser-Render-Test.

## TDD-RED-Erwartung

Aktueller Staging-Stand (Commit `4e5a912c`) hat die alten Werte
(`--g-r-3: 8px`, `--g-r-4: 12px`, `--g-info: rgb(42, 108, 179)`).
Alle 3 Tests schlagen fehl bis `frontend/src/app.css` die JSX-Werte setzt.
