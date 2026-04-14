---
entity_id: weather_config_endpoints
type: module
created: 2026-04-14
updated: 2026-04-14
status: implemented
version: "1.0"
tags: [go, rest-api, chi, weather-config, trip, location, subscription, json-store]
---

# Weather Config Endpoints

## Approval

- [x] Approved

## Purpose

Go HTTP-Handler-Modul, das sechs REST-Endpoints bereitstellt, um das `display_config`-Subfeld gezielt auf Trip-, Location- und Subscription-Entitaeten zu lesen und zu ersetzen. Es ist ein Convenience-Layer ueber die bestehenden CRUD-Handler — statt immer das gesamte Objekt zu uebertragen reicht der Client nur die Anzeigeoptionen ein.

## Scope

### In Scope
- Sechs HTTP-Handler in `internal/handler/weather_config.go`: GET/PUT fuer Trip, Location, Subscription
- Route-Registrierung (6 Zeilen) in `cmd/server/main.go`
- Load→Read/Modify→Save-Pattern analog zu bestehenden CRUD-Handlern
- Fehlerbehandlung: 404 bei nicht gefundenem Parent, 400 bei ungueltiger JSON-Body

### Out of Scope
- Schema-Validierung von `display_config`-Inhalten (wird als opaque JSON round-getrippt)
- Neues Data Model (kein neues Struct notwendig)
- Authentifizierung / Multi-User-Isolation (V1: nur `userID = "default"`)
- Concurrent-Write-Protection (kein File-Locking in V1)

## Architecture

```
SvelteKit
    │
    ├── GET  /api/trips/{id}/weather-config
    ├── PUT  /api/trips/{id}/weather-config
    ├── GET  /api/locations/{id}/weather-config
    ├── PUT  /api/locations/{id}/weather-config
    ├── GET  /api/subscriptions/{id}/weather-config
    └── PUT  /api/subscriptions/{id}/weather-config
            │
            ▼
    Go Handler (:8090)
    internal/handler/weather_config.go
            │  Load → Read/Modify DisplayConfig → Save
            ▼
    internal/store/store.go
    LoadTrip/SaveTrip
    LoadLocation/SaveLocation
    LoadSubscriptions/SaveSubscriptions
            │
            ▼
    data/users/default/{trips,locations,compare_subscriptions}.json
```

## Source

- **File:** `internal/handler/weather_config.go` **(NEU)**
- **Identifier:** `GetTripWeatherConfig`, `PutTripWeatherConfig`, `GetLocationWeatherConfig`, `PutLocationWeatherConfig`, `GetSubscriptionWeatherConfig`, `PutSubscriptionWeatherConfig`

### Weitere betroffene Dateien
- **Routing:** `cmd/server/main.go` **(ERWEITERT)** — 6 Route-Registrierungen

## Endpoints

### GET /api/trips/{id}/weather-config

**Response 200 (config vorhanden):**
```json
{"show_precipitation": true, "show_wind": false}
```

**Response 200 (config nicht gesetzt):**
```json
null
```

**Response 404:**
```json
{"error": "not_found"}
```

---

### PUT /api/trips/{id}/weather-config

**Request Body:** Beliebiges gueltiges JSON-Objekt (opaque, kein Schema).
```json
{"show_precipitation": true, "show_wind": false}
```

**Response 200:** Gespeichertes `display_config` als JSON-Objekt.

**Response 400:**
```json
{"error": "bad_request"}
```

**Response 404:**
```json
{"error": "not_found"}
```

---

### GET /api/locations/{id}/weather-config

Identisches Verhalten wie `GET /api/trips/{id}/weather-config`, jedoch fuer Location-Entitaeten.

---

### PUT /api/locations/{id}/weather-config

Identisches Verhalten wie `PUT /api/trips/{id}/weather-config`, jedoch fuer Location-Entitaeten.

---

### GET /api/subscriptions/{id}/weather-config

Identisches Verhalten wie `GET /api/trips/{id}/weather-config`, jedoch fuer Subscription-Entitaeten.

---

### PUT /api/subscriptions/{id}/weather-config

Identisches Verhalten wie `PUT /api/trips/{id}/weather-config`, jedoch fuer Subscription-Entitaeten.

---

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `go-chi/chi/v5` | go module | HTTP Router, `chi.URLParam` fuer `{id}` |
| `encoding/json` | go stdlib | JSON-Deserialisierung des Request-Body und Serialisierung der Response |
| `internal/model` | go package | `Trip.DisplayConfig`, `Location.DisplayConfig`, `CompareSubscription.DisplayConfig` (alle `map[string]interface{}`) |
| `internal/store` | go package | `LoadTrip`/`SaveTrip`, `LoadLocation`/`SaveLocation`, `LoadSubscriptions`/`SaveSubscriptions` |

## Implementation Details

### Handler-Muster (fuer alle 3 Entitaeten gleich)

