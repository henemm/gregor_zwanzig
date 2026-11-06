# Context: fix-2581-demo-cache-vergiftung

## Request Summary
Die Demo-Vorschau (FixtureProvider) teilt sich den prozessweiten Wetter-Cache mit dem Live-Abruf. Fixture-Werte landen so in echten Briefings/Alarmen (und umgekehrt).

## Related Files
| File | Relevance |
|------|-----------|
| src/services/weather_cache.py:226 `_bucket_key` | Schluessel `{lat}_{lon}_{elev}_{model_id}_{ensemble}_{snow}`, kein Provider |
| src/services/segment_weather.py:419 `_resolve_model_id` | liefert `select_model()` des Providers, sonst `provider.name` |
| src/providers/fixture.py:79 `name` | gibt bewusst `"openmeteo"` zurueck ("transparent fuer Aufrufer") |
| src/providers/openmeteo.py:~581 `select_model` | Rueckfall-Modell ebenfalls `"openmeteo"` -> identisch mit Fixture-model_id |
| src/services/preview_service.py:186 | Demo -> `FixtureProvider`, laeuft ueber `scheduler._fetch_weather` / `fetch_night_weather` mit shared Cache |

## Ursache (belegt)
Fixture hat kein `select_model` -> `model_id = provider.name = "openmeteo"`. Live-OpenMeteo nutzt dieselbe Kennung, sobald kein Regionalmodell passt (Rueckfall `"openmeteo"`). Bei Fakes/Tests und im Rueckfall identischer Bucket -> Cache-Treffer ueber Provider-Grenze. Zusaetzlich teilen `flight_key` (Single-Flight) denselben Schluessel.

## Existing Patterns
- Cache-Schluessel wurde bereits zweimal um Dimensionen erweitert (#1329 model_id, #1991 Hoehe) mit Begruendung im Docstring.
- Tests injizieren `cache=` explizit; `reset_shared_weather_cache_for_tests()` in conftest.

## Loesungsrichtung (Empfehlung)
Fixture-Provider bekommt eine eigene Cache-Kennung (z. B. `_resolve_model_id` liefert fuer Provider mit Merkmal `is_fixture`/`cache_namespace` ein Praefix `fixture:`), `name` bleibt `"openmeteo"` (Aufrufer-Transparenz). Alternative: Demo mit eigener privater Cache-Instanz. Praefix im Schluessel ist kleiner und prueft sich per Kern-Test.

## Dependents
SegmentWeatherService wird von trip_alert, trip_report_scheduler, stage_weather, comparison_engine, compare_location_weather_source genutzt -> alle profitieren; Schluesselaenderung ist rein additiv (Cache leer nach Neustart).

## Existing Specs
Spec zu #1329 (Wetter-Cache) pruefen in Phase 2.

## Risks
- Kein Seiteneffekt auf `provider.name` (wird als `provider`-Feld in Daten ausgegeben).
- Test muss echtes Verhalten zeigen: zwei Fixture-Saetze, Reihenfolge demo->live und live->demo, ohne Cache-Leeren dazwischen.
- Nachtsegment (`fetch_night_weather`) und andere Wege mit Provider-Durchreichung mitpruefen.

## Analyse (Phase 2, 2026-11-06)

### Verifizierte Ursache
`segment_weather.py::_resolve_model_id` faellt ohne `select_model()` auf `provider.name` zurueck. `FixtureProvider.name` ist bewusst `"openmeteo"`. Damit ist `model_id` von Demo und Live-Rueckfall identisch; `_bucket_key` und `flight_key` enthalten keinen Provider -> Cache-Treffer und Single-Flight ueber die Provider-Grenze.

### Zweiter Vergiftungsweg (neu, nicht im Issue)
`segment_weather.py:~400` ruft `capture_segment_forecast(provider=self._provider.name, model=...)`. Im Demo-Modus werden Fixture-Werte als `provider="openmeteo"` ins Prognose-Archiv geschrieben (Kill-Switch `GZ_FORECAST_CAPTURE` ist standardmaessig AN). Gleiche Wurzel (Fixture tarnt sich als openmeteo), anderer Ausgang. Ein reiner Cache-Schluessel-Fix schliesst ihn NICHT.

### Optionen
| | A: Kennung `fixture:` im model_id | B: Demo mit eigener Cache-Instanz | C: A + Capture fuer Fixture aussetzen |
|---|---|---|---|
| Cache-Vergiftung | geloest | geloest | geloest |
| Archiv-Vergiftung | offen | offen | geloest |
| Eingriff | 1 Stelle (`_resolve_model_id`) + Provider-Merkmal | Preview-Service + Durchreichung an `_fetch_weather`/`fetch_night_weather` | A + 1 Guard in Capture-Aufruf |

### Empfehlung: C
Provider-Merkmal `cache_namespace` (FixtureProvider: `"fixture"`, andere: fehlt). `_resolve_model_id` stellt es voran (`fixture:openmeteo`); `provider.name` bleibt `"openmeteo"`. Capture wird fuer Provider mit `cache_namespace` uebersprungen. Kein Test-Fake betroffen (Merkmal per `getattr`, Standard None).

Nebenwirkung im Offline-Testmodus (`GZ_TEST_FIXTURE_DIR`, `get_provider`): dort liefert der Prod-Pfad ebenfalls den FixtureProvider -> Cache-Schluessel aendert sich nur dort, konsistent innerhalb eines Satzes; kein Verhaltensverlust.

### Nicht betroffen / ausserhalb
- `radar_cache` und `thunder_window_cache` haben eigene Schluessel; Demo nutzt dort keinen Fixture-Weg (Preview ruft nur `_fetch_weather`/`fetch_night_weather`) -> nicht Teil dieses Fixes, in Spec als geprueft vermerken.

### Testplan (Nutzersicht, Kern-Schicht, offline)
1. Zwei Fixture-Verzeichnisse (2 C / 22 C), Reihenfolge demo->live und live->demo OHNE Cache-Leeren: jeder Abruf liefert den eigenen Wert (RED heute).
2. Demo-Abruf schreibt keine Zeile ins Prognose-Archiv (RED heute).
3. Zwei verschiedene Nutzer (Pflicht fuer datenbewegende Pfade): Bucket bleibt nutzerunabhaengig geteilt, aber Fixture getrennt.
4. Nachtsegment (`fetch_night_weather` mit provider=Fixture) nutzt den Fixture-Namensraum.

### Offene Punkte fuer die Spec
Spec `weather_cache.md` (#1329) um AC fuer Provider-Namensraum ergaenzen; Docstring `_bucket_key` / `_resolve_model_id` mit Begruendung wie bei #1329/#1991.
