---
entity_id: fix-1897-verwaister-briefing-slot
type: module
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [briefing, alert-gate, idempotenz, bugfix]
---

# Verwaister Briefing-Slot nach hartem Prozessende (#1897)

## Approval

- [x] Approved — PO, 2026-08-16 ('go')

## Purpose

Ein Briefing-Versand, der durch ein hartes Prozessende (Deploy, SIGKILL, OOM, Crash) mitten im
Lauf abbricht, hinterlässt im Slot-Speicher einen Claim mit `outcome: null`, der heute fälschlich
als „erledigt" zählt. In Produktion (Trip KHW `5f534011`) ist das am 14.08.2026 (evening) und
16.08.2026 (morning) tatsächlich eingetreten: das Briefing blieb für den Rest des Ortstags aus,
und die Alarm-Vorlauf-Sperre aus #1594 hob sich fälschlich auf, obwohl nie ein Briefing kam.

## Source

- **File:** `src/services/briefing_slots.py`
- **Identifier:** `class BriefingSlotStore` — Methoden `is_recorded()`, `reserve()`,
  `record_outcome()`, `release()`

Zusätzlich betroffen (Aufrufer, dieselbe Schicht):

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `_collect_due_trips()`, `trip_briefing_due_at()`, `_dispatch_due_item()`

- **File:** `src/services/dispatch_orchestrator.py`
- **Identifier:** `dispatch_one()` — reicht `now_utc` an `_dispatch_due_item()` durch

> **Schicht-Hinweis:** Alle drei Dateien liegen im Python-Core (`src/services/...`, FastAPI-Domäne).
> Es gibt keine Go- oder Frontend-Beteiligung: `internal/handler/cockpit.go` liest ausschließlich
> `briefing_log.json`, nicht `briefing_slots.json`, und der Go-Cron-Takt
> (`internal/scheduler/scheduler.go:141`) bleibt unverändert — der Nachhol-Mechanismus existiert
> bereits, es braucht keinen neuen Auslöser.

## Estimated Scope

- **LoC:** ~145–220 (Produktiv ~55–80, Test ~90–140) — unter dem 250er-Workflow-Limit, aber ohne
  Reserve. Wird es enger, ist Kürzung des Nachweises **nicht** der Ausweg, sondern Rückfrage beim PO.
- **Files:** 6 (3 Produktiv, 2 Test, 1 Spec-Nachtrag)
- **Effort:** medium — Risiko MEDIUM, weil der Doppelversand-Pfad (`reserve()`) berührt wird,
  aber nur um eine Alters-Bedingung unter der bestehenden Sperre ergänzt, nicht neu aufgebaut.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `BriefingSlotStore` (`src/services/briefing_slots.py`) | module | Persistenter Slot-Speicher (`briefing_slots.json`), Doppelversand-Schutz via `reserve()` unter Sidecar-Sperre; wird um `CLAIM_TTL`, Übernahme-Logik und ein zweites Prädikat erweitert. |
