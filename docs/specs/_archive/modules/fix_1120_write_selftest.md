---
entity_id: fix_1120_write_selftest
type: bugfix
created: 2026-07-08
updated: 2026-07-08
status: draft
workflow: fix-1120-write-selftest
---

# Aktiver Schreib-Selftest fuer data/ (#1120)

## Approval

- [x] Approved (PO, 2026-07-08)

## Purpose

Der Go-Scheduler prueft heute nirgends aktiv, ob `gregor-api` noch in `data/` schreiben kann.
Die Berechtigungs-Regression #1066 (Gruppen-Schreibrecht auf `data/` ging durch einen
`setfacl`-Sweep verloren) blieb deshalb **tagelang unbemerkt** — es gab keinen Check, der
Schreibzugriff aktiv verifizierte, nur Lesezugriff (`/api/health`). Dieser Fix schliesst die
**Monitoring-Luecke**: ein neuer periodischer Cron-Job prueft alle 15 Minuten non-destruktiv, ob
die vorhandenen Trip-Dateien noch schreibbar sind, und meldet eine Regression aktiv statt sie
per Zufall aufzudecken.

## Source

- **File:** `internal/scheduler/scheduler.go`
- **Identifier:** neuer Job `data_write_selftest`, neue Methode `(s *Scheduler) dataWriteSelftest()`
- **File:** `internal/scheduler/selftest.go` (neu)
- **Identifier:** `func probeDataWritable(dataDir string) error`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `os` (Go stdlib) | package | `os.OpenFile(path, os.O_WRONLY, 0)` + `Close()` — non-destruktive Schreibprobe |
| `os.ReadDir` (Go stdlib) | package | error-geprüfte Traversierung `users/` → `users/<id>/trips/` → `*.json` (bewusst KEIN `filepath.Glob` — das verschluckt Verzeichnis-Lesefehler, F001) |
| `internal/scheduler.Scheduler.recordRun` | intern | bestehender Job-Runner (scheduler.go:184) — schreibt `lastRuns[jobID]`, macht Status automatisch unter `/api/scheduler/status` sichtbar |
| `internal/scheduler.Scheduler.notifier` (`Notifier` Typ) | intern | Alerting-Callback, defaultet auf `notify.SendMQ` (scheduler.go:27, 78-80) |
| `internal/notify.SendMQ` | intern | MQ-Versand an `infra` (internal/notify/mq.go:35-78), fail-soft ohne Secret |
| `internal/store.Store.DataDir` | intern | liefert das konfigurierte Datenverzeichnis (Default `data`, Env `GZ_DATA_DIR`) als Traversierungs-Basis |
| `github.com/robfig/cron/v3` | go module | bereits genutzte Cron-Bibliothek, kein neuer Eintrag noetig — nur ein weiterer `jobDef` in der bestehenden `jobs[]`-Tabelle (scheduler.go:91-99) |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `internal/scheduler/scheduler.go` | MODIFY | Neuer Eintrag in `jobs[]` (Cron `*/15 * * * *`), neue Methode `dataWriteSelftest()`, Edge-getriggertes Alerting bei `ok→error` |
| `internal/scheduler/selftest.go` | CREATE | Helper `probeDataWritable(dataDir string) error` — `os.ReadDir`-Traversierung + `O_WRONLY`-Probe pro Datei |
| `internal/scheduler/selftest_test.go` | CREATE | Go-Tests fuer `probeDataWritable` (nicht schreibbar / schreibbar / leer) |
| `internal/scheduler/data_write_selftest_test.go` | CREATE | Go-Test fuer Edge-Alert-Verhalten (`ok→error` einmalig, zweites `error` in Folge kein erneuter Alert) |
| `docs/project/known_issues.md` | MODIFY | Eintrag zu #1120 (aktiver Schreib-Selftest als Gegenmassnahme zu #1066) |

### Estimated Changes
- Files: 5
- LoC: +130/-0 (grobe Schaetzung, reine Additiv-Aenderung, kein bestehender Code wird geloescht)

## Implementation Details

