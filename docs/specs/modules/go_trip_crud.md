---
entity_id: go_trip_crud
type: module
created: 2026-04-12
updated: 2026-04-12
status: draft
version: "1.0"
tags: [migration, go, trip, crud]
---

# M1d: Go Trip Model + Read-Only Store + GET Endpoints

## Approval

- [ ] Approved

## Purpose

Trip-Datenmodell (Trip/Stage/Waypoint) als Go Structs, Read-Only JSON Store und GET Endpoints. Vervollstaendigt M1 zusammen mit M1e (Write-Operationen).

## Scope

### In Scope
- Trip/Stage/Waypoint Go Structs (kompatibel mit bestehenden JSON-Dateien)
- Store erweitern: LoadTrips(), LoadTrip(id)
- GET /api/trips — alle Trips als JSON Array
- GET /api/trips/{id} — einzelner Trip als JSON
- Tests mit echten Daten aus data/users/default/trips/

### Out of Scope
- Write-Operationen POST/PUT/DELETE (M1e)
- Input-Validierung (M1e)
- Typisierte Configs (display_config, report_config bleiben opaque maps)
- Custom time.Time Parsing fuer date/start_time (bleiben Strings)

## Architecture

```
GET /api/trips      → handler.TripsHandler(store)    → store.LoadTrips()
GET /api/trips/{id} → handler.TripHandler(store)     → store.LoadTrip(id)
```

## Source

- **Files:** `internal/model/trip.go`, `internal/store/store.go` (erweitern), `internal/handler/trip.go`, `cmd/server/main.go` (erweitern)
- **Identifier:** `Trip{}`, `Stage{}`, `Waypoint{}`, `Store.LoadTrips()`, `Store.LoadTrip()`, `TripsHandler()`, `TripHandler()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| internal/store | go package | Store erweitern um Trip-Methoden |
| internal/model | go package | Trip/Stage/Waypoint Structs |
| go-chi/chi/v5 | go module | URL-Parameter ({id}) |
| data/users/default/trips/*.json | data files | Trip-Daten (read-only) |

## Implementation Details

### Trip Model (internal/model/trip.go)

```go
type Waypoint struct {
    ID         string  `json:"id"`
    Name       string  `json:"name"`
    Lat        float64 `json:"lat"`
    Lon        float64 `json:"lon"`
    ElevationM int     `json:"elevation_m"`
    TimeWindow *string `json:"time_window,omitempty"`
}

type Stage struct {
    ID        string     `json:"id"`
    Name      string     `json:"name"`
    Date      string     `json:"date"`
    Waypoints []Waypoint `json:"waypoints"`
    StartTime *string    `json:"start_time,omitempty"`
}

type Trip struct {
    ID                string                 `json:"id"`
    Name              string                 `json:"name"`
    Stages            []Stage                `json:"stages"`
    AvalancheRegions  []string               `json:"avalanche_regions,omitempty"`
    Aggregation       map[string]interface{} `json:"aggregation,omitempty"`
    WeatherConfig     map[string]interface{} `json:"weather_config,omitempty"`
    DisplayConfig     map[string]interface{} `json:"display_config,omitempty"`
    ReportConfig      map[string]interface{} `json:"report_config,omitempty"`
}
```

Felder wie `date`, `start_time`, `time_window` bleiben Strings fuer JSON-Kompatibilitaet. Configs als opaque maps bis M2.

### Store erweitern (internal/store/store.go)

```go
func (s *Store) TripsDir() string {
    return filepath.Join(s.DataDir, "users", s.UserID, "trips")
}

func (s *Store) LoadTrips() ([]Trip, error) {
    // Gleicher Pattern wie LoadLocations:
    // 1. ReadDir(TripsDir)
    // 2. Fuer jede .json: ReadFile + Unmarshal → Trip
    // 3. Fehlerhafte Dateien ueberspringen (log)
    // 4. Sortiert nach Name zurueckgeben
}

func (s *Store) LoadTrip(id string) (*Trip, error) {
    // 1. Pfad: TripsDir/id.json
    // 2. ReadFile + Unmarshal
    // 3. Nicht gefunden → nil, nil
    // 4. Parse-Fehler → nil, error
}
```

### Trip Handler (internal/handler/trip.go)

```go
func TripsHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        trips, err := s.LoadTrips()
        if err != nil {
            w.Header().Set("Content-Type", "application/json")
            w.WriteHeader(500)
            w.Write([]byte(`{"error":"store_error"}`))
            return
        }
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(trips)
    }
}

func TripHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        id := chi.URLParam(r, "id")
        trip, err := s.LoadTrip(id)
        if err != nil {
            w.Header().Set("Content-Type", "application/json")
            w.WriteHeader(500)
            w.Write([]byte(`{"error":"store_error"}`))
            return
        }
        if trip == nil {
            w.Header().Set("Content-Type", "application/json")
            w.WriteHeader(404)
            w.Write([]byte(`{"error":"not_found"}`))
            return
        }
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(trip)
    }
}
```

### Main erweitern (cmd/server/main.go)

```go
r.Get("/api/trips", handler.TripsHandler(s))
r.Get("/api/trips/{id}", handler.TripHandler(s))
```

## Expected Behavior

### GET /api/trips
- **Input:** `curl http://localhost:8090/api/trips`
- **Output:** JSON Array aller Trips
- **Beispiel:**
```json
[
  {
    "id": "gr221-mallorca",
    "name": "GR221 Mallorca",
    "stages": [{"id":"S1","name":"Tag 1","date":"2026-01-17","waypoints":[...]}],
    "aggregation": {"profile":"wandern"}
  }
]
```

### GET /api/trips/{id}
- **Input:** `curl http://localhost:8090/api/trips/gr221-mallorca`
- **Output:** Einzelner Trip als JSON Object
- **Nicht gefunden:** `404 {"error":"not_found"}`

### Error Cases
- `data/users/default/trips/` existiert nicht → leeres Array `[]`
- Kaputte JSON-Datei → wird uebersprungen
- Trip-ID nicht gefunden → `404 {"error":"not_found"}`

## Testing

### TDD Tests (Go)

```bash
go test ./internal/... -v
```

1. **Store LoadTrips:** Echte Trips aus data/users/default/trips/ laden
2. **Store LoadTrips Empty:** Leeres Verzeichnis → []
3. **Store LoadTrips Bad JSON:** Fehlerhafte Datei ueberspringen
4. **Store LoadTrip by ID:** Einzelnen Trip laden (echte Datei)
5. **Store LoadTrip Not Found:** Nicht existierende ID → nil, nil
6. **Handler GET /api/trips:** JSON Array Response
7. **Handler GET /api/trips/{id}:** JSON Object Response
8. **Handler GET /api/trips/{id} 404:** Nicht gefunden → 404

## Known Limitations

- Nur Read-Only (kein POST/PUT/DELETE)
- Configs als untypisierte Maps
- date/start_time/time_window als Strings (kein Parsing)
- Kein Caching

## Changelog

- 2026-04-12: Initial spec (M1d — Trip Model + Read-Only Store + GET)
