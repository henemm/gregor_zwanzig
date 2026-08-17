---
entity_id: fix_1931_heartbeat_warn_spam
type: module
created: 2026-08-17
updated: 2026-08-17
status: draft
version: "1.0"
tags: [scheduler, heartbeat, bugfix]
---

# Fix #1931: warnMissingHeartbeatOnce spammt infra bei jedem Prod-Neustart

## Approval

- [ ] Approved

## Purpose

`briefingDispatch()` löst bei jedem erfolgreichen Lauf `pingHeartbeat("briefing_dispatch", s.heartbeatComparePresets)` aus. Da `HEARTBEAT_COMPARE_PRESETS` in Prod bewusst dauerhaft leer ist (Überwachung läuft stattdessen über den bestehenden "Gregor20 Core"-Heartbeat, #1898), löst dieser Aufruf bei jedem Prod-Neustart eine neue MQ-Warnung an `infra` aus (In-Memory-`sync.Once` überlebt keinen Neustart) — 14× seit dem 30.07.2026. Dieses Modul stellt sicher, dass der akzeptierte Zustand "briefing_dispatch ohne konfigurierte Heartbeat-URL" nur noch lokal geloggt, aber nicht mehr als MQ-Warnung an `infra` gemeldet wird — ohne den generischen `pingHeartbeat`/`warnMissingHeartbeatOnce`-Mechanismus für andere Jobs zu verändern.

## Source

- **File:** `internal/scheduler/scheduler.go`
- **Identifier:** `func (s *Scheduler) briefingDispatch()` (Zeile ~297), `func (s *Scheduler) pingHeartbeat(jobName, url string)` (Zeile ~694), `func (s *Scheduler) warnMissingHeartbeatOnce(jobName string)` (Zeile ~711)

## Estimated Scope

- **LoC:** ~+15/-5
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/config/config.go` (`HEARTBEAT_COMPARE_PRESETS`) | config | Liefert die (in Prod bewusst leere) `heartbeatComparePresets`-URL |
| `s.notifier` (MQ-Sender-Function-Field) | internal collaborator | Wird vom generischen `warnMissingHeartbeatOnce` weiterhin für andere Jobs genutzt |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `internal/scheduler/scheduler.go` | MODIFY | `briefingDispatch()` ruft bei leerer `heartbeatComparePresets`-URL nicht mehr `pingHeartbeat()` (und damit nicht mehr `warnMissingHeartbeatOnce`) auf, sondern schreibt nur einen lokalen Log-Eintrag. Bei gesetzter URL bleibt der bisherige Ping-Aufruf unverändert. |
| `internal/scheduler/scheduler_test.go` | MODIFY | Neue/angepasste Assertions, die belegen, dass `briefing_dispatch` bei leerer URL keinen `notifier`-Aufruf mehr auslöst, während der generische Mechanismus (anderer `jobName`, leere URL) unverändert genau einmal pingt. |

### Estimated Changes
- Files: 2
- LoC: +15/-5

## Implementation Details

`briefingDispatch()` prüft nach dem bestehenden "beide Teil-Jobs ok"-Gate zusätzlich, ob `s.heartbeatComparePresets` leer ist:

- Ist die URL gesetzt → unverändertes Verhalten: `s.pingHeartbeat("briefing_dispatch", s.heartbeatComparePresets)` (HTTP-GET an BetterStack).
- Ist die URL leer → **kein** Aufruf von `pingHeartbeat`/`warnMissingHeartbeatOnce` mehr für `briefing_dispatch`; stattdessen ein einzeiliger `log.Printf`, dass der Heartbeat für diesen Job absichtlich deaktiviert ist (Verweis auf #1898 im Kommentar).

Der generische Pfad `pingHeartbeat` → `warnMissingHeartbeatOnce` (inkl. `sync.Once`-Semantik pro `jobName`) bleibt für alle anderen (auch künftige) Jobs unverändert bestehen — es wird kein Code aus diesen Funktionen entfernt, nur der Aufrufer `briefingDispatch()` verzweigt vor dem Aufruf.

## Expected Behavior

- **Input:** `briefingDispatch()` läuft erfolgreich durch (beide Teil-Jobs `status: ok`); `s.heartbeatComparePresets` ist leer (Prod-Normalfall).
- **Output:** Kein Aufruf von `s.notifier(...)`, kein HTTP-Request an BetterStack. Ein lokaler Log-Eintrag markiert den Zustand als erwartet/akzeptiert.
- **Side effects:** Keine MQ-Nachricht an `infra` mehr bei Prod-Neustarts für diesen Job. Andere Jobs (hypothetisch, aktuell keine weiteren Aufrufer von `pingHeartbeat` mit leerer URL) lösen bei leerer URL weiterhin genau eine MQ-Warnung pro Prozesslaufzeit aus.

## Acceptance Criteria

- **AC-1:** Given `briefingDispatch()` läuft mit leerer `heartbeatComparePresets`-URL und beide Teil-Jobs melden `status: ok` / When der Dispatch abgeschlossen ist / Then wurde `s.notifier` kein einziges Mal aufgerufen (0 Calls), auch nach mehrfachem Aufruf von `briefingDispatch()` im selben Prozess.
  - Test: `sched.notifier` als zählende Test-Funktion injizieren, `sched.briefingDispatch()` mit leerer `HeartbeatComparePresets` und Erfolgs-Stubs für beide Teil-Endpunkte mehrfach aufrufen, Call-Count auf 0 prüfen.

- **AC-2:** Given der generische `pingHeartbeat`-Mechanismus wird für einen anderen `jobName` als `briefing_dispatch` mit leerer URL aufgerufen (z. B. `another_job`) / When `pingHeartbeat(jobName, "")` ausgeführt wird / Then wird `s.notifier` genau einmal mit `recipient="infra"` aufgerufen (Bestandsschutz Issue #118).
  - Test: bestehender/angepasster `TestPingHeartbeat_EmptyURL_TriggersNotifier`-artiger Test bleibt grün, ruft `sched.pingHeartbeat("another_job", "")` auf und prüft `len(calls) == 1` sowie `recipient == "infra"`.

- **AC-3:** Given `briefingDispatch()` läuft mit gesetzter, nicht-leerer `heartbeatComparePresets`-URL / When beide Teil-Jobs `ok` melden / Then wird der Heartbeat wie bisher exakt einmal per HTTP-GET gepingt (unverändertes Verhalten, kein Regressions-Risiko für den konfigurierten Fall).
  - Test: bestehender `TestBriefingDispatch_HeartbeatOnlyOnCompareOk` Subtest "both ok -> heartbeat pinged exactly once" bleibt unverändert grün.

## Known Limitations

- Der Fix ist gezielt auf `briefing_dispatch` beschränkt; sollte künftig ein weiterer Job dauerhaft ohne Heartbeat-URL betrieben werden sollen, braucht dieser Job denselben expliziten Leer-URL-Zweig (kein generischer Opt-out-Mechanismus wird hier eingeführt).
- Der lokale Log-Eintrag bei leerer URL ersetzt keine aktive Überwachung — die Überwachung für `briefing_dispatch` läuft weiterhin ausschließlich über den externen "Gregor20 Core"-Heartbeat (`check-gregor20.sh`, #1898).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Bugfix-Korrektur eines bereits getroffenen Betriebs-Entscheids (Überwachung via #1898 statt `HEARTBEAT_COMPARE_PRESETS`); kein neues Architektur-Muster, keine neue Entscheidungsfläche.

## Changelog

- 2026-08-17: Initial spec created
