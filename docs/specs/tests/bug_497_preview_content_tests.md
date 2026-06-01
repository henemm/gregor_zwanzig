---
entity_id: bug_497_preview_content_tests
type: tests
created: 2026-05-31
updated: 2026-05-31
status: draft
version: "1.0"
tags: [tests, preview, sms, fixture-provider, demo-mode, issue-497]
parent: bug_497_preview_content
phase: phase5_tdd_red
---

# Issue #497 — Preview-Inhalt falsch (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/bug_497_preview_content.md`.
Prüft zwei Bugs: SMS-Präfix-Kürzung (Bug 1) und fehlende Fixture-Felder (Bug 2).
Kein Mocking — conftest.py setzt GZ_TEST_FIXTURE_DIR automatisch (FixtureProvider).

## Source

- **File:** `tests/tdd/test_bug_497_preview_content.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_bug_497_preview_content.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `ac1_sms_prefix_uses_id_before_colon` | AC-1 | `render_sms_preview()` für Stage "KHW_10: von Egger Alm..." liefert token_line mit Präfix "KHW_10:" |
| `ac2_fixture_provides_cloud_low_pct` | AC-2 | `FixtureProvider.fetch_forecast()` liefert `cloud_low_pct` als Integer (nicht None) |
| `ac3_fixture_provides_pop_pct` | AC-3 | `FixtureProvider.fetch_forecast()` liefert `pop_pct` als Integer (nicht None) |
| `ac4_fixture_provides_snowfall_limit_m` | AC-4 | `FixtureProvider.fetch_forecast()` liefert `snowfall_limit_m` als Integer > 0 (nicht None) |
| `ac5_fixture_provides_wind_direction_deg` | AC-5 | `FixtureProvider.fetch_forecast()` liefert `wind_direction_deg` als Integer 0–359 (nicht None) |

## Implementation Details

- Kein Mocking. conftest autouse-Fixture setzt GZ_TEST_FIXTURE_DIR auf fixtures/openmeteo/.
- AC-1: Echter PreviewService-Aufruf mit trip 5f534011 (henning), target_date 2026-05-31.
- AC-2–5: Direkter FixtureProvider(FIXTURE_DIR)-Aufruf, fetch_forecast() für Innsbruck (47.2692, 11.4041).
- RED-Phase: Tests schlagen fehl, weil Fixture-JSONs die 4 Felder nicht enthalten und preview_service.py:151 noch replace() nutzt.

## Expected Behavior

- **Input:** Trip 5f534011, Stage 2026-05-31, FixtureProvider mit fixtures/openmeteo/*.json
- **Output:** token_line beginnt mit "KHW_10:"; ForecastDataPoint hat cloud_low_pct/pop_pct/snowfall_limit_m/wind_direction_deg ≠ None
- **Side effects:** keine HTTP-Calls dank FixtureProvider

## Acceptance Criteria

- **AC-T1:** Given Tests geschrieben, Fixes noch nicht implementiert / When pytest läuft / Then alle 5 Tests rot (RED-Phase korrekt).
- **AC-T2:** Given GREEN-Phase abgeschlossen / When pytest läuft / Then alle 5 Tests grün, kein Mocking.

## Changelog

- 2026-05-31: Initial — Test-Manifest für Issue #497.
