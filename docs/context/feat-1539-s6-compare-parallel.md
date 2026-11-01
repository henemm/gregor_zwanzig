# Context: feat-1539-s6-compare-parallel

## Request Summary
Issue #1539, Scheibe S6: Die beiden Ortsvergleich-Alarmpfade (Aenderungs-Alarm `compare_alert`, amtliche Warnungen `compare_official_alert`) rufen die Daten je Ort noch nacheinander ab. Sie sollen den Baustein `parallel_fetch.fetch_ordered` nutzen (Vorbilder S3 Trip-Alarm, S4 Radar, S5 Briefing). #1539 bleibt offen (PR-Text "Refs #1539").

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/compare_alert.py:576` `_detect_triggered_locations` | serielle `for location_id in location_ids`-Schleife, je Ort `_evaluate_one_location` (Fehler je Ort gefangen, `log_enrichment_call`) |
| `src/services/compare_alert.py:611-661` `_evaluate_one_location` | Anker laden, Frisch-Abruf `self._weather_source.fetch(...)` (Zeile 651, Netz), danach `DeviationAlertEngine.evaluate` und `AlertStateService.load`. Abruf ist der Latenzblock; Snapshot-/State-Zugriffe sind Dateizugriffe je Ort |
| `src/services/compare_official_alert.py:416` `_detect`, `:~480` `_fetch_locations` | serielle `for loc in locs`-Schleife um `get_official_alerts_for_location(...)` in `collect_source_queries(sink)`; Ergebnis `raw` (Alarm, [loc.id]) und `queries_by_loc` |
| `src/services/parallel_fetch.py` | Baustein `fetch_ordered(items, fn, provider=, deadline_at=)`: Eingabereihenfolge, `skipped` ("deadline"/"timeout"), Slots je Provider, `copy_context()` je Aufgabe, Aufruf aus Worker laeuft inline |
| `src/services/single_flight.py`, `warn_egress.cached_fetch` | geteilte Abrufe fuer Warn-Feeds (S1b), schuetzen vor Mehrfachabruf derselben Kachel |
| `src/services/radar_service.py:466-520` | S4-Muster `hole_nowcasts`/`nowcast_abrufer`: Worker schreibt keinen geteilten Zustand, Auswertung im Hauptfaden |
| `src/services/comparison_parallel.py` | #1765: `run_comparison_parallel` mit eigenem `ThreadPoolExecutor` (max 4). Wird von Vorschau, Sofortvergleich und Versand (`scheduler_dispatch_service.py:611`) genutzt -- das Compare-Briefing ist also schon parallel. Nicht Teil von S6 |
| `src/services/comparison_engine.py:142` | serielle Schleife in `ComparisonEngine.run`; wird nur noch ueber `comparison_parallel` mit je einem Ort aufgerufen, kein Alarm-Pfad |
| `src/services/compare_location_weather_source.py` | Standard-Wetterquelle des Aenderungs-Alarms (Netz) |
| `internal/scheduler/scheduler.go:354,866` | Go-Takt `compare_alert_checks` (15 min) und `compare_radar_alert_checks` (5 min); `skipped_since_last_run` ist der Wirkungsnachweis |
| `docs/adr/0103-parallele-abrufe-semaphorenzahlen.md` | Slotzahlen je Provider (open_meteo 3, meteo_france 4, unbekannt 3) |
| `docs/specs/modules/feat_1539_s3..s5_*.md`, `docs/context/feat-1539-s5-briefing-parallel.md` | Vorlagen fuer Spec und Testzuschnitt |

## Bereits erledigt (nicht Teil von S6)
- Compare-Radar-Alarm: in S4 (`hole_nowcasts` fuer Ortsvergleich-Orte).
- Compare-Briefing/Vorschau/Sofortvergleich: #1765 B1/B1b (`run_comparison_parallel`).
- Auslaufbaustein, Single-flight, atomares `reserve()`: S1b/S2.

## Offen in S6 (Befund)
1. `compare_alert._detect_triggered_locations`: Netzabruf je Ort seriell.
2. `compare_official_alert._fetch_locations`: Warn-Abruf je Ort seriell. Ergebnis wird erst danach dedupliziert und gegen den State je Ort bewertet (Hauptfaden).

## Existing Patterns
- Worker macht nur den Abruf, Auswertung/State-Schreiben/Versand im Hauptfaden in Eingabereihenfolge (S3/S4/S5).
- Teilausfall je Ort isoliert (Outcome.error), `skipped` zaehlt als gescheitert und wird sichtbar protokolliert (ADR-0038).
- Frist als absoluter `time.monotonic()`-Wert; kein stilles Weglassen.
- Mandantentrennung: `user_id` aus dem Aufrufer-Objekt (`self._user_id`), nie "default"; Test mit zwei Nutzern.

## Dependencies
- Upstream: `fetch_ordered`, `CompareLocationWeatherSource`, `get_official_alerts_for_location`, `collect_source_queries`, `AlertStateService`, `CompareWeatherSnapshotService`, `ForecastBudgetGate.reserve`.
- Downstream: `/api/scheduler/compare-alert-checks`, Scheduler-Dispatch; Mail-/SMS-/Telegram-Alarmversand (unveraendert, nach der Detect-Phase).

## Existing Specs
`feat_1539_s3_trip_alarm_parallel.md`, `feat_1539_s4_radar_parallel.md`, `feat_1539_s5_briefing_parallel.md`, `fix_1765_b1b_versand_sofortvergleich_parallel.md`, ADR-0103.

## Risks & Considerations
- **Kontextvariablen/Senken:** `collect_source_queries(sink)` ist vermutlich Context-gebunden; je Aufgabe eigenen Sink im Worker anlegen und im Hauptfaden zusammenfuehren (sonst Vermischung der Orte oder Verlust der Entwarnungs-Basis).
- **Geteilter Zustand im Worker:** `_evaluate_one_location` ruft `_protokolliere_fehlende_basis` (schreibt Protokoll) und laedt/schreibt State -- nur der Abruf (Zeile 651) darf in den Worker, alles andere bleibt im Hauptfaden (Reihenfolge der Protokolleintraege).
- **Reihenfolge:** `triggered`, `raw` und Positionsnummern (`_location_positions`) haengen an der Eingabereihenfolge; `fetch_ordered` garantiert sie.
- **Provider-Schluessel:** Ortsvergleich-Orte koennen europaweit liegen; Wetterquelle meist `open_meteo`, Warn-Feeds laufen ueber `warn_egress` mit eigenem Single-flight. Slot-Wahl in der Analyse klaeren (ADR-0103 gilt, kein neues ADR erwartet).
- **Zwei Nutzer:** Scheduler ruft je Nutzer getrennt; Test mit zwei Nutzern auf gleichen Koordinaten (Single-flight darf keine Nutzerdaten vermischen).
- **Frist:** Alarmlauf braucht endliche Frist; bei Ablauf kein stilles Weglassen (Teilerfolg sichtbar, Ort zaehlt als fehlgeschlagen).

## Analysis

### Type
Feature (Performance/Skalierung, Scheibe S6 von #1539; kein Verhaltenswechsel fuer Nutzer).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/compare_alert.py` | MODIFY | `_evaluate_one_location` in zwei Teile trennen: `_vorbereite_ort` (Anker laden, `too_old`/`missing`-Protokoll, Abruf-Parameter; Hauptfaden, seriell) und `_bewerte_ort` (State laden, `DeviationAlertEngine.evaluate`; Hauptfaden). Dazwischen NUR `self._weather_source.fetch(...)` ueber `fetch_ordered(provider="open_meteo")` |
| `src/services/compare_official_alert.py` | MODIFY | `_fetch_locations`: Worker = `collect_source_queries(eigener sink)` + `get_official_alerts_for_location` je Ort; Hauptfaden fuegt `raw`/`queries_by_loc` in Eingabereihenfolge zusammen |
| `tests/…/test_compare_alert_parallel*.py`, `…official_alert_parallel*.py` | CREATE | Verhaltenstests, nach Muster S3-S5 (Reihenfolge, Teilausfall, Frist, zwei Nutzer) |
| `docs/specs/modules/feat_1539_s6_compare_parallel.md` | CREATE | Spec mit ACs |
| `docs/features/architecture.md` | MODIFY | Vermerk wie bei S5 |

