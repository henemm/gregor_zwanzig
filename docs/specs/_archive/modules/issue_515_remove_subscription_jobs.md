---
entity_id: issue_515_remove_subscription_jobs
type: module
created: 2026-06-01
updated: 2026-06-01
status: draft
version: "1.0"
tags: [scheduler, cleanup, compare]
---

# Issue #515: morning_subscriptions + evening_subscriptions entfernen

## Approval

- [ ] Approved

## Purpose

Die Jobs `morning_subscriptions` (07:00) und `evening_subscriptions` (18:00) sind seit
Commit b8e34f0 (feat #490) obsolet. Sie lesen ausschließlich `compare_subscriptions.json`
und sind vollständig durch `compare_presets_daily` (06:00) ersetzt.

Issue #509 hat einen Doppelversand-Guard als Workaround eingebaut. Dieser Guard wird
zusammen mit den Jobs entfernt, weil es keinen Grund mehr gibt, ihn zu brauchen.

Es gibt nur einen Nutzer (henning), der vollständig auf Presets migriert ist. Der
06:00/07:00-Drift war kein bewusstes Design.

## Source

- **`internal/scheduler/scheduler.go`** — Go-Cron-Jobs + Heartbeat-Felder
- **`internal/config/config.go`** — `HeartbeatMorning`/`HeartbeatEvening` Felder
- **`api/routers/scheduler.py`** — Python-Endpoints + Funktionen + Guard
- **`tests/tdd/test_issue_509_preset_migration.py`** — Guard-Tests entfernen

## Estimated Scope

- **LoC:** ~-200 (nur Löschungen)
- **Files:** 4
- **Effort:** low

## Dependencies

- `internal/scheduler/scheduler.go` → cron-Registrierung, Heartbeat
- `internal/config/config.go` → `HeartbeatMorning`, `HeartbeatEvening`
- `api/routers/scheduler.py` → Endpoints, `_run_subscriptions_by_schedule`, `_run_weekly_subscriptions`
- `tests/tdd/test_issue_509_preset_migration.py` → `TestDoubleDispatchGuard`-Klasse

## Acceptance Criteria

**AC-1:** Given der Scheduler läuft / When 07:00 und 18:00 erreicht werden /
Then werden KEINE `morning_subscriptions`- oder `evening_subscriptions`-Jobs ausgelöst —
die Jobs existieren nicht mehr im Cron.

**AC-2:** Given `api/routers/scheduler.py` / When die Datei geladen wird /
Then existieren weder der `/morning-subscriptions`-Endpoint noch `/evening-subscriptions`,
noch die Funktionen `_run_subscriptions_by_schedule` oder `_run_weekly_subscriptions`.

**AC-3:** Given `api/routers/scheduler.py` / When die Datei geladen wird /
Then existiert kein Doppelversand-Guard-Code mehr (weder `_preset_path`-Variable noch
`"Doppelversand-Guard"`-Kommentar) — der Guard war nur für das alte System nötig.
Der `data_root`-Parameter in `_run_compare_presets_daily` bleibt erhalten (wird von Tests genutzt).

**AC-4:** Given `compare_presets_daily` läuft um 06:00 / When Presets vorhanden /
Then sendet der Job wie bisher — kein Regressionsrisiko durch die Löschungen.

**AC-5:** Given `tests/tdd/test_issue_509_preset_migration.py` /
Then enthält die Datei nur noch die `TestEmpfaengerFallback`-Klasse (mail_to-Fallback bleibt
gültig) — die `TestDoubleDispatchGuard`-Klasse ist entfernt.

## Implementation Plan

### Go: `internal/scheduler/scheduler.go`

Entfernen:
- Cron-Einträge für `morning_subscriptions` (Z. 95) und `evening_subscriptions` (Z. 96)
- Methoden `morningSubscriptions()` und `eveningSubscriptions()` (~Z. 148–170)
- Struct-Felder `heartbeatMorning` und `heartbeatEvening` (~Z. 45–46)
- Struct-Initialisierung dieser Felder (~Z. 74–75)

### Go: `internal/config/config.go`

Entfernen:
- `HeartbeatMorning string` (~Z. 19)
- `HeartbeatEvening string` (~Z. 20)

### Python: `api/routers/scheduler.py`

Entfernen:
- Endpoint `POST /morning-subscriptions` + `trigger_morning()` (~Z. 20–26)
- Endpoint `POST /evening-subscriptions` + `trigger_evening()` (~Z. 29–36)
- Funktion `_run_subscriptions_by_schedule()` (~Z. 127–189)
- Funktion `_run_weekly_subscriptions()` (~Z. 192–252)

**Kein Änderungsbedarf in `_run_compare_presets_daily`** — der mail_to-Fallback (Issue #509
AC-2) bleibt vollständig erhalten. Der `data_root`-Parameter in `_run_compare_presets_daily`
bleibt ebenfalls (wird von Tests genutzt).

### Tests: `tests/tdd/test_issue_509_preset_migration.py`

Entfernen:
- Klasse `TestDoubleDispatchGuard` komplett (6 Tests, alle testen entfernte Funktionen)

Erhalten:
- Klasse `TestEmpfaengerFallback` komplett (2 Tests, testen `_run_compare_presets_daily`)

## Changelog

- **2026-06-01** — Spec erstellt. Aufgedeckt nach #509: Guard war Workaround für unnötige Parallelität.

## Out of Scope

- Entfernen von `compare_subscriptions.json`-Dateien auf dem Server (Backup, kein Handlungsbedarf)
- Entfernen von `_save_subscription()` / `_send_subscription()` — könnten noch von `manual_send_subscription` genutzt werden
- BetterStack-Heartbeat-Tokens für `HEARTBEAT_MORNING`/`HEARTBEAT_EVENING` deaktivieren — separat über BetterStack-UI
