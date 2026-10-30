---
entity_id: feat_1539_s5_briefing_parallel
type: feature
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [scheduler, nebenlaeufigkeit, parallel-fetch, trip-briefing, amtliche-warnungen, ausblick-trend, gewitter-fallback, multi-user, epic-2138, issue-1539]
---

# Feature #1539 Workflow 5 — S5 Briefing-Abrufe parallel

Issue #1539, Epic #2138, Workflow `feat-1539-s5-briefing-parallel`, Scheibe **S5**. Dritter Nutzer des Abruf-Bausteins
`parallel_fetch.fetch_ordered` (Vorbilder: S3 Trip-Alarm, S4 Radar). #1539 bleibt danach offen (PR-Text „Refs #1539",
nie „Closes").

## Approval

- [ ] Approved

## Purpose

Im Trip-Briefing laufen drei Abrufblöcke noch strikt nacheinander, obwohl der Segment-Abruf des Zieltags bereits
parallel ist (#2439): (1) die amtlichen Warnungen je eindeutigem Etappen-Startpunkt, (2) der Ausblick-Trend über bis
zu drei Folge-Etappen (der größte Latenzblock), (3) der Gewitter-Fallback über bis zu zwei Folge-Etappen. Dieser
Workflow lässt die Netzabrufe dieser drei Blöcke nebeneinander laufen. Es ist eine **rein mechanische Umstellung ohne
Verhaltenswechsel**: gleiche Inhalte, gleiche Reihenfolge, gleiche Fehlersemantik, gleicher Versand, keine neuen
Metriken, keine neuen Hinweise, keine Handlungsempfehlungen.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `TripReportSchedulerService._build_stage_trend`, `TripReportSchedulerService._collect_future_stage_weather`, Warnungsblock der Briefing-Erzeugung
- **Warnungsblock:** in der Briefing-Erzeugung, Schleife über `segment_weather` ca. `:1733-1766`
  (`get_official_alerts_with_status` + `collect_source_queries`, `official_queries.extend(_briefing_queries(...))`)
- **Trend:** `TripReportSchedulerService._build_stage_trend`, Etappenschleife ca. `:2973-3088`
- **Gewitter-Fallback:** `TripReportSchedulerService._collect_future_stage_weather`, Etappenschleife ca. `:3453-3474`
- **Bestehender Abruf (Referenz, unverändert):** `_fetch_weather` ca. `:2667-2719` (nutzt bereits `fetch_ordered`,
  Provider `open_meteo`, Frist `FETCH_WEATHER_DEADLINE_SECONDS` = 600 s, Konstante ca. `:88`, Fehlerplatzhalter
  `_fehler_platzhalter`)
- **Seriell zu haltender Schritt:** `_convert_trip_to_segments` ca. `:2489` (schreibt `self._last_converted_trip`,
  kann GPX-Distanzen nachtragen/persistieren)
- **Bausteine (unverändert):** `src/services/parallel_fetch.py` (`fetch_ordered`, `FetchOutcome`),
  `src/services/official_alerts/base.py` (`collect_source_queries`, ContextVar `_source_query_sink`),
  `src/services/warn_egress.py` (`cached_fetch`, Single-flight)

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/trip_report_scheduler.py`). Kein Go-Code, kein
> Frontend. Der Go-Scheduler bleibt Taktgeber.
>
> **Teilung Trip/Ortsvergleich:** Das Ortsvergleich-Briefing ist bereits parallel (`comparison_parallel.py`,
> fix_1765_*) und wird nicht angefasst. Es entsteht keine neue Trip-Komponente ohne Pendant: S5 nutzt denselben
> Baustein `fetch_ordered`, den auch der Ortsvergleich-Pfad nutzt.
>
> **Kanäle:** Die drei Blöcke liefern Daten für das Briefing auf allen vier Kanälen (E-Mail, Telegram, SMS,
> Premium-SMS: Warnungen, Ausblick-Tabelle, TH+-Zeile). Inhalt und Versand bleiben unverändert.
>
> **Mandantentrennung:** `self._user_id` wird von den Workern nur gelesen und bleibt unverändert; nie `"default"`
> (Pflicht-AC mit zwei Nutzern).

## Estimated Scope

- **LoC:** ca. +90/-40 produktiv (1 Datei), Tests ca. +250
- **Files:** 1 produktiv MODIFY (`trip_report_scheduler.py`), 1 bis 2 Testdateien CREATE
  (`tests/tdd/test_briefing_parallel_*.py`), diese Spec
- **Effort:** medium
- **Risk Level:** MITTEL — kritischer Versandpfad (alle vier Kanäle), aber mechanische Umstellung mit unveränderter
  Fehlersemantik

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1539-s5-briefing-parallel.md` | Analyse | Verbindliche Analyse, Befunde, Technical Approach |
| `feat_1539_s1b_s2_abruf_baustein.md` | Spec (live) | Vertrag von `fetch_ordered` (Ergebnis in Eingabereihenfolge, `skipped`, Inline im Worker) |
| `feat_1539_s3_trip_alarm_parallel.md`, `feat_1539_s4_radar_parallel.md` | Specs | Vorbild: Auswertung im Hauptfaden, `skipped` zählt als gescheitert |
| ADR-0038 | ADR | Endliche Frist, sichtbarer Teilerfolg statt stilles Weglassen |
| ADR-0103 | ADR (bestehend) | Semaphorenzahlen; unbekannter Provider-Schlüssel bekommt 3 Slots (Env `GZ_PARALLEL_FETCH_SLOTS_<NAME>`); gilt unverändert, kein neues ADR |

## Scope

**In Scope**

- Warnungsblock: Abruf je eindeutiger Startkoordinate über `fetch_ordered`.
- Trend (`_build_stage_trend`) und Gewitter-Fallback (`_collect_future_stage_weather`): zweiphasig, Netzteil je
  Etappe parallel, über **einen gemeinsamen privaten Helfer** (kein Doppelcode).
- Endliche Frist für beide Etappen-Abrufe und den Warn-Abruf.

**Out of Scope**

- Ortsvergleich-Briefing (bereits parallel), S6 (Compare-Alarm), S7 (Go-Nutzer-Fan-out).
- Ensemble-Hauptlauf und Nachtwetter (je ein Aufruf, kein Gewinn).
- Änderungen an `parallel_fetch.py`, `official_alerts/*`, `warn_egress.py`, `_fetch_weather`,
  `_convert_trip_to_segments` (Letzteres bleibt wie es ist, wird nur weiter seriell aufgerufen).
- Atomarität in `openmeteo.py` (C4-63) und Thundering Herd nationaler Warndienste dpc/vigilance (C4-64):
  bleiben Nebenbefunde in #1539/#1199.
- Neue Anzeige, neue Texte, neue Metriken, Handlungsempfehlungen.

## Implementation Details

### Entschiedene Punkte der Analyse

1. **Frist:** Es wird **kein neuer Wert** eingeführt. Sowohl der Etappen-Abruf (Trend, Fallback) als auch der
   Warn-Abruf nutzen `time_module.monotonic() + FETCH_WEATHER_DEADLINE_SECONDS`. Die Marke wird einmal je Block
   unmittelbar vor `fetch_ordered` gebildet (wie in `_fetch_weather`). Das verschachtelte `_fetch_weather` im Worker
   läuft inline seriell mit eigener Frist; die äußere Marke begrenzt, wann noch nicht gestartete Etappen als
   `skipped` verworfen werden.
2. **Provider-Schlüssel:** Etappen-Abruf: `open_meteo` (gleiche Semaphore wie der Segment-Abruf, Gesamtparallelität
   bleibt bei 3 gedeckelt). Amtliche Warnungen: **eigener Schlüssel `official_alerts`** (unbekannter Schlüssel ⇒
   3 Slots laut ADR-0103, kein neues ADR; Warn- und Wetterabruf blockieren einander nicht; Warndienste sind
   Amtsdienste, daher Höflichkeitsgrenze 3).
3. **Parallelitätsnachweis:** Überlappung wird mit echter Barrier bzw. Zeitmessung am Provider-Rand bewiesen,
   nicht durch einen Mock der eigenen Annahme.

### 1. Amtliche Warnungen (Warnungsblock)

1. Im Hauptfaden: eindeutige Startkoordinaten wie bisher sammeln (Überspringen von `sw.has_error`, Rundung auf
   3 Nachkommastellen, erste Fundstelle gewinnt). Ergebnis: geordnete Liste `(sw, coord)`.
2. `fetch_ordered(liste, worker, provider="official_alerts", deadline_at=...)`. Der Worker setzt
   `collect_source_queries(_sink)` **selbst innerhalb der Aufgabe** (die ContextVar ist je Aufgabe per
   `copy_context()` isoliert) und gibt `(alerts, unavailable, _sink)` zurück.
3. Im Hauptfaden, in Koordinatenreihenfolge: `sw.official_alerts`, `sw.official_alerts_unavailable` zuweisen und
   `official_queries.extend(_briefing_queries(_sink, sw))`. **Kein Schreibzugriff aus dem Worker** auf `sw` oder
   `official_queries`.
4. Fehler im Worker (Ausnahme) oder `skipped` ⇒ unveränderter Platzhalter: `sw.official_alerts = []`,
   `sw.official_alerts_unavailable = True`, Warn-Log mit Grund (Quellenausfall ist nie Entwarnung, #1348/ADR-0021).
5. Bei `official_alerts_enabled is False` bleibt der Block strukturell ohne Abruf.

### 2. Trend und Gewitter-Fallback (gemeinsamer Helfer)

Zweiphasig; die Schleifenstruktur der beiden Methoden bleibt erhalten, nur der Netzteil wandert in den Helfer.

**Phase 1 (seriell, Hauptfaden):** je Etappe in Etappenreihenfolge Horizont-Prüfung (`BEYOND_HORIZON` bzw. beim
Fallback `continue`), `self._last_converted_trip = None`, `_convert_trip_to_segments(trip, stage.date)`, Fortschreibung
von `trip = self._last_converted_trip` falls gesetzt (Backfill/Persistenz bleibt im Hauptfaden und in derselben
Reihenfolge). Pro Etappe wird der Stand `(stage, segments, trip)` gemerkt; `trip` ist der Stand **nach** dieser
Etappe, so wie ihn der serielle Ablauf an `_enrich_ensemble_for_trip` übergibt. Leere Segmente oder Ausnahme ⇒
unverändert (Trend: `failures.add(UNAVAILABLE)` + Warn-Log, Fallback: Etappe wird still übersprungen).

**Phase 2 (parallel):** Der Helfer `_abrufe_fuer_etappen(vorbereitet)` ruft
`fetch_ordered(vorbereitet, worker, provider="open_meteo", deadline_at=...)`. Der Worker führt je Etappe
`self._fetch_weather(segments)` und danach `self._enrich_ensemble_for_trip(trip, seg_weather)` aus und gibt
`seg_weather` zurück (jede Etappe arbeitet nur auf ihren eigenen Daten).

**Phase 3 (seriell, Hauptfaden):** Der Helfer liefert pro Etappe in Eingabereihenfolge `(stage, seg_weather | None,
Fehlergrund)`. Auswertung und Zeilenbau (`aggregate_stage`, `build_outlook_row`, `_trend_note`, `row["date"]`,
`row["name"]`, `row["note"]`) laufen seriell in Etappenreihenfolge, `trend.append` nur im Hauptfaden.
Fehler/`skipped`/leeres Wetter ⇒ Trend: `failures.add(UNAVAILABLE)` + Warn-Log (`skipped` mit Grund laut geloggt);
Fallback: Warn-Log `Thunder-forecast fetch failed for stage …`, Etappe entfällt. Ausnahme im Zeilenbau ⇒ unverändert
`UNAVAILABLE`.

**Zustand nach dem Lauf:** `self._last_converted_trip` hat am Ende denselben Wert wie im seriellen Ablauf (Phase 1
läuft unverändert seriell). Der Endzustand `FOUND`/`UNAVAILABLE`/`BEYOND_HORIZON` bleibt nach der Regel #1486.

### 3. Unveränderte Garantien

- Totalausfall-Erkennung (`OUTAGE_WITHHOLD_RATIO`, #1113) und `_fehler_platzhalter` bleiben unverändert.
- Verschachtelung: `_fetch_weather` im Worker läuft inline seriell (kein Deadlock); Parallelität entsteht über
  Etappen, nicht zusätzlich über Segmente.

### Wirkmaß

Wirkmaß ist die Briefing-Erzeugungsdauer im Prod-Journal. Typisch 1 bis 4 Startkoordinaten, 3 Trend-Etappen, 2
Fallback-Etappen. Der Gewinn liegt in der Überlappung der Etappenabrufe (statt nacheinander) und im parallelen
Warn-Abruf; die Obergrenze setzt der `open_meteo`-Slot (3). Echte Nebenläufigkeit ist auf Staging nicht messbar
(`NOT_MEASURABLE_ON_STAGING`).

## Expected Behavior

- **Input:** Trip mit Etappen, Zieltag, Warnungen aktiv oder nicht (unverändert).
- **Output:** Warnungen je Segment, Ausblick-Zeilen und Gewitter-Etappendaten **inhaltlich und in der Reihenfolge
  identisch** zum seriellen Lauf; `official_queries` in Koordinatenreihenfolge.
- **Side effects:** kürzere Laufzeit des Briefings bei mehreren Koordinaten/Etappen; keine zusätzlichen Upstream-Calls.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit mehreren eindeutigen Etappen-Startkoordinaten, deren Warn-Abrufe in umgekehrter
  Reihenfolge fertig werden / When das Briefing die amtlichen Warnungen lädt / Then stehen die Warnungen am jeweils
  richtigen Segment, `official_queries` ist in Koordinatenreihenfolge identisch zum seriellen Lauf, doppelte
  Koordinaten werden weiterhin nur einmal abgerufen, und Segmente mit Fehlern werden weiterhin übersprungen.
  - Test: `tests/tdd/test_briefing_parallel_warnungen.py`; absteigende Verzögerung am Provider-Rand, Ergebnis und
    `official_queries` gegen den seriellen Lauf (gleiche Eingaben) verglichen.

- **AC-2:** Given ein Trip mit drei Folge-Etappen, bei dem das Umwandeln in Segmente GPX-Distanzen nachträgt und
  `_last_converted_trip` fortschreibt / When der Ausblick-Trend gebaut wird / Then läuft `_convert_trip_to_segments`
  je Etappe seriell im Hauptfaden in Etappenreihenfolge (jede Etappe sieht den fortgeschriebenen Trip der
  Vorgängerin), der Netzabruf läuft parallel, und die Trend-Zeilen stehen in Etappenreihenfolge, identisch zum
  seriellen Lauf.
  - Test: `tests/tdd/test_briefing_parallel_trend.py`; Backfill-Trip, Aufruf-Thread und -Reihenfolge von
    `_convert_trip_to_segments` erfasst (nur Beobachtung, kein Ersatz), absteigende Verzögerung am Provider-Rand,
    Zeilen gegen seriellen Lauf verglichen.

- **AC-3:** Given zwei Folge-Etappen im Prognosehorizont, die der Trend nicht abdeckt / When der Gewitter-Fallback
  die Etappenwetter sammelt / Then liefert er dieselben Daten in derselben Reihenfolge wie vor der Umstellung, und
  Trend und Fallback benutzen denselben privaten Helfer für den parallelen Netzteil (kein duplizierter Abrufcode).
  - Test: `tests/tdd/test_briefing_parallel_trend.py`; Ergebnisvergleich seriell gegen parallel; Nachweis des
    gemeinsamen Pfads über beobachtetes Verhalten (Aufrufzähler des Helfers bei Trend- und Fallback-Lauf, kein
    Dateiinhalt-Check).

- **AC-4:** Given in den Etappen-Abrufen scheitert eine Etappe mit Ausnahme, eine liefert leeres Wetter, und beim
  Warn-Abruf scheitert eine Koordinate / When Trend, Fallback und Warnungen verarbeitet werden / Then entfällt im
  Trend nur die betroffene Etappe und der Zustand wird `UNAVAILABLE` (bleibt wenigstens eine Zeile, gilt `FOUND`),
  im Fallback entfällt die Etappe still mit Warn-Log, die Warnung erhält `[]` mit `official_alerts_unavailable=True`
  (nie Entwarnung), und die Totalausfall-Erkennung des Hauptlaufs verhält sich wie zuvor.
  - Test: `tests/tdd/test_briefing_parallel_fehler.py`; Fehler gezielt je Etappe/Koordinate am Provider-Rand,
    Zustand, Logzeilen und `unavailable`-Flag geprüft; Bestandstests zu #1486 (Ausblick-Zustände) und #1113
    (Totalausfall-Schwelle) bleiben grün.

- **AC-5:** Given die Frist ist bereits abgelaufen bzw. läuft während der Etappen- und Warn-Abrufe ab / When
  Trend, Fallback und Warnungen ausgeführt werden / Then wird mit einer endlichen Frist gearbeitet (derselben
  Konstante `FETCH_WEATHER_DEADLINE_SECONDS`, kein neuer Wert), jede nicht abgeschlossene Etappe bzw. Koordinate
  zählt wie gescheitert (`skipped`) und steht mit Grund im Log, und nichts wird still weggelassen.
  - Test: `tests/tdd/test_briefing_parallel_fehler.py`; Frist im Test verkürzt (Konstante über das Modul gesetzt),
    Slots auf 1 begrenzt, Ergebnis und Fehlerzeilen mit Grund geprüft.

- **AC-6:** Given Etappen-Abrufe mit künstlicher Verzögerung je Etappe am Provider-Rand / When der Trend gebaut wird
  / Then überlappen sich die Abrufe nachweislich (Barrier, die nur freigibt, wenn mindestens zwei Abrufe zeitgleich
  laufen) und die Gesamtdauer liegt bei drei Etappen mit je 0,5 s Verzögerung unter 80 % der Summe der
  Einzelverzögerungen (unter 1,2 s bei 1,5 s Summe); dasselbe gilt für mehrere Warn-Koordinaten.
  - Test: `tests/tdd/test_briefing_parallel_trend.py` und `test_briefing_parallel_warnungen.py`; Barrier und
    gemessene Dauer, keine Mock-Annahme im Prüfling.

- **AC-7:** Given zwei verschiedene Nutzer mit je einem Trip führen gleichzeitig das Briefing mit Trend,
  Fallback und Warnungen aus / When die Worker laufen / Then trägt jeder Abruf die `user_id` seines Nutzers (am
  Provider-Rand erfasst, nie `"default"` oder `None`), und weder Etappen, Warnungen noch `official_queries` des
  einen Nutzers erscheinen im Ergebnis des anderen.
  - Test: `tests/tdd/test_briefing_parallel_mandanten.py` mit zwei `user_id`; Thread-Fehler selbst eingesammelt.

- **AC-8:** Given Warn-Abrufe und Wetter-Etappen-Abrufe laufen im selben Briefing / When die Provider-Semaphoren
  vergeben werden / Then laufen die Warn-Abrufe unter dem Provider-Schlüssel `official_alerts` und die
  Etappen-Abrufe unter `open_meteo`, sodass ein ausgelasteter `open_meteo`-Slot den Warn-Abruf nicht blockiert.
  - Test: `tests/tdd/test_briefing_parallel_warnungen.py`; alle drei `open_meteo`-Slots durch gehaltene Abrufe
    belegt, Warn-Abruf wird dennoch gestartet (Zeit- bzw. Startnachweis am Provider-Rand).

- **AC-9:** Given ein paralleler Lauf mit gemischtem Erfolg und Fehler / When der Lauf endet / Then werden
  `trend`, `failures`, `official_queries`, die Zuweisungen an die Segmentdaten und `_last_converted_trip`
  ausschließlich vom Hauptfaden geschrieben (kein Schreibzugriff aus einem Worker-Thread) und stimmen nach vielen
  Wiederholungen mit dem seriellen Ergebnis überein.
  - Test: `tests/tdd/test_briefing_parallel_fehler.py`; schreibende Thread-Kennung erfasst und mit dem Hauptfaden
    verglichen, Wiederholungslauf.

## Testplan

Testdateien nach Verhalten benannt, Kern-Schicht (deterministisch, ohne Netz):
`tests/tdd/test_briefing_parallel_warnungen.py` (AC-1, AC-6, AC-8), `test_briefing_parallel_trend.py`
(AC-2, AC-3, AC-6), `test_briefing_parallel_fehler.py` (AC-4, AC-5, AC-9), `test_briefing_parallel_mandanten.py`
(AC-7). Wetter- und Warndaten kommen als Fixtures am Provider-Rand; Zähler, Verzögerungen und Barrier sitzen am
Provider, **nicht** im Prüfling. Kein Mock-Theater, keine Dateiinhalt-Checks. Concurrency-Tests sammeln
Thread-Ausnahmen selbst ein. Der Prüfling wird relativ zur Testdatei aufgelöst (Worktree-sicher). Bestehende
Briefing-/Ausblick-/Gewitter-Tests bleiben grün.

**Mutations-Gegenprobe (Pflicht für den Adversary; nur per String-Ersetzung mit externer Sicherungskopie, nie
`git checkout/stash/reset`; zu klären ist jeweils, **welcher** Test rot wird):**

1. Ergebnisse in Fertigstellungs- statt Eingabereihenfolge zusammenführen ⇒ AC-1 bzw. AC-2 rot.
2. `official_queries.extend` im Worker statt im Hauptfaden ⇒ AC-1 bzw. AC-9 rot.
3. `_convert_trip_to_segments` in den Worker verlegen ⇒ AC-2 rot.
4. `trip` nicht mehr je Etappe fortschreiben (immer Ausgangs-Trip) ⇒ AC-2 rot.
5. Fehler/`skipped` als „keine Warnungen" ohne `unavailable=True` behandeln ⇒ AC-4 rot.
6. `skipped` nicht als Fehler zählen oder nicht loggen ⇒ AC-5 rot.
7. `deadline_at` auf unendlich setzen ⇒ AC-5 rot.
8. Provider-Schlüssel der Warnungen auf `open_meteo` ⇒ AC-8 rot.
9. `user_id` im Worker auf `"default"` oder `None` ⇒ AC-7 rot.
10. Fallback mit eigenem Abrufcode statt des gemeinsamen Helfers ⇒ AC-3 rot.

## Known Limitations

- **Begrenzter Hebel:** höchstens 3 Trend- und 2 Fallback-Etappen, typisch 1 bis 4 Warn-Koordinaten;
  Gesamtparallelität bleibt durch `open_meteo`-Slot 3 gedeckelt.
- **Laufende Threads sind nicht abbrechbar:** ein zu später Abruf wird verworfen (`skipped`), sein Thread hält den
  Slot bis zum Ende.
- **Nebenläufigkeit auf Staging nicht messbar** (`NOT_MEASURABLE_ON_STAGING`): Verhalten wird im Kern durch Tests
  bewiesen, die Wirkung erst durch Nachmessung im Prod-Journal.
- **Slotzahl ist ein Startwert** aus ADR-0103 (Prüfdatum 2027-01-26); der Schlüssel `official_alerts` nutzt den
  Standardwert 3.
- Mehrfachabfrage nationaler Warndienste je Koordinate (C4-64) bleibt Nebenbefund.

## Verbleibt in #1539

- **S6:** Compare-Alarm und amtliche Warnungen im Alarmpfad parallel.
- **S7:** Go-Nutzer-Fan-out gemäß Gesamtplan. #1539 bleibt bis dahin offen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** ADR-0103 (Semaphorenzahlen, unbekannter Schlüssel ⇒ 3 Slots) gilt unverändert; zweiphasiger
  Ablauf, gemeinsamer Helfer und Provider-Schlüssel `official_alerts` sind lokale Umsetzungsdetails. ADR-0038
  (endliche Frist) und ADR-0021 (Quellenausfall nie Entwarnung) bleiben gültig.

## Changelog

- 2026-10-30: Initial spec created (Workflow feat-1539-s5-briefing-parallel, S5)
