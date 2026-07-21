---
entity_id: bug_823_snapshot_date_guard
type: module
created: 2026-06-20
updated: 2026-06-20
status: approved
version: "1.0"
tags: [alerts, snapshot, bug]
---

# Bug #823 — Alert-Pfad: datierter Snapshot hat Vorrang

## Approval

- [x] Approved

## Purpose

`TripAlertService._get_cached_weather()` lädt bisher nur den undatierten Snapshot
`{trip_id}.json`. Nach dem Abend-Briefing enthält dieser aber `target_date=morgen`,
wodurch der Alert die falsche Etappe als Referenz benutzt. Der Fix priorisiert den
datierten Snapshot `{trip_id}_{YYYY-MM-DD}.json` für heute.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService._get_cached_weather`

## Estimated Scope

- **LoC:** ~10
- **Files:** 1 (+ 1 Testdatei)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherSnapshotService.load_dated` | call | Lädt datierten Snapshot für heute |
| `WeatherSnapshotService.load` | call | Fallback wenn kein datierter Snapshot |

## Acceptance Criteria

**AC-1: dated_snapshot_preferred_over_undated**
Given ein undatierter Snapshot (Abend-Briefing, morgen-Daten) und ein datierter Snapshot für heute /
When `_get_cached_weather()` aufgerufen wird /
Then wird der datierte Snapshot (heute) zurückgegeben, nicht der undatierte.

**AC-2: undated_fallback_when_no_dated_exists**
Given nur ein undatierter Snapshot existiert (kein dated) /
When `_get_cached_weather()` aufgerufen wird /
Then wird der undatierte Snapshot zurückgegeben (Rückwärts-Kompatibilität).

**AC-3: evening_briefing_stale_snapshot_does_not_trigger_false_alert**
Given datierter Snapshot für heute (2 mm) + undatierter Snapshot mit morgen-Daten (20 mm) /
When Alert-Lauf mit frischem Nowcast (2 mm, passend zum heutigen Snapshot) /
Then kein Alert — kein falsches Δ durch Verwendung des morgen-Snapshots.

## Changelog

- 2026-06-20: Initial spec created (Bug #823)
