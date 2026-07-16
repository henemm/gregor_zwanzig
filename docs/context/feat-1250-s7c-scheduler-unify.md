# Context: feat-1250-s7c-scheduler-unify

## Request Summary

Epic #1250 (Trip+Vergleich auf gemeinsame `BriefingSubscription`), letzte Scheibe **S7c**:
die zwei stündlichen Cron-Einstiege `trip_reports_hourly` und `compare_presets_daily`
im Go-Scheduler zu **einem** vereinheitlichten Einstieg zusammenlegen — verhaltensneutral,
mit strikt erhaltener `last_run`-Beobachtbarkeit pro Ursprungs-Job (AC-24) und korrektem
Dispatch je `kind` (AC-23). PO-Entscheidung 2026-07-16: bauen (nicht descopen).

## Ist-Architektur (Kern-Erkenntnis)

Der **Go-Scheduler liest KEINEN Store**. Er ist ein reiner Cron-Wecker, der HTTP-POSTs an
den Python-Kern feuert. Der eigentliche `kind`-Dispatch passiert bereits in Python:

| Go-Job (Cron) | Ausdruck | POST-Ziel (Python) | Python liest |
|---|---|---|---|
| `trip_reports_hourly` | `0 * * * *` | `/api/scheduler/trip-reports` (pro User) | `briefings/` kind=route (S7a) |
| `compare_presets_daily` | `0 * * * *` | `/api/scheduler/compare-presets-daily` (pro User) | `briefings/` kind=vergleich (S7b) |

→ **AC-23-Substanz (korrekter Dispatch je kind, keine Vermischung) ist bereits LIVE** —
route-Briefings laufen in den Trip-Render-Pfad, vergleich-Briefings in den Compare-Pfad,
weil jeder der zwei Endpunkte selbst nach `kind` filtert.
→ **AC-24-Substanz (getrennte last_run pro Job) ist bereits LIVE** — beide Jobs haben eigene
`lastRuns[]`-Einträge und eigene Zeilen in `/api/scheduler/status`.

Übrig bleibt nur der **kosmetische Zusammenschluss** der beiden Cron-Registrierungen zu einer.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `internal/scheduler/scheduler.go:90-106` | Job-Registrierung (`jobs`-Slice); Zeilen 91 (`trip_reports_hourly`) + 100 (`compare_presets_daily`) sind die zwei zu mergenden Einstiege |
| `internal/scheduler/scheduler.go:153-157` | `tripReports()` — `recordRun("trip_reports_hourly", runForAllUsers(...trip-reports))` |
| `internal/scheduler/scheduler.go:262-273` | `comparePresetsDaily()` — `recordRun(...)` **plus** Heartbeat-Ping nur bei Status ok (`heartbeatComparePresets`) |
| `internal/scheduler/scheduler.go:275-293` | `recordRun()` — schreibt `lastRuns[jobID]` (ok/error + time) |
| `internal/scheduler/scheduler.go:406-441` | `Status()` — **Eintrags-getrieben**: iteriert `s.cron.Entries()`, pro Cron-Eintrag genau eine `entryMap[e.ID] → jobMeta.id → lastRuns[id]`-Zeile |
| `internal/scheduler/scheduler.go:118` | Start-Log „9 jobs" |
| `internal/handler/scheduler_status.go:11-14` | `SchedulerStatusHandler` → gibt `sched.Status()` als JSON aus (`/api/scheduler/status`, router.go:192) |
| `internal/scheduler/scheduler_test.go:199-200` | Test fordert **exakt `len(jobs) == 9`** — bricht bei naivem Merge (→ 8 Einträge) |
| `internal/scheduler/multi_user_test.go:80-160` | `TestTripReports_*` — treiben `sched.tripReports()` direkt; bleiben grün, solange die interne `recordRun("trip_reports_hourly", runForAllUsers(...))`-Logik erhalten bleibt |
| `internal/scheduler/data_write_selftest_test.go:64-72` | Muster für „Status() nach Job-Lauf → last_run vorhanden" (Vorlage für AC-24-Test) |
| `src/services/scheduler_dispatch_service.py:34-56` | Python-Compare-Daily liest `briefings/` (kind=vergleich); **kein Änderungsbedarf** |

## Kern-Design-Zwang (aus Status())

`Status()` baut die Job-Liste aus **Cron-Einträgen**, nicht aus `lastRuns`-Keys. Deshalb:

- **Naiver Merge** (zwei Einträge → einer, eine `jobMeta`) ⇒ `Status()` zeigt nur noch **eine**
  Zeile für den kombinierten Job ⇒ **AC-24 gebrochen** + `len(jobs)==9`-Test rot.
