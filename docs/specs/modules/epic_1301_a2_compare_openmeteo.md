---
entity_id: epic_1301_a2_compare_openmeteo
type: module
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [compare, provider, refactor, epic-1301]
---

# A2 — Ortsvergleich auf den gemeinsamen Wetter-Weg (openmeteo)

## Approval

- [x] Approved (PO 2026-07-17)

## Purpose

Der Ortsvergleich holt Wetterdaten künftig überall über `get_provider("openmeteo")`
statt über die standort-basierte Provider-Auswahl `_select_provider_for_location`
(die für Alpen-Orte direkt einen `GeoSphereProvider` erzeugte). Dadurch erben
Alpen-Orte die in A1 befreite Nachfüll-Mechanik: Metric-Gap-Fill (WEATHER-05b),
Modell-Fallback (#1115) und Cross-Provider-Ausweiche (#1141). Die bei Alpen-Orten
heute dauerhaft leeren Metriken pop, uv, visibility, cape und freezing_level werden
gefüllt; das 60-h-Horizont-Dach von AROME entfällt.

## Source

- **File:** `src/services/comparison_engine.py`
- **Identifier:** `_select_provider_for_location` (entfällt), `fetch_forecast_for_location`
- **File:** `src/services/compare_location_weather_source.py`
- **Identifier:** `CompareLocationWeatherSource.fetch`

Python-Core / Domain-Backend (`src/services/`, `src/providers/`).

## Estimated Scope

- **LoC:** ~120 (Quelle netto ~ -20; Tests ~ +60 / -90) — voraussichtlich unter 250
- **Files:** 4 (2 Quelle, 2 Test)
- **Effort:** low–medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `get_provider("openmeteo")` (`providers/base.py:120`) | uses | Der gemeinsame Provider-Weg; liefert unter `GZ_TEST_FIXTURE_DIR` den `FixtureProvider` |
| `OpenMeteoProvider.fetch_forecast` (`openmeteo.py:741`) | uses | Kapselt Gap-Fill + Modell-Fallback + Cross-Provider-Ausweiche — wird geerbt |
| `ForecastService` / `SegmentWeatherService` | uses | Rufen `provider.fetch_forecast`; unverändert |
| `ComparisonEngine.run` (`comparison_engine.py:74`), `compare_alert.py:73`, `scheduler_dispatch_service.py:444` | dependents | Konsumenten des Compare-Wetterpfads |

## Implementation Details

```
1. comparison_engine.py:
   - _select_provider_for_location (307-323) ersatzlos entfernen.
   - :343  provider = _select_provider_for_location(loc.lat, loc.lon)
        →  provider = get_provider("openmeteo")
        (get_provider ist bereits importiert bzw. lokal importieren wie bisher)
   - :19   ungenutzten Import `from providers.geosphere import GeoSphereProvider` entfernen.

2. compare_location_weather_source.py:
   - :32-34  from services.comparison_engine import _select_provider_for_location
             provider = _select_provider_for_location(lat, lon)
          →  from providers.base import get_provider
             provider = get_provider("openmeteo")
   - Modul-Docstring (:11-12) auf „holt über get_provider('openmeteo')" korrigieren.

3. Tests:
   - test_compare_provider_routing.py: Routing-Assertions (GeoSphere für Alpen) entfallen;
     Datei spiegelt „überall openmeteo" wider (Alpen- und Nicht-Alpen-Ort liefern Daten
     über denselben Weg). Bleibt live-markiert, soweit echte API-Calls nötig.
   - NEU test_a2_compare_openmeteo_metrics.py (Kern, netzfrei): unter GZ_TEST_FIXTURE_DIR
     mit einer openmeteo-Fixture, die pop/uv/visibility/cape/freezing_level enthält, führt
     fetch_forecast_for_location für einen Alpen-Ort (47.3, 11.4) zu gefüllten Werten
     dieser fünf Metriken. Vor A2 rot (Alpen-Zweig instanziiert GeoSphere direkt, umgeht
     die Fixture), nach A2 grün.
```

## Expected Behavior

- **Input:** `SavedLocation` mit beliebigen Koordinaten (Alpen wie außeralpin).
- **Output:** `fetch_forecast_for_location` / `CompareLocationWeatherSource.fetch`
  liefern Werte über `OpenMeteoProvider` inkl. Gap-Fill-gefüllter Metriken
  pop/uv/visibility/cape/freezing_level — auch für Alpen-Orte.
- **Side effects:** Keine neuen. Kein GeoSphere-Direktabruf mehr im Compare-Pfad.

## Known Limitations (Teil der Freigabe)

1. **Schneewerte fallen für Alpen-Orte weg.** openmeteo liefert keine SNOWGRID-Werte
   (`snow_depth_cm`, `swe_kgm2`, `snowfall_limit_m` sind hart `None`). Bis **A3** diese
   als GeoSphere-Ergänzung über die A1-Merge-Funktion zurückholt, zeigen Alpen-Orte
   keine SNOWGRID-Schneewerte. Bergfex-Schnee (`bergfex_slug`) bleibt unberührt.
   Akzeptiert: kein aktiver Prod-User, Scheiben-Sequenz A2→A3 PO-freigegeben.
2. **Horizont:** A2 hebt das 60-h-Dach auf (openmeteo reicht ~15 Tage), aber die real
   angeforderten `hours` bleiben bis **A4** bei 48. A2 schaltet die Fähigkeit frei,
   nicht die tatsächlich längere Vorschau.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit einem Alpen-Ort (lat 47.3, lon 11.4) / When das
  Wetter über `fetch_forecast_for_location` geholt wird und `GZ_TEST_FIXTURE_DIR` auf
  eine openmeteo-Fixture mit pop/uv/visibility/cape/freezing_level zeigt / Then enthält
  das Ergebnis gefüllte Werte für diese fünf Metriken (nicht `None`).
  - Test: `test_a2_compare_openmeteo_metrics.py` — Kern, netzfrei; rot vor Fix
    (Alpen-Zweig umging die Fixture via direktem `GeoSphereProvider`), grün nach Fix.

- **AC-2:** Given der Compare-Wetterpfad / When `fetch_forecast_for_location` und
  `CompareLocationWeatherSource.fetch` aufgerufen werden / Then holen **beide** den
  Provider ausschließlich über `get_provider("openmeteo")`; die Funktion
  `_select_provider_for_location` existiert nicht mehr und kein Code instanziiert im
  Compare-Pfad direkt `GeoSphereProvider`.
  - Test: `_select_provider_for_location` ist nicht mehr importierbar; ein Aufruf des
    Compare-Pfads für Alpen-Koordinaten läuft über den openmeteo-Weg (Fixture greift).

- **AC-3:** Given der außeralpine Ort (z. B. Mallorca 39.7, 2.6) im selben Vergleich /
  When das Wetter geholt wird / Then bleibt sein Verhalten unverändert (Daten über
  openmeteo, kein Fehler) — keine Regression für Nicht-Alpen-Orte.
  - Test: bestehender/angepasster Nicht-Alpen-Fall in `test_compare_provider_routing.py`
    liefert Daten ohne Fehler.

- **AC-4:** Given die bestehende Kern-Testsuite / When sie nach dem Refactor läuft /
  Then bleibt sie grün; kein Kern-Test bricht durch das Entfernen der Funktion (nur die
  `live`-markierte Routing-Datei wurde inhaltlich auf „überall openmeteo" angepasst).
  - Test: `uv run pytest` (Kern, ohne `live`/`email`) grün.

## Regression Protection

- WEATHER-05b-Gap-Fill-Tests (`test_model_metric_fallback.py`) bleiben unverändert grün
  — A2 fasst den Trip-Pfad nicht an.
- Nicht-Alpen-Orte verhalten sich unverändert (AC-3).

## Out of Scope

- Schnee-Rückführung vom Landesdienst (→ A3).
- Anheben von `forecast_hours` (→ A4).
- Renderer-/Matrix-Änderungen (→ B).
