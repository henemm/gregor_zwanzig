---
entity_id: issue_342_pro_metrik_horizon_backend_tests
type: tests
created: 2026-05-23
updated: 2026-05-23
status: draft
version: "1.0"
tags: [tests, backend, weather, metric-preset, schema-migration, issue-342]
parent: issue_342_pro_metrik_horizon_backend
phase: phase5_tdd_red
---

# Issue #342 — Pro-Metrik-Zeithorizont (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest fuer den Python-Renderer-Filter aus
`docs/specs/modules/issue_342_pro_metrik_horizon_backend.md`. Jeder pytest-Test
mappt 1:1 auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_342_pro_metrik_horizon_backend.md` v1.0

## Source

- **File:** `tests/tdd/test_horizon_filter.py` (NEU — Tests fuer Renderer-
  Horizon-Filter pro Etappe, derive_horizon-Mapping und Backward-Compat ohne
  horizons-Feld).
- **Go-Tests:** Companion in `internal/store/store_test.go` (Migration) und
  `internal/handler/metric_preset_test.go` (PATCH-Endpoint).

## Acceptance Criteria

- **AC-1:** Given dc_metrics mit `thunder.horizons.today=False` /
  When `visible_cols(dc_metrics, horizon="today")` aufgerufen wird /
  Then enthaelt das Ergebnis kein `thunder`, aber `wind`.
  - Test: `test_visible_cols_filters_today_metric`

- **AC-2:** Given dieselbe dc_metrics-Liste /
  When `visible_cols(dc_metrics, horizon="tomorrow")` aufgerufen wird /
  Then enthaelt das Ergebnis `thunder` (`horizons.tomorrow=True`).
  - Test: `test_visible_cols_shows_tomorrow_metric`

- **AC-3:** Given dc_metrics mit allen `horizons.*=False` /
  When `visible_cols(dc_metrics, horizon=None)` (Tag 4+) aufgerufen wird /
  Then werden alle `enabled` Metriken zurueckgegeben, disabled bleiben raus.
  - Test: `test_visible_cols_ignores_horizon_for_day4`

- **AC-7:** Given dc_metrics ohne `horizons`-Feld (Legacy) /
  When `visible_cols(dc_metrics, horizon="today")` aufgerufen wird /
  Then wird die Metrik gezeigt (Default `{true,true,true}` greift).
  - Test: `test_visible_cols_legacy_no_horizons_field`

- **AC-MAP:** Given Report-Datum 2026-05-23 /
  When `derive_horizon(report, etappe)` mit delta 0/1/2/3 aufgerufen wird /
  Then liefert die Funktion `today`/`tomorrow`/`day_after`/`None`.
  - Test: `test_derive_horizon_mapping`

- **AC-E2E:** Given drei Etappen heute/morgen/uebermorgen mit per-Metrik
  unterschiedlichen `horizons` /
  When `render_html()` die HTML-Tabellen baut /
  Then enthaelt jede Etappen-Tabelle nur die fuer ihren Horizont sichtbaren
  Spalten. (Deferred zur /5-implement-Phase, weil ein echtes
  NormalizedForecast-Fixture noetig ist.)
  - Test: `test_render_html_filters_per_stage` (`pytest.skip` im RED)

## Expected Behavior

- **Input:** `dc_metrics` als `list[dict]` mit `metric_id`, `enabled` und
  optional `horizons={today,tomorrow,day_after}`. `horizon` als
  `"today"|"tomorrow"|"day_after"|None`.
- **Output:** `list[str]` der sichtbaren `metric_id`s.
- **Side effects:** Keine — alle Tests sind pure Function-Calls auf echte
  Python-Strukturen, kein Filesystem-Touch.

## Tests

| Test | AC | Beschreibung |
|------|----|--------------|
| `test_visible_cols_filters_today_metric` | AC-1 | thunder ausgeblendet fuer today |
| `test_visible_cols_shows_tomorrow_metric` | AC-2 | thunder sichtbar fuer tomorrow |
| `test_visible_cols_ignores_horizon_for_day4` | AC-3 | horizon=None ignoriert horizons |
| `test_visible_cols_legacy_no_horizons_field` | AC-7 | Legacy-dc ohne horizons-Key |
| `test_derive_horizon_mapping` | AC-MAP | delta 0/1/2/3 → today/tomorrow/day_after/None |
| `test_render_html_filters_per_stage` | AC-E2E | E2E (skipped in RED, aktiviert in GREEN) |

## Risks

- Heutiges `visible_cols(rows: list[dict]) -> list[tuple[str, str]]` hat eine
  voellig andere Signatur als die neue `visible_cols(dc_metrics, horizon=...)`.
  In RED schlaegt der Test-Import bzw. der Funktionsaufruf mit `TypeError`
  fehl — das ist gewollt.

## Changelog

- 2026-05-23: Initial Tests-Spec fuer Issue #342, 6 Tests, mapped auf AC-1/2/3/7
  plus zwei Hilfs-ACs (AC-MAP, AC-E2E).
