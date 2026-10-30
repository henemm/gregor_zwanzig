---
entity_id: feat_1539_s4_radar_parallel
type: feature
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [scheduler, nebenlaeufigkeit, parallel-fetch, radar, trip-alarm, compare-alarm, single-flight, budget, multi-user, epic-2138, issue-1539]
---

# Feature #1539 Workflow 4 — S4 Radar-Abrufe parallel

Issue #1539, Epic #2138, Workflow `feat-1539-s4-radar-parallel`, Scheibe **S4**. Zweiter Nutzer des Abruf-Bausteins
`parallel_fetch.fetch_ordered` (S2, S3 als Vorbild). #1539 bleibt danach offen (PR-Text „Refs #1539", nie „Closes").

## Approval

- [ ] Approved

## Purpose

Der Radar-Alarm ruft die Regen-Nowcasts der Zonenpunkte eines Trips und der Orte eines Ortsvergleichs heute strikt
nacheinander ab. Der Radar-Lauf läuft im 5-Minuten-Takt (ADR-0082) mit harter Laufgrenze von 45 s (ADR-0038).
Dieser Workflow lässt die Netzabrufe nebeneinander laufen und beseitigt dabei drei Gefahren der Parallelität:
Zustand, der sich zwischen Abrufen überschreibt (falsch ausgelöster oder ausbleibender Alarm), nicht-atomare
Budgetbuchung (Überbuchung) und doppelte Upstream-Calls auf dieselbe Kachel (Mehrverbrauch). Reihenfolge,
Fehlersemantik, Auslöseregel und Versand bleiben unverändert.

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `RadarNowcastService.get_nowcast` (Instanzzustand ca. `:522-560`), Open-Meteo-Pfad mit
  `_budget_gate.allow()` + `record_call()` (ca. `:1003-1023`), `RadarDeadlineExceeded` / `_raise_if_deadline`
  (ca. `:447-456`)
- **Trip-Radar:** `src/services/trip_alert.py`, Zonenschleife `for _p in _punkte[1:]` (ca. `:2310-2335`);
  erster Punkt (ca. `:2260`) bleibt seriell
- **Compare-Radar:** `src/services/compare_radar_alert.py`, `_detect_triggered_locations` (ca. `:538-596`)
- **Bausteine (unverändert):** `src/services/parallel_fetch.py` (`fetch_ordered`, `FetchOutcome`),
  `src/services/single_flight.py`, `src/services/forecast_budget.py` (`ForecastBudgetGate.reserve`, seit S1b),
  `src/services/radar_cache.py` (geteilter Cache `get_shared_radar_cache`)

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/`). Kein Go-Code, kein Frontend. Der Go-Scheduler
> bleibt Taktgeber (Radar-Takt 5 min, Wartebudget 240 s) und wird nicht angefasst.
>
> **Teilung Trip/Ortsvergleich:** Beide Radar-Flächen benutzen denselben Baustein (`fetch_ordered`) und denselben
> Dienst (`RadarNowcastService`). Es wird keine einseitige Neuanlage geschaffen; Unterschiede bestehen nur dort, wo
> die Semantik bereits heute verschieden ist (Trip: Lücke je Punkt, Abbruch der Einheit; Compare: Ausnahme wird
> hochgereicht, kein Ausfall-Protokoll bei Grenzabbruch).
>
> **Kanäle:** Der Radar-Abruf liefert die Datenbasis für Regen-/Radar-Alarme auf allen vier Kanälen (E-Mail,
> Telegram, SMS, Premium-SMS). Inhalt, Auslösung und Versand bleiben unverändert, nur die Beschaffung der
> Rohdaten wird schneller.
>
> **Mandantentrennung:** `user_id` wird in jeden Worker durchgereicht, nie `"default"` (Pflicht-AC mit zwei
> Nutzern).

## Estimated Scope

- **LoC:** ca. +110/-30 produktiv (3 Dateien), Tests ca. +250
- **Files:** 3 produktiv MODIFY (`radar_service.py`, `trip_alert.py`, `compare_radar_alert.py`), 1 Testdatei CREATE
  (`tests/tdd/test_radar_parallel_fetch.py`), diese Spec
- **Effort:** medium
- **Risk Level:** MITTEL bis HOCH — Alarmpfad, Datenwettlauf im Dienst, auf Staging nicht messbar

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1539-s4-radar-parallel.md` | Analyse | Verbindliche Analyse, Risiken, Dateien |
| `docs/context/feat-1539-parallele-abrufe.md` | Gesamtplan | Einordnung S4 gegenüber S5 bis S7 |
| `feat_1539_s1b_s2_abruf_baustein.md` | Spec (live) | Vertrag von `fetch_ordered`, `single_flight`, `reserve()` |
| `feat_1539_s3_trip_alarm_parallel.md` | Spec (live) | Vorbild: Auswertung im Hauptfaden, `skipped` zählt als gescheitert |
| `feat_2261_a2s2_radar_takt.md`, `fix_2261_a2s1_alarmlauf_reihenfolge.md` | Specs (live) | Radar-Takt 5 min, Laufgrenze, Reihenfolge |
| ADR-0021 | ADR | Feste Gate-Reihenfolge, Quellenausfall ist nie Entwarnung |
| ADR-0038 | ADR | Harte Laufzeitgrenze, sichtbarer Teilerfolg statt stilles Weglassen |
| ADR-0082 | ADR | Radar-Takt und Laufgrenze |
| ADR-0103 | ADR (bestehend) | Semaphorenzahlen (`open_meteo` = 3); gilt unverändert, kein neues ADR |