| `check_briefing_imminent` (#1594, `src/services/alert_gate.py:200-300`) | function | UND-Bedingung der Alarm-Vorlauf-Sperre; Bedingung 1 hängt an `trip_briefing_due_at()`, dessen Antwort sich mit dieser Spec ändert (offener Claim = „Briefing steht noch aus"). |
| `_process_pending_markers` (#1012, `src/services/trip_report_scheduler.py`) | function | Nachliefer-Marker-Mechanismus; liest über `dispatch_orchestrator.py:66-67` dieselbe `due_trip_ids_now`-Menge, die `_collect_due_trips()` liefert. Eine unehrlich lange oder kurze Liste legt diesen Mechanismus lautlos still — daher das zweite, eigenständige Prädikat statt einer Vereinheitlichung mit `is_recorded()`. |
| Briefing-Anker (`src/services/alert_briefing_anchor.py:215-230`, `last_briefing_at()`) | function | Bedingung 2 der Alarm-Sperre; wird von `_anchor_and_reset()` erst **nach** dem Versandaufruf gesetzt (`trip_report_scheduler.py:1521-1527`) und bleibt daher im Crash-Fall korrekt leer — unverändert durch diese Spec. |

## Implementation Details

**Drei Zustände statt zwei.** Ein Eintrag im Slot-Speicher ist heute entweder „nicht vorhanden"
oder „erledigt" (jeder gefundene Eintrag zählt, `briefing_slots.py:78`). Neu werden drei Zustände
unterschieden:

1. **Abgeschlossen** — `outcome` ist gesetzt, also nicht `null`. In der Praxis ist das immer
   einer der vier Werte aus `VERMERK_AUSGAENGE` (`trip_report_scheduler.py:94`: `sent`,
   `no_stage`, `no_weather`, `no_channels`); die Regel prüft aber bewusst nur „gesetzt" und
   nicht die Zugehörigkeit zu dieser Menge — sonst entschiede der Speicher über die
   Ausgangs-Auswahl des Schedulers mit und ein künftiger fünfter Ausgang fiele still auf
   „nicht erledigt" zurück. Dazu die bestehende Rückwärts-Ableitung aus `briefing_log.json`
   (unverändert).
2. **Lebendig in Arbeit** — `outcome: null`, `recorded_at` jünger als `CLAIM_TTL` gegenüber dem
   übergebenen Zeitpunkt. Ein Versand läuft real oder ist so kürzlich gestartet, dass er noch
   laufen kann.
3. **Verwaist** — `outcome: null`, `recorded_at` älter als `CLAIM_TTL`. Der Prozess ist mit hoher
   Wahrscheinlichkeit hart beendet worden, bevor er abschließen konnte.

**Die beiden Wirkorte stellen unterschiedliche Fragen und bekommen unterschiedliche Antworten:**

| Wirkort | Frage | Antwort bei offenem Claim (Zustand 2/3) |
|---|---|---|
| `_collect_due_trips()` (`trip_report_scheduler.py:553`) | „Wird jetzt ein Versand stattfinden?" | **lebendig:** nein (läuft ja gerade, Trip fehlt in der Fälligkeitsliste) · **verwaist:** ja (Trip steht wieder in der Liste) |
| `trip_briefing_due_at()` (`trip_report_scheduler.py:196`) | „Steht für diesen Slot noch ein Briefing aus (Alarm-Sperre)?" | **immer ja**, unabhängig vom Alter — solange `outcome` nicht gesetzt ist, kam nichts raus, die Alarm-Sperre aus #1594 muss halten |

Konkret:

- **`is_recorded(...)` wird zu „abgeschlossen"** — nur `outcome`-gesetzte Einträge (und die
  Rückwärts-Ableitung) zählen. Aufrufer: `trip_briefing_due_at()`.
- **Ein zweites, eigenständig benanntes Prädikat = „abgeschlossen ODER lebendig in Arbeit"** —
  zusätzlich Einträge mit `outcome: null` und `recorded_at` jünger als `CLAIM_TTL`. Aufrufer:
  `_collect_due_trips()`. Hält die Fälligkeitsliste ehrlich gegenüber `_process_pending_markers`
  (#1012) und lässt offene Nachliefer-Marker nicht verfallen.
- **`reserve(..., moment)` bekommt einen Pflicht-Zeitparameter** (ADR-0051 Regel 3, kein
  `datetime.now()`-Rückfall) und übernimmt einen fremden offenen Claim, wenn dessen `recorded_at`
  älter als `CLAIM_TTL` gegenüber `moment` ist: neues `recorded_at`, `outcome` bleibt `null`. Ein
  jüngerer Claim blockiert weiter wie heute (`_find` verweigert die Reservierung,
  `briefing_slots.py:92-93`).
- **Altersprüfung und Übernahme MÜSSEN in derselben Sperren-Closure liegen** — der bestehenden
  `_update()`-Operation unter der Sidecar-Datei-Sperre (`services/file_lock.acquire_exclusive`).
  Ein getrennter Lese-dann-Schreib-Schritt (erst Alter prüfen, dann später schreiben) würde zwei
  gleichzeitigen Läufen erlauben, denselben verwaisten Claim beide für sich zu beanspruchen —
  genau der teure Doppelversand-Pfad, den `reserve()` heute schon verhindert.
- **`_dispatch_due_item()` reicht `now_utc` durch** an `reserve()`; `dispatch_orchestrator.py`
  reicht denselben Zeitpunkt von `dispatch_one()` weiter — ein einziger, konsistenter Moment pro
  Lauf statt mehrerer `now()`-Aufrufe.
- **Zugestellt-aber-nicht-vermerkt-Fall:** Stirbt der Prozess zwischen erfolgreichem Versand und
  `record_outcome()`, ist die Mail bereits draußen, obwohl der Claim verwaist erscheint.
  `briefing_log.json` erhält den Eintrag bereits **vor** dem Anker
  (`trip_report_scheduler.py:1623`); die Übernahme-Logik nutzt den bestehenden Leser
  `_log_bezeugt_versand`, um in diesem Fall den Claim direkt als `sent` abzuschließen statt einen
  Doppelversand auszulösen.

**`CLAIM_TTL` als Modul-Attribut**, analog zu `LOCK_TIMEOUT_SECONDS`, zur Laufzeit lesbar (damit
Tests die Frist unterschreiten können):

```python
CLAIM_TTL = 900  # Sekunden (15 min)
```

Begründung, gemessen an 22 realen Versandläufen des Trips KHW (05.–15.08.2026):

- **Untergrenze:** > 319 s — der längste real gemessene Einzelversand (11.08. abends,
  Zeitraum 11.–15.08.: 218–319 s; Zeitraum 05.–10.08.: 54–93 s).
- **Obergrenze:** < 1 h — der Abstand zweier Cron-Ticks (`internal/scheduler/scheduler.go:141`,
  `0 * * * *`); darüber wirkt die Frist nie, weil der nächste Übernahme-Versuch ohnehin erst zur
  vollen Stunde stattfindet.
- **Gewählt: 900 s** — knapp dreifacher Abstand zum gemessenen Maximum. Da der nächste
  Reserve-Versuch ohnehin erst zur vollen Stunde erfolgt, verhält sich jeder Wert zwischen 10 und
  50 Minuten am nächsten Tick identisch; 900 s liegt komfortabel in dieser Zone.

## Expected Behavior

- **Input:** Zeitstempel des Lauf-Moments (`now_utc`), Trip-ID, Slot-Schlüssel (`local_day`, `slot`),
  bestehender Zustand von `briefing_slots.json`.
- **Output:** korrekte Fälligkeits-Antwort an `_collect_due_trips()` und `trip_briefing_due_at()`
  gemäß den drei Zuständen; bei Übernahme eines verwaisten Claims ein aktualisierter Eintrag mit
  neuem `recorded_at` und `outcome: null`, gefolgt vom Versand.
- **Side effects:** Schreibzugriff auf `briefing_slots.json` unter Sidecar-Datei-Sperre; bei
  Übernahme eines Claims, der laut `briefing_log.json` bereits zugestellt wurde, direkter Abschluss
  mit `outcome: sent` statt erneutem Versand.

## Acceptance Criteria

- **AC-1:** Given ein Morgen-Briefing wurde um 07:00 Ortszeit begonnen und der Prozess endete davor hart, sodass ein Vermerk ohne Ausgang zurückbleibt / When der nächste stündliche Lauf um 08:00 Ortszeit läuft / Then wird das Briefing verschickt und der Vermerk trägt danach den Ausgang `sent`.
  - Test: Nutzersicht-Test über die reale Scheduler-Unterklasse (Muster aus `tests/tdd/test_briefing_slot_idempotenz.py`): Claim mit `outcome: null` und `recorded_at` älter als `CLAIM_TTL` vorbereiten, Lauf mit `now_utc = 08:00` ausführen, prüfen dass der Versandkanal aufgerufen wurde und `record_outcome` mit `"sent"` geschrieben wurde — nicht per Dateiinhalt-Grep, sondern über den beobachtbaren Versandaufruf.

- **AC-2:** Given für einen Trip steht ein Briefing im Fälligkeitsfenster an und es liegt ein Vermerk ohne Ausgang vor, weil der Versand läuft oder abgebrochen ist / When im selben Zeitraum ein Änderungs-Alarm ausgewertet wird / Then wird der Alarm nicht als eigenständige Nachricht verschickt, weil das Briefing noch aussteht.
  - Test: `check_briefing_imminent()` (#1594) mit offenem Claim (`outcome: null`, beliebiges Alter) und geänderten Wetterdaten aufrufen; prüfen, dass die Alarm-Sperre greift und kein separater Alarm-Versand ausgelöst wird — Nachbar zu R6 in `tests/tdd/test_trip_alert_briefing_imminent.py`.

- **AC-3:** Given ein Vermerk ohne Ausgang ist jünger als `CLAIM_TTL`, der Versand läuft also noch / When ein zweiter Lauf denselben Slot reservieren will / Then verweigert die Reservierung und es findet kein zweiter Versand statt.
  - Test: Claim mit `recorded_at = now - 100s` (< `CLAIM_TTL`) setzen, den Versand über die reale Scheduler-Unterklasse anstoßen; prüfen, dass `reserve()` `False` liefert (keine Ausnahme, fail-closed wie heute) und kein zweiter Versandaufruf am Kanal ankommt.

- **AC-4:** Given ein Vermerk ohne Ausgang ist älter als `CLAIM_TTL` / When ein Lauf denselben Slot reservieren will / Then wird der Vermerk übernommen, sein Zeitstempel auf den neuen Zeitpunkt gesetzt, und der Versand findet statt.
  - Test: Claim mit `recorded_at = now - 1000s` (> `CLAIM_TTL`) setzen, `reserve(..., moment=now)` aufrufen, prüfen dass die Reservierung gelingt, `recorded_at` auf `now` aktualisiert wird und der anschließende Versand ausgeführt wird.

- **AC-5:** Given ein Vermerk ohne Ausgang ist älter als `CLAIM_TTL`, aber das Briefing-Protokoll weist für denselben Trip, dieselbe Slot-Art und denselben Ortstag einen regulären Versand aus / When ein Lauf den Slot reservieren will / Then findet kein erneuter Versand statt.
  - Test: verwaisten Claim (`outcome: null`, älter als `CLAIM_TTL`) UND einen passenden `briefing_log.json`-Eintrag (`_log_bezeugt_versand` liefert True) vorbereiten; `reserve(..., moment=now)` aufrufen; prüfen, dass kein Versandkanal-Aufruf erfolgt und der Claim stattdessen direkt mit `outcome: sent` abgeschlossen wird.

- **AC-6:** Given ein Vermerk ohne Ausgang ist jünger als `CLAIM_TTL` / When die Fälligkeitsliste zusammengestellt wird / Then steht der Trip nicht darin, sodass ein offener Nachliefer-Marker aus #1012 nicht verfällt.
  - Test: Claim jünger als `CLAIM_TTL` vorbereiten, offenen #1012-Nachliefer-Marker für denselben Trip setzen, `_collect_due_trips()` aufrufen; prüfen dass der Trip fehlt UND dass der Marker nach dem Lauf weiterhin offen ist (nicht durch `_process_pending_markers` verfallen).

- **AC-7:** Given zwei Läufe versuchen im selben Augenblick, denselben verwaisten Vermerk zu übernehmen / When beide reservieren wollen / Then übernimmt genau einer, der andere sendet nicht.
  - Test: Gleichzeitigkeit über `threading.Barrier` erzwingen, niemals über Wartezeiten oder die Uhr — zwei Threads rufen `reserve(..., moment=now)` auf denselben verwaisten Claim gleichzeitig auf (synchronisiert per Barrier direkt vor dem Aufruf), Assertion dass genau ein Thread die Reservierung erhält und nur ein Versandaufruf protokolliert wird.

- **AC-8:** Given Bestandseinträge, die vor dieser Änderung geschrieben wurden / When sie gelesen werden / Then verhalten sich abgeschlossene Vermerke unverändert und es ist keine Datenmigration nötig.
  - Test: Fixture mit den vier Prod-Vermerk-Formen (`sent`, `no_stage`, `no_weather`, `no_channels`) aus dem bestehenden Schema (`_eintrag()`, `briefing_slots.py:136-144`, trägt bereits `recorded_at`) ohne jede Migration einlesen; prüfen, dass `is_recorded()` für alle vier weiterhin `True` liefert und kein Schreibzugriff zur Migration erfolgt.

- **AC-9:** Given der Abbruch geschah so spät, dass beim nächsten stündlichen Lauf das dreistündige Nachhol-Fenster bereits vorbei ist / When dieser Lauf läuft / Then wird das Briefing nicht mehr nachgeholt und die Alarm-Sperre gilt für diesen Slot nicht mehr.
  - Test: verwaisten Claim mit `recorded_at` außerhalb von `NACHHOL_FENSTER_STUNDEN = 3` (`trip_report_scheduler.py:106`) vorbereiten, Lauf mit passendem `now_utc` ausführen; prüfen dass `_collect_due_trips()` den Trip nicht mehr liefert UND dass `check_briefing_imminent()` für diesen Slot keine Sperre mehr meldet (Alarm darf wieder eigenständig raus).

## Known Limitations

- **Nachhol-Grenze am Fensterende (AC-9).** Ein verwaister Claim wird nach der Übernahme wieder
  dem regulären 3-Stunden-Fenster (`NACHHOL_FENSTER_STUNDEN`) unterworfen. Ein um 07:00
  abgebrochenes Morgen-Briefing kommt beim 08:00-Lauf nach, ein um 09:30 abgebrochenes gar nicht
  mehr für diesen Slot. Das ist eine bewusste, im Kontext-Dokument geprüfte Grenze, kein
  unentdeckter Defekt.
- **Mögliche Verzögerung einer Änderungsmeldung um bis zu eine Stunde.** Die Alarm-Sperre hält
  künftig auch während der 1–5 Minuten, die ein realer Versand dauert, und nach einem
  abgebrochenen Versand bis zum nächsten Nachhol-Versuch. Eine Änderungsmeldung kann dadurch bis
  zu einer Stunde später ankommen. Das ist keine neue Nebenwirkung, sondern die konsequente
  Anwendung der bereits getroffenen Entscheidung aus ADR-0009/#1594 („ersetzt, nicht
  verschluckt").
- **Der Ortsvergleichs-Pfad ist nicht betroffen.** `compare_alert.py` und
  `compare_official_alert.py` rufen `check_briefing_imminent()` mit einem eigenen Prädikat auf und
  benutzen `BriefingSlotStore` heute nicht (#1777 ist die offene Scheibe, die den Vergleich
  anschließen würde). Die Korrektur sitzt bewusst im geteilten Store statt im Trip-Scheduler, damit
  sie automatisch trägt, sobald #1777 umgesetzt ist.
- **Der auslösende Deploy-Zeitpunkt wird hier nicht behandelt.** Ob und wie Deploys den Prozess
  während eines laufenden Versands beenden, ist eine Frage der Infrastruktur (`henemm-infra`) und
  bleibt getrennt — dieses Fix bleibt unabhängig davon gültig, weil Crash/OOM/Neustart jederzeit
  eintreten können, nicht nur bei Deploys.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (neue) — ADR-0051 und ADR-0044 werden eingehalten, nicht abgelöst.
- **Rationale:** ADR-0051 Regel 3 verlangt, dass jede neue Ablaufprüfung einen übergebenen
  Zeitpunkt als Pflicht-Parameter nimmt statt auf `datetime.now()` zurückzufallen — genau so ist
  `reserve(..., moment)` und die Verwaisungs-Prüfung in dieser Spec entworfen, damit Tests die
  `CLAIM_TTL`-Grenze deterministisch über `threading.Barrier` und feste Zeitpunkte statt über
  Wartezeiten oder die Systemuhr steuern können. ADR-0044 (Kalendertage folgen der Ortszeit) ist
  unberührt, weil die Slot-Schlüssel (`local_day`, `slot`) unverändert bleiben — nur die
  Zustandslogik innerhalb eines Slots wird um eine Alters-Dimension ergänzt. Die
  Entscheidung von #1725 (`fix_1725_faelligkeit_und_idempotenz.md`: reserve-then-release,
  fail-closed, vier Ausgänge setzen den Vermerk) wird dadurch **präzisiert, nicht abgelöst**: der
  Doppelversand-Schutz bleibt in `reserve()`, fail-closed bleibt die Fehlerrichtung — ergänzt wird
  einzig, dass ein hinreichend alter offener Claim keine dauerhafte Blockade mehr ist. Die
  #1725-Spec wird als eigener Scope-Eintrag (`docs/specs/modules/fix_1725_faelligkeit_und_idempotenz.md`,
  MODIFY) um die Verwaisungs-Regel nachgetragen.

## Changelog

- 2026-08-16: Initial spec created (Issue #1897)
