---
entity_id: issue_205_followup_read_path_tests
type: tests
created: 2026-05-14
updated: 2026-05-14
status: draft
version: "1.0"
tags: [tests, go, read-path, follow-up-205]
parent: issue_205_followup_read_path
phase: phase5_tdd_red
---

# Issue #205 Follow-Up — Read-Path-Coercion (Tests)

## Approval

- [x] Approved

## Purpose

Test-Manifest für den Hot-Fix `issue_205_followup_read_path`.

## Source

- **File:** `internal/store/store_trip_read_test.go` (NEU oder erweitert)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `TestLoadTrip_LegacyJSONCoercesNilAlertRulesToEmpty` | AC-1 | Legacy-JSON ohne `alert_rules` → `LoadTrip()` liefert `[]AlertRule{}`. |
| `TestLoadTrip_PreservesExistingAlertRules` | AC-2 | JSON mit 3 Rules → `LoadTrip()` liefert 3 Rules unverändert. |
| `TestLoadTrip_MarshalAfterLoadProducesEmptyArrayNotNull` | AC-3 | Nach `LoadTrip()` produziert `json.Marshal(trip)` `"alert_rules":[]`, nie `null`. |

## Acceptance Criteria

- **AC-T1:** Given die Test-Datei existiert + Implementation fehlt /
  When `go test ./internal/store/` läuft /
  Then schlagen mindestens 2 von 3 Tests fehl.

- **AC-T2:** Given GREEN-Phase abgeschlossen /
  When derselbe Go-Test-Lauf ausgeführt wird /
  Then alle 3 Tests grün.

## Changelog

- 2026-05-14: Initial — Test-Manifest für Read-Path-Coercion.