## Scope

**In Scope**

- Je paralleler Abruf eine **eigene** `RadarNowcastService`-Instanz (teilen den geteilten Radar-Cache); damit
  überschreiben sich `_openmeteo_unavailable_this_call`, `_budget_throttled_this_call`,
  `_inca_unavailable_this_call`, `_priority` und `_budget_gate` nicht gegenseitig. Kein ContextVar-Umbau.
- Single-flight um den Radar-Cache-Miss (`single_flight.py`).
- Radar-Open-Meteo-Pfad von `allow()` + `record_call()` auf atomares `ForecastBudgetGate.reserve()`.
- Trip-Radar: `_punkte[1:]` über `fetch_ordered(provider="open_meteo")`.
- Compare-Radar: Abrufe in `_detect_triggered_locations` über `fetch_ordered(provider="open_meteo")`.

**Out of Scope**

- S5 Briefing, S6 Compare-Alarm und amtliche Warnungen, S7 Go-Nutzer-Fan-out.
- Änderungen an `parallel_fetch.py`, `single_flight.py`, `forecast_budget.py`, `radar_cache.py`.
- Neue Alarmregeln, neue Metriken, Änderungen an Auswertung (`derive_rain_zones`, `_zonen_messwert`), Dedup
  (`_finalize_triggered_state`) oder Versand.
- Die Trip-Schleife über mehrere Trips bleibt seriell.

## Implementation Details

### 1. Zustand je Abruf (`radar_service.py`, `trip_alert.py`, `compare_radar_alert.py`)

Der Worker holt sich eine frische Dienst-Instanz (gleiche Fabrik wie `_get_radar_service`, aber nicht die
geteilte lazy Instanz) und ruft `get_nowcast(...)` darauf. Alle `*_this_call`-Flags, `_priority` und `_budget_gate`
leben damit je Abruf. Der geteilte Radar-Cache (`get_shared_radar_cache`) bleibt prozessweit geteilt. Die
Auswertung der Flags (Quelle nicht verfügbar, gedrosselt) geschieht im Hauptfaden aus dem Ergebnis des Workers; der
Worker gibt Ergebnis und die drei Flags als Teil seines Rückgabewerts zurück.

### 2. Single-flight um den Cache-Miss (`radar_service.py`)