**GET-Handler:**
1. `chi.URLParam(r, "id")` lesen
2. Entitaet laden (z.B. `store.LoadTrip("default", id)`)
3. Entitaet nicht gefunden → 404 `{"error":"not_found"}`
4. `entity.DisplayConfig` als JSON serialisieren und mit Status 200 schreiben
   - Wenn `DisplayConfig == nil`: `null` wird von `encoding/json` korrekt serialisiert

**PUT-Handler:**
1. `chi.URLParam(r, "id")` lesen
2. Entitaet laden; nicht gefunden → 404
3. Request-Body als `map[string]interface{}` dekodieren → Fehler → 400 `{"error":"bad_request"}`
4. `entity.DisplayConfig = decodedMap` setzen
5. Entitaet speichern (z.B. `store.SaveTrip("default", entity)`)
6. Gespeichertes `entity.DisplayConfig` mit Status 200 zurueckgeben

### Konkrete Handler-Signaturen

```go
// internal/handler/weather_config.go

func GetTripWeatherConfig(store *store.Store) http.HandlerFunc
func PutTripWeatherConfig(store *store.Store) http.HandlerFunc

func GetLocationWeatherConfig(store *store.Store) http.HandlerFunc
func PutLocationWeatherConfig(store *store.Store) http.HandlerFunc

func GetSubscriptionWeatherConfig(store *store.Store) http.HandlerFunc
func PutSubscriptionWeatherConfig(store *store.Store) http.HandlerFunc
```

Jeder Handler ist eine Closure ueber `store` — identisches Pattern wie `internal/handler/trip.go` (UpdateTripHandler als Referenz).

### Route-Registrierung (`cmd/server/main.go`)

```go
r.Get("/api/trips/{id}/weather-config",          handler.GetTripWeatherConfig(store))
r.Put("/api/trips/{id}/weather-config",          handler.PutTripWeatherConfig(store))
r.Get("/api/locations/{id}/weather-config",      handler.GetLocationWeatherConfig(store))
r.Put("/api/locations/{id}/weather-config",      handler.PutLocationWeatherConfig(store))
r.Get("/api/subscriptions/{id}/weather-config",  handler.GetSubscriptionWeatherConfig(store))
r.Put("/api/subscriptions/{id}/weather-config",  handler.PutSubscriptionWeatherConfig(store))
```

### Store-Aufrufe (bestehende Methoden, keine Aenderung)

| Entitaet | Laden | Speichern |
|----------|-------|-----------|
| Trip | `store.LoadTrip(userID, id) (*model.Trip, error)` | `store.SaveTrip(userID, trip)` |
| Location | `store.LoadLocation(userID, id) (*model.Location, error)` | `store.SaveLocation(userID, location)` |
| Subscription | `store.LoadSubscriptions(userID)` + lineare Suche + `store.SaveSubscriptions(userID, subs)` | — |

Hinweis fuer Subscriptions: Da kein `LoadSubscription(id)`-Singleton existiert, laedt der Handler alle Subscriptions, sucht per linearer Suche nach der ID und speichert dann den gesamten Slice zurueck (Read-Modify-Write, identisch zu `UpdateSubscription`).

## Expected Behavior

- **Input:** HTTP-Request mit `{id}` URL-Parameter; bei PUT zusaetzlich JSON-Request-Body
- **Output:** JSON-Response — gespeichertes oder gelesenes `display_config` als Objekt, `null` wenn nicht gesetzt; HTTP-Statuscodes 200, 400, 404
- **Side effects:** PUT-Requests schreiben die gesamte Entitaet zurueck in die JSON-Datei auf Disk (z.B. `data/users/default/trips.json`)

### Error Cases

| Szenario | HTTP Status | Body |
|----------|-------------|------|
| Parent-Entitaet nicht gefunden | 404 | `{"error":"not_found"}` |
| Request-Body ist kein gueltiges JSON | 400 | `{"error":"bad_request"}` |
| `display_config` nicht gesetzt (GET) | 200 | `null` |

## Known Limitations

- Kein File-Locking: Parallele PUT-Requests koennen bei hoher Last zu Race Conditions fuehren (akzeptiert fuer V1 Single-User)
- `display_config` wird als `map[string]interface{}` ohne Typ-Validierung round-getrippt; die typisierte Repraesentation liegt auf Python/Frontend-Seite (`src/app/models.py`: `UnifiedWeatherDisplayConfig`)
- `userID` ist in V1 hartcodiert auf `"default"`
- Subscription-Handler benoetigt Load-All + lineare Suche, da kein `LoadSubscription(id)`-Singleton im Store vorhanden ist

## Changelog

- 2026-04-14: Implemented — `internal/handler/weather_config.go` (NEW) + route registration in `cmd/server/main.go`
- 2026-04-14: Initial spec (M5c — Weather Config Endpoints, Go REST API)
