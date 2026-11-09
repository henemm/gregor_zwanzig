---
entity_id: fix_2224_warn_journal_rotation
type: module
created: 2026-11-09
updated: 2026-11-09
status: draft
version: "1.0"
tags: [official-alerts, observability, journal, rotation, scheduler-status]
workflow: fix-2224-warn-journal-rotation
---

<!-- Issue #2224 -->

# Rotation des Warn-Dienst-Journals `warn_service_calls.jsonl`

## Approval

- [ ] Approved

## Purpose

Das Diagnose-Journal `data/diagnostics/warn_service_calls.jsonl` hält jeden Abruf der
amtlichen Warn-Dienste fest (auch Cache-Treffer) sowie Zonen-Drift-Ereignisse (#1434). Es wird
nur angehängt, nie rotiert. Messung Prod 2026-11-09: 64,9 MB / 406.506 Zeilen seit 2026-07-22
(ca. 600 KB pro Tag), davon nur 32 Drift-Zeilen. Die Go-Zustandsprüfung liest die ganze Datei
bei jedem Scheduler-Status-Abruf. Das Wachstum ist unbegrenzt und der Lesepfad wird mit der
Zeit immer teurer.

Diese Spec begrenzt das Wachstum durch **größenbasierte Rotation mit genau einer
Vorgänger-Generation** (`warn_service_calls.jsonl.1`), ohne dass der Warn-Ausfall-Monitor
(`check-gregor20.sh`, #1422) oder die Zonen-Drift-Auswertung (#1434) Aussagen verlieren oder
Fehlalarme auslösen. Das Journal ist rein diagnostisch; es gibt keine Nutzer-sichtbare Funktion.

## Source

- **Schreiber (Python):** `src/services/official_alerts/warn_egress.py` —
  `warn_calls_path()`, `log_warn_service_call()`, `log_zone_drift()`
- **Leser (Go):** `internal/scheduler/warn_service_health.go` —
  `aggregateWarnServiceCalls()`, `Scheduler.WarnServiceHealth()`
- **Test-Umlenkung:** `tests/conftest.py` (`WARN_CALLS_PATH_OVERRIDE`, autouse-Fixture)

**Schicht:** Python-Core (`src/services/`) als Schreiber, Go-API (`internal/`) als Leser; kein
Frontend.

**Querschnitts-Prüfpunkte:**
- Trip/Ortsvergleich-Teilung: nicht betroffen (kein UI-Baustein).
- Mandantentrennung: nicht betroffen, globales Diagnose-Journal ohne Nutzerdaten, kein
  nutzerbezogener Endpunkt.
- Kanäle: nicht betroffen, Briefing- und Alarm-Inhalte ändern sich nicht.

## Scope

- **LoC:** ca. +160/-10 (Produktivcode ca. 50, Rest Tests)
- **Files:** 4 (`warn_egress.py`, `warn_service_health.go`, `warn_service_health_test.go`,
  `tests/tdd/test_warn_journal_rotation.py`) plus diese Spec
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `warn_egress.WARN_CALLS_PATH_OVERRIDE` | variable | Test-Umlenkung des Journalpfads; Rotation arbeitet auf dem aufgelösten Pfad, `.1` und `.lock` liegen daneben |
| `fcntl.flock` auf `<datei>.lock` | Muster | Bestehendes Sperrmuster (`forecast_budget.py`, `alert_check_state.py`, `briefing_slots.py`) |
| `internal/scheduler/scheduler.go` (Einhängepunkt `warn_service_health`) | module | Reicht das Aggregat in `/api/scheduler/status` durch; unverändert |
| `henemm-infra/scripts/check-gregor20.sh` | extern | Wertet nur Frische aus (Versuch <=3h ohne Erfolg <=3h; Drift nur bei Frische <=24h); unverändert |

## Entscheidungen

| Punkt | Entscheidung | Begründung |
|---|---|---|
| Schwelle | 8 MB (`WARN_JOURNAL_MAX_BYTES`, Modulkonstante, in Tests überschreibbar) | Obergrenze Platte ca. 16 MB, Rückblick 13 bis 26 Tage, mehr als das 10-fache des 24h-Monitorfensters |
| Generationen | genau eine: `warn_service_calls.jsonl.1` | Einfachster Lesepfad in Go (zwei Dateien, keine Glob-Sortierung) |
| Umbenennung | `os.replace(path, path.1)` (atomar, überschreibt alte `.1`) | Zweite Rotation verdrängt die vorherige `.1` |
| Nebenläufigkeit | `fcntl.flock` auf `<datei>.lock`, Größe unter der Sperre erneut prüfen | Ein uvicorn-Prozess, aber mehrere Threads schreiben; ohne Sperre kann eine doppelte Umbenennung die gerade erzeugte `.1` überschreiben und Zeilen vernichten |
| Fehlerverhalten | eigenes `try/except` um die Rotation, danach wird trotzdem angehängt | Observability darf den Abruf nie beeinträchtigen |
| Go-Lesereihenfolge | **erst** aktuelle Datei öffnen (Deskriptor halten), **dann** `.1`; `.1` überspringen, wenn `os.SameFile` mit der geöffneten aktuellen Datei | Rotiert Python zwischen den beiden Opens, bliebe sonst die gerade umbenannte Datei ungelesen (Fehlalarm) oder würde doppelt gezählt |
| Fehlende Dateien | legitim (kein Fehler) | Frisches Deployment, noch nie rotiert |
| Lesefehler | echter Fehler in aktueller Datei **oder** `.1` setzt `journal_read_error` | Unterscheidung „nie geschrieben" gegenüber „nicht lesbar" (#1422 AC-7) bleibt erhalten |
| Drift-Zähler | bedeuten künftig „Vorkommen im Aufbewahrungsfenster" statt „seit Juli kumulativ" | Der Monitor wertet nur die Frische (Zeitstempel) aus; Go-Kommentar wird angepasst |
| Auslieferung | Python- und Go-Teil im selben PR und Deploy | Die 65-MB-Prod-Datei wird beim ersten Schreiben sofort rotiert; der Go-Leser muss `.1` dann schon kennen |
| Nicht im Scope | Schwesterjournale `openmeteo_calls.jsonl` (22,5 MB), `enrichment_calls.jsonl` (5,6 MB) | Eigener Leser/Schreiber, Folge-Issue #2883 (Epic #2733) |

## Implementation Details

### Python (`warn_egress.py`)

1. Konstante `WARN_JOURNAL_MAX_BYTES = 8 * 1024 * 1024` (Modulebene, per `monkeypatch`
   überschreibbar).
2. Helfer `_rotate_if_needed(path: Path) -> None`:
   - `path.stat().st_size < WARN_JOURNAL_MAX_BYTES` oder Datei fehlt: sofort zurück (schneller
     Pfad ohne Sperre, damit der häufige Fall nichts kostet).
   - Sonst `<path>.lock` öffnen (`"a"`), `fcntl.flock(LOCK_EX)`, Größe **unter der Sperre erneut**
     prüfen; nur wenn immer noch >= Schwelle: `os.replace(path, path.with_name(path.name + ".1"))`.
   - Sperre freigeben (`finally`). Gesamter Helfer in eigenem `try/except Exception: pass`.
3. `log_warn_service_call()` und `log_zone_drift()` rufen `_rotate_if_needed(path)` nach
   `mkdir` und vor dem Append auf. Die bestehende Zeilenstruktur ändert sich nicht.
4. Der Append öffnet die Datei danach neu (`path.open("a")`), schreibt also in die neue
   aktuelle Datei; ein Schreiber, der bereits geöffnet hat, schreibt POSIX-sicher in die
   umbenannte Datei weiter und verliert nichts.

### Go (`warn_service_health.go`)

1. `aggregateWarnServiceCalls(path)` öffnet **zuerst** `path`, **danach** `path + ".1"`.
   Ist `.1` per `os.SameFile` dieselbe Datei wie die bereits geöffnete aktuelle (Rotation
   zwischen den Opens, bzw. Hardlink), wird `.1` übersprungen.
2. Beide Dateien laufen durch dieselbe Zeilenauswertung (gemeinsamer Helfer, keine
   Kopie); die Aggregation nimmt weiterhin je Dienst das Maximum der Zeitstempel, ist also
   unabhängig von der Lesereihenfolge.
3. `os.IsNotExist` bei einer der beiden Dateien: kein Fehler. Anderer Open-Fehler oder
   Scanner-Fehler bei einer der beiden: Rückgabe `readErr = true` (die Aggregate der lesbaren
   Datei bleiben erhalten).
4. Dokumentationskommentar zu `zone_drift`: Zähler = Vorkommen im Aufbewahrungsfenster
   (aktuelle Datei + eine Vorgänger-Generation).

## Expected Behavior

- **Input:** Journalzeile wird angehängt; die aktuelle Datei hat die Schwelle erreicht oder
  überschritten.
- **Output:** Die volle Datei wird zu `warn_service_calls.jsonl.1`, die neue Zeile steht in
  einer frischen `warn_service_calls.jsonl`. Der Status-Endpunkt liefert unverändert dieselben
  Felder je Dienst (`last_attempt_at`, `last_success_at`, `self_throttled`, `zone_drift`).
- **Side effects:** Datei `warn_service_calls.jsonl.lock` entsteht (leer, dauerhaft). Platzbedarf
  des Journals begrenzt auf ca. 2 x Schwelle (plus eine Zeile).

## Definition of Done

- Alle AC-1 bis AC-11 sind durch die Tests im Test Plan belegt (Python- und Go-Tests grün, Mutationsproben vom Adversary gefangen).
- Python- und Go-Teil sind gemeinsam auf Staging und Prod ausgeliefert.
- Auf Prod ist nach dem ersten Schreibvorgang die Bestandsdatei zur Vorgänger-Generation geworden, die aktuelle Datei ist klein, und der Scheduler-Status meldet je Dienst unveränderte Zeitstempel ohne `journal_read_error`.
- Der Warn-Ausfall-Monitor löst nach dem Deploy keinen Fehlalarm aus.

## Acceptance Criteria

- **AC-1:** Given das Journal hat die Schwelle von 8 MB erreicht, When der Warn-Dienst-Abruf die nächste Zeile protokolliert, Then liegt der bisherige Inhalt unverändert in `warn_service_calls.jsonl.1`, und die aktuelle Datei enthält nur die neue Zeile.
- **AC-2:** Given es existiert bereits eine `warn_service_calls.jsonl.1` und die aktuelle Datei erreicht die Schwelle erneut, When die nächste Zeile geschrieben wird, Then ersetzt die zweite Rotation die alte `.1` (deren Inhalt ist weg), es gibt nie eine `.2`, und die Platte hält höchstens ca. das Doppelte der Schwelle.
- **AC-3:** Given das Journal liegt unter der Schwelle, When Zeilen angehängt werden, Then findet keine Rotation statt: keine `.1` entsteht, und alle Zeilen bleiben in der aktuellen Datei in der geschriebenen Reihenfolge.
- **AC-4:** Given mehrere Threads schreiben gleichzeitig Journalzeilen, während die Schwelle überschritten wird, When die Schreiber fertig sind, Then ist keine Zeile verloren und keine doppelt, es wurde nicht doppelt umbenannt (eine zuvor erzeugte `.1` wird nicht von einer zweiten Umbenennung überschrieben), und jede Zeile ist vollständiges, gültiges JSON.
- **AC-5:** Given die Rotation selbst schlägt fehl (z.B. `.1` kann nicht ersetzt werden oder die Sperrdatei ist nicht anlegbar), When ein Warn-Dienst-Abruf protokolliert wird, Then bleibt der Abruf unbeeinträchtigt (keine Exception nach außen), und die Zeile wird trotzdem in die aktuelle Datei geschrieben.
- **AC-6:** Given der letzte erfolgreiche Abruf eines Dienstes steht nur in `.1` (die aktuelle Datei enthält nur danach liegende fehlgeschlagene Versuche), When der Scheduler-Status abgefragt wird, Then meldet `warn_service_health` für diesen Dienst den `last_success_at` aus `.1` und den neueren `last_attempt_at`; es entsteht kein Fehlalarm „kein Erfolg".
- **AC-7:** Given zwischen dem Öffnen der aktuellen Datei und dem Öffnen von `.1` hat eine Rotation stattgefunden (`.1` ist dieselbe Datei wie die geöffnete aktuelle, nachgestellt durch einen Hardlink), When der Status berechnet wird, Then wird der Inhalt nicht doppelt gezählt: Drift-Zähler und Versuchsdaten stimmen mit dem Einmal-Lesen überein.
- **AC-8:** Given es existiert keine `warn_service_calls.jsonl.1` (noch nie rotiert), When der Status abgefragt wird, Then wird dies nicht als Fehler gemeldet (kein `journal_read_error`), und die Aggregation entspricht der bisherigen Auswertung der aktuellen Datei. Ist auch die aktuelle Datei nicht vorhanden, ist das Ergebnis leer und ebenfalls ohne Fehler.
- **AC-9:** Given `.1` existiert, ist aber nicht lesbar (z.B. ein Verzeichnis statt einer Datei), When der Status abgefragt wird, Then meldet `warn_service_health` `journal_read_error: true`, während die Daten der lesbaren aktuellen Datei weiterhin ausgeliefert werden.
- **AC-10:** Given das Prod-Journal ist 65 MB groß (weit über der Schwelle), When nach dem Deploy die erste Zeile geschrieben wird, Then wird der Bestand komplett zu `.1`, die aktuelle Datei beginnt klein, und der Status-Endpunkt liefert unmittelbar danach unveränderte Dienst-Zeitstempel (kein Datenverlust in der Aussage, kein Alarm).
- **AC-11:** Given Zonen-Drift-Zeilen liegen teils in `.1`, teils in der aktuellen Datei, When der Status abgefragt wird, Then zählt `zone_drift` die Vorkommen aus beiden Dateien (Aufbewahrungsfenster), und `last_with_warning_at` / `last_without_warning_at` tragen den jeweils jüngsten Zeitstempel aus beiden Dateien.

## Test Plan (kein Mock-Theater)

Alle Tests arbeiten mit echten Dateien in `tmp_path` und echten Threads. Verboten sind
`Mock()`, `patch()` und `MagicMock`. Die Schwelle wird über `monkeypatch.setattr` auf die
Modulkonstante auf wenige hundert Byte gesenkt, der Pfad über das bestehende
`WARN_CALLS_PATH_OVERRIDE`.

**Python `tests/tdd/test_warn_journal_rotation.py`**

- `test_rotation_bei_schwelle` (AC-1): Datei bis Schwelle füllen, `log_warn_service_call()`
  aufrufen; `.1` hat den alten Inhalt byte-gleich, aktuelle Datei genau eine neue Zeile.
- `test_unter_schwelle_keine_rotation` (AC-3).
- `test_zweite_rotation_verdraengt_alte_generation` (AC-2): zweimal füllen; `.1` enthält nur
  Generation 2, keine `.2`, Gesamtgröße <= 2 x Schwelle + eine Zeile.
- `test_parallele_schreiber_verlieren_keine_zeile` (AC-4): z.B. 8 Threads x 200 Zeilen mit
  kleiner Schwelle über `threading.Barrier`; Zeilen aus aktueller Datei + `.1` zusammen
  ergeben alle IDs genau einmal, soweit sie nicht von einer legitimen zweiten Rotation
  verdrängt wurden (Schwelle so wählen, dass insgesamt höchstens eine Rotation nötig ist:
  Schwelle > Gesamtvolumen / 2), und alle Zeilen sind gültiges JSON.
- `test_rotationsfehler_ist_fail_soft` (AC-5): `.1` als nicht ersetzbares Verzeichnis mit
  Inhalt anlegen (echter `os.replace`-Fehler); der Aufruf wirft nicht und die neue Zeile steht
  in der aktuellen Datei. Zusätzlich: Sperrdatei-Pfad als Verzeichnis angelegt.
- `test_log_zone_drift_rotiert_ebenfalls` (AC-1 für die zweite Schreibfunktion).
- `test_bestand_ueber_schwelle_wird_beim_ersten_schreiben_rotiert` (AC-10): Datei mit
  mehrfacher Schwelle vorbelegen, ein Aufruf, `.1` hat den Bestand.

**Go `internal/scheduler/warn_service_health_test.go`** (echte Dateien in `t.TempDir()`,
Aufruf von `aggregateWarnServiceCalls` und `Scheduler.WarnServiceHealth()` mit echter
`DataDir`)

- `TestWarnServiceHealth_LetzterErfolgNurInEins` (AC-6).
- `TestWarnServiceHealth_NurEinsOhneAktuelle` (AC-6, AC-8): aktuelle Datei fehlt, `.1` da.
- `TestWarnServiceHealth_KeineEins` (AC-8): ohne `.1` identisch zum Bestandsverhalten.
- `TestWarnServiceHealth_LesefehlerInEins` (AC-9): `.1` als Verzeichnis ⇒ `journal_read_error`.
- `TestWarnServiceHealth_HardlinkEinsGleichAktuell` (AC-7): `os.Link(aktuell, aktuell+".1")`,
  Zähler nicht verdoppelt.
- `TestWarnServiceHealth_DriftUeberBeideDateien` (AC-11).
- Bestehende Go-Tests (#1422, #1434) bleiben unverändert grün (Regressionsschutz).

Mutationsproben für den Adversary: Wegfall des erneuten Größen-Checks unter der Sperre (AC-4),
Wegfall von `os.SameFile` (AC-7), Lesereihenfolge `.1` zuerst (AC-6), `.1`-Lesefehler
verschluckt (AC-9) und Wegfall des `try/except` (AC-5) müssen je mindestens einen Test rot
machen.

## Known Limitations

- Nach der ersten Prod-Rotation liest Go einmalig die 65-MB-`.1` bei jedem Status-Abruf, bis
  die zweite Rotation sie verdrängt (ca. 13 Tage). Akzeptiert, da kleiner als der heutige
  Zustand und einmalig.
- Zwischen Python-Neustart und Go-Neustart beim Deploy kann ein Restfenster im
  Sekundenbereich entstehen; es ist deutlich kleiner als das 3h-Monitorfenster und daher
  unkritisch.
- Der Rückblick der Drift-Zähler und der Verbrauchsmessung (#1397) beträgt nur noch 13 bis
  26 Tage (je nach Zeitpunkt der Rotation).
- Die Cache-Treffer-Zeilen (Masse des Journals) werden weiterhin geschrieben; die
  Journal-Semantik ändert sich nicht.
- Schwesterjournale (`openmeteo_calls.jsonl`, `enrichment_calls.jsonl`) bleiben unrotiert,
  Folge-Issue #2883.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Betrifft nur Aufbewahrung und Lesepfad eines internen Diagnose-Journals;
  keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor, Test-/Deploy-Strategie)
  wird berührt. Das Monitor-Verhalten (#1422, #1434) bleibt fachlich gleich.

## Changelog

- 2026-11-09: Initial spec (Issue #2224)
