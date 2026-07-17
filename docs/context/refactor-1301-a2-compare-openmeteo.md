# Context: A2 — Vergleich auf gemeinsamen Wetter-Weg (Epic #1301)

## Request Summary
`_select_provider_for_location` (`comparison_engine.py:307-323`) entfällt; der
Ortsvergleich holt Wetter überall über `get_provider("openmeteo")`. Damit erben
Alpen-Orte die in A1 befreite Nachfüll-Mechanik (Metric-Gap-Fill WEATHER-05b,
Modell-Fallback #1115, Cross-Provider-Ausweiche #1141): pop/uv/visibility/cape/
freezing_level werden gefüllt, das 60-h-Dach von AROME entfällt.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/comparison_engine.py:307-323` | `_select_provider_for_location` — zu entfernen |
| `src/services/comparison_engine.py:343` | Aufruf 1 (`fetch_forecast_for_location` → `ForecastService`) |
| `src/services/compare_location_weather_source.py:32-34` | Aufruf 2 (Alert-Pfad → `SegmentWeatherService`) |
| `src/providers/base.py:120-156` | `get_provider("openmeteo")` — der gemeinsame Weg |
| `src/services/comparison_engine.py:432-448` | Snow-Werte aus forecast.data (heute SNOWGRID via GeoSphere) → A3-relevant |
| `tests/tdd/test_compare_provider_routing.py` | Testet die zu entfernende Funktion direkt (Marker `live`) — muss umgebaut/entfernt |

## Existing Patterns
- **Provider-Factory:** `get_provider("openmeteo")` ist der etablierte Weg; A1 hat
  die Merge-/Gap-Fill-Mechanik bereits so aufgestellt, dass sie über
  `OpenMeteoProvider.fetch_forecast` läuft. Trip fährt bereits überall openmeteo.
- **Offline-Test-Modus:** `get_provider` liefert bei `GZ_TEST_FIXTURE_DIR` +
  `name=="openmeteo"` einen `FixtureProvider` (`base.py:141-144`) — Kern-Tests
  können netzfrei aufgezeichnete Daten fahren.

## Dependencies
- Upstream (was A2 nutzt): `get_provider`, `ForecastService`, `SegmentWeatherService`,
  `OpenMeteoProvider.fetch_forecast` (inkl. der in A1 befreiten `merge_missing_fields`).
- Downstream (was A2 nutzt/verändert): der Compare-Report-Renderpfad und der
  15-Min-Alert-Check konsumieren die Ergebnisse; Metrik-Extraktion in
  `fetch_forecast_for_location:370-449` liest openmeteo-Felder direkt.

## Existing Specs
- `docs/specs/modules/model_metric_fallback.md` — WEATHER-05b Gap-Fill (A1-Grundlage)
- `docs/specs/bugfix/compare_provider_routing.md` — Spec der jetzt entfallenden Routing-Funktion
- `docs/specs/modules/issue_1169_compare_alert_consumer.md` — Alert-Consumer (Aufruf 2)

## Risks & Considerations
- **Snow-Regression bis A3:** Nach A2 kommen Alpen-Orte über openmeteo; die heutige
  GeoSphere-SNOWGRID-Schneeschicht fällt weg, bis A3 sie als Ergänzung zurückholt.
  Kein aktiver Prod-User; Scheiben-Sequenz A2→A3 vom PO freigegeben.
- **Test-Reichweite:** `test_compare_provider_routing.py` und Docstring-Referenzen
  in `test_issue_1150/1106/1107` prüfen — asserten sie Alps→GeoSphere, brechen sie.
- **Gap-Fill wirklich geerbt?** Analyse muss bestätigen, dass
  `ForecastService(get_provider("openmeteo")).get_forecast(...)` durch
  `OpenMeteoProvider.fetch_forecast` läuft und die Gap-Fill-Mechanik greift.
- **Horizont vs. angeforderte Stunden:** openmeteo hebt das 60-h-Dach auf; die real
  angeforderten `hours` bleiben bis A4 bei 48. A2-Nutzen = Metriken gefüllt + Dach weg.
- **`GeoSphereProvider`-Import** in comparison_engine wird nach Entfernen ggf. ungenutzt.

## Analysis

### Type
Refactor (Verhaltenswandel im Compare-Datenpfad — Feature-Track).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/comparison_engine.py` | MODIFY | `_select_provider_for_location` (307-323) entfernen; Aufruf :343 → `get_provider("openmeteo")`; ungenutzten `GeoSphereProvider`-Import (19) entfernen |
| `src/services/compare_location_weather_source.py` | MODIFY | Aufruf :32-34 → `get_provider("openmeteo")`; Docstring-Hinweis auf `_select_provider_for_location` (11-12) korrigieren |
| `tests/tdd/test_compare_provider_routing.py` | MODIFY | Routing-Klasse entfällt; Tests auf „überall openmeteo" umschreiben (kein GeoSphere-Assert mehr) |
| `tests/tdd/test_a2_compare_openmeteo_metrics.py` | CREATE | Kern-Test (netzfrei, openmeteo-Fixture): Alpen-Ort bekommt pop/uv/visibility/cape/freezing_level gefüllt — RED vor, GREEN nach A2 |

### Scope Assessment
- Files: 4 (2 src, 2 test)
- Estimated LoC: Quelle klein (~ -20 netto in comparison_engine + 2 Zeilen Aufrufer); Tests +~60/-~90. Voraussichtlich **unter 250** — Plan-Warnung war konservativ. Wird überwacht.
- Risk Level: MEDIUM (kritischer Compare-Datenpfad, aber Kern-Suite unberührt, Mechanik durch A1 vorbereitet).

### Technical Approach
Beide Aufrufer holen den Provider künftig über `get_provider("openmeteo")`. Da die
komplette Gap-Fill-/Fallback-Mechanik in `OpenMeteoProvider.fetch_forecast` gekapselt
ist (belegt: `openmeteo.py:954-995` metric_gap, `:833-869` Modell-Fallback,
`:871-893` Cross-Provider), erben beide Pfade sie automatisch. Kein neuer Code in den
Services. Nachweis über den Offline-Fixture-Modus (`base.py:141-144`): unter
`GZ_TEST_FIXTURE_DIR` liefert `get_provider("openmeteo")` einen `FixtureProvider` —
vor A2 umging der Alpen-Zweig diesen (direkte `GeoSphereProvider()`-Instanz), nach A2
nicht mehr. Genau darauf baut der Bug-Repro-Test.

### Dependencies
- Konsumenten: `ComparisonEngine.run()` (`comparison_engine.py:74`), Alert-Pfad
  (`compare_alert.py:73`, `scheduler_dispatch_service.py:444/447`). Kein Konsument
  prüft in der Kern-Suite GeoSphere-Schnee.

### Open Questions
- [x] Gap-Fill vererbt? → JA (beide Services rufen `fetch_forecast`).
- [x] Alle fünf Metriken von openmeteo? → JA.
- [x] Snow nach A2? → fällt ersatzlos weg, ist A3-Grenze (Known Limitation).
- [ ] **Known Limitation für Freigabe:** Alpen-Orte verlieren mit A2 die
  SNOWGRID-Schneewerte (snow_depth/swe/snowfall_limit) bis A3 sie ergänzt. Horizont:
  A2 hebt das 60-h-Dach auf, real angeforderte Stunden bleiben bis A4 bei 48.
