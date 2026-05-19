# Context: Compare #250 — Compare-Engine (Backend)

## Request Summary

Neuer Go-nativer Endpoint `POST /api/compare/run`, der Wetterdaten für N Locations parallel abruft, sie nach Aktivitätsprofil bewertet und ein sortiertes Ranking zurückgibt. Ersetzt/ergänzt den bestehenden sequenziellen Python-Proxy (`GET /api/compare`).

## Schlüsselbefund: Was existiert bereits

| Was | Wo | Relevanz |
|-----|----|----------|
| Python `ComparisonEngine` | `src/services/comparison_engine.py` | Sequenziell (kein Goroutine), GET-Endpoint, anderes Response-Format |
| Python Scoring | `src/services/comparison_scoring.py` | Profile: wintersport/wandern/allgemein, additive Punkte, kein config-driven |
| Go `GET /api/compare` | `cmd/server/main.go:107` | Proxy auf Python, bleibt unverändert |
| Go `OpenMeteoProvider.FetchForecast()` | `internal/provider/openmeteo/provider.go` | Fertig, nutzt goroutines intern für Fallback |
| Go `aggregateForecasts()` | `internal/handler/stage_weather.go` | Aggregiert ForecastDataPoints für einen Tag/Zeitfenster |
| Go `risk.Assess()` | `internal/risk/engine.go` | Segment-Risk-Level (nicht Score 0–100) |
| `model.SegmentWeatherSummary` | `internal/model/segment.go` | DTOs für aggregierte Metriken |
| `store.LoadLocations()` / `LoadLocation()` | `internal/store/store.go:38,185` | Lädt Locations aus JSON-Files |

## Was Issue #250 NEU fordert

- **Endpoint:** `POST /api/compare/run` (nicht GET wie Python)
- **Go-nativ:** Keine Python-Delegation, direkt `OpenMeteoProvider` nutzen
- **Goroutines:** N Locations parallel, nicht sequenziell
- **15-Min-Cache:** In-Memory pro `location_id × date × profile`
- **4 Profile:** `WINTERSPORT`, `ALPINE_TOURING`, `SUMMER_TREKKING`, `ALLGEMEIN` (Uppercase-Enum)
- **Scoring config-getrieben:** Gewichtungen in Config/Konstanten, nicht hardkodiert
- **Response-Format NEU:**
  ```json
  {
    "rows": [{"location_id": "...", "score": 78, "rank": 1, "metrics": {...}}],
    "winner": {"location_id": "...", "tags": [...]},
    "hourly": {"loc-1": [...]}   // Top-3 stündliche Werte
  }
  ```

## Scoring-Gewichtungen (aus Issue)

| Profil | Gewichtung |
|--------|-----------|
| WINTERSPORT | Schnee cm (30%), Neuschnee (25%), Sonne h (20%), Wind/Böen (15%), Wolkenlage (10%) |
| ALPINE_TOURING | Lawinenstufe (35%), Neuschnee (25%), Sicht (20%), Wind (20%) |
| SUMMER_TREKKING | Regen (30%), Gewitter% (25%), Wind (20%), UV (15%), Sicht (10%) |
| ALLGEMEIN | Temp (25%), Wind (25%), Regen (25%), Sicht (25%) |

**Normalisierung:** Bester Wert pro Metrik = 100% (relativ, nicht absolut)

## Related Files

| File | Relevanz |
|------|----------|
| `internal/handler/stage_weather.go` | `aggregateForecasts()` wiederverwenden oder adaptieren |
| `internal/provider/openmeteo/provider.go` | `FetchForecast(lat, lon, hours)` direkt nutzen |
| `internal/model/segment.go` | `SegmentWeatherSummary` als Metriken-Basis |
| `internal/model/forecast.go` | `ForecastDataPoint`, `Timeseries` |
| `internal/store/store.go` | `LoadLocations()`, `LoadLocation()` |
| `internal/model/location.go` | `Location`-Struct mit Lat/Lon/ElevationM |
| `cmd/server/main.go` | Route registrieren: `r.Post("/api/compare/run", ...)` |
| `src/services/comparison_scoring.py` | Referenz für Scoring-Logik (Python, für Portierung) |
| `src/services/comparison_engine.py` | Referenz für Metrics-Aggregation (Python) |

## Neue Files (zu erstellen)

| File | Inhalt |
|------|--------|
| `internal/compare/engine.go` | Core: Parallelabfrage + Aggregation + Scoring + Cache |
| `internal/compare/scoring.go` | Profil-gewichtetes Scoring (config-getrieben) |
| `internal/handler/compare.go` | HTTP-Handler für POST /api/compare/run |
| `internal/compare/engine_test.go` | Tests (keine Mocks, echte API-Calls) |

## Dependencies

- **Upstream:** `OpenMeteoProvider.FetchForecast()` → braucht Lat/Lon → aus `store.LoadLocation()`
- **Downstream:** Frontend Compare-Screen (Issue #249 oder Sub-Issue 5 von #246) konsumiert diesen Endpoint

## Bestehende Patterns

1. **Parallel mit WaitGroup + Mutex:** `StagesWeatherHandler` (stage_weather.go:26-45) macht genau das — goroutines pro Stage, WaitGroup, Mutex für results-Map
2. **Provider nutzen:** `FetchForecast(lat, lon, hours)` gibt `*model.Timeseries` zurück
3. **Aggregation:** `aggregateForecasts(points, date)` filtert nach Datum, aggregiert Metriken
4. **In-Memory-Cache:** `internal/provider/openmeteo/cache.go` zeigt Cache-Pattern (File-basiert), neuer Cache muss aber In-Memory (15 Min) sein

## Risiken

1. **Lawinenstufe für ALPINE_TOURING:** Kein Feld in `ForecastDataPoint` — muss als Placeholder (0) oder über externe Quelle (nicht in Scope) behandelt werden
2. **Normalisierter Score:** Relativer Ansatz (bester Wert = 100%) bedeutet, der Winner hat immer Score 100 für jede Metrik — bei gleichem Wetter aller Locations ggf. irreführend. Alternativ: absolute Schwellenwerte wie Python-Scorer.
3. **`hourly` nur Top-3:** Muss Ranking bereits feststehen bevor hourly gebaut wird → zweistufiger Ablauf
4. **Cache-Key:** `location_id × date × profile` — Location-IDs müssen normiert sein (lowercase, keine Spaces)
5. **Auth-Kontext:** Handler läuft mit Auth-Middleware, `WithUser()` nötig für Store-Zugriff

## Existing Specs

- `docs/specs/modules/compare_247_location_model.md` — Location-Struct-Erweiterung (Voraussetzung abgeschlossen)
- `docs/specs/epic_129a_1_compare_helpers.md` — Python ComparisonEngine Spec
