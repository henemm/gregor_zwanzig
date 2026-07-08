# Context: fix-1120-write-selftest

## Request Summary
Ein periodischer **Schreib-Selftest** auf `data/`, der eine künftige Berechtigungs-Regression
(wie #1066) **aktiv meldet**, statt sie per Zufall aufzudecken. Der Health-Endpoint prüft heute
nur Lesezugriff; ein tagelanger stiller Schreib-Ausfall blieb unbemerkt.

## Ausgangs-Incident (#1066)
- `gregor-api.service` läuft als User `claude-gregor` und schreibt Trip-JSONs nur über die
  **Gruppen**-Klasse. Ein `setfacl`-Sweep reduzierte `group::` auf `r-x` → jeder Schreibversuch
  auf **bereits existierende** Dateien schlug fehl (`os.WriteFile` mit `O_TRUNC` ignoriert den
  `perm`-Parameter bei existierenden Dateien → bestehende ACL/Mode entscheidet).
- **Konsequenz für den Selftest (KORRIGIERT nach Strategie-Analyse):** Entscheidend ist nicht
  Existenz/Persistenz, sondern der **Owner**. POSIX-ACL-Reihenfolge: `euid == Owner` → `user::`
  entscheidet (fertig); sonst benannter ACL-Eintrag; sonst `group::`. Der #1066-Sweep traf
  `group::`. Der Service (`claude-gregor`) griff auf `hem`-eigene Dateien nur über `group::` zu →
  gesperrt. **Legt der Selftest die Probe-Datei selbst an, gehört sie `claude-gregor` → Zugriff
  über `user::` → blind gegenüber jedem `group::`-Sweep → False Negative.** Die diskriminierende
  Variable ist **ausschließlich der Owner** (fremd vs. eigen), nicht die Existenzdauer.
- **Probe-Mechanik (non-destruktiv):** `os.OpenFile(path, O_WRONLY, 0)` + `Close()` — **kein**
  `O_TRUNC`, **kein** `O_CREATE`. Verlangt kernelseitig identische Schreibberechtigung wie der reale
  `os.WriteFile`-Pfad (`MAY_WRITE`), honoriert ACL/Maske exakt, ändert **weder Inhalt noch mtime**.
  EACCES == #1066. Ein voller Write-Roundtrip ist **nicht** nötig (und würde bei Fremd-Owner am
  Datenrisiko scheitern) — geöffnet-zum-Schreiben-und-wieder-zu reicht als Nachweis.
- **Beide Services laufen als `claude-gregor`** (verifiziert via `systemctl show`). Keiner kann
  `chown` auf `hem` (braucht CAP_CHOWN). Eine dedizierte `hem`-eigene Fixture müsste also **extern
  beim Deploy** (Script läuft als `hem`) provisioniert werden — Cross-Repo-Abhängigkeit
  (`henemm-infra`).

