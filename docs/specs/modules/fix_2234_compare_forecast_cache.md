---
entity_id: fix_2234_compare_forecast_cache
type: module
created: 2026-10-31
updated: 2026-10-31
status: draft
version: "1.0"
tags: [forecast, cache, compare, ortsvergleich, vorschau, single-flight, budget]
---

# Grundvorhersage-Cache im Ortsvergleich-Pfad (Issue #2234)

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich holt die Grundvorhersage je Ort direkt über `ForecastService.get_forecast`, am prozessweit geteilten Wetter-Cache vorbei. Eine zweite Vorschau desselben Vergleichs, der Versand nach einer Vorschau und ein Doppelklick rufen deshalb den Wetter-Anbieter jedes Mal erneut ab. Dieses Modul führt den Vergleichs-Abruf über denselben geteilten Weg (`SegmentWeatherService`), den schon der Trip-Pfad und der Compare-Alarm-Pfad nutzen, und gleicht das Abruf-Fenster so an, dass die bestehende „Covers"-Trefferregel des Caches im Vergleich überhaupt greifen kann. Folge-Ticket aus #1329 (dort als „Grundvorhersage-Cache im Vergleichspfad" angekündigt, nie angelegt).

Erfolgszusage: **wiederholte** Abrufe (zweite Vorschau, Vorschau → Versand, gleiche Orte in Trip/Vergleich) kosten innerhalb von 10 Minuten keinen Anbieter-Abruf mehr. Die **erste (kalte)** Vorschau wird dadurch **nicht** schneller (siehe „Nicht im Scope").

### Messung (live, lokal, 2026-10-31)

| Teilabruf je Ort (96 h) | Alpen kalt | Alpen warm | Korsika kalt | Korsika warm |
|---|---|---|---|---|
| gesamt `fetch_forecast_for_location` | 11,76 s | 0,69 s | 14,59 s | 14,59 s |
| Gewitter-Anreicherung (in `fetch_forecast`) | 10,87 s | 0,32 s | 14,35 s | 14,43 s |
| Hauptabruf, UV, Ensemble, metric_gap, SNOWGRID, Radar | je < 0,4 s | ca. 0 | je < 0,1 s | ca. 0 |

Vorschau mit 3 Orten (parallel): 27,05 s kalt / 14,23 s warm. Die im Issue genannten 75 s stammen vom 2026-08-15, also vor der Parallelisierung #1765 B1, und sind veraltet. Fast 100 % der Zeit liegen innerhalb von `OpenMeteoProvider.fetch_forecast`; ein Treffer im Shared Cache (rohe, fertig angereicherte Zeitreihe) überspringt alles davon, einschließlich der Gewitter-Anreicherung.

## Source

- **File:** `src/services/comparison_engine.py`
- **Identifier:** `fetch_forecast_for_location`, `ComparisonEngine.run`, neue Fenster-Hilfsfunktion
- **File:** `src/services/comparison_parallel.py` (`run_comparison_parallel`, `_run_one_location`: `user_id` durchreichen)
- **File:** `src/services/compare_preview_service.py` (Aufrufer Vorschau, 96 h)
- **File:** `src/services/scheduler_dispatch_service.py` (Aufrufer Versand, 96 h)
- **File:** `api/routers/compare.py` (Aufrufer Sofortvergleich)
- **File:** `src/services/segment_weather.py` (Guard: leere Zeitreihe nicht cachen)

> **Schicht-Hinweis:** Alles liegt im Python-Core (`src/services/`, `api/`). Die Go-API, das Frontend und `src/services/weather_cache.py` (Covers-Regel, Schlüssel) bleiben unverändert. Die Go-API reicht die echte `user_id` bereits an den Python-Core durch; dort wird sie bis zum Abruf weitergegeben.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Trip-Pfad und Compare-Alarm-Pfad nutzen `SegmentWeatherService` bereits (Beispiel `compare_location_weather_source.py:116-187`). Der Vergleichs-Abruf nutzt denselben Weg, mit demselben Cache, demselben Single-Flight (#1539) und demselben Budget-Gate (#1329/#2387). Ein eigener Cache im `ForecastService` (zweiter Cache) wäre ein Verstoß gegen die Code-Teilung (Anti-Pattern #1170) und ist deshalb ausdrücklich verworfen. Es entsteht keine neue Compare-Komponente mit Trip-Pendant.
> - **Mandantentrennung:** Wetter ist nutzerneutral; der Cache-Schlüssel enthält bewusst kein `user_id`. Die echte `user_id` wird nur für das Budget-Gate durchgereicht, nie `"default"`. Getestet mit zwei verschiedenen Nutzern (AC-7).
> - **Kanäle:** Die Änderung betrifft nur die Beschaffung der Rohdaten vor dem Rendern. Der Inhalt der vier Kanäle (E-Mail · Telegram · SMS · Premium-SMS) bleibt unverändert, weil Rohdaten und Aggregate identisch sind (AC-1, AC-4).

## Estimated Scope

- **LoC:** ca. +80/-20 Produktivcode, ca. +150 Test
- **Files:** 6 Produktiv + 1 Test
- **Effort:** medium (Risk: MEDIUM, zentraler Abrufweg von Vorschau, Versand und Sofortvergleich, dazu neue Budget-Buchung)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `SegmentWeatherService.fetch_segment_weather` | upstream | Geteilter Abrufweg: Cache-get → Single-Flight → Budget-Gate → Fetch → put |
| `get_shared_weather_cache` / `WeatherCacheService` | upstream | Prozessweiter Cache, TTL 600 s, Covers-Regel (unverändert) |
| `ForecastBudgetGate` | upstream | Tagesbudget je Nutzer; Priorität `user_briefing` wird nie gedrosselt |
| `OpenMeteoProvider.fetch_forecast` | upstream | Hauptabruf inkl. Ensemble, Schnee, Gewitter-Anreicherung |
| `forecast_capture` (#2030) | upstream | Vorhersage-Mitschnitt im geteilten Service |
| `compare_location_weather_source.py` | Vorbild | Ein-Punkt-`TripSegment`-Muster für den Segment-Weg |
| `ComparisonEngine.run`, `comparison_parallel` | downstream | Aufrufer von `fetch_forecast_for_location` |
| Vorschau, Versand, Sofortvergleich | downstream | Drei Aufrufer, die die `user_id` liefern müssen |

## Implementation Details

Gewählt ist Variante 1 der Analyse (Segment-Weg + angeglichenes Fenster). Verworfen: (2) eigener Cache im `ForecastService` (zweiter Cache, umgeht Single-Flight und Budget-Gate), (3) tolerantere Covers-Regel (bricht die F001-Garantie aus #1329 „kein stilles Abschneiden" für alle Pfade).

**Ursache:** (1) `fetch_forecast_for_location` ruft `ForecastService.get_forecast` direkt am Cache vorbei. (2) Selbst mit Cache gäbe es keinen Treffer: `forecast.py` bildet das Fenster `now` bis `now+96h` sekundengenau, und die Covers-Regel verlangt `entry.window_end >= req_end`. Ein Aufruf 30 s später hat ein späteres Ende und ist ein Miss; der Single-Flight-Schlüssel enthält das Fenster, ein Doppelklick teilt also auch keinen Abruf.

**1. Abruf über den Segment-Weg.** `fetch_forecast_for_location` holt über `SegmentWeatherService.fetch_segment_weather` mit einem Ein-Punkt-`TripSegment` (Muster `compare_location_weather_source.py:116-187`) und diesen Parametern:

```
enrich_ensemble=True, enrich_snow=True   # eigener Bucket, getrennt vom Alarm-Bucket (False/False)
priority="user_briefing"                 # Vorschau/Versand nie gedrosselt
user_id=<echte user_id>                  # Budget-Buchung beim ausloesenden Nutzer
```

**2. Fenster-Angleichung an einer Stelle** (eine Hilfsfunktion in `comparison_engine.py`, festgelegt in der RED-Phase: `compare_fetch_window(now: datetime, hours: int = COMPARE_FORECAST_HOURS) -> tuple[datetime, datetime]`, beide Werte mit `tzinfo is timezone.utc`):

```
start = now(UTC) auf die volle Stunde abgerundet
end   = 23:59:59 UTC des Kalendertags von (now + 96 h)
```

Begründung (geprüft): Der Provider fragt Open-Meteo tageweise ab (`strftime("%Y-%m-%d")`) und schneidet nicht zu; die Gewitter-Anreicherung richtet sich nach den Zeitstempeln der Reihe und nach „jetzt", nicht nach `start`/`end`. Ein Fenster mit gleichen UTC-Kalendertagen liefert daher identische Daten. Das Ende darf **nicht** auf den nächsten 00:00 springen, sonst käme ein Extra-Tag hinzu und die Aggregate änderten sich. Innerhalb derselben Stunde ist das Fenster identisch; über die Stunde hinweg bleibt der Treffer erhalten, solange das gespeicherte Ende (`23:59:59` des Zieltags) das neue Ende deckt, also innerhalb desselben Kalendertags von `now+96h`. `weather_cache.py` und der Trip-Pfad bleiben unverändert.

`fetch_forecast_for_location` aggregiert weiterhin über alle Punkte der Zeitreihe; Zieltag und Zeitfenster schneidet wie bisher erst `ComparisonEngine.run` (`_filter_by_target_date_and_window`) zu, der Ausblick nutzt die Folgetage aus `raw_data`.

**3. `user_id` durchreichen** als Keyword (Default `None`): `compare_preview_service.py` (Vorschau), `scheduler_dispatch_service.py` (Versand) und `api/routers/compare.py` (Sofortvergleich) → `run_comparison_parallel` / `_run_one_location` → `ComparisonEngine.run` → `fetch_forecast_for_location`. Die Worker im ThreadPool erben keine ContextVars; die Übergabe geschieht deshalb explizit. Die `user_id` stammt aus dem Auth-Kontext des jeweiligen Aufrufers, nie ein Fallback auf `"default"`.

**4. Fehlerabbildung.** Der Segment-Weg liefert `has_error`/`error_message` (z. B. `budget_throttled`) statt einer Exception. Das wird auf `result["error"]` in der Form abgebildet, die `ComparisonEngine.run` (Fehlerbehandlung je Ort) heute erwartet; das Verhalten für den Aufrufer ist gegenüber heute unverändert.

**5. Guard gegen leere Reihen.** Eine erfolgreiche, aber leere Zeitreihe wird nicht gecacht (`put` nur bei `timeseries.data` nicht leer) in `segment_weather.py`. Das wirkt auch im Trip-Pfad und ist dort ebenso richtig.

**6. Vorhersage-Mitschnitt (#2030).** Er greift für jeden Aufruf des geteilten Service. Der Vergleich folgt dem Compare-Alarm-Pfad und nutzt eine stabile, nutzerneutrale `point_id` als `segment_id`. Ein neuer Schalter am geteilten Service ist nicht vorgesehen.

**7. Mandanten.** Im gecachten Wert steht kein Ortsname und keine Nutzerkennung; der Segment-Weg setzt einen neutralen Namen. Identität und Aggregat entstehen bei jedem Aufruf beim Aufrufer neu (Garantie F001 aus #1329).

## Expected Behavior

- **Input:** Vergleich (Orte, Zieltag, `user_id`) aus Vorschau, Versand oder Sofortvergleich.
- **Output:** Je Ort dieselben `raw_data` und Aggregate wie bisher; wiederholte Abrufe innerhalb von 10 Minuten werden aus dem geteilten Cache bedient. Fehler erscheinen unverändert als `result["error"]`.
- **Side effects:** Vorschau und Versand buchen künftig einen Abruf im Tagesbudget des auslösenden Nutzers je Cache-Miss (nie gedrosselt, Priorität `user_briefing`). Vergleichs-Abrufe füllen den geteilten Cache und werden so von Trip-Etappen am selben Ort mitbenutzt.

## Acceptance Criteria

- **AC-1:** Given ein Vergleich mit drei Orten, dessen Vorschau gerade berechnet wurde / When innerhalb von 10 Minuten dieselbe Vorschau erneut berechnet wird / Then gehen **0** Abrufe an den Wetter-Anbieter, und `raw_data` sowie alle Aggregate jedes Orts sind identisch mit der ersten Vorschau.
  - Test: `CountingFakeProvider` (ohne Mock) hinter dem geteilten Cache; zweite Vorschau über `ComparisonEngine.run` lässt den Zähler unverändert, und die Ergebnisse beider Läufe sind gleich.

- **AC-2:** Given eine Vorschau eines Vergleichs wurde berechnet / When innerhalb von 10 Minuten der Versand desselben Vergleichs läuft (Pfad des `scheduler_dispatch_service`) / Then gehen **0** Abrufe an den Wetter-Anbieter.
  - Test: Erst Vorschau-Aufruf, dann Versand-Aufruf mit demselben Fake-Provider; Zähler nach dem Versand gleich dem Zähler nach der Vorschau.

- **AC-3:** Given zwei Vorschauen desselben Vergleichs werden gleichzeitig gestartet (Doppelklick) und der Cache ist leer / When beide laufen / Then wird je Ort genau **1** Abruf an den Wetter-Anbieter gemacht (Single-Flight), und beide Vorschauen liefern dasselbe Ergebnis.
  - Test: Zwei Threads rufen `ComparisonEngine.run` gleichzeitig auf; der `CountingFakeProvider` verzögert den Abruf kurz, damit die Überschneidung sicher eintritt; Zähler gleich Anzahl der Orte.

- **AC-4:** Given eine Wetterlage für drei Orte / When das Fenster einmal wie bisher (`now` bis `now+96h`, sekundengenau) und einmal angeglichen (Start auf volle Stunde abgerundet, Ende 23:59:59 UTC des Tages von `now+96h`) abgerufen wird / Then liegt der Start auf einer vollen Stunde, das Ende exakt auf 23:59:59 UTC desselben Kalendertags wie `now+96h` (kein zusätzlicher Tag), und die Aggregate sind Punkt für Punkt unverändert gegenüber dem alten Fenster.
  - Test: Kern-Schicht prüft die Fensterhilfsfunktion mit festen Uhrzeiten (u. a. 23:59, 00:00, Stundenwechsel) auf Start/Ende und Tagesanzahl; der Live-Nachweis im Validator vergleicht alt gegen angeglichen Punkt für Punkt (inkl. Ensemble und metric_gap, die `start`/`end` womöglich direkt nutzen).

- **AC-5:** Given ein Vergleichs-Ort und eine Trip-Etappe am selben Ort (Anreicherung Ensemble + Schnee, True/True) sowie ein Compare-Alarm am selben Ort (False/False) / When zuerst der Vergleich und dann Trip-Etappe und Compare-Alarm abrufen / Then bedient der Vergleichs-Eintrag die Trip-Etappe ohne neuen Abruf, während der Compare-Alarm (eigener Bucket False/False) einen eigenen Abruf macht.
  - Test: `CountingFakeProvider`; Zähler bleibt nach der Trip-Etappe gleich, steigt beim Compare-Alarm um 1 (Muster `test_forecast_cache_sharing.py`, Test „Trip und Compare-Preset am selben Ort teilen einen Abruf").

- **AC-6:** Given der Wetter-Anbieter liefert einen Fehler oder eine erfolgreiche, aber leere Zeitreihe / When ein Vergleich berechnet wird und danach erneut / Then wird beides nicht gecacht, der nächste Aufruf holt neu, und der Fehler erscheint wie heute als `result["error"]` des betroffenen Orts (die übrigen Orte werden weiter ausgewertet).
  - Test: Fake-Provider, der zuerst einen Fehler bzw. leere Daten und dann gültige Daten liefert; Zähler steigt bei beiden Aufrufen, der zweite Lauf liefert Daten; die Form von `result["error"]` entspricht der bisherigen.

- **AC-7:** Given zwei verschiedene Nutzer mit je einem Vergleich, der denselben Ort enthält / When beide Vorschauen nacheinander laufen / Then wird der Anbieter-Abruf geteilt (1 Abruf), das Budget wird nur beim auslösenden Nutzer gebucht, und im Ergebnis des zweiten Nutzers steht nichts Nutzerbezogenes des ersten (kein Name, keine Kennung). Außerdem reichen Vorschau, Versand und Sofortvergleich die echte `user_id` des jeweiligen Nutzers durch, nie `"default"`.
  - Test: Zwei Nutzer-IDs gegen denselben Fake-Provider; Budget-Zähler je Nutzer geprüft (nur Nutzer A bucht), Ergebnis von Nutzer B enthält keine Felder von A. Für alle drei Aufrufer prüft ein Test, dass die am Segment-Weg ankommende `user_id` die des Aufrufers ist.

- **AC-8:** Given das Tagesbudget eines Nutzers ist zu mehr als 95 % ausgeschöpft / When dieser Nutzer eine Vorschau oder den Versand eines Vergleichs auslöst / Then wird der Abruf nie gedrosselt (Priorität `user_briefing`), und das Ergebnis enthält keinen Fehler `budget_throttled`.
  - Test: `ForecastBudgetGate` mit vorpräpariertem Zählerstand (96 %); Vorschau und Versand liefern Daten und erreichen den Fake-Provider.

## Known Limitations

- **Keine schnellere kalte Vorschau.** Die erste Vorschau bleibt bei ca. 27 s für 3 Orte (Messung oben), bestimmt von der Gewitter-Anreicherung. Der Cache hilft nur beim wiederholten Aufruf.
- **TTL 10 Minuten.** Nach Ablauf (oder nach Neustart von `gregor-python`, In-Memory-Singleton) wird neu geholt; ein Versand nutzt keine ältere Vorhersage als heute, `cached_at` bleibt als Abrufzeit erhalten.
- **Neue Budget-Buchung.** Vorschau und Versand verbrauchen jetzt je Miss ein Stück Tagesbudget (zuvor am Gate vorbei). Sie werden dennoch nie gedrosselt.
- **Fenster-Restrisiko.** Ensemble und metric_gap könnten `start`/`end` direkt nutzen; das wird live im Validator per Punkt-für-Punkt-Vergleich (AC-4) belegt, nicht nur angenommen.

## Nicht im Scope

- Schnellere kalte Vorschau (Gewitter-Anreicherung, ca. 27 s für 3 Orte).
- Bergfex-Abruf in `comparison_engine.py` (ohne Cache; in Prod hat kein Nutzer einen `bergfex_slug` gesetzt, daher keine Rest-Latenz).
- Änderung der Covers-Regel oder von `weather_cache.py`.
- Ein neuer oder zweiter Cache.

**Folge-Ticket (beim Abschluss anlegen):** Cache für die ICON-EU-Gewitter-Anreicherung `dwd_eu.py` (Korsika und übriges ICON-EU-Gebiet: 14,4 s kalt gleich warm, ohne Cache); dazu der `_RASTER_CACHE` in `dwd.py`, der bei Modelllauf-Wechsel und Neustart verfällt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird kein neuer Mechanismus eingeführt. Der Vergleichs-Abruf nutzt den bestehenden geteilten Cache samt Single-Flight und Budget-Gate (ADR-0032, #1329). Die Entscheidung gegen einen zweiten Cache folgt der festen Teilungsregel Trip/Ortsvergleich.

## Test Plan

Kern-Schicht, netzfrei, ohne Mock-Theater (Test-Politik siehe `CLAUDE.md`):

- Neue Testdatei nach Verhalten benannt: `tests/unit/test_compare_preview_second_call_uses_cache.py`.
- `CountingFakeProvider` nach dem Muster aus `tests/unit/test_forecast_cache_sharing.py` (echte, deterministische `NormalizedTimeseries`, Aufrufzähler, kein `patch()`/`Mock()`); der Shared-Cache-Reset läuft zentral über die autouse-Fixture in `tests/conftest.py`.
- AC-1/AC-2/AC-5: Zähler vor und nach zweitem Aufruf. AC-3: zwei Threads mit künstlich verzögertem Abruf. AC-4: Fensterhilfsfunktion mit festen Uhrzeiten. AC-6: Fehler- bzw. Leer-Provider. AC-7: zwei Nutzer-IDs, Budget je Nutzer. AC-8: vorpräparierter Zählerstand.
- Test gegen den Ausgangszustand zuerst rot (zweite Vorschau erzeugt Abrufe), erst danach Implementierung.

Live-Nachweis im Validator (Staging, `/e2e-verify`): Punkt-für-Punkt-Vergleich der Zeitreihe und der Aggregate für mindestens einen Alpen-Ort und einen Korsika-Ort, einmal mit altem sekundengenauem Fenster, einmal mit angeglichenem Fenster (AC-4); anschließend zweite Vorschau desselben Vergleichs, die messbar ohne Anbieter-Abrufe bleibt (AC-1). Die Zusage gilt für den warmen Zweitaufruf, nicht für die kalte Erstvorschau.

## Changelog

- 2026-10-31: Initial spec created (Issue #2234, Variante 1: Segment-Weg + angeglichenes Fenster)