### Scope Assessment
- Files: 2 Quell + 2 Test + Spec/Doku
- Estimated LoC: +90/-30 Quellcode
- Risk Level: MEDIUM (Alarmpfad; Fehler waeren stille Alarmverluste)

### Technical Approach
1. **Compare-Aenderungs-Alarm:** Drei Phasen je Preset. (a) seriell im Hauptfaden: je Ort Anker/Protokoll (`_protokolliere_fehlende_basis` bleibt in Eingabereihenfolge, kein geteilter Zustand im Worker), nicht aufloesbare/zu alte Orte fallen hier raus; (b) parallel: nur der Frisch-Abruf (`fetch`), Worker haelt keinen Zustand; (c) seriell: State laden + `evaluate`, `triggered` in Eingabereihenfolge. Fehler je Ort: `Outcome.error` oder `skipped` -> wie bisher `log_enrichment_call(..., OUTCOME_UNAVAILABLE)` + `logger.error`, kein Abbruch der anderen Orte.
2. **Compare-Warnungen:** Worker je Ort mit eigenem `sink` (ContextVar wird durch `copy_context()` je Aufgabe isoliert, `collect_source_queries` setzt/loest den Token im Worker). Rueckgabe `(alerts, sink)`; Hauptfaden baut `AllClearQuery`. Fehler/`skipped` eines Ortes: bisher bricht die serielle Schleife komplett ab (Exception geht hoch) -> **zu pruefen/festlegen in Spec**: Verhalten beibehalten (Fehler hochreichen, Preset gilt als gescheitert, `last_failed_count`) statt still Orte ohne Entwarnungs-Basis zu liefern, weil fehlende `queries` sonst als „Entwarnung moeglich" missdeutet werden koennte.
3. **Provider/Slots:** Aenderungs-Alarm `open_meteo` (3 Slots, ADR-0103). Warn-Feeds: `get_official_alerts_for_location` laeuft ueber Single-flight/`warn_egress`, eigene Kachel-Absicherung; Slot `open_meteo`-neutral waehlen -> Provider-Schluessel „unbekannt" (3) oder eigener Name; kein neues ADR noetig.
4. **Frist:** absolut `time.monotonic()`. Ohne Lauf-Frist Default 60 s je Preset (wie `FRESH_WEATHER_DEFAULT_DEADLINE_SECONDS`, S3); Lauf-Frist darf hoechstens `ALERT_RUN_DEADLINE_SECONDS` (180 s) nicht ueberschreiten (Go-Wartebudget 300 s, ADR-0038). `skipped` zaehlt als gescheitert und ist im Log sichtbar.
5. **Nicht anfassen:** `comparison_parallel`, `comparison_engine`, Radar-Alarm (schon erledigt).

### Dependencies
`parallel_fetch.fetch_ordered`, `CompareLocationWeatherSource`, `get_official_alerts_for_location`, `collect_source_queries` (ContextVar in `official_alerts/base.py:140`), `AlertStateService`, `CompareWeatherSnapshotService`; nachgelagert unveraendert: Router `/api/scheduler/compare-alert-checks`, Alarmversand.

### Findings gegen den Plan
Keine tragenden. Beachten: (1) Wetterquelle muss thread-sicher sein (Standardquelle vor Spec pruefen: gemeinsame Clients/Caches); (2) `_snapshot_service.load` ist Dateizugriff -> bewusst im Hauptfaden gelassen.

### Open Questions
- [ ] Warn-Abruf: Ortsfehler hochreichen (Ist-Verhalten) oder je Ort isolieren? Empfehlung: Ist-Verhalten beibehalten, Spec legt es als AC fest.
- [ ] Thread-Sicherheit von `CompareLocationWeatherSource.fetch` in Spec/Test belegen (zwei gleichzeitige Orte, gleiche Koordinaten, zwei Nutzer).
