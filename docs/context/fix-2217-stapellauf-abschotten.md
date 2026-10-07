# Context: fix-2217-stapellauf-abschotten

## Request Summary
Issue #2217 (Epic #2505 Versand-Zuverlässigkeit): Stapelläufe abschotten. (A) Ein Panic in einem Go-Scheduler-Job darf nicht den Prozess und damit alle Jobs abreißen. (B) Eine Ausnahme bei einem Trip im Radar-Alarmlauf darf die Folge-Trips desselben Laufs nicht mitreißen — und der Ausfall muss sichtbar bleiben (kein stilles Verschlucken, #1405).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/scheduler/scheduler.go:211` | `cron.New(cron.WithLocation(loc))` — leere Chain (robfig/cron v3.0.1 setzt trotz Doku-Kommentar `NewChain()`), Panic beendet Prozess |
| `internal/scheduler/scheduler.go:862-911` | `recordRun`: TryLock-Overlap-Sperre (#1447 S2a), schreibt `lastRuns`/`overlapState`. Panic in `fn()` ⇒ Zeilen 884-910 laufen nicht ⇒ `lastRuns` behält altes (oft „ok") Ergebnis, Flankenalarm (662) bleibt aus |
| `internal/scheduler/scheduler.go:483` | `callUserWithBudget` startet `triggerEndpointForUser` in eigener Goroutine — von `cron.Recover` NICHT abgedeckt |
| `internal/scheduler/scheduler.go:919-971` | `triggerResponseBody` liest `status`/`count`/`failed`; `failed>0` = harter Fehler, `status:"partial"` = Teilerfolg; HTTP 500 = harter Fehler |
| `internal/scheduler/job_overlap_test.go:28` | `newOverlapTestScheduler` — Tests rufen `recordRun("id", func() error{...})` direkt; Panic-Closure als Testeinstieg |
| `src/services/trip_alert.py:1904-2780` | `_check_radar_trips`: `trip_local_today` 1913, `_resolve_alert_segment` 1922 (schreibt Trip-Datei via backfill 1745), `check_nowcast_gate`/`anchor_tz` 1988/1997, `tz_for_coords` 2116, Rest ab 2184 ungeschützt |
| `src/services/trip_alert.py:1060-1163` | `check_all_trips`: `trip_local_today` 1069, `_official_trigger_possible` 1104, `_get_cached_weather` 1121 ungeschützt |
| `src/services/trip_alert.py:179-191` | `AlertCheckRunResult` — kein Fehlerzähler |
| `api/routers/scheduler.py:73,118` | Router fängt nichts ⇒ HTTP 500 an Go |
| `src/services/dispatch_orchestrator.py:69-96` | Referenzmuster: try/except je Einheit, `_failed += 1`, Rückgabe `(sent, failed)` |
| `src/services/radar_service.py:446` | `RadarDeadlineExceeded` (Subklasse von Exception) — MUSS vor breitem `except` durchgereicht werden (trip_alert.py:2127) |
| `tests/test_success_status_guard.py:1623-1627,1866-1874,2107` | #1405-Ratsche: B9/B10/B11/B11b/B11c als bekannte Verstöße „ohne Gegenzähler"; `test_known_violations_only_shrink` verlangt Entfernen sobald Zähler existiert |
| `tests/tdd/test_radar_alarmlauf_fairness.py` | `_ScriptedRadar(raise_on=...)` 168-199, `_make_trips`, DI `_get_radar_service` 262, echter FastAPI-Router 458ff, Uhr-Fixture 125 |

Weitere ungeschützte Stapel-Schleifen (Scope-Frage für Analyse): `compare_radar_alert.py:162-174` (nur `RadarDeadlineExceeded` gefangen), `compare_alert.py:186-465` (bewusst ohne try, Kommentar 246-256), `compare_official_alert.py:97`, `trip_report_scheduler.py` `_collect_due_trips` 598-626 / `_get_active_trips` 961ff, `compare_slot_scheduler.py:129-145`, `scheduler_dispatch_service.py:97-111`.

## Existing Patterns
- Python „pro Einheit abfangen + zählen": `dispatch_orchestrator.py:69-96` (bestes Vorbild), `trip_alert.py:1972-1976` und `2080-2104` („Muster fix_1479": `logger.error` mit Trip-ID + `continue`), `trip_report_scheduler.py:477-487`, `inbound_sms_reader.py:250`.
- Go: kein produktives `recover()` außer `internal/provider/openmeteo/calllog.go:42` (verschluckt still — Anti-Muster). Logging durchgehend `log.Printf("[scheduler] ...")`; `cron.PrintfLogger(log.Default())` passt.

