# Context: fix-1329-forecast-cache-budget (Issue #1329, Scheibe C+)

## Request Summary
Produktion erschöpft das open-meteo-Tageskontingent (10.000/Tag, Free-Tier auf Server-IP); am 2026-07-20 304× HTTP 429 in Prod. PO-Kritik: „Dass Staging/Tests den Produktivbetrieb stören, kann nicht richtig sein." Diese Scheibe baut den geteilten Forecast-Cache + Verbrauchssteuerung (Punkt 1+2 der Architektur-Einordnung auf #1329). Go-seitiges Scheduler-Env-Gate (A) und Testdaten-Hygiene (B) liegen bei der Sitzung, die #1329 führt.

## KORREKTUR gegenüber der ersten Einordnung (wichtig)
Die Annahme „Alert- und Radar-Job holen denselben Ort im selben Zyklus doppelt über dieselbe API" ist **so nicht haltbar**. Belegt:
- Alert-Pfade rufen `provider.fetch_forecast()` (open-meteo **stündlich**): `trip_alert.py:801-838` (`_fetch_fresh_weather`), `compare_location_weather_source.py:32-53`.
- Radar-Pfade rufen `RadarNowcastService.get_nowcast(lat, lon)` (`radar_service.py:79`), das je nach Region auf BrightSky/RADOLAN, GeoSphere INCA, RadarDPC, AROME-FR-HD **oder** open-meteo `minutely_15` geht (`radar_service.py:201-330`). Kein gemeinsamer Code-Pfad mit `fetch_forecast`.
→ Radar belastet das open-meteo-Kontingent nur im Fallback-Fall. Ein gemeinsamer Cache-Eintrag kann beide Pfade **nicht** bedienen (andere Auflösung, andere Endpunkte) — es braucht getrennte Namensräume.

## Root Cause (verifiziert)

1. **Der vorhandene Cache cached nichts.** `WeatherCacheService` (`services/weather_cache.py:29-181`, thread-safe, TTL 3600 s, LRU 100, Key `f"{segment_id}_{start_iso}_{end_iso}"` `:149-162`) ist **per-Instanz**. Jeder Aufrufer baut pro Aufruf einen NEUEN `SegmentWeatherService` (`segment_weather.py:60-64`, `cache=None` → frischer Cache): `trip_alert.py:801`, `compare_location_weather_source.py:32`. `trip_alert.py:833` ruft zusätzlich explizit `service._cache.clear()`. Ergebnis: null Wiederverwendung über Trips, Orte, Nutzer und Zyklen hinweg.
2. **Kein prozessweiter/persistenter Forecast-Cache.** `openmeteo.py:192` cached nur **Modell-Verfügbarkeit** (`data/cache/model_availability.json`, TTL 7 Tage) — keine Wetterdaten.
3. **Kein Verbrauchsbegriff.** Nirgends ein Zähler/Budget/Prioritätsbegriff; Erschöpfung zeigt sich erst als 429 mitten im Nutzer-Versand.
4. **Cache-Schlüssel-Vorbedingung günstig:** Beide Alert-Aufrufer normalisieren identisch auf `enrich_ensemble=False, enrich_snow=False` (`trip_alert.py:836-837`, `compare_location_weather_source.py:51-52`) — gleiche Koordinate + gleiche Stunde ⇒ identische Upstream-Anfrage, also teilbar.

## Related Files
| File | Relevance |
|---|---|
| `src/services/weather_cache.py:29-181` | Vorhandener, funktionsfähiger Cache — muss geteilt statt pro Instanz verwendet werden |
| `src/services/segment_weather.py:60-64,140-146` | Konstruiert Default-Cache; einzige Stelle, die `fetch_forecast` für Alert-Pfade ruft |
| `src/services/trip_alert.py:801-838` | Trip-Alert-Fetch; `:833` `_cache.clear()` — Cache-Killer |
| `src/services/compare_location_weather_source.py:32-53` | Compare-Alert-Fetch, synthetisches 1-Punkt-Segment `now..now+1h` |
| `src/services/forecast.py:85` | `get_forecast` — Briefing/Preview-Pfad (Priorität „Nutzer") |
| `src/services/comparison_engine.py:39,81,327-345` | Compare-Report, `COMPARE_FORECAST_HOURS=96` |
| `src/providers/base.py:41-48,123-159` | Protokoll `fetch_forecast(location, start, end, enrich_ensemble, enrich_snow)`, Fabrik `get_provider` |
| `src/providers/openmeteo.py:192-330` | Muster für datei-basierten Cache (fail-soft, TTL, kein Lock) |
| `src/services/throttle_store.py:33-73` | Muster für datei-basierten Zustand pro Nutzer (Read-Modify-Write) |
| `api/routers/scheduler.py:47-83` | Die vier Job-Endpunkte |
| `internal/scheduler/scheduler.go:110-118,148ff` | Go-Cron `*/15`, ein HTTP-POST pro Nutzer und Job |

## Prozess-Topologie (entscheidend für die Cache-Bauform)
Alle vier Jobs landen im selben uvicorn-Prozess (`gregor-python`, Prod `127.0.0.1:8000`, Staging `:8001`); kein `--workers` im Repo ⇒ Single-Worker. Ein **prozessweiter In-Memory-Cache genügt** für die Zyklus-Teilung; er überlebt keinen Deploy-Neustart (akzeptabel bei kurzem TTL). Prod/Staging sind durch getrennte Prozesse und Arbeitsverzeichnisse automatisch isoliert.

## Existing Patterns
- Fail-soft-Cache mit TTL: `openmeteo.py:258-274` (None bei fehlend/abgelaufen/kaputt, kein Crash).
- Thread-Sicherheit: `weather_cache.py` nutzt `threading.Lock` — beibehalten, da gleichzeitige Job-Requests in denselben Prozess laufen können.
- Datei-Zustand pro Nutzer: `ThrottleStore` — Vorbild, falls das Budget prozessübergreifend/neustartfest sein soll.

## Dependencies / Dependents
- Upstream: `get_provider("openmeteo")`, `NormalizedTimeseries`.
- Downstream: Trip-Alerts, Compare-Alerts, Briefings/Previews, Compare-Reports — **nutzersichtbarer kritischer Pfad**.

## Risks & Considerations
- **Höchstes Risiko: veraltete Daten in Alarmen.** Alert-Zyklus ist 15 Min; TTL muss kürzer als der Nutzen-Horizont sein (Vorschlag: ~10-14 Min, jedenfalls < 15). Ein zu langer TTL macht Alarme blind für frische Entwicklung — genau das Gegenteil des Produktzwecks.
- `trip_alert.py:833` `_cache.clear()` existiert vermutlich bewusst („frische Daten für Alarm"). Entfernen ist eine **Verhaltensänderung**, die begründet und getestet werden muss (Alarm-Frische vs. Kontingent).
- Cache-Schlüssel muss Modellwahl mit abdecken (wird intern aus lat/lon abgeleitet, nicht übergeben) — sonst liefert der Cache Daten des falschen Modells.
- Budget-/Prioritätssteuerung darf **niemals** ein Nutzer-Briefing verwerfen; sie drosselt Polling. Fail-open bei Zähler-Defekt (ein kaputter Zähler darf nicht den Versand blockieren).
- Kein Mock-Theater: Cache-Verhalten ist deterministisch testbar (zwei Aufrufe, ein Upstream-Call — über einen zählenden Fake-Provider, kein `patch()` auf die eigene Annahme).
- Messbarkeit ist Teil der Lieferung: ohne Zähler im Status-Endpunkt bleibt der Erfolg Behauptung (#1329 verlangt genau das).
