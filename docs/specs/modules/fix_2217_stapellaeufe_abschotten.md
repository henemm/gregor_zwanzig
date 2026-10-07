---
entity_id: fix_2217_stapellaeufe_abschotten
type: module
created: 2026-10-06
updated: 2026-10-06
status: approved
version: "1.0"
tags: [scheduler, radar, alarm, fehler-isolation, panic, stapellauf]
---

<!-- Issue #2217 (abgespalten aus #1199, Einträge C1-63 und B2-49), Epic #2505
     „Versand-Zuverlässigkeit". Formatvorbild:
     docs/specs/modules/fix_1752_radar_folgt_alarm_kanaelen.md -->

# Stapelläufe abschotten: Go-Scheduler ohne Panic-Schutz, Radar-Alarmlauf reißt für Folge-Trips ab

## Approval

- [x] Approved (PO, 2026-10-07: „freigabe“)

## Purpose

Zwei Stellen, an denen **ein einziger** Fehler alle anderen mitreißt:

1. **Go-Scheduler (C1-63).** `cron.New(cron.WithLocation(loc))` ohne `cron.Recover`. In
   `robfig/cron/v3` läuft jeder Job in einer eigenen Goroutine; eine unbehandelte Panic dort
   **beendet den ganzen `gregor-api`-Prozess** — Auth, API, alle Jobs, alle Nutzer, bis systemd
   neu startet. Dasselbe gilt für die Goroutine je Nutzer-Aufruf in `callUserWithBudget()`
   (`scheduler.go:483`): eine Panic beim Aufruf für EINEN Nutzer beendet den Prozess für alle.
