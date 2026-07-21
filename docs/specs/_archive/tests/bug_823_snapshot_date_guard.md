---
entity_id: bug_823_snapshot_date_guard_tests
type: tests
created: 2026-06-20
updated: 2026-06-20
status: approved
version: "1.0"
tags: [alerts, snapshot, bug]
---

# Tests — Bug #823: Alert-Pfad Datums-Guard für Snapshot

## Approval

- [x] Approved

## Purpose

Tests für `_get_cached_weather()` in `TripAlertService` — stellt sicher, dass
der datierte Snapshot (heute) Vorrang vor dem undatierten hat (der nach
Abend-Briefing auf morgen zeigt).

## Test File

`tests/tdd/test_issue_823_snapshot_date_guard.py`

## Covered Entities

- `dated_snapshot_preferred_over_undated`
- `undated_fallback_when_no_dated_exists`
- `evening_briefing_stale_snapshot_does_not_trigger_false_alert`

## Tests

**dated_snapshot_preferred_over_undated (AC-1):**
Undatierter Snapshot (morgen, 20 mm) + datierter Snapshot für heute (2 mm) →
`_get_cached_weather()` gibt den datierten zurück (precip=2.0).

**undated_fallback_when_no_dated_exists (AC-2):**
Nur undatierter Snapshot vorhanden → Fallback-Rückgabe des undatierten.

**evening_briefing_stale_snapshot_does_not_trigger_false_alert (AC-3):**
E2E: Abend-Briefing schreibt undatierten Snapshot mit morgen-Daten (20 mm) +
datierter Snapshot heute (2 mm) + frischer Nowcast (2 mm) → kein Alert.

## Changelog

- 2026-06-20: Tests für Bug #823 erstellt
