# Context: fix-2149-scheduler-budget-teilb

## Request Summary
Issue #2149, Scheibe B: Ein hängender Nutzer darf die Scheduler-Läufe (Briefings, Alarme) der übrigen Nutzer nicht mehr aufhalten. Gefordert sind ein Zeitbudget je Nutzeraufruf und ein Gesamtbudget je Lauf, ohne dass der hängende Nutzer dadurch wieder unsichtbar wird. Scheibe A (Sichtbarkeit je Nutzer) ist seit 16.09. live (`7d2ac763`).

Vorgänger-Kontext (Stand vor Scheibe A, Zeilennummern veraltet): `docs/context/fix-2149-scheduler-nutzer-budget.md`.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/scheduler/scheduler.go:166` | Geteilter `http.Client{Timeout: 3000 s}` (#1912) — einziges Zeitlimit je Nutzeraufruf |
| `internal/scheduler/scheduler.go:243-298` | `runForAllUsers`: sequenzielle Schleife, `classifyUserOutcome` (:325), `userState.Record` (:274), `Prune` (:291), `sendBundledUserAlerts` (:344) |
| `internal/scheduler/scheduler.go:707-759` | `triggerEndpointForUser`: `client.Post` **ohne Context** (:709); Klassifikation Timeout→partial, Transport/HTTP≥400/`failed>0`→hart, `status=partial`→partial |
| `internal/scheduler/scheduler.go:73-79` | `isTimeoutTransportError`: `net.Error.Timeout()` ODER `context.DeadlineExceeded` ⇒ partial ⇒ kein Alarm (Falle 1) |
| `internal/scheduler/scheduler.go:634-683` | `recordRun` mit `TryLock`: Folge-Ticks übersprungen (`overlapState.SkippedSinceLastRun`), solange Vorgänger läuft |
| `internal/scheduler/scheduler.go:188-214` | Job-Registrierung (Takte siehe unten) |
| `internal/scheduler/scheduler.go:844-950` | `overlapField`, `usersField`, `Status()` — Andockpunkt für „läuft noch/übersprungen" |
| `internal/scheduler/scheduler.go:230-234` | `Stop()` wartet nur auf cron-gestartete Funktionen, nicht auf abgeleitete Goroutinen |
| `internal/scheduler/user_run_state.go` | Scheibe A: `scheduler_user_state.json`, Schwellen 3/8 (:26-29), `userJobRecord` (:32), `recordLocked` (:157-197), `aggregateLocked` (:221), `fanOutJobIDs` (:274); Persistenz nur in `Prune` |
| `cmd/server/main.go:120-140` | `sched.Start()`, `defer sched.Stop()`, `ListenAndServe` ohne Signal-Handling |
| `api/routers/scheduler.py` | Alle Scheduler-Endpoints sync `def` ⇒ Threadpool, Verbindungsabbruch stoppt die Arbeit NICHT (Falle 2); alert-checks liefert `status:"partial"`, `reason:"deadline"` (:74-83) |
| `src/services/briefing_slots.py:50,98,125,213` | Claim mit `CLAIM_TTL=900` schützt Trip-Briefings vor Doppelversand |
| `src/services/throttle_store.py:101-133` | `is_throttled` (reines Lesen) und `record` getrennt — Check-then-record-Lücke im Alarmpfad |
| `src/services/trip_alert.py:61-66,833-974` | `ALERT_RUN_DEADLINE_SECONDS=90`, nur am Anfang jeder Trip-Iteration geprüft (:866); Kommentar veraltet (120 s, scheduler.go:82) |
| `src/services/compare_alert.py:173,404` | Compare-Alarm: Throttle-Check/-Record, keine Reservierung |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh:119-200,752-790` | Externer Konsument von `/api/scheduler/status`; verlangt `last_run.time` < 20 min für 5 Alarm-Jobs |

## Jobs
| Job | Takt | Art |
|---|---|---|
| trip_reports_hourly + compare_presets_daily (in `briefing_dispatch`) | `0 * * * *` | Fan-out |
| alert_checks, compare_alert_checks, compare_official_alert_checks | `*/15` | Fan-out |
| radar_alert_checks, compare_radar_alert_checks | `7,22,37,52` | Fan-out |
| inbound_command_poll, premium_sms_poll | `*/5` | global |
| data_write_selftest | `*/15` | global, lokal |

Jobs laufen untereinander bereits parallel (eigene Goroutine je Cron-Eintrag); innerhalb eines Jobs ist die Nutzerschleife sequenziell.

