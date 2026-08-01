---
entity_id: fix_1447_s2a_scheduler_ueberlappung_teilerfolg
type: bugfix
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.1"
tags: [scheduler, go, observability, überlappung, teilerfolg]
---

# Fix #1447 Scheibe S2a — Überlappungsschutz + Teilerfolg im Go-Scheduler

## Approval

- [ ] Approved

## Purpose

Der Go-Scheduler (`internal/scheduler/scheduler.go`) startet jeden Cron-Tick
unabhängig davon, ob der vorherige Lauf desselben Jobs noch läuft
(`cron.New()` ohne `cron.WithChain(...)`, `:79`) — zwei überlappende Läufe
können gleichzeitig `lastRuns` beschreiben, wobei der zuletzt *fertige* Lauf
gewinnt, unabhängig von der Startreihenfolge. Zusätzlich kennt
`jobResult.Status` nur `"ok"`/`"error"` (`:32`) und `triggerResponseBody`
wertet aus der Python-Antwort ausschließlich `failed` aus (`:365-369`) — das
Feld `status`, das Scheibe S1 für abgebrochene Alarm-Läufe auf `"partial"`
setzt, wird von Go **nie gelesen**. Ein Alarm-Zyklus, der wegen der neuen
Zeitobergrenze aus S1 nur teilweise durchlief, kommt im Go-Status als voller
Erfolg an.

Diese Scheibe schließt beide Lücken auf der Go-Seite: (Teil A) ein Job
startet nicht erneut, solange er noch läuft, und der übersprungene Tick wird
sichtbar verbucht statt kommentarlos zu verschwinden; (Teil B) ein
`status: "partial"` aus dem Python-Kern schlägt bis in
`/api/scheduler/status` durch, statt als `"ok"` gemeldet zu werden. Beide
Mechanismen laufen über denselben gemeinsamen Engpass (`recordRun`,
`triggerEndpointForUser`) und wirken damit automatisch auf **alle** neun
Scheduler-Jobs, nicht nur auf `alert_checks` — siehe „Zwangsläufige
Auswirkung auf andere Jobs" unten.

**Design-Korrektur (v1.1):** Ein übersprungener Tick darf den zuletzt
tatsächlich ausgeführten Lauf **nicht überschreiben** — sonst entsteht
derselbe Fehlertyp wie in #1434 (DPC-Zonen-Drift): ein Zustand ohne eigenen
Zeitstempel je Kategorie erzeugt ein Dauersignal, das „einmal kurz
überlappt" nicht mehr von „hängt seit einer Stunde" unterscheiden kann.
Hängt ein Job dauerhaft (genau der Fall aus #1447 — ein Lauf über 120
Sekunden), würde **jeder** Folge-Tick „skipped, vor 30 Sekunden" darüber
schreiben — das sieht frisch und harmlos aus, während der Job seit einer
Stunde steht, und die einzige Information, an der man das erkennen könnte
(„letzter Erfolg war vor einer Stunde"), wäre weg. Diese Spec führt daher
den Overlap-Skip als **eigenen, danebenliegenden Zustand** je Job, analog
zur `zone_drift`-Teilstruktur aus #1434 (getrennter Zeitstempel je
Kategorie, kumulativer Zähler seit dem letzten echten Ereignis, fehlender
Block bedeutet Ruhe). Details in „Implementation Details" und „Vertragsform
`/api/scheduler/status`".

## Source

- **Datei:** `internal/scheduler/scheduler.go`
- **Identifier:** `type jobResult` (`:29-34`), `func (s *Scheduler) recordRun`
  (`:342-359`), `type triggerResponseBody` (`:365-369`),
  `func (s *Scheduler) triggerEndpointForUser` (`:372-399`),
  `func (s *Scheduler) runForAllUsers` (`:148-183`), `func (s *Scheduler)
  Status` (`:472-535`)

> **Schicht-Hinweis:** Reine Go-API-Schicht (`internal/scheduler/`). Keine
> Python-Änderung (S1 liefert die Antwortform bereits), kein Frontend-Anteil.
> `internal/handler/scheduler_status.go` (der HTTP-Handler für
> `/api/scheduler/status`) bleibt unverändert — er serialisiert nur
> `sched.Status()`, dessen Inhalt sich durch die neuen Werte automatisch
> ändert.

## Estimated Scope

- **LoC:** geschätzt **~480-620 added+deleted** (Code **und** Tests) — s.
  „LoC-Einschätzung" unten. **Deutlich über dem Workflow-Limit von 250.**
  PO-Freigabe für `workflow.py set-field loc_limit_override 650` ist
  **vor** der Implementierung einzuholen.
- **Files:** 1 Quelldatei modifiziert, 2 neue Testdateien, 1 Doku-Datei
  (`docs/reference/api_contract.md`, zählt nicht gegen das Limit)