Nach einem Cache-Miss läuft der Upstream-Abruf über `single_flight` mit dem Schlüssel der gerundeten Kachel
(derselbe Schlüssel wie im Radar-Cache). Parallele Abrufe auf dieselbe Kachel erzeugen genau einen Upstream-Call;
die übrigen erhalten das Ergebnis des ersten. Schlägt der erste Abruf mit Ausnahme fehl, bekommen die wartenden
dieselbe Ausnahme.

### 3. Atomares Budget (`radar_service.py`, Open-Meteo-Pfad)

`allow()` + `record_call()` werden durch einen einzigen Aufruf `reserve()` ersetzt. Bei Ablehnung ist das
Verhalten unverändert: Ergebnis „throttled" (`_budget_throttled_this_call`), kein Folgeabruf. Prioritätsregel
(`user_briefing` nie gedrosselt) und fail-open-Verhalten bleiben die des Gates.

### 4. Trip-Radar (`trip_alert.py`)

1. Der erste Zonenpunkt wird seriell abgerufen und trägt unverändert die Auslöseregel.
2. Nur `_punkte[1:]` gehen als Liste an `fetch_ordered(..., provider="open_meteo", deadline_at=<Radar-Frist>)`.
   Die Frist ist dieselbe monotonische Marke wie heute im Radar-Lauf.
3. Ergebnisse werden im Hauptfaden in Eingabereihenfolge ausgewertet. Fehler je Punkt (`error`) ⇒ `None`
   (Lücke), kein Abbruch.
4. `skipped` ("deadline"/"timeout") zählt wie gescheitert (Lücke `None`) und wird laut geloggt (ADR-0038).
5. Trat im Worker `RadarDeadlineExceeded` auf, wird sie im Hauptfaden **neu geworfen**; die bestehende Behandlung
   (`_abort_radar_unit` + Abbruch) greift. Das ist weder Lücke noch Quellenausfall noch Entwarnung.
6. `user_id` wird in jeden Worker durchgereicht.

### 5. Compare-Radar (`compare_radar_alert.py`)

1. `_detect_triggered_locations` ruft die Orte über `fetch_ordered(..., provider="open_meteo")` ab.
2. Auswertung (Auslöseprüfung) und Sammeln der Ausfälle (`ausfaelle`) geschehen im Hauptfaden, in
   Eingabereihenfolge der Orte.