## Existing Patterns
- **Überlappungsschutz auf Job-Ebene:** `TryLock` + `overlapState` + `overlapField` im Status — Vorbild für einen Nutzer-Ebenen-Marker „läuft noch".
- **Pro-Nutzer-Buchführung (Scheibe A):** `userRunState.Record(job, uid, outcome, err)` mit Kantenbildung und gebündeltem MQ-Alarm; neues Ergebnis (z. B. `skipped`/`budget`) würde hier andocken.
- **Harte Frist im Job statt längerer Aufrufer-Wartezeit:** ADR-0038 (`docs/adr/0038-zeitgrenze-je-nutzerlauf-unter-aufrufer-wartezeit.md`); Python-Seite liefert sichtbares `partial`.
- **Doppelversand-Schutz per Claim:** `briefing_slots.reserve`/`record_outcome`/`release` (nur Trip-Briefing).
- **Tests:** `httptest`-Server mit `time.Sleep`/Signalkanal, `sched.client = &http.Client{Timeout: 50ms}`, `recordingNotifier`; keine Fake-Clock.

## Dependencies
- **Upstream:** Python-Core-Endpoints (`api/routers/scheduler.py`), `store.ListUserIDs`, Notifier (MQ `gregor`→`infra`), `userRunState`-Datei.
- **Downstream:** `/api/scheduler/status` (unauthentifiziert, Account-Seite), `check-gregor20.sh` (henemm-infra), BetterStack-Heartbeat (`briefingDispatch` pingt nur bei beiden `ok`), Tests in `internal/scheduler/*_test.go`.

## Existing Specs
- `docs/specs/modules/fix_2149_scheduler_nutzer_sichtbarkeit.md` — Scheibe A; Out-of-Scope-Block :30-41 beschreibt Scheibe B (Budget je Aufruf + Gesamtbudget, eigene Fehlerklasse, In-Flight-Marker, rotierende Nutzerreihenfolge, sequenziell, Parallelität nur mit ADR ab ~8–10 Nutzern)
- `docs/specs/modules/scheduler_multi_user.md` — :26 continue-on-error, :32 sequenziell bleibt
- `docs/specs/modules/fix_1912_scheduler_briefing_timeout.md` — Begründung 3000 s, Timeout ⇒ partial ohne Alarm
- `docs/reference/api_contract.md:1307,2546` — zwei Bedeutungen von partial; Timeout ohne MQ-Alarm
- ADR-0038 — harte Frist im Job-Code

