---
entity_id: feat_1539_s6_compare_parallel
type: feature
created: 2026-10-30
updated: 2026-10-30
status: draft
version: "1.0"
tags: [scheduler, nebenlaeufigkeit, parallel-fetch, ortsvergleich, aenderungs-alarm, amtliche-warnungen, multi-user, epic-2138, issue-1539]
---

# Feature #1539 Workflow 6 — S6 Ortsvergleich-Alarme parallel

Issue #1539, Epic #2138, Workflow `feat-1539-s6-compare-parallel`, Scheibe **S6**. Vierter Nutzer des Abruf-Bausteins
`parallel_fetch.fetch_ordered` (Vorbilder: S3 Trip-Alarm, S4 Radar, S5 Briefing). #1539 bleibt danach offen (PR-Text
„Refs #1539", nie „Closes").

## Approval

- [ ] Approved

## Purpose

Die beiden Ortsvergleich-Alarmpfade rufen ihre Daten je Ort noch strikt nacheinander ab: (1) der
Änderungs-Alarm (`CompareAlertService`) holt je Ort das frische Wetter, (2) der Alarm für amtliche Warnungen
(`CompareOfficialAlertService`) holt je Ort die Warnungen. Bei einem Preset mit mehreren Orten addieren sich die
Wartezeiten; der Alarmlauf je Nutzer verbraucht dadurch Wartebudget des Go-Takts (ADR-0038). Dieser Workflow lässt
die **Netzabrufe** dieser beiden Pfade je Preset nebeneinander laufen. Es ist eine **rein mechanische Umstellung ohne
Verhaltenswechsel für Nutzer**: gleiche Alarme, gleiche Reihenfolge, gleiche Fehlersemantik, gleicher Versand, keine
neuen Texte, keine neuen Metriken, keine Handlungsempfehlungen.

## Source

- **File:** `src/services/compare_alert.py`
- **Identifier:** `CompareAlertService._detect_triggered_locations`, `CompareAlertService._evaluate_one_location`
  (ca. `:576-683`; wird in `_vorbereite_ort` und `_bewerte_ort` getrennt)
- **Netzabruf (Latenzblock):** `self._weather_source.fetch(...)` ca. `:651`
- **File:** `src/services/compare_official_alert.py`
- **Identifier:** `CompareOfficialAlertService._fetch_locations` (ca. `:487-504`, serielle Schleife um
  `get_official_alerts_for_location`), `_detect` (ca. `:416`, Aufrufer), `_day_window_end` (ca. `:506`)
- **Bausteine (unverändert):** `src/services/parallel_fetch.py` (`fetch_ordered`, `FetchOutcome`),
  `src/services/official_alerts/base.py` (`collect_source_queries`, ContextVar `_source_query_sink`),
  `src/services/compare_location_weather_source.py` (`CompareLocationWeatherSource.fetch`),
  `src/services/official_alerts/warn_egress.py` (`cached_fetch`, Single-flight)
- **Frist-Konstanten (Referenz, unverändert):** `src/services/trip_alert.py`
  `FRESH_WEATHER_DEFAULT_DEADLINE_SECONDS = 60.0` (ca. `:81`) und `ALERT_RUN_DEADLINE_SECONDS = 180.0` (ca. `:71`);
  Durchreichung in S3 über `self._run_deadline_at` mit Standardwert (ca. `:3025-3027`)

> **Schicht-Hinweis:** Ausschließlich Python-Core (`src/services/compare_alert.py`,
> `src/services/compare_official_alert.py`). Kein Go-Code, kein Frontend. Der Go-Scheduler
> (`compare_alert_checks`, 15 min) bleibt einziger Taktgeber und ruft pro Nutzer getrennt.
>
> **Teilung Trip/Ortsvergleich:** Der Trip-Alarm ist seit S3 parallel, Radar seit S4, das Briefing seit S5. S6
> zieht den Ortsvergleich-Alarm mit demselben Baustein `fetch_ordered` nach. Es entsteht keine neue Komponente ohne
> Pendant.
>
> **Kanäle:** Alarme erreichen weiterhin alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS). Versand und
> Inhalt liegen nach der Detect-Phase und bleiben unverändert (PO-Vorgabe Kanalparität, ADR-0095).
>
> **Mandantentrennung:** `self._user_id` wird von den Workern nur gelesen und bleibt unverändert; nie `"default"`
> (Pflicht-AC mit zwei Nutzern).