- **Erforderliches Design (Path A):** EIN Cron-Eintrag `0 * * * *` mit einer Dispatch-Funktion,
  die intern **beide** `recordRun`-Aufrufe macht (`trip_reports_hourly` + `compare_presets_daily`,
  Heartbeat-Erhalt), UND `Status()` so anpassen, dass der vereinheitlichte Eintrag weiterhin
  **beide** logischen Job-Zeilen (mit je eigenem `last_run`) ausgibt — `next_run` geteilt (ehrlich:
  sie laufen jetzt zum selben Tick). So bleibt der Status-Consumer verhaltensneutral (9 Zeilen,
  gleiche ids, gleiche last_run-Semantik) und die Cron-Registrierung ist „ein Einstieg".

## Existing Patterns

- **recordRun-Kapsel:** jeder Job ist `s.recordRun(id, func() error {...})` → einheitliche
  ok/error-Buchführung in `lastRuns`. Der Merge behält beide Kapseln, ruft sie nur aus einer
  Cron-Funktion auf.
- **Heartbeat nur bei Erfolg:** `comparePresetsDaily` pingt BetterStack **nur** wenn
  `lastRuns["compare_presets_daily"].Status == "ok"` (CLAUDE.md: Readiness statt Liveness) —
  muss im Merge exakt erhalten bleiben.
- **entryMap als Job-Identität:** `cron.EntryID → jobMeta{id,name}`. Für Path A braucht der
  vereinheitlichte Eintrag eine Repräsentation seiner zwei Sub-Jobs (z. B. `jobMeta` mit
  einer `subIDs []string`-Liste, oder eine feste Merge→Sub-Job-Abbildung in `Status()`).

## Dependencies

- **Upstream (was der Code nutzt):** `robfig/cron` (Job-Registrierung/Goroutine-pro-Eintrag),
  `runForAllUsers`/`triggerEndpointForUser` (HTTP-POST-Fan-out), Python-Trigger-Endpunkte.
- **Downstream (was davon abhängt):** `/api/scheduler/status` (Frontend/Monitoring/`check-gregor20.sh`),
  BetterStack-Heartbeat `compare_presets_daily`, `scheduler_test.go`-Job-Count.

## Existing Specs

- `docs/specs/modules/issue_1250_briefing_subscription.md` — Programm-Spec; AC-23/AC-24 (Zeilen 545-562),
  S7c-Scheibenbeschreibung (Zeile 211-213), KL-7/ADR-0023-Kontext.
- ADR-0023 (Persistenz-Cutover-Entscheidungen) — S7c ist die entkoppelte Aufräum-Scheibe.

## Risks & Considerations

- **R1 — AC-24-Beobachtbarkeitsverlust (HAUPTRISIKO):** `Status()` ist Eintrags-getrieben; ohne
  gezielte Expansion des Merge-Eintrags verschwindet eine `last_run`-Zeile. Muss durch Test
  abgesichert werden (Status zeigt nach Lauf BEIDE Jobs mit aktualisiertem last_run).
- **R2 — Nebenläufigkeit → Sequenz:** heute laufen die zwei Einträge in getrennten cron-Goroutinen
  (nebenläufig). Ein einziger Eintrag ruft die zwei Fan-outs **sequenziell** in einer Goroutine
  (trip zuerst, dann compare). Gleiche Seiteneffekte/Daten, aber längere Tick-Dauer. Verhaltensneutral
  im Ergebnis; muss offengelegt werden. Alternative: interne Parallel-Goroutinen (mehr Komplexität) —
  Design-Entscheidung für die Spec.
- **R3 — Heartbeat-Regression:** compare-Heartbeat darf weiterhin NUR bei compare-Erfolg feuern,
  unabhängig vom trip-Ergebnis. Kein gemeinsamer „ganzer Tick ok"-Ping.
- **R4 — `len(jobs)==9`-Test:** muss angepasst werden (bleibt 9 Zeilen via Sub-Job-Expansion, ODER
  Test spiegelt die neue Einstiegs-Zahl). Bevorzugt: 9 Zeilen erhalten (verhaltensneutral für Consumer).
- **R5 — Live-Scheduler, hohes Blast-Radius:** dies ist der Pfad, der real Briefings/Alarme auslöst.
  Adversary + Staging-E2E (Scheduler `last_run` beider Jobs frisch nach echtem Tick) zwingend.
- **R6 — Kein Python/Renderer/Migrations-Eingriff nötig:** Änderung ist Go-lokal
  (`internal/scheduler/scheduler.go` + Tests). `kind`-Dispatch bleibt an der Python-Naht.

## Analysis

