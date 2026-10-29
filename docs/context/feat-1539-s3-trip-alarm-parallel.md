# Context: feat-1539-s3-trip-alarm-parallel

## Request Summary
Dritter Workflow zu #1539 (Epic #2138): Den Etappen-Abruf des **Trip-Alarms** erstmals über den Baustein
`parallel_fetch.fetch_ordered` (S2, live 2026-10-08, PR #2544) laufen lassen. Dabei die Provider-Semaphorenzahlen
**messen** und als ADR festhalten. Gesamtplan und Vorher-Messung: `docs/context/feat-1539-parallele-abrufe.md`;
Baustein-Kontext: `docs/context/feat-1539-s1b-s2-abruf-baustein.md`. S4 (Radar), S5 (Briefing), S6 (Compare) folgen
**nicht** in diesem Workflow.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py:2954-3020` | `_fetch_fresh_weather`: **die** Umbaustelle. Serielle `for cached in cached_weather`-Schleife; Zeitfilter (`end_time < now` / `start_time.date() > today`) ⇒ `continue`; je Etappe `service.fetch_segment_weather(..., enrich_ensemble=False, enrich_snow=False, priority="alert_check", user_id=...)`; Fehler je Etappe gefangen (`gescheitert += 1`); setzt `self._fetch_stats = (versucht, gescheitert)`; S0-Dauerzeile „Etappe X: Abruf in N s" |
| `src/services/trip_alert.py:742-757` | Einziger Produktiv-Aufrufer in `check_and_send_alerts`; wertet `_fetch_stats` für `enrichment_health` (#2218) aus — Semantik „leer ohne Versuch = Normalfall" muss bleiben |
| `src/services/trip_alert.py:1096-1300` | `check_all_trips`: Trips **seriell** (Rotation #2261 A-2 S1, `skipped_ids`, State-Write). `deadline_at = run_started_at + ALERT_RUN_DEADLINE_SECONDS (180 s)` ist **lokal** und erreicht `_fetch_fresh_weather` heute nicht ⇒ Frist muss durchgereicht werden |
| `src/services/parallel_fetch.py` | Baustein: `fetch_ordered(items, fn, *, provider, deadline_at, max_parallel=None) -> list[FetchOutcome]`; Executor 8 (`GZ_PARALLEL_FETCH_WORKERS`), Slots je Provider (`open_meteo`=3, `meteoalarm`=1, `meteo_france`=4; Env `GZ_PARALLEL_FETCH_SLOTS_<PROVIDER>`); `copy_context()` je Aufgabe; Aufruf aus einem Worker läuft inline seriell; `skipped="deadline"` / `"timeout"` |
| `src/providers/call_log.py:41-104` | ⚠️ `resolve_call_source()` erkennt „alarm" am **Funktionsnamen `_fetch_fresh_weather` im Aufruf-Stapel** des ausführenden Threads. Im Worker fehlt dieser Frame ⇒ Journal bucht „unbekannt" (#1765 B1, belegt 7,4 %). Gegenmittel: `override_call_source(...)` (ContextVar, reist per `copy_context` in den Worker) |
| `src/services/alert_preview_hours.py:42-80` | Zweiter Aufrufer: `trip_preview_series` ruft `svc._fetch_fresh_weather` über `_within(deadline, …)` in einem Hilfsfaden. Dort steht oben im Stapel `render_sms_preview` ⇒ Quelle „vorschau" (höhere Marker-Priorität als „alarm"). Eine feste Überschreibung auf „alarm" würde Vorschau-Last falsch einordnen |
| `src/services/segment_weather.py` (S1b/S2) | `fetch_segment_weather` mit Single-flight + atomarem `reserve()`; bereits thread-sicher für parallele Aufrufer. Rückgabe je Etappe aggregiert beim Aufrufer |
| `src/services/comparison_parallel.py` | Vorbild für Teilausfall je Element und Index-Ordnung (Compare, eigener Executor, `MAX_PARALLEL_LOCATIONS=4`) |
| `src/providers/openmeteo.py:68,80,116-122` | Retry 5× exp. 2–60 s, `{502,503,504}`, `FETCH_DEADLINE_SECONDS=60`; Retries laufen **unter** dem Semaphore-Slot (Baustein-Zusicherung) |

## Existing Patterns
- Ergebnisverarbeitung nach `fetch_ordered`: `FetchOutcome.error` ⇒ wie bisher `gescheitert += 1` + `logger.error`; `skipped` ⇒ ebenfalls gezählt und **laut** geloggt (ADR-0038: kein stilles Weglassen).
- ContextVar-Weitergabe: `override_call_source` vor dem Aufruf in dem Thread setzen, der den Stack noch hat (`resolve_call_source()` dort auflösen, dann überschreiben ⇒ „vorschau" bleibt „vorschau", Alarm bleibt „alarm").
- Zeitfilter und Aggregation bleiben seriell im Hauptfaden; parallel läuft **nur** der Netzabruf je Etappe.

## Dependencies
- Upstream: `parallel_fetch`, `segment_weather` (Single-flight, `reserve`), `weather_cache`, `forecast_budget`, `call_log`.
- Downstream: `check_and_send_alerts` (Δ-Auswertung, Versand, `_fetch_stats`/`enrichment_health`), `alert_preview_hours.trip_preview_series` (Vorschau-API), Go-Scheduler (Wartebudget 300 s, ADR-0038-Invariante `180 + 64 ≤ 300`).

## Existing Specs / ADRs
- `docs/specs/modules/feat_1539_s1b_s2_abruf_baustein.md` — Baustein-Vertrag, Semaphore-Erwerb mit Frist (Pflicht-AC).
- `docs/specs/modules/fix_1329_forecast_cache_budget.md` — gleiche Koordinate/Stunde ⇒ 1 Upstream-Call; `user_briefing` nie gedrosselt.
- ADR-0038 (harte Laufzeitgrenze je Lauf), ADR-0021 (feste Gate-Reihenfolge), Epic #2261 A-2 S1 (Rotation). Nächste freie ADR-Nummer: **0103** (höchste vorhanden: 0102).
- Neues ADR für die gemessenen Semaphorenzahlen nötig (Prüfdatum +90 Tage, Regel-Budget).

## Tests (Bestand, die `_fetch_fresh_weather` berühren und grün bleiben müssen)
`tests/tdd/test_bundle_791_847_844_alerts.py` (AC-3 Zeitfilter, echter Call), `test_bug_338_openmeteo_call_counter.py`
(source == „alarm"), `test_briefing_anchor_survives_dispatch_failure.py` (AC-9 Zeitfilter),
`test_ruhezeit_und_zaehler_folgen_der_ortszone.py` (ersetzt `_fetch_fresh_weather` als Netz-Naht),
`tests/tdd/test_trip_alert_duration_logging.py` (S0: genau eine „Etappe X: Abruf in N s"-Zeile je Etappe).
Concurrency-Vorbilder: `tests/unit/test_parallel_fetch_*.py`, `test_call_source_ueber_threadgrenze.py`.
Pytest-Hinweis: Thread-Ausnahmen sind nur Warnungen (C4-62) ⇒ neue Tests sammeln Fehler selbst ein.

## Risks & Considerations
1. **call_source „unbekannt"**: stackbasierte Erkennung bricht im Worker. Pflicht-AC: Journal bucht für Alarm-Abrufe weiter „alarm", für Vorschau-Abrufe weiter „vorschau".
2. **Deadline nicht durchgereicht**: `_fetch_fresh_weather` kennt `deadline_at` nicht. Ohne Frist wäre `fetch_ordered` unbegrenzt ⇒ Verstoß gegen ADR-0038. Frist = Restzeit des Laufs (180 s ab Lauf-Start) bzw. bei Vorschau/anderen Aufrufern ein endlicher Standard; Weg der Durchreichung ist Analyse-Entscheidung.
3. **`skipped`/`timeout` vs. `_fetch_stats`**: übersprungene Etappen müssen als **gescheitert** zählen (sonst meldet `enrichment_health` fälschlich „ok", und ein Alarm würde aus unvollständiger Reihe berechnet). Unvollständige Reihe ⇒ Δ-Auswertung auf Teilmenge: Verhalten heute bei Einzelfehler ist „Etappe fehlt in `fresh_weather`" — gleiche Semantik beibehalten.
4. **Geteilter Zustand im Worker**: `self._fetch_stats` und `fresh_weather.append` dürfen nicht aus Workern geschrieben werden ⇒ Ergebnisse im Hauptfaden einsammeln.
5. **Open-Meteo-Last**: Tageszahl der Calls darf nicht steigen (Single-flight, `reserve`); 503-Retries laufen unter dem Slot. Semaphorenzahl 3 ist bisher Annahme — Messung steht aus.
6. **Wenig Hebel bei wenigen Etappen**: Der Zeitfilter lässt nur **heutige, nicht beendete** Etappen durch (typisch 1–6). Der Nutzen hängt an der Etappenzahl je Trip; Vorher-Messung (p95 37 s je Lauf, Abbrüche an der 180-s-Grenze) aus dem Gesamtkontext gilt.
7. **Vorschau-Pfad** (`_within`-Hilfsfaden) ruft dieselbe Methode: darf nicht regressieren (Frist 2-fach: `_within` + `fetch_ordered`).
8. **Multi-User**: `user_id` muss unverändert in jeden Worker-Aufruf; Test mit zwei Nutzern (Pflicht laut CLAUDE.md).
9. **Messbarkeit auf Staging begrenzt**: echte Nebenläufigkeit ist `NOT_MEASURABLE_ON_STAGING` (S2-Erfahrung). Prod-Journal ist für `hem` nicht lesbar (`journalctl -u gregor-python` liefert 0 Zeilen); Messung der Semaphorenzahlen braucht `sudo -n -u claude-gregor`-Zugriff oder eine Messroutine im Code (Entscheidung in `/20-analyse`).

## Open Questions (technisch, klärt `/20-analyse`)
- Wie reist `deadline_at` in `_fetch_fresh_weather` (Parameter vs. Instanzfeld) ohne Signaturbruch für `alert_preview_hours` (`fetch or svc._fetch_fresh_weather`) und die Tests, die die Methode ersetzen?
- Messmethode und -quelle für die Semaphorenzahl (Open-Meteo 503-/429-Quote bei 1/2/3/4 Slots), die ADR-fähig ist.
- Wie viele Etappen hat ein Trip im Alarm-Fenster in der Praxis (Obergrenze für `max_parallel`)?

## Analysis

### Type
Feature (Teil von Bug-artigem Skalierungsproblem #1539, Scheibe S3)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_alert.py` (`_fetch_fresh_weather`, `check_all_trips`) | MODIFY | Netzabruf je Etappe über `fetch_ordered(provider="open_meteo")`; Zeitfilter + Sammeln im Hauptfaden; Frist aus Instanzfeld |
| `docs/adr/0103-*.md` + `docs/adr/README.md` | CREATE/MODIFY | Semaphorenzahlen (Open-Meteo), Messmethode, Prüfdatum +90 Tage |
| `docs/specs/modules/feat_1539_s3_trip_alarm_parallel.md` | CREATE | Spec mit ACs |
| `tests/tdd/test_trip_alert_parallel_fetch.py` (o. ä., nach Verhalten benannt) | CREATE | Reihenfolge, Teilausfall, call_source, Frist, 2 Nutzer |
| `src/services/alert_preview_hours.py` | unverändert | Vorschau ruft weiter `_fetch_fresh_weather(anchor)` – Signatur bleibt |

### Scope Assessment
- Files: ca. 2 Produktiv + 1 ADR + 1 Spec + 1–2 Testdateien
- Estimated LoC: +70/-25 produktiv, Tests ca. +200
- Risk Level: MEDIUM (zentraler Alarm-Pfad, echte Nebenläufigkeit; auf Staging nicht messbar)

### Technical Approach (Entscheidungen zu den offenen Fragen)
1. **Frist ohne Signaturbruch:** Instanzfeld `self._run_deadline_at` (absoluter `monotonic`-Wert), in `check_all_trips` neben `deadline_at` gesetzt und nach dem Lauf zurückgesetzt. `_fetch_fresh_weather(cached_weather)` bleibt unverändert aufrufbar (Vorschau, Tests, die die Methode ersetzen). Ohne Feld (Vorschau/Einzelaufruf): endlicher Standard (`monotonic() + 60 s`, an `FETCH_DEADLINE_SECONDS` angelehnt) – nie unbegrenzt (ADR-0038).
2. **call_source:** im Aufrufer-Thread `resolve_call_source()` auflösen (liefert „alarm" bzw. „vorschau"), im Worker per `override_call_source(...)` setzen. So bleibt Vorschau „vorschau", Alarm „alarm".
3. **Struktur:** Zeitfilter seriell im Hauptfaden → Liste „fällige Etappen" → `fetch_ordered` → Auswertung seriell: `error`/`skipped` ⇒ `gescheitert += 1` + ERROR-Log; `fresh_weather` in Eingabereihenfolge; `_fetch_stats` nur im Hauptfaden. Semantik „Etappe fehlt in `fresh_weather`" wie heute bei Einzelfehler. S0-Dauerzeile je Etappe bleibt (im Worker gemessen, im Hauptfaden geloggt, damit genau eine Zeile je Etappe).
4. **`max_parallel`:** keine feste Obergrenze nötig – fällige Etappen im Alarm-Fenster typisch 1–6, Slot-Grenze (Open-Meteo 3) begrenzt ohnehin.
5. **Messung der Semaphorenzahl:** Prod-Journal ist per `sudo -n -u claude-gregor journalctl` erreichbar (in dieser Worktree-Sitzung blockt der Wächter den `sudo`-Aufruf mit Zeitraum-Argument; Messung deshalb als eigener Schritt in `/50` bzw. per PO-Terminal). Messgröße: Anteil 503/429 und Etappen-Abrufdauer (p50/p95) vor vs. nach Umstellung, bei Slots 3 (Default). Ergebnis + Startwert werden im ADR festgehalten; Slotzahl bleibt per Env `GZ_PARALLEL_FETCH_SLOTS_OPEN_METEO` nachstellbar. Vor-Messung steht bereits fest: p95 Lauf 37 s, max 215 s, Abbrüche an 180-s-Grenze.
6. **Nicht Teil:** Trip-Schleife bleibt seriell (Rotation #2261), Radar/Briefing/Compare = S4–S6.

### Dependencies
`parallel_fetch`, `segment_weather` (Single-flight, `reserve`), `call_log.override_call_source`, `enrichment_health` (#2218), Go-Scheduler-Wartebudget (180+64≤300).

### Open Questions
- [ ] Keine für den PO. Technisch offen nur: ADR-Messwerte (Nachmessung nach Deploy, Prüfdatum +90 Tage).

### Pflicht-ACs für die Spec (Ableitung aus Risiken)
Reihenfolge erhalten · Teilausfall isoliert (`gescheitert` zählt, Rest läuft) · `skipped` zählt als gescheitert · call_source „alarm"/„vorschau" im Worker · Frist durchgereicht, kein unbegrenztes Warten · `_fetch_stats` nur aus Hauptfaden · zwei Nutzer, `user_id` je Worker · Tagesanzahl Open-Meteo-Calls steigt nicht · Zeitfilter/Alt-Tests grün.
