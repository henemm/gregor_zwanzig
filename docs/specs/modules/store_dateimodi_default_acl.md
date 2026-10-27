---
entity_id: store_dateimodi_default_acl
type: module
created: 2026-10-27
updated: 2026-10-27
status: draft
version: "1.0"
tags: [go, python, store, dateirechte, acl, multi-user, epic-2138, issue-2624]
---

# Store-Dateimodi unter Default-ACL (0770 / 0660)

## Approval

- [ ] Approved

## Purpose

Neu angelegte Verzeichnisse und Dateien unter `data/users` (und Wetter-Cache/Journal) entstehen mit Gruppen-Schreibrecht (Verzeichnisse `0770`, Dateien `0660`). Der bisherige feste Modus `0755`/`0644` begrenzt unter einer Default-ACL (`d:g:gregor-staging-data:rwX`) die ACL-Maske auf `r-x`/`r--`; die Gruppe verliert das Schreibrecht, der Datenrechte-Wächter in `check-gregor20.sh` schlägt bei jedem neuen Konto an (Herkunft: henemm-infra#331, Issue #2624, Epic #2138 "Going Live").

## Source

- **Go-Konstanten (NEU):** `internal/fsmode/fsmode.go` — `DirMode = 0o770`, `FileMode = 0o660`
- **Go-Store:** `internal/store/*.go` (Schreiber `write.go`, Anlage in `user.go` u. a.)
- **Go-Weitere Schreiber:** `internal/scheduler/user_run_state.go`, `internal/handler/telegram_connect.go`, `internal/provider/openmeteo/{cache,calllog}.go`
- **Python-Sperrdateien:** `src/services/file_lock.py` (Konstante) + 7 weitere Dienste
- **Identifier:** `fsmode.DirMode`, `fsmode.FileMode`, `file_lock.LOCK_FILE_MODE`

Schicht: Go-API (`internal/`) und Python-Core (`src/services/`). Kein Frontend.

### Verifizierte Fundstellen (gegen Worktree-Stand geprüft)

Go, Verzeichnisse `0755` -> `fsmode.DirMode`:
`store/user.go:82,224,237,290,332,386` · `store/trip.go:291` · `store/location.go:101` · `store/group.go:169` · `store/metric_preset.go:138` · `store/compare_preset.go:256` · `store/briefing_subscription.go:61` · `store/sessions.go:72` · `store/invite.go:66` (`0o755`) · `store/briefing_lock.go:172` (`0o755`) · `provider/openmeteo/cache.go:59` · `provider/openmeteo/calllog.go:67` (`0o755`).

Go, Dateien -> `fsmode.FileMode`:
`store/write.go:50` (`Chmod 0644`; Kommentar Z.29 nennt "0644") · `scheduler/user_run_state.go:142` (`Chmod 0644`) · `store/briefing_lock.go:175` (`OpenFile ... 0o600`) · `provider/openmeteo/cache.go:68` (`WriteFile 0644`) · `provider/openmeteo/calllog.go:72` (`0o644`) · `handler/telegram_connect.go:69` (`CreateTemp`, 0600, derzeit **kein** Chmod -> `Chmod(tmp, FileMode)` vor `Rename` ergänzen).

Python, Sperrdateien `os.open(..., 0o644)` -> `LOCK_FILE_MODE` (0o660):
`file_lock.py:86` · `forecast_budget.py:465` · `throttle_store.py:191` · `briefing_slots.py:238,512` · `sms_daily_limit.py:164,225,272` · `alert_check_state.py:58` · `official_alerts/meteoalarm_budget.py:281`.
Alle Sperrdateien liegen **neben** ihrer Zustandsdatei (`<Pfad>.lock`); die Zustandsdateien liegen im Datenbaum (`data/users/<id>/...` bzw. `data/`), also im von der Default-ACL betroffenen Baum. Daher werden alle mitgezogen, auch wenn einzelne Zustandsdateien auf Ebene `data/` statt `data/users/` liegen.

## Scope

### In Scope

- Konstanten-Paket `internal/fsmode`, Umstellung aller oben genannten Go-Stellen.
- Zweiter atomarer Schreiber (`scheduler/user_run_state.go`) als Pendant zu `store/write.go`.
- Python-Sperrdateien (PO-Regel: Reste nie abspalten).
- Python-Zustandsdateien, die per `tempfile.mkstemp` (Modus `0600`) + `os.replace` geschrieben werden (Adversary-Befund F-ADV-P1): `forecast_budget.py`, `briefing_slots.py`, `sms_daily_limit.py`, `throttle_store.py`, `alert_check_state.py`, `alert_daily_limit.py`, `official_alerts/meteoalarm_budget.py`, `position_fix.py`, `inbound_sms_reader.py` — gemeinsamer Helfer in `file_lock.py`, `fchmod(fd, LOCK_FILE_MODE)` auf die frische Temp-Datei vor `os.replace` (jede Datei ist je Schreibvorgang neu, daher kein EPERM-Risiko).
- Tests der Kern-Schicht, Abnahme-Messung auf Staging, Gegenprobe auf Prod.

### Out of Scope

- **Keine Migration:** Bestehende Verzeichnisse bleiben `0755` (Infra hat sie repariert; `MkdirAll` ändert Bestehendes nicht). Bestehende Dateien wandern beim nächsten Schreiben auf `0660` (`writeFileAtomic` setzt den Modus bei jedem Schreiben).
- Test-Fixtures mit `0755`/`0644` (ca. 382 Zeilen, betreffen den Produktivpfad nicht).
- Setzen der Default-ACL selbst (Betrieb, henemm-security#255).
- Python-`atomic_write_json`: übernimmt den Modus der Zieldatei bzw. entsteht mit `0666 & umask`; Maske dort unkritisch, unverändert.

> **Querschnitts-Prüfpunkte:**
> - Trip/Ortsvergleich-Teilung: nicht berührt (keine UI-Komponente); Trip- und Vergleichs-Stores ziehen über dieselbe Konstante mit.
> - Mandantentrennung: Test mit zwei Konten nacheinander; `user_id` aus dem Auth-Kontext unverändert.
> - Kanäle: Briefing-/Alarm-Inhalt nicht berührt (Kanäle E-Mail, Telegram, SMS, Premium-SMS unverändert; Telegram-Token-Datei und Briefing-Lock fallen unter die Modus-Umstellung).

## Estimated Scope

- **LoC:** ca. +70/-35 produktiv (überwiegend Einzeiler), Tests ca. +150
- **Files:** ca. 16 Go-Produktivdateien + 1 neue Konstanten-Datei + 11 Python-Dateien (8 Sperrdatei-Stellen in 7 Modulen + `file_lock.py`-Helfer; plus `alert_daily_limit.py`, `position_fix.py`, `inbound_sms_reader.py` für AC-10) + 2-3 Testdateien
- **Effort:** medium (mechanisch, aber Rechte-/Sicherheitsfläche in Prod). Falls das LoC-Limit 250 überschritten wird: `loc_limit_override`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Dateisystem + Default-ACL | Betrieb | Maske wird vom übergebenen Modus begrenzt; Default-ACL setzt der Betrieb (henemm-security#255) |
| `internal/store` | Go-Paket | importiert `fsmode` |
| `internal/scheduler` | Go-Paket | importiert `fsmode` |
| `internal/provider/openmeteo` | Go-Paket | importiert `fsmode` |
| `internal/handler` | Go-Paket | importiert `fsmode` |
| `src/services/file_lock.py` | Python-Modul | hält `LOCK_FILE_MODE`; 7 Dienste importieren es |
| ADR-0031 | Entscheidung | Python schreibt in dieselben Dateien wie Go |
| `henemm-infra/scripts/check-gregor20.sh` | Wächter | Datenrechte-Prüfung (Abnahmekriterium) |

**Importzyklus-Prüfung:** `fsmode` importiert nichts aus dem Projekt (nur Standardbibliothek `io/fs`/`os`). Es ist ein reines Blatt-Paket; ein Zyklus ist damit ausgeschlossen. Befund per Grep: `store`, `provider/openmeteo` und `scheduler` importieren sich nicht gegenseitig in Richtung `fsmode`; `store` importiert nur `config`/`model`, `scheduler` nur `store`/`notify`/`provider`. Ein Import von `store` aus `openmeteo` wäre dagegen riskant (`provider` -> `store` -> `provider`-Nähe) und wird bewusst vermieden. Die Python-Seite importiert `LOCK_FILE_MODE` aus `file_lock.py`; `file_lock.py` importiert keine der 7 Verbraucher (vom Developer per `python -c "import ..."` gegenzuprüfen).

## Implementation Details

```
internal/fsmode/fsmode.go
  const DirMode  os.FileMode = 0o770
  const FileMode os.FileMode = 0o660

Alle os.MkdirAll(x, 0755|0o755)        -> os.MkdirAll(x, fsmode.DirMode)
store/write.go    Chmod(tmp, 0644)      -> Chmod(tmp, fsmode.FileMode); Kommentar Z.29 anpassen
scheduler/user_run_state.go Chmod 0644  -> fsmode.FileMode
store/briefing_lock.go OpenFile 0o600   -> fsmode.FileMode  (sonst Maske --- fuer die Gruppe)
openmeteo/cache.go WriteFile 0644, calllog.go 0o644 -> fsmode.FileMode
handler/telegram_connect.go: nach tmp.Close() und vor Rename: os.Chmod(tmpName, fsmode.FileMode);
  Fehler behandeln wie die uebrigen Schreibfehler (Temp-Datei entfernen, Fehler zurueckgeben)

src/services/file_lock.py:  LOCK_FILE_MODE = 0o660
8 os.open(..., 0o644)-Stellen -> os.open(..., LOCK_FILE_MODE)
```

Hinweis zur Umask: `os.MkdirAll`/`OpenFile` unterliegen der Prozess-Umask (Prod: `UMask=0077` in systemd). Dort wo der Modus **explizit** per `Chmod` gesetzt wird (Dateien über `writeFileAtomic`), gilt der Wert exakt. Für `MkdirAll`/`os.open` wirkt `Modus & ~umask`; der Test darf sich daher nicht auf die Prozess-Umask verlassen (siehe Tests). Bei Prod-Umask `0077` bliebe ein per `MkdirAll` angelegtes Verzeichnis ohne Chmod `0700`; deshalb setzt der Developer nach Neuanlage (`ProvisionUserDirs` und die übrigen Anlagestellen) ein explizites `os.Chmod(dir, fsmode.DirMode)`, sofern das Verzeichnis neu entstanden ist, oder prüft/dokumentiert die Wirkung der Umask im Test. Dies ist der Kern der Zusicherung "Maske bleibt rwx" und muss am Ort der Wirkung geprüft werden (Test mit `syscall.Umask(0o077)`).

## Expected Behavior

- **Input:** Anlage eines Kontos, Schreiben von Store-Dateien, Scheduler-Zustand, Telegram-Token, Wetter-Cache/Journal, Python-Sperrdateien.
- **Output:** Neu entstandene Verzeichnisse `0770`, neu geschriebene Dateien `0660` (unabhängig von der Prozess-Umask); unter Default-ACL `g::rwX` bleibt die Maske `rwx` (Verzeichnisse) bzw. `rw-` (Dateien).
- **Side effects:** Gruppe der Besitzer-Gruppe erhält Schreibrecht. In Prod (Gruppe `claude-gregor`, `other ---`) öffnet sich nichts weiter: `claude-security` bleibt über seinen ACL-Eintrag effektiv `r-x`, `other` bleibt `---`. Bestehende Pfade unverändert bis zum nächsten Schreiben.

## Tests (Kern-Schicht, deterministisch, kein Mock-Theater)

1. **Go Modus-Test** (`internal/store/..._test.go`, Verhalten statt Quelltext): Store in `t.TempDir()`, `syscall.Umask(0o077)` temporär setzen (zurücksetzen per `t.Cleanup`), zwei Konten nacheinander mit `ProvisionUserDirs` anlegen, je Konto Trip, Location, Gruppe, Preset, Session, Einladung und Briefing-Lock schreiben; danach rekursiv `Stat().Mode().Perm()`: Verzeichnisse `0770`, Dateien `0660`. Zusätzlich dasselbe für Scheduler-`user_run_state`, Telegram-Token-Datei und Open-Meteo-Cache/Calllog (je im eigenen Paket-Test).
2. **Go ACL-Test:** in `t.TempDir()` `setfacl -d -m g::rwX <dir>`, Konto anlegen, `getfacl` auswerten: `mask::rwx` bei Verzeichnissen, `mask::rw-` bei Dateien. `t.Skip` mit Begründung, wenn `setfacl`/`getfacl` fehlt oder das Dateisystem ACLs nicht unterstützt. **Ehrlich benannt: Dieser Skip-Pfad ist kein Gate** — auf einem Runner ohne ACL-Dateisystem wird der Test übersprungen und beweist dort nichts; die Modus-Zusicherung bewacht dann allein Test 1, die ACL-Wirkung die Staging-Messung.
3. **Python Sperrdatei-Test** (`tests/...`): `syscall`-/`os.umask(0o077)` setzen, die Sperr-Pfade der 8 Stellen über ihre echten öffentlichen Aufrufe (z. B. `locked_json_rmw`, Throttle-/Slot-/Budget-Schreibpfad) in `tmp_path` auslösen, danach `os.stat(<datei>.lock).st_mode & 0o777 == 0o660`.
3b. **Python Zustandsdatei-Test (AC-10)** (`tests/...`): Umask `0o077` setzen, die Schreibpfade der 9 mkstemp-Dienste (Forecast-Budget, Briefing-Slots, SMS-Tageslimit, Throttle, Alert-Check-Zustand, Alert-Tageslimit, MeteoAlarm-Budget, Position-Fix, Inbound-SMS) über ihre echten öffentlichen Aufrufe in `tmp_path` auslösen, danach `st_mode & 0o777 == 0o660` der Zustandsdatei (nicht der `.lock`-Datei).
4. **Mutations-Gegenprobe (Adversary):** `FileMode` bzw. `DirMode` in je einem der Pfade (insbesondere `telegram_connect`, `briefing_lock`, `user_run_state`, `calllog`) per String-Ersetzung auf alten Wert zurückdrehen; jeder Rückdreher muss genau den zugehörigen Test rot machen.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer registriert ein neues Konto auf einem Server mit Default-ACL `g::rwX` auf dem Datenwurzelverzeichnis / When der Store das Konto anlegt (`ProvisionUserDirs`) / Then haben alle neu entstandenen Verzeichnisse unter `data/users/<id>/` den Modus `0770` und die ACL-Maske bleibt `rwx`, sodass die Dienstgruppe weiterhin schreiben darf.
  - Test: Go-Test mit echtem Store in `t.TempDir()` und gesetzter Umask `0077`; `Stat().Perm()` aller angelegten Verzeichnisse == `0770`; ergänzend `getfacl`-Test (`mask::rwx`) mit ehrlichem Skip ohne ACL-Dateisystem.

- **AC-2:** Given ein Konto existiert / When der Store eine beliebige Datei schreibt (Trips, Orte, Gruppen, Presets, Sessions, Einladungen, Briefing-Abos) / Then hat die Datei danach den Modus `0660` und die ACL-Maske ist `rw-`, nicht `r--`.
  - Test: Go-Test schreibt je Entität eine Datei und prüft `Stat().Perm() == 0660` unter Umask `0077`; ACL-Test prüft `mask::rw-`.

- **AC-3:** Given zwei verschiedene Konten werden nacheinander registriert / When beide Konten angelegt und beschrieben wurden / Then zeigen beide Konten dasselbe Rechtebild (Verzeichnisse `0770`, Dateien `0660`) und keines der Konten sieht oder verändert Dateien des anderen.
  - Test: Zwei-Konten-Test (Mandantenpflicht): beide Datenbäume rekursiv prüfen; Lesen mit Konto A liefert nie Daten von Konto B.

- **AC-4:** Given der Scheduler schreibt seinen Lauf-Zustand je Nutzer, der Telegram-Verbindungs-Token-Speicher legt seine Datei an und das Briefing-Lock wird erstmals angelegt / When diese drei Schreiber laufen / Then haben ihre Dateien ebenfalls `0660` (Lock-Datei nicht mehr `0600`, Telegram-Datei nicht mehr `0600`).
  - Test: je ein Paket-Test (`scheduler`, `handler`, `store`) mit `Stat().Perm() == 0660` unter Umask `0077`.

- **AC-5:** Given der Open-Meteo-Wetter-Cache und das Drift-Journal (Calllog) werden erstmals geschrieben / When der Provider einen Abruf zwischenspeichert bzw. protokolliert / Then ist das Verzeichnis `0770` und sind Cache-Datei sowie Journal `0660`.
  - Test: Paket-Test in `internal/provider/openmeteo` mit `t.TempDir()` und Umask `0077`.

- **AC-6:** Given Python-Dienste legen Sperrdateien an (Alert-Zustand, Briefing-Slots, Forecast-Budget, SMS-Tageslimit, Throttle, MeteoAlarm-Budget, generischer Datei-Lock) / When die jeweilige `.lock`-Datei neu entsteht / Then hat sie den Modus `0660` und nicht mehr `0644`.
  - Test: Python-Test löst die echten Schreibpfade in `tmp_path` bei Umask `0077` aus und prüft `st_mode & 0o777 == 0o660`; keine Quelltext-Prüfung.

- **AC-7:** Given auf dem Server existieren bereits Verzeichnisse mit `0755` und Dateien mit `0644` / When der Store nach dem Deploy erneut in sie schreibt / Then bleiben die bestehenden Verzeichnisse unangetastet (`0755`), die geschriebenen Dateien wechseln von selbst auf `0660`, und es gehen keine Bestandsdaten verloren.
  - Test: Go-Test legt Bestandsverzeichnis `0755` und Datei `0644` mit Inhalt an, schreibt über den Store, prüft Verzeichnis-Modus unverändert, Datei `0660`, vorheriger Fremdinhalt (Read-Modify-Write) erhalten.

- **AC-8:** Given ein Wegwerf-Konto wird auf Staging neu registriert (Staging-Daten sind für `hem` nicht lesbar) / When die Messung per `sudo -n -u claude-gregor` die neue Verzeichnis- und Dateirechte und `getfacl` liest und `check-gregor20.sh` läuft / Then ist das Konto für `claude-gregor` beschreibbar, `getfacl users/<id>/sessions.json` zeigt `mask::rw-` und der Datenrechte-Wächter meldet kein Problem; ist das nicht messbar, wird `NOT_MEASURABLE_ON_STAGING` gemeldet und kein PASS erfunden.
  - Test: Staging-Abnahme im `/e2e-verify`-Schritt, Befund wörtlich ins Verdict.

- **AC-9:** Given der Prod-Deploy ist erfolgt / When die `getfacl`-Gegenprobe auf `/var/lib/gregor/users` (neues oder frisch beschriebenes Konto) läuft / Then bleibt `claude-security` effektiv `r-x` (Dateien `r--`), die Gruppe `claude-gregor` ist `rwx`/`rw-` und `other` bleibt `---`, es öffnet sich also kein zusätzlicher Zugriff.
  - Test: Post-Deploy-Messung per `sudo -n -u claude-gregor getfacl`; Ausgabe im Deploy-Nachweis, Abweichung gilt als Hard-Gate-Fehler.

- **AC-10:** Given Python-Dienste schreiben ihre Zustandsdateien (Forecast-Budget, Briefing-Slots, SMS-Tageslimit, Throttle, Alert-Check-Zustand, Alert-Tageslimit, MeteoAlarm-Budget, Position-Fix, Inbound-SMS) unter einer Default-ACL und Prozess-Umask `0077` / When die jeweilige Datei neu geschrieben wird / Then hat sie danach den Modus `0660` (nicht `0600`), sodass die ACL-Maske `rw-` bleibt und die Dienstgruppe die Datei lesen und schreiben kann.
  - Test: Python-Test löst die echten Schreibpfade in `tmp_path` bei Umask `0077` aus und prüft `st_mode & 0o777 == 0o660` je Datei; keine Quelltext-Prüfung.

## Known Limitations

- Bestehende Verzeichnisse bleiben `0755`, bis sie neu angelegt werden; die Reparatur der Bestandsverzeichnisse liegt bei der Infrastruktur (bereits erfolgt), nicht im Code.
- Der ACL-Test ist auf Runnern ohne ACL-Dateisystem übersprungen (`t.Skip`) und dort **kein Gate**; die Modus-Tests (Umask `0077`) laufen immer.
- Unter Prod-Umask `0077` entscheidet das explizite `Chmod` nach der Anlage (nicht der `MkdirAll`-Parameter allein) über den tatsächlichen Verzeichnismodus; deshalb Test mit gesetzter Umask.
- Nur Dateien über `writeFileAtomic` bzw. den Scheduler-Zustand wandern beim nächsten Schreiben auf `0660`. Bereits bestehende Sperrdateien (Briefing-`.lock` `0600`, Python-`.lock` `0644`) sowie der bestehende Open-Meteo-Cache und das Calllog behalten ihren Modus, bis sie neu angelegt werden: `chmod` erfolgt bewusst nur bei Neuanlage, damit keine fremde Datei mit EPERM scheitert. Festgehalten durch `test_bestehende_sperrdatei_behaelt_modus_0644` und `TestDateimodi_BestehendeCacheUndJournalDateiBehaltenModus`.
- Die Gruppen-Schreibbarkeit hängt davon ab, dass die Besitzergruppe korrekt gesetzt ist (Betrieb); der Code setzt sie nicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; berührt ADR-0031 (Persistenz dateibasiert, Python schreibt mit) und ADR-0003 (Mandantentrennung) nur in der Dateimodus-Ausprägung.
- **Rationale:** Reine Modus-Korrektur ohne Änderung von Datenmodell, Persistenzort oder Mandantentrennung. Eine zentrale Konstante je Sprache statt verstreuter Magic Numbers (ein Änderungspunkt statt ca. 25).

## Changelog

- 2026-10-27: Initial spec created (Issue #2624, Workflow fix-2624-store-modi-default-acl)
