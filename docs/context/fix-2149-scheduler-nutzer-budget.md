# Context: fix-2149-scheduler-nutzer-budget

## Request Summary
Issue #2149 (Teil von Epic #2138 Multi-User-Readiness, priority:high): Der Go-Scheduler arbeitet die Nutzer
strikt nacheinander ab, ohne Zeitbudget je Nutzer; ein hängender Nutzer blockiert alle anderen, und ein
dauerhaft scheiternder Einzel-Account bleibt unsichtbar, solange andere Nutzer erfolgreich sind.
Gewünscht: Budget je Nutzeraufruf + Gesamtbudget je Lauf, pro Nutzer `last_run`/`last_error`/
`consecutive_failures` im Status, Alarm bei N Fehlern in Folge je Nutzer.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/scheduler/scheduler.go:161` | Geteilter `http.Client{Timeout: 3000s}` (#1912) — einziges Zeitlimit, auch für globale Jobs (`triggerGlobalEndpoint:673`, `triggerPremiumSmsPollEndpoint:476`) |
| `internal/scheduler/scheduler.go:237-288` | `runForAllUsers` — sequenzielle Nutzerschleife, Rangfolge error > partial > ok (#1447 S2a) |
| `internal/scheduler/scheduler.go:617-665` | `triggerEndpointForUser` — `client.Post(url?user_id=…)`, kein Context; Timeout → `partialRunError`, HTTP ≥400 / `failed>0` → hart, `status=="partial"` → partial |
| `internal/scheduler/scheduler.go:59-79` | `partialRunError`, `isTimeoutTransportError` (erkennt auch `context.DeadlineExceeded`) |
| `internal/scheduler/scheduler.go:297-367` | `briefingDispatch` (Heartbeat nur bei beidseitig ok), `tripReports` (einzige Alarm-Flanke via `lastHardStatus`) |
| `internal/scheduler/scheduler.go:369-403` | alert/radar/compare-Jobs — kein Alarm |
| `internal/scheduler/scheduler.go:553-602` | `recordRun` — TryLock je jobID, `overlapState`, `lastRuns` (nur im Speicher) |
| `internal/scheduler/scheduler.go:765-836` | `Status()` — JSON `jobs[]{id,name,next_run,last_run{time,status,error},overlap?}` + Health-Blöcke |
| `internal/handler/scheduler_status.go:11`, `internal/router/router.go:241` | Status-Handler/Route |
| `internal/middleware/auth.go:50` | `/api/scheduler/status` ist **ohne Anmeldung** erreichbar |
| `api/routers/scheduler.py` | Python-Endpunkte, alle synchron, immer HTTP 200; nur alert-checks hat eigene Frist (90 s) |
| `src/services/trip_alert.py:60-65` | `ALERT_RUN_DEADLINE_SECONDS=90`, Kommentar rechnet noch mit 120 s Aufrufer-Wartezeit |
| `src/services/briefing_slots.py:48` | längster gemessener Einzelversand 319 s, `CLAIM_TTL=900` |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh:119-200, 752-790` | Consumer des Status-JSON; zählt Fehlerserien selbst; 5 Alarm-Jobs müssen `last_run.time` < 20 min haben |
| `frontend/src/routes/account/+page.server.ts:24`, `+page.svelte:898-918`, `frontend/src/lib/types.ts:576` | Frontend-Consumer des Status |
| `docs/reference/api_contract.md:1213` | Doku Status-Endpoint (veraltet) |