## Estimated Scope

- **LoC:** ca. +90/-30 produktiv (2 Dateien), Tests ca. +300
- **Files:** 2 produktiv MODIFY (`compare_alert.py`, `compare_official_alert.py`), 1 Doku MODIFY
  (`docs/features/architecture.md`), 3 bis 5 Testdateien CREATE (`tests/tdd/test_compare_alert_parallel_*.py`,
  `tests/tdd/test_compare_official_alert_parallel_*.py`), 1 Bestandstest ANPASSEN (Naht, siehe unten), diese Spec
- **Effort:** medium
- **Risk Level:** MITTEL — Alarmpfad (ein Fehler wäre ein stiller Alarmverlust), aber mechanische Umstellung mit
  unveränderter Fehlersemantik

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/context/feat-1539-s6-compare-parallel.md` | Analyse | Verbindliche Analyse, Befunde, Technical Approach |
| `feat_1539_s1b_s2_abruf_baustein.md` | Spec (live) | Vertrag von `fetch_ordered` (Ergebnis in Eingabereihenfolge, `skipped`, Inline im Worker) |
| `feat_1539_s3_trip_alarm_parallel.md`, `feat_1539_s4_radar_parallel.md`, `feat_1539_s5_briefing_parallel.md` | Specs | Vorbild: Worker holt nur Daten, Auswertung im Hauptfaden, `skipped` zählt als gescheitert |
| ADR-0038 | ADR | Endliche Frist, sichtbarer Teilerfolg statt stilles Weglassen |
| ADR-0103 | ADR (bestehend) | Semaphorenzahlen; `open_meteo` 3 Slots, unbekannter Provider-Schlüssel bekommt 3 Slots (Env `GZ_PARALLEL_FETCH_SLOTS_<NAME>`); gilt unverändert, kein neues ADR |
| ADR-0021 | ADR | Quellenausfall ist nie Entwarnung (#1348, #1441) |

## Scope

**In Scope**

- Änderungs-Alarm: Frisch-Abruf je Ort über `fetch_ordered(provider="open_meteo")`, dreiphasiger Ablauf je Preset.
- Warn-Alarm: Warn-Abruf je Ort über `fetch_ordered(provider="official_alerts")`, dreiphasiger Ablauf je Preset.
- Endliche Frist für beide Pfade (Konstanten aus `trip_alert.py` wiederverwendet, kein neuer Wert).
- Dokuvermerk in `docs/features/architecture.md` (Abschnitt „Abruf-Baustein", wie bei S5).

**Out of Scope**

- Ortsvergleich-Briefing/Vorschau/Sofortvergleich (`comparison_parallel.py`, #1765, bereits parallel),
  `comparison_engine.py` (kein Alarmpfad).
- Compare-Radar-Alarm (in S4 erledigt), Go-Scheduler, S7 (Go-Nutzer-Fan-out).
- Änderungen an `parallel_fetch.py`, `official_alerts/*`, `warn_egress.py`, `CompareLocationWeatherSource`,
  `DeviationAlertEngine`, `AlertStateService`, an Versand, Kanal-Auflösung und Protokoll (`alert_log`).
- Atomarität in `openmeteo.py` (C4-63) und Thundering Herd nationaler Warndienste (C4-64): bleiben Nebenbefunde in
  #1539/#1199.
- Neue Anzeige, neue Texte, neue Metriken, Handlungsempfehlungen.

## Implementation Details

### Entschiedene Punkte der Analyse

1. **Frist (beide Pfade):** absolut `time.monotonic()`. Je Preset wird die Marke unmittelbar vor `fetch_ordered`
   gebildet: `time.monotonic() + FRESH_WEATHER_DEFAULT_DEADLINE_SECONDS` (60 s, Konstante aus
   `services.trip_alert` wiederverwendet, kein neuer Wert). Beide Compare-Dienste haben heute keine Lauf-Frist; sie
   erhalten ein optionales Attribut `_run_deadline_at` (Vorbild S3, Standard `None`), das `check_all_compare_presets`
   zu Laufbeginn auf `Laufbeginn + ALERT_RUN_DEADLINE_SECONDS` (180 s, ebenfalls aus `trip_alert`, ADR-0038: Grenze
   + Überhang unter dem Go-Wartebudget 300 s) setzt und am Laufende wieder auf `None`. Die wirksame Frist je Preset
   ist `min(Preset-Marke, _run_deadline_at)`, wenn eine Lauf-Frist gesetzt ist; sie überschreitet damit nie 180 s
   ab Laufbeginn. Ohne Lauf-Frist (Einzelaufruf, Test) gilt allein die 60-s-Marke.
2. **Provider-Schlüssel:** Änderungs-Alarm `open_meteo` (ADR-0103: 3 Slots, gemeinsame Semaphore mit allen anderen
   Wetterabrufen; die Gesamtparallelität bleibt gedeckelt). Warn-Alarm: **eigener Schlüssel `official_alerts`**
   (unbekannter Schlüssel ⇒ 3 Slots laut ADR-0103, kein neues ADR; Warn- und Wetterabruf blockieren einander nicht;
   dieselbe Wahl wie in S5).
3. **Parallelitätsnachweis:** Überlappung wird mit echter Barrier bzw. Zeitmessung am Provider-Rand bewiesen, nicht
   durch einen Mock der eigenen Annahme.
4. **Thread-Sicherheit der Wetterquelle (geprüft):** `CompareLocationWeatherSource.fetch` hält keinen geteilten
   Zustand. Es baut je Aufruf ein neues Segment und eine neue `SegmentWeatherService`-Instanz; `get_provider("openmeteo")`
   (`providers/base.py`) erzeugt über die Fabrik je Aufruf eine **neue Provider-Instanz** (die Registry wird
   einmalig doppelt gesperrt gefüllt, `_ensure_providers_loaded`). Gemeinsam ist nur, was bereits unter Last
   parallel benutzt wird: der Segment-Cache (Issue #1329, 10-Min-TTL) und das Abrufbudget (S4: atomares `reserve()`),
   beides auch vom parallelen Trip-Alarm (S3) genutzt. Der Abruf trägt `user_id` als Pflicht-Schlüsselwort
   (Issue #2387, kein Default); das Budget fällt in den Topf des Nutzers, dessen Vergleich geprüft wird.

### 1. Änderungs-Alarm (`compare_alert.py`)

`_evaluate_one_location` wird in zwei Teile getrennt; `_detect_triggered_locations` läuft dreiphasig je Preset:

**Phase 1 (seriell, Hauptfaden, Eingabereihenfolge):** je Ort in Reihenfolge von `location_ids`:
Ort auflösen (`all_locations.get`; nicht auflösbar ⇒ unverändert Warn-Log „nicht aufloesbar", weiter),
`self._snapshot_service.load(...)` (Dateizugriff), `_anchor_too_old` ⇒ `_protokolliere_fehlende_basis(..., "too_old", ...)`
und der Ort fällt aus, `missing` (kein Anker) ⇒ `_protokolliere_fehlende_basis(..., "missing")`, danach die
Abruf-Parameter bilden (`start_hour`/`end_hour` aus `day_window`, `elevation_m`, `user_id`, `target_date` nur wenn der
Anker einen Tagesbezug trägt, #1661). Der Teil heißt `_vorbereite_ort` und liefert den Ort als Abrufauftrag
(oder `None`, wenn er ausfällt). Die Schreibzugriffe der Protokolleinträge (`missing`/`too_old`) und deren
Entdopplung je Preset+Tag+Untergrund entstehen **ausschließlich hier und damit in Eingabereihenfolge**.

**Phase 2 (parallel):** `fetch_ordered(aufträge, worker, provider="open_meteo", deadline_at=...)`. Der Worker ruft
**nur** `self._weather_source.fetch(location_id, loc.lat, loc.lon, start_hour, end_hour, **zusatz)` und gibt den
`PointWeatherData` zurück. Er schreibt keinen geteilten Zustand (kein Protokoll, kein `alert_state`, keine Liste).

**Phase 3 (seriell, Hauptfaden, Eingabereihenfolge):** je Ergebnis `AlertStateService.load(entity_id)`,
`DeviationAlertEngine().evaluate(cached=..., fresh=[fresh_point], config=..., alert_state=...)` (Teil
`_bewerte_ort`), Aufbau des Treffer-Dicts unverändert, `triggered.append` in Eingabereihenfolge. Je Ort:

- OK ⇒ `log_enrichment_call(PATH_ALERT_FETCH, OUTCOME_OK, unit=f"{user_id}/{preset_id}/{location_id}")` (wie bisher).
- Fehler (`FetchOutcome.error`, auch Ausnahme in der Auswertung) oder `skipped` (Frist/Zeitüberschreitung) ⇒
  `logger.error("Compare-Alert check failed for …")` mit Grund (bei `skipped` der Wert `deadline`/`timeout`, ein
  Fristablauf ist nie still) und `log_enrichment_call(..., OUTCOME_UNAVAILABLE, unit=...)`; **die anderen Orte laufen
  weiter** (Teilausfall je Ort, wie bisher).

Der Versand, die Kanal-Gruppierung, Cooldown, Tageslimit, Backoff und Protokoll nach `_detect_triggered_locations`
bleiben unverändert. Die dünne Hülle `_evaluate_one_location` entfällt (alle Aufrufer sind `_detect_triggered_locations`);
der Bestandstest `tests/test_alert_stumme_ausfaelle.py` (`_compare_lauf`) überschreibt diese Naht und wird auf einen
Fehler am Wetterquellen-Rand umgestellt (gleiche Zusicherung: Ortsfehler wird je Ort gebucht, andere Orte laufen
weiter). Textverweise auf `_evaluate_one_location` in Kommentaren (z. B. `alert_preview_hours.py`) werden nachgezogen.

### 2. Warn-Alarm (`compare_official_alert.py`)

`_fetch_locations` läuft dreiphasig; die Signatur und der Rückgabewert `(raw, queries_by_loc)` bleiben unverändert,
`_detect` ist unberührt:

**Phase 1 (seriell, Hauptfaden):** je Ort in Reihenfolge `window_end = self._day_window_end(preset_id, loc, now)`
(liest die Presets, Dateizugriff — daher nicht im Worker). Ergebnis: geordnete Liste `(loc, window_end)`.

**Phase 2 (parallel):** `fetch_ordered(liste, worker, provider="official_alerts", deadline_at=...)`. Der Worker legt
**selbst** einen eigenen `sink` an, setzt `collect_source_queries(sink)` innerhalb der Aufgabe (die ContextVar
`_source_query_sink` ist je Aufgabe durch `copy_context()` isoliert, `collect_source_queries` setzt und löst den
Token im Worker) und ruft `list(get_official_alerts_for_location(loc.lat, loc.lon, window_start=now, window_end=window_end, now=now))`.
Rückgabe: `(alerts, sink)`. Der Worker schreibt weder `raw` noch `queries_by_loc`.

**Phase 3 (seriell, Hauptfaden, Eingabereihenfolge):** je Ergebnis `raw.extend((alert, [loc.id]) for alert in alerts)`
und `queries_by_loc[loc.id] = [AllClearQuery(scope=loc.id, scope_ids=(loc.id,), window_start=now, window_end=window_end,
sources=sink[-1].sources if sink else None, shown=tuple(alerts))]`. `_detect` ist dadurch inhaltlich und in der
Reihenfolge identisch zum seriellen Lauf.

**Fehlersemantik (Ist-Verhalten, geprüft und beibehalten):** In der heutigen seriellen Schleife steht kein
`try/except` um den Ortsabruf. Eine Ausnahme (z. B. aus `_day_window_end`, wenn die Presets nicht lesbar sind, oder
aus einer Quelle) geht aus `_fetch_locations` über `_detect` und `_check_one_preset` bis `_check_all_counted`; dort
wird sie je Preset gefangen (`report_unit_failure("Compare-Amtlich-Alarmlauf", preset_id)`, `failed += 1`), und das
Preset zählt über `last_failed_count` als gescheitert (Router `scheduler.py` → `failed`); die Folge-Presets laufen
weiter (#2217). Es entsteht dabei keine Teilmenge an Orten ohne Entwarnungs-Basis. Dieses Verhalten bleibt:

- Ausnahme eines Ortes (`FetchOutcome.error`) ⇒ nach Abschluss von Phase 2 wird sie im Hauptfaden **neu geworfen**
  (erste fehlgeschlagene Eingabeposition), das Preset gilt als gescheitert wie bisher.
- `skipped` (`deadline` oder `timeout`) ⇒ ebenso als Fehler des Presets mit sichtbarem Log-Grund
  (`logger.error` mit Ort und Grund, dann Ausnahme). **Nie** werden Orte ohne `queries_by_loc`-Eintrag an `_detect`
  weitergegeben: sonst wüsste `detect_official_allclear` nichts von der Quelle und ein Quellenausfall könnte als
  „Entwarnung möglich" missdeutet werden (ADR-0021, #1348, #1441).
- Der Warn-Aufruf selbst „wirft nie" (`get_official_alerts_for_location` ist fail-soft je Quelle); der Fehlerzweig
  betrifft daher vor allem `_day_window_end`, Frist und Zeitüberschreitung.

### 3. Unveränderte Garantien

- Reihenfolge von `triggered`, `raw`, `queries_by_loc` und der Positionsnummern (`_location_positions`) hängt an
  `location_ids` und bleibt erhalten.
- Ruhezeit, Tageslimit, Cooldown, `check_briefing_imminent` und `is_silenced` laufen weiter **vor** dem Abruf; ein
  stillgelegtes oder unterdrücktes Preset kostet keinen Abruf (#1467 AG2/AG6).
- Verschachtelung: ein `fetch_ordered`-Aufruf aus einem Worker läuft inline seriell (kein Deadlock).

### Wirkmaß

Wirkmaß ist `last_duration_s` je Lauf (`compare_alert_checks`, `compare_official_alert`) im Prod-Journal
(`compare_alert: Lauf beendet nach …s`) und `skipped_since_last_run` im Go-Takt. Typisch 2 bis 6 Orte je Preset; die
Obergrenze setzt der Slot (3). Echte Nebenläufigkeit ist auf Staging nicht messbar (`NOT_MEASURABLE_ON_STAGING`).

## Expected Behavior

- **Input:** Compare-Presets eines Nutzers mit mehreren Orten (unverändert).
- **Output:** `triggered`, `raw` und `queries_by_loc` **inhaltlich und in der Reihenfolge identisch** zum seriellen
  Lauf; Versand, Protokoll und Zählung (`last_failed_count`, `last_checked_count`) unverändert.
- **Side effects:** kürzere Laufzeit des Alarmlaufs bei mehreren Orten; keine zusätzlichen Upstream-Calls.

## Acceptance Criteria

- **AC-1:** Given ein Preset mit mehreren Orten, deren Frisch-Abrufe in umgekehrter Reihenfolge fertig werden / When
  der Änderungs-Alarm die Orte auswertet / Then steht `triggered` in der Reihenfolge von `location_ids`, jeder Treffer
  gehört zum richtigen Ort, und das Ergebnis ist identisch zum seriellen Lauf mit denselben Eingaben.
  - Test: `tests/tdd/test_compare_alert_parallel_aenderung.py`; absteigende Verzögerung am Wetterquellen-Rand,
    Ergebnis gegen den seriellen Lauf (Slots auf 1) verglichen.

- **AC-2:** Given ein Preset mit drei Orten, von denen einer keinen Anker hat (`missing`), einer einen zu alten Anker
  (`too_old`) und einer nicht auflösbar ist / When der Änderungs-Alarm läuft / Then entstehen die Protokolleinträge
  (`missing`, `too_old`) weiterhin im Hauptfaden in Eingabereihenfolge und je Preset+Tag+Untergrund höchstens einmal,
  der `too_old`-Ort und der nicht auflösbare Ort lösen keinen Abruf aus, und der nicht auflösbare Ort erzeugt wie
  bisher einen Warn-Log.
  - Test: `tests/tdd/test_compare_alert_parallel_aenderung.py`; Reihenfolge der Protokolleinträge und der Abrufe am
    Wetterquellen-Rand gegen den seriellen Lauf; schreibende Thread-Kennung erfasst und mit dem Hauptfaden verglichen.

- **AC-3:** Given Frisch-Abrufe mit künstlicher Verzögerung je Ort am Wetterquellen-Rand / When der Änderungs-Alarm
  ein Preset mit drei Orten prüft / Then überlappen sich die Abrufe nachweislich (Barrier, die nur freigibt, wenn
  mindestens zwei Abrufe zeitgleich laufen), und die Gesamtdauer liegt bei drei Orten mit je 0,5 s Verzögerung unter
  80 % der Summe der Einzelverzögerungen (unter 1,2 s bei 1,5 s Summe).
  - Test: `tests/tdd/test_compare_alert_parallel_aenderung.py`; Barrier und gemessene Dauer, keine Mock-Annahme im
    Prüfling.

- **AC-4:** Given in einem Preset scheitert der Frisch-Abruf eines Ortes mit Ausnahme / When der Änderungs-Alarm
  läuft / Then wird nur dieser Ort mit `logger.error` und `OUTCOME_UNAVAILABLE` gebucht, die übrigen Orte werden
  weiter ausgewertet und können Treffer liefern, und `OUTCOME_OK` wird nur für erfolgreiche Orte gebucht (Verhalten
  wie bisher; Bestandstest `test_alert_stumme_ausfaelle.py`, AC „Ortsfehler" bleibt grün).
  - Test: `tests/tdd/test_compare_alert_parallel_fehler.py`; Fehler gezielt je Ort am Wetterquellen-Rand,
    Logzeilen und Buchungen geprüft.

- **AC-5:** Given die Frist ist bereits abgelaufen bzw. läuft während der Abrufe ab (Konstanten über das Modul
  verkürzt, Slots auf 1 begrenzt) / When Änderungs-Alarm und Warn-Alarm ein Preset prüfen / Then wird mit einer
  endlichen Frist gearbeitet (60 s Standard je Preset, wirksame Frist höchstens `ALERT_RUN_DEADLINE_SECONDS` = 180 s
  ab Laufbeginn; dieselben Konstanten wie S3, kein neuer Wert), jeder nicht abgeschlossene Ort (`skipped`) steht mit
  Grund im Log, zählt beim Änderungs-Alarm als gescheiterter Ort (`OUTCOME_UNAVAILABLE`) und beim Warn-Alarm als
  gescheitertes Preset, und nichts wird still weggelassen.
  - Test: `tests/tdd/test_compare_alert_parallel_fehler.py` und `tests/tdd/test_compare_official_alert_parallel_fehler.py`;
    Frist im Test verkürzt, Ergebnis und Fehlerzeilen mit Grund geprüft; Nachweis, dass eine gesetzte Lauf-Frist die
    60-s-Marke nie verlängert.

- **AC-6:** Given Warn-Abrufe mit absteigender Verzögerung je Ort und je Ort eigener Quellen-Rückmeldung (sink) /
  When der Warn-Alarm die Orte lädt / Then enthält `raw` die Warnungen in Eingabereihenfolge der Orte, jede
  `AllClearQuery` in `queries_by_loc` gehört zum richtigen Ort und trägt dessen `sources` und `shown` (keine
  Vermischung der Senken zwischen Orten), und das Ergebnis ist identisch zum seriellen Lauf mit denselben Eingaben.
  - Test: `tests/tdd/test_compare_official_alert_parallel_ergebnis.py`; Verzögerung und unterschiedliche Quellen am
    Warn-Quellen-Rand, Vergleich gegen den seriellen Lauf (Slots auf 1).

- **AC-7:** Given Warn-Abrufe mit künstlicher Verzögerung je Ort / When der Warn-Alarm ein Preset mit drei Orten
  lädt / Then überlappen sich die Abrufe nachweislich (Barrier), die Gesamtdauer liegt unter 80 % der Summe der
  Einzelverzögerungen, die Abrufe laufen unter dem Provider-Schlüssel `official_alerts`, und ein durch gehaltene
  Abrufe vollständig belegter `open_meteo`-Slot blockiert den Warn-Abruf nicht.
  - Test: `tests/tdd/test_compare_official_alert_parallel_ergebnis.py`; Barrier, Zeitmessung und Startnachweis am
    Provider-Rand bei belegten `open_meteo`-Slots.

- **AC-8:** Given beim Warn-Alarm scheitert ein Ort (Ausnahme im Abruf bzw. beim Bilden des Tagesfensters) oder wird
  wegen Fristablauf verworfen / When das Preset geprüft wird / Then geht der Fehler wie bisher als Ausnahme aus
  `_fetch_locations` hoch, das Preset zählt in `last_failed_count` als gescheitert, die Folge-Presets laufen weiter,
  und es werden **nie** Orte ohne Entwarnungs-Basis (`queries_by_loc`-Eintrag) an `_detect` weitergegeben, sodass ein
  Quellenausfall nicht als Entwarnung gewertet wird.
  - Test: `tests/tdd/test_compare_official_alert_parallel_fehler.py`; Fehler und Fristablauf je Ort am
    Warn-Quellen-Rand, `last_failed_count`, keine Zustellung einer Entwarnung und unverändert gespeicherter Warn-Stand
    geprüft; Bestandstests zu #2217 und #1441 bleiben grün.

- **AC-9:** Given zwei verschiedene Nutzer mit je einem Compare-Preset auf Orten mit **gleichen Koordinaten** laufen
  gleichzeitig durch Änderungs-Alarm und Warn-Alarm / When die Worker laufen / Then trägt jeder Abruf die `user_id`
  seines Nutzers (am Wetterquellen-Rand erfasst, nie `"default"` oder `None`), Protokoll, Warn-Stand, Treffer,
  `raw` und `queries_by_loc` des einen Nutzers erscheinen nie im Ergebnis des anderen, und Single-flight/Cache
  vermischen keine Nutzerdaten.
  - Test: `tests/tdd/test_compare_alert_parallel_mandanten.py` mit zwei `user_id`; Thread-Fehler selbst eingesammelt.

- **AC-10:** Given ein paralleler Lauf beider Pfade mit gemischtem Erfolg und Fehler / When der Lauf endet / Then
  werden `triggered`, `raw`, `queries_by_loc`, Alarm-Zustand (`AlertStateService`), Protokolleinträge und
  `last_failed_count` ausschließlich vom Hauptfaden geschrieben (kein Schreibzugriff aus einem Worker-Thread, der
  Worker ruft nur `fetch` bzw. `get_official_alerts_for_location`) und stimmen nach vielen Wiederholungen mit dem
  seriellen Ergebnis überein.
  - Test: `tests/tdd/test_compare_alert_parallel_fehler.py` und `tests/tdd/test_compare_official_alert_parallel_fehler.py`;
    schreibende Thread-Kennung erfasst und mit dem Hauptfaden verglichen, Wiederholungslauf.

- **AC-11:** Given der Versand nach der Detect-Phase (E-Mail, Telegram, SMS, Premium-SMS) / When ein Preset mit
  Treffern bzw. Warnungen durchläuft / Then bleiben Kanal-Gruppierung, Schwellen, Backoff, Protokoll und
  Alarmtexte unverändert; Bestandstests der Compare-Alarmpfade (u. a. `test_compare_alert_*`,
  `test_compare_official_alert*`, Ruhezeit-/Tageslimit-/Briefing-imminent-Tests vor dem Abruf) bleiben ohne
  Änderung grün.
  - Test: bestehende Testdateien unverändert (mit Ausnahme der in „Implementation Details" genannten Naht in
    `test_alert_stumme_ausfaelle.py`).

## Testplan

Testdateien nach Verhalten benannt, Kern-Schicht (deterministisch, ohne Netz):
`tests/tdd/test_compare_alert_parallel_aenderung.py` (AC-1, AC-2, AC-3),
`tests/tdd/test_compare_alert_parallel_fehler.py` (AC-4, AC-5, AC-10),
`tests/tdd/test_compare_official_alert_parallel_ergebnis.py` (AC-6, AC-7),
`tests/tdd/test_compare_official_alert_parallel_fehler.py` (AC-5, AC-8, AC-10),
`tests/tdd/test_compare_alert_parallel_mandanten.py` (AC-9). Wetter- und Warndaten kommen als Fixtures am
Provider-Rand (Wetterquelle bzw. Warnquellen-Funktion); Zähler, Verzögerungen und Barrier sitzen am Rand, **nicht**
im Prüfling. Kein Mock-Theater, keine Dateiinhalt-Checks. Concurrency-Tests sammeln Thread-Ausnahmen selbst ein.
Der Prüfling wird relativ zur Testdatei aufgelöst (Worktree-sicher). `uv run pytest` immer mit benannten Dateien.

**Mutations-Gegenprobe (Pflicht für den Adversary; nur per String-Ersetzung mit externer Sicherungskopie, nie
`git checkout/stash/reset`; zu klären ist jeweils, **welcher** Test rot wird):**

1. Ergebnisse in Fertigstellungs- statt Eingabereihenfolge zusammenführen ⇒ AC-1 bzw. AC-6 rot.
2. `_protokolliere_fehlende_basis` oder `snapshot_service.load` in den Worker verlegen ⇒ AC-2 bzw. AC-10 rot.
3. `AlertStateService.load`/`evaluate` in den Worker verlegen ⇒ AC-10 rot.
4. Einen gemeinsamen statt je Aufgabe eigenen `sink` im Warn-Worker benutzen ⇒ AC-6 rot.
5. Fehler eines Warn-Ortes verschlucken und das Preset ohne diesen Ort weiterlaufen lassen ⇒ AC-8 rot.
6. `skipped` nicht als Fehler zählen oder nicht loggen ⇒ AC-5 bzw. AC-8 rot.
7. `deadline_at` auf unendlich setzen oder Lauf-Frist ignorieren ⇒ AC-5 rot.
8. Provider-Schlüssel der Warnungen auf `open_meteo` ⇒ AC-7 rot.
9. `user_id` im Worker auf `"default"` oder `None` ⇒ AC-9 rot.
10. Ortsfehler im Änderungs-Alarm bricht die übrigen Orte ab ⇒ AC-4 rot.

## Known Limitations

- **Begrenzter Hebel:** typisch 2 bis 6 Orte je Preset; Gesamtparallelität bleibt durch `open_meteo`-Slot 3 bzw.
  Warn-Slot 3 gedeckelt. Presets eines Nutzers laufen weiter nacheinander.
- **Laufende Threads sind nicht abbrechbar:** ein zu später Abruf wird verworfen (`skipped`), sein Thread hält den
  Slot bis zum Ende.
- **Nebenläufigkeit auf Staging nicht messbar** (`NOT_MEASURABLE_ON_STAGING`): Verhalten wird im Kern durch Tests
  bewiesen, die Wirkung erst durch Nachmessung im Prod-Journal.
- **Slotzahl ist ein Startwert** aus ADR-0103 (Prüfdatum 2027-01-26); der Schlüssel `official_alerts` nutzt den
  Standardwert 3.
- Mehrfachabfrage nationaler Warndienste je Koordinate (C4-64) bleibt Nebenbefund.

## Verbleibt in #1539

- **S7:** Go-Nutzer-Fan-out gemäß Gesamtplan. #1539 bleibt bis dahin offen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** ADR-0103 (Semaphorenzahlen, unbekannter Schlüssel ⇒ 3 Slots) gilt unverändert; dreiphasiger Ablauf,
  Aufteilung von `_evaluate_one_location` und Provider-Schlüssel `official_alerts` sind lokale Umsetzungsdetails.
  ADR-0038 (endliche Frist) und ADR-0021 (Quellenausfall nie Entwarnung) bleiben gültig.

## Changelog

- 2026-10-30: Initial spec created (Workflow feat-1539-s6-compare-parallel, S6)
