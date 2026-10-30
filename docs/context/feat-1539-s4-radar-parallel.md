# Context: feat-1539-s4-radar-parallel

## Request Summary
Vierter Workflow zu #1539 (Epic #2138): Die Radar-Abrufe über Zonenpunkte (Trip-Radar) und Orte (Compare-Radar) laufen
über den Baustein `parallel_fetch.fetch_ordered` (S2, S3 als Vorbild, ADR-0103). Dabei wird der Radar-Pfad vom
nicht-atomaren `allow()` + `record_call()` auf `reserve()` umgestellt. Gesamtplan: `docs/context/feat-1539-parallele-abrufe.md`
(Zeile 185, ca. 100 LoC). Radar-Jobs laufen im 5-Minuten-Takt (ADR-0082), Laufgrenze 45 s.
S5 (Briefing) und S6 (Compare-Alarm/Amtlich) folgen **nicht** in diesem Workflow.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_alert.py:2310-2335` | Trip-Radar: **serielle** Schleife `for _p in _punkte[1:]` über die weiteren Zonenpunkte. Der erste Punkt (`:2260`) trägt die Auslöseregel und bleibt eigener Abruf mit eigener Fehlersemantik. Fehler je Punkt ⇒ `None` (Lücke, kein Abbruch); `RadarDeadlineExceeded` ⇒ `_abort_radar_unit` + `break` |
| `src/services/compare_radar_alert.py:538-596` | Compare-Radar `_detect_triggered_locations`: serielle Ortsschleife; `RadarDeadlineExceeded` wird **hochgereicht** (Preset gilt als „nicht erreicht", keine Spur im Ausfall-Protokoll); `ausfaelle` werden erst nach der Schleife protokolliert |
| `src/services/radar_service.py:447-456` | `RadarDeadlineExceeded` + `_raise_if_deadline(deadline_at)`; geprüft vor jeder Quelle der Kette |
| `src/services/radar_service.py:522-560` | ⚠️ `get_nowcast` schreibt **Instanzzustand**: `_openmeteo_unavailable_this_call`, `_budget_throttled_this_call`, `_inca_unavailable_this_call`, `_priority`, `_budget_gate` (je Aufruf neu gesetzt, `:551-560`). Beide Aufrufer halten **eine** Dienst-Instanz (`_get_radar_service`, lazy). Parallele Aufrufe auf derselben Instanz überschreiben sich gegenseitig (Datenwettlauf) |
| `src/services/radar_service.py:1003-1023` | `_budget_gate.allow(self._priority)` + `record_call()` getrennt ⇒ nicht atomar; `ForecastBudgetGate.reserve()` existiert seit S1b (`forecast_budget.py:153`, fail-open, nie gedrosselt für `user_briefing`) |
| `src/services/radar_cache.py` | In-Memory, Lock, TTL 240 s (geteilter Cache `get_shared_radar_cache`) – thread-sicher, aber **kein Single-flight**: zwei parallele Aufrufe auf dieselbe Kachel holen doppelt |
| `src/services/parallel_fetch.py` | `fetch_ordered(items, fn, *, provider, deadline_at, max_parallel=None)`; Provider-Slots (`open_meteo`=3), `copy_context()` je Aufgabe, `skipped="deadline"/"timeout"`; `deadline_at` ist `time.monotonic()`-Marke wie bei Radar |
| `src/services/single_flight.py` | S1b: dedupliziert gleiche Abrufe über Aufrufer hinweg; Kandidat für den Radar-Cache-Miss |

## Existing Patterns
- S3 (`trip_alert._fetch_fresh_weather`): Zeitfilter und Aggregation im Hauptfaden, parallel nur der Netzabruf; Fehlerzählung aus `FetchOutcome`; `skipped` zählt als gescheitert und wird laut geloggt.
- Compare: `comparison_parallel.py` (Index-Ordnung, Teilausfall je Element).

## Dependencies
- Upstream: `parallel_fetch`, `single_flight`, `ForecastBudgetGate.reserve`, `radar_cache`, `weather_cache`.
- Downstream: Trip-Radar-Auswertung (`derive_rain_zones`, `_zonen_messwert`), Compare-Radar-Versand/Dedup (`_finalize_triggered_state`), Go-Scheduler (Radar-Takt 5 min, Wartebudget 240 s).

## Existing Specs / ADRs
ADR-0082 (Radar-Takt/Laufgrenze), ADR-0038 (harte Laufzeitgrenze), ADR-0021 (feste Gate-Reihenfolge, Quellenausfall ≠ Entwarnung), ADR-0103 (Semaphorenzahlen, Prüfdatum 2027-01-26),
`docs/specs/modules/feat_2261_a2s2_radar_takt.md`, `fix_2261_a2s1_alarmlauf_reihenfolge.md`, `feat_1539_s1b_s2_abruf_baustein.md`, `feat_1539_s3_trip_alarm_parallel.md`.
Tests (Bestand, bleiben grün): `tests/tdd/test_alert_run_deadline.py`, `test_radar_alarmlauf_*`, Radar-Zonen-Tests (#2051 S2a), Compare-Radar-Ausfall-Protokoll (#2050 S4a).

## Risks & Considerations
1. **Instanzzustand im `RadarNowcastService` (Hauptrisiko)**: Die `*_this_call`-Flags und `_budget_gate`/`_priority` sind pro Instanz. Parallel auf einer Instanz ⇒ ein Worker setzt das Flag zurück oder liest das des Nachbarn ⇒ falsche Drosselung bzw. falsches „Quelle nicht verfügbar" (das wäre ein **falsches Ausbleiben oder Auslösen eines Alarms**). Lösungsweg zur Entscheidung in der Spec: (a) je Worker eine eigene Dienst-Instanz (teilen den globalen Cache), oder (b) Zustand als Aufrufkontext (ContextVar/lokal) statt `self`. (a) ist klein und lokal; (b) ist sauberer, aber größer.
2. **`RadarDeadlineExceeded` aus dem Worker**: `fetch_ordered` fängt Fehler je Aufgabe. Die Ausnahme muss im Hauptfaden **neu geworfen** werden (Trip: `_abort_radar_unit` + Abbruch; Compare: Ausnahme hochreichen, keine Ausfall-Spur). Sie darf weder zu `None` (Lücke) noch zu einem Quellenausfall werden.
3. **Budget**: Umstellung `allow`+`record_call` auf `reserve()` im Radar-Pfad, sonst überbuchen parallele Aufrufer. Verhalten bei Ablehnung unverändert: `throttled`, kein Folgeabruf (`_openmeteo_unavailable_this_call`).
4. **Doppelabruf je Kachel**: Der Radar-Cache hat kein Single-flight. Zonenpunkte nahe beieinander teilen eine gerundete Kachel ⇒ parallel zwei Upstream-Calls. Single-flight um den Cache-Miss ist die Zusicherung „kein Mehrverbrauch".
5. **Reihenfolge/Semantik Trip**: Der erste Punkt bleibt seriell und trägt die Auslöseregel; nur `_punkte[1:]` parallel. Ergebnis in Eingabereihenfolge (`derive_rain_zones` hängt daran). Fehler je Punkt = `None`.
6. **Hebel**: Zonenpunkte je Trip typisch 2–5; Compare-Orte je Preset typisch 3–9. Gewinn real, aber begrenzt – Wirkmaß ist `duration_s` (S0) für Radar, nicht der Go-Überlaufzähler.
7. **Slots**: Radar nutzt Open-Meteo (`minutely_15`), plus DWD/Météo-France-Quellen der Kette. Provider-Schlüssel für `fetch_ordered`: `open_meteo` (Startwert 3) – Messung nur eingeschränkt möglich (`NOT_MEASURABLE_ON_STAGING` für echte Nebenläufigkeit).
8. **Multi-User**: `user_id` muss in jeden Worker; Test mit zwei Nutzern (Pflicht).
9. **Compare-Radar `finally`-Block** protokolliert Ausfälle nur bei nicht-Grenzabbruch – diese Semantik darf durch Sammeln im Hauptfaden nicht kippen.

## Open Questions (klärt `/30-write-spec`, technisch, keine PO-Frage)
- Lösungsweg zu Risiko 1: Instanz je Worker oder Zustand als Aufrufkontext?
- Single-flight im Radar-Cache jetzt (Risiko 4) oder bewusst später? Empfehlung: jetzt, sonst steigt der Tagesverbrauch.

## Analysis

### Type
Feature (Teil von #1539, Scheibe S4)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_alert.py` (`_check_radar_trips`, Zonenschleife) | MODIFY | `_punkte[1:]` über `fetch_ordered`; Deadline im Hauptfaden neu werfen |
| `src/services/compare_radar_alert.py` (`_detect_triggered_locations`) | MODIFY | Ortsabrufe parallel; Auswertung/Ausfallsammlung im Hauptfaden; Deadline durchreichen |
| `src/services/radar_service.py` | MODIFY | Zustand pro Aufruf statt pro Instanz (oder Instanz je Worker); `reserve()` statt `allow`+`record_call`; Single-flight um Cache-Miss |
| `docs/specs/modules/feat_1539_s4_radar_parallel.md` | CREATE | Spec mit ACs (Deutsch, zur Freigabe) |
| `tests/tdd/test_radar_parallel_fetch.py` (o. ä.) | CREATE | Reihenfolge, Teilausfall, Deadline-Neuwurf, kein Zustandsübersprechen, `reserve`, 2 Nutzer |

### Scope Assessment
- Files: 3 Produktiv + Spec + 1–2 Testdateien
- Estimated LoC: +110/-30 produktiv (leicht über der 100 der Grobschätzung wegen Zustandsentkopplung), Tests ca. +250
- Risk Level: MEDIUM-HIGH (Alarmpfad, Datenwettlauf im Dienst; falsche Auslösung/Unterdrückung möglich, auf Staging nicht messbar)
