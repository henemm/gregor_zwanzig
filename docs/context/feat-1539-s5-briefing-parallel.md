# Context: feat-1539-s5-briefing-parallel

## Request Summary
Issue #1539 (Epic #2138), Scheibe S5: Im Trip-Briefing laufen noch drei Abrufblöcke nacheinander, obwohl der
Segment-Abruf des Zieltags schon parallel ist (#2439). S5 lässt sie über den Baustein `parallel_fetch.fetch_ordered`
nebeneinander laufen (Vorbild S3 Trip-Alarm, S4 Radar). #1539 bleibt danach offen (PR-Text „Refs #1539").

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:1733-1760` | Amtliche Warnungen: Schleife über eindeutige Startkoordinaten, je ein `get_official_alerts_with_status` mit `collect_source_queries(_sink)` (seriell) |
| `src/services/trip_report_scheduler.py:2973-3011` (`_build_stage_trend`) | Ausblick-Trend: bis zu 3 Folge-Etappen, je `_convert_trip_to_segments` + `_fetch_weather` + `_enrich_ensemble_for_trip` (seriell, größter Latenzblock) |
| `src/services/trip_report_scheduler.py:3403-3470` (`_collect_future_stage_weather`) | Gewitter-Fallback: bis zu 2 Etappen, gleiches Muster |
| `src/services/trip_report_scheduler.py:2667-2720` (`_fetch_weather`) | Bereits parallel (`fetch_ordered`, `open_meteo`, `FETCH_WEATHER_DEADLINE_SECONDS`); Referenz für Fehlerplatzhalter |
| `src/services/trip_report_scheduler.py:2537` (`_convert_trip_to_segments`) | **Schreibt `self._last_converted_trip`** (Instanzzustand) und kann GPX-Distanzen nachtragen (`backfill_stage_distances`) |
| `src/services/parallel_fetch.py` | Baustein: Executor, Semaphore je Provider (`open_meteo` 3, sonst 3), `copy_context()` je Aufgabe, Aufruf aus Worker läuft INLINE seriell |
| `src/services/official_alerts/base.py:134-148` | `_source_query_sink` ist eine `ContextVar`; `collect_source_queries` setzt/zurücksetzt sie |
| `src/services/trip_alert.py:3003-3040` | S3-Vorbild: `fetch_ordered`, Auswertung im Hauptfaden in Eingabereihenfolge |

## Existing Patterns
- S3/S4: `fetch_ordered(items, fn, provider=..., deadline_at=...)`, Ergebnis in Eingabereihenfolge, Auswertung
  (Zustand, Logging, Zählung) nur im Hauptfaden.
- Fehlersemantik der Briefing-Pfade ist fail-soft (Platzhalter bzw. Etappe überspringen), `skipped`
  (deadline/timeout) wird wie ein Fehler behandelt.

## Befunde aus dem Kontext (für /20-analyse)
1. **Senke ist thread-sicher:** `_source_query_sink` ist eine ContextVar, `fetch_ordered` ruft `copy_context()`
   je Aufgabe, und die Senke wird INNERHALB der Aufgabe gesetzt. Das Anhängen an `official_queries` muss danach im
   Hauptfaden in Koordinatenreihenfolge passieren (nicht aus dem Worker).
2. **Trend-/Fallback-Schleifen sind NICHT einfach parallelisierbar:** `_convert_trip_to_segments` schreibt
   `self._last_converted_trip` und kann persistieren. Dieser Schritt muss seriell im Hauptfaden bleiben; parallel
   darf nur der Netzteil (`_fetch_weather` + `_enrich_ensemble_for_trip`) je Etappe laufen.
3. **Verschachtelung:** Ein `_fetch_weather` innerhalb eines Workers läuft inline seriell (kein Deadlock). Parallel
   wird also über Etappen, nicht mehr zusätzlich über Segmente. Die Gesamtparallelität bleibt durch den
   `open_meteo`-Slot (3) begrenzt.
4. **Provider-Schlüssel Warnungen:** eigener Schlüssel nötig (unbekannte Schlüssel bekommen 3 Slots,
   Env `GZ_PARALLEL_FETCH_SLOTS_<NAME>`). Zu klären in der Analyse; Warn-Abrufe laufen zusätzlich über
   `warn_egress.cached_fetch` mit Single-flight.
5. **Frist:** immer endliches `deadline_at` (ADR-0038/0103).
6. **Ortsvergleich-Briefing ist bereits parallel** (`comparison_parallel.py`, fix_1765_*); kein S5-Bedarf.
7. Kleinkram (Ensemble Hauptlauf, Nachtwetter, je 1 Aufruf): geringer Gewinn, nur falls billig mitnehmbar.

## Dependencies
- Upstream: `parallel_fetch`, `SegmentWeatherService`, `official_alerts`, `warn_egress`.
- Downstream: Briefing-Versand (Mail/Telegram/SMS/Premium-SMS), Gewitter-Zeile (TH+), Ausblick-Tabelle, Quellen-Gesundheit
  (#1441 S2, `official_queries`).

## Existing Specs
- `docs/specs/modules/feat_1539_s4_radar_parallel.md` (Format-Vorlage), `feat_1539_s3_trip_alarm_parallel.md`,
  `feat_1539_s1b_s2_abruf_baustein.md`; ADR `docs/adr/0103-parallele-abrufe-semaphorenzahlen.md`.

## Risks & Considerations
- Reihenfolge von Warnungen, Trend-Zeilen und `official_queries` muss identisch zum seriellen Lauf bleiben.
- Mandantentrennung: `self._user_id` wird von Workern gelesen, bleibt unverändert; Test mit zwei Nutzern nötig.
- Totalausfall-Erkennung (`OUTAGE_WITHHOLD_RATIO`) und Fehlerplatzhalter dürfen sich nicht ändern.
- Briefing ist kritischer Versandpfad → Adversary mit Mutations-Gegenprobe, mindestens 2 Runden.

## Analysis

### Type
Feature (Performance/Skalierung, kein Verhaltenswechsel). Scheibe S5 von #1539 (Epic #2138); #1539 bleibt offen („Refs #1539").

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_report_scheduler.py` (Warnungsblock ~1733-1760) | MODIFY | Eindeutige Startkoordinaten per `fetch_ordered` (eigener Provider-Schlüssel `official_alerts`); Worker liefert `(alerts, unavailable, sink)`; Zuweisung an `sw` und `official_queries.extend(...)` im Hauptfaden in Koordinatenreihenfolge |
| `src/services/trip_report_scheduler.py` (`_build_stage_trend` ~2973-3011) | MODIFY | Zweiphasig: (1) seriell im Hauptfaden Horizont-Check + `_convert_trip_to_segments` je Etappe (hält `_last_converted_trip` / Backfill im Hauptfaden), (2) `fetch_ordered` über die Etappen für `_fetch_weather` + `_enrich_ensemble_for_trip`, (3) Auswertung/Zeilenbau seriell in Etappenreihenfolge |
| `src/services/trip_report_scheduler.py` (`_collect_future_stage_weather` ~3403-3470) | MODIFY | Gleiches Zweiphasen-Muster, gemeinsamer Helfer mit dem Trend (kein Doppelcode) |
| `src/services/trip_report_scheduler.py` (neue Konstante) | MODIFY | Endliche Frist für den Etappen-/Warn-Abruf (analog `FETCH_WEATHER_DEADLINE_SECONDS`, ADR-0038/0103) |
| `docs/specs/modules/feat_1539_s5_briefing_parallel.md` | CREATE | Spec (Format wie S4) |
| `tests/tdd/test_briefing_parallel_*.py` | CREATE | Verhaltenstests (Reihenfolge, Fail-soft, Zwei-Nutzer, Frist, Parallelitätsnachweis) |

### Scope Assessment
- Files: 1 Produktivdatei (+ Spec, 1–2 Testdateien)
- Estimated LoC: ca. +90/−40 Produktion, +250 Test
- Risk Level: MEDIUM — kritischer Versandpfad (alle vier Kanäle), aber rein mechanische Umstellung mit unveränderter Fehlersemantik

### Technical Approach
Vorbild S3/S4: `fetch_ordered(items, fn, provider=..., deadline_at=...)`, Ergebnis in Eingabereihenfolge, **Auswertung und Zustandsänderung nur im Hauptfaden**.

1. **Amtliche Warnungen** (Befund 1, 4): Worker setzt `collect_source_queries(_sink)` selbst (ContextVar wird je Aufgabe per `copy_context()` isoliert) und gibt `(alerts, unavailable, _sink)` zurück; Fehler/`skipped` ⇒ bisheriger Platzhalter (`[]`, `unavailable=True`, Warn-Log). `official_queries.extend(_briefing_queries(_sink, sw))` im Hauptfaden in Koordinatenreihenfolge. **Provider-Schlüssel `official_alerts`** (eigene Semaphore, Default 3 reicht; Warndienste sind Amtsdienste ⇒ Höflichkeitsgrenze, nicht der `open_meteo`-Slot, damit Warn- und Wetterabruf einander nicht blockieren). Single-flight in `warn_egress.cached_fetch` bleibt Schutz gegen Doppelabrufe gleicher Koordinate; die seriell-parallele Mehrfachabfrage nationaler Dienste (C4-64) ist Nebenbefund, nicht S5-Umfang.
2. **Trend + Gewitter-Fallback** (Befund 2, 3): Der Schritt `_convert_trip_to_segments` bleibt seriell im Hauptfaden (Instanzzustand `_last_converted_trip`, GPX-Backfill/Persistenz). Danach läuft je Etappe der reine Netzteil (`_fetch_weather` + `_enrich_ensemble_for_trip`) über `fetch_ordered(provider="open_meteo")`. Das verschachtelte `_fetch_weather` läuft im Worker inline seriell (kein Deadlock; Parallelität über Etappen statt Segmente, begrenzt durch den `open_meteo`-Slot 3). Ein gemeinsamer privater Helfer bedient Trend und Fallback (Anti-Duplikat).
3. **Fehlersemantik unverändert:** Trend: leere Segmente/leeres Wetter/Ausnahme ⇒ `failures.add(UNAVAILABLE)`, Etappe entfällt; Fallback: Etappe wird still übersprungen. `skipped` (deadline/timeout) zählt wie Fehler und wird laut geloggt. Horizont-Prüfung (`BEYOND_HORIZON`) bleibt vor dem Abruf, im Hauptfaden.
4. **Nicht im Umfang:** Ortsvergleich-Briefing (schon parallel, Befund 6); Ensemble-Hauptlauf/Nachtwetter (je 1 Aufruf, Befund 7 – kein Gewinn); Atomarität `openmeteo.py` (C4-63) und Thundering Herd dpc/vigilance (C4-64) bleiben Nebenbefunde in #1539/#1199.

### Befunde, die gegen den Plan sprechen
Keine harten. Zwei bewusste Grenzen: (a) Gesamtparallelität bleibt durch `open_meteo`-Slot 3 gedeckelt – der Gewinn liegt in Überlappung von Warn- und Etappenabruf sowie 3 Etappen gleichzeitig statt nacheinander; (b) im Trend wird `trip` pro Etappe aus `_last_converted_trip` fortgeschrieben – diese Reihenfolge muss in der seriellen Vorphase exakt erhalten bleiben (Test mit Backfill-Trip).

### Dependencies
Upstream: `parallel_fetch`, `SegmentWeatherService`, `official_alerts` (+ `warn_egress`). Downstream: Briefing-Versand aller vier Kanäle, TH+-Zeile, Ausblick-Tabelle, Quellen-Gesundheit (`official_queries`, #1441 S2). ADR-0038/0103.

### Open Questions
- [ ] Frist-Wert für Etappen-Abruf (Vorschlag: `FETCH_WEATHER_DEADLINE_SECONDS` wiederverwenden, kein neuer Wert) – in Spec festlegen, kein PO-Thema.
- [ ] Parallelitätsnachweis im Test: Überlappung per Zeitmessung/Barrier statt Mock der eigenen Annahme (Spec AC).
