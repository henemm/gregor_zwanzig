---
entity_id: feat_1539_s3_trip_alarm_parallel
type: feature
created: 2026-10-28
updated: 2026-10-28
status: draft
version: "1.0"
tags: [scheduler, nebenlaeufigkeit, parallel-fetch, trip-alarm, call-source, multi-user, adr, epic-2138, issue-1539]
---

# Feature #1539 Workflow 3 — S3 Trip-Alarm: Etappen-Abruf parallel

Issue #1539, Epic #2138, Workflow `feat-1539-s3-trip-alarm-parallel`, Scheibe **S3**. Erster echter Nutzer des
Abruf-Bausteins `parallel_fetch.fetch_ordered` (S2, live seit 2026-10-08). #1539 bleibt danach offen
(PR-Text „Refs #1539", nie „Closes").

## Approval

- [ ] Approved

## Purpose

Der Trip-Alarm ruft das Wetter der Etappen eines Trips heute strikt nacheinander ab. Läufe brechen deshalb an der
Zeitobergrenze von 180 s ab (gemessen: typisch 37 s je Lauf im p95, Spitze 215 s). Dieser Workflow lässt die
Netzabrufe der fälligen Etappen eines Trips nebeneinander laufen, ohne dass sich Reihenfolge, Fehlerverhalten,
Herkunftsbuchung im Journal oder die Zahl der Open-Meteo-Abrufe ändern. Zusätzlich werden die Semaphorenzahlen
für Open-Meteo gemessen und als ADR festgehalten.

## Source

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService._fetch_fresh_weather` (ca. `:2954-3020`), `check_all_trips` (ca. `:1096-1300`,
  setzt die Frist), `check_and_send_alerts` (Aufrufer, wertet `_fetch_stats` aus, ca. `:742-757`)
- **Baustein (unverändert):** `src/services/parallel_fetch.py` (`fetch_ordered`, `FetchOutcome`)
- **Herkunftsbuchung (unverändert):** `src/providers/call_log.py` (`resolve_call_source`, `override_call_source`)
- **Zweiter Aufrufer (unverändert):** `src/services/alert_preview_hours.py` (`trip_preview_series`)
- **Neu:** `docs/adr/0103-parallele-abrufe-semaphorenzahlen.md`, Eintrag in `docs/adr/README.md`

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/`). Kein Go-Code, kein Frontend. Der Go-Scheduler
> bleibt Taktgeber; sein Wartebudget (300 s, Invariante `180 + 64 <= 300`, ADR-0038) wird nicht angefasst.
>
> **Teilung Trip/Ortsvergleich:** Der Trip-Alarm hat kein Compare-Pendant an dieser Stelle; der Ortsvergleich
> nutzt `comparison_parallel.py` und kommt in S6 auf den gemeinsamen Baustein. Keine einseitige Neuanlage: es
> wird der vorhandene gemeinsame Baustein benutzt.
>
> **Kanäle:** Der Abruf liefert die Datenbasis für Alarme auf allen vier Kanälen (E-Mail, Telegram, SMS,
> Premium-SMS). Inhalt und Versand bleiben unverändert; nur die Beschaffung der Rohdaten wird schneller.
>
> **Mandantentrennung:** `user_id` wird unverändert in jeden Abruf durchgereicht (Pflicht-AC mit zwei Nutzern).

## Estimated Scope

- **LoC:** ca. +70/-25 Produktivcode, Tests ca. +200
- **Files:** 1 produktiv MODIFY (`trip_alert.py`), 1 ADR CREATE, 1 ADR-Index MODIFY, 1 Testdatei CREATE
- **Effort:** medium
- **Risk Level:** MITTEL — zentraler Alarm-Pfad, echte Nebenläufigkeit, auf Staging nicht messbar

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1539-s3-trip-alarm-parallel.md` | Analyse | Verbindliche Analyse und Entscheidungen |
| `docs/context/feat-1539-parallele-abrufe.md` | Gesamtplan | Einordnung S3 gegenüber S4 bis S7, Vorher-Messung |
| `feat_1539_s1b_s2_abruf_baustein.md` | Spec (live) | Vertrag von `fetch_ordered`: Reihenfolge, Teilausfall, Slot mit Frist, `skipped` |
| `fix_1329_forecast_cache_budget.md` | Spec (live) | Gleiche Koordinate/Stunde ⇒ ein Upstream-Call; `user_briefing` nie gedrosselt |
| ADR-0038 | ADR | Harte Laufzeitgrenze je Lauf, sichtbarer Teilerfolg statt stilles Weglassen |
| ADR-0100 | ADR | Regel-Budget: neue Festlegung trägt Prüfdatum +90 Tage |
| `src/services/segment_weather.py` | Dienst | Single-flight und atomares `reserve()`; bereits parallel-sicher |
| `#2218 enrichment_health` | Feature | wertet `_fetch_stats` aus; Semantik „leer ohne Versuch = Normalfall" bleibt |

