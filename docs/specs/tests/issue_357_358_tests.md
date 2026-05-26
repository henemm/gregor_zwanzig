---
entity_id: issue_357_358_tests
type: tests
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [tests, sms, wind-exposition, token-pipeline, test-fix, issue-357, issue-358]
parent: issue_357_358_wind_exposition_sms_and_warning_token
phase: phase5_tdd_red
---

# Issue #357 + #358 — Tests

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/issue_357_358_wind_exposition_sms_and_warning_token.md`.
Jeder pytest-Test mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.

## Source

- **File:** `tests/tdd/test_issue_357_358.py` (NEU — RED-Tests für WIND_EXPOSITION im SMS-Token-Pfad und G_BOX_WARNING_BG-Test-Korrektur)

## Test Inventory

### Python (`tests/tdd/test_issue_357_358.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_sms_grat_wind_moderate` | AC-1 | Exponiertes Segment + wind_max=35 km/h → "GratWind" im SMS-String |
| `test_ac2_sms_no_exposition_no_label` | AC-2 | Kein exponierter Abschnitt → kein GratWind/GratSturm (Regressions-Guard) |
| `test_ac3_sms_grat_sturm_high` | AC-3 | Exponiertes Segment + wind_max=55 km/h → "GratSturm" im SMS-String |
| `test_ac4_warning_token_in_compare_html` | AC-4 | G_BOX_WARNING_BG in compare_html.py referenziert (korrekte Ziel-Datei) |

## Changelog

- 2026-05-26: Initial Test-Manifest erstellt. RED-Phase für Issue #357 (AC-1, AC-2, AC-3) und #358 (AC-4).
