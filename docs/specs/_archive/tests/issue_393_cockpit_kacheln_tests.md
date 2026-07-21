---
entity_id: issue_393_cockpit_kacheln_tests
type: tests
created: 2026-05-27
updated: 2026-05-27
status: draft
version: "1.0"
tags: [tests, cockpit, briefing-log, alert-log, go-handler, frontend, issue-393]
parent: issue_393_cockpit_kacheln
phase: phase5_tdd_red
---

# Issue #393 — Cockpit-Kacheln: Test-Manifest

## Approval

- [x] Approved

## Zweck

Test-Manifest für `docs/specs/modules/issue_393_cockpit_kacheln.md`.
Jeder Test mappt auf ein Acceptance Criterion der Parent-Spec.

Parent-Spec: `docs/specs/modules/issue_393_cockpit_kacheln.md` v1.0

## Source

- **Python:** `tests/tdd/test_briefing_log.py` (NEU)
- **Python:** `tests/tdd/test_alert_log.py` (NEU)
- **Go:** `internal/handler/cockpit_test.go` (NEU)
- **Frontend:** `frontend/src/lib/issue_393_cockpit_kacheln.test.ts` (NEU)

## Test Inventory

### Python: test_briefing_log.py

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_append_briefing_log_creates_file_with_entry` | AC-1 | briefing_log.json wird erstellt mit trip_id, kind, channels, sent_at |
| `test_append_briefing_log_appends_to_existing_file` | AC-1 | Zweiter Aufruf hängt Eintrag an, erster bleibt erhalten |
| `test_append_briefing_log_channels_list_preserved` | AC-1 | Mehrkanalige Liste (email+signal+telegram) korrekt gespeichert |
| `test_append_briefing_log_kind_evening` | AC-1 | kind='evening' korrekt im Eintrag |

### Python: test_alert_log.py

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_append_alert_log_creates_file_with_entry` | AC-2 | alert_log.json wird erstellt mit trip_id, sent_at, changes_count, severity |
| `test_append_alert_log_appends_to_existing` | AC-2 | Zweiter Aufruf hängt Eintrag an |
| `test_append_alert_log_purges_entries_older_than_48h` | AC-9 | Einträge älter als 48h werden beim Schreiben entfernt |
| `test_append_alert_log_retains_fresh_entries` | AC-9 | Einträge innerhalb 48h bleiben erhalten |

### Go: cockpit_test.go

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `TestCockpitStatusHandler_EmptyWhenNoLogs` | AC-3 | Leere Arrays wenn Log-Files nicht existieren (kein 500-Error) |
| `TestCockpitStatusHandler_FiltersBriefingsByToday` | AC-4/5 | Nur heutige Einträge in briefings zurückgegeben |
| `TestCockpitStatusHandler_FiltersAlertsByLast24h` | AC-6/7 | Nur Alerts der letzten 24h zurückgegeben |
| `TestCockpitStatusHandler_ReturnsJsonStructure` | AC-3 | Response hat briefings[] und alerts[] Felder |

### Frontend: issue_393_cockpit_kacheln.test.ts

| Test-Funktion | AC | Was geprüft wird |
|---|---|---|
| `test_page_server_fetches_cockpit_status` | AC-8 | +page.server.ts enthält Fetch auf /api/cockpit/status |
| `test_page_server_uses_abort_signal_timeout` | AC-8 | AbortSignal.timeout() im cockpit-Fetch vorhanden |
| `test_page_server_no_weather_endpoint` | AC-10 | Kein Wetter-Endpoint-Call in +page.server.ts |
| `test_cockpit_helpers_planned_briefings_accepts_sent_log` | AC-4/5 | plannedBriefings() hat sentLog-Parameter |

## Test-Ausführung

```bash
# Python RED-Phase
cd /home/hem/gregor_zwanzig && uv run pytest tests/tdd/test_briefing_log.py tests/tdd/test_alert_log.py -v

# Go RED-Phase
cd /home/hem/gregor_zwanzig && go test ./internal/handler/ -run TestCockpit -v

# Frontend RED-Phase
cd /home/hem/gregor_zwanzig/frontend && node --experimental-strip-types --test src/lib/issue_393_cockpit_kacheln.test.ts
```

## Expected RED-State

Alle Python/Go-Tests FAIL weil Methoden/_Handler noch nicht existieren.
Frontend-Tests FAIL weil SSR-Loader und cockpitHelpers.ts noch nicht angepasst.

## Changelog

- 2026-05-27: Initial test manifest erstellt für Issue #393 (Cockpit-Kacheln).
