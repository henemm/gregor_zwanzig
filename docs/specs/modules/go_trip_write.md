---
entity_id: go_trip_write
type: module
created: 2026-04-13
updated: 2026-04-13
status: draft
version: "1.0"
tags: [migration, go, trip, crud, write]
---

# M1e: Trip Write Operations (POST/PUT/DELETE)

## Approval

- [ ] Approved

## Purpose

Write-Operationen fuer Trips: Erstellen, Aktualisieren und Loeschen via REST API. Ergaenzt M1d (Read-Only) um volle CRUD-Faehigkeit.

## Scope

### In Scope
- Store: SaveTrip(trip), DeleteTrip(id)
- POST /api/trips — neuen Trip anlegen
- PUT /api/trips/{id} — bestehenden Trip aktualisieren
- DELETE /api/trips/{id} — Trip loeschen
- Input-Validierung: id, name, mindestens 1 Stage mit 1 Waypoint
- Tests mit echten Dateien (TempDir)

### Out of Scope
- Location Write (M1f)
- Typisierte Configs (bleiben opaque maps)
- Conflict Detection (kein ETag/If-Match)
- Bulk Operations

## Architecture

```
POST   /api/trips       → handler.CreateTripHandler(store)  → store.SaveTrip(trip)
PUT    /api/trips/{id}  → handler.UpdateTripHandler(store)  → store.SaveTrip(trip)
DELETE /api/trips/{id}  → handler.DeleteTripHandler(store)  → store.DeleteTrip(id)
```

## Source

- **Files:** `internal/store/store.go` (erweitern), `internal/handler/trip.go` (erweitern), `cmd/server/main.go` (erweitern)
- **Identifier:** `Store.SaveTrip()`, `Store.DeleteTrip()`, `CreateTripHandler()`, `UpdateTripHandler()`, `DeleteTripHandler()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| internal/store | go package | SaveTrip, DeleteTrip hinzufuegen |
| internal/model | go package | Trip Struct (besteht aus M1d) |
| go-chi/chi/v5 | go module | URL-Parameter ({id}) |

## Implementation Details

### Store erweitern (internal/store/store.go)

```go
func (s *Store) SaveTrip(trip model.Trip) error {
    dir := s.TripsDir()
    os.MkdirAll(dir, 0755)

    data, err := json.MarshalIndent(trip, "", "  ")
    if err != nil {
        return err
    }

    return os.WriteFile(filepath.Join(dir, trip.ID+".json"), data, 0644)
}

func (s *Store) DeleteTrip(id string) error {
    path := filepath.Join(s.TripsDir(), id+".json")
    err := os.Remove(path)
    if os.IsNotExist(err) {
        return nil
    }
    return err
}
```

DeleteTrip gibt keinen Fehler bei nicht-existierender Datei (idempotent).

### Handler erweitern (internal/handler/trip.go)

```go
func CreateTripHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        var trip model.Trip
        if err := json.NewDecoder(r.Body).Decode(&trip); err != nil {
            // 400 bad_request
        }
        if err := validateTrip(trip); err != nil {
            // 400 validation_error mit Details
        }
        if err := s.SaveTrip(trip); err != nil {
            // 500 store_error
        }
        // 201 Created mit Trip als Response
    }
}

func UpdateTripHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        id := chi.URLParam(r, "id")
        // Pruefen ob Trip existiert (404 wenn nicht)
        var trip model.Trip
        // Decode + Validate
        trip.ID = id  // URL-ID hat Vorrang
        // SaveTrip + 200 OK
    }
}

func DeleteTripHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        id := chi.URLParam(r, "id")
        // DeleteTrip + 204 No Content
    }
}

func validateTrip(t model.Trip) error {
    // id nicht leer
    // name nicht leer
    // mindestens 1 Stage
    // jede Stage: mindestens 1 Waypoint
    // jeder Waypoint: lat/lon != 0
}
```

### Validierung

| Feld | Regel | Error |
|------|-------|-------|
| trip.ID | nicht leer | "id required" |
| trip.Name | nicht leer | "name required" |
| trip.Stages | len >= 1 | "at least one stage required" |
| stage.Waypoints | len >= 1 pro Stage | "stage {id}: at least one waypoint required" |
| waypoint.Lat/Lon | nicht beide 0 | "waypoint {id}: coordinates required" |

### Routes (cmd/server/main.go)

```go
r.Post("/api/trips", handler.CreateTripHandler(s))
r.Put("/api/trips/{id}", handler.UpdateTripHandler(s))
r.Delete("/api/trips/{id}", handler.DeleteTripHandler(s))
```

## Expected Behavior

### POST /api/trips
- **Input:** JSON Body mit Trip
- **Erfolg:** `201 {"id":"new-trip","name":"New Trip",...}`
- **Fehlender Body:** `400 {"error":"bad_request"}`
- **Validierungsfehler:** `400 {"error":"validation_error","detail":"name required"}`

### PUT /api/trips/{id}
- **Input:** JSON Body mit Trip
- **Erfolg:** `200 {"id":"existing-trip",...}`
- **Trip nicht vorhanden:** `404 {"error":"not_found"}`
- **URL-ID ueberschreibt Body-ID**

### DELETE /api/trips/{id}
- **Erfolg:** `204 No Content`
- **Nicht vorhanden:** `204 No Content` (idempotent)

## Testing

### TDD Tests (Go)

```bash
go test ./internal/... -v
```

1. **Store SaveTrip:** Trip speichern, danach laden und vergleichen
2. **Store DeleteTrip:** Trip speichern, loeschen, LoadTrip gibt nil
3. **Store DeleteTrip Not Found:** Nicht existierender Trip → kein Fehler
4. **Handler POST /api/trips:** Gueliger Trip → 201
5. **Handler POST /api/trips invalid:** Fehlender Name → 400
6. **Handler PUT /api/trips/{id}:** Existierender Trip → 200
7. **Handler PUT /api/trips/{id} 404:** Nicht existierend → 404
8. **Handler DELETE /api/trips/{id}:** Trip loeschen → 204

## Known Limitations

- Keine Conflict Detection (kein ETag)
- Keine atomaren Writes (kein Temp-File + Rename)
- Keine Validierung von date/start_time Format (Strings)
- DeleteTrip ist idempotent (kein 404 bei nicht-existierend)

## Changelog

- 2026-04-13: Initial spec (M1e — Trip Write Operations)
