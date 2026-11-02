---
entity_id: weather_config_endpoints
type: module
created: 2026-04-14
updated: 2026-11-02
status: implemented
version: "1.1"
tags: [go, rest-api, chi, weather-config, trip, location, json-store]
---

# Weather Config Endpoints

## Approval

- [x] Approved

## Purpose

Go HTTP-Handler-Modul, das vier REST-Endpoints bereitstellt, um das `display_config`-Subfeld gezielt auf Trip- und Location-Entitaeten zu lesen und zu aendern. Es ist ein Convenience-Layer ueber die bestehenden CRUD-Handler — statt immer das gesamte Objekt zu uebertragen reicht der Client nur die Anzeigeoptionen ein.

> Stand 2026-11-02 (#2161): Die frueheren Endpunkte fuer den Drittstack-Abo-Typ sind seit #1250 (Scheibe 0) entfernt. Die Handler laufen mandantengetrennt ueber `s.WithUser(...)` (ADR-0003, #1395/#1396).

## Scope

### In Scope
- Vier HTTP-Handler in `internal/handler/weather_config.go`: GET/PUT fuer Trip und Location
- Route-Registrierung in `internal/router/router.go`
- Load→Read/Modify(Merge)→Save-Pattern analog zu bestehenden CRUD-Handlern
- Mandantentrennung: jeder Handler bindet den Store per `s.WithUser(middleware.UserIDFromContext(r.Context()))` an den angemeldeten Nutzer
- Fehlerbehandlung: 404 bei nicht gefundenem Parent, 400 bei ungueltigem JSON-Body, 412 bei abweichendem `If-Match` (Trip), 503 bei belegter Trip-Sperre

### Out of Scope
- Schema-Validierung von `display_config`-Inhalten (wird als opaque JSON round-getrippt)
- Neues Data Model (kein neues Struct notwendig)

## Architecture

```
SvelteKit
    │
    ├── GET  /api/trips/{id}/weather-config
    ├── PUT  /api/trips/{id}/weather-config
    ├── GET  /api/locations/{id}/weather-config
    └── PUT  /api/locations/{id}/weather-config
            │
            ▼
    Go Handler (:8090)
    internal/handler/weather_config.go
            │  s.WithUser(userID aus Auth-Kontext)
            │  Sperre → Load → Merge DisplayConfig → Save
            ▼
    internal/store
    LoadTrip/SaveTrip, LoadLocation/SaveLocation
            │
            ▼
    data/users/<user_id>/briefings/<id>.json   (Trip)
    data/users/<user_id>/locations/<id>.json   (Location)
```

## Source

- **File:** `internal/handler/weather_config.go`
- **Identifier:** `GetTripWeatherConfigHandler`, `PutTripWeatherConfigHandler`, `GetLocationWeatherConfigHandler`, `PutLocationWeatherConfigHandler`

### Weitere betroffene Dateien
- **Routing:** `internal/router/router.go` — 4 Route-Registrierungen
- **Sperren/Vorbedingung:** `internal/handler/schreibsperre.go` (`lockBriefingOr503`), `internal/handler/etag.go` (`ifMatchAllows`, `setETagHeader`), `internal/store/location_lock.go` (`LockLocation`)

## Endpoints

### GET /api/trips/{id}/weather-config

**Response 200 (config vorhanden):** setzt `ETag` (Stempel der ganzen Briefing-Datei)
```json
{"show_precipitation": true, "show_wind": false}
```

**Response 200 (config nicht gesetzt):**
```json
null
```

**Response 404:** Trip existiert fuer den angemeldeten Nutzer nicht.

---

### PUT /api/trips/{id}/weather-config

**Request Body:** Beliebiges gueltiges JSON-Objekt (opaque, kein Schema). Optionaler Header `If-Match` mit dem zuletzt gelesenen ETag.
```json
{"show_precipitation": true, "show_wind": false}
```

**Response 200:** Gespeichertes `display_config` als JSON-Objekt, neuer `ETag`.

**Response 400:** Body ist kein gueltiges JSON.

**Response 404:** Trip existiert fuer den angemeldeten Nutzer nicht.

**Response 412:** `If-Match` passt nicht zur aktuellen Fassung.

**Response 503:** Trip-Sperre belegt (`Retry-After: 5`).

---

### GET /api/locations/{id}/weather-config

Wie `GET /api/trips/{id}/weather-config`, jedoch fuer Location-Entitaeten, ohne Sperre und ohne `ETag`.

---

### PUT /api/locations/{id}/weather-config

Wie `PUT /api/trips/{id}/weather-config`, jedoch fuer Location-Entitaeten; Schreibsperre ueber `LockLocation`, keine `If-Match`-Pruefung.

---

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `go-chi/chi/v5` | go module | HTTP Router, `chi.URLParam` fuer `{id}` |
| `encoding/json` | go stdlib | JSON-Deserialisierung des Request-Body und Serialisierung der Response |
| `internal/middleware` | go package | `UserIDFromContext` (userID aus dem Auth-Kontext) |
| `internal/model` | go package | `Trip.DisplayConfig`, `Location.DisplayConfig` (`map[string]interface{}`) |
| `internal/store` | go package | `WithUser`, `LoadTrip`/`SaveTrip`, `LoadLocation`/`SaveLocation`, `LockLocation`, `BriefingFingerprint` |

## Implementation Details

### Handler-Muster

**GET-Handler:**
1. `s := s.WithUser(middleware.UserIDFromContext(r.Context()))` (anfragelokal, #1395/#1396)
2. `chi.URLParam(r, "id")` lesen, ungueltige ID abweisen
3. Trip: `lockBriefingOr503` auch beim Lesen, damit der ETag zur ausgelieferten Fassung gehoert
4. Entitaet laden (`s.LoadTrip(id)` bzw. `s.LoadLocation(id)`); nicht gefunden → 404
5. `entity.DisplayConfig` als JSON mit Status 200 schreiben (`nil` → `null`)

**PUT-Handler:**
1. `s := s.WithUser(middleware.UserIDFromContext(r.Context()))`
2. `chi.URLParam(r, "id")` lesen, ungueltige ID abweisen
3. Sperre nehmen: Trip `lockBriefingOr503` (#1395), Location `s.LockLocation(id)` (#2158)
4. Entitaet laden; nicht gefunden → 404
5. Nur Trip: `ifMatchAllows(If-Match, Fingerprint)` vor dem Dekodieren; Abweichung → 412
6. Request-Body als `map[string]interface{}` dekodieren → Fehler → 400
7. `entity.DisplayConfig = mergeConfigMap(alt, neu)` (Feld-Level-Merge, #1151/#1159, kein Replace)
8. Nur Trip: `alert_rules` mit den aktiven Metriken synchronisieren (#701)
9. `entity.ID = id` setzen und speichern (`s.SaveTrip` bzw. `s.SaveLocation`)
10. Gespeichertes `display_config` mit Status 200 zurueckgeben (Trip mit neuem `ETag`)

### Locking-Ist-Stand (2026-11-02)

- **Trip:** GET und PUT nehmen `lockBriefingOr503`; PUT prueft optional `If-Match` gegen den Datei-Stempel (`ifMatchAllows`, `internal/handler/etag.go`). Ohne `If-Match`-Header (oder mit `*`) ist die Versionspruefung bewusst nicht scharf.
- **Location:** PUT nimmt `s.LockLocation(id)` (#2158); keine ETag-/If-Match-Pruefung.

### Route-Registrierung (`internal/router/router.go`)

```go
r.Get("/api/trips/{id}/weather-config", handler.GetTripWeatherConfigHandler(deps.Store))
r.Put("/api/trips/{id}/weather-config", handler.PutTripWeatherConfigHandler(deps.Store))
r.Get("/api/locations/{id}/weather-config", handler.GetLocationWeatherConfigHandler(deps.Store))
r.Put("/api/locations/{id}/weather-config", handler.PutLocationWeatherConfigHandler(deps.Store))
```

## Expected Behavior

- **Input:** HTTP-Request eines angemeldeten Nutzers mit `{id}` URL-Parameter; bei PUT zusaetzlich JSON-Request-Body
- **Output:** JSON-Response — gespeichertes oder gelesenes `display_config` als Objekt, `null` wenn nicht gesetzt; HTTP-Statuscodes 200, 400, 404, 412, 503
- **Side effects:** PUT schreibt die Entitaet in die Datei des angemeldeten Nutzers zurueck (`data/users/<user_id>/...`)

### Error Cases

| Szenario | HTTP Status |
|----------|-------------|
| Parent-Entitaet fuer diesen Nutzer nicht gefunden | 404 |
| Request-Body ist kein gueltiges JSON | 400 |
| `If-Match` passt nicht (Trip) | 412 |
| Trip-Sperre belegt | 503 |
| `display_config` nicht gesetzt (GET) | 200, `null` |

## Known Limitations

- `display_config` wird als `map[string]interface{}` ohne Typ-Validierung round-getrippt; die typisierte Repraesentation liegt auf Python/Frontend-Seite (`src/app/models.py`: `UnifiedWeatherDisplayConfig`)
- Trip-PUT ohne `If-Match`-Header prueft die Version nicht (bewusst nicht scharf); die Sperre schuetzt nur gegen gleichzeitige Schreibvorgaenge, nicht gegen veraltete Fassungen im Client
- Location-PUT hat Sperre (#2158), aber keine ETag-/If-Match-Pruefung

## Changelog

- 2026-11-02: Doku an Ist-Stand angeglichen (#2161): Endpunkte des mit #1250 entfernten Drittstacks gestrichen, Mandantentrennung ueber `s.WithUser(...)`, Locking-Ist-Stand (Trip `lockBriefingOr503` + optionales If-Match, Location `LockLocation` seit #2158), Routing in `internal/router/router.go`
- 2026-04-14: Implemented — `internal/handler/weather_config.go` (NEW) + route registration in `cmd/server/main.go`
- 2026-04-14: Initial spec (M5c — Weather Config Endpoints, Go REST API)
