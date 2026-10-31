# Context: fix-2234-compare-forecast-cache

## Request Summary
Issue #2234 (aus Triage #1199, Eintrag C4-61): Der Ortsvergleich-Pfad holt die Grundvorhersage
ohne Zwischenspeicher. Eine zweite Vorschau desselben Vergleichs dauert deshalb genauso lange wie
die erste (gemessen: 3 Orte kalt 75,76 s / warm 75,66 s). Das in #1329 angekündigte Folge-Ticket
„Grundvorhersage-Cache im Vergleichspfad" wurde nie angelegt.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/comparison_engine.py:412-442` | `fetch_forecast_for_location`: `ForecastService(get_provider("openmeteo")).get_forecast(location, hours_ahead=hours)`, direkt, ohne Cache; danach Bergfex (:447 ff.) |
| `src/services/comparison_engine.py:40,143-145` | `COMPARE_FORECAST_HOURS = 96`; `ComparisonEngine.run` ruft je Ort genau einmal `fetch_forecast_for_location` |
| `src/services/forecast.py:59-90` | `get_forecast`: Fenster `now` (ungerundet) bis `now+hours`; ruft `provider.fetch_forecast` mit Default-Enrich (Ensemble + Schnee = True) |
| `src/services/weather_cache.py` | `WeatherCacheService` (rohe `NormalizedTimeseries`, Bucket `lat_lon_elev_model_ensemble_snow`, „covers"-Trefferregel über Fenster, TTL, LRU 100), Prozess-Singleton `get_shared_weather_cache()` (TTL 600 s) |
| `src/services/segment_weather.py:64-300` | Einziger heutiger Cache-Nutzer: Cache-get → Single-Flight (#1539) → Budget-Gate (#1329/#2387, je `user_id`) → Fetch → put |
| `src/services/compare_location_weather_source.py:116-187` | Compare-ALARM-Pfad nutzt bereits `SegmentWeatherService` (Ein-Punkt-`TripSegment`, `enrich_ensemble=False`, `enrich_snow=False`, `priority="alert_check"`, `user_id`) |
| `src/services/comparison_parallel.py:75-96` | Vorschau läuft je Ort parallel (#1765 B1) |
| `src/services/compare_preview_service.py:129` | Vorschau-Aufrufer (96 h) |
| `src/services/scheduler_dispatch_service.py:833` | Versand-Aufrufer (96 h) |
| `api/routers/compare.py:34,80-87` | Sofortvergleich, `forecast_hours` Query-Default 48 |
| `src/providers/openmeteo.py:1035-1320` | `fetch_forecast`: Hauptabruf (+ Modell-Fallback), UV/AQ, Ensemble, metric_gap-Fallback, Schnee (GeoSphere, nur SNOWGRID-Gebiet), Gewitter-Anreicherung (DWD/DWD-EU/Météo-France) — ca. 4–7+ HTTP-Abrufe je Ort |

## Existing Patterns
- **Cache auf ROHER Zeitreihe, nie auf abgeleitetem Ergebnis** (#1329 F001): Identität und Aggregat entstehen beim Aufrufer. Ein Vergleichs-Cache muss dasselbe tun.
- **„Covers"-Regel statt exakter Schlüssel**: Ein Eintrag mit breiterem Fenster bedient engere Anfragen. Ungerundetes `now` als Fensterstart trifft trotzdem (späteres `now` liegt im alten Fenster), solange das Ende (`now+96h`) gedeckt ist. Ein später gestarteter Aufruf mit gleichem `hours` hat ein Ende nach dem gespeicherten → **Miss**. Fensterbildung muss für Treffer gerundet/angeglichen werden (Analyse-Punkt).
- **Höhe im Schlüssel** (#1991), auf ganze Meter normalisiert.
- **Single-Flight** (#1539) gegen doppelte gleichzeitige Abrufe desselben Schlüssels.
- **Fake-Provider mit `call_count`, ohne Mock**: `tests/unit/test_forecast_cache_sharing.py` (`CountingFakeProvider` :48 u. a.), Test „Trip und Compare-Preset am selben Ort teilen einen Abruf" (:339).

## Dependencies
- Upstream: `providers.base.get_provider`, `OpenMeteoProvider.fetch_forecast` (inkl. Enrichment-Kaskade), `WeatherCacheService`, `ForecastBudgetGate` (je Nutzer), `BergfexScraper`.
- Downstream: `ComparisonEngine.run` → Vorschau (`compare_preview_service`), Versand (`scheduler_dispatch_service`), Sofortvergleich (`api/routers/compare.py`) → Renderer (E-Mail-Vergleichstabelle, SMS, Telegram, Premium-SMS).

## Existing Specs
- `docs/specs/modules/fix_1329_forecast_cache_budget.md:399-419` — Scope-Schnitt, Ankündigung des Folge-Tickets
- `docs/context/fix-1765-1839-vorschau-laufzeit.md:96-134,254-258` — Messtabelle (75 s / 25 s je Ort), Cache-Inventar je Abruf-Gruppe
- `docs/specs/modules/fix_1765_b1_compare_vorschau_parallel.md:20,168-169` — Parallelisierung, erwartet ~26 s (langsamster Ort)
- `docs/specs/modules/shared_preview_tab.md:216` — verweist auf #2234

## Risks & Considerations
- **Wirkung nur beim wiederholten Aufruf**: Ein Cache macht die *erste* (kalte) Vorschau nicht schneller. Er hilft bei wiederholter Vorschau, bei Vorschau → Versand und bei gleichen Orten in Trip/Vergleich/Alarm. Die Analyse muss klären, welche Zahl die Spec als Erfolg zusagt.
- **Zeitanteile unbekannt**: Es gibt nur die Summe je Ort (~25 s). Nicht gemessen ist, wie viel auf den Hauptabruf, das Ensemble, den Schnee, den Gewitter-Abruf (DWD, Budget 150 s, „teuerster Einzelabruf", ohne Cache), Bergfex oder amtliche Warnungen (gecacht, 1800 s) fällt. Wenn ein nicht gecachter Teil (Gewitter, Bergfex) außerhalb von `fetch_forecast` liegt oder der Cache-Schlüssel ihn nicht umfasst, bleibt „warm" langsam. **Erste Aufgabe der Analyse: Zeit je Gruppe messen.**
- **Enrich-Flags im Schlüssel**: Der Vergleich braucht Ensemble + Schnee (True/True); der Compare-Alarm-Pfad holt False/False. Das sind getrennte Buckets ohne gegenseitigen Treffer. Das ist korrekt und darf nicht „optimiert" werden, sonst fehlen Daten.
- **Frische vs. Versand**: TTL 600 s. Ein Versand darf keine ältere Vorhersage nutzen als heute auch; `cached_at` muss als Abrufzeit erhalten bleiben.
- **Budget-Gate je Nutzer** (#2387): Wenn der Vergleichspfad über `SegmentWeatherService` läuft, unterliegt er dem Gate. Vorschau und Versand sind `user_briefing`-äquivalent und dürfen nie gedrosselt werden. Die Priorität muss bewusst gewählt werden.
- **Mandanten**: Der Cache-Schlüssel enthält kein `user_id` (Wetter ist nutzerneutral, gewollt). Es darf nichts Nutzerbezogenes (Name, Preset-ID) in den gecachten Wert gelangen.
- **Parallelität**: Die Vorschau holt die Orte gleichzeitig. Single-Flight verhindert doppelte Abrufe desselben Orts.
- **Code-Teilung**: Trip-Pfad und Compare-Alarm-Pfad nutzen schon `SegmentWeatherService`. Eine Lösung sollte diesen geteilten Weg nutzen und keinen zweiten Cache bauen (Teilungs-Gate, Anti-Pattern #1170).

## Analysis

### Type
Bug (Leistungsfehler: zweite Vorschau desselben Vergleichs ist so langsam wie die erste)

### Messung (live, lokal, 2026-10-31, Skript im Scratchpad)
| Teilabruf je Ort (96 h) | Alpen kalt | Alpen warm | Korsika kalt | Korsika warm |
|---|---|---|---|---|
| gesamt `fetch_forecast_for_location` | 11,76 s | 0,69 s | 14,59 s | 14,59 s |
| Gewitter-Anreicherung (`enrich_thunder`, in `fetch_forecast`) | 10,87 | 0,32 (`dwd.py _RASTER_CACHE`) | 14,35 (ICON-EU, `dwd_eu.py` ohne Cache) | 14,43 |
| Hauptabruf, UV, Ensemble, metric_gap, SNOWGRID, Radar | je < 0,4 | ≈ 0 | je < 0,1 | ≈ 0 |
| amtliche Warnungen (außerhalb, eigener 1800-s-Cache) | 1,02 | 0,01 | 0,18 | 0,01 |

- Vorschau mit 3 Orten (parallel, `run_comparison_parallel`): **27,05 s kalt / 14,23 s warm** (Rest = Korsika ICON-EU).
- Die Zahl 75 s im Issue stammt vom 2026-08-15, also **vor** der Parallelisierung #1765 B1 (Merge 2026-08-16). Sie ist veraltet, das Grundproblem (kalt ≈ warm) besteht aber weiter.
- **Fast 100 % der Zeit liegen innerhalb `OpenMeteoProvider.fetch_forecast`.** Ein Treffer im Shared Cache (rohe, fertig angereicherte `NormalizedTimeseries`) überspringt alles davon, einschließlich Gewitter.
- **Bergfex** (`comparison_engine.py:449`, ohne Cache): in Prod hat kein Nutzer einen `bergfex_slug` gesetzt (0 Dateien unter `data/users`), daher keine Rest-Latenz. Er bleibt außerhalb des Scopes.

### Ursache (Root Cause)
1. `fetch_forecast_for_location` (`comparison_engine.py:412 ff.`) ruft `ForecastService.get_forecast` direkt auf, am geteilten `WeatherCacheService` vorbei. `ForecastService` wird nur hier genutzt.
2. Selbst mit Cache gäbe es keinen Treffer: `forecast.py:80-81` bildet das Fenster `now`/`now+96h` sekundengenau, und die Covers-Regel `weather_cache.py:138` verlangt `entry.window_end >= req_end`. Ein Aufruf 30 s später ist ein MISS. Der Single-Flight-Schlüssel (`weather_cache.py:262-270`) enthält das Fenster, ein Doppelklick teilt also auch keinen Abruf.

### Fenster-Neutralität (geprüft)
- Der Provider fragt Open-Meteo **tageweise** ab (`openmeteo.py:1112-1114`, `strftime("%Y-%m-%d")`) und schneidet die Daten nicht zu. Die Gewitter-Anreicherung richtet sich nach den Zeitstempeln der Reihe und nach „jetzt" (`thunder_enrichment.py:93-98, 598`), nicht nach `start`/`end`.
- ⇒ Ein Fenster, dessen **UTC-Kalendertage gleich bleiben**, liefert identische Daten. Gewählt wird: Start = `now` auf die volle Stunde abgerundet, Ende = 23:59:59 UTC des Tages von `now+96h`. Das Ende darf **nicht** auf den nächsten 00:00 springen, sonst käme ein Extra-Tag hinzu und die Aggregate würden sich ändern.
- `fetch_forecast_for_location` aggregiert über **alle** Punkte von `forecast.data`. Zieltag und Zeitfenster schneidet erst `ComparisonEngine.run` (`_filter_by_target_date_and_window`) zu, der Ausblick nutzt die Folgetage aus `raw_data`. Weil die Tage gleich bleiben, ändern sich auch diese Werte nicht.
- Restrisiko: Ensemble und metric_gap könnten `start`/`end` direkt nutzen. Das muss im Validator per Punkt-für-Punkt-Vergleich (alt gegen angeglichen, live) belegt werden.

### Varianten
| Kriterium | (1) Segment-Weg + angeglichenes Fenster | (2) eigener Cache in ForecastService | (3) tolerante Covers-Regel |
|---|---|---|---|
| Code-Teilung (#1170) | ein Cache, ein Single-Flight, ein Budget-Gate, wie im Compare-Alarm-Pfad | zweiter Cache = Verstoß | geteilt, ändert aber die globale Regel |
| Treffer Vorschau→Vorschau/Versand (10 min) | ja | ja | ja |
| Risiko Trip-/Alarm-Pfad | gering (Trip-Fenster enger, Test :339 deckt das Teilen ab) | keins | hoch (bricht die F001-Garantie „kein stilles Abschneiden") |
| Budget-Gate | Vorschau bucht künftig 1 Abruf je MISS (`user_briefing`, nie gedrosselt) | umgangen | wie heute |
| LoC | ~60–90 + Tests | ~50–70, doppelte Pflege | ~30 + Folgetests |

**Empfehlung: Variante 1.**

### Technical Approach
1. `fetch_forecast_for_location` holt über `SegmentWeatherService.fetch_segment_weather` mit einem Ein-Punkt-`TripSegment`, nach dem Muster von `compare_location_weather_source.py:116-187`, mit diesen Parametern: `enrich_ensemble=True`, `enrich_snow=True` (eigener Bucket, korrekt getrennt vom Alarm-Bucket False/False), `priority="user_briefing"` und `user_id`.
2. Das angeglichene Fenster wird an **einer** Stelle (Hilfsfunktion) gebildet. `weather_cache.py` (Covers-Regel, Schlüssel) und der Trip-Pfad bleiben unverändert.
3. `user_id` wird als Keyword (Default `None`) durchgereicht: `compare_preview_service.py:129`, `scheduler_dispatch_service.py:833` und `api/routers/compare.py:80-87` → `comparison_parallel.run_comparison_parallel` / `_run_one_location` → `ComparisonEngine.run` → `fetch_forecast_for_location`. Die Worker im ThreadPool erben keine ContextVars, deshalb geschieht das explizit.
4. Fehlerabbildung: Aus dem Segment-Weg kommt `has_error`/`error_message` (Drosselung: `budget_throttled`) zurück, nicht eine Exception. Das muss auf `result["error"]` abgebildet werden, in der Form, die `ComparisonEngine.run:147-161` erwartet.
5. Guard: Eine erfolgreiche, aber **leere** Zeitreihe wird nicht gecacht (`segment_weather.py:~258`, `put` nur bei `timeseries.data`). Das wirkt auch im Trip-Pfad und ist dort ebenso richtig.
6. Vorhersage-Mitschnitt (#2030, `segment_weather.py:393-404`): Er greift für jeden Aufruf des geteilten Service. Der Vergleich folgt dem Compare-Alarm-Pfad und nutzt eine stabile, nutzerneutrale `point_id` als `segment_id`. Ein neuer Schalter am geteilten Service ist nicht vorgesehen.
7. Mandanten: Im gecachten Wert steht kein Ortsname und keine Nutzerkennung (`ForecastMeta`/Datenpunkte ohne Namen, der Segment-Weg setzt einen neutralen Namen).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/comparison_engine.py` | MODIFY | Abruf über `SegmentWeatherService`, Fenster-Angleichung, Fehlerabbildung, `user_id` in `run` und `fetch_forecast_for_location` |
| `src/services/comparison_parallel.py` | MODIFY | `user_id` durchreichen |
| `src/services/compare_preview_service.py` | MODIFY | `user_id` übergeben |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `user_id` übergeben |
| `api/routers/compare.py` | MODIFY | `user_id` übergeben |
| `src/services/segment_weather.py` | MODIFY | Guard: leere Zeitreihe nicht cachen |
| `tests/unit/test_compare_forecast_cache.py` (o. ä., nach Verhalten benannt) | CREATE | `CountingFakeProvider`, ohne Mock |

### Scope Assessment
- Dateien: 6 Produktiv + 1 Test
- Estimated LoC: +80/-20 Produktivcode, ~+150 Test
- Risk Level: MEDIUM (zentraler Abrufweg von Vorschau, Versand und Sofortvergleich, dazu neue Budget-Buchung)

### Zusagbarer Erfolg (für die ACs)
- Zweite Vorschau desselben Vergleichs innerhalb 10 min: **0 Provider-Abrufe**, identische `raw_data` und Aggregate.
- Vorschau → Versand innerhalb 10 min: 0 Provider-Abrufe.
- Zwei gleichzeitige Vorschauen (Doppelklick): 1 Abruf je Ort (Single-Flight).
- Ein Trip-Etappenpunkt am selben Ort (enrich True/True) wird vom Vergleichs-Eintrag bedient. Ein Compare-Alarm (False/False) bleibt getrennt.
- Fehler und leere Reihen werden nicht gecacht. Der nächste Aufruf holt neu.
- Zwei Nutzer, gleicher Ort: Der Abruf wird geteilt, das Budget wird beim auslösenden Nutzer gebucht, und im Ergebnis des zweiten Nutzers steht nichts Nutzerbezogenes des ersten.
- **Nicht zugesagt:** schnellere kalte Vorschau (~27 s bei 3 Orten, bestimmt von der Gewitter-Anreicherung).

### Dependencies
`SegmentWeatherService` (Cache, Single-Flight #1539, Budget-Gate #1329/#2387), `get_shared_weather_cache` (TTL 600 s), `OpenMeteoProvider.fetch_forecast`, `forecast_capture` (#2030).

### Folge-Tickets (beim Abschluss anlegen)
- Gewitter-Laufzeit kalt: `dwd_eu.py` ohne Cache (14,4 s kalt = warm, ICON-EU-Gebiet); `dwd.py _RASTER_CACHE` verfällt bei Modelllauf-Wechsel/Neustart. Hinweis: `docs/context/fix-1765-1839-vorschau-laufzeit.md` sagt noch „dwd.py ohne Cache", das ist durch #2465 überholt.

### Open Questions
- keine an den PO (alle Punkte technisch entschieden)
