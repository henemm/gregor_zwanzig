---
entity_id: issue_180_alert_metric_table_tests
type: tests
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
tags: [tests, alerts, frontend, svelte, issue-180, epic-139]
parent: issue_180_alert_metric_table
phase: phase5_tdd_red
---

# Issue #180 — Alert-Konfigurator: Schwellwert-Tabelle (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für `docs/specs/modules/issue_180_alert_metric_table.md`.
Da Issue #180 rein Frontend ist (Svelte-Komponenten, kein Python-Code),
prüfen die Tests Datei-Existenz und Inhalts-Invarianten der Svelte-Dateien.

## Source

- **File:** `tests/tdd/test_issue_180_alert_metric_table.py` (NEU)

## Test Inventory

### Python (`tests/tdd/test_issue_180_alert_metric_table.py`)

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_ac1_alerts_tab_svelte_exists` | AC-1 | `alerts-tab/AlertsTab.svelte` existiert |
| `test_ac1_alert_metric_table_svelte_exists` | AC-1 | `alerts-tab/AlertMetricTable.svelte` existiert |
| `test_ac1_alert_metric_row_svelte_exists` | AC-1 | `alerts-tab/AlertMetricRow.svelte` existiert |
| `test_ac1_metric_row_has_testid` | AC-1 | AlertMetricRow.svelte enthält `alert-metric-row-` testid |
| `test_ac2_delta_only_metrics_referenced` | AC-2 | AlertMetricRow.svelte importiert `DELTA_ONLY_METRICS` |
| `test_ac3_table_references_alert_rules` | AC-3 | AlertMetricTable.svelte referenziert `alert_rules` |
| `test_ac4_tab_calls_api_put` | AC-4 | AlertsTab.svelte enthält `api.put` |
| `test_ac4_tab_includes_alert_rules_in_payload` | AC-4 | AlertsTab.svelte enthält `alert_rules` im Save-Block |
| `test_ac6_tab_imports_cooldown_card` | AC-6 | AlertsTab.svelte importiert `AlertCooldownCard` |
| `test_ac7_tab_imports_quiet_hours_card` | AC-7 | AlertsTab.svelte importiert `AlertQuietHoursCard` |
| `test_ac8_tab_includes_cooldown_minutes` | AC-8 | AlertsTab.svelte enthält `alert_cooldown_minutes` |
| `test_trip_tabs_wires_alerts_tab` | AC-1 | TripTabs.svelte importiert `AlertsTab` (kein Platzhalter mehr) |

## Implementation Details

Tests im RED-Modus schlagen fehl, weil:
- `AlertsTab.svelte`, `AlertMetricTable.svelte`, `AlertMetricRow.svelte` noch nicht existieren
  → `FileNotFoundError` bei `Path(...).read_text()`
- `TripTabs.svelte` enthält noch nicht `AlertsTab`
  → Assertion `'AlertsTab' in content` schlägt fehl

In GREEN-Phase bestehen alle Tests, wenn die Svelte-Dateien mit den erwarteten
Inhalten erstellt wurden.

## Acceptance Criteria

- **AC-T1:** Given die Implementierung fehlt /
  When `pytest tests/tdd/test_issue_180_alert_metric_table.py -v` läuft /
  Then schlagen mindestens 11 der 12 Tests fehl (RED-Phase).

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When `pytest tests/tdd/test_issue_180_alert_metric_table.py -v` läuft /
  Then sind alle 12 Tests grün.

## Changelog

- 2026-05-18: Initial — Test-Manifest für Issue #180.