### Type
Feature (Refactor/Cleanup, verhaltensneutral) — Sub-Scheibe von Epic #1250.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | (1) `jobs`-Slice: die zwei `0 * * * *`-Einträge `trip_reports_hourly` + `compare_presets_daily` durch **einen** vereinheitlichten Eintrag ersetzen. (2) Neue Dispatch-Funktion `briefingDispatch()`, die intern beide bestehenden `recordRun`-Kapseln (`tripReports`-Logik + `comparePresetsDaily`-Logik inkl. Heartbeat) aufruft. (3) `Status()` + `jobMeta`/`entryMap` so erweitern, dass der vereinheitlichte Eintrag weiterhin **beide** logischen Job-Zeilen (`trip_reports_hourly`, `compare_presets_daily`) mit je eigenem `last_run` ausgibt. (4) Start-Log „9 jobs" konsistent halten. |
| `internal/scheduler/scheduler_test.go` | MODIFY | `len(jobs)==9`-Erwartung an die Sub-Job-Expansion anpassen (bleibt 9 Status-Zeilen); ggf. neuer Assert, dass der eine Cron-Eintrag zwei Status-Zeilen erzeugt. |
| `internal/scheduler/scheduler_unify_test.go` | CREATE | AC-23-Test (ein Dispatch-Lauf triggert beide Endpunkte, route→trip / vergleich→compare, kein Cross-Talk) + AC-24-Test (`Status()` nach Lauf zeigt beide Jobs mit frischem `last_run`) + Heartbeat-Erhalt-Test (compare-Heartbeat nur bei compare-ok). |

**Kein** Python-, Renderer-, Mail- oder Migrations-Eingriff. `kind`-Dispatch bleibt an der Python-Naht.

### Scope Assessment
- Files: 2 MODIFY + 1 CREATE (alle unter `internal/scheduler/`)
- Estimated LoC: ~+90 / −30 (deutlich unter 250er-Limit)
- Risk Level: **MEDIUM–HIGH** — kleiner, isolierter Diff, aber am **Live-Scheduler** (kritischer Versand-Pfad); Hauptrisiko ist stille AC-24-Observability-Regression.

### Technical Approach (Empfehlung — Path A)
**Ein Cron-Eintrag `briefing_dispatch` (`0 * * * *`), der sequenziell beide Fan-outs ausführt und beide `last_run`-Records + den compare-Heartbeat erhält; `Status()` expandiert diesen Eintrag zurück in seine zwei logischen Sub-Jobs.**

Design-Entscheidungen (selbst getroffen, offengelegt — keine PO-Frage):
- **Sequenziell statt nebenläufig (R2):** Der vereinheitlichte Eintrag ruft trip-Fan-out, dann compare-Fan-out. Heute laufen sie in getrennten cron-Goroutinen nebenläufig; sequenziell verlängert nur die Tick-Wallzeit (stündlicher Job → irrelevant), Seiteneffekte/Daten/Status identisch. Einfacher + ehrlicher als interne Parallel-Goroutinen. **Verhaltensneutral im Ergebnis.**
- **Status()-Expansion (R1/R4):** `jobMeta` bekommt eine Sub-Job-Liste (oder `Status()` bildet den Merge-Eintrag auf seine zwei `lastRuns`-Keys ab). Ergebnis: weiterhin 9 Job-Zeilen, gleiche ids/names/last_run-Semantik → Status-Consumer (`/api/scheduler/status`, Monitoring) sieht keinen Unterschied. `next_run` beider Zeilen = das (identische) `next_run` des Merge-Eintrags.
- **Heartbeat (R3):** compare-Heartbeat feuert weiterhin ausschließlich bei `lastRuns["compare_presets_daily"].Status=="ok"`, unabhängig vom trip-Ausgang. Kein kombinierter „Tick-ok"-Ping.

### Dependencies
- Upstream: `robfig/cron`, `runForAllUsers`/`triggerEndpointForUser`, Python-Trigger-Endpunkte (unverändert).
- Downstream: `/api/scheduler/status`-Consumer, BetterStack-Heartbeat `compare_presets_daily`, `scheduler_test.go`-Job-Count.

### Open Questions
- [x] Sequenz vs. Parallel → **selbst entschieden: sequenziell** (siehe oben), keine PO-Frage.
- [x] AC-23 „render-path spy": auf Go-Ebene als Endpunkt-Spy (beide POST-Ziele getroffen, korrekt getrennt) — die tiefere kind→Renderer-Zuordnung ist bereits durch S7a/S7b (getrennte Python-Endpunkte) abgedeckt.
- Keine offenen Fragen an den PO. Nächster PO-Eingriff: **AC-Freigabe (Phase 3)**.

## Nächster Schritt
`/30-write-spec` — Spec mit AC-Test-Mapping (AC-23/AC-24 aus der Programm-Spec übernehmen, Path-A-Design + verhaltensneutrale Invarianten als ACs fixieren).