## Risks & Considerations
1. **Klassifikationsfalle:** Ein `context.WithTimeout` je Nutzer landet über `isTimeoutTransportError` als `partial` ⇒ kein Alarm ⇒ der hängende Nutzer ist wieder unsichtbar. Budget-Überschreitung braucht eine eigene Fehlerklasse.
2. **Doppellauf:** Go-Abbruch stoppt Python nicht. Re-Trigger im nächsten Tick ⇒ Trip-Briefing durch Claim geschützt, **Alarmpfad nicht** (Throttle-Lücke) ⇒ doppelter, nutzersichtbarer Alarm möglich. Spricht für „nicht abbrechen, sondern aufhören zu warten" + In-Flight-Marker, der den Nutzer im nächsten Tick sichtbar überspringt.
3. **Budget-Arithmetik:** Ticket nennt 120 s, #1912 setzte bewusst 3000 s (echter Versand 319 s); alert-checks bimodal, beim PO-Konto 91–308 s. Budget muss unter dem Takt (15 min / 60 min) liegen und gültige lange Läufe nicht abschneiden. Python-Frist 90 s ist keine harte Grenze.
4. **Losgelöste Goroutinen:** 3000-s-Client-Timeout > 15-min-Takt ⇒ ein Nutzer kann mehrere Ticks „läuft noch" bleiben; `Stop()` wartet nicht auf sie; kein Graceful Shutdown in `main.go`. Braucht eigene Obergrenze und klare Buchführung.
5. **Gesamtbudget je Lauf:** Übersprungene Nutzer müssen gezählt und sichtbar sein (nicht „kein Ergebnis"); rotierende Reihenfolge verhindert, dass stets derselbe Nutzer hinten runterfällt.
6. **Externe Überwachung:** `check-gregor20.sh` erwartet frisches `last_run.time`; Statusform nicht brechen, neue Felder additiv, keine Nutzerkennung (Datenschutz aus Scheibe A).
7. **Bestehende Tests:** `TestClientTimeout_Is3000Seconds` und Timeout⇒partial-Tests bewachen #1912 — Änderungen dort sind bewusst, nicht beiläufig.
8. **Sequenziell bleibt** (Spec :32); echte Parallelität wäre ADR-pflichtig und ist nicht Teil dieser Scheibe.

## Analysis

### Type
Bug (Folgescheibe; Ticket-Label `bug`, priority:high) — fachlich eine Robustheits-Erweiterung des Schedulers.

### Messbasis
Produktions-Journal und `/var/lib/gregor/scheduler_user_state.json` sind für diese Session nicht lesbar (fehlende Gruppenrechte, nicht umgangen). Einzige Messbasis bleibt die 14-Tage-Messung aus Scheibe A (`fix_2149_scheduler_nutzer_sichtbarkeit.md:172-185`): alert-checks bimodal, 89 Deadline-Treffer beim PO-Konto mit 91–308 s; echter Briefing-Versand 319 s (#1912); 3 Nutzer.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | `triggerEndpointForUser` mit `NewRequestWithContext`; Wartebudget je Job-Art; `runForAllUsers` wartet per `select` nur bis zum Budget; neue Fehlerklasse vor `isTimeoutTransportError` geprüft; Job-Rang `partial`; Status-Andockung |
| `internal/scheduler/user_run_state.go` | MODIFY | neues Ergebnis (Budget überschritten / übersprungen weil Aufruf läuft), Zähler, Alarm-Kante, Aggregat-Erweiterung (nur Zahlen) |
| `internal/scheduler/user_call_budget.go` | CREATE | In-Flight-Register (nicht persistiert) mit Token je Auslösung, Verbuchung/Verwerfen des Spätergebnisses |
| `internal/scheduler/*_test.go` | CREATE/MODIFY | Marker/Token/Spätergebnis, Rang-Regression gegen #1346/#1912, Datenschutz des Fehlertexts; bestehende JSON-/Aggregat-Vergleiche in `scheduler_status_privacy_test.go`, `user_partial_and_persistence_test.go` prüfen |
| `docs/adr/0039-…` | CREATE | Aufruferseitige Wartegrenze je Nutzer; Aufgerufener arbeitet weiter; begrenzte faktische Nebenläufigkeit auf Python-Seite |
| `docs/reference/api_contract.md` §12 (:1213-1333) | MODIFY | neue Aggregat-Felder unter `users{}` |
| `frontend/src/routes/account/+page.svelte` (~:900-920) | MODIFY (optional) | neue Zähler neben `failing`/`partial` anzeigen |
| Python (`throttle_store.py`, `trip_alert.py`, `compare_alert.py`) | — | unverändert; Doppellauf wird im Normalbetrieb Go-seitig durch Überspringen verhindert (Restfenster siehe Known Limitations) |

### Scope Assessment
- Files: ~6–9
- Estimated LoC: Go-Code ~260–370, Go-Tests ~250–320, Doku ~100 ⇒ `loc_limit_override` nötig (wie Scheibe A)
- Risk Level: HIGH (kritischer Pfad für Alarme aller Nutzer)

### Technical Approach
**Empfehlung: V2 „Aufhören zu warten" statt Abbrechen.**
- V1 (Abbruch per `context.WithTimeout`) verworfen: Python läuft trotzdem weiter (sync `def`), der nächste Takt löst erneut aus ⇒ doppelter Alarm über die Throttle-Lücke; ein Marker bräuchte eine geratene Lebensdauer.
- V2: Der POST läuft in einer Goroutine weiter; die Nutzerschleife wartet nur bis zum Wartebudget, markiert den Nutzer als „Aufruf läuft" und macht mit dem nächsten weiter. Die weiterlaufende Goroutine ist selbst das Fertig-Signal.
- Nächster Takt: Nutzer mit laufendem Aufruf wird **sichtbar übersprungen** (eigenes Ergebnis, eigener Zähler), kein zweiter POST.
- Spätergebnis: wird mit Token je Auslösung verbucht; veraltetes Token ⇒ verworfen und geloggt. In-Flight-Register wird **nicht** persistiert (sonst Phantom-Marker nach Neustart).
- Klassifikation: Budget-Überschreitung ist eigene Fehlerklasse, geprüft **vor** `isTimeoutTransportError`; auf Nutzerebene zählt sie zur Alarm-Schwelle (nicht unsichtbar wie #1912-partial), auf **Job-Ebene** rankt sie als `partial` (sonst fälschlicher Totalausfall-Alarm #1346 in `tripReports`).
- **Budgets werden vom Takt her gerechnet (nicht je Nutzer hochmultipliziert):** 300 s je Nutzer × 3 Nutzer = 900 s = exakt der `*/15`-Takt ⇒ ohne Laufdeckel würde der nächste Tick wieder für alle im `TryLock`-Überspringen landen. Daher:
  - **Laufbudget** je Job unter dem Takt mit Reserve — Alarm-Jobs 720 s (Takt 900 s); Briefing-Teiljobs so, dass Trip + Compare zusammen deutlich unter 3600 s bleiben.
  - **Wartebudget je Nutzer** = min(Job-Nutzerbudget, verbleibendes Laufbudget) — Alarm 300 s (gemessen 91–308 s), Briefing 600 s (> 319 s Versand).
  - Nutzer, die wegen erschöpften Laufbudgets nicht mehr drankommen, werden **gezählt und sichtbar** verbucht (nicht „kein Ergebnis").
  - **Rotierende Reihenfolge** (Startindex = Laufzähler mod N), damit nicht immer derselbe Nutzer hinten runterfällt — Teil dieser Scheibe, nicht vertagt (Ticket-Erwartung nennt Laufbudget ausdrücklich; Scheibe-A-Kommentar Punkt 1).
- **Goroutinen-Deckel:** eigener Context je weiterlaufendem Aufruf, ~2 Takte (Alarm 1800 s; Briefing bleibt beim Client-Limit 3000 s < 2 Takte). Bei Ablauf: Marker freigeben, Spätergebnis per Token verwerfen. Client-Timeout 3000 s und #1912-Tests bleiben unverändert.
- **Alarm-Schwelle:** Budget-Überschreitung und „übersprungen, weil Aufruf noch läuft" zählen in den **schnellen** Zähler `consecutive_failures` (3 ⇒ `high`) — ein hängender Alarm-Nutzer wird damit nach ~30–45 min gemeldet; der 8er-Teilerfolgs-Zähler (8 × 15 min = 2 h) wäre zu spät. „Wegen Laufbudget nicht erreicht" ist nicht Fehler dieses Nutzers ⇒ zählt als Teilerfolg; Rotation verhindert Dauer-Benachteiligung.
- **Heartbeat:** `briefingDispatch` pingt nur bei beiden Teiljobs `ok` ⇒ ein übersprungener Nutzer ⇒ kein Ping ⇒ BetterStack-Meldung. **Gewollt** (Readiness-Regel) — muss so in der Spec stehen.
- Lock-Reihenfolge `s.mu → userState.mu` bleibt; Spätergebnis-Verbuchung greift nur `userState.mu`.

### Dependencies
- Setzt auf Scheibe A auf (`userRunState`, Aggregat, Alarmbündelung).
- ADR-0039 vor Implementierung (erweitert ADR-0038; berührt `scheduler_multi_user.md:32`, weil ein weiterlaufender Aufruf faktisch höchstens eine zusätzliche Python-Anfrage je hängendem Nutzer bedeutet).
- Externe Überwachung `check-gregor20.sh`: auch ein Lauf, in dem Nutzer übersprungen wurden, braucht `last_run.time` und Rang.

### Known Limitations (für die Spec)
- **Neustart-Restfenster Doppellauf:** Das In-Flight-Register ist bewusst nicht persistiert (sonst Phantom-Marker). Ein Deploy/Neustart von `gregor-api` leert es, während ein sync-`def`-Lauf in Python weiterarbeitet ⇒ der nächste Takt kann erneut auslösen ⇒ doppelter Alarm über die Throttle-Lücke möglich. Fenster: Neustart während eines Aufrufs > Wartebudget. Nicht Python-seitig geschlossen.
- **Deckel-Ablauf:** Nach ~2 Takten wird der Marker freigegeben, obwohl Python theoretisch noch laufen könnte — gleiches Restrisiko, praktisch durch Python-Frist je Trip begrenzt.
- **Shutdown:** Laufende Goroutinen werden beim Beenden verworfen; Ergebnis bleibt unverbucht, Python unberührt.

### Open Questions
Keine fachlichen. Technische Punkte oben als Tech-Lead-Entscheid festgelegt; ADR-0039 in `docs/adr/README.md` eintragen (Index-Drift-Test).
