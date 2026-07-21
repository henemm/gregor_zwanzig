---
entity_id: issue_396_archive_stats_tests
type: tests
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "1.0"
tags: [tests, archive, stats, briefing-log, alert-log, go-api, frontend, issue-396]
parent: issue_396_archive_stats
phase: phase5_tdd_red
---

# Issue #396 — Archiv-Statistiken: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_396_archive_stats.md`.
Jeder Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_396_archive_stats.md` v1.0

## Source

- **Python:** `tests/tdd/test_issue_396_archive_stats.py` (NEU)

## Test Inventory

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_store_go_has_briefing_count_by_trip` | AC-1 | BriefingCountByTrip existiert in store.go |
| `test_briefing_count_per_trip` | AC-1 | Briefing-Zähler pro trip_id korrekt aggregiert |
| `test_alert_retention_code_removed` | AC-2 | 48h-Retention-Code nicht mehr in trip_alert.py |
| `test_alert_count_includes_old_entries` | AC-2 | Alte Alert-Einträge werden gezählt (kein Retention-Filter) |
| `test_cockpit_still_filters_24h` | AC-3 | cockpit.go filtert weiterhin auf 24h (Regression Guard) |
| `test_store_go_has_alert_count_by_trip` | AC-4 | AlertCountByTrip existiert in store.go |
| `test_zero_counts_handled` | AC-4 | Leere Logs → 0 statt Crash oder — |
| `test_archive_stats_handler_exists` | AC-4 | archive_stats.go mit ArchiveStatsHandler vorhanden |

## Test-Ausführung

```bash
cd /home/hem/gregor_zwanzig && uv run pytest tests/tdd/test_issue_396_archive_stats.py -v
```

## Expected RED-State

- `test_store_go_has_briefing_count_by_trip` FAIL — BriefingCountByTrip fehlt
- `test_briefing_count_per_trip` FAIL — BriefingCountByTrip fehlt
- `test_alert_retention_code_removed` FAIL — 48h-Code noch vorhanden
- `test_alert_count_includes_old_entries` FAIL — AlertCountByTrip fehlt + Retention noch aktiv
- `test_cockpit_still_filters_24h` PASS — Go filtert bereits unabhängig (Regression Guard)
- `test_store_go_has_alert_count_by_trip` FAIL — AlertCountByTrip fehlt
- `test_zero_counts_handled` FAIL — archive_stats.go fehlt
- `test_archive_stats_handler_exists` FAIL — archive_stats.go fehlt

## Changelog

- 2026-05-27: Test-Manifest erstellt für Issue #396 (Archiv-Statistiken).