## Related Files
| File | Relevance |
|------|-----------|
| `internal/scheduler/scheduler.go` | Go-Cron (robfig/cron/v3). Job-Tabelle `:91-99`, `recordRun` `:184-201` (füllt `lastRuns`), `Status()` `:315-348`, `pingHeartbeat` `:270-283`, `warnMissingHeartbeatOnce`/`SendMQ` `:287-312`. **Hier fügt sich der neue Job ein.** |
| `cmd/server/main.go:78-82` | Scheduler-Wiring (`scheduler.New(cfg, s)` + `sched.Start()`) — läuft **in `gregor-api`**, also als `claude-gregor`. |
| `internal/store/store.go` | `Store{DataDir,UserID}`, `New`, `WithUser(userId)` (shallow copy, leerer String = No-op → Isolations-Mechanismus). |
| `internal/store/trip.go:94-129` | `SaveTrip()` → schreibt via `writeFileLogged`. `TripsDir` `:14`, `LoadTrip` `:64`. |
| `internal/store/write.go:13-19` | `writeFileLogged(path,data)` — `os.WriteFile(…,0644)`, loggt Schreibfehler serverseitig mit Pfad (#1066-Fix, Commit 50cd548b), gibt außen generischen Fehler. **Zentrale Schreib-Primitive.** |
| `internal/handler/scheduler_status.go` + `internal/router/router.go:193` | `/api/scheduler/status` (auth-frei) — spiegelt jeden Job-`last_run` automatisch, sobald er über `recordRun` läuft. |
| `internal/handler/proxy.go:17-43` | `HealthHandler` — prüft aktuell nur Python-Core-Erreichbarkeit (Read), kein `data/`-Write. Zweiter möglicher Andockpunkt (Sub-Check-Feld). |
| `internal/notify/mq.go:35-78` | `SendMQ(sender,recipient,priority,subject,body)` → `claude-mq` (fail-soft ohne Secret). Alerting-Weg an `infra`. |
| `internal/config/config.go` | Env-Prefix `GZ`; `DataDir` via `GZ_DATA_DIR` (default `data`); Heartbeat-URLs `GZ_HEARTBEAT_*`. |
| `internal/mail/sender.go:41-46` / `src/app/config.py:20-40` | `IsTestUser`/`is_test_user_id` — User-ID mit Substring `test`/`tdd` blockt Mail-Versand automatisch. |

## Existing Patterns
- **Neuer periodischer Job:** Eintrag in `jobs[]` (`scheduler.go:91`) + Methode, die
  `s.recordRun("<jobID>", fn)` aufruft. `fn func() error` — Fehler landet in
  `lastRuns[jobID].Status="error"` und ist sofort unter `/api/scheduler/status` sichtbar.
- **Test-User-Isolation:** `store.WithUser("gregor-test").SaveTrip(...)` schreibt nach
  `data/users/gregor-test/…`, getrennt von echten Nutzern; Mail-Versand automatisch geblockt.
- **Readiness-statt-Liveness (globale Konvention):** Erfolgs-Signal nur bei echtem Schreib-
  Roundtrip-Erfolg. Bei Fehler: **kein** Erfolgssignal, stattdessen Alert.
- **Alerting vorhanden:** `pingHeartbeat` (BetterStack) + `warnMissingHeartbeatOnce`→`SendMQ`
  an `infra`. Aktuell nur `comparePresetsDaily` nutzt Heartbeat.

## Dependencies
- **Upstream:** `store` (Schreiben/Lesen), `notify.SendMQ` (Alert), `robfig/cron`.
- **Downstream:** `/api/scheduler/status` (Observability); optional externes
  `henemm-infra/check-gregor20.sh` (könnte Job-Status pollen — separater Repo, via MQ ankündigen).

## Existing Specs
- `docs/specs/modules/go_scheduler.md` — Scheduler-Spec (Job-Muster, Status).
- `docs/specs/modules/fix_1066_store_write_logging.md` — #1066-Fix.
- `docs/specs/bugfix/heartbeat_url_rotation.md` — Heartbeat/MQ-Muster.

## Analysis

### Type
Bug (Monitoring-Lücke) — additiv, isolierter neuer Scheduler-Job.

### Technischer Ansatz (nach Strategie-Bewertung)
Neuer Go-Cron-Job `data_write_selftest` in `internal/scheduler/scheduler.go` (`*/15`), der:
1. per **`os.OpenFile(O_WRONLY)` + `Close()`** die Schreibbarkeit einer **`hem`-eigenen** Datei
   unter `data/` non-destruktiv prüft (reproduziert #1066-EACCES ohne Datenänderung),
2. das Ergebnis via `recordRun("data_write_selftest", fn)` in `/api/scheduler/status` sichtbar macht,
3. bei **Übergang `ok→error`** (edge-getriggert, kein `sync.Once`) `SendMQ("gregor","infra",…)` sendet.

### Gewählter Ansatz (PO-Entscheidung 2026-07-08): Option A — echte Touren-Dateien überwachen
Der Job enumeriert vorhandene `data/users/*/trips/*.json` und prüft jede non-destruktiv auf
Schreibbarkeit (`O_WRONLY`-Open + `Close`, kein Read/Write/mtime-Change). Kein Provisioning, keine
Cross-Repo-Abhängigkeit; überwacht **genau die real gefährdete Population** — hätte #1066 auf
`default`/`henning` direkt gefangen. Ist keine Datei vorhanden → `ok` (nichts zu schützen).
- Schlägt **mindestens eine** Datei fehl (EACCES) → Job-Status `error` inkl. des/der betroffenen
  Pfade(s) in der Fehlermeldung (Pfad ist intern, kein Nutzer-Inhalt).
- Owner-Hinweis: Betroffen sind `hem`-eigene Dateien (Zugriff über `group::`). Service-eigene
  (`claude-gregor`) sind über `user::` immun — werden mitgeprüft, bestehen aber trivial; das ist ok.

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `internal/scheduler/scheduler.go` | MODIFY | Job-Eintrag `jobs[]` (`*/15`) + Methode `dataWriteSelftest()` + Edge-Alert `ok→error` |
| `internal/scheduler/selftest.go` (o. `internal/store/`) | CREATE | `probeDataWritable(dataDir) error` — Glob `users/*/trips/*.json`, `O_WRONLY`+Close pro Datei |
| `internal/scheduler/*_test.go` | CREATE | Tests: nicht-schreibbar→error, schreibbar→ok, keine Dateien→ok, Edge-Alert nur bei `ok→error` |
| `docs/project/known_issues.md` | MODIFY | #1120-Eintrag |

### Scope Assessment
- Files: 3–4 · Est. LoC: **~120–170** (unter 250-Limit) · Risk: **NIEDRIG** (rein additiv, isoliert, non-destruktiv, keine neuen Deps, kein Cross-Repo)

### Frequenz & Alerting (festgelegt)
- **`*/15`** analog `alert_checks`/`radar_alert_checks` — #1066 blieb tagelang unbemerkt, 15 min Latenz ist reichlich.
- **Edge-getriggert:** MQ an `infra` nur beim Übergang `ok→error` (Vorzustand aus `lastRuns[jobID]`
  vor `recordRun` lesen). Kein `sync.Once` (verschluckt spätere Re-Onsets im langlebigen Prozess).
  Kein BetterStack (Quota erschöpft). Optional Recovery-Notiz bei `error→ok`.

### Open Questions
- Keine offen — Ansatz, Ziel-Dateien, Frequenz und Alerting sind festgelegt.

## Risks & Considerations
- **Owner ist die Schlüsselgröße (NICHT Persistenz):** Die Probe-Datei muss `hem`-eigen sein,
  damit der Service über `group::` zugreift; nur dann fängt sie den `group::`-Sweep. Eine
  service-eigene Datei (auch persistente) wird über `user::` geöffnet → False Negative. → Nie
  selbst anlegen; entweder echte `hem`-Dateien prüfen (Option A) oder extern provisionierte
  Fixture (Option B).
- **Non-destruktive Probe zwingend:** `O_WRONLY`-Open ohne `O_TRUNC`/`O_CREATE` (+ sofort `Close`).
  Ändert nichts, honoriert aber ACLs identisch zum realen Schreibpfad.
- **BetterStack-Quota erschöpft (10 Heartbeats belegt):** Kein neuer dedizierter Heartbeat ohne
  Upgrade. Primärer Alerting-Weg daher **MQ an `infra`** bei Schreibfehler + Job-Status in
  `/api/scheduler/status`. (Merke: BetterStack-Quota-Constraint.)
- **Kein Nutzerdaten-Kontakt:** Ausschließlich `data/users/gregor-test/…` (bzw. dedizierter
  Test-Pfad). Kein Bezug zu echten Trips/Usern; kein Mail-Versand (Test-User-Prädikat).
- **Frequenz vs. Rauschen:** Zu häufig = Log-/IO-Rauschen; zu selten = späte Erkennung. Kandidat
  `*/15` analog `alertChecks`/`radarAlertChecks`.
- **Nur Go-Pfad getestet:** Der Live-API-Schreibpfad (Nutzer-relevant) ist Go/`claude-gregor`.
  Der Python-Scheduler-Schreibpfad (`loader.save_trip`) läuft ggf. unter anderem User — bewusst
  **out of scope** für diesen Selftest (Fokus = der Pfad, der bei #1066 versagte).
- **Alert-Flapping:** Bei anhaltendem Fehler nicht bei jedem Lauf eine MQ-Nachricht senden —
  Once-/Entprellungs-Mechanik erwägen (vgl. `warnMissingHeartbeatOnce`).