- **Effort:** medium-high — zwei orthogonale Mechanismen (Sperre +
  Status-Klassifikation), eine Rangfolge-Entscheidung bei gemischten
  Nutzer-Ergebnissen, ein von der Zeitachse getrennt geführter
  Overlap-Zustand (nach dem #1434-Muster) und ein Nebenläufigkeits-Test, der
  besonders sorgfältig konstruiert werden muss

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0038 | Architektur-Entscheidung | Trägt den Grundsatz „Job-eigene Zeitgrenze unter Aufrufer-Wartezeit" und benennt den Überlappungsschutz bereits ausdrücklich als „Fix #1447 Scheibe S2" — diese Scheibe setzt das um, ohne den Grundsatz zu erweitern |
| `docs/specs/modules/fix_1447_s1_alarm_lauf_zeitgrenze.md` | Spec (ausgeliefert) | Liefert die Antwortform `{"status":"partial","count":N,"checked":C,"skipped":S,"duration_s":D,"reason":"deadline"}` für `/api/scheduler/alert-checks`, die diese Scheibe erstmals auswertet |
| `docs/specs/modules/fix_1434_dpc_zonen_drift.md` | Spec (ausgeliefert) | Vorbild für die Trennung von „letztes echtes Ereignis" (unangetastet) und „zusätzlicher, kumulativer Zustand mit eigenem Zeitstempel" (`zone_drift`-Teilstruktur) — auf den Overlap-Skip dieser Scheibe übertragen |
| `sync.Mutex.TryLock()` | Go-Stdlib (seit Go 1.18, Repo auf Go 1.25) | Nicht-blockierender Sperrversuch je Job-ID — Grundlage des Überlappungsschutzes |
| `robfig/cron/v3` | Bibliothek (bereits Dependency) | Startet jeden Tick in eigener Goroutine ohne Rücksicht auf laufende Vorgänger — genau das Verhalten, das diese Scheibe je Job-ID abfängt |
| `internal/handler/scheduler_status.go` | Go-Handler (nur gelesen) | Serialisiert `sched.Status()` unverändert — neue Werte fließen automatisch durch, kein Code-Eingriff nötig |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | Neue Job-Sperren-Verwaltung (`jobLocks map[string]*sync.Mutex` + Helfer); `recordRun` nimmt die Sperre für die Dauer von `fn()`; bei belegter Sperre wird **nicht** `lastRuns[jobID]` überschrieben, sondern ein separater `jobOverlapState` je Job hochgezählt (Zähler + jüngster Zeitstempel, s. u.); bei jedem tatsächlich ausgeführten Lauf wird dieser Zähler zurückgesetzt; neuer Fehlertyp `partialRunError`, den `triggerEndpointForUser` bei `status: "partial"` (und `failed` == 0/fehlend) zurückgibt; `runForAllUsers` klassifiziert je Nutzer in hart/fehlerhaft vs. teilweise und bildet daraus die Rangfolge `error > partial > ok`; `Status()` gibt das neue Overlap-Feld pro Job zusätzlich zu `last_run` aus |
| `internal/scheduler/job_overlap_test.go` | CREATE | Nachweis Teil A: gleicher Job wird bei Überlappung nicht zweimal ausgeführt; mehrere aufeinanderfolgende Skips sind vom einmaligen Skip unterscheidbar; der zuletzt ausgeführte Lauf bleibt dabei unverändert sichtbar; unterschiedliche Jobs blockieren sich nicht — inkl. der geforderten Gegenprobe (s. Test-Plan) |
| `internal/scheduler/job_status_partial_test.go` | CREATE | Nachweis Teil B: `status: "partial"` ohne `failed` schlägt bis `jobResult.Status` durch, `failed > 0` bleibt unverändert `"error"` (Regressionstest gegen #1012 AC-5), Rangfolge bei gemischten Nutzer-Ergebnissen |
| `docs/reference/api_contract.md` | MODIFY (zählt nicht gegen LoC-Limit) | §12 (Scheduler Status Endpoint): `jobs[].last_run` bleibt unverändert der zuletzt **ausgeführte** Lauf (nie durch einen Overlap-Skip überschrieben), `jobs[].last_run.status`-Enum bleibt `ok`/`partial`/`error` (kein `"skipped"` als Laufergebnis); neues, optionales Feld `jobs[].overlap` (nur vorhanden, wenn seit dem letzten ausgeführten Lauf mindestens ein Tick übersprungen wurde); §14.6 (Alert-Checks Trigger, S1) ergänzt um den Verweis, dass S2a die dort dokumentierte „Known limitation" auflöst |

### Estimated Changes

- Files: 4 (1 Quelldatei, 2 neue Testdateien, 1 Doku-Datei)
- LoC: s. „LoC-Einschätzung"

## LoC-Einschätzung

| Datei | ~LoC (added, netto grob) |
|---|---|
| `internal/scheduler/scheduler.go` (Sperren-Verwaltung, `jobOverlapState`, `partialRunError`, `recordRun`-Umbau inkl. Overlap-Zustand statt Überschreiben, `runForAllUsers`-Umbau, `triggerEndpointForUser`-Erweiterung, `Status()`-Erweiterung um das Overlap-Feld in beiden Ausgabe-Zweigen — Haupt-Jobs und expandierte `subs`, Doc-Kommentare) | 140-210 (inkl. ~25-30 gelöschter/ersetzter Zeilen aus dem heutigen `recordRun`/`runForAllUsers`) |
| `internal/scheduler/job_overlap_test.go` (4 Tests: gleicher Job blockiert sich selbst und wird nicht ausgeführt inkl. Gegenprobe; mehrfache aufeinanderfolgende Skips sind zählbar unterscheidbar; letzter ausgeführter Lauf übersteht Skips unverändert; zwei verschiedene Jobs blockieren sich nicht) | 200-240 |
| `internal/scheduler/job_status_partial_test.go` (3 Tests/Tabellen: `triggerEndpointForUser` klassifiziert `partial` korrekt; `alertChecks()` verbucht `partial` End-to-End über `Status()`; Rangfolge bei gemischten Nutzer-Ergebnissen, mind. 2 Unterfälle) | 150-180 |

Summe grob **490-630 added+deleted**, gerundet **~480-620**. Das ist
deutlich über dem 250-Zeilen-Limit des Workflows und höher als die
ursprüngliche Schätzung dieser Spec (v1.0: ~390-500) — Grund ist die
Design-Korrektur: der Overlap-Zustand braucht einen eigenen, vom
`last_run`-Zeitpunkt getrennten Zähler samt Zeitstempel (statt eines
einzelnen überschriebenen Felds), das in **beiden** Ausgabe-Zweigen von
`Status()` (Haupt-Jobs und expandierte `subs`) berücksichtigt werden muss,
plus zwei zusätzliche Testfälle für die Unterscheidbarkeit „ein Skip" vs.
„viele Skips in Folge" und für „letzter Lauf übersteht den Skip". **Nicht**
akzeptabel als Ausweg: eine der beiden Testdateien verkleinern, indem sie
weniger echte Fälle abdeckt (insbesondere nicht die Rangfolge-Unterfälle,
die Gegenprobe oder die Overlap-Unterscheidbarkeits-Tests streichen).

## Implementation Details

### Teil A — Überlappungsschutz mit Sichtbarkeit, getrennt von `last_run`

`recordRun` ist bereits heute der gemeinsame Engpass **aller** neun Jobs
(`tripReports`, `comparePresetsDaily`, `alertChecks`, `radarAlertChecks`,
`compareAlertChecks`, `compareRadarAlertChecks`,
`compareOfficialAlertChecks`, `dataWriteSelftest`, `inboundCommands` — jeder
ruft `s.recordRun(jobID, fn)` auf, geprüft durch vollständiges Durchlesen
aller Aufrufstellen in `scheduler.go`). Eine Sperre **innerhalb** von
`recordRun`, keyed auf `jobID`, deckt damit automatisch alle neun Jobs ab,
ohne jede Aufrufstelle einzeln anzufassen.

Neu am `Scheduler`-Struct:

```go
jobLocksMu sync.Mutex
jobLocks   map[string]*sync.Mutex

// overlapState verzeichnet übersprungene Ticks je Job GETRENNT von lastRuns
// (Issue #1447 S2a, Korrektur nach #1434-Muster): ein Skip darf den
// Zeitpunkt/Ausgang des zuletzt tatsächlich ausgeführten Laufs nicht
// überschreiben, sonst verdeckt ein Dauerhänger sich selbst hinter einem
// immer frischen "skipped"-Zeitstempel. Geschützt durch s.mu wie lastRuns.
overlapState map[string]*jobOverlapState
```

Neuer Zustandstyp:

```go
// jobOverlapState zählt Ticks, die wegen eines noch laufenden Vorgängers
// übersprungen wurden — seit dem letzten TATSÄCHLICH ausgeführten Lauf
// dieses Jobs. Wächst mit jedem weiteren Skip, wird bei jedem echten Lauf
// (Erfolg, Teilerfolg ODER Fehler) auf 0 zurückgesetzt. Analog zu
// zone_drift in #1434: kumulativer Zähler + eigener Zeitstempel, damit
// "einmal kurz übersprungen" von "hängt seit N Ticks" unterscheidbar bleibt.
type jobOverlapState struct {
    SkippedSinceLastRun int        `json:"skipped_since_last_run"`
    LastSkippedAt        *time.Time `json:"last_skipped_at,omitempty"`
}
```

Neuer Sperren-Helfer, analog zum bestehenden
`onceMissingHB`/`onceMissingHBmu`-Muster für lazy-initialisierte Maps unter
eigenem Mutex:

```go
func (s *Scheduler) jobLock(jobID string) *sync.Mutex {
    s.jobLocksMu.Lock()
    defer s.jobLocksMu.Unlock()
    l, ok := s.jobLocks[jobID]
    if !ok {
        l = &sync.Mutex{}
        s.jobLocks[jobID] = l
    }
    return l
}
```

`recordRun` nimmt die Job-Sperre für die **gesamte Dauer** von `fn()`
(`TryLock()`, nicht `Lock()` — ein blockierendes `Lock()` würde die
Cron-Goroutine des zweiten Ticks anhalten statt den Tick zu überspringen,
und robfig/cron würde bei häufigen Overlaps Goroutinen stapeln). Bei
belegter Sperre wird **ausschließlich** `overlapState[jobID]`
fortgeschrieben — `lastRuns[jobID]` bleibt unangetastet:

```go
func (s *Scheduler) recordRun(jobID string, fn func() error) {
    lock := s.jobLock(jobID)
    if !lock.TryLock() {
        now := time.Now().In(s.cron.Location())
        s.mu.Lock()
        st, ok := s.overlapState[jobID]
        if !ok {
            st = &jobOverlapState{}
            s.overlapState[jobID] = st
        }
        st.SkippedSinceLastRun++
        st.LastSkippedAt = &now
        n := st.SkippedSinceLastRun
        s.mu.Unlock()
        log.Printf("[scheduler] %s: previous run still in progress, "+
            "skipping this tick (%d skipped since last executed run)", jobID, n)
        return // lastRuns[jobID] bewusst NICHT angefasst
    }
    defer lock.Unlock()

    err := fn()

    s.mu.Lock()
    defer s.mu.Unlock()
    // Der Job lief gerade tatsächlich (egal mit welchem Ausgang) — die
    // Overlap-Zählung seit dem letzten ausgeführten Lauf beginnt neu.
    if st, ok := s.overlapState[jobID]; ok {
        st.SkippedSinceLastRun = 0
    }
    // ... bestehende Erfolg/Fehler-Verbuchung in lastRuns[jobID], erweitert
    // um "partial" (s. Teil B) — unverändert gegenüber v1.0 dieser Spec.
}
```

**`Status()` gibt beide Zustände nebeneinander aus, nicht ineinander
verschachtelt oder überschrieben:**

```go
job["last_run"] = ...          // unverändert: nur der zuletzt AUSGEFÜHRTE Lauf
if st, ok := s.overlapState[meta.id]; ok && st.SkippedSinceLastRun > 0 {
    job["overlap"] = map[string]any{
        "skipped_since_last_run": st.SkippedSinceLastRun,
        "last_skipped_at":        st.LastSkippedAt.Format(time.RFC3339),
    }
}
```

Dieselbe Ergänzung ist **zweimal** nötig: im Haupt-Zweig von `Status()` und
im `subs`-Expansions-Zweig (`briefing_dispatch` → `trip_reports_hourly` /
`compare_presets_daily`, `:482-503`) — sonst fehlt das Overlap-Signal genau
für die beiden Jobs, die über den unified Cron-Eintrag laufen. Das Feld
`overlap` fehlt vollständig, solange kein einziger Skip seit dem letzten
Lauf aufgetreten ist — **fehlender Block bedeutet Ruhe, kein Fehler**,
exakt die aus #1434 übernommene Konvention.

**Bewusst je Job, nicht global:** Der Schlüssel ist `jobID` (z. B.
`"alert_checks"`, `"radar_alert_checks"`, `"trip_reports_hourly"`) — ein
laufender `alert_checks`-Lauf sperrt und zählt nur `alert_checks`, nicht
`radar_alert_checks` oder `data_write_selftest`. Das erfüllt AC-4
strukturell, ohne dass es einer Sonderbehandlung bedarf.

**`briefingDispatch()` bleibt unverändert:** Es ruft `s.tripReports()` und
`s.comparePresetsDaily()` sequenziell auf; jede dieser beiden Methoden
verbucht ihre eigene Sperre und ihren eigenen Overlap-Zustand unter ihrer
eigenen `jobID` (`"trip_reports_hourly"`, `"compare_presets_daily"`)
innerhalb ihres eigenen `recordRun`-Aufrufs. `briefingDispatch()` selbst
bekommt **keine** eigene Sperre — siehe „Known Limitations" zur Konsequenz
daraus.

### Teil B — Teilerfolg durchreichen

Neuer, unexportierter Fehlertyp, der eine *reduzierte* statt einer
*gescheiterten* Ausführung markiert:

```go
// partialRunError signalisiert, dass ein Job-Lauf teilweise erfolgreich war
// (status: "partial" ohne failed > 0 aus der Python-Antwort, Issue #1447 S1) —
// recordRun verbucht das als jobResult.Status "partial", nicht "error".
type partialRunError struct{ msg string }

func (e *partialRunError) Error() string { return e.msg }
```

`triggerEndpointForUser` erhält nach der bestehenden `failed > 0`-Prüfung
(unverändert, AC-6) einen neuen Zweig:

```go
var parsed triggerResponseBody
if jsonErr := json.Unmarshal(body, &parsed); jsonErr == nil {
    if parsed.Failed > 0 {
        return fmt.Errorf(...) // unverändert, Issue #1012 AC-5
    }
    if parsed.Status == "partial" {
        return &partialRunError{msg: fmt.Sprintf(
            "%s?user_id=%s reported partial status (count=%d): %s",
            path, userID, parsed.Count, string(body),
        )}
    }
}
```

`runForAllUsers` klassifiziert die pro-Nutzer-Fehler statt nur den ersten zu
merken:

```go
var firstHardErr, firstPartialErr error
for _, uid := range userIDs {
    err := s.triggerEndpointForUser(path, uid)
    if err == nil {
        continue
    }
    var pe *partialRunError
    if errors.As(err, &pe) {
        log.Printf("[scheduler] %s: user %s partial: %v", jobID, uid, err)
        if firstPartialErr == nil {
            firstPartialErr = err
        }
        continue
    }
    log.Printf("[scheduler] %s: user %s failed: %v", jobID, uid, err)
    if firstHardErr == nil {
        firstHardErr = err
    }
}
if firstHardErr != nil {
    return firstHardErr
}
return firstPartialErr // nil, falls kein Nutzer partial war -> "ok"
```

`recordRun` unterscheidet beim Klassifizieren von `err` (aus `fn()`) per
`errors.As` zwischen `partialRunError` und echtem Fehler:

```go
if err != nil {
    var pe *partialRunError
    status := "error"
    if errors.As(err, &pe) {
        status = "partial"
    } else {
        log.Printf("[scheduler] %s failed: %v", jobID, err)
    }
    s.lastRuns[jobID] = &jobResult{Time: ..., Status: status, Error: err.Error()}
} else {
    s.lastRuns[jobID] = &jobResult{Time: ..., Status: "ok"}
}
```

**Rangfolge bei gemischten Nutzer-Ergebnissen (explizit festgelegt):**
`error` > `partial` > `ok`. Ein einziger Nutzer mit echtem Fehler macht den
gesamten Job-Lauf `"error"`, auch wenn andere Nutzer nur `"partial"` waren —
ein verlorener Alarm-Versand (echter Fehler) ist gravierender als ein
verzögerter (Teilerfolg) und darf im aggregierten Status nicht hinter einem
bloßen Teilerfolg verschwinden. Gibt es keinen echten Fehler, aber
mindestens einen `partial`-Nutzer, ist der Job-Lauf `"partial"`. Nur wenn
**alle** Nutzer `"ok"` waren, ist der Job-Lauf `"ok"`.

**Geprüft und bewusst als Grenze belassen, nicht dieselbe Fehlerklasse wie
Teil A:** `firstHardErr`/`firstPartialErr` in `runForAllUsers` merken sich
nur die Kennung/Nachricht des **ersten** betroffenen Nutzers je Kategorie —
Nutzer 3 und 4 mit demselben oder einem anderen Fehler tauchen im
aggregierten `jobResult.Error`-Text nicht namentlich auf, obwohl jeder
einzeln geloggt wird (`log.Printf` je Nutzer, unverändert gegenüber heute).
Das ist **kein** Wiederauftreten des Teil-A-Fehlertyps: `jobResult.Time` und
`jobResult.Status` je Tick sind stets aktuell für **diesen** Lauf, es gibt
keine falsche Frische — nur eine reduzierte Detailtiefe innerhalb eines
bereits korrekt als `"error"`/`"partial"` erkennbaren Gesamtzustands. Dieses
Verhalten besteht für harte Fehler bereits **vor** dieser Scheibe
unverändert (`firstErr` in `runForAllUsers` heute, `:172-182`) und wird für
`partial` lediglich gleichermaßen übernommen, nicht verschärft. Eine
Mehrnutzer-Detailliste im aggregierten Status wäre eine eigene,
weiterführende Änderung und würde den ohnehin bereits deutlich
überschrittenen Umfang dieser Scheibe zusätzlich vergrößern — bewusst nicht
Teil von S2a, siehe „Known Limitations".

### Zwangsläufige Auswirkung auf andere Jobs

Weil `recordRun` und `triggerEndpointForUser` gemeinsamer Code aller Jobs
sind, gilt zwangsläufig:

- **Überlappungsschutz + Overlap-Zustand (Teil A)** gilt automatisch für
  **alle neun** Jobs, einschließlich `radar_alert_checks`,
  `compare_alert_checks`, `compare_radar_alert_checks`,
  `compare_official_alert_checks`, `data_write_selftest` und
  `inbound_command_poll` — nicht nur für `alert_checks`. Das ist
  beabsichtigt und in AC-4 explizit geprüft.
- **Teilerfolg-Durchreichung (Teil B)** gilt automatisch für alle Jobs, die
  über `triggerEndpointForUser` laufen — also auch `radar_alert_checks`,
  `compare_alert_checks`, `compare_radar_alert_checks`,
  `compare_official_alert_checks`, `trip_reports_hourly` und
  `compare_presets_daily`. Praktisch wirksam wird das heute nur bei
  `alert_checks`, weil ausschließlich dessen Python-Endpunkt (S1)
  `status: "partial"` ohne `failed` liefert; die anderen Endpunkte melden
  `status: "partial"` bislang nur **zusammen mit** `failed > 0` (bestehende
  `#766`/`#1290`-Konvention in `api/routers/scheduler.py`), was weiterhin
  als `"error"` klassifiziert wird. Sollte einer dieser Endpunkte künftig
  denselben S1-Deadline-Mechanismus bekommen, greift die Teilerfolg-Meldung
  ohne weiteren Go-Eingriff.
- **`inbound_command_poll`** bekommt **nur** den Überlappungsschutz, **nicht**
  die Teilerfolg-Durchreichung: `inboundCommands()` ruft
  `triggerGlobalEndpoint`, nicht `triggerEndpointForUser`, auf —
  `triggerGlobalEndpoint` parst den Antwort-Body gar nicht. Diese Scheibe
  ändert `triggerGlobalEndpoint` **nicht** (kein bekannter Bedarf, kein
  Python-Endpunkt dahinter meldet `status`).
- **`data_write_selftest`** bekommt ebenfalls nur den Überlappungsschutz —
  seine `fn` (`probeDataWritable`) ist kein HTTP-Aufruf und kann folglich nie
  `partialRunError` zurückgeben.
- Kein Python-Code, keine Compare-/Radar-spezifische Logik wird angefasst —
  die Wirkung entsteht ausschließlich durch den geteilten Go-Mechanismus.

## Vertragsform `/api/scheduler/status` (Kern der Korrektur)

`"skipped"` ist **kein Wert von `jobs[].last_run.status`** — das Enum bleibt
`ok`/`partial`/`error`, unverändert das Ergebnis eines tatsächlich
ausgeführten Laufs. Ein Overlap-Skip ist stattdessen ein **Zustand des
Jobs**, sichtbar als eigenständiges, optionales Geschwisterfeld:

```json
{
  "id": "alert_checks",
  "name": "Alert Checks (every 15 min)",
  "next_run": "2026-08-01T13:15:00Z",
  "last_run": {
    "time": "2026-08-01T12:00:00Z",
    "status": "ok",
    "error": null
  },
  "overlap": {
    "skipped_since_last_run": 3,
    "last_skipped_at": "2026-08-01T13:00:00Z"
  }
}
```

- `last_run` zeigt **immer** den zuletzt tatsächlich ausgeführten Lauf —
  auch während der Job gerade (wieder) läuft oder Ticks übersprungen
  werden. Ein Betrachter erkennt daran, **ob und wann** der Job zuletzt
  wirklich durchlief und mit welchem Ergebnis.
- `overlap` fehlt vollständig, solange seit dem letzten ausgeführten Lauf
  kein einziger Tick übersprungen wurde — fehlendes Feld bedeutet Ruhe,
  niemals einen Fehler (analog zur `zone_drift`-Konvention aus #1434).
- `overlap.skipped_since_last_run` wächst mit jedem weiteren übersprungenen
  Tick und macht damit „einmal kurz überlappt" (`1`) von „hängt seit vier
  Ticks" (`4`) unterscheidbar — genau der Wert, der in der ursprünglichen
  Fassung dieser Spec fehlte.
- `overlap.last_skipped_at` ist der Zeitpunkt des jüngsten Skips; zusammen
  mit `next_run` lässt sich daraus ableiten, wie lange der Zustand schon
  andauert.
- Der Zähler wird auf `0` zurückgesetzt (und das Feld verschwindet dadurch
  wieder aus der Ausgabe), sobald der Job das nächste Mal tatsächlich
  ausgeführt wird — unabhängig vom Ausgang dieses Laufs.

## Expected Behavior

- **Input:** unverändert — Cron-Ticks lösen dieselben `s.recordRun(jobID,
  fn)`-Aufrufe aus wie heute.
- **Output (`/api/scheduler/status`), neu möglich:**
  - Zusätzliches `overlap`-Feld je Job (s. „Vertragsform" oben), sobald seit
    dem letzten ausgeführten Lauf mindestens ein Tick übersprungen wurde.
    `last_run` bleibt davon unberührt.
  - `last_run.status: "partial"` — wenn mindestens ein Nutzer `status:
    "partial"` ohne `failed` gemeldet hat und kein Nutzer einen echten
    Fehler hatte.
- **Unverändert:** `last_run.status: "ok"` bei vollständigem Erfolg aller
  Nutzer, `last_run.status: "error"` bei mindestens einem echten Fehler
  (HTTP ≥ 400, Netzfehler, `failed > 0`) — identisch zum heutigen Verhalten.
- **Side effects:** neue Log-Zeile bei Überlappungs-Skip (inkl. laufender
  Skip-Zähler) und bei Teilerfolg (`"... reported partial status ..."`).
  Kein neuer HTTP-Endpunkt, keine neue Konfiguration.

## Test-Plan / Test-Politik

Kein Mock-Theater, keine Dateiinhalt-Prüfung als Verhaltensnachweis.
Co-located in `internal/scheduler/`, `go` liegt unter `/usr/local/go/bin`
(nicht im PATH).

### Teil A — `internal/scheduler/job_overlap_test.go`

- **Der heikelste Test dieser Scheibe:** ein Nebenläufigkeits-Test, der den
  Prüfling (Scheduler-Instanz, Sperren-Map) für jeden Nebenläufigkeits-Fall
  neu aufbaut, kann grün werden, obwohl der Schutz fehlt oder falsch
  verdrahtet ist. **Deshalb:** genau eine `*Scheduler`-Instanz aufbauen,
  danach `recordRun`-Aufrufe für dieselbe `jobID` echt nebenläufig fahren —
  die blockierende Ausführung hält kontrolliert über einen ungepufferten
  Kanal, nachfolgende Aufrufe laufen erst, nachdem die erste sicher
  innerhalb von `fn` angekommen ist (Signal-Kanal, kein
  `time.Sleep`-Raten).
  - `TestRecordRun_SecondCallDuringOverlap_NotExecuted`: zählt
    `atomic.Int32`-Ausführungen der injizierten `fn`; nach dem zweiten,
    synchron im Hauptgoroutine ausgeführten `recordRun`-Aufruf muss der
    Zähler weiterhin `1` sein — die zweite `fn` wurde **gar nicht**
    aufgerufen, nicht nur "schnell durchgelaufen". **Gegenprobe:** dieser
    Test ist ohne die `TryLock`-Sperre in `recordRun` nachweislich rot (der
    Zähler stünde auf `2`), weil `recordRun` heute jede `fn` bedingungslos
    ausführt — kein künstlicher Toggle nötig, das ist der natürliche
    RED-Zustand vor der Implementierung.
  - `TestRecordRun_ConsecutiveOverlapSkips_CountDistinguishesFromSingleSkip`
    (AC-2): während dieselbe blockierende Ausführung weiterläuft, wird
    `recordRun` für dieselbe `jobID` **dreimal** hintereinander erneut
    aufgerufen. Geprüft wird, dass `overlapState[jobID].SkippedSinceLastRun`
    nach dem ersten Zusatzaufruf `1`, nach dem zweiten `2`, nach dem dritten
    `3` ist — nicht nur, dass irgendein Skip-Zustand existiert. Das ist die
    eigentliche Korrektur gegenüber der ursprünglichen Fassung: ein Test,
    der nur `> 0` prüft, hätte den Fehler nicht gefangen.
  - `TestRecordRun_OverlapSkip_DoesNotOverwriteLastExecutedRun` (neu, AC-3):
    Job läuft einmal vollständig und erfolgreich durch (`lastRuns[jobID]`
    zeigt `Status: "ok"`, `Time: T1`). Danach startet derselbe Job erneut
    und blockiert; während er blockiert, wird `recordRun` für dieselbe
    `jobID` mehrfach erneut aufgerufen (Skips). Geprüft wird, dass
    `lastRuns[jobID].Time == T1` und `lastRuns[jobID].Status == "ok"`
    **unverändert** bleiben, während `overlapState[jobID]` parallel
    hochzählt — End-to-End über `sched.Status()` für `id ==
    "alert_checks"` (`last_run` und `overlap` gleichzeitig geprüft).
  - `TestRecordRun_DifferentJobsDoNotBlockEachOther` (AC-5): zwei
    verschiedene `jobID`s, `recordRun` für die erste blockiert kontrolliert
    wie oben; die zweite `jobID` muss währenddessen **vollständig
    durchlaufen** (Zähler für die zweite `fn` erreicht `1`, nicht `0`) —
    Beweis, dass Sperre und Overlap-Zustand je Job und nicht global sind.

### Teil B — `internal/scheduler/job_status_partial_test.go`

- `TestTriggerEndpointForUser_PartialWithoutFailed_ReturnsPartialNotHardError`:
  `httptest`-Server liefert `{"status":"partial","count":1,"checked":3,"skipped":2,"duration_s":90.02,"reason":"deadline"}`
  (kein `failed`-Feld); `triggerEndpointForUser` liefert einen Fehler
  ungleich `nil`, der sich per `errors.As` als `*partialRunError`
  identifizieren lässt (Abgrenzung von der bestehenden
  `TestTriggerEndpoint_FailedBodyTreatedAsError`, die weiterhin einen
  gewöhnlichen Fehler ohne diese Klassifikation erwartet und unverändert
  grün bleiben muss — Regressionsschutz für #1012 AC-5).
- `TestAlertChecks_PartialResponse_RecordedAsPartialStatus`: End-to-End über
  `sched.alertChecks()` mit demselben Server-Body wie oben; `sched.Status()`
  zeigt für `id == "alert_checks"` `last_run.status == "partial"`, nicht
  `"ok"`.
- `TestRunForAllUsers_MixedUserResults_ErrorRanksAbovePartial`, table-driven
  mit mindestens zwei Unterfällen:
  1. Nutzer A → `partial`, Nutzer B → HTTP 500 (echter Fehler) ⇒
     Gesamt-Status `"error"`.
  2. Nutzer A → `ok`, Nutzer B → `partial` ⇒ Gesamt-Status `"partial"`.
  Server unterscheidet Nutzer über den `user_id`-Query-Parameter.

### Namens- und Pfadregeln

- Beide Testdateien nach Verhalten benannt, keine Issue-Nummer im Dateinamen.
- Package `scheduler` (nicht `scheduler_test`) — Zugriff auf unexportierte
  `recordRun`, `triggerEndpointForUser`, `partialRunError`,
  `jobOverlapState`, analog zu allen bestehenden Testdateien in diesem
  Paket.
- Kein `time.Sleep`-basiertes Timing — ausschließlich Kanäle/`sync`-Primitive
  für Reihenfolge-Garantien.

## Acceptance Criteria

- **AC-1:** Given derselbe Job (identifiziert über seine Job-ID) läuft
  gerade noch / When der nächste planmäßige Tick für genau diesen Job
  ansteht / Then wird dieser Tick nicht ausgeführt, sondern übersprungen,
  ohne die Job-Funktion selbst aufzurufen.
  - Test: `TestRecordRun_SecondCallDuringOverlap_NotExecuted` — Ausführungs-
    Zähler der injizierten Job-Funktion bleibt bei `1`, obwohl `recordRun`
    zweimal für dieselbe Job-ID aufgerufen wurde.

- **AC-2:** Given ein Job hängt so lange, dass mehrere aufeinanderfolgende
  Ticks übersprungen werden / When `/api/scheduler/status` währenddessen
  wiederholt abgefragt wird / Then steigt die Anzahl der seit dem letzten
  ausgeführten Lauf übersprungenen Ticks sichtbar mit jedem weiteren Skip
  an — ein andauerndes Hängen ist dadurch von einem einmaligen, kurzen
  Overlap unterscheidbar, nicht nur an der bloßen Anwesenheit eines
  Skip-Vermerks.
  - Test:
    `TestRecordRun_ConsecutiveOverlapSkips_CountDistinguishesFromSingleSkip`
    — der Zähler steigt nachweislich `1 → 2 → 3`, nicht nur „vorhanden".

- **AC-3:** Given ein Job wird durch einen oder mehrere Overlap-Skips
  übersprungen, während sein vorheriger Lauf noch läuft / When
  `/api/scheduler/status` danach abgefragt wird / Then zeigt der
  `last_run`-Eintrag dieses Jobs weiterhin unverändert Zeitpunkt und
  Ergebnis des zuletzt tatsächlich ausgeführten Laufs — ein Skip
  überschreibt niemals den letzten echten Lauf.
  - Test: `TestRecordRun_OverlapSkip_DoesNotOverwriteLastExecutedRun` —
    `last_run.time`/`last_run.status` bleiben über mehrere Skips hinweg
    identisch zum Stand vor dem Overlap.

- **AC-4:** Given zwei unterschiedliche Jobs laufen gleichzeitig / When
  einer von beiden noch nicht fertig ist / Then wird der jeweils andere Job
  dadurch nicht blockiert und läuft zu seiner planmäßigen Zeit normal an.
  - Test: `TestRecordRun_DifferentJobsDoNotBlockEachOther` — der zweite Job
    führt seine Funktion vollständig aus, während der erste kontrolliert
    blockiert.

- **AC-5:** Given der Python-Kern meldet für einen Nutzer `status:
  "partial"` ohne dass `failed` gesetzt ist / When der Go-Scheduler die
  Antwort auswertet / Then trägt der Job-Status in `/api/scheduler/status`
  `"partial"` ein, nicht `"ok"`.
  - Test: `TestAlertChecks_PartialResponse_RecordedAsPartialStatus`.

- **AC-6:** Given der Python-Kern meldet für einen Nutzer `failed` größer 0,
  unabhängig vom Wert von `status` / When der Go-Scheduler die Antwort
  auswertet / Then bleibt der Job-Status `"error"`, wie vor dieser Änderung.
  - Test: bestehender `TestTriggerEndpoint_FailedBodyTreatedAsError` bleibt
    unverändert grün; neuer
    `TestTriggerEndpointForUser_PartialWithoutFailed_ReturnsPartialNotHardError`
    grenzt den neuen Partial-Fall davon ab.

- **AC-7:** Given innerhalb eines Job-Laufs melden verschiedene Nutzer
  unterschiedliche Ergebnisse (z. B. ein Nutzer partial, ein anderer error)
  / When der Gesamtstatus des Job-Laufs gebildet wird / Then gewinnt
  `"error"` vor `"partial"` vor `"ok"` — ein einzelner echter Fehler macht
  den ganzen Lauf `"error"`, auch wenn andere Nutzer nur teilweise
  erfolgreich waren.
  - Test: `TestRunForAllUsers_MixedUserResults_ErrorRanksAbovePartial`
    (beide Unterfälle: error+partial → error; ok+partial → partial).

- **AC-8:** Given ein Job-Lauf ohne Überlappung, ohne Teilerfolg und ohne
  Fehler / When er wie gewohnt komplett durchläuft / Then verhält er sich in
  Zeitpunkt, Status und Inhalt der Antwort exakt wie vor dieser Scheibe —
  Status `"ok"` für alle beteiligten Nutzer, kein `overlap`-Feld in der
  Antwort.
  - Test: bestehende Tests (`TestBriefingDispatch_TriggersBothEndpointsAndRecordsBothLastRuns`,
    `TestTripReports_IteratesOverAllUsers`, `TestStatus` u. a.) bleiben ohne
    Anpassung grün.

## Known Limitations

- **`runForAllUsers` hält nur den ersten betroffenen Nutzer je Kategorie
  fest** (Kennung/Nachricht in `jobResult.Error`), nicht alle. Bewusst
  belassen, s. „Teil B" oben — anders als der korrigierte Teil-A-Fehler
  entsteht dadurch keine falsche Frische (`jobResult.Time` ist stets aktuell
  für den jeweiligen Tick), nur reduzierte Detailtiefe innerhalb eines
  bereits korrekt klassifizierten Gesamtzustands. Vollständige
  Mehrnutzer-Details bleiben im Log, nicht im Status.
- **`briefingDispatch()` selbst ist nicht gesperrt**, nur seine beiden
  Teil-Jobs einzeln. Zwei überlappende `briefing_dispatch`-Ticks können sich
  bei ihren jeweils zweiten Teil-Jobs (`compare_presets_daily`) durchaus
  gegenseitig nicht blockieren, obwohl sie „demselben" Cron-Eintrag
  entstammen — das ist beabsichtigt (Sperre ist je Job, nicht je
  Cron-Eintrag, AC-4) und keine Lücke dieser Scheibe.
- **`inbound_command_poll` und `data_write_selftest` erhalten nur
  Überlappungsschutz, keine Teilerfolg-Durchreichung** — s. „Zwangsläufige
  Auswirkung auf andere Jobs".
- **Die 120-Sekunden-Wartezeit des Go-HTTP-Clients bleibt unverändert** —
  weder angehoben noch gesenkt, wie im Auftrag dieser Scheibe festgelegt.
- **`overlapState` wächst nie über eine laufende Prozess-Lebensdauer hinaus
  zurück** — nach einem Neustart des Go-Prozesses ist jeder Zähler wieder
  `0`/das Feld fehlt, analog zu `lastRuns` selbst (bereits heute nicht
  persistent). Kein neues Verhalten, nur zur Vollständigkeit festgehalten.
- **Kein Heartbeat für die Alarm-Jobs.** Das ist Scheibe S2b und hängt an
  einer noch offenen Infrastruktur-Rückfrage (zwei tote BetterStack-Plätze
  „Gregor20 Core"/„Gregor20 Wetterquellen"; zusätzlich liest
  `internal/config/config.go:19` die abweichend benannte
  `HEARTBEAT_COMPARE_PRESETS` statt der Projektkonvention
  `GZ_HEARTBEAT_*`). Diese Scheibe rührt daran nicht.
- **Kein Python-seitiger Effekt.** Nur `alert-checks` liefert heute
  `status: "partial"` ohne `failed`; andere Endpunkte müssten dafür erst
  denselben S1-Deadline-Mechanismus bekommen (nicht Teil dieser Scheibe).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0038 trägt diese Scheibe bereits)
- **Rationale:** ADR-0038 hat den Grundsatz „job-eigene Zeitgrenze unter
  Aufrufer-Wartezeit" bereits festgehalten und den Überlappungsschutz darin
  ausdrücklich als Folgemaßnahme benannt („Der Überlappungsschutz selbst ist
  als eigene Maßnahme vorgesehen (Fix #1447 Scheibe S2), ersetzt aber nicht
  die Notwendigkeit einer job-eigenen Grenze."). Diese Scheibe setzt diese
  bereits getroffene Grundsatzentscheidung um. Die verbleibenden
  Entscheidungen dieser Scheibe — Sperre je `jobID` über `sync.Mutex.TryLock()`
  statt `cron.WithChain(cron.SkipIfStillRunning(...))` (weil Letzteres nur
  loggen, nicht in `lastRuns` verbuchen kann, s. Auftrag), die Rangfolge
  `error > partial > ok` bei gemischten Nutzer-Ergebnissen, und die Trennung
  von Overlap-Zustand und letztem ausgeführten Lauf (Anwendung des in
  #1434 bereits etablierten Musters, keine neue Grundsatzentscheidung) —
  sind lokale Implementierungsentscheidungen innerhalb eines einzelnen
  Pakets (`internal/scheduler/`), nicht „schwer umkehrbar" oder
  system-übergreifend im Sinne der ADR-Faustregeln (`docs/adr/README.md`).
  Sie stehen stattdessen hier in der Spec. Kein neues ADR nötig.

## Changelog

- 2026-08-01: Initial spec created
- 2026-08-01 (v1.1): Design-Korrektur vor PO-Vorlage — Overlap-Skip
  überschreibt nicht mehr `last_run`, sondern führt einen eigenen,
  kumulativen Zustand mit Zeitstempel (`overlap`), analog zum
  #1434-`zone_drift`-Muster. AC-2 neu gefasst (Zählbarkeit statt bloßer
  Anwesenheit), AC-3 neu ergänzt (letzter Lauf übersteht Skip),
  nachfolgende ACs umnummeriert. `runForAllUsers`-Mehrnutzer-Detailverlust
  geprüft und als bewusste, nicht gleichartige Grenze dokumentiert.
  Umfangsschätzung von ~390-500 auf ~480-620 angehoben.
