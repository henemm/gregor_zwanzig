---
entity_id: issue_1346_silent_briefing_outage
type: module
created: 2026-07-23
updated: 2026-07-23
status: draft
version: "1.0"
tags: [scheduler, monitoring, heartbeat, observability, go]
---

# #1346 — Stiller Briefing-Totalausfall wird laut

## Approval

- [x] Approved (PO „freigabe" 2026-07-23)

## Purpose

Ein Totalausfall des stündlichen Trip-Briefing-Versands (alle Touren scheitern am
Wetterabruf) muss aktiv alarmieren statt still zu bleiben. Heute pingt der einzige
überwachte Heartbeat nur am Ortsvergleich-Erfolg und verdeckt so einen kompletten
Briefing-Ausfall; es gibt keine Betreiber-Meldung.

## Source

- **File:** `internal/scheduler/scheduler.go`
- **Identifier:** `briefingDispatch()`, `tripReports()`, `comparePresetsDaily()`, `recordRun()`, `pingHeartbeat()`

## Estimated Scope

- **LoC:** ~+55/-8
- **Files:** 1 Code (`internal/scheduler/scheduler.go`) + 1 Test (`internal/scheduler/scheduler_unify_test.go`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `s.heartbeatComparePresets` (ENV `HEARTBEAT_COMPARE_PRESETS`) | wiederverwendet | wird zum Briefing-Dispatch-Heartbeat umgewidmet; URL/ENV unverändert |
| `s.notifier` (MQ `gregor`→`infra`) | wiederverwendet | edge-getriggerter Alarm, 1:1 nach `dataWriteSelftest`-Muster |
| `s.lastRuns[jobID].Status` | gelesen | Erfolgs-/Fehler-Gate beider Jobs |

## Implementation Details

**Grundprinzip — keine neuen Ressourcen:** Kein neuer BetterStack-Heartbeat
(Kontingent voll). Der bestehende Ping wird konsolidiert und schärfer gegated.

1. **Ping-Umzug + Konsolidierung** (`briefingDispatch()`):
   - `pingHeartbeat`-Aufruf aus `comparePresetsDaily()` **entfernen**.
   - Nach `tripReports()` und `comparePresetsDaily()` beide `lastRuns`-Status lesen.
   - Nur wenn **`trip_reports_hourly` == "ok" UND `compare_presets_daily` == "ok"**
     → `pingHeartbeat("briefing_dispatch", s.heartbeatComparePresets)`.
   - Ist einer der beiden Jobs `error` → **kein** Ping (externes Monitoring alarmiert
     durch ausbleibenden Heartbeat).

2. **Edge-getriggerter MQ-Alarm** (analog `dataWriteSelftest()`):
   - Vor `tripReports()` den bisherigen `trip_reports_hourly`-Status als `prevStatus`
     merken; nach dem Lauf den aktuellen lesen.
   - Übergang **ok→error** (inkl. erster Lauf ohne Vorzustand): MQ an `infra`,
     Priorität `high`, Betreff nennt Briefing-Totalausfall + Fehlertext.
   - Übergang **error→ok**: Recovery-Notiz an `infra`, Priorität `normal`.
   - Kein `sync.Once` — ein späterer Re-Onset im langlebigen Prozess muss erneut alarmieren.

3. **Fail-soft unverändert:** leere Heartbeat-URL → bestehendes
   `warnMissingHeartbeatOnce`; der MQ-Alarm greift URL-unabhängig.

## Expected Behavior

- **Input:** stündlicher `briefingDispatch()`-Tick (Go-Cron).
- **Output:**
  - Beide Jobs ok → genau **1** Heartbeat-Ping, **kein** MQ-Alarm.
  - `trip_reports_hourly` error (Totalausfall) → **0** Heartbeat-Pings, **1** MQ-Alarm `high` an `infra`.
  - error→ok im Folgetick → 1 Heartbeat-Ping + 1 Recovery-MQ `normal`.
- **Side effects:** BetterStack-Heartbeat, MQ-Nachrichten. Kein Python-/Datenpfad berührt.

## Acceptance Criteria

- **AC-1:** Given ein `briefingDispatch()`-Lauf, bei dem der Trip-Briefing-Job für
  mindestens einen Nutzer einen Totalausfall meldet (`failed > 0`) / When der Tick
  abgeschlossen ist / Then wird der Briefing-Heartbeat **nicht** gepingt und der
  Job-Status im Scheduler ist `error`.
  - Test: Go-Test mit httptest-Fake: trip-reports-Endpoint liefert `{"failed":1}`,
    compare-presets ok → Heartbeat-Server erhält **0** Requests; `Status()` zeigt
    `trip_reports_hourly=error`.

- **AC-2:** Given ein `briefingDispatch()`-Lauf, bei dem **beide** Jobs erfolgreich
  sind / When der Tick abgeschlossen ist / Then wird der Briefing-Heartbeat **genau
  einmal** gepingt und **kein** MQ-Alarm gesendet.
  - Test: Go-Test: beide Fake-Endpoints ok → Heartbeat-Server erhält genau 1 Request,
    Notifier-Spy 0 Aufrufe.

- **AC-3:** Given der Trip-Briefing-Job kippt von `ok` (Vortick) auf `error` (Totalausfall)
  / When der Tick abgeschlossen ist / Then geht **eine** MQ-Nachricht mit Priorität
  `high` an `infra`, deren Betreff den Briefing-Totalausfall benennt.
  - Test: Go-Test: erst ein ok-Tick, dann ein error-Tick → Notifier-Spy erhält genau
    1 Aufruf `("gregor","infra","high",…)`; Betreff enthält Bezug auf Briefing/Totalausfall.

- **AC-4:** Given der Trip-Briefing-Job bleibt über zwei aufeinanderfolgende Ticks
  `error` / When der zweite Tick abgeschlossen ist / Then wird **keine** zweite
  identische MQ-Nachricht gesendet (Edge-Trigger, kein Dauerspam); bei Erholung
  (`error`→`ok`) geht genau eine Recovery-Notiz `normal`.
  - Test: Go-Test: error-Tick → 1 Alarm; zweiter error-Tick → 0 weitere Alarme;
    ok-Tick → 1 Recovery-Aufruf `normal`.

## Known Limitations

- Der Heartbeat deckt jetzt den **gesamten** stündlichen Briefing-Dispatch (Trip +
  Ortsvergleich) ab. Ein Ortsvergleich-Fehler unterdrückt den Heartbeat ebenfalls —
  das ist beabsichtigt (bereits heutiges Verhalten) und die korrekte Readiness-Semantik.
- BetterStack-Monitor-Label heißt technisch weiter „compare-presets", bis infra es
  kosmetisch auf „briefing-dispatch" umbenennt (MQ #53434). Rein kosmetisch, URL bleibt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine neue Entscheidungsfläche — die Änderung korrigiert die
  Readiness-Semantik eines bestehenden Heartbeats und spiegelt zwei etablierte,
  getestete Muster (`comparePresetsDaily`-Heartbeat, `dataWriteSelftest`-MQ). Die
  Heartbeat-Readiness-Regel ist bereits in `~/.claude/CLAUDE.md` verankert.

## Changelog

- 2026-07-23: Initial spec created
