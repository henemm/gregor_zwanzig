---
entity_id: fix_2883_diagnose_journal_rotation
type: module
created: 2026-11-09
updated: 2026-11-09
status: draft
version: "1.0"
tags: [observability, journal, rotation, scheduler-status, briefing-health, enrichment-health]
workflow: fix-2883-diagnose-journal-rotation
---

<!-- Issue #2883, Epic #2733 -->

# Rotation der Diagnose-Journale `openmeteo_calls.jsonl` und `enrichment_calls.jsonl`

## Approval

- [ ] Approved

## Purpose

Zwei Diagnose-Journale wachsen unbegrenzt, weil sie nur angehängt, nie rotiert werden.
Messung Prod 2026-11-09: `data/diagnostics/openmeteo_calls.jsonl` 22,5 MB / 145.585 Zeilen seit
2026-05-22 (ca. 130 KB pro Tag), `data/diagnostics/enrichment_calls.jsonl` 5,6 MB / 51.507 Zeilen
seit 2026-08-20 (ca. 70 KB pro Tag). Die Go-Zustandsprüfungen (`briefing_health`,
`enrichment_health`) lesen die Dateien bei jedem `/api/scheduler/status`-Abruf komplett; der
Lesepfad wird mit der Zeit immer teurer.

Diese Spec übernimmt die in #2224 entschiedene und ausgelieferte Lösung für das Warn-Dienst-Journal:
**größenbasierte Rotation ab 8 MiB mit genau einer Vorgänger-Generation `.1`**, Lesen immer aus
aktueller Datei plus `.1`. Statt den Mechanismus ein drittes Mal zu kopieren, werden die
Rotationslogik (Python) und das Öffnen der beiden Generationen (Go) in je einen gemeinsamen Helfer
herausgelöst, den auch das Warn-Dienst-Journal nutzt. Die Journale sind rein diagnostisch; es gibt
keine Nutzer-sichtbare Funktion. Die Überwachung (`check-gregor20.sh`) darf weder Aussagen
verlieren noch Fehlalarme auslösen.

## Source

- **Schreiber (Python):**
  - `src/providers/call_log.py` — `log_api_call()` (Pfad `diagnostics_path()`, Override `DIAGNOSTICS_PATH`)
  - `src/providers/enrichment_health.py` — `log_enrichment_call()` (Pfad frisch über `get_data_root()`)
  - `src/services/official_alerts/warn_egress.py` — `_rotate_if_needed()` (Wrapper, Logik wandert in den Helfer)
- **Neuer Helfer (Python):** `src/utils/journal_rotation.py` — `rotate_if_needed(path, max_bytes)`
- **Leser (Go):**
  - `internal/scheduler/briefing_health.go` — `analyzeBriefingProviderErrors()`, `findLastBriefingProviderError()`
  - `internal/scheduler/enrichment_health.go` — `aggregateEnrichmentCalls()`
  - `internal/scheduler/warn_service_health.go` — `aggregateWarnServiceCalls()` (stellt auf den Helfer um)
- **Neuer Helfer (Go):** `internal/scheduler/journal_rotation.go` — `openJournalGenerations()`
- **Analyse-Skript:** `scripts/analyze_openmeteo_calls.py` — `_load()`

**Schicht:** Python-Core als Schreiber, Go-API als Leser; kein Frontend.

**Querschnitts-Prüfpunkte:**
- Trip/Ortsvergleich-Teilung: nicht betroffen (kein UI-Baustein).
- Mandantentrennung: nicht betroffen, globale Diagnose-Journale ohne Nutzerdaten, kein nutzerbezogener Endpunkt.
- Kanäle: nicht betroffen, Briefing- und Alarm-Inhalte ändern sich nicht.

## Scope

