# Context: M5c Weather Config + Compare

## Request Summary
Go-Endpoints für Weather Config (GET/PUT pro Trip, Location, Subscription) und Compare (Standort-Vergleich mit Scoring). Issue #39.

## Scope-Analyse

### Weather Config Endpoints
`display_config` ist bereits als `map[string]interface{}` in Trip, Location und Subscription gespeichert. Die Endpoints sind **reine JSON-Reads/Writes auf ein Subfeld** — kein neues Model nötig.

| Endpoint | Logik |
|----------|-------|
| `GET /api/trips/{id}/weather-config` | Trip laden → `display_config` zurückgeben |
| `PUT /api/trips/{id}/weather-config` | Trip laden → `display_config` ersetzen → speichern |
| `GET /api/locations/{id}/weather-config` | Location laden → `display_config` zurückgeben |
| `PUT /api/locations/{id}/weather-config` | Location laden → `display_config` ersetzen → speichern |
| `GET /api/subscriptions/{id}/weather-config` | Subscription laden → `display_config` zurückgeben |
| `PUT /api/subscriptions/{id}/weather-config` | Subscription laden → `display_config` ersetzen → speichern |

### Compare Endpoint
`GET /api/compare?locations=id1,id2,...` ist **komplex** — braucht Forecast-Fetching + Scoring-Algorithmus. Das ist zu viel für ein einzelnes Feature (~300+ LOC Scoring allein).

**Empfehlung: M5c nur Weather Config, Compare als separates Issue.**

## Betroffene Dateien (nur Weather Config)

| Datei | Änderung |
|-------|----------|
| `internal/handler/weather_config.go` | **NEU** — 6 Handler (GET/PUT × Trip/Location/Subscription) |
| `cmd/server/main.go` | +6 Zeilen Route-Registrierung |

Kein neues Model nötig — `display_config` ist bereits `map[string]interface{}` in allen drei Entities.

## Bestehendes Pattern

`display_config` wird schon via Trip/Location/Subscription CRUD gelesen und geschrieben (als Teil des gesamten Objekts). Die neuen Endpoints sind ein **Convenience-Layer**: gezielter Zugriff auf nur das Config-Subfeld.

## Python-Referenz

| Datei | Funktion |
|-------|----------|
| `src/app/models.py:443-480` | UnifiedWeatherDisplayConfig, MetricConfig |
| `src/app/metric_catalog.py` | 23 verfügbare Metriken |
| `src/web/pages/weather_config.py` | Config-Dialoge (Trip/Location/Subscription) |

## Go-Referenz

| Datei | Relevanz |
|-------|----------|
| `internal/model/trip.go` | Trip.DisplayConfig (map[string]interface{}) |
| `internal/model/location.go` | Location.DisplayConfig (map[string]interface{}) |
| `internal/model/subscription.go` | CompareSubscription.DisplayConfig (map[string]interface{}) |
| `internal/store/store.go` | Load/Save für alle drei Entities |
| `internal/handler/trip.go` | UpdateTripHandler als Pattern |

## Risiken
- Keine — reine CRUD-Operationen auf bestehendes Subfeld
- display_config wird als opaque JSON behandelt (kein Typ-Check in Go)
