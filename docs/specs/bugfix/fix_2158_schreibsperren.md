---
entity_id: fix_2158_schreibsperren
type: bugfix
created: 2026-10-05
updated: 2026-10-05
status: draft
version: "1.0"
workflow: fix-2158-schreibsperren
issue: 2158
epic: 2138
tags: [persistenz, nebenlaeufigkeit, flock, lost-update, multi-user]
---

# Schreibsperren gegen Lost Updates auf Nutzerdateien (#2158)

## Approval

- [ ] Approved

## Purpose

Wenn Browser, Telegram-Kommando, Briefing-Lauf oder Alarmlauf gleichzeitig dieselbe Nutzerdatei ändern, geht heute eine der Änderungen still verloren (Lost Update), im schlimmsten Fall werden Felder durch eine halb gelesene Datei überschrieben. Diese Spec führt eine prozessübergreifende Sperre (`flock` auf einer gemeinsamen Sperrdatei) zwischen Go-API und Python-Core ein, ergänzt fehlende Sperren bei Orten, Gruppen und Metrik-Vorlagen und stellt sicher, dass Python nie mit veraltetem Trip-Objekt über neuere Browser-Änderungen schreibt.

## Source

- **File:** `internal/store/briefing_lock.go` (Go), `src/app/loader.py` (Python)
- **Identifier:** `LockBriefing` (Go) / `save_trip` -> neu `update_trip` (Python)

## Scope

### In Scope