**Probe-Mechanik (`selftest.go`):** `probeDataWritable(dataDir)` traversiert error-geprüft per
`os.ReadDir`: `users/` → pro User-Verzeichnis `users/<id>/trips/` → jede `*.json`-Datei. Jede
Trip-Datei wird mit `os.OpenFile(path, os.O_WRONLY, 0)` geöffnet, gefolgt von sofortigem
`Close()`. Es wird **kein** `O_TRUNC`, **kein** `O_CREATE`, kein Read und kein Write ausgefuehrt —
weder Inhalt noch mtime aendern sich. Dieser Aufruf verlangt kernelseitig dieselbe
Schreibberechtigung (`MAY_WRITE`) wie der reale Schreibpfad `os.WriteFile` in
`internal/store/write.go:13-19` und reproduziert damit das #1066-EACCES identisch, ohne Daten zu
veraendern. Schlaegt das Oeffnen fehl, wird der Pfad in der zurueckgegebenen Fehlermeldung genannt
(interner Server-Pfad, kein Nutzer-Inhalt — es wird nie Dateiinhalt gelesen).

**Bewusst KEIN `filepath.Glob` (F001, im Adversary-Review gefunden):** `filepath.Glob` verschluckt
laut Go-Doku alle Verzeichnis-Lesefehler (liefert nur `ErrBadPattern`). Verliert `users/`,
`users/<id>/` oder `trips/` das Lese-/Traversierungsrecht (plausible Variante des rekursiven
`setfacl -R`-Sweeps aus #1066), würde Glob still eine leere Liste liefern → False `ok`. Die
`os.ReadDir`-Traversierung unterscheidet stattdessen sauber: `fs.ErrNotExist` → kein Fehler (keine
Daten vorhanden, kein False Alarm, AC-3); **jeder andere Lesefehler** (z.B. `EACCES`) → `error`
mit Pfad. Gibt es keine Trip-Dateien, liefert die Funktion `nil`.

**Job-Registrierung (`scheduler.go`):** Ein weiterer Eintrag in der bestehenden `jobs[]`-Tabelle
(scheduler.go:91-99) mit Cron-Ausdruck `*/15 * * * *` (analog `alert_checks`/`radar_alert_checks`)
ruft `s.dataWriteSelftest` auf. Diese Methode folgt dem etablierten Muster der anderen Jobs
(z.B. `alertChecks()`, scheduler.go:152-156): sie ruft `s.recordRun("data_write_selftest", fn)`
auf, wobei `fn` intern `probeDataWritable(s.store.DataDir)` aufruft. Dadurch landet
`status`/`error` automatisch in `lastRuns["data_write_selftest"]` und ist ohne weitere Aenderung
unter `/api/scheduler/status` (auth-frei, scheduler.go:315-348) sichtbar. Der Prozess laeuft in
`gregor-api` als User `claude-gregor` — exakt der Prozess, der bei #1066 versagte.

**Edge-getriggertes Alerting:** Vor dem `recordRun`-Aufruf wird der bisherige Status aus
`s.lastRuns["data_write_selftest"]` gelesen (unter `s.mu`-Lock, analog zum bestehenden Muster in
`comparePresetsDaily()`, scheduler.go:175-180). Nach `recordRun` wird der neue Status verglichen:
nur beim Uebergang `ok→error` (oder erstmaliger Fehler ohne Vorlauf) wird **genau eine**
MQ-Nachricht ueber `s.notifier("gregor", "infra", "high", subject, body)` gesendet — analog zum
bestehenden `warnMissingHeartbeatOnce`-Muster (scheduler.go:287-312), aber bewusst **ohne**
`sync.Once`, da `sync.Once` einen spaeteren Re-Onset im langlebigen Prozess verschlucken wuerde
(einmal gefeuert, nie wieder). Optional wird bei `error→ok` eine Recovery-Notiz mit Prioritaet
`normal` gesendet. Kein BetterStack-Heartbeat (Quota erschoepft, 10 Heartbeats belegt).

## Out of Scope / Was sich nicht aendert

- **Kein voller Write-Roundtrip:** Es wird zu keinem Zeitpunkt Dateiinhalt veraendert, gelesen
  oder neu geschrieben — nur `OpenFile(O_WRONLY)` + `Close`.
- **Keine dedizierte Fixture, kein Cross-Repo-Provisioning:** `henemm-infra` bleibt unberuehrt.
  Geprueft werden ausschliesslich echte, bereits vorhandene Trip-Dateien unter
  `data/users/*/trips/*.json` (PO-Entscheidung Option A).
- **Kein neuer BetterStack-Heartbeat** (Quota erschoepft).
- **Python-Schreibpfad (`loader.save_trip`) ist NICHT Scope** — geprueft wird ausschliesslich der
  Go-API-Schreibpfad, der bei #1066 tatsaechlich versagte.
- **Bestehende Scheduler-Jobs** (`tripReports`, `alertChecks`, `inboundCommands`,
  `comparePresetsDaily`, `radarAlertChecks`) und ihr Verhalten bleiben unveraendert.
- **`/api/health` (proxy.go) wird NICHT geaendert** — Sichtbarkeit laeuft ausschliesslich ueber
  `/api/scheduler/status`.

## Expected Behavior

- **Input:** Cron-Trigger alle 15 Minuten (`*/15 * * * *`), Prozess `gregor-api` als `claude-gregor`
- **Output:** `lastRuns["data_write_selftest"]` mit `status: "ok"` oder `status: "error"` inkl.
  betroffener Pfad(e) im Fehlertext, sichtbar unter `/api/scheduler/status`
- **Side effects:** Bei Uebergang `ok→error` genau eine MQ-Nachricht an `infra` (Prioritaet
  `high`); optional Recovery-Notiz bei `error→ok` (Prioritaet `normal`); keine Aenderung an
  Dateiinhalt oder mtime irgendeiner geprueften Datei

## Test Plan

### Automated Tests (TDD RED)
- [ ] Test 1: GIVEN eine echte temporaere Datei mit `chmod 0444` (fuer den aufrufenden Prozess
  nicht schreibbar) unter einer Test-`dataDir`-Struktur `users/*/trips/*.json` WHEN
  `probeDataWritable(dataDir)` aufgerufen wird THEN liefert die Funktion einen Fehler ungleich
  nil, der den betroffenen Dateipfad enthaelt.
- [ ] Test 2: GIVEN dieselbe Datei ist normal schreibbar (Default-Rechte im Temp-Dir) WHEN
  `probeDataWritable(dataDir)` aufgerufen wird THEN liefert die Funktion `nil`, und weder
  Dateiinhalt noch mtime der Datei haben sich veraendert (echter Vorher/Nachher-Vergleich,
  kein Mock).
- [ ] Test 3: GIVEN ein leeres `dataDir` ohne jede `users/*/trips/*.json`-Datei WHEN
  `probeDataWritable(dataDir)` aufgerufen wird THEN liefert die Funktion `nil` (kein False
  Alarm bei fehlenden Trip-Dateien).
- [ ] Test 4: GIVEN der Job laeuft zweimal hintereinander, erstmals mit Uebergang `ok→error`
  (nicht schreibbare Datei) und danach nochmal mit weiterhin `error` WHEN ein test-lokaler
  Notifier-Recorder (echtes Funktions-Callback, das Aufrufe zaehlt, kein Mock-Framework) als
  `Scheduler.notifier` injiziert wird THEN wird der Notifier genau einmal aufgerufen (beim
  Uebergang), nicht ein zweites Mal beim Folgelauf mit weiterhin `error`.

## Acceptance Criteria

- **AC-1:** Given eine echte, fuer den pruefenden Prozess nicht schreibbare Datei (`chmod 0444`
  bzw. äquivalente ACL) liegt unter `data/users/<user>/trips/<trip>.json` / When der neue Job
  `data_write_selftest` laeuft / Then landet in `/api/scheduler/status` fuer diesen Job
  `status: "error"` mit einer Fehlermeldung, die den betroffenen Dateipfad nennt.
  - Test: Echte Temp-Datei mit `os.Chmod(...,0444)`, echter Job-Lauf ueber `recordRun`, HTTP-Call
    gegen `/api/scheduler/status` prueft `status`+`error`-Feld — kein Mock.

- **AC-2:** Given alle unter `data/users/*/trips/*.json` gefundenen Dateien sind schreibbar /
  When der Job `data_write_selftest` laeuft / Then landet in `/api/scheduler/status`
  `status: "ok"` fuer diesen Job, und keine der geprueften Dateien hat sich inhaltlich oder in
  der mtime veraendert (Vorher/Nachher-Vergleich).
  - Test: Echte Temp-Dateien mit Standard-Rechten, Job-Lauf, Status-Pruefung + Datei-Vergleich
    vor/nach Lauf — kein Dateiinhalt-String-Check, sondern struktureller Vergleich.

- **AC-3:** Given es existieren aktuell keine Trip-Dateien unter `data/users/*/trips/*.json`
  (leeres oder nicht vorhandenes Verzeichnis) / When der Job `data_write_selftest` laeuft / Then
  landet `status: "ok"` in `/api/scheduler/status` — kein False Alarm bei fehlender Population.
  - Test: Job-Lauf gegen leeres Temp-`dataDir`, Status-Pruefung liefert `ok`.

- **AC-4:** Given der Job wechselt von `status: "ok"` zu `status: "error"` (z.B. eine zuvor
  schreibbare Datei wird zwischen zwei Laeufen non-schreibbar gemacht) / When der zweite Lauf
  abschliesst / Then wird genau eine MQ-Nachricht an `infra` mit Prioritaet `high` gesendet, die
  den Job-Namen und den betroffenen Pfad im Nachrichtentext nennt.
  - Test: Test-lokaler Notifier-Recorder (echtes Funktions-Callback statt `notify.SendMQ`) als
    `Scheduler.notifier` injiziert, zwei aufeinanderfolgende Job-Laeufe mit erzwungenem
    `ok→error`-Uebergang, Aufrufanzahl des Recorders geprueft (== 1).

- **AC-5:** Given der Job bleibt ueber mehrere aufeinanderfolgende Laeufe hinweg im
  `status: "error"` (kein erneuter Uebergang) / When ein weiterer Lauf mit unveraendertem
  Fehlerzustand abschliesst / Then wird KEINE weitere MQ-Nachricht gesendet — die Edge-Logik
  feuert ausschliesslich beim Statuswechsel, nicht bei jedem Fehler-Tick (verhindert
  Alert-Flapping bei anhaltendem Ausfall).
  - Test: Drei aufeinanderfolgende Job-Laeufe mit konstant nicht schreibbarer Datei, Notifier-
    Recorder zaehlt weiterhin genau einen Aufruf (aus dem initialen `ok→error`-Uebergang).

- **AC-6:** Given der Job wechselt von `status: "error"` zurueck zu `status: "ok"` (Datei wird
  wieder schreibbar gemacht) / When der Folge-Lauf abschliesst / Then wird optional eine
  Recovery-Notiz mit Prioritaet `normal` gesendet, die Bestandsfunktionalitaet der Jobs
  `tripReports`, `alertChecks`, `inboundCommands`, `comparePresetsDaily`, `radarAlertChecks`
  bleibt dabei vollstaendig unveraendert (kein Regressionsverhalten in bestehenden Jobs).
  - Test: Erzwungener `error→ok`-Uebergang im Notifier-Recorder geprueft; zusaetzlich bestehende
    Scheduler-Tests (`scheduler_test.go` o.ae.) laufen weiterhin gruen ohne Anpassung.

## Known Limitations

- Geprueft werden ausschliesslich Dateien, die zum Pruef-Zeitpunkt bereits unter
  `data/users/*/trips/*.json` existieren. Legt ein Nutzer seinen ersten Trip an, waehrend eine
  Berechtigungs-Regression bereits aktiv ist, faengt der Selftest das erst, sobald mindestens
  eine bestehende Datei betroffen ist — ein reiner Neuanlage-Fehlerfall (`O_CREATE`) wird nicht
  separat geprobt.
- **Fix-Runde 1 (#1120, F001):** Verzeichnis-Lese-/Traversierungsfehler unter `users/`,
  `users/<id>/` bzw. `trips/` (z.B. durch einen rekursiven `setfacl -R`-Sweep, der einer
  Zwischenebene das Leserecht entzieht) werden jetzt aktiv als `error` gemeldet statt still
  uebersehen zu werden. Die urspruengliche Implementierung nutzte `filepath.Glob`, das laut
  Doku Verzeichnis-Lesefehler verschluckt (liefert `err==nil` + leere Treffer-Liste) — dieser
  Blindspot ist mit der Umstellung auf explizite `os.ReadDir`-Traversierung geschlossen.
- Der Selftest deckt ausschliesslich den Go-API-Schreibpfad ab. Ein analoger Python-seitiger
  Schreibpfad (`loader.save_trip`) ist bewusst nicht Teil dieses Fixes.
- Kein BetterStack-Heartbeat fuer diesen Job — Alerting laeuft ausschliesslich ueber MQ an
  `infra` und den Status-Endpoint; externes Polling durch `henemm-infra/check-gregor20.sh` ist
  nicht Teil dieses Fixes und muesste separat via MQ angekuendigt werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additiver, isolierter neuer Scheduler-Job innerhalb der bestehenden
  Job-Architektur (`jobs[]`-Tabelle + `recordRun`-Muster aus `docs/specs/modules/go_scheduler.md`).
  Keine neue Architekturentscheidung, keine neuen Abhaengigkeiten, kein neuer Kommunikationsweg —
  folgt exakt dem etablierten Edge-Alert-Muster (`warnMissingHeartbeatOnce`).

## Changelog

- 2026-07-08: Initial spec created
