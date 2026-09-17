---
entity_id: fix_2149_scheduler_budget_teilb
type: bugfix
created: 2026-09-16
updated: 2026-09-17
status: draft
version: "1.1"
tags: [scheduler, multi-user, resilience, budget]
---

# Fix #2149 Scheibe B — Zeitbudget je Nutzer und je Lauf im Go-Scheduler

## Approval

- [ ] Approved

## Purpose

Der Go-Scheduler ruft Nutzer innerhalb eines Fan-out-Jobs (z. B. `alert_checks`)
sequenziell auf und wartet je Nutzer auf die volle HTTP-Antwort
(`s.client.Timeout = 3000s`, Issue #1912). Ein einzelner hängender Nutzer
verzögert dadurch die Verarbeitung **aller** übrigen Nutzer desselben Laufs
um bis zu 50 Minuten — Scheibe A (#2149, live seit 16.09.) macht dieses
Verhalten zwar sichtbar und alarmfähig, ändert aber nichts an der Verzögerung
selbst. Diese Scheibe führt ein Wartebudget je Nutzeraufruf und ein
Laufbudget je Job ein: Der eigentliche HTTP-Aufruf läuft in einer Goroutine
zu Ende, aber die Nutzerschleife wartet nur bis zum Budget und macht dann mit
dem nächsten Nutzer weiter. Ein hängender Nutzer wird dadurch selbst zum
sichtbaren, alarmfähigen Ereignis (Wiederverwendung der Scheibe-A-Zählkette),
statt weiterhin unsichtbar alle anderen aufzuhalten.

## Source

- **Datei:** `internal/scheduler/scheduler.go`
- **Identifier:** `func (s *Scheduler) runForAllUsers` (`:243-298`),
  `func (s *Scheduler) triggerEndpointForUser` (`:707-759`), `func
  isTimeoutTransportError` (`:73-79`), `func (s *Scheduler) recordRun`
  (`:634-683`), `func (s *Scheduler) tripReports` (`:412-448`), `func (s
  *Scheduler) briefingDispatch` (`:378-399`), `func (s *Scheduler) Status`
  (`:873-950`) — sowie neu `internal/scheduler/user_call_budget.go`

> **Schicht-Hinweis:** Reine Go-API-Schicht (`internal/scheduler/`). Kein
> Python-, Frontend- oder Infra-Eingriff. Python (`throttle_store.py`,
> `trip_alert.py`, `compare_alert.py`) bleibt unverändert — ein weiterlaufender
> Aufruf bedeutet für Python dieselbe eine synchrone Anfrage wie heute, nur
> dass der Go-Scheduler nicht mehr blockierend auf ihre Antwort wartet.

## Estimated Scope

- **LoC:** ~550-650 (Go-Code ~260-320, Go-Tests ~250-300, Doku ~40-50) —
  vor `/50-implement` `loc_limit_override 700` prüfen/setzen (analog Scheibe A).
- **Files:** ~7-9 (2 Quelldateien modifiziert, 1 neue Quelldatei, 2-3 neue
  Testdateien, 1 neue ADR-Datei + README-Index-Eintrag, 1 Doku-Datei
  `api_contract.md`, optional 1 Frontend-Datei)
- **Effort:** high — kritischer Pfad für alle Alarme, neue Nebenläufigkeit
  (Goroutine je wartendem Nutzeraufruf, Token-basierte Spätergebnis-
  Verbuchung), zwei getrennte Budget-Ebenen (Wartebudget je Nutzer,
  Laufbudget je Job) mit gegenseitiger Abhängigkeit (`min(...)`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0038 | Architektur-Entscheidung | Grundsatz „job-eigene Zeitgrenze unter Aufrufer-Wartezeit" — diese Scheibe erweitert ihn um eine aufruferseitige Wartegrenze je Nutzer, während der Aufgerufene (Python) weiterarbeitet. Braucht ein eigenes, neues ADR (s. unten), weil der Aufrufer erstmals **nicht mehr auf das Ende des eigenen Aufrufs wartet** |
| `docs/specs/modules/fix_2149_scheduler_nutzer_sichtbarkeit.md` (Scheibe A, live) | Spec (ausgeliefert) | Liefert `userRunState`, die Zählerregel (`ConsecutiveFailures`/`ConsecutivePartial`, Schwellen 3/8), die Alarm-Bündelung je Job-Lauf und das `users{}`-Aggregat — diese Scheibe fügt neue Outcome-Werte in dieselbe Zählkette ein, ohne einen neuen Alarmweg zu bauen |
| `docs/specs/modules/fix_1912_scheduler_briefing_timeout.md` | Spec (ausgeliefert) | `isTimeoutTransportError`, `partialRunError.wrapped`, `client.Timeout = 3000s` bleiben **unverändert**; diese Scheibe fügt eine eigene, vorgelagerte Fehlerklasse hinzu, die die #1912-Kette nicht ersetzt |
| `docs/specs/modules/fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md` | Spec (ausgeliefert) | Rangfolge `error > partial > ok`, `TryLock`-Overlap-Sperre je Job bleiben unverändert; ein Laufbudget-Rest wird wie ein Timeout als `partial` gerankt |
| `tripReports()` Alarm-Flanke (Issue #1346) | Bestehender Code (`scheduler.go:412-448`) | Bleibt unverändert und unabhängig vom Pro-Nutzer-Alarm; ein Budget-Fall darf `lastHardStatus` nicht auf `"error"` setzen, sonst feuert der Totalausfall-Alarm fälschlich |
| `docs/specs/modules/scheduler_multi_user.md` (`:32`) | Spec (ausgeliefert) | „Sequenziell bleibt" — diese Scheibe ändert daran nichts: Es entsteht keine echte Parallelität der Nutzerschleife, nur ein begrenztes Weiterlaufen einzelner, aufgegebener Aufrufe im Hintergrund |
| `docs/reference/api_contract.md` §12 | Referenz-Doku | Wird um drei neue, additive Zahlenfelder unter `jobs[].users{}` ergänzt |
| `/home/hem/henemm-infra/scripts/check-gregor20.sh` | Externer Konsument | Erwartet frisches `last_run.time` auch bei einem Lauf mit übersprungenen Nutzern — unverändert erfüllt, weil `recordRun` den Lauf immer als durchgeführt bucht |

## Implementation Details

### 1. Grundmechanik: warten aufhören, nicht abbrechen

`triggerEndpointForUser` bleibt als synchrone Funktion bestehen. Der Aufruf
wird pro Nutzer in eine Goroutine mit gepuffertem Ergebniskanal verpackt:

```
resultCh := make(chan error, 1)
go func() { resultCh <- s.triggerEndpointForUser(path, uid) }()
select {
case err := <-resultCh:
    // normale Klassifikation + Record() wie bisher (zaehlt)
case <-time.After(wait):
    // Wartebudget ueberschritten: sofort als "budget" buchen (zaehlt),
    // Goroutine + resultCh bleiben im In-Flight-Register, weiterlaufen
}
```

`wait = min(jobUserWaitBudget, verbleibendes Laufbudget)`. Der gepufferte
Kanal (Größe 1) verhindert einen Goroutine-Leak, falls niemand später
liest — er wird spätestens vom Cap-Timer konsumiert.

### 2. In-Flight-Register (neu: `internal/scheduler/user_call_budget.go`)

```go
type callToken uint64

type inFlightEntry struct {
    token    callToken
    resultCh chan error
    started  time.Time
}

type userCallBudget struct {
    mu    sync.Mutex
    state map[string]map[string]*inFlightEntry // [jobID][userID]
    next  callToken
}
```

- `Begin(jobID, userID string, resultCh chan error) callToken` — legt den
  Eintrag an (nur erreichbar, wenn kein Eintrag existiert, s. Punkt 3),
  vergibt einen neuen, monoton steigenden Token.
- `IsInFlight(jobID, userID string) bool` — Prüfung zu Beginn der
  Nutzerschleife, ob ein vorheriger Aufruf noch markiert ist.
- `TryHarvest(jobID, userID string) (err error, ok bool)` — nicht-blockierender
  Versuch (`select ... default:`), ein inzwischen fertiges Spätergebnis zu
  lesen; wird zu Beginn der Nutzerschleife aufgerufen, **bevor** über
  Skip/neuen POST entschieden wird (s. Punkt 4).
- `Finish(jobID, userID string, token callToken) (bool)` — entfernt den
  Eintrag nur, wenn `token` noch der aktuell hinterlegte ist; genutzt vom
  Cap-Timer und von `TryHarvest`. Gibt zurück, ob das Entfernen erfolgreich
  war (= Token war aktuell).

Eigener `sync.Mutex`, **nicht** persistiert (bewusst — ein Marker aus einem
Vorprozess ist nach einem Neustart bedeutungslos, weil auch das
Goroutinen-Ergebnis mit dem Prozess verschwindet, s. Known Limitations und
AC-14). Lock-Reihenfolge bleibt `s.mu → userState.mu`; `userCallBudget.mu`
wird nie gemeinsam mit einer der beiden anderen Sperren gehalten.

### 3. Cap je wartendem Aufruf

Zusätzlich zum Wartebudget bekommt jeder in den Hintergrund verlagerte
Aufruf einen eigenen Deckel, gestartet **im selben Moment** wie der Aufruf
(`time.AfterFunc(cap, func() { if s.callBudget.Finish(jobID, uid, token) { log... } })`):

- Alarm-Jobs (`alert_checks`, `radar_alert_checks`, `compare_alert_checks`,
  `compare_radar_alert_checks`, `compare_official_alert_checks`): eigener
  Cap **1800s** (= 2 Takte à 900s) — deutlich unter dem geteilten
  `s.client.Timeout = 3000s`, weil ein Alarm-Aufruf, der länger als zwei
  Takte unterwegs ist, praktisch nie mehr sinnvoll rechtzeitig ankommt.
- Briefing-Teiljobs (`trip_reports_hourly`, `compare_presets_daily`): **kein**
  zusätzlicher Cap-Context — das bestehende `s.client.Timeout = 3000s`
  (#1912) bleibt der einzige und alleinige Deckel, unverändert. Ein Aufruf,
  der den Client-Timeout erreicht, scheitert dort ohnehin mit
  `isTimeoutTransportError == true` und räumt sich über den regulären
  `resultCh`-Pfad selbst auf.

Läuft der Alarm-Cap ab, bevor `resultCh` liefert: Marker wird freigegeben
(`Finish` mit dem gestarteten Token), **keine Buchung** irgendeiner Art
erfolgt — weder `ok`/`error`/`partial`/`budget`. Das ist bewusst
grosszügiger als ein stiller Fehlschlag: Der nächste Lauf darf für diesen
Nutzer wieder einen frischen POST auslösen (AC-6). Antwortet der
Hintergrund-Aufruf dennoch nach Cap-Ablauf, wird das verworfene Ergebnis
**geloggt** (reines Server-Log, keine Zustands- oder Zähleränderung) — die
Nutzerkennung steht dort wie überall im Log als separater Formatparameter
zur Verfügung, erscheint aber nie im öffentlichen Fehlertext.

### 4. Klassifikation: eigene Fehlerklasse vor #1912

Neuer Fehlertyp in `scheduler.go`, der über `Unwrap()` an die bestehende
`*partialRunError`-Kette andockt, damit `recordRun`s vorhandene
`errors.As(err, &pe)`-Prüfung den Job-Lauf unverändert als `"partial"`
rankt (nicht `"error"` — sonst würde ein Budget-Fall #1346 fälschlich
auslösen):

```go
type budgetExceededError struct{ msg string }

func (e *budgetExceededError) Error() string { return e.msg }
func (e *budgetExceededError) Unwrap() error { return &partialRunError{msg: e.msg} }
```

`classifyUserOutcome` (bzw. die neue Schleifenlogik in `runForAllUsers`)
prüft **zuerst** `errors.As(err, &budgetErr)` — noch vor jedem Aufruf von
`isTimeoutTransportError` — und setzt bei Treffer `outcome = "budget"`.
Ein regulärer #1912-Transport-Timeout (der POST selbst läuft in die
Client-Frist) bleibt unverändert `outcome = "partial"`; beide Fälle ranken
den Job als `"partial"`, unterscheiden sich aber auf Nutzerebene (s. Punkt 5).

Analog wird ein Skip wegen bereits laufendem Aufruf (kein neuer POST, s.
Punkt 6) als eigener, dritter Wert `outcome = "skipped_in_flight"` geführt,
und ein wegen erschöpftem Laufbudget gar nicht erst versuchter Nutzer als
`outcome = "not_reached"`.

### 5. Erweiterte Zählerregel in `user_run_state.go` (Record)

Ergänzung der bestehenden Scheibe-A-Tabelle um drei neue Zeilen — die
Alarm-Flanken-Logik (3 ⇒ `high`, 8 ⇒ `normal`, Recovery, Bündelung je
Job-Lauf) bleibt **vollständig unverändert**, es werden nur zusätzliche
Outcome-Werte in dieselbe Zählkette eingespeist:

| Ergebnis | `ConsecutiveFailures` | `ConsecutivePartial` |
|---|---|---|
| `budget` (Wartebudget überschritten) | **+1** | unverändert |
| `skipped_in_flight` (Aufruf lief noch aus Vorlauf) | **+1** | unverändert |
| `not_reached` (Laufbudget vor diesem Nutzer erschöpft) | unverändert | **+1** |

Begründung `budget`/`skipped_in_flight` → `ConsecutiveFailures`: Ein
dauerhaft hängender Nutzer soll nach spätestens drei Läufen (≈ 30-45 min
bei `*/15`-Jobs) einen `high`-Alarm auslösen — der 8er-Teilerfolgs-Zähler
wäre mit bis zu 2h Latenz zu spät. Begründung `not_reached` →
`ConsecutivePartial`: Ein Nutzer, der nur deshalb nicht drankam, weil
**andere** Nutzer das Laufbudget aufgebraucht haben, trägt keine eigene
Schuld — Rotation (Punkt 7) verhindert zusätzlich systematische
Benachteiligung.

### 6. Spätergebnis-Verbuchung — zählt NICHT rückwirkend

Wenn `TryHarvest` zu Laufbeginn ein inzwischen fertiges Ergebnis mit
aktuellem Token findet, wird dieses Ergebnis **informativ** in
`LastRun`/`LastStatus`/`LastError` übernommen (direkter Feldschreibzugriff,
nicht über `Record()`), **ohne** `ConsecutiveFailures`/`ConsecutivePartial`
zu verändern und **ohne** eine Alarm-/Recovery-Flanke auszulösen. Diese
Entscheidung ist bewusst: Würde ein spätes `ok` die Fehlerserie
zurücksetzen, könnte ein Nutzer, der immer knapp über dem Wartebudget,
aber kurz danach erfolgreich antwortet, **nie** die Alarmschwelle von 3
erreichen — er wäre trotz chronischer Verzögerung dauerhaft unsichtbar
(AC-4). Die zählende Buchung ist bereits mit `budget`/`skipped_in_flight`
im Moment des Wartebudget-Ablaufs erfolgt und bleibt maßgeblich.

Ist der Token beim Harvest-Versuch bereits veraltet (Cap ist zwischenzeitlich
abgelaufen und hat den Eintrag entfernt, oder ein neuerer Lauf hat
inzwischen einen frischen Marker für denselben Nutzer gesetzt), wird das
Ergebnis verworfen und lediglich geloggt — mit derselben redigierten
Fehlertext-Konstruktion wie in Scheibe A (kein `?user_id=` im Text; die
`uid` steht wie überall im Log ohnehin als separater Formatparameter zur
Verfügung, das ist keine neue Ausnahme vom öffentlichen Redaktionsprinzip,
weil dieser Log nicht in `/api/scheduler/status` einfließt).

### 7. Skip bei bereits laufendem Aufruf, Laufbudget, Rotation

Vor der eigentlichen Nutzerschleife läuft ein **Vorab-Durchgang über alle
(rotierten) Nutzer**, der für jeden ein etwaiges Spätergebnis erntet
(`TryHarvest`/`harvestLateResult`, Punkt 6). Erst danach ist der
Marker-Zustand für **alle** Nutzer dieses Laufs aktuell — unabhängig davon,
an welcher Position ein Nutzer in der rotierten Liste steht.

Die anschließende Hauptschleife durchläuft **alle** Nutzer der rotierten
Liste bis zum Ende; sie bricht bei erschöpftem Laufbudget **nicht** sofort
ab. Je Nutzer gilt:

1. Ist für `(jobID, uid)` weiterhin ein Marker aktiv (Aufruf aus einem
   vorherigen Lauf läuft noch) → **kein** neuer POST, `outcome =
   "skipped_in_flight"`, weiter zum nächsten Nutzer.
2. Sonst: Ist das verbleibende Laufbudget bereits ≤ 0 → dieser Nutzer wird
   ohne Versuch als `outcome = "not_reached"` gebucht, weiter zum nächsten
   Nutzer (kein neuer POST mehr für den Rest des Laufs, die Schleife läuft
   aber bis zum Ende der Liste weiter).
3. Sonst: `wait = min(jobUserWaitBudget, verbleibendes Laufbudget)`, Aufruf
   per Goroutine (Punkt 1).

Die In-Flight-Prüfung hat bewusst **Vorrang** vor der Laufbudget-Prüfung:
Ein Nutzer mit noch markiertem Vorlauf-Aufruf zählt als
`skipped_in_flight`, selbst wenn das Laufbudget des aktuellen Laufs bereits
erschöpft ist — sonst würde derselbe hängende Nutzer je nach Zufall der
Erschöpfungsreihenfolge mal als `skipped_in_flight`, mal als `not_reached`
gebucht.

**Rotation:** neues Feld `runCounter map[string]int` (geschützt durch
`s.mu`, analog `overlapState`), inkrementiert bei jedem Eintritt in
`runForAllUsers` für die jeweilige `jobID`. Die Nutzerliste wird vor der
Schleife um `start = runCounter[jobID] % len(userIDs)` rotiert
(`rotated = append(userIDs[start:], userIDs[:start]...)`), sodass nicht
in jedem Lauf derselbe Nutzer am Ende steht, wenn das Laufbudget knapp wird.

**Job-Rang bei `skipped_in_flight`:** Ein `skipped_in_flight`-Fall liefert
sofort einen `&partialRunError{msg: "<jobID>: Aufruf aus Vorlauf läuft
noch"}` (öffentlicher Text, **ohne** Nutzerkennung) — ein Lauf mit
mindestens einem übersprungenen Nutzer rankt dadurch als `"partial"`, nicht
`"ok"`, sonst würde `briefingDispatch` trotz hängendem Nutzer fälschlich
einen Heartbeat pingen (AC-13).

**Job-Rang bei `not_reached`:** Gibt es in einem Lauf mindestens einen
`not_reached`-Nutzer und sonst keinen härteren Fehler (kein
`skipped_in_flight`, `budget` oder echter Fehler), liefert
`runForAllUsers` am Laufende einen eigenen synthetischen
`&partialRunError{msg: "<jobID>: Laufbudget erschöpft, N Nutzer nicht
erreicht"}` zurück, damit `last_run.status = "partial"` bleibt (Rangfolge
`error > partial > ok` unverändert) — ohne dass `lastHardStatus` berührt
wird (AC-10).

### 8. Budgets als injizierbare `Scheduler`-Felder

Analog zum bestehenden Testmuster (`sched.client = &http.Client{Timeout:
50ms}`) werden die Budgets **unexported** Felder auf `*Scheduler`, mit
Produktions-Defaults in `New()` und direkter Überschreibbarkeit in Tests
derselben Package (keine Millisekunden-Konstanten):

| Feld | Default | Herleitung |
|---|---|---|
| `alertRunBudget` | `720 * time.Second` | 80 % des `*/15`-Takts (900s) — dieselbe Reserve-Logik wie #1912 für den Stundentakt |
| `alertWaitBudget` | `300 * time.Second` | gemessen 91-308s (Scheibe-A-Analyse, PO-Konto), mit Puffer |
| `alertCallCap` | `1800 * time.Second` | 2 Takte à 900s |
| `briefingRunBudget` | `1440 * time.Second` je Teiljob | 80 % des Stundentakts (3600s), aufgeteilt auf die zwei sequenziellen Teiljobs `trip_reports_hourly` + `compare_presets_daily` (2×1440s = 2880s ≤ 3600s, 720s Reserve) — **nicht** die ursprünglich erwogenen 1500s+1500s, sondern nach derselben Herleitung wie bei Alarm-Jobs berechnet, damit beide Budgetarten konsistent begründet sind |
| `briefingWaitBudget` | `600 * time.Second` | > 319s gemessener Einzelversand (#1912), ≤ `briefingRunBudget` |
| — Briefing-Cap | kein eigenes Feld | bestehendes `s.client.Timeout = 3000s` bleibt der einzige Deckel (Punkt 3) |

`alertRunBudget`/`alertWaitBudget`/`alertCallCap` gelten für alle fünf
Alarm-Fan-out-Jobs (auch die beiden `7,22,37,52`-Radar-Jobs — deren Takt ist
ebenfalls effektiv 15 Minuten).

### 9. `Status()`-Erweiterung — nur Zahlen, je zuletzt abgeschlossenem Lauf

Neues, per `s.mu` geschütztes Feld `runBudgetSummary map[string]*jobBudgetSummary`
(Geschwister von `overlapState`, gefüllt am Ende jedes `runForAllUsers`-Laufs
für den jeweiligen `jobID`):

```go
type jobBudgetSummary struct {
    InFlight         int // am Laufende noch aktive Marker (Wartebudget ueberschritten)
    SkippedInFlight  int // wegen Marker aus Vorlauf kein neuer POST
    NotReachedBudget int // wegen erschoepftem Laufbudget gar nicht versucht
}
```

`InFlight` wird am Laufende ausschließlich über die bereits gefilterte,
aktuell existierende Nutzerliste (dieselbe Filterung wie `Prune`) ermittelt
— Marker gelöschter oder ausgeschlossener Test-Nutzer zählen nicht mit.

`usersField` (bzw. ein neuer Helfer `budgetSummaryField`, nach demselben
Muster wie `overlapField`) hängt bei den sieben Fan-out-Jobs zusätzlich
ein:

```json
"users": {
  "total": 3, "failing": 1, "partial": 0,
  "in_flight": 1, "skipped_in_flight": 0, "not_reached_budget": 0
}
```

Wie beim bestehenden `overlap`-Feld muss der Helfer in **beiden**
`Status()`-Zweigen (Haupt- und `subs`-Expansion) eingehängt werden — genau
die Falle, die die #1447- und Scheibe-A-Spec bereits dokumentiert haben.
Fehlt jeder der drei Werte bei `0`, bleibt das Feld dennoch vorhanden (im
Gegensatz zu `overlap`/`users`, die bei Nichtanwendbarkeit ganz fehlen) —
`0` ist hier ein gültiger, informativer Wert, kein „nicht anwendbar".
`docs/reference/api_contract.md` §12 wird um diese drei Felder ergänzt.

**Frontend-Anzeige:** `frontend/src/routes/account/+page.svelte` zeigt die
drei neuen Zahlen **nicht** an — explizit Out of Scope dieser Scheibe (s.
Known Limitations), weil die Account-Seite bereits `failing`/`partial`
zeigt und eine weitere Erweiterung eigenständig abgewogen werden sollte.

## Expected Behavior

- **Input:** unverändert — dieselben Cron-Ticks, dieselben Python-Endpoints.
- **Output (Zeitverhalten), neu:** ein einzelner hängender Nutzer verzögert
  andere Nutzer desselben Laufs um höchstens das für diesen Job geltende
  Wartebudget (300s Alarm, 600s Briefing), nicht mehr um bis zu 3000s.
- **Output (`/api/scheduler/status`), neu:** `jobs[].users.in_flight`,
  `jobs[].users.skipped_in_flight`, `jobs[].users.not_reached_budget` bei
  den sieben Fan-out-Jobs — reine Zahlen, keine Nutzerkennung.
- **Output (MQ):** kein neuer Nachrichtentyp — `budget`/`skipped_in_flight`
  speisen die bestehende `high`-Schwelle (3), `not_reached` die bestehende
  `normal`-Schwelle (8) aus Scheibe A.
- **Side effects:** neue, nicht persistierte In-Flight-Register im
  Prozessspeicher; weiterlaufende Goroutinen nach einem Wartebudget-Ablauf,
  begrenzt durch den Alarm-Cap (1800s) bzw. den bestehenden Client-Timeout
  (3000s, Briefing).
- **Unverändert:** Rangfolge `error > partial > ok`, Overlap-Mechanik (#1447
  S2a), `isTimeoutTransportError`/Client-Timeout (#1912), #1346-Totalausfall-
  Alarm, Scheibe-A-Alarmschwellen und -Bündelung, sequenzielle Nutzerschleife
  (kein echtes Parallel-Fan-out).

## Acceptance Criteria

- **AC-1:** Given drei Nutzer desselben Alarm-Jobs, wobei Nutzer B erst nach
  500s antwortet (Wartebudget 300s) / When der Lauf gestartet wird / Then
  wird B nach spätestens 300s als `budget` gebucht und der Lauf fährt sofort
  mit dem nächsten Nutzer fort, statt auf B's Antwort zu warten.
  - Test: `httptest`-Server mit steuerbarer Verzögerung je `user_id`;
    Messung der Zeit bis zum POST an den dritten Nutzer.

- **AC-2:** Given B's Aufruf aus Lauf 1 läuft beim Start von Lauf 2 (900s
  später) noch / When Lauf 2 denselben Job für B ausführt / Then erhält der
  Python-Core für B in Lauf 2 keinen zweiten POST, B wird als
  `skipped_in_flight` gezählt.
  - Test: `httptest`-Server zählt Requests je `user_id`; Assertion
    Request-Count == 1 nach Lauf 2.

- **AC-3:** Given B wird in drei aufeinanderfolgenden Läufen jeweils als
  `budget` oder `skipped_in_flight` gebucht (gemischte Kategorien erlaubt)
  / When der dritte dieser Läufe abgeschlossen ist / Then löst genau eine
  MQ-Nachricht mit Priorität `high` aus, über dieselbe Bündelung wie
  Scheibe A.
  - Test: `recordingNotifier` zählt Aufrufe über drei simulierte Läufe.

- **AC-4:** Given B wurde in Lauf 1 als `budget` gebucht
  (`ConsecutiveFailures == 1`), der Hintergrund-Aufruf schließt kurz danach
  doch noch erfolgreich ab, bevor der Cap abläuft / When das Spätergebnis
  eintrifft / Then werden `LastRun`/`LastStatus` aktualisiert, aber
  `ConsecutiveFailures` bleibt bei 1 — ein dritter Budget-Lauf in Folge löst
  trotz der zwischenzeitlichen Erfolgsmeldung den Alarm aus.
  - Test: drei Läufe mit je knapp-über-Budget-Antwortzeit und jeweils kurz
    danach erfolgreichem Abschluss; nach dem dritten Lauf genau ein Alarm.

- **AC-5:** Given der Cap für B's Aufruf aus Lauf 1 ist bereits abgelaufen
  und der Marker freigegeben, ein neuerer Lauf hat inzwischen einen frischen
  Marker für B gesetzt / When der ursprüngliche, alte Aufruf schließlich
  doch antwortet / Then wird dieses veraltete Ergebnis verworfen (kein
  Zustandsupdate über `Record()` oder direktes Feld), nur eine Log-Zeile
  ohne Nutzerkennung im öffentlich sichtbaren Text entsteht.
  - Test: künstlich verzögerter erster Aufruf über den Cap hinaus, danach
    zweiter Lauf mit neuem Marker; Prüfung, dass der alte Kanal keine
    Zustandsänderung mehr auslöst.

- **AC-6:** Given B's Aufruf läuft länger als der Alarm-Cap (1800s) / When
  der Cap abläuft, bevor eine Antwort eintrifft / Then wird der In-Flight-
  Marker freigegeben, es erfolgt keine Buchung irgendeiner Art für diesen
  Aufruf, und der nächste Lauf kann für B einen neuen POST auslösen.
  - Test: Cap testweise auf wenige Millisekunden gesetzt, `httptest`-Server
    antwortet nie; zweiter Lauf prüft neuen Request-Count für B.

- **AC-7:** Given das Laufbudget eines Alarm-Jobs (720s) ist durch zwei
  langsame Nutzer bereits ausgeschöpft, bevor der dritte Nutzer an der Reihe
  wäre / When der Lauf endet / Then wird der dritte Nutzer als
  `not_reached_budget` gezählt (kein POST versucht), der Job-Lauf rankt als
  `partial`, und `ConsecutiveFailures` dieses Nutzers bleibt unverändert.
  - Test: Test-Budgets klein gesetzt, zwei simulierte langsame Nutzer
    verbrauchen das Laufbudget; dritter Nutzer wird geprüft.

- **AC-8:** Given derselbe Job läuft dreimal hintereinander mit knapp
  ausreichendem Laufbudget für nur zwei von drei Nutzern / When die drei
  Läufe ausgewertet werden / Then ist nicht in jedem Lauf derselbe Nutzer
  der `not_reached_budget`-Fall, sondern die Startposition rotiert
  nachweisbar (`Startindex = Laufzähler mod Nutzeranzahl`).
  - Test: drei Läufe, Prüfung der tatsächlich kontaktierten Nutzer je Lauf.

- **AC-9:** Given ein Nutzeraufruf überschreitet das Wartebudget, während
  ein regulärer #1912-Client-Timeout denselben Aufruf ebenfalls als
  Transport-Timeout klassifizieren würde / When die Klassifikation
  stattfindet / Then wird der Ausgang als eigene Kategorie `budget` gebucht
  (zählt in `ConsecutiveFailures`), nicht als #1912-Timeout-`partial`, weil
  die Budget-Prüfung dem Warten vorgelagert ist und vor jeder
  `isTimeoutTransportError`-Prüfung greift.
  - Test: gezielter Unit-Test auf die Prüfreihenfolge mit einem Fall, der
    beide Bedingungen erfüllen würde.

- **AC-10:** Given ein Lauf von `trip_reports_hourly` hat für einen von drei
  Nutzern eine Budget-Überschreitung, die anderen zwei sind `ok` / When der
  Lauf endet / Then rankt `last_run.status` als `partial` (nicht `error`),
  `lastHardStatus` bleibt unverändert, und `tripReports()` löst **keinen**
  #1346-Totalausfall-Alarm aus.
  - Test: bestehender #1346-Regressionstest um ein Budget-Szenario ergänzt;
    Assertion `high`-Notifier-Aufrufzähler == 0.

- **AC-11:** Given ein Lauf erzeugt mindestens je einen Fall von `in_flight`,
  `skipped_in_flight` und `not_reached_budget` / When
  `/api/scheduler/status` danach abgefragt wird / Then enthält die Antwort
  für den betroffenen Job alle drei neuen Zahlenfelder unter `users{}`, aber
  an keiner Stelle eine `user_id` oder eine vollständige URL.
  - Test: JSON-Volltextsuche der `Status()`-Antwort nach bekannten
    Test-`user_id`s und `"?user_id="`.

- **AC-12:** Given ein Lauf enthält mindestens einen `skipped_in_flight`-
  oder `budget`-Fall / When der Lauf regulär beendet wird / Then wird
  `last_run.time` auf die aktuelle Ausführungszeit gesetzt, genau wie
  `check-gregor20.sh` es für die Frische-Prüfung voraussetzt.
  - Test: Zeitstempel vor/nach dem Lauf vergleichen.

- **AC-13:** Given `briefingDispatch` ist mit einer echten, nicht-leeren
  Heartbeat-URL konfiguriert (Test-`httptest`-Server als Ziel), und im Lauf
  wird mindestens ein Nutzer als `skipped_in_flight` oder `budget` gebucht,
  sodass mindestens einer der beiden Teiljobs nicht `ok` rankt / When der
  Dispatch-Lauf endet / Then wird kein Heartbeat-Ping an die konfigurierte
  URL gesendet.
  - Test: `httptest`-Server als Heartbeat-Ziel, Request-Counter bleibt 0
    (nicht die leere-URL-Variante, die trivial grün wäre).

- **AC-14:** Given ein Nutzeraufruf ist als in-flight markiert, als der
  Go-Prozess durch eine neue `*Scheduler`-Instanz über denselben Store-Pfad
  ersetzt wird (simulierter Neustart) / When die neue Instanz denselben Job
  für denselben Nutzer ausführt / Then wird ein neuer POST ausgelöst — kein
  Marker aus der alten Instanz blockiert ihn, weil das In-Flight-Register
  nur im Prozessspeicher gehalten wird.
  - Test: zwei `*Scheduler`-Instanzen, erste hält einen offenen Marker,
    zweite wird frisch erzeugt und der Request-Count geprüft.

- **AC-15:** Given der bestehende #1912-Test prüft `s.client.Timeout ==
  3000 * time.Second` / When diese Scheibe implementiert ist / Then bleibt
  dieser Test ohne inhaltliche Anpassung grün, weil das Client-Timeout
  selbst unverändert bleibt und der neue Alarm-Cap ein unabhängiger,
  zusätzlicher Mechanismus ist.
  - Test: bestehende Testdatei (`TestClientTimeout_Is3000Seconds`),
    unveränderter Regressionslauf.

## Known Limitations

- **Neustart-Restfenster Doppellauf.** Das In-Flight-Register ist bewusst
  nicht persistiert. Ein Deploy/Neustart von `gregor-api` während ein
  Nutzeraufruf im Hintergrund noch läuft (Wartebudget bereits
  überschritten, Cap noch nicht abgelaufen) leert das Register, während
  Python (sync `def`) den ursprünglichen Aufruf synchron zu Ende bringt.
  Der nächste Tick kann für diesen Nutzer erneut auslösen — Trip-Briefings
  sind über `briefing_slots.py`-Claims geschützt, der Alarmpfad
  (`throttle_store.py`) hat eine bekannte Check-then-record-Lücke und kann
  in diesem Fenster theoretisch doppelt alarmieren. Python bleibt in dieser
  Scheibe unverändert.
- **Deckel-Ablauf-Restrisiko.** Nach Ablauf des Alarm-Caps (1800s) wird der
  Marker freigegeben, obwohl der Python-Aufruf theoretisch noch laufen
  könnte — praktisch durch die Python-eigene Trip-Deadline (90s je Trip,
  `trip_alert.py:61-66`) begrenzt.
- **Shutdown verwirft laufende Goroutinen unverbucht.** `Scheduler.Stop()`
  wartet weiterhin nur auf cron-gestartete Funktionen (unverändert seit vor
  dieser Scheibe), nicht auf im Hintergrund weiterlaufende Nutzeraufrufe —
  ihr Ergebnis geht beim Prozessende verloren, Python bleibt unberührt.
- **Kein Frontend-Zähler.** Die drei neuen `users{}`-Felder erscheinen
  ausschließlich im API-Response; `frontend/src/routes/account/+page.svelte`
  wird in dieser Scheibe nicht erweitert.
- **Weiterhin sequenziell.** Es entsteht keine echte Parallelität der
  Nutzerschleife — nur einzelne, aufgegebene Aufrufe laufen begrenzt im
  Hintergrund weiter. Echte Parallelität bleibt laut
  `scheduler_multi_user.md:32` einer eigenen, künftigen ADR-pflichtigen
  Entscheidung vorbehalten (~8-10 Nutzer, heute 3).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0070 (neu anzulegen — die im Auftrag genannte Nummer
  „ADR-0039" ist bereits durch `docs/adr/0039-amtliche-warnungen-aus-
  kontingentfreiem-feed.md` vergeben; 0070 ist die nächste freie Nummer
  Stand 2026-09-16, **vor Anlage erneut gegen `docs/adr/` prüfen**, da
  parallele Sessions am selben Repository arbeiten können)
- **Rationale:** ADR-0038 hat bereits festgehalten, dass ein Job seine
  eigene Zeitgrenze unter der Aufrufer-Wartezeit trägt. Diese Scheibe geht
  einen Schritt weiter: Der **Aufrufer** (Go-Scheduler) hört selbst auf zu
  warten, während der **Aufgerufene** (Python) unverändert bis zum Ende
  weiterarbeitet — ein Grundsatzwechsel, der ADR-0038 nicht widerspricht,
  aber explizit erweitert (neues ADR mit Status „Erweitert ADR-0038", kein
  „Abgelöst durch"). Neu und ADR-pflichtig, weil system-übergreifend und
  schwer umkehrbar im Sinne der ADR-Faustregeln (`docs/adr/README.md`):
  (1) faktisch kann pro hängendem Nutzer künftig **höchstens eine**
  zusätzliche, unaufgeforderte Python-Anfrage im nächsten Tick entstehen
  (der In-Flight-Marker verhindert eine zweite, solange der erste Aufruf
  noch läuft) — das berührt die in `scheduler_multi_user.md:32`
  dokumentierte Sequenziell-Entscheidung, ohne sie aufzugeben; (2) es
  entsteht erstmals ein Zustand, in dem der Go-Scheduler und der laufende
  Python-Aufruf bewusst auseinanderlaufen dürfen. Das ADR-File und der
  Eintrag in `docs/adr/README.md` sind Pflicht-Deliverables dieser
  Implementierung (Index-Drift-Test `test_adr_index_drift.py`).

## Changelog

- 2026-09-16: Initial spec created (Scheibe B von Issue #2149)
- 2026-09-17 (v1.1): Implementation Details an die Adversary-verifizierte
  Umsetzung angeglichen (Verdict VERIFIED,
  `docs/artifacts/fix-2149-scheduler-budget-teilb/adversary-dialog.md`,
  Sektion „Sonderprüfung: gemeldete Abweichungen des Developers"): Abschnitt
  7 beschreibt jetzt den Vorab-Ernte-Durchgang über alle Nutzer sowie die
  Hauptschleife, die bei erschöpftem Laufbudget **nicht** sofort abbricht,
  sondern je verbleibendem Nutzer zuerst die In-Flight-Prüfung
  (`skipped_in_flight`) vor der Laufbudget-Prüfung (`not_reached`) anwendet;
  ergänzt, dass bereits ein `skipped_in_flight`-Fall den Job-Lauf zum
  Teilerfolg macht (Fehlertext „Aufruf aus Vorlauf läuft noch", ohne
  Nutzerkennung). Abschnitt 3 ergänzt um das Logging verworfener
  Spätergebnisse nach Cap-Ablauf. Abschnitt 9 ergänzt, dass `in_flight` nur
  aktuell existierende Nutzer zählt. Keine dieser Korrekturen ändert
  Verhalten oder Akzeptanzkriterien — sie richten den Beschreibungstext an
  der bereits implementierten und verifizierten Umsetzung aus.