- Gemeinsame Sperrdatei `data/users/<uid>/briefings/<id>.json.lock` für Trips und Compare-Presets, gesperrt von Go UND Python per `flock(LOCK_EX)`.
- Go: Sperren für Orte (je Nutzer+Ort), Gruppen (je Nutzer, inkl. `migrateGroups` beim GET), Metrik-Vorlagen (je Nutzer); Timeout ⇒ 503 + `Retry-After`.
- Python: `update_trip(user_id, trip_id, mutate)` (Sperre, frisch lesen, mutieren, atomar schreiben); Umstellung der 6 Kommandos, `_skip_next_verbrauchen`, `backfill_stage_distances` und der 3 Compare-Preset-Schreiber.
- Export (`store/user.go`) und `scripts/cleanup_1708c_dead_trips.py` ignorieren `*.lock`.
- ADR-0082 (löst ADR-0031 ab), ADR-0036 Zeilenbelege korrigieren, Index konsistent.
- Nachweis, dass `telegram_tokens.json` bereits atomar und gesperrt ist (#2160 AC-14).

### Out of Scope

- Neuer Go-Schreib-Endpunkt für Python (Angriffsfläche, `requireLocalOnly` ist alleiniger Schutz, #2159 offen).
- ETag/If-Match-Logik (#1395/#1433) bleibt unverändert.
- Nur-Python-Dateien (`pending_briefings.json`, `briefing_log.json`, Snapshots, `alert_state`): kein Konflikt mit Go.
- Netzwerk-Dateisysteme (siehe Annahme).

### Annahme: lokale Platte

`flock` gilt nur auf lokalem Dateisystem. Die Datenablage `data/users/` liegt auf der lokalen Platte des Servers (kein NFS/SMB). Wird die Ablage je verlagert, muss ADR-0082 neu bewertet werden.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/adr/0082-gemeinsame-schreibsperre-go-python.md` | CREATE | Gemeinsame Sperrdatei, Lock-Pfad, Reihenfolge, Fristen |
| `docs/adr/0031-*.md`, `docs/adr/README.md` | MODIFY | Status "Abgelöst durch ADR-0082", Index konsistent |
| `docs/adr/0036-*.md` | MODIFY | veraltete Zeilenbelege korrigieren |
| `internal/store/briefing_lock.go` | MODIFY | nach Mutex `syscall.Flock(LOCK_EX|LOCK_NB)` + Poll, Frist ~5 s, `LockBriefingErr` |
| `internal/handler/trip.go`, `weather_config.go`, `compare_preset.go`, `briefing_subscription.go` | MODIFY | Lock-Timeout ⇒ 503 + Retry-After |
| `internal/store/location_lock.go` | CREATE | Sperre je (Nutzer, Ort) |
| `internal/handler/location.go`, `weather_config.go` | MODIFY | Update/Patch/Delete/PutWeatherConfig unter Orts-Sperre |
| `internal/store/group.go`, `internal/handler/group.go` | MODIFY | Gruppen-Sperre je Nutzer, `loadGroupsLocked`-Variante |
| `internal/store/metric_preset.go`, `internal/handler/metric_preset.go` | MODIFY | Vorlagen-Sperre je Nutzer |
| `internal/store/user.go` | MODIFY | Export nur `*.json` unter `briefings/`, `locations/` |
| `src/app/loader.py` | MODIFY | `update_trip`; `save_trip` gesperrt + atomar, kein `existing={}` bei Parse-Fehler |
| `src/services/file_lock.py` | MODIFY (klein) | Helfer für gesperrtes JSON-RMW |
| `src/services/trip_command_processor.py` | MODIFY | 6 Kommandos als Mutations-Closures |
| `src/services/trip_report_scheduler.py` | MODIFY | `_skip_next_verbrauchen` idempotent unter Sperre |
| `src/services/track_resolution.py` | MODIFY | Backfill nur auf unveränderte Etappen anwenden |
| `src/services/scheduler_dispatch_service.py` | MODIFY | 3 Compare-Preset-Schreiber gesperrt + atomar |
| `scripts/cleanup_1708c_dead_trips.py` | MODIFY | `*.lock` überspringen |
| `tests/tdd/test_trip_schreibsperre.py` | CREATE | Python-Kerntests |
| `tests/tdd/test_compare_preset_schreibsperre.py` | CREATE | Compare-Preset-Schreiber |
| `internal/store/briefing_flock_test.go`, `location_lock_test.go`, `group_lock_test.go`, `metric_preset_lock_test.go`, `export_lock_test.go` | CREATE | Go-Kerntests Store |
| `internal/handler/schreibsperre_503_test.go`, `location_parallel_test.go`, `group_parallel_test.go`, `metric_preset_parallel_test.go` | CREATE | Go-Handlertests |

### Estimated Changes

- Files: ~20 produktiv, ~10 Test
- LoC: ca. +550 produktiv, +500 Test. Das Standardlimit von 250 reicht nicht: `workflow.py set-field loc_limit_override 700` vor `/50-implement`. Alles in EINEM Workflow, kein Abspalten.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/file_lock.py` (`acquire_exclusive`) | module | Python-flock mit Timeout, Konvention `<ziel>.lock` |
| `internal/store/briefing_lock.go` | module | Prozessinterner Mutex je (Nutzer, Id), wird um flock erweitert |
| `internal/store/quota_lock.go` | module | Quota-Sperre, steht in der Lock-Reihenfolge ganz vorn |
| `internal/store/write.go` (`writeFileAtomic`) | module | Atomares Schreiben in Go |
| `src/app/loader.py` (`_deep_merge_preserve_unknown`) | module | Merge-Verhalten, Overlay gewinnt, Listen werden ersetzt |
| ADR-0031, ADR-0036, ADR-0076 | adr | Vorgänger/verwandte Entscheidungen |
| `tests/test_adr_index_drift.py` | test | Index-Datei-Konsistenz der ADRs |
| #2159 | issue | Grund gegen Go-Endpunkt (Localhost-Guard) |
| #1395/#1433 | issue | ETag, bleibt unverändert |
| #2160 AC-14 | issue | `telegram_tokens.json` bereits atomar |

## Implementation Details

**Architekturentscheidung:** `flock` auf gemeinsamer Datei, kein Go-Schreib-Endpunkt. Go-`flock(2)` und Python-`fcntl.flock` sind auf Linux kompatibel, sofern beide DIESELBE Datei `data/users/<uid>/briefings/<id>.json.lock` sperren. Der Pfad wird in ADR-0082 festgeschrieben und auf beiden Seiten getestet (sonst wirkt die Sperre still nicht). Die Sperrdatei liegt neben dem Ziel, weil `os.replace`/`rename` die Inode des Ziels tauscht.

**Sperre allein heilt kein Stale-Objekt:** Der Scheduler hält sein Trip-Objekt seit Laufbeginn; `_deep_merge_preserve_unknown` ersetzt Listen (`stages`) komplett. Deshalb gilt: das RMW läuft UNTER der Sperre auf frisch gelesenem Stand, nur die gewollte Änderung wird angewandt.

**`update_trip`** (Python): Sperre holen, Datei frisch lesen (Parse-Fehler wirft, es wird NICHT mit `{}` weitergemacht, Datei bleibt unverändert), `mutate` auf dem frischen Trip, atomar über tempfile + `os.replace`, Sperre lösen. `save_trip` bleibt für Bestandsaufrufer, ist aber intern gesperrt + atomar. Alle Python-Schreiber auf `briefings/` (Trips und Compare-Presets) schreiben atomar.

**Idempotenz je Aufrufer:**
- `_skip_next_verbrauchen`: setzt `skip_next=false` nur, wenn es in der frischen Datei noch `true` ist.
- Backfill: übernimmt berechnete Distanzen nur für Etappen, deren ID und Wegpunkte in der frischen Datei unverändert sind. Stage-Arrival-Berechnung bleibt bit-gleich.
- Kommandos: Mutation (Ruhetag, Start verschieben, Pause, Skip, Abbrechen, Fortsetzen) arbeitet auf dem frischen Trip.

**Go:** `LockBriefing` nimmt nach dem Mutex den flock (nicht blockierend mit 20-ms-Poll, Frist ca. 5 s); Fristablauf liefert Fehler, Handler antworten 503 + `Retry-After`, nichts wird geschrieben. Orte: Sperre je (Nutzer, Ort). Gruppen und Metrik-Vorlagen: je Nutzer eine Sperre, weil Sammeldateien (`groups.json`, `metric_presets.json`). `migrateGroups` läuft unter bereits gehaltener Gruppen-Sperre über die interne Variante `loadGroupsLocked` (keine Reentranz).

**Keine Verklemmungsgefahr durch Python-Aufrufe:** Kein Go-Handler hält `LockBriefing` während eines synchronen Python-Aufrufs (geprüft an `trip.go`, `weather_config.go`, `compare_preset.go`, `briefing_subscription.go`; Proxys nehmen keine Sperre).

### Lock-Reihenfolge (verbindlich, deadlock-frei)

Quota -> Gruppen/Vorlagen (je Nutzer) -> Ort -> Briefing-Mutex -> Datei-flock. Nie umgekehrt. `DeleteGroup` (Gruppen-Sperre) darf danach Orte sperren, nie umgekehrt.

### Timeout-Tabelle (Frist 5 s)

| Aufrufer | Verhalten bei Timeout |
|---|---|
| Go-Schreib-Handler | 503 + `Retry-After`, nichts geschrieben |
| Inbound-Kommando | nichts schreiben, Antwort an den Nutzer "bitte erneut senden", nie still verwerfen |
| `_skip_next_verbrauchen` | Trip in diesem Lauf NICHT senden (Überspringen-Zusage gilt), nächster Lauf erneut |
| Backfill Distanzen | Warn-Log, mit In-Memory-Ergebnis weiterrechnen, nicht persistieren |
| Compare-Status/Pause/Resume | Warn-Log, Rückgabe `False`; Kommando-Pfad meldet Fehler an den Nutzer |
| Jeder Pfad | niemals Rückfall auf ungesperrtes Schreiben |

### Export und Listen

Listen filtern bereits `*.json`; `<id>.json.lock` wird nicht gezählt. Ausnahmen werden korrigiert: Export `store/user.go` (nur `*.json`), `scripts/cleanup_1708c_dead_trips.py` (`*.lock` überspringen).

## Expected Behavior

- **Input:** gleichzeitige Schreibzugriffe aus Browser (Go), Telegram/Mail/SMS-Kommandos, Briefing-/Alarmlauf (Python) auf dieselbe Nutzerdatei.
- **Output:** alle Änderungen bleiben erhalten; bei Sperr-Fristablauf eine klare Fehlermeldung (503 bzw. "bitte erneut senden") statt stillem Verlust.
- **Side effects:** neue `*.json.lock`-Dateien neben Trips/Compare-Presets (leer, nicht in Export/Listen); Python schreibt `briefings/` nur noch atomar.

## Acceptance Criteria

- **AC-1:** Given ein Ort mit Name und Wetter-Konfiguration / When zwei Anfragen gleichzeitig verschiedene Felder desselben Orts ändern (z. B. Name per PATCH und Wetter-Konfiguration per PUT) / Then enthält der Ort danach beide Änderungen und keine geht verloren.
  - Test: `location_parallel_test.go`, N parallele Schreiber, disjunkte Felder, Endstand geprüft (kein Sleep).

- **AC-2:** Given zwei verschiedene Gruppen eines Nutzers / When beide gleichzeitig angelegt oder geändert werden / Then sind danach beide Änderungen in `groups.json` vorhanden.
  - Test: `group_parallel_test.go`, parallele Create/Update, Endstand beide Gruppen.

- **AC-3:** Given eine Gruppe mit Orten / When die Gruppe gelöscht wird, während gleichzeitig ein Ort dieser Gruppe aktualisiert wird / Then enden beide Vorgänge ohne Verklemmung innerhalb der Testfrist, und unabhängig von der Reihenfolge gilt genau dieser Endstand: die Gruppe fehlt in `groups.json`, der Ort trägt das geänderte Feld, und der Ort verweist nicht mehr auf die gelöschte Gruppe (Test mit beiden erzwungenen Reihenfolgen).
  - Test: `DeleteGroup` ‖ Orts-Update mit Test-Timeout; Verklemmung ⇒ Timeout ⇒ rot.

- **AC-4:** Given eine Gruppen-Datei im Altformat, die beim Lesen migriert wird / When ein GET (Migration schreibt) und ein Gruppen-Schreiber gleichzeitig laufen / Then geht keine der beiden Änderungen verloren und es entsteht keine Verklemmung.
  - Test: `group_lock_test.go`, GET mit Migration ‖ Create, beide Wirkungen geprüft.

- **AC-5:** Given zwei verschiedene Metrik-Vorlagen eines Nutzers / When beide gleichzeitig angelegt, geändert oder gelöscht werden / Then sind danach beide Änderungen in `metric_presets.json` erhalten.
  - Test: `metric_preset_parallel_test.go`, parallele Create/Patch, Endstand.

- **AC-6:** Given eine fremde Sperre (eigener File-Descriptor mit `flock`) auf `<id>.json.lock` / When die Go-API einen Trip speichern will / Then wartet sie bis zur Freigabe und schreibt danach; läuft die Frist ab, antwortet sie 503 mit `Retry-After` und es wurde nichts geschrieben (Datei unverändert).
  - Test: `briefing_flock_test.go` + `schreibsperre_503_test.go`, Freigabe per Kanal-Handshake, Frist im Test verkürzt, Bytevergleich der Datei.

- **AC-7:** Given die Go-API hält die Briefing-Sperre eines Trips / When ein Python-Prozess denselben Trip per `update_trip` ändern will / Then wartet Python, bis Go freigibt (gleiche Sperrdatei `<id>.json.lock`), und schreibt erst danach.
  - Test: Python-Subprozess gegen Go-gehaltene Sperre, Pipe-Handshake statt Sleep; beweist gleichen Lock-Pfad über die Prozessgrenze.

- **AC-8:** Given ein Nutzer ändert im Browser Trip-Name und Etappenliste / When danach ein Telegram-Kommando, ein Briefing-Lauf (`skip_next`) oder ein Alarmlauf (Backfill) mit einem VORHER geladenen, veralteten Trip-Objekt schreibt / Then bleibt die Browser-Änderung (Name, Etappenliste) erhalten und nur die gewollte Änderung des Kommandos/Laufs wird angewandt.
  - Test: `test_trip_schreibsperre.py`, Trip laden, Platte per Browser-Änderung ändern, dann je Pfad (6 Kommandos, `_skip_next_verbrauchen`, Backfill) mit altem Objekt; Endstand der Datei.

- **AC-9:** Given eine beschädigte oder halb geschriebene Trip-Datei / When Python sie per `update_trip`, `save_trip` oder Kommando ändern will / Then wird nichts geschrieben, ein definierter Fehler gemeldet und die Datei bleibt byte-identisch (kein Ersetzen durch `existing={}`, kein #102-Muster).
  - Test: kaputte JSON-Datei, Aufruf, Exception geprüft, Bytevergleich vorher/nachher.

- **AC-10:** Given ein Python-Prozess hält die Sperre eines Trips länger als die Frist / When ein Inbound-Kommando, `_skip_next_verbrauchen`, Backfill oder ein Compare-Schreiber den Trip ändern will / Then gilt je Aufrufer das Timeout-Verhalten der Tabelle (Kommando: Antwort "bitte erneut senden"; `skip_next`: Trip in diesem Lauf nicht senden; Backfill: nicht persistieren; Compare: `False` plus Fehlermeldung) und es wird in keinem Pfad ungesperrt geschrieben.
  - Test: `test_trip_schreibsperre.py`, Sperre durch Test-Subprozess gehalten, Frist verkürzt, jeder Aufrufer-Pfad einmal, Datei unverändert.

- **AC-11:** Given beliebige Python-Schreiber auf `briefings/` (Trip, Compare-Status, Pause, Fortsetzen) / When sie schreiben / Then geschieht das atomar über temporäre Datei und `os.replace`, sodass ein gleichzeitiger Leser nie eine halbe Datei sieht.
  - Test: Leser-Thread liest während vieler Schreibvorgänge, jede gelesene Datei ist vollständig parsebar; kein Dateiinhalt-Check des Quellcodes.

- **AC-12:** Given zwei verschiedene Nutzer mit gleicher Trip-ID / When beide gleichzeitig speichern / Then liegen die Sperren in getrennten Dateien (`data/users/<uidA>/...` und `<uidB>/...`), die Nutzer blockieren sich nicht gegenseitig und keine Änderung landet im falschen Nutzerverzeichnis.
  - Test: Go und Python, Nutzer A hält Sperre, Nutzer B schreibt sofort durch; Endstände je Nutzer geprüft (Mandantentrennung).

- **AC-13:** Given Trips, Compare-Presets, Orte und Sperrdateien im Nutzerverzeichnis / When der Nutzer seine Daten exportiert oder Trips/Vergleiche/Orte aufgelistet werden / Then enthält weder Export-Archiv noch Liste eine `.lock`-Datei, und `cleanup_1708c_dead_trips.py` behandelt Sperrdateien nicht als Trip.
  - Test: `export_lock_test.go`, Archivinhalt; Listen-Test mit vorhandener `.lock`; Skript-Test mit `*.lock`.

- **AC-14:** Given ein Compare-Preset / When Status-Update und Pause gleichzeitig geschrieben werden / Then sind danach beide Felder (Status und Pause) erhalten.
  - Test: `test_compare_preset_schreibsperre.py`, `save_compare_preset_status` ‖ `save_compare_preset_pause`, beide Felder im Endstand.

- **AC-15:** Given `telegram_tokens.json` / When mehrere Token-Schreibvorgänge parallel laufen / Then bleibt jeder Token erhalten und die Datei wird atomar ersetzt; dafür wird ein neuer Nebenläufigkeitstest geschrieben (bisher existiert keiner), Produktivcode bleibt unverändert, weil #2160 AC-14 Atomarität und Sperre bereits geliefert hat.
  - Test: Go-Test mit parallelen Token-Schreibern, falls noch nicht vorhanden, sonst Verweis auf den bestehenden Test.

- **AC-16:** Given ADR-0031 war "Go einzige Schreib-Autorität" / When ADR-0082 angelegt wird / Then trägt ADR-0031 in Datei und Index den Status "Abgelöst durch ADR-0082", ADR-0082 steht im Index, und `tests/test_adr_index_drift.py` ist grün.
  - Test: `uv run pytest tests/test_adr_index_drift.py`.

- **AC-17:** Given die bestehenden Kommando-Tests und die Stage-Arrival-Berechnung / When die Aufrufer auf `update_trip` umgestellt sind / Then bleiben alle bestehenden Kommando-Tests grün und die gespeicherten Etappen-Ankunftszeiten sind bit-gleich zum Stand vor der Änderung.
  - Test: bestehende Testdateien zu Kommandos benannt laufen lassen; Vergleichstest der Stage-Arrival-Werte mit versionierter Referenz.

## Test Plan

### Automated Tests (TDD RED)

Kern-Tests, deterministisch, ohne Netz; keine Sleeps als Beweis (Pipe-Handshake bzw. Kanal-Barrieren), keine Mock-Theater (echte Dateien, echte Prozesse).

- [ ] Test 1: GIVEN ein Ort WHEN PATCH ‖ PUT-Wetter-Konfiguration parallel THEN beide Felder erhalten (`internal/handler/location_parallel_test.go`). Der Issue-Test "zwei verschiedene Orte parallel" ist heute schon grün (eine Datei je Ort) und beweist nichts, daher wird er ersetzt.
- [ ] Test 2: GIVEN zwei Gruppen WHEN parallel THEN beide in `groups.json`; DeleteGroup ‖ Orts-Update ohne Verklemmung; GET-Migration ‖ Schreiber (`group_parallel_test.go`, `group_lock_test.go`).
- [ ] Test 3: GIVEN zwei Metrik-Vorlagen WHEN parallel THEN beide erhalten (`metric_preset_parallel_test.go`).
- [ ] Test 4: GIVEN roher flock auf `<id>.json.lock` WHEN Go speichert THEN wartet bzw. 503 + Retry-After bei kurzer Frist, Datei unverändert (`briefing_flock_test.go`, `schreibsperre_503_test.go`).
- [ ] Test 5: GIVEN Go hält `LockBriefing` WHEN Python-Subprozess `acquire_exclusive` THEN wartet (Pipe-Handshake) (`test_trip_schreibsperre.py`).
- [ ] Test 6: GIVEN Python hält Sperre WHEN `update_trip`/Kommando/`skip_next`/Backfill/Compare mit verkürzter Frist THEN definiertes Timeout-Verhalten je Aufrufer.
- [ ] Test 7: GIVEN Stale-Trip-Objekt WHEN Browser-Änderung auf Platte und dann Kommando/`skip_next`/Backfill THEN Browser-Änderung bleibt.
- [ ] Test 8: GIVEN kaputte Datei WHEN `update_trip` THEN Exception, Datei byte-identisch.
- [ ] Test 9: GIVEN zwei Nutzer, gleiche Trip-ID WHEN parallel THEN getrennte Sperren, kein gegenseitiges Blockieren (Go + Python).
- [ ] Test 10: GIVEN Sperrdateien WHEN Export/Listen THEN keine `.lock`-Datei (`export_lock_test.go`).
- [ ] Test 11: GIVEN Compare-Preset WHEN Status ‖ Pause THEN beide Felder erhalten (`test_compare_preset_schreibsperre.py`).
- [ ] Test 12: GIVEN parallele Token-Schreiber WHEN `telegram_tokens.json` THEN keiner geht verloren (neu: `internal/store/telegram_token_concurrency_test.go`).
- [ ] Test 13: GIVEN ADR-0082 WHEN Index-Drift-Test THEN grün (`tests/test_adr_index_drift.py`).
- [ ] Test 14: GIVEN umgestellte Kommandos WHEN bestehende Kommando-Tests THEN grün; Stage-Arrival bit-gleich.

### Mutationsprobe (Pflicht im Adversary, nur per String-Ersetzung mit externer Sicherungskopie)

| Entfernte/verfälschte Sperre | Test, der rot werden MUSS |
|---|---|
| Orts-Sperre in Patch/Update | Test 1 (`location_parallel_test.go`) |
| Gruppen-Sperre in Create/Update | Test 2 (`group_parallel_test.go`) |
| Gruppen-Sperre um `migrateGroups` beim GET | Test 2 (`group_lock_test.go`, GET-Migration ‖ Schreiber) |
| Vorlagen-Sperre | Test 3 (`metric_preset_parallel_test.go`) |
| flock in `LockBriefing` (Go) | Test 4 (`briefing_flock_test.go`) und Test 5 |
| 503-Pfad bei Fristablauf (Fehler ignoriert, trotzdem geschrieben) | Test 4 (`schreibsperre_503_test.go`) |
| flock in Python `update_trip` | Test 5 |
| Frisch-Lesen unter Sperre (Rückfall auf übergebenes Objekt) | Test 7 |
| Parse-Fehler wieder schlucken (`existing={}`) | Test 8 |
| Atomares Schreiben (`os.replace` -> direktes `open("w")`) | AC-11-Lesertest |
| Lock-Pfad Python um ein Zeichen abweichend | Test 5 (Cross-Process) |
| Nutzer-ID aus Lock-Pfad entfernt | Test 9 |
| `.lock`-Filter im Export entfernt | Test 10 |
| Compare-Schreiber ohne Sperre | Test 11 |
| ungesperrter Rückfall bei Timeout | Test 6 |

Wird bei einer Verfälschung KEIN Test rot, ist das ein Finding.

## Lock-Reihenfolge und Teilschritte

Teilschritte so geschnitten, dass nach jedem Schritt alles grün bleibt: (1) ADR-0082 + Go-Sperren Orte/Gruppen/Vorlagen -> (2) Go-flock + 503 + Export-/Skript-Filter -> (3) Python `update_trip`/`save_trip` -> (4) Aufrufer-Umstellung (Kommandos, `skip_next`, Backfill) -> (5) Compare-Preset-Schreiber.

## Known Limitations

- Nur lokale Platte (siehe Annahme); flock auf NFS ist nicht zuverlässig.
- Ein Python-Schreiber, der die Sperrdatei nicht benutzt (z. B. manuelles Skript), wird nicht geschützt. Die bekannten Skripte (`scripts/*`) laufen manuell; Umstellung nur, wenn sie `briefings/` produktiv schreiben.
- Die Sperre schützt nicht vor dem fachlichen Konflikt "Browser überschreibt Python-Änderung ohne If-Match"; das bleibt Sache des ETag (#1395/#1433).
- Risiken: MITTEL-HOCH. Größte Regressionsfläche ist die Umstellung der Kommando-Closures und die Stage-Arrival-Berechnung beim Speichern (AC-17). Ein zu langes Halten der Sperre würde Kommandos verzögern; die Frist von 5 s begrenzt das. Staging-Daten sind für `hem` nicht lesbar, daher Nachweis über deterministische Kern-Tests, nicht über Staging-Dateizugriff.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0082 (löst ADR-0031 ab; ADR-0031 erhält Status "Abgelöst durch ADR-0082", ADR-0036 Zeilenbelege werden korrigiert)
- **Rationale:** ADR-0031 ("Go einzige Schreib-Autorität") entspricht nicht der Realität, Python schreibt `briefings/<id>.json` ebenfalls. Statt eines neuen Go-Schreib-Endpunkts (neue Cross-User-Angriffsfläche, #2159 offen) sperren beide Prozesse dieselbe Sperrdatei per flock; keine Verklemmung, da kein Go-Handler die Briefing-Sperre während eines Python-Aufrufs hält.

## Changelog

- 2026-10-05: Initial spec created