- **LoC:** ca. +110/-60 Produktivcode, ca. +300 Tests
- **Files:** ca. 10 Quell-/Skriptdateien (siehe Tabelle) plus 3 bis 4 Testdateien plus diese Spec
- **Effort:** medium (Helfer-Extraktion berührt den frisch ausgelieferten #2224-Pfad)

| Datei | Änderung |
|---|---|
| `src/utils/journal_rotation.py` | NEU: gemeinsamer Helfer |
| `src/services/official_alerts/warn_egress.py` | `_rotate_if_needed(path)` bleibt dünner Wrapper |
| `src/providers/call_log.py` | Konstante `OPENMETEO_JOURNAL_MAX_BYTES`, Rotation vor dem Anhängen |
| `src/providers/enrichment_health.py` | Konstante `ENRICHMENT_JOURNAL_MAX_BYTES`, Rotation vor dem Anhängen |
| `internal/scheduler/journal_rotation.go` | NEU: gemeinsamer Go-Helfer |
| `internal/scheduler/warn_service_health.go` | auf gemeinsamen Helfer umgestellt |
| `internal/scheduler/briefing_health.go` | beide openmeteo-Leser lesen aktuelle Datei plus `.1` |
| `internal/scheduler/enrichment_health.go` | liest aktuelle Datei plus `.1`, neue Fehlerbehandlung |
| `scripts/analyze_openmeteo_calls.py` | `_load()` liest `.1` plus aktuelle Datei |
| `src/services/forecast_capture.py` | Kommentar Z. 166 („bleibt unrotiert") korrigiert |
| Tests | `tests/tdd/test_diagnose_journal_rotation.py` (neu), `warn_service_health_test.go`, `briefing_health_test.go`, `enrichment_health_test.go` |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.get_data_root()` | function | Auflösung des Journalpfads (enrichment); `.1` und `.lock` liegen daneben |
| `call_log.DIAGNOSTICS_PATH` | variable | Test-Override des openmeteo-Pfads; Rotation arbeitet auf dem aufgelösten Pfad |
| `fcntl.flock` auf `<datei>.lock` | Muster | Sperrmuster aus #2224 (`forecast_budget.py`, `alert_check_state.py`) |
| `warn_egress.WARN_JOURNAL_MAX_BYTES` | variable | Monkeypatch-Naht der #2224-Tests; muss zur Aufrufzeit gelesen werden |
| `/api/scheduler/status` | endpoint | Reicht `briefing_health` und `enrichment_health` durch; Felder unverändert |
| `henemm-infra/scripts/check-gregor20.sh` | extern | Wertet Streak, 24h-Zähler, letzten Fehler (Fenster 24h/2h) und `enrichment_health.*` (`ENRICHMENT_MAX_AGE_H=48`) aus; unverändert |
| `forecast_capture._prune` | function | Löscht nur `forecast_capture_*.jsonl` mit Datum im Namen; `.jsonl.1` nicht betroffen |

## Entscheidungen

| Punkt | Entscheidung | Begründung |
|---|---|---|
| Schwelle | 8 MiB je Schreiber, eigene Modulkonstanten (`OPENMETEO_JOURNAL_MAX_BYTES`, `ENRICHMENT_JOURNAL_MAX_BYTES`), zur Aufrufzeit gelesen | Konsistenz mit #2224; in Tests per `monkeypatch` überschreibbar |
| Generationen | genau eine: `<datei>.1` | Einfachster Lesepfad (zwei Dateien, keine Glob-Sortierung); PO-freigegebene #2224-Entscheidung |
| Python-Helfer | herauslösen statt kopieren: `rotate_if_needed(path, max_bytes)` | Drei Schreiber teilen dieselbe Rotationssemantik; Rennbedingungs-Logik nicht an drei Stellen pflegen |
| Go-Helfer | `openJournalGenerations(path)` liefert aktuelle Datei ZUERST, dann `.1`, `os.SameFile`-Dedupe, `NotExist` = Leerzustand, sonst Fehler-Flag; gemeinsame Test-Naht `journalBetweenOpens` | Rotiert Python zwischen den Opens, bliebe sonst die umbenannte Datei ungelesen oder würde doppelt gezählt |
| Reihenfolge der Aggregation | beliebig | Alle Aggregationen sind reihenfolgeunabhängig (Maxima, OR; `analyzeBriefingProviderErrors` sortiert selbst). Einzige Ausnahme `unitLatest` (`>=` bei Gleichstand), praktisch irrelevant bei Mikrosekunden-Zeitstempeln |
| `briefing_health` | bleibt ohne Fehler-Flag, fail-soft; API-Felder unverändert, kein neues Feld | Kein Vertragsbruch für `check-gregor20.sh` |
| `enrichment_health` | Nicht-`NotExist`-Open-Fehler setzen jetzt `journal_read_error` | Bewusste Verhaltensänderung: bisher blieb ein nicht lesbares Journal stumm; das Feld existiert bereits (Scan-Fehler setzten es schon) |
| Warn-Journal (#2224) | Verhalten unverändert, nur Helfer herausgelöst | Bestehende #2224-Tests sichern das ab |
| Umstieg | Altdatei über Schwelle wird beim ersten Schreiben komplett nach `.1` verschoben | Kein Datenverlust; eine frühere `.1` gibt es nicht |
| Auslieferung | Python- und Go-Teil im selben PR und Deploy | Die 22,5-MB-Datei wird beim ersten Schreiben rotiert; Go muss `.1` dann schon kennen |

## Implementation Details

### Python

1. `src/utils/journal_rotation.py`: `rotate_if_needed(path: Path, max_bytes: int) -> None`, 1:1 die
   #2224-Logik:
   - Datei fehlt oder `st_size < max_bytes`: sofort zurück (schneller Pfad ohne Sperre).
   - Sonst `<path>.lock` öffnen (`"a"`), `fcntl.flock(LOCK_EX)`, Größe **unter der Sperre erneut**
     prüfen; nur wenn weiterhin `>= max_bytes`: `os.replace(path, path.with_name(path.name + ".1"))`.
   - Sperre im `finally` freigeben. Gesamter Helfer in `try/except Exception: pass` (fail-soft).
2. `warn_egress._rotate_if_needed(path)` ruft den Helfer mit `WARN_JOURNAL_MAX_BYTES`, **zur
   Aufrufzeit gelesen** (monkeypatch-Naht bleibt).
3. `call_log.log_api_call()` und `enrichment_health.log_enrichment_call()` rufen
   `rotate_if_needed(path, <eigene Konstante>)` nach `mkdir` und vor dem Append auf. Der Append
   öffnet die Datei danach neu. Zeilenformat und fail-soft-Verhalten der Schreiber bleiben.

### Go

1. `journal_rotation.go`: `openJournalGenerations(path string) (files []*os.File, readErr bool)`.
   Öffnet zuerst `path`, dann `path + ".1"`; ist `.1` per `os.SameFile` dieselbe Datei wie die
   geöffnete aktuelle, wird sie übersprungen. `os.IsNotExist` ist kein Fehler; jeder andere
   Open-Fehler setzt `readErr = true`, lesbare Dateien bleiben erhalten. Test-Naht
   `journalBetweenOpens` wird zwischen den beiden Opens aufgerufen.
2. `warn_service_health.go`: `openWarnJournal`, `sameOpenFile`, `warnJournalBetweenOpens` entfallen
   zugunsten des Helfers; Aggregation und Ergebnis bleiben gleich.
3. `briefing_health.go`: `analyzeBriefingProviderErrors` und `findLastBriefingProviderError`
   scannen alle vom Helfer gelieferten Dateien; Signaturen und fail-soft (kein Fehler-Flag)
   bleiben.
4. `enrichment_health.go`: `aggregateEnrichmentCalls` scannt alle gelieferten Dateien; ein
   Open-Fehler (nicht `NotExist`) oder Scan-Fehler setzt `journal_read_error`.

### Skript

`scripts/analyze_openmeteo_calls.py`: `_load()` liest zuerst `<pfad>.1` (falls vorhanden), dann die
aktuelle Datei; fehlende Dateien sind kein Fehler.

## Expected Behavior

- **Input:** Eine Journalzeile wird angehängt; die aktuelle Datei hat 8 MiB erreicht oder überschritten.
- **Output:** Die volle Datei wird zu `<datei>.1`, die neue Zeile steht in einer frischen
  aktuellen Datei. `/api/scheduler/status` liefert unverändert dieselben Felder
  (`briefing_health.provider_error_streak_since`, `provider_errors_recent_count`,
  `last_provider_error_at`; `enrichment_health.*`).
- **Side effects:** Je Journal entsteht eine leere Sperrdatei `<datei>.lock`. Platzbedarf je
  Journal begrenzt auf ca. 2 x Schwelle (16 MiB).

## Definition of Done

- Alle AC-1 bis AC-14 sind durch die Tests im Test Plan belegt (Python- und Go-Tests grün,
  Mutationsproben vom Adversary gefangen).
- Python- und Go-Teil sind gemeinsam auf Staging und Prod ausgeliefert.
- Auf Prod ist nach dem ersten Schreibvorgang die Bestandsdatei zu `.1` geworden, die aktuelle Datei
  ist klein, und `/api/scheduler/status` meldet unveränderte Felder ohne `journal_read_error`.
- `check-gregor20.sh` löst nach dem Deploy keinen Fehlalarm aus.
- Die #2224-Tests (Python und Go) bleiben unverändert grün (bis auf den Namen der Go-Test-Naht).

## Acceptance Criteria

- **AC-1:** Given das Abruf-Journal `openmeteo_calls.jsonl` hat 8 MiB erreicht, When der nächste Provider-Abruf protokolliert wird, Then liegt der bisherige Inhalt unverändert in `openmeteo_calls.jsonl.1`, und die aktuelle Datei enthält nur die neue Zeile.
- **AC-2:** Given das Anreicherungs-Journal `enrichment_calls.jsonl` hat 8 MiB erreicht, When der nächste Anreicherungsversuch protokolliert wird, Then liegt der bisherige Inhalt unverändert in `enrichment_calls.jsonl.1`, und die aktuelle Datei enthält nur die neue Zeile.
- **AC-3:** Given zu einem Journal existiert bereits eine `.1` und die aktuelle Datei erreicht die Schwelle erneut, When die nächste Zeile geschrieben wird, Then ersetzt die zweite Rotation die alte `.1`, es entsteht nie eine `.2`, und die Platte hält je Journal höchstens ca. das Doppelte der Schwelle. Liegt das Journal unter der Schwelle, findet keine Rotation statt: keine `.1` entsteht, alle Zeilen bleiben in der aktuellen Datei in der geschriebenen Reihenfolge.
- **AC-4:** Given eine der beiden Altdateien ist beim Deploy deutlich größer als die Schwelle (Prod: 22,5 MB), When nach dem Deploy die erste Zeile geschrieben wird, Then wird der gesamte Bestand nach `.1` verschoben, die aktuelle Datei beginnt klein, und es geht keine Zeile des Bestands verloren.
- **AC-5:** Given mehrere Threads schreiben gleichzeitig Journalzeilen, während die Schwelle überschritten wird, When die Schreiber fertig sind, Then ist keine Zeile verloren und keine doppelt, es wurde nicht doppelt umbenannt (eine gerade erzeugte `.1` wird nicht von einer zweiten Umbenennung überschrieben), und jede Zeile ist vollständiges, gültiges JSON.
- **AC-6:** Given die Rotation selbst schlägt fehl (z.B. `.1` kann nicht ersetzt werden oder die Sperrdatei ist nicht anlegbar), When ein Provider-Abruf oder ein Anreicherungsversuch protokolliert wird, Then bleibt der Abruf unbeeinträchtigt (keine Exception nach außen), und die Zeile wird trotzdem in die aktuelle Datei geschrieben.
- **AC-7:** Given Fehlerabrufe und Erfolge verteilen sich auf `openmeteo_calls.jsonl.1` und die aktuelle Datei (z.B. eine Fehlerserie, die über die Rotationsgrenze reicht), When der Scheduler-Status abgefragt wird, Then berechnet `briefing_health` Fehler-Serie (`provider_error_streak_since`), 24h-Zähler (`provider_errors_recent_count`) und letzten Fehler (`last_provider_error_at`) über beide Dateien, genauso wie bei einer einzigen ungeteilten Datei.
- **AC-8:** Given der letzte Anreicherungsversuch eines Pfads oder dessen letzter Erfolg steht nur in `enrichment_calls.jsonl.1`, When der Scheduler-Status abgefragt wird, Then meldet `enrichment_health` für diesen Pfad die Zeitstempel aus beiden Dateien (jeweils den jüngsten), und es entsteht kein Fehlalarm „kein Versuch" oder „kein Erfolg".
- **AC-9:** Given zwischen dem Öffnen der aktuellen Datei und dem Öffnen von `.1` hat eine Rotation stattgefunden (`.1` ist dieselbe Datei wie die geöffnete aktuelle, nachgestellt durch einen Hardlink), When der Status berechnet wird, Then wird der Inhalt weder von `briefing_health` noch von `enrichment_health` doppelt gezählt: 24h-Zähler und Zähler der Anreicherung stimmen mit dem Einmal-Lesen überein.
- **AC-10:** Given zu einem Journal existiert keine `.1` (noch nie rotiert) oder auch die aktuelle Datei fehlt, When der Status abgefragt wird, Then wird dies nicht als Fehler gemeldet (kein `journal_read_error`), und die Auswertung entspricht der bisherigen Auswertung der aktuellen Datei bzw. ist leer.
- **AC-11:** Given `enrichment_calls.jsonl.1` existiert, ist aber nicht lesbar (z.B. ein Verzeichnis statt einer Datei), When der Status abgefragt wird, Then meldet `enrichment_health` `journal_read_error: true`, während die Daten der lesbaren aktuellen Datei weiterhin ausgeliefert werden. Dies ist eine bewusste Verhaltensänderung: bisher blieb ein solcher Open-Fehler stumm. Im Gegensatz dazu bleibt `briefing_health` bei einem nicht lesbaren `openmeteo_calls.jsonl.1` fail-soft (kein Fehler-Flag, Auswertung der lesbaren Datei).
- **AC-12:** Given der Status-Endpunkt wird nach der Änderung abgefragt, When `briefing_health` ausgeliefert wird, Then enthält die Antwort exakt dieselben Felder wie vorher, ohne neues Feld, sodass `check-gregor20.sh` unverändert funktioniert.
- **AC-13:** Given das Warn-Dienst-Journal `warn_service_calls.jsonl` (#2224), When es nach dem Herauslösen der gemeinsamen Helfer rotiert und gelesen wird, Then verhalten sich Rotation (inklusive Überschreiben von `WARN_JOURNAL_MAX_BYTES` per `monkeypatch` zur Aufrufzeit) und Status (`warn_service_health`) unverändert: alle bestehenden #2224-Tests laufen ohne inhaltliche Änderung grün.
- **AC-14:** Given beide Generationen eines openmeteo-Journals liegen vor, When ein Betreiber `scripts/analyze_openmeteo_calls.py` ausführt, Then wertet das Skript `.1` und die aktuelle Datei gemeinsam aus; fehlt `.1`, läuft es wie bisher nur auf der aktuellen Datei ohne Fehler.

## Test Plan (kein Mock-Theater)

Alle Tests arbeiten mit echten Dateien in `tmp_path` (Python) bzw. `t.TempDir()` (Go) und echten
Threads. Verboten sind `Mock()`, `patch()` und `MagicMock`. Die Schwelle wird per
`monkeypatch.setattr` auf die jeweilige Modulkonstante auf wenige hundert Byte gesenkt (erlaubt,
wie in #2224); der Pfad über `call_log.DIAGNOSTICS_PATH` bzw. `get_data_root()`-Umlenkung.

**Python `tests/tdd/test_diagnose_journal_rotation.py`**

- `test_openmeteo_rotation_bei_schwelle` (AC-1), `test_enrichment_rotation_bei_schwelle` (AC-2):
  Datei bis Schwelle füllen, ein Schreibaufruf; `.1` byte-gleich der Altdatei, aktuelle Datei genau
  eine neue Zeile.
- `test_unter_schwelle_keine_rotation` und `test_zweite_rotation_verdraengt_alte_generation`
  (AC-3): keine `.2`, Gesamtgröße <= 2 x Schwelle + eine Zeile.
- `test_bestand_ueber_schwelle_wird_beim_ersten_schreiben_rotiert` (AC-4): Datei mit mehrfacher
  Schwelle vorbelegen, ein Aufruf, `.1` hat den Bestand vollständig.
- `test_parallele_schreiber_verlieren_keine_zeile` (AC-5): z.B. 8 Threads x 200 Zeilen mit
  `threading.Barrier`, Schwelle so, dass höchstens eine Rotation nötig ist; Zeilen aus aktueller
  Datei plus `.1` ergeben alle IDs genau einmal, alle gültiges JSON. Für beide Schreiber.
- `test_rotationsfehler_ist_fail_soft` (AC-6): `.1` als nicht ersetzbares, gefülltes Verzeichnis
  (echter `os.replace`-Fehler) sowie Sperrdatei-Pfad als Verzeichnis; kein Wurf, Zeile steht in der
  aktuellen Datei. Für beide Schreiber.
- `test_analyse_skript_liest_beide_generationen` (AC-14): Skript-`_load` über `.1` plus aktuelle
  Datei, und ohne `.1`.
- Regression #2224: `tests/tdd/test_warn_journal_rotation.py` bleibt unverändert grün (AC-13).

**Go** (echte Dateien, Aufruf der Aggregationsfunktionen und der Status-Methoden mit echter `DataDir`)

- `briefing_health_test.go`: Fehlerserie über die Rotationsgrenze (AC-7); 24h-Zähler und letzter
  Fehler mit Einträgen nur in `.1` (AC-7); Hardlink `.1` gleich aktuell, kein Doppelzählen (AC-9);
  ohne `.1` und ohne aktuelle Datei (AC-10); `.1` als Verzeichnis bleibt fail-soft ohne Fehler-Flag
  (AC-11); JSON-Feldmenge von `briefing_health` unverändert (AC-12).
- `enrichment_health_test.go`: letzter Versuch/Erfolg nur in `.1` (AC-8); Hardlink (AC-9); keine
  `.1` und keine Datei (AC-10); `.1` als Verzeichnis ⇒ `journal_read_error` bei erhaltenen
  Aggregaten der aktuellen Datei (AC-11); Rotation zwischen den Opens über `journalBetweenOpens`
  ohne Doppelzählung (AC-9).
- `warn_service_health_test.go`: nur Namensnachzug der Test-Naht, alle Fälle unverändert grün
  (AC-13).

Mutationsproben für den Adversary: Wegfall der erneuten Größenprüfung unter der Sperre (AC-5),
Wegfall von `os.SameFile` (AC-9), Lesereihenfolge `.1` zuerst (AC-8), `.1`-Lesefehler in
enrichment verschluckt (AC-11), Wegfall des `try/except` im Helfer (AC-6), Schwelle als Import-Konstante
statt zur Aufrufzeit gelesen (AC-13) und `.1` in `findLastBriefingProviderError` nicht gelesen
(AC-7) müssen je mindestens einen Test rot machen.

## Known Limitations

- **Aufbewahrung:** Bei heutigem Durchsatz hält aktuelle Datei plus `.1` für openmeteo ca. 4
  Monate (8 MiB bei ca. 130 KB/Tag je Generation), für enrichment noch länger. Ein selten genutzter
  Anreicherungspfad kann nach sehr langer Zeit ganz aus den Journalen herausfallen; sein Schlüssel
  fehlt dann in `enrichment_health`. Die Überwachung überspringt Pfade, deren letzter Versuch älter
  als 48 h ist, ohnehin, daher entsteht kein Fehlalarm. Die Überwachungsfenster (24h/2h/48h) bleiben
  immer abgedeckt.
- **Umstieg:** Die erste Rotation verschiebt die Altdaten nach `.1`; die zweite (ca. 2 Monate später)
  verwirft sie. Bis dahin liest Go bei jedem Status-Abruf die große `.1` (kleiner als der heutige
  Zustand und einmalig).
- Zwischen Python-Neustart und Go-Neustart beim Deploy kann ein Restfenster im Sekundenbereich
  entstehen; deutlich kleiner als die Monitorfenster, daher unkritisch.
- Eine Rotation ändert den Rückblick des Analyse-Skripts auf ca. 4 Monate.

### Nicht im Umfang

- `openmeteo_calls_go.jsonl` (Go-Schreiber, ca. 1.238 Zeilen, klein).
- Das Journal von `track_resolution_health`.
- Der tote Alt-Override `openmeteo.DIAGNOSTICS_PATH` (Tests patchen ihn noch; keine Wirkung auf die Rotation).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Betrifft nur Aufbewahrung und Lesepfad interner Diagnose-Journale und folgt der
  bestehenden #2224-Entscheidung; keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth,
  Editor, Test-/Deploy-Strategie) wird berührt.

## Changelog

- 2026-11-09: Initial spec (Issue #2883, Epic #2733)