## Existing Patterns
- **Timeout = Teilerfolg, kein Ausfall** (#1912): Transport-Timeout → `partialRunError` → Status `partial`, kein Alarm, kein Heartbeat.
- **Overlap-Sperre** (#1447 S2a): `TryLock` je jobID, Skip-Zähler `overlapState` (Zähler + Zeitstempel, bei echtem Lauf auf 0) — Vorlage für einen Zähler „Fehler in Folge".
- **Alarm-Flanke** in `tripReports`: nur bei Statuswechsel, Recovery-Notiz bei error→ok; `notifier` injizierbar.
- **Health-Module** (`briefing_health.go` u. a.): liefern Rohwerte, Schwellen/Alarm in `check-gregor20.sh`.
- **Tests:** `httptest.NewServer` mit Unterscheidung nach `user_id`, Store über `t.TempDir()` (`createTestUsers`, `testStoreWithUsers`), `sched.client`/`sched.notifier` direkt gesetzt, Signal-Kanäle statt Sleep (`job_overlap_test.go:28`).

## Dependencies
- Upstream: `store.ListUserIDs`, `model.IsTestUserID`, Python-Core-Endpunkte, `notify.SendMQ`, `robfig/cron`.
- Downstream: `/api/scheduler/status` → `check-gregor20.sh` (Infra-Monitoring), Account-Seite im Frontend; Heartbeat `briefingDispatch`.

## Existing Specs
- `docs/specs/modules/fix_1912_scheduler_briefing_timeout.md` — 3000 s, Timeout ≠ Ausfall; Known Limitation: Konstante an 4 Stellen verstreut.
- `docs/specs/modules/fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md` — TryLock, Rangfolge; Known Limitation: nur erster betroffener Nutzer im Status.
- `docs/specs/modules/scheduler_multi_user.md` — Z. 32: parallele Nutzeriteration bewusst nicht umgesetzt (Python-Last); Z. 212: sequenzielle Verzögerung bei < 20 Nutzern akzeptabel.
- `docs/adr/` ADR-0038 — harte Frist im Job, spürbar unter der Aufrufer-Wartezeit; Anheben der Aufrufer-Wartezeit ausdrücklich verworfen (durch #1912 faktisch aufgeweicht).
- Issue #1539 (offen) — Parallelisierung **innerhalb** Python (Orte/Etappen), andere Ebene.

## Risks & Considerations
- **Zielkonflikt #1912 ↔ #2149:** ein knappes Budget je Nutzer (z. B. 120 s) schneidet gültige Versände (319 s) ab; ein großzügiges Budget (3000 s) lässt einen hängenden Nutzer alle blockieren. Ein Budget je **Job-Art** (Stundentakt vs. 15-Min-Takt) ist wahrscheinlich nötig.
- **Abbruch auf Go-Seite stoppt Python nicht:** Python arbeitet synchron im Threadpool weiter; ein Go-Abbruch plus Folge-Tick kann parallele Python-Last erzeugen (Doppelversand-Schutz über `briefing_slots` Claim prüfen).
- **Parallelisierung** widerspricht `scheduler_multi_user.md` — nur mit begründeter Neuentscheidung (ggf. ADR) und begrenzter Parallelität.
- **Datenschutz:** Status-Endpoint ist öffentlich; User-IDs können frei gewählte Benutzernamen sein; Fehlertexte enthalten heute schon `?user_id=`. Pro-Nutzer-Status öffentlich auszugeben wäre ein Leck (Epic #2138/#2268).
- **Consumer-Kompatibilität:** `check-gregor20.sh` und Frontend erwarten die bestehende `jobs[]`-Form; Tests zählen exakt 10 Job-Zeilen und „genau 1 Alarm".
- **Alarm-Lärm:** MQ-Alarm geht per Telegram an den PO — Per-User-Alarm braucht Flanke/Entprellung, sonst Dauerfeuer.
- **Status nur im Speicher:** `consecutive_failures` beginnt nach jedem Neustart/Deploy bei 0.
- **Bricht sicher:** `TestClientTimeout_Is3000Seconds` (`timeout_kein_ausfall_test.go:278`).
- **Prod-Umfang:** aktuell 3 Nutzer mit `user.json` — der Blockadefall ist heute selten, wächst aber mit Epic #2138.

## Analysis

### Type
Bug (Beobachtbarkeitslücke + fehlende Zeitgrenze je Nutzer)

### Messbefunde Produktion (14 Tage bis 2026-09-15)
- alert-checks je Nutzer bimodal: meist ~0 s (nichts zu tun); **89 Deadline-Treffer** beim PO-Konto, 91–308 s (Median 132 s).
- Python-Frist `ALERT_RUN_DEADLINE_SECONDS=90` wird nur **vor jedem Trip** geprüft (`trip_alert.py:866-869`) → keine harte Grenze; Trips nach dem `break` werden in diesem Tick **gar nicht geprüft**, Go verbucht das als `partial` (`api/routers/scheduler.py:75`).
- Längster Trip-Briefing-Einzelversand 319 s (#1912). 0 Overlap-Skips in 14 Tagen.
- Python: ein Uvicorn-Prozess, sync `def` im Threadpool (40); Go-Abbruch stoppt Python nicht.
- Doppelversand-Schutz: Briefings per `briefing_slots`-Claim (900 s); Alert-/Compare-Alert-Pfad nur `ThrottleStore` mit Check-then-record-Lücke (`throttle_store.py:101-133`) → ein Go-Abbruch plus Re-Trigger kann doppelte Alarme erzeugen.

### Kernbefunde für das Design
1. **Klassifikationsfalle:** `isTimeoutTransportError` (`scheduler.go:73-79`) wertet `context.DeadlineExceeded` als partial → ein naives `context.WithTimeout` je Nutzer macht den hängenden Nutzer wieder unsichtbar. Budget-Abbruch braucht eigene Klassifikation.
2. **Zwei Bedeutungen von partial:** #1912-partial = „Python hat vermutlich fertig gearbeitet"; Deadline-partial = „Trips wurden nicht geprüft". Chronisches Deadline-partial ist die einzige real messbare Einzelnutzer-Degradation.
3. **PII:** `/api/scheduler/status` öffentlich; `jobResult.Error` enthält heute `?user_id=` (`scheduler.go:626/647/657`) und erscheint zudem auf der Account-Seite **jedes** Nutzers (Cross-User-Sichtbarkeit).
4. **Reset nach Deploy:** In-Memory-Zähler verdeckt beim Stundenjob bis zu 3 h Fehlerserie → Persistenz nötig.

### Schnitt (Tech-Lead-Entscheidung)
- **Scheibe A (dieser Workflow): Sichtbarkeit + Alarm je Nutzer.** Pro (Job, Nutzer): `last_run`, `last_status`, `last_error`, `consecutive_failures`, `consecutive_partial`; persistiert atomar im Datenverzeichnis; Flanken-Alarm per MQ bei N harten Fehlern in Folge bzw. höherer Schwelle für Teilerfolge in Folge, Recovery-Notiz; öffentlicher Status nur anonymes Aggregat; `?user_id=` aus dem öffentlichen Fehlertext entfernt. Kein Zeit-/Nebenläufigkeitsrisiko, kein ADR (Fortführung ADR-0038).
- **Scheibe B (Folge-Workflow, selbes Issue): Zeitbudget je Nutzer + Gesamtbudget je Lauf.** Budget-Abbruch eigene Klassifikation (hart), sichtbare „wegen Budget übersprungen"-Zählung, Rotation der Reihenfolge, In-Flight-Marker gegen Doppellauf (die Race entsteht erst durch den Go-Abbruch). Sequenziell bleibt; Parallelität erst bei Wachstum (~8–10 Nutzer) mit eigenem ADR.
- Issue #2149 wird erst nach Scheibe B geschlossen.

### Affected Files (Scheibe A)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | Nutzerergebnis je Aufruf erfassen, Fehlertext redigieren, Aggregat in `Status()` |
| `internal/scheduler/user_run_state.go` | CREATE | Zustand je (Job, Nutzer), Zähler, Schwellen, Alarm-Flanke, Persistenz |
| `internal/scheduler/user_run_state_test.go` | CREATE | Zähler/Alarm/Persistenz/zwei Nutzer |
| `internal/scheduler/*_test.go` | MODIFY | ggf. Anpassung von Tests, die den Fehlertext mit `user_id` erwarten |
| `docs/reference/api_contract.md` | MODIFY | Status-Endpoint aktualisieren |
| `docs/specs/modules/scheduler_multi_user.md` | MODIFY | Verweis auf neue Spec |

### Scope Assessment
- Files: ~5 (Code 2 + Tests 1–3)
- Estimated LoC: +300–400 (inkl. Tests) → `loc_limit_override 500`
- Risk Level: MEDIUM (kritischer Pfad, aber rein additiv beobachtend)

### Technical Approach
Nach jedem `triggerEndpointForUser` das Ergebnis (ok/partial/error) in einen Zustandsspeicher je (jobID, userID) buchen. Harte Fehler erhöhen `consecutive_failures`, Teilerfolge `consecutive_partial`, ok setzt beide zurück. Schwellenüberschreitung → genau eine MQ-Nachricht (Flanke), Erholung → eine Recovery-Nachricht. Zustand wird nach jedem Lauf atomar geschrieben (tmp + rename) und beim Start geladen; defekte/fehlende Datei → leerer Zustand, kein Absturz. Öffentliches JSON: je Job nur Zähler (`users_failing`, `users_partial`), keine IDs. Nutzer, die nicht mehr existieren oder Testkonten sind, werden nicht geführt.

### Open Questions
- keine an den PO; Schwellenwerte (3 harte Fehler, 8 Teilerfolge in Folge) als Tech-Lead-Entscheidung in der Spec begründet.