## Scope

**In Scope**

- Netzabruf der fälligen Etappen in `_fetch_fresh_weather` über `fetch_ordered(provider="open_meteo")`.
- Durchreichen der Lauf-Frist per Instanzfeld `_run_deadline_at`.
- Herkunft (`call_source`) „alarm" bzw. „vorschau" auch im Worker-Thread.
- Messung der Open-Meteo-Semaphorenzahl und ADR-0103.

**Out of Scope**

- Die Trip-Schleife in `check_all_trips` bleibt **seriell** (Rotation #2261, Fairness und State-Write).
- Radar-Alarm (S4), Briefing (S5), Ortsvergleich (S6), Go-Nutzer-Fan-out (S7).
- Änderungen an `parallel_fetch.py`, `call_log.py`, `alert_preview_hours.py`, `segment_weather.py`.
- Neue Wetter-Metriken, neue Alarm-Regeln, Änderungen an Δ-Auswertung oder Versand.
- Kachelrundung des Caches.

## Implementation Details

### Ablauf in `_fetch_fresh_weather` (Signatur unverändert)

1. **Zeitfilter seriell im Hauptfaden** (wie heute): Etappen mit `end_time < jetzt` oder `start_time.date() > heute`
   fallen weg. Es entsteht die Liste der fälligen Etappen in Eingabereihenfolge. `versucht` = Länge dieser Liste.
2. **Herkunft auflösen im Aufrufer-Thread:** Dort, wo der Aufruf-Stapel noch bekannt ist, wird
   `resolve_call_source()` aufgelöst (liefert „alarm" im Alarmlauf, „vorschau" über die Vorschau). Die
   Worker-Funktion setzt diesen Wert per `override_call_source(...)` (ContextVar). Im Worker fehlt der Frame
   `_fetch_fresh_weather`, deshalb darf er sich nicht auf die Stapelerkennung verlassen.
3. **Frist:** `deadline_at = self._run_deadline_at`, falls gesetzt; sonst `time.monotonic() + 60 s`
   (angelehnt an `FETCH_DEADLINE_SECONDS` von Open-Meteo). Nie unbegrenzt (ADR-0038).
   `check_all_trips` setzt `self._run_deadline_at` neben der lokalen `deadline_at` (`run_started_at + 180 s`)
   und setzt es nach dem Lauf (auch bei Ausnahme, `finally`) zurück.
4. **Abruf:** `fetch_ordered(fällige, fn, provider="open_meteo", deadline_at=deadline_at)`. `fn` ruft
   `service.fetch_segment_weather(segment, enrich_ensemble=False, enrich_snow=False, priority="alert_check",
   user_id=self._user_id)` und misst die Dauer.
5. **Auswertung seriell im Hauptfaden**, in Eingabereihenfolge: Erfolg ⇒ an `fresh_weather` anhängen.
   `error` oder `skipped` ("deadline"/"timeout") ⇒ `gescheitert += 1` und `logger.error` mit Etappe und Grund.
   Die Etappe fehlt dann in `fresh_weather` (gleiche Semantik wie heute bei einem Einzelfehler).
6. **Dauerzeile (S0):** Pro Etappe genau eine Zeile „Etappe X: Abruf in N s", im Hauptfaden geloggt (die Dauer
   wird im Worker gemessen und im Ergebnis mitgegeben).
7. **Schreibzugriffe:** `self._fetch_stats = (versucht, gescheitert)` und `fresh_weather` werden **nur** im
   Hauptfaden geschrieben, nie aus einem Worker.

`max_parallel` bekommt keine feste Obergrenze: fällige Etappen sind im Alarm-Fenster typisch 1 bis 6, und die
Slotzahl des Bausteins begrenzt ohnehin.

### Messung und ADR-0103

- **Messgrößen:** Anteil der Antworten 503/429 von Open-Meteo sowie Etappen-Abrufdauer (p50/p95) im Prod-Journal
  vor und nach der Umstellung, bei Slotzahl 3.
- **Messquelle:** Prod-Journal per `sudo -n -u claude-gregor journalctl` (für `hem` ohne diesen Weg nicht lesbar;
  auf Staging ist echte Nebenläufigkeit nicht messbar). Die Messung ist ein eigener Schritt nach dem Deploy.
