# Context: fix-2109-kilometrierung-verlust

## Request Summary
Die Ausblick-Schleife (`_build_stage_trend`, `_collect_future_stage_weather`) ruft für bis zu 3 künftige Etappen `_convert_trip_to_segments(trip, stage.date)` auf. Diese Methode lässt intern `backfill_stage_distances()` den Trip nachträglich vermessen, persistiert das Ergebnis via `save_trip` — gibt das aktualisierte Trip-Objekt aber nur lokal zurück, nicht an den Aufrufer. Die Schleife arbeitet weiter mit dem alten (unvermessenen) `trip`-Objekt. Beim nächsten Schleifendurchlauf überschreibt `save_trip` (Read-Modify-Write mit Listen-als-Ganzes-Merge, #2058) die zuvor nachgetragene Kilometrierung der vorherigen Etappe wieder mit dem stale Stand. Nachgewiesen im Produktivbetrieb (Trip `5f534011`, Etappe `91bbc11b` dreimal nachgerüstet — Beweis für wiederholten Verlust).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:2324-2413` (`_build_stage_trend`) | Schleife über `future_stages[:3]`, Zeile 2396 ruft `_convert_trip_to_segments(trip, stage.date)` mit stale `trip` je Iteration |
| `src/services/trip_report_scheduler.py:2791-2870` (`_collect_future_stage_weather`) | Gleiches Muster, Zeile 2854 — Schleife über `trip.get_future_stages(target_date)`, gefiltert auf `wanted_dates` (bis zu 2 Etappen) |
| `src/services/trip_report_scheduler.py:1980-2028` (`_convert_trip_to_segments`) | Thin Delegator: ruft `backfill_stage_distances`, gibt NUR `List[TripSegment]` zurück, das aktualisierte `trip` bleibt lokal (Zeile 2025-2028). Wird direkt von **~20 Testdateien** aufgerufen (`segments = svc._convert_trip_to_segments(trip, date)`) — Signatur/Rückgabetyp ist eine breite, stabile Schnittstelle und darf NICHT geändert werden |
| `src/services/trip_report_scheduler.py:1240-1262` (`_build_report`, primärer Versandpfad) | Ruft `_convert_trip_to_segments` einmal für `target_date`, ggf. ein zweites Mal für einen Test-Fallback-Tag — kein Mehrfach-Backfill DERSELBEN Etappe, daher vermutlich nicht vom selben Verlustmuster betroffen. In Analyse-Phase gegenprüfen, ob `trip` danach noch für die aktuelle Etappe weiterverwendet wird |
| `src/services/track_resolution.py:264-345` (`backfill_stage_distances`) | Baut per `dataclasses.replace` ein NEUES Trip-Objekt, persistiert bei `persist=True` via `save_trip`, gibt das neue Objekt zurück. Fail-soft (jeder Fehler → unveränderter Trip). Idempotent: kehrt sofort um, wenn alle Wegpunkte bereits `distance_from_start_km` tragen (Zeile 298-304) |
| `src/app/loader.py:1708-1769` (`save_trip`) + `:128` (`_deep_merge_preserve_unknown`) | Read-Modify-Write mit Merge gegen die Datei auf Platte. Ersetzt Wegpunktlisten pro Etappe ALS GANZES (dokumentiert in #2058) — das ist der Mechanismus, der den stale Stand der vorherigen Iteration über den bereits gespeicherten Fortschritt schreibt |
| `tests/tdd/test_preview_does_not_mutate_trip_data.py` | Etabliertes Verhalten: `persist`-Parameter-Kontrakt von `_convert_trip_to_segments`/`backfill_stage_distances` ist bereits Gegenstand eines eigenen Bugfixes (#2036 CI-Nachschlag) — jeder Fix hier muss den `persist=False`-Preview-Pfad unangetastet lassen |
| `docs/specs/modules/trip_report_scheduler.md` | Bestehende Modul-Spec — Ausblick-Feature-Bereich, wird ggf. um AC ergänzt |

## Existing Patterns
- **`persist`-Parameter-Threading** (#2036/#2058): `_convert_trip_to_segments(trip, date, *, persist=None)` — `None` heißt "folge `self.persist_backfill`". Nebenpfade (`_build_stage_trend`, `_collect_future_stage_weather`) rufen OHNE Keyword und werden über das Objekt-Attribut gesteuert, weil Test-Doubles diese beiden Methoden komplett überschreiben (siehe unten). Ein Fix darf dieses Steuerungsmuster nicht durchbrechen.
- **Fail-soft**: `backfill_stage_distances` fängt jeden Fehler und gibt den unveränderten Trip zurück — eine fehlende Kilometerangabe ist laut Docstring "ein Schönheitsfehler, ein ausgefallener Alarm nicht". Der Fix muss diese Fail-soft-Eigenschaft erhalten.
- **Read-Modify-Write mit Merge ist CLAUDE.md-Pflicht** bei jeder Schema-relevanten Änderung — hier bereits vorhanden in `save_trip`, aber der Merge schützt nicht vor einem stale In-Memory-Objekt, das VOR dem Schreiben bereits veraltet ist.
- **Test-Doubles überschreiben `_build_stage_trend`/`_collect_future_stage_weather` komplett** (>15 Fundstellen, z.B. `test_thunder_origin_preview.py:316`, `test_outlook_scheduler_wires_hiking_window.py:47`) — ein Fix, der neue Pflichtparameter an diesen Methoden einführt, bricht diese Doubles lautlos (kein Fehler, aber die Overrides greifen dann nicht mehr wie erwartet). Signaturänderungen hier sind riskant; ein Fix, der NUR den internen Schleifenkörper ändert (ohne Methodensignatur zu berühren), ist vorzuziehen.

## Dependencies
- **Upstream:** `services.track_resolution.backfill_stage_distances`, `services.track_resolution.resolve_stage_track_km`, `app.loader.save_trip`/`get_data_dir`
- **Downstream:** `internal/model/naismith.go:135-138` (Go, Gehzeit-Schätzung nutzt `DistanceFromStartKm` — fällt bei fehlendem Wert auf Ersatzweg zurück, betrifft künftige Etappen im Ausblick). Alarm-Pfad (`trip_alert.py:1385`) ist NICHT betroffen — rüstet die Etappe von `today` selbst und separat nach, vor der Segmentauflösung.

## Existing Specs
- `docs/specs/modules/trip_report_scheduler.md` — Ausblick-Feature (Abschnitt Implementation Details)
- Kein dediziertes ADR zu Backfill-Semantik; #2036/#2058 sind die relevanten Vorgänger-Issues (nicht als ADR dokumentiert, nur als Issue-Historie)

## Risks & Considerations
- **Signaturbruch-Risiko:** `_convert_trip_to_segments` wird direkt von ~20 Testdateien mit der Erwartung `segments = svc._convert_trip_to_segments(...)` (reine Liste) aufgerufen. Rückgabetyp ändern (z.B. Tupel `(trip, segments)`) bricht diese breit. Fix sollte stattdessen den aktualisierten Trip NUR innerhalb der drei betroffenen Schleifen-Aufrufer (`_build_stage_trend`, `_collect_future_stage_weather`, ggf. `_build_report` Fallback) selbst nachführen — z.B. über einen neuen internen Helfer, der (trip, segments) liefert, während `_convert_trip_to_segments` selbst unverändert bleibt.
- **Doppel-Backfill/Log-Rauschen:** Wird derselbe Trip innerhalb einer Schleife mehrfach an `backfill_stage_distances` übergeben, muss das Verhalten bei "bereits vermessen" (`_melde_unplausible_messung`) nicht neu ausgelöst werden — jede Iteration betrifft eine ANDERE Etappe, daher unkritisch, aber in Adversary-Runde gegenprüfen.
- **Mutations-Wächter nötig:** Ein grüner Test allein beweist nichts. Wächter muss ZWEI Backfills nacheinander in derselben Schleife/demselben Prozess durchlaufen lassen und danach BEIDE Etappen als vermessen prüfen (Ticket-Vorgabe) — nicht nur die zuletzt bearbeitete.
- **Datenschema-Änderung:** Kein neues Feld, keine Migration — reiner Kontrollfluss-Fix. `data_schema_backup.py`-Hook greift trotzdem, da `trip_report_scheduler.py` als schema-relevant gilt (import-seitig verknüpft) — prüfen, ob der Pre-Snapshot-Hook triggert.
- **`_build_report`-Fallback (Zeile 1248/1258):** offene Frage für Analyse-Phase, ob dort ebenfalls ein Verlust entsteht, wenn `trip` nach dem ersten `_convert_trip_to_segments`-Aufruf noch für die (jetzt vermessene) Etappe weiterverwendet wird, bevor der zweite Aufruf (Fallback-Datum) läuft. Nicht Teil des Ticket-Nachweises, aber strukturell verwandt.

## Nicht Ziel (aus Ticket übernommen)
- Der schlüsselbasierte Listen-Merge aus #2058 — eigene Fallhöhe, eigene Entscheidung.
- Änderungen an der Trip-Konfiguration des PO.

## Analysis

### Type
Bug

### Root Cause bestätigt + erweitert
`_convert_trip_to_segments` (Zeile 2025-2028) reassigned `trip` nur lokal nach dem Backfill und gibt ausschließlich `List[TripSegment]` zurück. Jeder Aufrufer, der `trip` danach WEITERVERWENDET (statt es wegzuwerfen), arbeitet mit dem Stand von vor dem Backfill. Beim nächsten `save_trip` (Read-Modify-Write) wird die zuvor bereits persistierte Kilometrierung überschrieben, weil `_deep_merge_preserve_unknown` Listen — also auch `stages` — **wholesale ersetzt, nicht elementweise merged** (`loader.py:132`: *"Lists are replaced wholesale (not element-merged) — overlay wins."*). Das ist die exakte Stelle, die den in #2109 beschriebenen Verlust technisch erklärt.

**Erweiterter Fund (über das Ticket hinaus, gleicher Mechanismus):** Der Verlust ist nicht auf die Ausblick-Schleife beschränkt. `_build_report` (Zeile 1248) ruft `_convert_trip_to_segments(trip, target_date)` für die HEUTIGE Etappe auf, verwirft die Aktualisierung genauso — und reicht dasselbe stale `trip` anschließend an `_build_stage_trend` (Zeile 1423) und `_collect_future_stage_weather` (Zeile 2602) weiter. Der erste Speichervorgang INNERHALB der Ausblick-Schleife überschreibt dadurch bereits die soeben persistierte Kilometrierung der HEUTIGEN Etappe — nicht nur die einer vorherigen Ausblicks-Iteration. Vier Stellen teilen denselben Fehler:
1. `_build_report` Zeile 1248 (primärer Aufruf)
2. `_build_report` Zeile 1258 (Test-Fallback — unkritisch, da anderes Zieldatum UND nur erreicht, wenn Zeile 1248 keine Etappe fand, also dort auch kein Backfill lief)
3. `_build_stage_trend` Zeile 2396 (Schleife, bis zu 3 Iterationen)
4. `_collect_future_stage_weather` Zeile 2854 (Schleife, bis zu 2 Iterationen)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_report_scheduler.py` | MODIFY | `_convert_trip_to_segments` hinterlegt das aktualisierte Trip-Objekt zusätzlich in einem Instanz-Attribut (Sentinel-Pattern, s.u.); die drei Aufrufstellen (1248, 2396, 2854) lesen es nach dem Aufruf und führen ihr lokales `trip` nach |
| `tests/tdd/test_stage_trend_backfill_survives_iterations.py` (o.ä. Name, TDD-Phase legt fest) | CREATE | Wächter: zwei/drei Backfills nacheinander in derselben Ausblick-Schleife, danach ALLE betroffenen Etappen als vermessen prüfen |

### Scope Assessment
- Files: 1 Produktivdatei (4 Stellen) + 1 neue Testdatei
- Estimated LoC: ca. +25/-4 (klein, mechanischer Fix + Testdatei)
- Risk Level: **MEDIUM** — Blast Radius ist hoch (Schreibpfad auf Nutzerdaten), aber der Fix selbst ändert keine öffentliche Signatur und keine bestehende Rückgabelogik

### Technical Approach
**Kein Signaturwechsel von `_convert_trip_to_segments`.** Begründung: ~20 Testdateien rufen `svc._convert_trip_to_segments(trip, date)` direkt auf und erwarten eine reine `List[TripSegment]`; mindestens ein Test (`test_outlook_scheduler_wires_hiking_window.py:47-51`) **überschreibt** `_convert_trip_to_segments` in einer Unterklasse mit fester 2-Positional-Argument-Signatur — ein neues Keyword-Argument an der Aufrufstelle würde diesen Override zur Laufzeit mit `TypeError` brechen. Sowohl Rückgabetyp als auch Aufrufsignatur bleiben deshalb unangetastet.

**Gewählter Mechanismus: Instanz-Attribut als Seitenkanal**, passend zum bestehenden Muster (`self.persist_backfill` steuert bereits heute genau diese Methode auf dieselbe Art):

```python
# In _convert_trip_to_segments, nach dem Backfill (Ersatz für Zeile 2025-2028):
if user_id:
    trip = backfill_stage_distances(trip, user_id, target_date, persist=effective_persist)
self._last_converted_trip = trip
return convert_trip_to_segments(trip, target_date)
```

An jeder der drei betroffenen Aufrufstellen:
```python
self._last_converted_trip = None
segments = self._convert_trip_to_segments(trip, stage.date)  # oder target_date
if self._last_converted_trip is not None:
    trip = self._last_converted_trip
```

**Warum das Sentinel-Reset vor jedem Aufruf zwingend ist:** Wird `_convert_trip_to_segments` in einer Unterklasse überschrieben (wie im genannten Test), läuft der Seitenkanal nie — `self._last_converted_trip` bliebe sonst auf dem Wert eines FRÜHEREN, nicht überschriebenen Aufrufs stehen und der Aufrufer würde fälschlich ein fremdes `trip`-Objekt übernehmen. Das Zurücksetzen auf `None` unmittelbar vor jedem Aufruf verhindert das und lässt bestehende Overrides unverändert funktionieren (sie liefern weiterhin nur Segmente, das Fallback-`trip` bleibt unangetastet — exakt heutiges Verhalten).

Dieses Muster deckt alle vier identifizierten Stellen einheitlich ab, ohne dass irgendein bestehender Test seine Erwartung ändern muss.

### Dependencies
Keine neuen. Bestehende: `track_resolution.backfill_stage_distances`, `app.loader.save_trip`.

### Open Questions
- [x] Ist `_build_report` Zeile 1248/1258 vom selben Muster betroffen? → Ja (1248), Nein-praktisch (1258, da kein Backfill vor dem Fallback lief). Beide werden trotzdem einheitlich mitbehandelt (identischer Fix, kein Mehraufwand).
- [ ] PO-Freigabe der erweiterten Spec (4 statt der im Ticket explizit genannten 2-3 Stellen) — wird in der Spec transparent begründet, keine separate Rückfrage nötig (Tech-Lead-Entscheidung, kein PO-Ermessen).