3. `RadarDeadlineExceeded` aus einem Worker wird im Hauptfaden neu geworfen und hochgereicht (Preset gilt als
   „nicht erreicht"). Bei Grenzabbruch werden die Ausfälle **nicht** protokolliert; die bestehende
   `finally`-Semantik bleibt erhalten.
4. `skipped` zählt wie gescheitert und wird laut geloggt.
5. `user_id` wird in jeden Worker durchgereicht.

### Wirkmaß

Wirkmaß ist `duration_s` des Radar-Laufs im Prod-Journal (S0), nicht der Go-Überlaufzähler. Zonenpunkte je Trip
typisch 2 bis 5, Orte je Preset typisch 3 bis 9. Echte Nebenläufigkeit ist auf Staging nicht messbar
(`NOT_MEASURABLE_ON_STAGING`).

## Expected Behavior

- **Input:** Zonenpunkte eines Trips bzw. Orte eines Ortsvergleichs (unverändert).
- **Output:** Radar-Nowcasts in Eingabereihenfolge; gescheiterte oder übersprungene Punkte/Orte als Lücke bzw.
  Ausfall wie bisher. Auslösung, Entwarnung und Dedup unverändert.
- **Side effects:** Kürzere Laufzeit des Radar-Laufs bei mehreren Punkten/Orten. Keine zusätzlichen
  Open-Meteo-Calls pro Tag, Budget wird atomar gebucht.

## Acceptance Criteria

- **AC-1:** Given zwei Radar-Abrufe laufen gleichzeitig, der eine mit Open-Meteo-Fehler (Quelle nicht verfügbar),
  der andere erfolgreich / When beide parallel ausgewertet werden / Then behält jeder Abruf sein eigenes Ergebnis
  und seine eigenen Flags: der erfolgreiche meldet „verfügbar", der fehlgeschlagene „nicht verfügbar", und kein
  Abruf übernimmt den Zustand des anderen (auch nicht nach vielen Wiederholungen).
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; gezielt verzögerte Provider-Antworten, Flags je Abruf
    ausgelesen, Wiederholungslauf; Thread-Fehler werden selbst eingesammelt.

- **AC-2:** Given ein Trip mit fünf Zonenpunkten, deren Abrufe in umgekehrter Reihenfolge fertig werden / When
  der Trip-Radar läuft / Then sind die Ergebnisse in der ursprünglichen Reihenfolge der Zonenpunkte, der erste
  Punkt wurde seriell vor allen anderen abgerufen, und die Zonen werden aus dieser Reihenfolge abgeleitet.
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; absteigende Verzögerung am Provider-Rand, Reihenfolge der
    Ergebnisse und Startreihenfolge des ersten Punkts geprüft.

- **AC-3:** Given ein Trip mit vier Zonenpunkten, bei dem der Abruf des dritten Punkts scheitert / When der
  Trip-Radar läuft / Then fehlt nur dieser Punkt (Lücke), die übrigen werden ausgewertet, der Lauf bricht nicht
  ab, der Ausfall steht mit Punkt im Log, und es wird weder ein Alarm unterdrückt noch Entwarnung gesendet.
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; Fehler gezielt für einen Punkt am Provider-Rand.

- **AC-4:** Given die Radar-Frist läuft während des Abrufs einer der weiteren Zonenpunkte ab / When der
  Trip-Radar den im Worker aufgetretenen `RadarDeadlineExceeded` verarbeitet / Then wird die Ausnahme im
  Hauptfaden neu geworfen, die Radar-Einheit wird abgebrochen (`_abort_radar_unit`), und es entsteht weder eine
  Lücke noch ein Quellenausfall noch eine Entwarnung für diesen Trip.
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; Frist im Test verkürzt, Abbruchzustand und fehlende
    Entwarnung/Quellenausfall geprüft. Bestandstest `tests/tdd/test_alert_run_deadline.py` bleibt grün.

- **AC-5:** Given ein Ortsvergleich-Preset mit mehreren Orten, bei dem ein Worker `RadarDeadlineExceeded` wirft
  / When `_detect_triggered_locations` läuft / Then wird die Ausnahme hochgereicht (Preset gilt als nicht
  erreicht), und bei diesem Grenzabbruch wird keine Spur im Ausfall-Protokoll geschrieben; ohne Grenzabbruch
  werden die Ausfälle wie bisher nach der Schleife protokolliert.
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; beide Fälle (Grenzabbruch, normaler Teilausfall) mit dem
    echten Ausfall-Protokoll; Bestandstests zum Compare-Radar-Ausfall-Protokoll (#2050 S4a) bleiben grün.

- **AC-6:** Given zwei Zonenpunkte bzw. Orte, die auf dieselbe gerundete Kachel fallen / When ihre Abrufe
  gleichzeitig gestartet werden und der Radar-Cache leer ist / Then entsteht am Provider-Rand genau ein
  Upstream-Call für diese Kachel, beide Abrufe erhalten dasselbe Ergebnis, und die Zahl der Open-Meteo-Calls im
  parallelen Ablauf ist kleiner oder gleich der im seriellen.
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; Zähler an der HTTP-Grenze, seriell gegen parallel, Fall mit
    gleicher Kachel und Fall mit verschiedenen Kacheln.

- **AC-7:** Given das Open-Meteo-Tagesbudget ist knapp und mehrere Radar-Abrufe wollen gleichzeitig buchen /
  When alle über das atomare `reserve()` buchen / Then wird das Budget nicht überbucht (nie mehr bewilligte
  Calls als Restbudget), jeder abgelehnte Abruf liefert „throttled" ohne Folgeabruf, und die Zahl der gebuchten
  Calls stimmt mit der Zahl der tatsächlichen Upstream-Calls überein.
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; echtes Budget-Gate mit kleinem Restbudget, parallele Abrufe,
    Zähler an der HTTP-Grenze gegen Gate-Stand.

- **AC-8:** Given eine Frist, die bereits ganz oder teilweise abgelaufen ist, und mehr Punkte bzw. Orte als freie
  Slots / When der Radar-Abruf endet / Then zählt jeder übersprungene Punkt (`skipped` mit Grund Frist oder
  Zeitüberschreitung) wie gescheitert, fehlt im Ergebnis, und für jeden steht eine Fehlerzeile mit Grund im Log;
  nichts wird still weggelassen.
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; Open-Meteo auf einen Slot begrenzt, Frist verkürzt, Logzeilen
    und Ergebnis geprüft (Trip- und Compare-Pfad).

- **AC-9:** Given zwei verschiedene Nutzer mit je einem Trip bzw. Ortsvergleich führen gleichzeitig den
  Radar-Abruf aus / When die Worker laufen / Then trägt jeder Abruf die `user_id` seines Nutzers (am
  Provider-Rand erfasst, nie `"default"` oder `None`), Journal und Budget je Nutzer werden nicht vermischt, und
  kein Punkt oder Ort des einen Nutzers erscheint im Ergebnis des anderen.
  - Test: `tests/tdd/test_radar_parallel_fetch.py` mit zwei `user_id`; Thread-Fehler gesammelt.

- **AC-10:** Given der erste Zonenpunkt eines Trips löst die Auslöseregel nicht aus bzw. scheitert / When der
  Trip-Radar läuft / Then verhält sich der Lauf für den ersten Punkt wie bisher (eigene Fehlersemantik, gleiche
  Auslöseentscheidung wie im seriellen Ablauf), und ein paralleler Folgepunkt ändert diese Entscheidung nicht.
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; Vergleich serielle gegen parallele Entscheidung für
    dieselben Eingaben; Bestandstests `test_radar_alarmlauf_*` und Radar-Zonen-Tests (#2051 S2a) bleiben grün.

- **AC-11:** Given ein Radar-Lauf mit mehreren Zonenpunkten und Orten, parallel abgerufen / When der Lauf endet
  / Then werden `versucht`, `gescheitert` und die Ausfallsammlung ausschließlich vom Hauptfaden geschrieben
  (kein Schreibzugriff aus einem Worker-Thread) und stimmen nach vielen Wiederholungen mit gemischtem
  Erfolg/Fehler immer mit der Zahl der abgerufenen und gescheiterten Punkte überein.
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; schreibende Thread-Kennung erfasst und mit dem Hauptfaden
    verglichen, Wiederholungslauf.

- **AC-12:** Given ein Trip-Radar-Lauf mit mehreren Zonenpunkten / When der Lauf endet / Then steht die
  Laufdauer `duration_s` des Radar-Laufs im Journal, und die Dauer eines Laufs mit parallelen Abrufen mit
  künstlicher Verzögerung je Punkt liegt bei sechs Zonenpunkten mit je 0,5 s Verzögerung und drei Abruf-Plätzen
  unter 60 % der Summe der Einzelverzögerungen (also unter 1,8 s bei 3,0 s Summe).
  - Test: `tests/tdd/test_radar_parallel_fetch.py`; feste Verzögerung je Punkt am Provider-Rand, gemessene
    Laufdauer gegen Summe. Die Prod-Wirkung wird nach dem Deploy aus `duration_s` im Prod-Journal nachgemessen.

## Testplan

Eine nach Verhalten benannte Testdatei: `tests/tdd/test_radar_parallel_fetch.py` (Kern-Schicht, deterministisch,
ohne Netz). Wetterdaten kommen als versionierte Fixtures am Provider-Rand; Zähler und Verzögerungen sitzen an
Provider/HTTP, **nicht** im Prüfling. Kein Mock-Theater: Budget-Gate, Radar-Cache und Journal sind die echten.
Concurrency-Tests sammeln Thread-Ausnahmen selbst ein. Der Prüfling wird relativ zur Testdatei aufgelöst
(Worktree-sicher).

| Datei | Prüft |
|---|---|
| `tests/tdd/test_radar_parallel_fetch.py` (neu) | AC-1 bis AC-12 |
| `tests/tdd/test_alert_run_deadline.py`, `test_radar_alarmlauf_*`, Radar-Zonen-Tests, Compare-Radar-Ausfall-Protokoll (bestehend) | AC-4, AC-5, AC-10 bleiben grün |

**Mutations-Gegenprobe (Pflicht für den Adversary, nur per String-Ersetzung mit externer Sicherungskopie, nie
`git checkout/stash/reset`; zu klären ist jeweils, **welcher** Test rot wird):**

1. Worker nutzt die geteilte Dienst-Instanz statt einer eigenen ⇒ AC-1 rot.
2. Single-flight um den Cache-Miss entfernen ⇒ AC-6 rot.
3. `reserve()` zurück auf `allow()` + `record_call()` ⇒ AC-7 rot.
4. Ergebnisse in Fertigstellungs- statt Eingabereihenfolge einsammeln ⇒ AC-2 rot.
5. Ersten Punkt mit den übrigen parallel starten ⇒ AC-2 oder AC-10 rot.
6. `RadarDeadlineExceeded` im Hauptfaden zu `None` (Lücke) machen ⇒ AC-4 rot.
7. Im Compare-Pfad die Ausnahme schlucken oder Ausfälle auch bei Grenzabbruch protokollieren ⇒ AC-5 rot.
8. `skipped` nicht als gescheitert zählen oder nicht loggen ⇒ AC-8 rot.
9. `user_id` im Worker auf `"default"` oder `None` setzen ⇒ AC-9 rot.
10. `versucht`/`gescheitert` oder Ausfallsammlung aus dem Worker schreiben ⇒ AC-11 rot.

## Known Limitations

- **Begrenzter Hebel:** 2 bis 5 Zonenpunkte je Trip bzw. 3 bis 9 Orte je Preset; Gewinn real, aber begrenzt.
  Wirkmaß ist `duration_s` im Radar-Lauf, nicht der Go-Überlaufzähler.
- **Laufende Threads sind nicht abbrechbar:** Ein zu später Abruf wird verworfen (`timeout`), sein Thread hält
  den Slot bis zum Ende.
- **Nebenläufigkeit auf Staging nicht messbar** (`NOT_MEASURABLE_ON_STAGING`): Verhalten wird im Kern durch
  Tests bewiesen, die Wirkung erst durch Nachmessung im Prod-Journal.
- **Slotzahl ist ein Startwert** aus ADR-0103 (`open_meteo` = 3, Prüfdatum 2027-01-26). Radar nutzt zusätzlich
  DWD/Météo-France-Quellen der Kette; der Provider-Schlüssel für `fetch_ordered` ist `open_meteo`.

## Verbleibt in #1539

- **S5:** Briefing-Abrufe parallel.
- **S6:** Compare-Alarm und amtliche Warnungen parallel.
- (S7 Go-Nutzer-Fan-out gemäß Gesamtplan.) #1539 bleibt bis dahin offen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** ADR-0103 (Semaphorenzahlen, `open_meteo` = 3) gilt unverändert; die Zustandsentkopplung je
  Abruf, das Single-flight und die Umstellung auf `reserve()` sind lokale Umsetzungsdetails ohne neue
  Grundsatzentscheidung. ADR-0021 (Gate-Reihenfolge) und ADR-0038 (Laufgrenze) bleiben gültig.

## Changelog

- 2026-10-30: Initial spec created (Workflow feat-1539-s4-radar-parallel, S4)
