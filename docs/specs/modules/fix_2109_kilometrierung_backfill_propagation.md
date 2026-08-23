---
entity_id: fix_2109_kilometrierung_backfill_propagation
type: bugfix
created: 2026-08-23
updated: 2026-08-23
status: draft
version: "1.0"
tags: [trip-report-scheduler, backfill, track-resolution, persistence]
workflow: fix-2109-kilometrierung-verlust
---

# Nachgerüstete Kilometrierung geht in der Ausblick-Schleife wieder verloren

## Approval

- [ ] Approved

## Purpose

`_convert_trip_to_segments()` lässt intern `backfill_stage_distances()` den Trip nachträglich
vermessen und persistiert das Ergebnis via `save_trip()` — gibt das aktualisierte Trip-Objekt aber
ausschließlich als lokale Variable zurück, nicht an den Aufrufer. Vier Aufrufstellen arbeiten
danach mit dem STALE `trip`-Objekt weiter. Da `save_trip()` Listen (u. a. `stages`) beim
Read-Modify-Write-Merge wholesale ersetzt statt elementweise zu mergen, überschreibt jeder
nachfolgende Save mit dem stale `trip` eine bereits persistierte Kilometrierung wieder mit dem
alten Stand. Diese Spec führt das aktualisierte Trip-Objekt an allen betroffenen Aufrufstellen
zurück in die lokale Variable, damit nachfolgende Saves nicht rückwirkend Daten verlieren.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `_convert_trip_to_segments()` (:1980-2028), `_build_report()` (:1248, :1258),
  `_build_stage_trend()` (:2396), `_collect_future_stage_weather()` (:2854)

> **Schicht-Hinweis:** Python-Core / Domain-Backend (`src/services/`). Kein Go- und kein
> Frontend-Anteil — reiner Kontrollfluss-Fix innerhalb bestehender Methoden, kein neues Datenfeld,
> keine Schema-Änderung.

## Estimated Scope

- **LoC:** ~25-35 Produktivcode
- **Files:** 2 (`src/services/trip_report_scheduler.py`, 1 neue Testdatei unter `tests/tdd/`)
- **Effort:** medium — mechanischer Fix an vier Stellen, aber der Wächter muss echte
  Mehrfach-Iteration über den persistierten Zustand nachweisen, nicht nur den Rückgabewert einer
  einzelnen Methode.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/track_resolution.py` (`backfill_stage_distances`) | module | Baut per `dataclasses.replace` ein neues Trip-Objekt, persistiert bei `persist=True`, gibt das neue Objekt zurück. Fail-soft, idempotent — bleibt unverändert |
| `src/app/loader.py` (`save_trip`, `_deep_merge_preserve_unknown`) | module | Read-Modify-Write mit Merge; ersetzt Listen (`stages`) wholesale, nicht elementweise (#2058) — der Mechanismus, der den stale Stand über bereits Persistiertes schreibt. Bleibt unverändert |
| `src/services/trip_report_scheduler.py` (`self.persist_backfill`) | attribute | Bestehendes Instanz-Attribut-Steuerungsmuster für dieselbe Methode — Vorbild für den neuen Seitenkanal `self._last_converted_trip` |
| `tests/tdd/test_outlook_scheduler_wires_hiking_window.py` (:47-51) | test | Überschreibt `_convert_trip_to_segments` in einer Unterklasse mit fester 2-Positional-Argument-Signatur — muss unverändert funktionieren (kein `TypeError`, kein Übernehmen eines fremden `trip`) |
| `tests/tdd/test_preview_does_not_mutate_trip_data.py` | test | Etabliert den `persist=False`-Preview-Pfad (#2036 CI-Nachschlag) — darf durch diesen Fix nicht wieder brechen |

## Implementation Details

**Kein Signaturwechsel von `_convert_trip_to_segments`.** Begründung: ~20 Testdateien rufen
`svc._convert_trip_to_segments(trip, date)` direkt auf und erwarten eine reine
`List[TripSegment]`; mindestens ein Test (`test_outlook_scheduler_wires_hiking_window.py:47-51`)
überschreibt die Methode in einer Unterklasse mit fester 2-Positional-Argument-Signatur — ein
zusätzliches Argument an der Aufrufstelle würde diesen Override mit `TypeError` brechen. Sowohl
Rückgabetyp als auch Aufrufsignatur bleiben deshalb unangetastet.

**Mechanismus: Instanz-Attribut als Seitenkanal**, passend zum bestehenden Muster
(`self.persist_backfill` steuert bereits heute dieselbe Methode auf identische Art):

In `_convert_trip_to_segments`, Ersatz für Zeile 2025-2028:

```python
if user_id:
    trip = backfill_stage_distances(trip, user_id, target_date, persist=effective_persist)
self._last_converted_trip = trip
return convert_trip_to_segments(trip, target_date)
```

An jeder der vier betroffenen Aufrufstellen (`_build_report` :1248, `_build_report` :1258 als
Test-Fallback, `_build_stage_trend` :2396, `_collect_future_stage_weather` :2854) unmittelbar um
den bestehenden Aufruf:

```python
self._last_converted_trip = None
segments = self._convert_trip_to_segments(trip, stage.date)  # bzw. target_date
if self._last_converted_trip is not None:
    trip = self._last_converted_trip
