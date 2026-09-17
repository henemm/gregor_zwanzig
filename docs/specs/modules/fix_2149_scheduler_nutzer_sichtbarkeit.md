---
entity_id: fix_2149_scheduler_nutzer_sichtbarkeit
type: bugfix
created: 2026-09-15
updated: 2026-09-15
status: draft
version: "1.0"
tags: [scheduler, multi-user, observability]
---

# Fix #2149 Scheibe A — Sichtbarkeit + Alarm je Nutzer im Go-Scheduler

## Approval

- [ ] Approved

## Purpose

Der Go-Scheduler bucht Job-Ergebnisse nur **aggregiert je Job**
(`lastRuns[jobID]`) — ein Einzelnutzer, dessen Läufe dauerhaft scheitern oder
chronisch unvollständig bleiben, ist unsichtbar, solange andere Nutzer
desselben Jobs erfolgreich sind (Rangfolge `error > partial > ok` aus #1447
S2a verdeckt genau diesen Fall zusätzlich, wenn Nutzer wechseln). Diese
Scheibe führt eine Buchführung **je (Job, Nutzer)** ein — Zeitpunkt, Status,
Fehlertext, Fehlerserie, Teilerfolgsserie — persistiert sie über Neustarts
hinweg und meldet dauerhafte Einzelnutzer-Probleme per MQ an `infra`, ohne
Nutzerkennungen über den öffentlichen `/api/scheduler/status`-Endpoint
preiszugeben.

