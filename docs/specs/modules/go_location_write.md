---
entity_id: go_location_write
type: module
created: 2026-04-13
updated: 2026-04-13
status: draft
version: "1.0"
tags: [migration, go, location, crud, write]
---

# M1f: Location Write Operations (POST/PUT/DELETE)

## Approval

- [ ] Approved

## Purpose

Write-Operationen fuer Locations: Erstellen, Aktualisieren und Loeschen via REST API. Ergaenzt M1c (Read-Only) um volle CRUD-Faehigkeit. Gleicher Pattern wie M1e (Trip Write).

## Scope

### In Scope
- Store: SaveLocation(loc), DeleteLocation(id)
- POST /api/locations — neue Location anlegen
- PUT /api/locations/{id} — bestehende Location aktualisieren
- DELETE /api/locations/{id} — Location loeschen
- Input-Validierung: id, name, lat/lon != 0
- Tests mit TempDir

### Out of Scope
- Typisierte DisplayConfig (bleibt opaque map)
- Duplikat-Erkennung (gleiche Koordinaten)
- Bulk Operations

## Architecture

```
POST   /api/locations       → handler.CreateLocationHandler(store) → store.SaveLocation(loc)
PUT    /api/locations/{id}  → handler.UpdateLocationHandler(store) → store.SaveLocation(loc)
DELETE /api/locations/{id}  → handler.DeleteLocationHandler(store) → store.DeleteLocation(id)
```

## Source

- **Files:** `internal/store/store.go` (erweitern), `internal/handler/location.go` (erweitern), `cmd/server/main.go` (erweitern)
- **Identifier:** `Store.SaveLocation()`, `Store.DeleteLocation()`, `CreateLocationHandler()`, `UpdateLocationHandler()`, `DeleteLocationHandler()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| internal/store | go package | SaveLocation, DeleteLocation hinzufuegen |
| internal/model | go package | Location Struct (besteht aus M1c) |
| go-chi/chi/v5 | go module | URL-Parameter ({id}) |

## Implementation Details

### Store erweitern (internal/store/store.go)

```go
func (s *Store) SaveLocation(loc model.Location) error {
    dir := s.LocationsDir()
    os.MkdirAll(dir, 0755)
    data, _ := json.MarshalIndent(loc, "", "  ")
    return os.WriteFile(filepath.Join(dir, loc.ID+".json"), data, 0644)
}

func (s *Store) DeleteLocation(id string) error {
    path := filepath.Join(s.LocationsDir(), id+".json")
    err := os.Remove(path)
    if os.IsNotExist(err) {
        return nil
    }
    return err
}
```

### Handler erweitern (internal/handler/location.go)

```go
func validateLocation(loc model.Location) error {
    // id nicht leer
    // name nicht leer
    // lat/lon nicht beide 0
}

func CreateLocationHandler(s *store.Store) http.HandlerFunc
func UpdateLocationHandler(s *store.Store) http.HandlerFunc
func DeleteLocationHandler(s *store.Store) http.HandlerFunc
```

Gleicher Pattern wie Trip Write Handler. UpdateLocation prueft Existenz (404), URL-ID ueberschreibt Body-ID. Delete ist idempotent (204).

### Store: LoadLocation (neu)

Fuer PUT brauchen wir eine Existenz-Pruefung:

```go
func (s *Store) LoadLocation(id string) (*model.Location, error) {
    path := filepath.Join(s.LocationsDir(), id+".json")
    data, err := os.ReadFile(path)
    if os.IsNotExist(err) { return nil, nil }
    if err != nil { return nil, err }
    var loc model.Location
    json.Unmarshal(data, &loc)
    return &loc, nil
}
```

### Routes (cmd/server/main.go)

```go
r.Post("/api/locations", handler.CreateLocationHandler(s))
r.Put("/api/locations/{id}", handler.UpdateLocationHandler(s))
r.Delete("/api/locations/{id}", handler.DeleteLocationHandler(s))
```

## Expected Behavior

### POST /api/locations
- **Erfolg:** `201 {"id":"new-loc","name":"New Location","lat":47.0,"lon":11.0}`
- **Fehlender Body:** `400 {"error":"bad_request"}`
- **Validierungsfehler:** `400 {"error":"validation_error","detail":"name required"}`

### PUT /api/locations/{id}
- **Erfolg:** `200 {"id":"existing",...}`
- **Nicht vorhanden:** `404 {"error":"not_found"}`
- **URL-ID ueberschreibt Body-ID**

### DELETE /api/locations/{id}
- **Erfolg:** `204 No Content`
- **Nicht vorhanden:** `204 No Content` (idempotent)

## Testing

1. **Store SaveLocation:** Speichern + Laden roundtrip
2. **Store DeleteLocation:** Speichern, Loeschen, LoadLocation → nil
3. **Store DeleteLocation Not Found:** Kein Fehler
4. **Store LoadLocation:** Einzelne Location laden
5. **Store LoadLocation Not Found:** nil, nil
6. **Handler POST 201:** Gueltige Location
7. **Handler POST 400:** Fehlender Name
8. **Handler POST 400:** Zero Coords
9. **Handler PUT 200:** Existierende Location
10. **Handler PUT 404:** Nicht vorhanden
11. **Handler DELETE 204:** Location loeschen

## Known Limitations

- Keine Duplikat-Erkennung
- Keine atomaren Writes
- DeleteLocation idempotent (kein 404)

## Changelog

- 2026-04-13: Initial spec (M1f — Location Write Operations)