```

**Warum das Reset auf `None` vor jedem Aufruf zwingend ist:** Wird `_convert_trip_to_segments` in
einer Unterklasse überschrieben (wie im genannten Test), läuft der Seitenkanal nie —
`self._last_converted_trip` bliebe sonst auf dem Wert eines FRÜHEREN, nicht überschriebenen
Aufrufs stehen, und der Aufrufer würde fälschlich ein fremdes `trip`-Objekt aus einem anderen
Kontext übernehmen. Das Zurücksetzen auf `None` unmittelbar vor jedem Aufruf verhindert das:
läuft der Override, bleibt `self._last_converted_trip` `None`, der Aufrufer behält sein
ursprüngliches `trip` — exakt heutiges (getestetes) Verhalten.

**Warum vier statt der im Ticket genannten zwei/drei Stellen:** `_build_report` (:1248) ruft
`_convert_trip_to_segments` für die HEUTIGE Etappe auf und reicht dasselbe stale `trip`
anschließend an `_build_stage_trend` und `_collect_future_stage_weather` weiter — der erste
Speichervorgang INNERHALB der Ausblick-Schleife überschreibt dadurch bereits die soeben
persistierte Kilometrierung der heutigen Etappe, nicht nur die einer vorherigen
Ausblicks-Iteration. Zeile 1258 (Test-Fallback, anderes Zieldatum) wird aus Konsistenzgründen
identisch mitgepatcht, obwohl dort praktisch kein Verlust entsteht (kein Backfill lief vor
Erreichen dieser Zeile, da sie nur greift, wenn Zeile 1248 keine Etappe fand).

## Expected Behavior

- **Input:** Ein Trip mit mindestens zwei Etappen (heutige + mindestens eine künftige), deren
  Wegpunkte noch keine `distance_from_start_km`-Werte tragen, sowie ein GPX-Bestand, aus dem
  `backfill_stage_distances()` diese Werte für beide Etappen ableiten kann.
- **Output:** Nach einem vollständigen Report-Lauf (`_build_report` inkl. Ausblick) tragen ALLE
  vom Lauf berührten Etappen (heutige UND künftige) ihre nachgerüstete Kilometrierung auf der
  Platte — keine überschreibt die andere.
- **Side effects:** `self._last_converted_trip` ist ein neues, rein internes Instanz-Attribut ohne
  Persistenz und ohne API-Sichtbarkeit. Keine Änderung an `save_trip()`, `backfill_stage_distances()`
  oder deren Signaturen.

## Acceptance Criteria

- **AC-1:** Given eine heutige Etappe hat noch keine nachgerüstete Kilometrierung, ein
  Ausblicks-Etappe folgt / When `_build_report()` läuft (persist=True) und dabei zuerst die
  heutige Etappe konvertiert, danach im Rahmen des Ausblicks die künftige Etappe konvertiert und
  gespeichert wird / Then trägt nach dem Lauf sowohl die heutige als auch die künftige Etappe ihre
  jeweils nachgerüstete Kilometrierung auf der Platte.
  - Test: Trip mit zwei unvermessenen Etappen und passendem GPX-Bestand wird durch
    `_build_report()` geschickt; anschließend wird der Trip neu von der Platte geladen und beide
    Etappen tragen `distance_from_start_km`-Werte an ihren Wegpunkten — nicht nur die zuletzt
    bearbeitete.

- **AC-2:** Given eine Ausblick-Schleife (`_build_stage_trend()` oder
  `_collect_future_stage_weather()`) durchläuft zwei oder drei künftige Etappen nacheinander, jede
  davon zuvor unvermessen / When jede Iteration `_convert_trip_to_segments()` aufruft und dabei
  ihre Etappe nachrüstet und speichert / Then trägt nach Abschluss der Schleife JEDE der
  durchlaufenen Etappen ihre nachgerüstete Kilometrierung — nicht nur die zeitlich letzte
  Iteration.
  - Test: Trip mit drei künftigen, unvermessenen Etappen und vollständigem GPX-Bestand wird durch
    `_build_stage_trend()` geschickt; nach dem Lauf wird der Trip neu von der Platte geladen und
    prüft für alle drei Etappen (nicht nur die dritte) auf gesetzte
    `distance_from_start_km`-Werte. Das ist der vom Ticket geforderte Wächter gegen den in Prod
    (Trip `5f534011`, Etappe `91bbc11b`) beobachteten Mehrfach-Verlust.

- **AC-3:** Given `_build_report()` rüstet die heutige Etappe nach (:1248) und übergibt den Trip
  danach an `_build_stage_trend()`, wo eine künftige Etappe ebenfalls nachgerüstet und gespeichert
  wird / When beide Schritte im selben Report-Lauf ablaufen / Then verliert die heutige Etappe ihre
  Kilometrierung NICHT, obwohl der Speichervorgang der künftigen Etappe zeitlich später erfolgt.
  - Test: Trip mit unvermessener heutiger und unvermessener künftiger Etappe wird durch den
    kompletten `_build_report()`-Lauf (inkl. Ausblick) geschickt; nach dem Lauf trägt die HEUTIGE
    Etappe ihre Kilometrierung, obwohl `_build_stage_trend()` danach nochmals gespeichert hat.
    Deckt die Cross-Boundary-Kette `_build_report` → `_build_stage_trend` ab.

- **AC-4:** Given eine Unterklasse überschreibt `_convert_trip_to_segments(self, trip,
  target_date)` mit der alten 2-Positional-Argument-Signatur (wie
  `test_outlook_scheduler_wires_hiking_window.py`) / When `_build_report()`,
  `_build_stage_trend()` oder `_collect_future_stage_weather()` diese überschriebene Methode
  aufrufen / Then läuft der Aufruf ohne `TypeError`, und der Aufrufer arbeitet weiterhin mit
  seinem ursprünglichen `trip`-Objekt statt mit dem Ergebnis eines früheren, nicht überschriebenen
  Aufrufs.
  - Test: Eine Testklasse überschreibt `_convert_trip_to_segments` exakt wie im bestehenden
    Override und ruft anschließend zweimal hintereinander eine der drei Aufrufer-Methoden mit
    unterschiedlichen `trip`-Objekten auf; der zweite Aufruf zeigt keine Spur des `trip`-Objekts
    aus dem ersten Aufruf (Identitätsprüfung `is`/`is not` auf das lokale `trip` nach dem Aufruf).

- **AC-5:** Given `backfill_stage_distances()` wirft eine Exception während eines Aufrufs von
  `_convert_trip_to_segments()` innerhalb der Ausblick-Schleife / When der Fehler auftritt / Then
  bleibt das bisher verwendete `trip`-Objekt beim Aufrufer unverändert nutzbar, kein Absturz des
  Report-Laufs, und die Fail-soft-Eigenschaft bleibt erhalten.
  - Test: `backfill_stage_distances` wird für eine Etappe so präpariert, dass sie eine Exception
    wirft; `_build_stage_trend()` bzw. `_collect_future_stage_weather()` läuft trotzdem bis zum
    Ende durch (kein unbehandelter Fehler propagiert nach außen), das lokale `trip` bleibt danach
    identisch zum Zustand vor dem fehlgeschlagenen Aufruf.

- **AC-6:** Given `PreviewService` ruft `_convert_trip_to_segments(trip, date, persist=False)`
  auf / When der Aufruf läuft / Then wird weiterhin NICHTS auf die Platte geschrieben — der neue
  Seitenkanal (`self._last_converted_trip`) ändert nichts am Persistenz-Verhalten des
  `persist=False`-Pfads.
  - Test: Bestehender Test `test_preview_does_not_mutate_trip_data.py` läuft unverändert grün;
    zusätzlich wird nach einem `persist=False`-Aufruf geprüft, dass die Trip-Datei auf der Platte
    zeitlich unverändert bleibt (kein neuer `mtime`).

## Known Limitations

- **Der schlüsselbasierte Listen-Merge aus #2058 wird nicht angefasst.** `save_trip()` ersetzt
  Listen weiterhin wholesale, nicht elementweise — diese Spec verhindert nur, dass ein STALE
  `trip`-Objekt überhaupt an `save_trip()` übergeben wird. Eine grundsätzlich robustere
  Merge-Strategie ist eine eigene, separate Entscheidung.
- **Keine Änderung an der Trip-Konfiguration des PO.** Der Fix ändert ausschließlich
  Kontrollfluss in `trip_report_scheduler.py`, keine Nutzerdaten.
- **Zeile 1258 (Test-Fallback) ist praktisch unkritisch**, da an dieser Stelle bislang kein
  Backfill lief, bevor sie erreicht wird (nur relevant, wenn Zeile 1248 keine Etappe fand). Wird
  aus Konsistenzgründen mit demselben Muster gepatcht, um keine Sonderfall-Ausnahme im Code zu
  hinterlassen, die bei künftigen Änderungen übersehen werden könnte.
- **Der Seitenkanal `self._last_converted_trip` ist proze­ss-/instanzlokal.** Parallel laufende
  Report-Läufe auf unterschiedlichen `TripReportSchedulerService`-Instanzen beeinflussen sich
  nicht gegenseitig; innerhalb EINER Instanz ist die Reihenfolge Reset→Aufruf→Lesen zwingend
  einzuhalten (siehe AC-4).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Kontrollfluss-Fix innerhalb bestehender Methoden — kein neues Datenfeld,
  keine Schema-Änderung, kein neuer Kanal, keine neue Persistenzentscheidung. Das Seitenkanal-Muster
  greift ein bereits etabliertes Steuerungsmuster (`self.persist_backfill`) auf, führt kein neues
  Architekturkonzept ein.

## Changelog

- 2026-08-23: Initial spec created