**Out of Scope / Folge-Scheibe B (selbes Issue #2149):** Zeitbudget je
Nutzeraufruf und Gesamtbudget je Lauf, eine eigene Fehlerklassifikation für
einen Budget-Abbruch (heute würde `context.DeadlineExceeded` fälschlich als
`partial` durchgehen, s. `isTimeoutTransportError`), ein In-Flight-Marker
gegen Doppellauf/Doppelversand (die Race entsteht erst durch einen
Go-seitigen Abbruch, während Python synchron weiterarbeitet) und Rotation
der Nutzer-Reihenfolge. Der Scheduler bleibt **sequenziell**; echte
Parallelität kommt erst bei spürbarem Wachstum (~8-10 Nutzer, heute 3) und
braucht dann ein eigenes ADR — das ist bereits in
`docs/specs/modules/scheduler_multi_user.md` als bewusste Entscheidung
festgehalten und wird hier nicht neu verhandelt. Issue #2149 wird erst nach
Scheibe B geschlossen.

**Update 2026-09-17:** Scheibe B ist umgesetzt (Verdict VERIFIED) —
Wartebudget je Nutzeraufruf, Laufbudget je Lauf, In-Flight-Register mit
Token und die Outcome-Werte `budget`/`skipped_in_flight`/`not_reached` s.
`docs/specs/modules/fix_2149_scheduler_budget_teilb.md` und
`docs/adr/0070-aufruferseitige-wartegrenze-je-nutzeraufruf.md`.

## Source

- **Datei:** `internal/scheduler/scheduler.go`
- **Identifier:** `func (s *Scheduler) runForAllUsers` (`:237-288`),
  `func (s *Scheduler) triggerEndpointForUser` (`:617-665`), `func (s
  *Scheduler) recordRun` (`:553-602`), `func (s *Scheduler) Status`
  (`:765-836`)

> **Schicht-Hinweis:** Reine Go-API-Schicht (`internal/scheduler/`). Kein
> Python-, Frontend- oder Infra-Eingriff. `internal/handler/scheduler_status.go`
> serialisiert weiterhin nur `sched.Status()` unverändert.

## Estimated Scope

- **LoC:** ~630-810 grob geschätzt (Code + Tests) — deutlich über der
  ursprünglich angenommenen Größenordnung von ~300-400; s.
  „LoC-Einschätzung" unten. Der bereits gesetzte `loc_limit_override 500`
  reicht damit voraussichtlich **nicht** und muss vor `/50-implement`
  geprüft und ggf. angehoben werden.
- **Files:** ~6-8 (1 Quelldatei modifiziert, 1 neue Quelldatei, 3 neue
  Testdateien, ggf. 1 bestehende Testdatei, 2 Doku-Dateien)
- **Effort:** medium-high — ein neuer, gekapselter Zustandstyp mit eigener
  Nebenläufigkeits-Disziplin (mehrere `*/15`- und stündliche Jobs schreiben
  potenziell in derselben Minute), eine gezielte Redaktion an einer
  Fehler-Konstruktionsstelle unter Erhalt der bestehenden `errors.As`-Kette
  aus #1912, zwei Ausgabe-Zweige in `Status()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0038 | Architektur-Entscheidung | Trägt den Grundsatz „job-eigene Zeitgrenze/Beobachtbarkeit unter Aufrufer-Wartezeit"; diese Scheibe erweitert die daraus bereits abgeleitete #1447-S2a-Buchführung um die Nutzer-Dimension, ohne den Grundsatz zu ändern |
| `docs/specs/modules/fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md` | Spec (ausgeliefert) | Vorbild für „eigener, danebenliegender Zustand mit eigenem Zeitstempel/Zähler, getrennt von `lastRuns`" (`overlapState`) — dieselbe Bauart wird hier auf `(jobID, userID)` angewendet. Rangfolge `error > partial > ok` und die Klassifikation via `errors.As(*partialRunError)` bleiben unverändert und werden nur zusätzlich pro Nutzer gebucht |
| `docs/specs/modules/fix_1912_scheduler_briefing_timeout.md` | Spec (ausgeliefert) | `isTimeoutTransportError`, `partialRunError.wrapped`, `client.Timeout = 3000s` bleiben unverändert — diese Scheibe redigiert nur den Meldungstext, nicht die `errors.As`/`errors.Is`-Kette, die #1912 zum gleichzeitigen Feststellen von „ist Timeout" und „ist partial" braucht |
| `tripReports()` Alarm-Flanke (Issue #1346) | Bestehender Code (`scheduler.go:320-367`) | Bleibt unverändert und unabhängig vom neuen Pro-Nutzer-Alarm; bestehende „genau 1 Alarm"-Tests dürfen nicht brechen |
| `store.ListUserIDs`, `model.IsTestUserID` | Go-Funktionen | Liefern die Nutzerliste bzw. filtern Testkonten — Pruning-Basis für den neuen Zustand |
| `notify.SendMQ` / `Scheduler.notifier` | Injizierbare Funktion | Bestehender, testbarer Alarmweg (wie in `tripReports()`), wird für Pro-Nutzer-Alarme wiederverwendet |
| `internal/store/write.go: writeFileAtomic` | Go-Funktion (unexported, nur als Muster) | tmp-im-Zielverzeichnis + `os.Rename`-Muster; da unexported in Package `store`, wird eine gleichwertige Funktion lokal in `internal/scheduler/user_run_state.go` implementiert (kein Import-Zugriff möglich) |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/scheduler/scheduler.go` | MODIFY | Fehlertext-Konstruktion in `triggerEndpointForUser` redigiert (kein `?user_id=` mehr im Rückgabefehler, der in den öffentlichen `jobResult.Error` einfließt) — unter Erhalt der `wrapped`-Fehlerkette für #1912; `runForAllUsers` ruft nach jeder Klassifikation eines Nutzer-Ergebnisses `s.userState.Record(...)` auf und am Ende `s.userState.Prune(...)`; `Scheduler`-Struct bekommt Feld `userState *userRunState`, `New()` lädt den persistierten Zustand; `Status()` ergänzt in **beiden** Ausgabe-Zweigen (Haupt- und `subs`-Expansion) ein optionales `users`-Aggregat je Fan-out-Job |
| `internal/scheduler/user_run_state.go` | CREATE | Zustandstyp je `(jobID, userID)`: `LastRun`, `LastStatus`, `LastError` (redigierter Text), `ConsecutiveFailures`, `ConsecutivePartial`, Alarm-Merker; Schwellen (3 hart, 8 Teilerfolg); `Record`/`Prune`/`Aggregate`; eigener `sync.Mutex`; atomares Laden/Schreiben (tmp + rename, analog `store/write.go`) |
| `internal/scheduler/user_failure_alarm_test.go` | CREATE | Zwei-Nutzer-Szenarien (AC-1, AC-2, AC-3): Fehlerserie löst genau einen Alarm aus, weitere Fehler kein zusätzlicher, Recovery, erneuter Alarm nach erneuter Serie, unterbrochene Serie kein Alarm |
| `internal/scheduler/user_partial_and_persistence_test.go` | CREATE | Teilerfolgsschwelle (AC-4), Neustart-Persistenz und defekte Zustandsdatei (AC-5), Pruning gelöschter Nutzer + Testkonto-Ausschluss (AC-7), nebenläufiges Schreiben zweier Fan-out-Jobs in denselben Zustand ohne Zählerverlust, `-race`-Lauf (AC-10) |
| `internal/scheduler/scheduler_status_privacy_test.go` | CREATE | Öffentlicher Status enthält nach einem Fehler — auch nach einem Transportfehler/geschlossener Verbindung, nicht nur HTTP 500 — keine Nutzerkennung (AC-6, AC-9); `users`-Aggregat erscheint in beiden `Status()`-Zweigen |
| `internal/scheduler/*_test.go` | MODIFY (ggf.) | Nur falls ein bestehender Test den vollen `?user_id=`-Fehlertext exakt erwartet (Grep vor Implementierung ergab aktuell keinen solchen Test — Sicherheitsnetz für die Redaktionsänderung) |
| `docs/reference/api_contract.md` | MODIFY | §12 Scheduler-Status: neues optionales `jobs[].users{total,failing,partial}`-Feld dokumentieren; `jobs[].last_run.error` enthält ab dieser Scheibe keine `user_id` mehr |
| `docs/specs/modules/scheduler_multi_user.md` | MODIFY | Reiner Querverweis-Zusatz („Pro-Nutzer-Sichtbarkeit s. Scheibe A von #2149"), keine inhaltliche Änderung an der dort getroffenen Sequenziell-Entscheidung |

### Estimated Changes

- Files: ~6-8 (Code 2, Tests 3-4, Doku 2)
- LoC: s. „LoC-Einschätzung"

## LoC-Einschätzung

| Datei | ~LoC (added, netto grob) |
|---|---|
| `internal/scheduler/scheduler.go` (Redaktion an der Fehler-Konstruktionsstelle, `Record`/`Prune`-Aufrufe in `runForAllUsers`, `userState`-Feld + Laden in `New()`, `users`-Aggregat in beiden `Status()`-Zweigen) | 90-130 |
| `internal/scheduler/user_run_state.go` (Typen, `Record`/`Prune`/`Aggregate`, eigener Mutex, atomares Laden/Schreiben, Schwellen-Konstanten) | 160-200 |
| `internal/scheduler/user_failure_alarm_test.go` (AC-1, AC-2, AC-3) | 110-140 |
| `internal/scheduler/user_partial_and_persistence_test.go` (AC-4, AC-5, AC-7, AC-10 — vier Szenarien, table-driven wo möglich) | 180-220 |
| `internal/scheduler/scheduler_status_privacy_test.go` (AC-6, AC-9, `users`-Aggregat in beiden `Status()`-Zweigen) | 90-120 |

Summe grob **630-810 added** (Code + Tests). Das übersteigt den bereits
gesetzten `loc_limit_override 500` voraussichtlich deutlich — abweichend
von der ursprünglichen Grobschätzung (~300-400) im Auftrag zu dieser Spec.
**Vor `/50-implement`** ist der tatsächliche Bedarf zu prüfen und der
Override bei Bedarf anzuheben (`workflow.py set-field loc_limit_override
800`). **Nicht akzeptabel als Ausweg:** eine der drei Testdateien
verkleinern, indem sie weniger der zehn Acceptance Criteria abdeckt —
zulässig ist ausschließlich weitere Verdichtung über table-driven Tests
(mehrere Unterfälle in einer Testfunktion), analog zum Vorgehen in
`fix_1447_s2a_scheduler_ueberlappung_teilerfolg.md`.

## Implementation Details

### 1. Buchung je (Job, Nutzer)

Die Buchung greift **innerhalb** der bestehenden Schleife in
`runForAllUsers` (`:237-288`), an genau der Stelle, wo `err :=
s.triggerEndpointForUser(path, uid)` bereits in ok/partial/error
klassifiziert wird — die Klassifikation selbst (`errors.As(*partialRunError)`)
bleibt unverändert, es kommt lediglich ein zusätzlicher Aufruf
`s.userState.Record(jobID, uid, outcome, errText)` je Iteration hinzu.
Daraus folgt automatisch, ohne Sonderbehandlung:

- **Keine Buchung**, wenn `store.ListUserIDs()` fehlschlägt (`:239`, früher
  Return) oder `len(userIDs) == 0` ist (`:256`, früher Return) — beide Fälle
  verlassen die Funktion, bevor die Schleife je betreten wird.
- **Ein Overlap-Skip des gesamten Jobs bucht nichts je Nutzer:** Ist die
  Job-Sperre aus #1447 S2a belegt, kehrt `recordRun` zurück, ohne `fn()` —
  und damit `runForAllUsers` — überhaupt aufzurufen (`:555-570`). Die
  Pro-Nutzer-Buchführung greift ausschließlich bei tatsächlich
  ausgeführten Läufen.
- **Pruning-Basis ist die bereits gefilterte `userIDs`-Liste** (`:250`, nach
  Abzug der Testkonten über `model.IsTestUserID`), nicht `allUserIDs` — ein
  Aufruf `s.userState.Prune(jobID, userIDs)` am Ende von `runForAllUsers`
  entfernt damit in einem Schritt sowohl gelöschte Konten als auch jedes
  potenziell geleakte Testkonto aus dem Zustand.
- Testkonten werden nie gebucht, weil sie die Schleife nie erreichen
  (bestehender Skip bei `:246-249`).
- Betroffen sind automatisch alle **sieben** Jobs, die über
  `runForAllUsers` laufen (durch vollständiges Durchlesen aller Aufrufstellen
  in `scheduler.go` verifiziert): `trip_reports_hourly` (`:337`),
  `alert_checks` (`:371`), `radar_alert_checks` (`:377`),
  `compare_alert_checks` (`:384`), `compare_radar_alert_checks` (`:392`),
  `compare_official_alert_checks` (`:401`), `compare_presets_daily` (`:525`).
  Die drei globalen Jobs (`inbound_command_poll`, `data_write_selftest`,
  `premium_sms_poll`) laufen über `triggerGlobalEndpoint`/eine eigene
  Funktion ohne Nutzer-Fan-out und bleiben unberührt.

Zählerregel (Tech-Lead-Entscheidung, aus den Kernbefunden der Analyse):

| Ergebnis | `ConsecutiveFailures` | `ConsecutivePartial` |
|---|---|---|
| `ok` | → 0 | → 0 |
| `error` | +1 | → 0 |
| `partial` | unverändert | +1 |

Begründung für „`partial` lässt `ConsecutiveFailures` unverändert": ein
Teilerfolg ist kein Beweis für Erholung von einer laufenden Fehlerserie
(z. B. Timeout mitten in einer Ausfallphase), aber auch kein zusätzlicher
harter Fehler — er darf die Fehlerserie weder verlängern noch abbrechen.

**Zwei Bedeutungen von `partial`**, beide fließen in `ConsecutivePartial`
ein, aber mit unterschiedlicher fachlicher Bedeutung (Messbefund aus der
Analyse): (a) #1912-Transport-Timeout — „Python hat vermutlich fertig
gearbeitet", der Go-Client wartete nur nicht lang genug; (b)
Python-Deadline (`trip_alert.py:866-869`) — die Trip-Schleife eines Nutzers
bricht mitten im Tick ab, restliche Trips dieses Nutzers bleiben in diesem
Tick **ungeprüft**. Die gemessenen 89 Deadline-Treffer in 14 Tagen beim
PO-Konto zeigen, dass (b) die real relevante, chronische
Einzelnutzer-Degradation ist. Die höhere Schwelle (8 statt z. B. 3) trägt
dem Rechnung: einzelne Treffer sind Normalbetrieb (89/14 Tage ≈ 6-7/Tag bei
96 Ticks/Tag, meist isoliert), eine **lange ununterbrochene Serie** bedeutet
dagegen, dass Trips dieses Nutzers wiederholt in Folge nicht geprüft wurden.

### 2. Alarm-Flanke je (Job, Nutzer)

Zustand pro `(jobID, userID)` trägt zusätzlich zwei Merker
(`FailureAlertSent`, `PartialAlertSent`), damit die Flanke — nicht der
Schwellenwert selbst — den Versand auslöst:

- `ConsecutiveFailures` erreicht **3** und `FailureAlertSent == false` →
  genau **eine** MQ-Nachricht über `s.notifier` (Sender `gregor`, Empfänger
  `infra`, Priorität `high`, analog zum bestehenden Muster in
  `tripReports()`), danach `FailureAlertSent = true`. Betreff nennt den
  Job, Text nennt Job, die **echte** `userID` und den zuletzt verbuchten
  Fehlertext aus `LastError`.
- `ConsecutivePartial` erreicht **8** (= 2 h beim 15-Minuten-Takt, 8 h beim
  Stundentakt) und `PartialAlertSent == false` → genau **eine**
  MQ-Nachricht Priorität `normal` („Nutzer-Läufe wiederholt unvollständig"),
  danach `PartialAlertSent = true`.
- Der erste `ok`-Lauf nach einem gesendeten Alarm (`FailureAlertSent ||
  PartialAlertSent`) löst genau **eine** Recovery-Nachricht (Priorität
  `normal`) aus und setzt beide Merker zurück. Ein `partial` nach einem
  Fehler-Alarm gilt **nicht** als Erholung (`ConsecutiveFailures` bleibt ja
  laut Zählerregel unverändert stehen, `FailureAlertSent` bleibt `true`,
  keine Recovery).
- **Bündelung je Job-Lauf (gegen Telegram-Lärm):** Alle Flanken, die
  innerhalb **eines** Laufs von `runForAllUsers` für denselben Job
  entstehen, werden am Ende dieses Laufs zu **höchstens einer Nachricht je
  Art** zusammengefasst (Fehler-Alarm `high`, Teilerfolg-Hinweis `normal`,
  Entwarnung `normal`), die alle betroffenen Nutzer auflistet. Scheitern bei
  einem Kernausfall alle 3 Nutzer eines Jobs gleichzeitig zum dritten Mal,
  entsteht so eine Nachricht für diesen Job statt drei.
- Der bestehende aggregierte Alarm in `tripReports()` (Issue #1346,
  Totalausfall, Flanke über `lastHardStatus`) bleibt **unverändert und
  unabhängig** vom neuen Pro-Nutzer-Alarm — beide Mechanismen laufen
  nebeneinander (s. „Known Limitations" zur Konsequenz bei einem
  Totalausfall).

**Woher die Nutzeridentität stammt (wichtig für Abschnitt 3):** Die
Redaktion aus Abschnitt 3 gilt **einheitlich** für jeden Fehlertext, der die
Konstruktionsstelle `triggerEndpointForUser` verlässt — es gibt ab dieser
Scheibe **keinen** zweiten, unredigierten Fehlertext irgendwo im System.
`LastError` speichert damit den bereits redigierten Text; das ist
ausreichend, weil die Nutzeridentität nie aus dem Fehlertext geparst werden
muss: Sie liegt an jeder Verwendungsstelle ohnehin separat vor — als
`uid`-Schleifenvariable in den bestehenden Log-Zeilen (`:272`, `:278`), als
`userID`-Parameter der MQ-Nachricht und als Map-Schlüssel im Zustand selbst.

### 3. Redaktion des öffentlichen Fehlertexts (an der Konstruktionsstelle)

`jobResult.Error` (gefüllt in `recordRun:591-595` aus `err.Error()`) fließt
unverändert in `/api/scheduler/status` → `jobs[].last_run.error` — ein
Endpoint, der **ohne Anmeldung** erreichbar ist
(`internal/middleware/auth.go:50`) und auf der Account-Seite **jedem**
angemeldeten Nutzer angezeigt wird. `triggerEndpointForUser` baut heute an
vier Stellen einen Fehlertext, der `?user_id=<id>` einbettet (`:626`
Timeout, `:630` sonstiger Transportfehler, `:647` `failed`-Antwort, `:657`
`partial`-Antwort); alle vier werden auf den `path` ohne Query umgestellt.

**Wichtig, weil sonst die Redaktion nur scheinbar greift:** `err` in `:626`
und `:630` stammt aus `s.client.Post(url, ...)` und ist ein `*url.Error`.
Dessen `Error()`-Text enthält **immer** die vollständige angefragte URL
inklusive `?user_id=<id>` (Format `Post "<url>": <ursache>`) — ein reines
Weglassen von `userID` im umgebenden `fmt.Sprintf`/`fmt.Errorf` reicht
**nicht**, weil `%v`/`%w` den vollen `err.Error()`-Text einbettet. Deshalb
wird für den **Meldungstext** stattdessen `errors.Unwrap(err)` verwendet,
das bei `*url.Error` die innere Ursache **ohne** URL liefert (z. B. `dial
tcp 127.0.0.1:8000: connect: connection refused`); liefert `errors.Unwrap`
`nil`, wird `err` selbst als Fallback verwendet. Das ist genau der Fall,
den ein reiner HTTP-500-Test **nicht** aufdeckt — der eigentliche
Leck-Kandidat ist ein **abgelehnter/geschlossener Port**
(Verbindungsverweigerung), nicht ein HTTP-Fehlerstatus. AC-9 und der
zugehörige Test prüfen deshalb explizit diesen Transportfehler-Fall.

**Der Unwrap gilt NUR für den Meldungstext, nicht für die Fehlerkette:**
Bei der Timeout-Variante (`:626`) bleibt `wrapped: err` unverändert das
**originale, volle** `err` — der Kommentar an `partialRunError.wrapped`
(`:55-58`) besteht genau deshalb, damit #1912s `errors.As`/`errors.Is`-
Traversal weiterhin sowohl „ist Timeout" (`net.Error`) als auch „ist
partial" (`*partialRunError`) am selben zurückgegebenen Fehler feststellen
kann. Nur `msg` wird aus der entpackten Ursache gebaut:

```go
if isTimeoutTransportError(err) {
    cause := errors.Unwrap(err)
    if cause == nil {
        cause = err
    }
    return &partialRunError{
        msg:     fmt.Sprintf("%s timed out: %v", path, cause),
        wrapped: err, // unveraendert: volle Kette fuer #1912 errors.As
    }
}
```

Bei `:630` (kein `*partialRunError`, sondern ein gewöhnlicher, hart
klassifizierter Fehler) gibt es keine `wrapped`-Kette zu erhalten — kein
Aufrufer prüft diesen Zweig per `errors.As` auf einen bestimmten Typ, er
landet ohnehin immer im Hart-Fehler-Zweig von `runForAllUsers`:

```go
cause := errors.Unwrap(err)
if cause == nil {
    cause = err
}
return fmt.Errorf("%s: transport error: %v", path, cause)
```

Die pro-Nutzer-Log-Zeilen (`:272`, `:278`, unverändert) bleiben **voll
detailliert**, weil sie `uid` bereits separat als Format-Parameter
mitgeben — sie verlieren durch die Redaktion des Fehlertexts keine
Information, die für den Betrieb relevant wäre.

### 4. Nutzerreferenz in der MQ-Nachricht (bewusst NICHT redigiert)

Die MQ geht an `infra`/den PO — ein interner Betriebskanal, kein öffentlich
erreichbarer Endpoint. Die CLAUDE.md-Regel „keine Secrets/Credentials in
MQ-Nachrichten" verbietet keine Nutzerkennungen; der Betreiber muss den
betroffenen Account identifizieren können, um ihn zu prüfen. Entscheidung:
Die MQ-Nachricht referenziert die **echte** `userID` (aus der
Schleifenvariable, nicht aus einem geparsten Fehlertext — sie ist an der
Aufrufstelle ohnehin bereits bekannt, s. Abschnitt 2). Das ist eine
bewusste Ausnahme vom öffentlichen Redaktionsprinzip aus Abschnitt 3, die
den `LastError`-Text selbst nicht betrifft (der bleibt redigiert, auch in
der MQ-Nachricht — nur die `userID` daneben ist Klartext).

### 5. `Status()`-Aggregat, kein Nutzerbezug

Je Fan-out-Job (die sieben aus Abschnitt 1) liefert `Status()` zusätzlich
ein optionales Feld:

```json
"users": {"total": 3, "failing": 1, "partial": 0}
```

`failing` = Anzahl Nutzer mit `ConsecutiveFailures >= 1`, `partial` =
Anzahl Nutzer mit `ConsecutivePartial >= 1` — **nur Zahlen, keine IDs**.
Analog zum `overlap`-Feld aus #1447 S2a fehlt das Feld vollständig, wenn der
Job kein Fan-out-Job ist (die drei globalen Jobs) — fehlendes Feld bedeutet
„nicht anwendbar", nicht „alles ok". Weil `trip_reports_hourly` und
`compare_presets_daily` **ausschließlich** im `subs`-Expansionszweig von
`Status()` erscheinen (`:774-798`), nicht im Hauptzweig (`:802-819`) — genau
die Falle, die die #1447-Spec bereits für das `overlap`-Feld dokumentiert
hat —, muss das `users`-Aggregat über einen gemeinsamen Helfer (analog
`overlapField`) in **beiden** Zweigen eingehängt werden. Bestehende Felder
(`id`, `name`, `next_run`, `last_run`, `overlap`) und die Zeilenanzahl (10
Jobs) bleiben unverändert. Consumer sind neben
`/home/hem/henemm-infra/scripts/check-gregor20.sh` auch
`frontend/src/routes/account/+page.svelte` und
`frontend/src/lib/types.ts:576` (Account-Seite) — beide parsen `jobs[]` und
dürfen durch das neue, optionale `users`-Feld nicht brechen.
`check-gregor20.sh` wird in dieser Scheibe **nicht** geändert — das
Aggregat ist informativ, der Alarmweg bleibt die MQ-Nachricht.

### 6. Zustandstyp und Persistenz, nebenläufigkeitssicher

`internal/scheduler/user_run_state.go` definiert einen eigenständigen
Zustandstyp mit **eigenem** `sync.Mutex` (getrennt von `s.mu`, analog zur
bestehenden Trennung `jobLocksMu`/`onceMissingHBmu`/`s.mu`):

```go
type userJobRecord struct {
    LastRun             time.Time `json:"last_run"`
    LastStatus          string    `json:"last_status"` // ok|partial|error
    LastError           string    `json:"last_error,omitempty"` // bereits redigiert
    ConsecutiveFailures int       `json:"consecutive_failures"`
    ConsecutivePartial  int       `json:"consecutive_partial"`
    FailureAlertSent    bool      `json:"failure_alert_sent"`
    PartialAlertSent    bool      `json:"partial_alert_sent"`
}

type userRunState struct {
    mu    sync.Mutex
    path  string
    state map[string]map[string]*userJobRecord // [jobID][userID]
}
```

**Grund für einen eigenen Mutex statt Wiederverwendung von `s.mu`:** Von
den sieben Fan-out-Jobs laufen drei im `*/15`-Takt (`alert_checks`,
`compare_alert_checks`, `compare_official_alert_checks`), zwei im
Offset-Takt `7,22,37,52` (`radar_alert_checks`, `compare_radar_alert_checks`,
Issue #1628 S0) und zwei stündlich zur vollen Minute über
`briefing_dispatch` (`trip_reports_hourly`, `compare_presets_daily`). Weil
die Overlap-Sperre aus #1447 S2a **je `jobID`**, nicht global greift,
können mehrere dieser Jobs gleichzeitig in denselben Zustand schreiben
wollen — zur vollen Stunde treffen sogar **fünf** Jobs (das `*/15`-Trio
plus das stündliche Paar) in derselben Minute `:00` aufeinander. `Record()`
hält den Mutex für die Dauer von Kartenaktualisierung **und** dem
vollständigen Schreiben der Snapshot-Datei (tmp + `os.Rename`, analog
`store/write.go`, lokal nachgebaut, da `writeFileAtomic` dort unexported
ist) — ein tmp-Datei-Rename verhindert nur einen **zerrissenen
Lesevorgang**, nicht einen **verlorenen Schreibvorgang**, wenn zwei Jobs
nacheinander je einen Voll-Snapshot schreiben, ohne voneinander zu wissen:
ohne gemeinsamen Mutex würde der zuletzt schreibende Job die Zähler des
anderen im selben Tick überschreiben. Der Aufruf von `s.notifier(...)` für
fällige Alarme geschieht **außerhalb** dieser Sperre (die Methode gibt die
fällige(n) Nachricht(en) als Rückgabewert zurück, der Aufrufer versendet
sie danach) — ein langsamer MQ-Versand darf die anderen, gleichzeitig
laufenden Jobs nicht seriell blockieren. Der CI-`go-test`-Lauf läuft mit
`-race`; ein ungeschützter Zugriff auf die Map käme dort als rotes Ergebnis
zurück, nicht als stille Inkonsistenz.

Laden: fehlende Datei → leerer Zustand (kein Fehler); unlesbare/defekte
Datei → leerer Zustand + eine Log-Zeile, kein Absturz, kein Blockieren des
Scheduler-Starts. Schreibfehler (z. B. Platte voll) → Log-Warnung, der
gerade gelaufene Job gilt trotzdem als durchgeführt (der In-Memory-Zustand
ist bereits aktualisiert, nur die Persistenz schlug fehl — s. „Known
Limitations").

**Ablageort — außerhalb `users/`:** `filepath.Join(store.DataDir,
"scheduler_user_state.json")`, also **Geschwisterdatei** von `users/`, nicht
darunter. `store.ListUserIDs()` (`internal/store/user.go:19-43`) verlangt
zwingend ein **Verzeichnis** mit `user.json` darin (`e.IsDir()` +
`os.Stat(userJSON)`) — eine Datei direkt unter `DataDir` kann dort
strukturell nie als Nutzer auftauchen, auch wenn sie versehentlich unter
`users/` läge. Die Ablage außerhalb ist trotzdem die gewählte, robustere
Variante, weil sie diese Prüfung erst gar nicht nötig macht.

## Expected Behavior

- **Input:** unverändert — dieselben Cron-Ticks, dieselben
  `triggerEndpointForUser`-Aufrufe je Nutzer.
- **Output (`/api/scheduler/status`), neu:**
  - `jobs[].users{total,failing,partial}` bei den sieben Fan-out-Jobs,
    fehlend bei den drei globalen Jobs.
  - `jobs[].last_run.error` enthält ab dieser Scheibe **keine** `user_id`
    mehr, auch nicht bei Transportfehlern.
- **Output (MQ, neu):** bis zu eine Fehler-Alarm-Nachricht, eine
  Teilerfolg-Alarm-Nachricht und eine Recovery-Nachricht je `(jobID,
  userID)`-Flanke — mit echter `userID` im Text, redigiertem Fehlertext.
- **Side effects:** neue Datei `scheduler_user_state.json` im
  Datenverzeichnis (Geschwisterdatei von `users/`); bestehende Log-Zeilen
  bleiben in voller Detailtiefe unverändert — nur der öffentlich exponierte
  `last_run.error`-Text ist redigiert.
- **Unverändert:** Rangfolge `error > partial > ok` je Job-Lauf,
  `tripReports()`-Alarm (#1346), Overlap-Mechanik (#1447 S2a), Timeout-Wert
  und -Klassifikation (#1912).

## Test-Plan

Kein Mock-Theater, keine Dateiinhalt-Prüfung als Verhaltensnachweis. Package
`scheduler` (Zugriff auf unexportierte Typen), `go` unter
`/usr/local/go/bin`, kein Netz (`httptest.NewServer`), Store über
`t.TempDir()`, `sched.notifier` als Aufzeichner (Slice statt echtem
`notify.SendMQ`).

- **`user_failure_alarm_test.go`**
  - AC-1: zwei Nutzer, B scheitert 3× in Folge über `httptest`-Server, der
    nach `user_id`-Query-Parameter unterscheidet; A bleibt `ok`. Nach dem
    dritten Fehler genau ein aufgezeichneter `notifier`-Aufruf, Text
    referenziert B, nicht A; A hat `ConsecutiveFailures == 0`.
  - AC-2: 4. und 5. Fehler von B → `notifier`-Aufrufzähler bleibt bei 1;
    danach `ok` → genau ein zweiter Aufruf (Recovery); danach erneut 3
    Fehler → genau ein dritter Aufruf (neuer Alarm).
  - AC-3: 2 Fehler, `ok`, 2 Fehler → `notifier` wird nie aufgerufen
    (`ConsecutiveFailures` erreicht nie 3 am Stück).
- **`user_partial_and_persistence_test.go`**
  - AC-4: 8 `partial`-Antworten in Folge → genau ein `notifier`-Aufruf
    Priorität `normal`; separates Szenario mit 7 `partial` + `ok` → kein
    Aufruf.
  - AC-5: Zwei `*Scheduler`-Instanzen über denselben `t.TempDir()`-Pfad —
    erste verbucht 2 Fehler und wird verworfen (simuliert Neustart), zweite
    lädt den Zustand beim Aufbau und verbucht den 3. Fehler → Alarm feuert
    trotzdem. Zweites Unterszenario: Zustandsdatei mit ungültigem JSON
    vorab geschrieben → `New()` läuft ohne Fehler, Zustand ist leer, der
    nächste Job-Lauf verbucht normal.
  - AC-7: Nutzer aus `userIDs`-Liste entfernt (Store ohne dessen
    `user.json`) → nach dem nächsten Lauf des Jobs ist sein Eintrag im
    Zustand weg; ein Testkonto (`model.IsTestUserID`) taucht nie im Zustand
    auf, auch nicht nach einem Lauf.
  - AC-10: zwei verschiedene `jobID`s (z. B. `alert_checks` und
    `compare_alert_checks`) rufen `Record()` echt nebenläufig für
    verschiedene Nutzer auf (Goroutinen + `sync.WaitGroup`, kein
    `time.Sleep`); nach Abschluss beider sind **beide** Zähler in der
    persistierten Datei vorhanden und korrekt — Lauf mit `go test -race`.
- **`scheduler_status_privacy_test.go`**
  - AC-6: `httptest`-Server liefert für einen Nutzer HTTP 500 → geprüft,
    dass `Status()`-JSON an **keiner** Stelle die betroffene `userID`
    enthält, `users.failing == 1`.
  - AC-9: `httptest`-Server wird nach dem ersten Request **geschlossen**
    (`server.Close()`), sodass der nächste `client.Post` auf eine
    verweigerte Verbindung trifft (Transportfehler, kein HTTP-Statuscode) —
    `Status()`-JSON enthält auch dann keine `userID` im Fehlertext. Dieser
    Test ist bewusst **nicht** durch einen HTTP-500-Fall ersetzbar, weil er
    genau die in Abschnitt 3 beschriebene `*url.Error`-Falle prüft.
  - `users`-Aggregat wird für `trip_reports_hourly` (subs-Zweig) **und**
    `alert_checks` (Hauptzweig) geprüft — Regressionsschutz gegen die
    #1447-`overlap`-Falle, hier auf `users` übertragen.
- **AC-8 (Regression):** bestehende Tests zu #1912
  (`timeout_kein_ausfall_test.go`), #1447 S2a (`job_overlap_test.go`,
  `job_status_partial_test.go`) und #1346 (Alarm-Test in
  `scheduler_unify_test.go` bzw. verwandte Dateien) bleiben ohne inhaltliche
  Anpassung grün. Nur falls ein Test den vollen `?user_id=`-Fehlertext exakt
  erwartet, wird er in `internal/scheduler/*_test.go` minimal angepasst
  (Grep vor Implementierungsstart ergab aktuell keinen solchen Treffer).

## Acceptance Criteria

- **AC-1:** Given zwei verschiedene Nutzer A und B nutzen denselben Job /
  When B dreimal in Folge mit einem echten Fehler scheitert und A dabei
  durchgehend erfolgreich bleibt / Then wird genau ein Alarm ausgelöst, der
  B betrifft, während A weder einen Alarm noch eine Zählerveränderung
  erhält.
  - Test: `user_failure_alarm_test.go`, Szenario Zwei-Nutzer-Isolation.

- **AC-2:** Given B hat bereits einen Fehler-Alarm ausgelöst / When B ein
  viertes und fünftes Mal in Folge scheitert / Then wird kein weiterer
  Alarm gesendet, und nach dem darauffolgenden ersten Erfolg wird genau
  eine Entwarnung gesendet, bevor eine erneute Serie von 3 Fehlern wieder
  einen neuen Alarm auslöst.
  - Test: `user_failure_alarm_test.go`, Szenario Flanke ohne Dauerfeuer.

- **AC-3:** Given ein Nutzer hat 2 Fehler in Folge, dann einen Erfolg, dann
  wieder 2 Fehler in Folge / When die Fehlerserie dadurch nie 3 am Stück
  erreicht / Then wird zu keinem Zeitpunkt ein Alarm ausgelöst.
  - Test: `user_failure_alarm_test.go`, Szenario unterbrochene Serie.

- **AC-4:** Given ein Nutzer meldet achtmal in Folge einen Teilerfolg
  (`partial`) / When die Schwelle von 8 erreicht wird / Then wird genau
  eine Nachricht mit Priorität `normal` gesendet; bei nur 7 Teilerfolgen
  gefolgt von einem Erfolg wird keine Nachricht gesendet.
  - Test: `user_partial_and_persistence_test.go`, Szenario Teilerfolgsschwelle.

- **AC-5:** Given ein Nutzer hat bereits 2 Fehler in Folge gebucht, und der
  Go-Prozess wird danach neu gestartet / When der dritte Fehler nach dem
  Neustart eintritt / Then löst er trotzdem den Alarm aus, weil der Zustand
  aus der persistierten Datei geladen wurde; ist die Zustandsdatei defekt,
  läuft der nächste Job dennoch fehlerfrei mit leerem Zustand.
  - Test: `user_partial_and_persistence_test.go`, Szenarien Neustart und
    defekte Datei.

- **AC-6:** Given ein Nutzer scheitert dreimal in Folge und löst einen
  Alarm aus / When der öffentliche `/api/scheduler/status`-Endpoint danach
  abgefragt wird / Then enthält die Antwort an keiner Stelle die
  Kennung dieses oder eines anderen Nutzers, während das Aggregat
  `failing: 1` für den betroffenen Job zeigt.
  - Test: `scheduler_status_privacy_test.go`, Szenario HTTP-500.

- **AC-7:** Given ein Nutzer wird gelöscht (verschwindet aus der
  Nutzerliste) / When der betroffene Job das nächste Mal läuft / Then wird
  sein Eintrag aus dem persistierten Zustand entfernt; ein Testkonto wird
  zu keinem Zeitpunkt im Zustand geführt.
  - Test: `user_partial_and_persistence_test.go`, Szenarien Pruning und
    Testkonto-Ausschluss.

- **AC-8:** Given die bestehenden Mechanismen aus #1912 (Timeout-Klassifikation),
  #1447 S2a (Overlap-Sperre, Rangfolge `error > partial > ok`) und #1346
  (aggregierter Totalausfall-Alarm) / When die neue Pro-Nutzer-Buchführung
  zusätzlich eingeführt wird / Then bleiben Rangfolge, `overlap`-Feld und
  der aggregierte #1346-Alarm in Verhalten und Ausgabe unverändert
  nachweisbar identisch zum Stand vor dieser Scheibe.
  - Test: bestehende Testdateien (Regressionslauf) bleiben ohne inhaltliche
    Anpassung grün; Ausnahme: minimale Textanpassung bei exaktem
    `?user_id=`-Abgleich, falls im Grep-Vorlauf doch gefunden.

- **AC-9:** Given ein Nutzer scheitert an einem Transportfehler
  (verweigerte/geschlossene Verbindung), nicht an einem HTTP-Fehlerstatus /
  When der öffentliche Status danach abgefragt wird / Then enthält auch
  dieser Fehlertext keine Nutzerkennung, obwohl die zugrundeliegende
  `*url.Error`-Meldung die volle angefragte URL einschließlich `user_id`
  trägt.
  - Test: `scheduler_status_privacy_test.go`, Szenario geschlossener Server.

- **AC-10:** Given zwei unterschiedliche Fan-out-Jobs laufen gleichzeitig
  und schreiben beide in denselben Zustandsspeicher / When beide nahezu
  zeitgleich ihre Ergebnisse verbuchen / Then gehen die Zähler keines der
  beiden Jobs verloren, und ein Testlauf mit `-race` meldet keinen
  Datenrennen-Befund.
  - Test: `user_partial_and_persistence_test.go`, Szenario nebenläufiges
    Schreiben.

- **AC-11:** Given zwei verschiedene Nutzer A und B desselben Jobs scheitern
  beide im selben Lauf zum dritten Mal in Folge / When dieser Lauf endet /
  Then wird für diesen Job genau eine Fehler-Alarm-Nachricht gesendet, die
  beide Nutzer nennt, und nach dem nächsten erfolgreichen Lauf beider genau
  eine gemeinsame Entwarnung.
  - Test: `user_failure_alarm_test.go`, Szenario Bündelung je Job-Lauf.

## Known Limitations

- **Chronische Teilerfolge unterhalb der Schwelle bleiben unalarmiert.**
  Erst ab 8 Teilerfolgen in Folge wird gemeldet; einzelne, isoliert
  auftretende ungeprüfte Trips (der überwiegende Teil der gemessenen 89
  Deadline-Treffer in 14 Tagen) lösen bewusst keinen Alarm aus, um
  Telegram-Lärm zu vermeiden.
- **Ein hängender Nutzer blockiert weiterhin alle anderen** — das
  Zeitbudget je Nutzer ist ausdrücklich Scheibe B, nicht Teil dieser
  Spezifikation.
- **Kein authentifizierter Einzelstatus für den Nutzer selbst.** Diese
  Scheibe liefert keinen angemeldeten Endpoint, über den ein Nutzer seinen
  eigenen Job-Status einsehen könnte — nur das anonyme Aggregat ist
  öffentlich, der volle Datensatz nur intern (MQ, Datei).
- **Stundentakt bedeutet bis zu 3 Stunden bis zum Alarm** bei
  `trip_reports_hourly`/`compare_presets_daily` (3 Fehler à 1 h), während
  bei den `*/15`-Jobs derselbe Schwellenwert bereits nach 45 Minuten greift.
- **Doppelte Alarmierung bei einem echten Totalausfall möglich.** Scheitern
  bei einem kompletten Kernausfall alle Nutzer gleichzeitig, feuert der
  bestehende aggregierte #1346-Alarm bereits beim ersten Tick, während der
  neue Pro-Nutzer-Alarm für jeden einzelnen betroffenen Nutzer erst beim
  dritten Fehler in Folge auslöst. Dank Bündelung je Job-Lauf (Abschnitt 2)
  entsteht dabei höchstens eine Nachricht je Fan-out-Job (bis zu 7 Jobs,
  zeitlich verteilt), nicht eine je Nutzer. Eine Entprellung über Jobs
  hinweg ist bewusst nicht Teil dieser Scheibe.
- **Ein Schreibfehler der Zustandsdatei verliert die Persistenz dieses
  Ticks stillschweigend** (nur Log-Warnung) — der In-Memory-Zustand bleibt
  in diesem Prozesslauf zwar korrekt, aber ein anschließender Neustart
  würde auf den letzten erfolgreich geschriebenen Stand zurückfallen.
  Wiederholte Schreibfehler (z. B. volle Platte) könnten so eine laufende
  Fehlerserie über einen Neustart hinweg verdecken — dasselbe Restrisiko,
  das auch für `lastRuns`/`overlapState` bereits ohne Persistenz gilt,
  hier jedoch mit dem zusätzlichen Unterschied, dass die Persistenz bei
  Erfolg tatsächlich vorhanden ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (ADR-0038 trägt diese Scheibe bereits)
- **Rationale:** ADR-0038 hat den Grundsatz „job-eigene Beobachtbarkeit
  unter Aufrufer-Wartezeit" bereits festgehalten; Fix #1447 S2a hat daraus
  bereits das Muster „eigener, danebenliegender Zustand mit eigenem
  Zeitstempel/Zähler, getrennt vom Haupt-Zustand" abgeleitet
  (`overlapState`). Diese Scheibe wendet exakt dasselbe Muster auf die
  zusätzliche Dimension `userID` an — eine Erweiterung der Granularität,
  keine neue Grundsatzentscheidung. Die Entscheidungen dieser Scheibe (ein
  eigener Mutex statt Wiederverwendung von `s.mu`, Schwellenwerte 3/8,
  Ablageort außerhalb `users/`, Redaktion am Konstruktionsort unter Erhalt
  der `errors.As`-Kette) sind lokale Implementierungsentscheidungen
  innerhalb eines einzelnen Pakets (`internal/scheduler/`), nicht
  system-übergreifend oder schwer umkehrbar im Sinne der ADR-Faustregeln
  (`docs/adr/README.md`). Die in „Out of Scope" benannte
  Parallelisierungsfrage (Scheibe B) bleibt ausdrücklich ADR-pflichtig,
  sobald sie tatsächlich angegangen wird.

## Changelog

- 2026-09-15: Initial spec created (Scheibe A von Issue #2149)