2. **Radar-Alarmlauf (B2-49).** In `_check_radar_trips()` (`src/services/trip_alert.py`)
   stehen `trip_local_today()` und `_resolve_alert_segment()` (→ `backfill_stage_distances`,
   `resolve_current_segment`) ungeschützt in der Trip-Schleife. Wirft einer davon für einen
   Trip mit beschädigten Daten, verlieren **alle folgenden Trips dieses Nutzers** ihren
   Regen-Alarm — bei jedem 5-Minuten-Tick erneut, bis die Daten repariert sind. Die
   Kanal-Auflösung ein paar Zeilen weiter ist bereits je Trip abgesichert (#1752 F001); diese
   Scheibe zieht die zwei Aufrufe davor auf dasselbe Muster.

Nutzersicht: ein Regen-Alarm, der nicht kommt, obwohl Regen naht — und dass ein Fehler eines
anderen Nutzers/Trips den eigenen Alarm verhindert.

## Source

- **File:** `internal/scheduler/scheduler.go` — `New()`, `recordRun()`, `callUserWithBudget()`
- **File:** `src/services/trip_alert.py` — `TripAlertService._check_radar_trips()`

## Estimated Scope

- **LoC:** ~40 Produktivcode + Tests
- **Files:** 2 Produktiv, 2 Testdateien (Go + Python)
- **Effort:** low

## Lösung

**Go:**
- `recordRun()` fängt eine Panic aus `fn()` per `defer recover()` ab, verbucht den Lauf als
  `status: "error"` mit `error: "panic: <Wert>"` in `lastRuns[jobID]` und loggt den Stacktrace.
  Die Job-Sperre wird freigegeben (bestehendes `defer lock.Unlock()`), der nächste Tick läuft
  normal. Damit ist die Panic im Status-Endpoint sichtbar (Observability-Pflicht), nicht nur im Log.
- Die Goroutine in `callUserWithBudget()` fängt eine Panic aus `triggerEndpointForUser` ab und
  liefert sie als normalen Fehler über `resultCh` — der Nutzer zählt als fehlgeschlagen, die
  übrigen Nutzer desselben Laufs werden weiter bedient.
- Äußeres Netz: `cron.New(cron.WithLocation(loc), cron.WithChain(cron.Recover(...)))` für Code,
  der außerhalb von `recordRun()` läuft.

**Python:** die beiden Aufrufe `trip_local_today()` und `_resolve_alert_segment()` in
`_check_radar_trips()` bekommen je Trip eine breite `except Exception`-Klausel mit
`logger.error(... trip.id ...)` und `continue` — identisch zum bestehenden Muster der
Kanal-Auflösung. Der Fortschrittsstempel des Trips bleibt gesetzt (er wurde erreicht).

## Bewusst nicht in dieser Scheibe

- **`cron.SkipIfStillRunning`.** Verworfen: `recordRun()` hat seit #1447 S2a eine eigene
  TryLock-Sperre je Job, die übersprungene Ticks im Status-Endpoint zählt (`overlap`).
  `SkipIfStillRunning` würde davor greifen und Ticks **still** verschlucken — die Zählung
  ginge verloren. Der Issue-Punkt ist durch die bestehende Sperre bereits abgedeckt.
- **Andere Python-Stapelläufe** (Gewitter-/Änderungs-/amtliche Alarme, Compare). Nicht Teil
  der Triage-Einträge; ggf. eigener Sammel-Eintrag in #1199.
- **Datenreparatur** des auslösenden beschädigten Trips — der Trip bleibt übersprungen und
  laut geloggt, bis er repariert ist.

## Acceptance Criteria

**AC-1:** Given ein Scheduler-Job, dessen Lauf-Funktion eine Panic auslöst / When der Job über `recordRun()` ausgeführt wird / Then läuft der Prozess weiter, der Job steht im Status als `error` mit einer Fehlermeldung, die mit `panic:` beginnt, und ein zweiter Aufruf desselben Jobs wird tatsächlich ausgeführt (die Sperre ist frei).

**AC-2:** Given ein Job-Fan-out über zwei Nutzer, bei dem der Aufruf für den ersten Nutzer eine Panic auslöst / When der Lauf ausgeführt wird / Then läuft der Prozess weiter, der erste Nutzer wird als fehlgeschlagen gewertet und der zweite Nutzer wird trotzdem bedient.

**AC-3:** Given der Scheduler ist mit `New()` erzeugt / When ein über den Cron-Takt gestarteter Eintrag außerhalb von `recordRun()` eine Panic auslöst / Then fängt die Cron-Kette sie ab und der Prozess läuft weiter.

**AC-4:** Given zwei Trips desselben Nutzers, von denen der erste beschädigte Daten trägt, an denen die Ortstag-Bestimmung oder die Segment-Auswahl echt scheitert / When der Radar-Alarmlauf läuft / Then wird nur dieser Trip übersprungen (mit Fehler-Log, das seine Trip-ID nennt), der zweite Trip wird geprüft und hinterlässt seinen Protokoll-Eintrag im echten `alert_log.json`.

**AC-5:** Given der Radar-Alarmlauf überspringt einen Trip wegen eines solchen Fehlers / When der Lauf endet / Then zählt der Trip als erreicht (`checked` und Fortschrittsstempel), damit er die faire Reihenfolge nicht dauerhaft an die Spitze drängt und andere Trips verdrängt.

## Tests

- Go: `internal/scheduler/job_panic_isolation_test.go` (AC-1 bis AC-3), ohne Mock des
  Prüflings — echte Panic in der Job-Funktion bzw. im Nutzer-Aufruf (httptest-Server, der die
  Verbindung kappt, reicht nicht für eine Panic; Naht ist die Job-Funktion selbst).
- Python: neuer Test in `tests/unit/test_radar_alert_channel_resolution.py`-Stil
  (`tests/unit/test_radar_alert_trip_isolation.py`), beschädigte Etappendaten erzeugen den
  Fehler echt, Nachweis über `alert_log.json` von Trip B (Prüfort = Wirkort).

## Changelog

- 2026-10-07: ACs vom PO freigegeben