## Dependencies
- Upstream: robfig/cron v3.0.1 (`go.mod:13`), Python-Core-Endpunkte für Alarmläufe.
- Downstream: `/api/scheduler/status` (lastRuns, overlapField 1072), Nutzer-Fehlerflanke + MQ, `check-gregor20.sh`-Monitoring, faire Reihenfolge `alert_check_state.py:107-111` (kaputter Trip rückt ans Ende).

## Existing Specs
- `docs/specs/modules/fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md` (Overlap/Teilerfolg)
- `docs/specs/modules/fix_2149_scheduler_budget_teilb.md`, `fix_2149_scheduler_nutzer_sichtbarkeit.md`, `fix_1912_scheduler_briefing_timeout.md`, `scheduler_multi_user.md`
- `docs/specs/modules/fix_1447_s1_alarm_lauf_zeitgrenze.md`, `feat_2261_a2s2_radar_takt.md`, `fix_1479_ruhezeit_wurzel.md`
- `docs/specs/modules/waechter_1405_erfolg_wirkung.md` (Klasse 2), `waechter_1405_stille_aufloesung.md`, `fix_2231_slot_reparatur.md`
- ADRs: 0018 (kein Kaschieren), 0044, 0051, 0082. Keine ADR zu Panic/Recover.

## Risks & Considerations
- **`SkipIfStillRunning` NICHT verwenden:** greift vor `recordRun`, umgeht die #1447-S2a-Skip-Zählung (Skip nur als verworfenes `logger.Info`), sperrt bei `briefing_dispatch` zwei jobIDs gemeinsam ⇒ doppelt/kollidiert mit bestehender Sperre.
- **Recover-Ort ist der Designkern:** nur `cron.Recover` hält den Prozess am Leben, lässt den Panic aber im Status unsichtbar (alter „ok"-Stand). Sichtbar als `Status:"error"` wird er nur bei `recover` in `recordRun` (Panic → error-Ergebnis → Flanke). `cron.Recover` zusätzlich als Netz ist billig.
- Goroutine in `callUserWithBudget` (483) braucht eigenen Schutz.
- Python: reines `except: continue` versteckt Fehler als „ok" (Go liest nur `failed`/`partial`). Fehlerzähler ins Ergebnis + `failed`/`partial` an Go, sonst Verstoß gegen #1405 und ADR-0018.
- `RadarDeadlineExceeded` vor breitem `except` behandeln (Deadline-Semantik/Fairness-Tests).
- #1405-Ratsche: sobald Zähler existiert, müssen B9–B11c aus der Liste bekannter Verstöße fallen (Ratsche zieht nur in eine Richtung).
- Scope-Grenze zu #2218 (Observability) und #1405 (Wächter 2) ziehen; weitere ungeschützte Schleifen (Compare-Läufe, Report-Scheduler) bewusst ein- oder ausschließen.
- `_resolve_alert_segment` schreibt Trip-Datei (backfill) — Ausnahme mittendrin darf keinen halbgeschriebenen Zustand hinterlassen (prüfen).

## Analysis

### Type
Bug (nutzersichtbar: ein Panic beendet alle Scheduler-Jobs; eine Ausnahme bei einem Trip/Preset kostet alle Folge-Einheiten desselben Laufs → Alarme fallen aus)

### Verifizierte Fakten (nicht erneut untersuchen)
- **Go `recordRun`** (`scheduler.go:862-911`): `defer lock.Unlock()` vor `fn()` (880/882), kein `recover` ⇒ Panic beendet den Prozess; überlebte er, bliebe `lastRuns` auf altem Stand. `recover` direkt um `fn()` (Helfer, z. B. `safeCall`) kollidiert NICHT mit der Overlap-Logik — die Zeilen 884-910 laufen danach normal, `lastRuns` bekommt `Status:"error"`.
- **Einzige Job-Goroutine** in `internal/scheduler/`: `callUserWithBudget` `scheduler.go:483-489`. Panic dort ⇒ Prozessabsturz; `cron.Recover` deckt sie NICHT ab. Fix: `defer recover()` IN der Goroutine + Fehler an `resultCh` senden, sonst wartet der Aufrufer bis zum Wartebudget und der `callBudget`-Marker hängt.
- **`cron.New(cron.WithLocation(loc))`** `scheduler.go:211`: leere Chain. `cron.WithChain(cron.Recover(cron.PrintfLogger(log.Default())))` als zusätzliches Netz (fängt Wrapper-Code außerhalb `recordRun`, z. B. Flankenlogik in `tripReports` 640ff).
- **Sichtbarkeit von `error` bei Alarm-Jobs ist gegeben** (kein neuer Mechanismus nötig): `runForAllUsers` verbucht je (jobID, userID) über `s.userState.Record` (Nutzer-Fehlerflanke #2149 A, `scheduler.go:323-335`); `check-gregor20.sh:187-205` alarmiert bei `status=="error"` ab 2 Läufen in Folge. Die ok→error-MQ-Flanke via `lastHardStatus` gibt es nur für `trip_reports_hourly` (640-675).
- **Go-Auswertung** `triggerResponseBody` 919-978: `failed>0` ⇒ harter Fehler; `status:"partial"` ohne failed ⇒ `partialRunError`; HTTP≥400 ⇒ error. `failed` schlägt `partial`.
- **`_resolve_alert_segment` → backfill → `update_trip`** (`src/app/loader.py:2012-2034`): gesperrt + atomar, Ausnahme in `mutate` bricht ohne Schreiben ab ⇒ **kein Halbzustand** (Haiku-Behauptung „nicht atomar" war falsch).
- **Python heute:** Ausnahme ⇒ Router (`api/routers/scheduler.py:73/118`) ⇒ HTTP 500 ⇒ Go `error`. Rot wird es also schon heute; **der Gewinn ist allein, dass Folge-Trips/-Presets weiter geprüft werden** und `failed` gezählt wird. Ein dauerhaft kaputter Trip erzeugt daher keinen neuen Alarmlärm.
- **Compare-Läufe:** `compare_alert.py:245-256` („bewusst ohne try") betrifft NUR die Ruhezeit-Prüfung (#1479, Schutz liegt im geteilten Baustein, ADR-0021) — **keine** Entscheidung gegen Schutz je Preset. `compare_radar_alert.py:162-174` fängt nur `RadarDeadlineExceeded`; `compare_official_alert.py:97` `sum(1 for … _check_one_preset)` ungeschützt. Alle drei haben bereits `_check_one_preset` ⇒ Schutz je Einheit ist dort klein.
- **#1405-Ratsche** `tests/test_success_status_guard.py:1866-1874`: B9 `check_all_trips`, B10 `_check_radar_trips`, B11 `compare_alert`, B11b `compare_radar_alert`, B11c `compare_official_alert` — Einträge fallen, sobald Gegenzähler existiert (`test_known_violations_only_shrink` 2107ff).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | `recover` um `fn()` in `recordRun` (Panic → error-Ergebnis, Stack nur ins Log, in `Error` nur `"panic in <jobID>"` — Status-Endpoint ist halb-öffentlich); `recover` + `resultCh` in Goroutine `callUserWithBudget`; `cron.Recover`-Chain |
| `internal/scheduler/scheduler_panic_test.go` | CREATE | Panic-Closure über `recordRun` (`newOverlapTestScheduler`, `job_overlap_test.go:28`); Panic in Nutzer-Goroutine (Client `s.client`, `scheduler.go:937` — Injizierbarkeit eines panickenden `RoundTripper` in /40 prüfen) |
| `src/services/trip_alert.py` | MODIFY | Schutz je Trip in `_check_radar_trips` (1904-2780) und `check_all_trips` (1060-1163): `except RadarDeadlineExceeded: raise` vor `except Exception` (`logger.error(exc_info=True)`, `failed += 1`, weiter); Stempel `reached[trip.id]` VOR dem try; `AlertCheckRunResult.failed: int = 0` (179-191) |
| `src/services/compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py` | MODIFY | dasselbe Muster je Preset um `_check_one_preset`, `failed` zählen |
| `api/routers/scheduler.py` | MODIFY | `failed` in die Antworten der 5 Alarm-Endpunkte; `status` bleibt `ok`/`partial` (Deadline) |
| `tests/test_success_status_guard.py` | MODIFY | B9, B10, B11, B11b, B11c aus den bekannten Verstößen entfernen |
| `tests/tdd/test_radar_alarmlauf_fairness.py` bzw. neue Verhaltens-Testdatei | MODIFY/CREATE | echter FastAPI-Router, ein Trip mit kaputten Daten (kein Mock), Folge-Trip bekommt Alarm |

### Scope Assessment
- Files: ~9 (5 Python-Produktiv, 1 Go-Produktiv, 3+ Tests)
- **LoC: deutlich über 250, voraussichtlich auch über 500.** `workflow.py` zählt `git diff --numstat` OHNE Whitespace-Ignorieren; die Schleife in `_check_radar_trips` ist ~860 Zeilen lang — jede Kapselung (try-Wrapper oder Extraktion `_check_one_radar_trip`) rückt den Rumpf ein ⇒ mehrere hundert „hinzugefügte" Zeilen. Override (`workflow.py set-field loc_limit_override <N>`) hat keine harte Obergrenze; in /30 mit realer Zahl festlegen. LoC ist damit KEIN Argument für eine Aufteilung.
- Risk Level: MEDIUM — zentraler Scheduler-Pfad und Alarmlauf, aber rein additiver Schutz.

### Technical Approach (Empfehlung)
EIN Workflow, ganzes Thema „Stapelläufe abschotten":
1. **Go:** recover im Helfer um `fn()` in `recordRun` → `error`-Ergebnis + Stack-Log; recover in der Nutzer-Goroutine → sofortiger Fehler über `resultCh`; `cron.Recover` als Netz. `SkipIfStillRunning`: NEIN (umgeht #1447-S2a-Skip-Zählung, kollidiert mit `briefing_dispatch`-Sperre).
2. **Python, Trip UND Ortsvergleich (Paritätsgebot CLAUDE.md, gleiches nutzersichtbares Fehlverhalten):** Schutz je Einheit nach Vorbild `dispatch_orchestrator.py:69-96`; Muster einmal als kleiner geteilter Baustein denken (Trip/Compare-Teilung), `RadarDeadlineExceeded` vorher durchreichen, `_abort_radar_unit` nicht doppelt.
3. **Semantik: gescheiterte Einheit ⇒ `failed>0` ⇒ harter Fehler** (nicht `partial`): ADR-0018 (kein Kaschieren); `partial` ist in Go (#1447/#1912) für „kein Ausfallbeweis" (Deadline/Timeout/Budget) reserviert; `failed>0` ⇒ error ist schon Praxis bei trip-reports (#1012).

### Vorgeschlagene ACs (für /30)
- Trip nach einem kaputten Trip bekommt im selben Lauf seinen Alarm; Antwort enthält `failed==1`; Job-Status `error`.
- Dasselbe für Ortsvergleich-Presets (alle drei Compare-Alarmläufe).
- Deadline liefert weiterhin `partial`, nicht `failed`.
- Kaputter Trip rückt in der Fairness-Reihenfolge ans Ende (`alert_check_state.py:107-111`).
- Panic in einem Go-Job: Prozess läuft weiter, Status `error` (vorher „ok"), nächster Lauf startet (Sperre frei).
- Panic in der Nutzer-Goroutine kehrt sofort mit Fehler zurück, nicht erst nach Ablauf des Wartebudgets.
- #1405-Ratsche: B9–B11c entfernt, Wächter grün.

### Risiken
- Stempel vor dem try, sonst bleibt ein früh werfender Trip an der Spitze.
- Bestehende Deadline-/Fairness-Tests mit `_ScriptedRadar(raise_on=...)` können anders reagieren.
- `checked` zählt gescheiterte Einheiten mit — gewollt, im Test festschreiben.
- Breites except darf Programmierfehler nicht verstummen lassen ⇒ `exc_info=True` + Zähler + `error`-Status.

### Dependencies
robfig/cron v3.0.1; Status-Endpoint/Monitoring (`check-gregor20.sh`) unverändert nutzbar; Abgrenzung zu #2218 (Observability) und #1405 (Wächter 2).

### Open Questions
- [ ] Kapselungsform der 860-Zeilen-Schleife (try-Wrapper vs. Extraktion) und konkreter `loc_limit_override` — technische Entscheidung in /30, keine PO-Frage.
