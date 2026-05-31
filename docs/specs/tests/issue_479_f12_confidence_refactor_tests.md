---
entity_id: issue_479_f12_confidence_refactor_tests
type: tests
created: 2026-05-31
updated: 2026-05-31
status: approved
version: "1.0"
tags: [tests, weather-pattern, sms, f12, issue-479]
parent: issue_479_f12_confidence_refactor
phase: phase5_tdd_red
---

# Issue #479 — F12 WL-Block aus Konfidenz: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_479_f12_confidence_refactor.md`.
Jeder pytest-Test mappt auf ein Acceptance Criterion (AC-1 bis AC-10) der
Parent-Spec. Keine Mocks — pure-funktionale Tests auf `compute_stability`,
strukturelle Tests auf Klassen-Felder / Methoden-Signaturen.

Parent-Spec: `docs/specs/modules/issue_479_f12_confidence_refactor.md` v1.0

## Source

- **File:** `tests/tdd/test_issue_479_f12_confidence_refactor.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_stability_result_has_no_score_field` | AC-1 | `StabilityResult` hat kein `score` / `component_scores`, dafür `confidence_pct` |
| `test_stability_from_high_confidence` | AC-2 | `[80, 90, 75]` → STABIL, `confidence_pct=75` |
| `test_stability_from_medium_confidence` | AC-3 | `[80, 60, 55]` → WECHSELHAFT, `confidence_pct=55` |
| `test_stability_from_low_confidence` | AC-4 | `[80, 45]` → FRAGIL, `confidence_pct=45` |
| `test_stability_none_values_ignored` | AC-5 | `[None, 80, None]` → STABIL |
| `test_stability_all_none_returns_none` | AC-6 | `[None, None]` → `None` |
| `test_stability_empty_list_returns_none` | AC-7 | `[]` → `None` |
| `test_wl_token_not_in_sms_output` | AC-8 | `"WL"` ist **nicht** in `STD_SYMBOLS` |
| `test_z500_method_removed_from_provider` | AC-9 | `OpenMeteoProvider._fetch_ensemble_with_z500` existiert nicht |
| `test_weather_pattern_service_no_provider_param` | AC-10 | `WeatherPatternService.__init__` hat keinen `provider`-Parameter |

## Test-Ausführung

```bash
uv run pytest tests/tdd/test_issue_479_f12_confidence_refactor.py -v
```

## Changelog

- 2026-05-31: Initial Test-Manifest für Issue #479
