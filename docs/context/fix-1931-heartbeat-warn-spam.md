# Context: #1931 — warnMissingHeartbeatOnce spammt infra bei jedem Prod-Neustart

## Analysis

### Type
Bug

### Symptom
`infra` erhält bei jedem Prod-Neustart von `gregor-api` erneut die MQ-Nachricht
"Heartbeat-URL für Job \"briefing_dispatch\" nicht konfiguriert" — 14× seit dem
30.07.2026 (henemm-infra#149). Die zugrunde liegende Konfiguration
(`HEARTBEAT_COMPARE_PRESETS` leer) ist inzwischen bewusst und dauerhaft so
gewollt: Überwachung läuft seit #1898 stattdessen über den bestehenden
"Gregor20 Core"-Heartbeat via `check-gregor20.sh` (Abschnitt 2 + 2b).

### Root Cause
- `internal/scheduler/scheduler.go:297-309` — `briefingDispatch()` ruft bei
  jedem erfolgreichen Lauf `s.pingHeartbeat("briefing_dispatch",
  s.heartbeatComparePresets)`.
- `internal/scheduler/scheduler.go:694-698` — `pingHeartbeat` ruft bei leerer
  URL `s.warnMissingHeartbeatOnce(jobName)`.
- `internal/scheduler/scheduler.go:709-736` — `warnMissingHeartbeatOnce`
  verwendet `sync.Once` **pro Prozesslaufzeit** (`s.onceMissingHB[jobName]`).
  Der Once-Zustand ist In-Memory und überlebt keinen Neustart → jeder
  Prod-Neustart erzeugt eine neue MQ-Nachricht.
- `internal/config/config.go:19` — `HEARTBEAT_COMPARE_PRESETS` hat
  `default:""`, ist in Prod absichtlich leer.

### Affected Files (erwartete Änderung)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | `briefingDispatch()` ruft für den Job `briefing_dispatch` bei leerer URL keine MQ-Warnung mehr aus |
| `internal/scheduler/scheduler_test.go` | MODIFY | Bestehende Assertions zu `warnMissingHeartbeatOnce`/`pingHeartbeat` für `briefing_dispatch` anpassen, sofern sie das alte (spammende) Verhalten fixieren |

### Bestehender Test aus #118 (Bestandsschutz)
`scheduler_test.go` prüft seit #118 den *allgemeinen* Mechanismus
(leere Heartbeat-URL → genau eine MQ-Notification, once-per-jobName). Dieser
Mechanismus bleibt für andere Jobs gültig und wird NICHT entfernt — nur der
konkrete Aufruf für `briefing_dispatch` mit der bewusst leeren
`heartbeatComparePresets`-URL darf keine MQ-Warnung mehr auslösen.

### Scope Assessment
- Files: 2 (1 Produktivcode, 1 Test)
- Estimated LoC: ~+15/-5
- Risk Level: LOW (isolierte Funktion, kein Datenpfad, kein Nutzerbezug)

### Technical Approach
`briefingDispatch()` ruft für `briefing_dispatch` künftig **nicht mehr**
`pingHeartbeat` (das den Warnpfad auslöst), sondern nur noch das normale
GET, wenn eine URL konfiguriert ist — bei leerer URL wird für genau diesen
Job kein `warnMissingHeartbeatOnce` mehr aufgerufen (nur noch ein Log-Eintrag,
kein MQ-Versand). Die generische `pingHeartbeat`/`warnMissingHeartbeatOnce`-
Maschinerie bleibt für andere, künftige Jobs unverändert nutzbar.

### Dependencies
Keine. Reiner Go-Scheduler-Code, kein Python-Core, kein Frontend.

### Open Questions
Keine — Ursache und Fix sind eindeutig, PO-Entscheidung (Konfiguration bleibt
leer) liegt bereits als MQ-Nachricht von `infra` vor.
