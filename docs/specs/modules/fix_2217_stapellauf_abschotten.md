---
entity_id: fix_2217_stapellauf_abschotten
type: module
created: 2026-10-06
updated: 2026-10-06
status: draft
version: "1.0"
tags: [bug, versand-zuverlaessigkeit, scheduler, alarmlauf, panic-schutz, epic-2505]
---

# Stapelläufe abschotten: ein Ausfall darf nicht alle mitreißen (Issue #2217)

## Approval

- [ ] Approved

## Purpose

Heute reißt ein einziger Fehler zu viel mit sich: (A) ein Programmabsturz („Panic") in
einem Go-Scheduler-Job beendet den ganzen Prozess und damit alle Jobs aller Nutzer;
(B) wirft die Prüfung EINES Trips (oder Ortsvergleichs) im Alarmlauf eine Ausnahme, werden
alle Folge-Trips/-Orte desselben Laufs gar nicht mehr geprüft — deren Alarme (Gewitter,
Regen, Unwetterwarnung) fallen still aus. Diese Spec schottet jede Einheit ab: Der
Fehler bleibt sichtbar (Log mit Stacktrace, Lauf-Status `error`, Zähler `failed`), aber
die übrigen Einheiten werden weiter bedient.

## Bezüge

ADR-0018 (kein Kaschieren), #1405 (Erfolgs-Wächter, Klasse 2), #1447 S2a
(Überlappungssperre/Teilerfolg), #2149 (Nutzer-Fehlerflanke/Budget), #2218
(Observability, Abgrenzung), Epic #2505 (Versand-Zuverlässigkeit).

## Source

- **File:** `internal/scheduler/scheduler.go` · **Identifier:** `recordRun`, `callUserWithBudget`, `cron.New` (Go-API)
- **File:** `src/services/trip_alert.py` · **Identifier:** `_check_radar_trips`, `check_all_trips`, `AlertCheckRunResult` (Python-Core)
- **File:** `src/services/compare_alert.py`, `compare_radar_alert.py`, `compare_official_alert.py` · **Identifier:** `_check_one_preset` und die Preset-Schleifen (Python-Core)
- **File:** `src/services/trip_report_scheduler.py` · **Identifier:** `_collect_due_trips` (Schleife ~598-626), `_get_active_trips` (~935-1030) (Python-Core, Briefing-Sammellauf)
- **File:** `src/services/compare_slot_scheduler.py` · **Identifier:** `presets_due_for_hour` (~103-175) (Python-Core)
- **File:** `src/services/scheduler_dispatch_service.py` · **Identifier:** `_auto_pause_expired_presets` (~60-120) (Python-Core)
- **File:** `src/services/dispatch_orchestrator.py` · **Identifier:** `collect_due`/`pre_pass`/`result` beider Strategien (Python-Core)
- **File:** `api/routers/scheduler.py` · **Identifier:** die 5 Alarm-Endpunkte und `trigger_trip_reports` bzw. Compare-Briefing-Endpunkt (Python-Core)
- **File:** `tests/test_success_status_guard.py` · **Identifier:** bekannte Verstöße B9, B10, B11, B11b, B11c

## Estimated Scope

- **LoC:** geschätzt ~1200–1450 laut `git diff --numstat` (Annahme: Schleifenrumpf von
  `_check_radar_trips` ~860 Zeilen wird durch den try-Wrapper eingerückt und zählt
  komplett als „geändert"; dazu `check_all_trips`, Compare-Läufe, Go ~60, Router ~30,
  Tests). Echter inhaltlicher Anteil: ~250 Zeilen.
- **Files:** 9 Produktivdateien (1 Go, 8 Python) + 1 geteilter Baustein (in bestehender
  Datei) + 3–4 Testdateien
- **Effort:** medium
- **Pflicht:** `workflow.py set-field loc_limit_override 2000` vor /50 (Einrückungs-Diff
  ist reiner Whitespace, kein Verhaltensumbau; LoC ist kein Argument für Aufteilung).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| robfig/cron v3.0.1 | Go-Lib | `cron.Recover` als zusätzliches Netz |
| `RadarDeadlineExceeded` (`radar_service.py:446`) | Python | Zeitgrenzen-Abbruch, muss VOR breitem `except` durchgereicht werden |
| `alert_check_state.py:107-111` | Python | Fairness-Reihenfolge („wer zuletzt erreicht wurde, kommt zuletzt") |
| `dispatch_orchestrator.py:69-96` | Python | Vorbild „je Einheit abfangen + zählen" |
| `triggerResponseBody` (`scheduler.go:919-978`) | Go | wertet `failed>0` als harten Fehler, `partial` als Teilerfolg |
| `check-gregor20.sh` / `/api/scheduler/status` | Monitoring | alarmiert bei `status=="error"` ab 2 Läufen in Folge — bleibt unverändert nutzbar |

## Implementation Details

```
GO  internal/scheduler/scheduler.go
  1. recordRun: fn() läuft über kleinen Helfer (z. B. safeCall) mit defer/recover.
     Panic => wird zu error-Ergebnis. In lastRuns[...].Error steht NUR
     "panic in <jobID>" (Status-Endpoint ist halb-öffentlich: kein Stack, keine
     Pfade). Voller Stack nur per log.Printf("[scheduler] panic in %s: %v\n%s", ...).
     Die Zeilen NACH fn() (Sperre freigeben, lastRuns/overlapState schreiben) laufen
     normal => Overlap-Sperre frei, nächster Lauf startet.
  2. callUserWithBudget: recover IN der Goroutine (~483). Panic => sofort
     error über resultCh (+ Stack-Log). Aufrufer wartet nicht bis zum Wartebudget,
     callBudget-Marker hängt nicht. Andere Nutzer derselben Runde laufen weiter.
  3. cron.New(cron.WithLocation(loc),
              cron.WithChain(cron.Recover(cron.PrintfLogger(log.Default()))))
     = zusätzliches Netz für Wrapper-Code außerhalb recordRun (z. B. Flankenlogik).
     SkipIfStillRunning ausdrücklich NICHT: greift vor recordRun, umgeht die
     Skip-Zählung aus #1447 S2a und sperrt bei briefing_dispatch zwei jobIDs
     gemeinsam (kollidiert mit der bestehenden Sperre).

PYTHON  geteilter Baustein (EIN kleiner Helfer, von Trip- UND Compare-Läufen genutzt)
  Aufgabe: eine Einheit (Trip oder Preset) ausführen;
    except RadarDeadlineExceeded: raise      (VOR dem breiten except; Deadline-
                                              Semantik/Fairness unverändert)
    except Exception: logger.error("<Lauf> Einheit <id> fehlgeschlagen",
                                   exc_info=True); Zähler failed += 1; weiter
  Ablageort: bestehende gemeinsame Alarm-Hilfsdatei (vor /50 per `ls` des
  Zielordners prüfen, keine Neuanlage wenn es einen passenden Ort gibt).
  Wo die Schleifenform den Helfer nicht zulässt (Trip-Schleifen, siehe unten),
  wird dasselbe Muster als try-Wrapper geschrieben; die Begründung steht hier:
  Der ~860-Zeilen-Rumpf von _check_radar_trips nutzt `continue` und lokale
  Akkumulatoren — eine Extraktion in eine Funktion müsste beides umbauen
  (Verhaltensrisiko). Der Wrapper lässt die Semantik unverändert.

  trip_alert.py
    _check_radar_trips (1904-2780), check_all_trips (1060-1163):
      Fairness-Stempel (reached[trip.id] o. ä.) VOR dem try => ein kaputter
      Trip rückt ans Ende der Reihenfolge, statt an der Spitze zu bleiben.
      try-Wrapper um den bestehenden Schleifenrumpf (keine Extraktion);
      Reihenfolge der excepts wie oben.
      Gescheiterte Einheit zählt in `checked` MIT (festgeschrieben, Test).
    AlertCheckRunResult (179-191): neues Feld failed: int = 0.
    _resolve_alert_segment/backfill: unverändert, atomar (loader.py:2012-2034),
      Ausnahme mittendrin hinterlässt keinen Halbzustand.

  compare_alert.py, compare_radar_alert.py, compare_official_alert.py
    Schutz je Preset um _check_one_preset, failed zählen (Paritätsgebot
    Trip/Ortsvergleich). Die Stelle "bewusst ohne try" in compare_alert.py
    (~246-256) betrifft NUR die Ruhezeit-Prüfung (#1479, Schutz im geteilten
    Baustein) und bleibt unverändert.

  BRIEFING-SAMMELLAUF (Fälligkeitsprüfung je Einheit, dieselbe Baustein-Logik)
    Ist-Weg von `failed` heute: `dispatch_orchestrator.run_briefing_dispatch`
    ruft `strategy.collect_due(now)` -> `pre_pass` -> `dispatch_one` je Eintrag;
    `dispatch_one` zählt Versandfehler in `self._failed`, `result()` liefert
    `(sent, failed)`; `api/routers/scheduler.py:56-58` gibt `count`/`failed` zurück,
    Go wertet `failed>0` seit #1012/#766 als `error` (`triggerResponseBody`).
    Lücke: Ausnahmen in `collect_due` (Fälligkeitsprüfung) kommen nie bis
    `dispatch_one`, werden also nie gezählt; sie brechen den ganzen Sammellauf ab.

    trip_report_scheduler.py
      _collect_due_trips (~598-626) UND _get_active_trips (~935ff: _get_target_date,
      get_stage_for_date, paused_at/slot_aktiv-Filter): try-Wrapper je Trip um den
      Schleifenrumpf, gleiche Reihenfolge der excepts (RadarDeadlineExceeded entfällt
      hier, nur falls dort relevant), logger.error mit Trip-ID + exc_info, Zähler
      `collect_failed` auf der Service-Instanz (am Anfang von `_collect_due_trips`
      auf 0 gesetzt), weiter mit nächstem Trip. Der Trip fehlt in der Liste dieses
      Laufs, kein Vermerk.
    dispatch_orchestrator.py
      `TripDispatchStrategy.collect_due` und `CompareDispatchStrategy.collect_due`
      addieren den Zähler der Fälligkeitsprüfung auf `self._failed`
      (`result()` bleibt `(sent, failed)`). Router und Go bleiben unverändert:
      `failed>0` => bestehende Antwort/`error`-Auswertung.
      Hinweis: bestehende Router-Logik `status = "partial" if failed > 0`
      (`scheduler.py:57`, `:223`) ist die Briefing-Altsemantik (#766) und wird
      hier NICHT angefasst; Go wertet `failed>0` vorrangig als `error`
      (`triggerResponseBody`: `failed` schlägt `partial`).
    compare_slot_scheduler.py (`presets_due_for_hour`)
      Schutz je Preset um den gesamten Schleifenrumpf (bisher nur
      `except (ValueError, TypeError)` um den Zeitplan-Block; `local_dt`/
      `first_resolvable_tz`/`resolve_preset_slots`-Folgefehler anderer Art brechen
      die ganze Liste ab). Fehlerzähler wie oben (Rückgabe-/Zählweg ohne
      Änderung der Listen-Signatur für bestehende Aufrufer, z. B. compare_alert.py:279).
    scheduler_dispatch_service.py (`_auto_pause_expired_presets`)
      Schutz je Preset (Zonenbestimmung, Datumsvergleich, `save_compare_preset_pause`
      sind bisher nur für ValueError/TypeError im Datumsvergleich geschützt); ein
      Fehler bei einem Preset hält die Auto-Pause der übrigen nicht auf; zählt
      in `failed` über `CompareDispatchStrategy.pre_pass`.

    UNVERÄNDERT (ausdrücklich): Vermerk-/Dedup-Mechanismus (#1725/#1897,
    `BriefingSlotStore`, `is_recorded_or_claimed`, `reserve`/`record_outcome`).
    Eine Ausnahme in der Fälligkeitsprüfung legt KEINEN Vermerk an und verbraucht
    KEINEN (`skip_next` eingeschlossen: `_skip_next_verbrauchen` läuft erst NACH
    erfolgreicher Prüfung, siehe ~616). Der Trip bleibt im Nachhol-Fenster
    (`NACHHOL_FENSTER_STUNDEN`) und wird beim nächsten stündlichen Lauf erneut
    versucht. Fällt die Ausnahme genau in `is_recorded_or_claimed`/
    `_skip_next_verbrauchen`, gilt dasselbe: Trip auslassen, nichts schreiben.

  api/routers/scheduler.py
    `failed` in die Antwort der 5 Alarm-Endpunkte. Semantik: failed>0 => Go wertet
    als harten Fehler (error), NICHT partial (ADR-0018). partial bleibt
    Deadline/Timeout/Budget vorbehalten; Deadline liefert weiter partial.

  tests/test_success_status_guard.py
    B9, B10, B11, B11b, B11c aus den bekannten Verstößen entfernen
    (Ratsche zieht nur in eine Richtung; test_known_violations_only_shrink).
```

## Expected Behavior

- **Input:** Ein Alarmlauf (Trip-Radar, Trip-Unwetterwarnung, drei Ortsvergleich-Läufe)
  trifft auf eine Einheit, die eine Ausnahme wirft; oder ein Go-Job/Nutzer-Aufruf löst
  einen Panic aus.
- **Output:** Alle übrigen Einheiten werden normal geprüft und alarmiert. Antwort des
  Python-Kerns enthält `failed=<Anzahl>`; Go setzt den Job-Status auf `error`. Bei
  Deadline unverändert `partial`. Bei Go-Panic: Prozess läuft weiter, Status `error`.
- **Side effects:** `logger.error` mit Trip-/Preset-ID und Stacktrace; Go-Stack im
  Server-Log; ein kaputter Trip rückt in der Fairness-Reihenfolge ans Ende. Ein
  dauerhaft kaputter Trip erzeugt keinen NEUEN Alarmlärm: rot wurde es schon vorher
  (HTTP 500 => `error`); der Gewinn ist, dass die Folge-Einheiten weiter geprüft werden.

## Out of Scope und Abgrenzung

- **#2218 (Observability):** zusätzliche Metriken/Dashboards für `failed` — nicht hier;
  hier nur Zähler, Log und bestehender `error`-Status (Monitoring `check-gregor20.sh`
  greift ohne Änderung).
- **#1405 (Wächter 2):** hier nur das Entfernen von B9–B11c, weil Gegenzähler jetzt
  existieren; keine neue Wächter-Logik.
- **Briefing-Sammellauf, `compare_slot_scheduler.py`, `scheduler_dispatch_service.py`:**
  NICHT mehr ausgeschlossen, sondern im Scope (PO-Regel: Epic thematisch abschließen,
  bekannte Abweichung im selben Ticket beheben). Prüfergebnis zu den zwei Compare-Dateien:
  `compare_slot_scheduler.py:129-145` und `scheduler_dispatch_service.py:97-111` haben
  dasselbe Fehlerbild nur teilweise: dort existiert ein Schutz je Preset, aber nur für
  `ValueError`/`TypeError` im Datumsblock (`compare_slot_scheduler.py:~144-151`;
  `scheduler_dispatch_service.py:~107-116`). Die Zonenbestimmung davor
  (`first_resolvable_tz`/`local_dt`, ~129-133 bzw. ~101-103) und `save_compare_preset_pause`
  (~118) sind ungeschützt; ein andersartiger Fehler bei EINEM Preset kostet damit alle
  folgenden Presets des Laufs. Deshalb im Scope (Parität Trip/Ortsvergleich).

## Acceptance Criteria

- **AC-1:** Given zwei Trips mit aktivem Radar-Alarm, wobei die Prüfung des ersten wegen
  fehlerhafter Daten eine Ausnahme wirft / When der Radar-Alarmlauf (über den echten
  Endpunkt) läuft / Then wird der zweite Trip im selben Lauf trotzdem geprüft und
  alarmiert, die Antwort enthält `failed == 1`, und der Job-Status in Go ist `error`
  (nicht `ok`, nicht `partial`).
  - Test: echter FastAPI-Router, `_ScriptedRadar(raise_on=...)`/kaputte Trip-Daten,
    Folge-Trip erhält Alarm (kein Mock-Theater).

- **AC-2:** Given zwei Trips im Unwetterwarnungs-/Alarmlauf (`check_all_trips`), wobei die
  Prüfung des ersten eine Ausnahme wirft / When der Lauf startet / Then erhält der zweite
  Trip seine Warnung, die Antwort enthält `failed == 1` und der Job-Status ist `error`.
  - Test: echter Router, kaputter Trip über echte Trip-Daten, Folge-Trip bekommt Warnung.

- **AC-3:** Given ein Ortsvergleich mit zwei Presets, wobei das erste eine Ausnahme
  auslöst / When jeweils der Ortsvergleich-Alarmlauf (Standard), der Radar-Lauf und der
  Lauf für amtliche Warnungen startet / Then wird in allen drei Läufen das zweite Preset
  weiter geprüft und alarmiert, die Antwort enthält `failed == 1` und der Job-Status ist
  `error`.
  - Test: drei Verhaltenstests (je Lauf), echter Router, kaputtes erstes Preset.

- **AC-4:** Given ein Alarmlauf, der die Zeitgrenze überschreitet (Deadline) / When der
  Lauf abbricht / Then liefert die Antwort weiterhin `status: "partial"` und `failed`
  bleibt 0; die Deadline-Ausnahme wird nicht vom allgemeinen Fehlerfänger geschluckt,
  sondern erreicht die bestehende Deadline-Behandlung unverändert.
  - Test: bestehende Deadline-/Fairness-Tests in `test_radar_alarmlauf_fairness.py`
    bleiben grün; zusätzlicher Test: Deadline + zuvor gescheiterter Trip => `partial`
    UND `failed == 1` getrennt gezählt.

- **AC-5:** Given ein Trip, dessen Prüfung wiederholt fehlschlägt / When mehrere
  Radar-Alarmläufe nacheinander laufen / Then rückt dieser Trip in der Fairness-Reihenfolge
  ans Ende (er blockiert nicht die Spitze der Reihenfolge), weil sein Stempel vor der
  Prüfung gesetzt wird; der gescheiterte Trip zählt in `checked` mit.
  - Test: Reihenfolge der erreichten Trips über mehrere Läufe, `checked`-Wert
    festgeschrieben.

- **AC-6:** Given eine Ausnahme bei einem Trip oder Preset im Alarmlauf / When sie
  aufgefangen wird / Then steht im Log ein ERROR-Eintrag mit der Trip- bzw. Preset-ID und
  dem vollständigen Stacktrace (nichts wird still verschluckt).
  - Test: Log-Aufnahme (`caplog`) prüft ID und Traceback-Text im Eintrag für Trip- und
    Compare-Läufe.

- **AC-7:** Given ein Go-Scheduler-Job, dessen Funktion einen Panic auslöst / When der Job
  läuft / Then bleibt der Prozess am Leben, der Status des Jobs steht auf `error` mit dem
  Text genau `"panic in <jobID>"` (ohne Stacktrace, da der Status-Endpunkt halb-öffentlich
  ist), der volle Stack steht nur im Server-Log, und der nächste Lauf desselben Jobs
  startet (Überlappungssperre ist frei).
  - Test: Go-Test mit `newOverlapTestScheduler` und panickender Closure über
    `recordRun`; danach zweiter `recordRun` desselben Jobs läuft durch.

- **AC-8:** Given ein Panic im Aufruf für einen einzelnen Nutzer (`callUserWithBudget`) /
  When mehrere Nutzer in derselben Runde bedient werden / Then erhält der Aufrufer sofort
  einen Fehler (nicht erst nach Ablauf des Wartebudgets), der Budget-Marker hängt nicht,
  und die übrigen Nutzer derselben Runde werden normal bedient.
  - Test: Go-Test mit panickendem `RoundTripper` über `s.client` (Injizierbarkeit in /40
    prüfen; falls nicht möglich, minimale Testnaht begründen); Messung der Rückkehrzeit
    deutlich unter dem Wartebudget.

- **AC-9:** Given der bisherige Wächter-Bestand der #1405-Ratsche / When
  `test_success_status_guard.py` läuft / Then sind B9, B10, B11, B11b und B11c nicht mehr
  in den bekannten Verstößen gelistet, und `test_known_violations_only_shrink` sowie die
  gesamte Datei laufen grün.
  - Test: Rückdreh-Gegenprobe — Einträge wieder einsetzen darf den Wächter nicht
    vakuum-grün lassen (Vorgabe aus Ratschen-Wissen #2151).

- **AC-10:** Given zwei verschiedene Nutzer A und B mit je einem Trip (bzw. Preset) im
  selben Lauf, wobei bei Nutzer A eine Ausnahme auftritt / When die Alarmläufe (Trip und
  Ortsvergleich) laufen / Then wird Nutzer B vollständig bedient und alarmiert, und der
  Fehler wird nur Nutzer A zugeordnet (`failed` und Log tragen die ID von A); es gibt
  keinen Rückfall auf `"default"`.
  - Test: Zwei-Nutzer-Test pro Lauf-Art (Pflicht für datenbewegende Endpunkte).

- **AC-11:** Given zwei Trips mit fälligem Morgen-Briefing, wobei die Fälligkeitsprüfung
  des ersten eine Ausnahme wirft / When der stündliche Briefing-Lauf (Trip-Report-Endpunkt)
  läuft / Then erhält der zweite Trip sein Briefing, die Antwort enthält `failed >= 1`, der
  Job-Status in Go ist `error`, und für den ersten Trip entsteht KEIN Vermerk (er wird beim
  nächsten Lauf im Nachhol-Fenster erneut versucht).
  - Test: echter Router mit Test-Nutzer, ein Trip mit kaputten Daten in der Fälligkeitsprüfung,
    Vermerk-Datei (`briefing_slots.json`) enthält nur den Eintrag des zweiten Trips.

- **AC-12:** Given ein Trip, dessen Filterprüfung in `_get_active_trips` (Zieltag/Etappe/
  Pause/Slot) eine Ausnahme wirft, und ein zweiter gesunder Trip / When der Briefing-Lauf
  läuft / Then wird der zweite Trip weiter berücksichtigt und bedient, die Antwort zählt den
  Ausfall in `failed`, und der Fehler steht mit Trip-ID und Stacktrace im Log.
  - Test: Verhaltenstest über `send_due_reports`/Endpunkt, `caplog` auf Trip-ID.

- **AC-13:** Given ein Trip mit gesetztem `skip_next`, dessen Fälligkeitsprüfung eine
  Ausnahme wirft / When der Lauf stattfindet / Then bleibt `skip_next` unverbraucht und es
  wird kein Vermerk angelegt; beim nächsten fehlerfreien Lauf wirkt `skip_next` wie zuvor
  genau einmal.
  - Test: Zustand des Trips und des Vermerk-Speichers vor/nach dem fehlerhaften Lauf
    identisch (Mutation: Verbrauch vor die Prüfung ziehen => rot).

- **AC-14:** Given ein Ortsvergleich-Briefing-Lauf mit zwei Presets, wobei die Fälligkeits-
  prüfung (Zonenbestimmung) bzw. die Auto-Pause des ersten Presets eine Ausnahme wirft /
  When der stündliche Lauf läuft / Then wird das zweite Preset weiter fällig gemeldet bzw.
  auto-pausiert, die Antwort enthält `failed >= 1`, Job-Status `error`, und es entsteht für
  das erste Preset kein Vermerk.
  - Test: echter Aufruf von `presets_due_for_hour`/`run_compare_presets_daily` mit einem
    Preset aus echten, aber kaputten Daten; Zwei-Nutzer-Variante (Nutzer A kaputt, Nutzer B
    bedient) im Rahmen von AC-10.

## Testplan

- **Kern-Schicht, deterministisch, ohne Netz/Live-Dienste.** Kein `Mock()`/`patch()`/
  `MagicMock`, das nur Annahmen spiegelt. Kaputter Trip/Preset über echte fehlerhafte
  Daten bzw. bestehende Fixtures: `tests/tdd/test_radar_alarmlauf_fairness.py`
  (`_ScriptedRadar(raise_on=...)`, `_make_trips`, DI `_get_radar_service`, echter
  FastAPI-Router, Uhr-Fixture).
- **Briefing-Sammellauf:** zusätzlich `tests/tdd/test_briefing_sammellauf_einheit_abschottung.py` (AC-11 bis AC-14); echter Router, echte `briefing_slots.json` im Test-Datenverzeichnis, Vermerk-Zustand vor/nach prüfen.
- **Neue Testdateien nach Verhalten benannt:** `tests/tdd/test_alarmlauf_einheit_abschottung.py`
  (Python, AC-1 bis AC-6, AC-10), `internal/scheduler/scheduler_panic_test.go`
  (Go, AC-7, AC-8). Keine Issue-Nummern im Namen. Aufruf nur mit benannten Dateien.
- **Live-Schicht:** Staging-Validierung nach Deploy (HTTP-Smoke, `last_run` im
  Status-Endpoint); ein echter Panic ist dort nicht herstellbar — Go-Verhalten wird
  ausschließlich im Kern bewiesen.
- **Mutations-Gegenprobe (Pflicht für den Adversary; per String-Ersetzung mit externer
  Sicherungskopie, nie `git checkout/stash/reset`):**

| Verfälschung | Muss rot machen |
|---|---|
| Fairness-Stempel NACH das try verschieben | AC-5 |
| `except RadarDeadlineExceeded: raise` entfernen oder hinter `except Exception` setzen | AC-4 |
| `failed` nicht in die Router-Antwort durchreichen | AC-1, AC-2, AC-3 |
| `failed>0` fälschlich als `partial` melden | AC-1 (Go-Status `error`) |
| `recover` in `recordRun` entfernen | AC-7 |
| `recover` in der Nutzer-Goroutine entfernen | AC-8 |
| Stack in `lastRuns[...].Error` schreiben | AC-7 (Text exakt) |
| Schutz nur in einem der drei Compare-Läufe weglassen | AC-3 (je Lauf eigener Test) |
| Fälligkeitsprüfung: `collect_failed` nicht auf `_failed` addieren | AC-11, AC-12, AC-14 |
| `_skip_next_verbrauchen` vor die abgesicherte Prüfung ziehen | AC-13 |
| Vermerk bei Ausnahme anlegen (z. B. Schutz um `record_outcome`) | AC-11 |
| try-Wrapper in `presets_due_for_hour` oder `_auto_pause_expired_presets` entfernen | AC-14 |
| Fehler verschlucken (kein `logger.error`/kein Zähler) | AC-6, AC-1 |

  Leitfrage: Ist die Zusicherung dort geprüft, wo sie WIRKT (Antwort/Status/Folge-Trip
  bekommt Alarm) — nicht nur dort, wo der Code steht?
- **Anti-Falle:** Rot im Worktree ohne Regression (`node_modules` etc.) trennen; der
  `test`-Job der CI ist täglich 22:00–02:30 UTC strukturell rot (Re-Run außerhalb).

## Known Limitations

- `recover` fängt nur echte Go-Panics. Nicht abfangbare Laufzeitfehler (z. B. `fatal error: concurrent map writes`, Speichererschöpfung) beenden den Prozess weiterhin; dagegen hilft nur der systemd-Neustart.
- Goroutinen, die künftig außerhalb von `callUserWithBudget` gestartet werden, sind nicht automatisch geschützt — jede neue Job-Goroutine braucht ihren eigenen `recover`.
- Ein dauerhaft kaputter Trip/Preset hält den Job-Status bei jedem Lauf auf `error` (gewollt: sichtbar statt verschluckt, ADR-0018). Er erzeugt keinen zusätzlichen Alarmlärm gegenüber heute, da der Lauf heute schon per HTTP 500 rot wird.
- Das breite `except Exception` fängt auch Programmierfehler; sie bleiben über Stacktrace im Log, `failed`-Zähler und `error`-Status sichtbar, werden aber nicht mehr als Abbruch des ganzen Laufs bemerkbar.
- Gescheiterte Einheiten zählen in `checked` mit (festgeschrieben, siehe Testplan).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine neue Grundsatzentscheidung. Die Semantik „gescheiterte Einheit ⇒ `failed>0` ⇒ Job-Status `error`, `partial` bleibt Deadline/Timeout/Budget vorbehalten“ folgt direkt aus ADR-0018 (kein Kaschieren) und der bestehenden Go-Auswertung (#1012, #1447 S2a). `recover`/`cron.Recover` sind lokale Robustheitsmaßnahmen ohne Auswirkung auf Kanäle, Provider, Datenmodell oder Auth.

## Changelog

- 2026-10-06: Initial draft (Issue #2217).
- 2026-10-06: Briefing-Sammellauf (`trip_report_scheduler.py`) sowie Ortsvergleich-Fälligkeitsprüfung (`compare_slot_scheduler.py`, `scheduler_dispatch_service.py`) in den Scope aufgenommen; Known Limitations und ADR-Abschnitt ergänzt.