- **Vorher-Messung (steht fest):** p95 je Lauf 37 s, Spitze 215 s, Abbrüche an der 180-s-Grenze.
- **ADR-0103** legt fest: Startwert Open-Meteo = **3** Slots (MeteoAlarm 1, Météo-France 4 unverändert), die
  Messmethode (oben), die Stellschraube `GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO`, und das **Prüfdatum 2027-01-26**
  (+90 Tage). Am Prüfdatum wird die Zahl gegen die Messwerte bestätigt oder korrigiert. Der ADR wird in
  `docs/adr/README.md` indiziert (Tabellenzeile, Status „Akzeptiert"); `tests/test_adr_index_drift.py` muss grün
  bleiben.

## Expected Behavior

- **Input:** Liste zwischengespeicherter Etappen-Wetterdaten eines Trips (unverändert).
- **Output:** Liste frischer Etappen-Wetterdaten in Eingabereihenfolge; gescheiterte oder übersprungene Etappen
  fehlen. `_fetch_stats = (versucht, gescheitert)` wie bisher.
- **Side effects:** Kürzere Wartezeit je Trip bei mehreren fälligen Etappen. Journal bucht weiter „alarm" bzw.
  „vorschau". Keine zusätzlichen Open-Meteo-Calls pro Tag.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit fünf fälligen Etappen, deren Abrufe in umgekehrter Reihenfolge fertig werden
  / When `_fetch_fresh_weather` läuft / Then enthält die Ergebnisliste die Etappen in der ursprünglichen
  Reihenfolge des Trips, unabhängig davon, welcher Abruf zuerst zurückkam.
  - Test: `tests/tdd/test_trip_alert_parallel_fetch.py`; Abrufe mit absteigender Verzögerung am Provider-Rand.

- **AC-2:** Given ein Trip mit vier fälligen Etappen, bei denen der Abruf der zweiten Etappe scheitert
  / When `_fetch_fresh_weather` läuft / Then werden die übrigen drei Etappen trotzdem geliefert, die zweite
  fehlt, `_fetch_stats` steht auf (4, 1), und der Fehler steht mit Etappe im Log.
  - Test: `tests/tdd/test_trip_alert_parallel_fetch.py`; Fehler gezielt für eine Etappe am Provider-Rand.

- **AC-3:** Given die Lauf-Frist läuft ab, bevor alle Etappen abgerufen sind (Frist im Test verkürzt, Open-Meteo
  auf einen Slot begrenzt) / When `_fetch_fresh_weather` endet / Then zählt jede übersprungene Etappe (nicht
  gestartet oder zu spät) als gescheitert in `_fetch_stats`, fehlt in der Ergebnisliste, und für jede steht eine
  Fehlerzeile mit Grund (Frist bzw. Zeitüberschreitung) im Log, nichts wird still weggelassen.
  - Test: `tests/tdd/test_trip_alert_parallel_fetch.py`; prüft `_fetch_stats`, Ergebnisliste und Logzeilen.

- **AC-4:** Given ein Alarmlauf (Aufruf aus dem Alarm-Pfad) / When die Etappen in Worker-Threads abgerufen
  werden / Then bucht das Open-Meteo-Journal jeden dieser Abrufe mit der Herkunft „alarm", keinen mit
  „unbekannt".
  - Test: `tests/tdd/test_trip_alert_parallel_fetch.py`; echtes Journal, Herkunft je Zeile ausgewertet.
    Der Bestandstest `test_bug_338_openmeteo_call_counter.py` bleibt grün.

- **AC-5:** Given die Vorschau (`trip_preview_series`) ruft `_fetch_fresh_weather` über ihren Hilfsfaden
  / When die Etappen in Worker-Threads abgerufen werden / Then bucht das Journal diese Abrufe mit der Herkunft
  „vorschau" und nicht mit „alarm".
  - Test: `tests/tdd/test_trip_alert_parallel_fetch.py`; Aufruf über den echten Vorschau-Weg.

- **AC-6:** Given `check_all_trips` hat die Lauf-Frist gesetzt / When `_fetch_fresh_weather` den Baustein
  aufruft / Then erhält der Baustein genau diese Frist (`_run_deadline_at`); nach dem Lauf, auch nach einer
  Ausnahme, ist das Feld zurückgesetzt. Ein Aufruf ohne gesetztes Feld (Vorschau, Einzelaufruf) bekommt eine
  endliche Frist von etwa 60 s ab Aufruf, niemals eine unbegrenzte.
  - Test: `tests/tdd/test_trip_alert_parallel_fetch.py`; die beim Baustein ankommende Frist wird gelesen;
    Fall mit gesetztem Feld, ohne Feld und nach Ausnahme im Lauf.

- **AC-7:** Given Worker, die parallel Ergebnisse liefern / When `_fetch_fresh_weather` endet / Then sind
  `_fetch_stats` und die Ergebnisliste ausschließlich vom Hauptfaden geschrieben worden (kein Schreibzugriff
  aus einem Worker-Thread), und `_fetch_stats` stimmt nach vielen Wiederholungen immer mit der Zahl der
  fälligen und der gescheiterten Etappen überein.
  - Test: `tests/tdd/test_trip_alert_parallel_fetch.py`; die schreibende Thread-Kennung wird erfasst und mit dem
    Hauptfaden verglichen, plus Wiederholungslauf mit gemischtem Erfolg/Fehler; Thread-Fehler werden selbst
    eingesammelt (C4-62).

- **AC-8:** Given zwei verschiedene Nutzer mit je einem Trip führen gleichzeitig den Alarm-Abruf aus / When die
  Worker laufen / Then trägt jeder Abruf die `user_id` seines Nutzers (am Provider-Rand erfasst), das
  Journal und das Budget je Nutzer werden nicht vermischt, und keine Etappe des einen Nutzers erscheint im
  Ergebnis des anderen.
  - Test: `tests/tdd/test_trip_alert_parallel_fetch.py` mit zwei `user_id`; Thread-Fehler gesammelt.

- **AC-9:** Given dieselben Trips mit mehreren fälligen Etappen, einmal im bisherigen seriellen Ablauf und einmal
  mit dem neuen parallelen Ablauf (auch mit Etappen am gleichen Ort) / When die echten Upstream-Calls am
  Provider-Rand gezählt werden / Then ist die Zahl der Open-Meteo-Calls im parallelen Ablauf kleiner oder
  gleich der im seriellen, es entstehen keine zusätzlichen Calls pro Tag.
  - Test: `tests/tdd/test_trip_alert_parallel_fetch.py`; Zähler an der HTTP-Grenze, seriell gegen parallel.

- **AC-10:** Given Etappen, die bereits beendet sind oder erst morgen oder später beginnen, und Aufrufer, die
  `_fetch_fresh_weather` ersetzen / When der Alarm-Pfad läuft / Then werden beendete und künftige Etappen weiter
  nicht abgerufen und nicht in `versucht` gezählt, ein Trip ganz ohne fällige Etappe meldet (0, 0), und die
  Bestandstests bleiben grün: `tests/tdd/test_bundle_791_847_844_alerts.py`,
  `tests/tdd/test_bug_338_openmeteo_call_counter.py`,
  `tests/tdd/test_briefing_anchor_survives_dispatch_failure.py`,
  `tests/tdd/test_ruhezeit_und_zaehler_folgen_der_ortszone.py`.
  - Test: `tests/tdd/test_trip_alert_parallel_fetch.py` (Zeitfilter mit eingefrorener Uhr) plus die genannten
    Bestandstests unverändert.

- **AC-11:** Given ein Trip mit mehreren fälligen Etappen, parallel abgerufen / When der Lauf ins Log schreibt
  / Then steht für jede Etappe genau eine Zeile „Etappe X: Abruf in N s", auch für gescheiterte und
  übersprungene Etappen, nie zwei und nie keine.
  - Test: `tests/tdd/test_trip_alert_duration_logging.py` (bestehend, bleibt grün) und ein Parallelfall in
    `tests/tdd/test_trip_alert_parallel_fetch.py`.

- **AC-12:** Given der Abruf-Code mit der Slotzahl für Open-Meteo / When ADR-0103 gelesen wird / Then nennt er
  die Semaphorenzahl Open-Meteo (Startwert 3), die Messmethode (503/429-Anteil und Abrufdauer p50/p95 vor und
  nach der Umstellung, Quelle Prod-Journal), die Stellschraube `GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO` und das
  Prüfdatum 2027-01-26; die Zeile steht in `docs/adr/README.md`.
  - Test: `tests/test_adr_index_drift.py` (bestehend) prüft die Index-Konsistenz; als `# doc-compliance-test`
    markierter Test prüft, dass ADR-0103 die vier Angaben und das Prüfdatum enthält.

## Testplan

Eine nach Verhalten benannte Testdatei: `tests/tdd/test_trip_alert_parallel_fetch.py` (Kern-Schicht,
deterministisch, ohne Netz). Wetterdaten kommen als versionierte Fixtures am Provider-Rand; Zähler und
Verzögerungen sitzen an Provider/HTTP, **nicht** in `_fetch_fresh_weather`. Kein Mock-Theater: das Journal ist das
echte, die Frist wird aus dem Baustein-Aufruf gelesen, nicht eingespiegelt. Concurrency-Tests sammeln Thread-
Ausnahmen selbst ein und prüfen sie (pytest meldet sie sonst nur als Warnung). Der Prüfling wird relativ zur
Testdatei aufgelöst (Worktree-sicher). Vorbilder: `tests/unit/test_parallel_fetch_*.py`,
`tests/unit/test_call_source_ueber_threadgrenze.py`, `tests/unit/test_comparison_parallel.py`.

| Datei | Prüft |
|---|---|
| `tests/tdd/test_trip_alert_parallel_fetch.py` | AC-1 bis AC-11 |
| `tests/tdd/test_trip_alert_duration_logging.py` (bestehend) | AC-11 |
| `tests/test_adr_index_drift.py` (bestehend) und Doc-Test zu ADR-0103 | AC-12 |
| Bestandstests aus AC-10 | AC-10 |

**Mutations-Gegenprobe (Pflicht für den Adversary, nur per String-Ersetzung mit externer Sicherungskopie, nie
`git checkout/stash/reset`; zu klären ist jeweils, **welcher** Test rot wird):**

1. `override_call_source` im Worker weglassen ⇒ AC-4 und AC-5 rot.
2. Feste Überschreibung auf „alarm" statt aufgelöster Herkunft ⇒ AC-5 rot.
3. Ergebnisse in Fertigstellungsreihenfolge statt Eingabereihenfolge einsammeln ⇒ AC-1 rot.
4. `skipped` nicht als gescheitert zählen ⇒ AC-3 rot.
5. Frist nicht durchreichen (`deadline_at` unbegrenzt oder `inf`) ⇒ AC-6 rot.
6. `_run_deadline_at` nach dem Lauf nicht zurücksetzen ⇒ AC-6 rot (Fall nach Ausnahme).
7. `_fetch_stats` oder `fresh_weather.append` aus der Worker-Funktion schreiben ⇒ AC-7 rot.
8. `user_id` im Worker auf `"default"` oder `None` setzen ⇒ AC-8 rot.
9. Zeitfilter in den Worker verlegen oder Filterbedingung verfälschen ⇒ AC-10 rot.
10. Dauerzeile im Worker und im Hauptfaden loggen ⇒ AC-11 rot.

## Known Limitations

- **Wenig Hebel bei wenigen Etappen:** Der Zeitfilter lässt nur heutige, nicht beendete Etappen durch (typisch
  1 bis 6). Der Gewinn hängt von der Etappenzahl des Trips ab.
- **Laufende Threads sind nicht abbrechbar:** Eine zu späte Etappe wird verworfen (`timeout`), ihr Thread hält
  den Slot bis zum Ende.
- **Teilmenge bei Ausfall:** Fehlt eine Etappe, wird die Δ-Auswertung wie bisher auf der vorhandenen Teilmenge
  gerechnet; `enrichment_health` sieht den Ausfall über `gescheitert`.
- **Nebenläufigkeit auf Staging nicht messbar** (`NOT_MEASURABLE_ON_STAGING`): Verhalten wird im Kern durch
  Tests bewiesen, die Wirkung (Laufzeit, 503-Anteil) erst durch die Nachmessung im Prod-Journal.
- **Semaphorenzahl ist ein Startwert:** 3 für Open-Meteo wird nach dem Deploy nachgemessen; Prüfdatum 2027-01-26.
- **Trips bleiben seriell:** Mehrere Trips eines Laufs werden weiter nacheinander verarbeitet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0103 (neu, Status „Akzeptiert", Prüfdatum 2027-01-26)
- **Rationale:** Die Semaphorenzahlen begrenzen die Last auf Open-Meteo und berühren die Provider-Fläche; sie
  werden mit dem ersten echten Nutzer des Bausteins gemessen und mit Messmethode und Prüfdatum festgehalten
  (Regel-Budget, ADR-0100). Ohne ADR wäre die Zahl eine stille Annahme. ADR-0038 (harte Laufzeitgrenze) bleibt
  gültig und wird durch die durchgereichte Frist eingehalten.

## Changelog

- 2026-10-28: Initial spec created (Workflow feat-1539-s3-trip-alarm-parallel, S3)
