---
entity_id: go_project_structure
type: module
created: 2026-04-12
updated: 2026-04-12
status: draft
version: "1.0"
tags: [migration, go, config, store]
---

# M1c: Go Projektstruktur + Config + JSON Store (Locations)

## Approval

- [ ] Approved

## Purpose

Go-Projekt von Single-File-Proxy (`cmd/gregor-api/main.go`) in eine produktionsreife Paketstruktur umbauen. Config-System mit `envconfig` (GZ_ Prefix), Location-Model, Read-Only JSON Store und GET /api/locations Endpoint. Bestehender Proxy-Code wird integriert.

## Scope

### In Scope
- Projektstruktur: `cmd/server/`, `internal/config/`, `internal/model/`, `internal/store/`, `internal/handler/`
- Config via `kelseyhightower/envconfig` mit GZ_ Prefix
- Location Go-Struct (kompatibel mit bestehenden JSON-Dateien)
- Read-Only JSON Store: `LoadLocations()` aus `data/users/default/locations/`
- GET /api/locations Endpoint (JSON Array)
- Bestehende Proxy-Endpoints (/api/health, /api/config, /api/forecast) migrieren
- Bestehende Tests migrieren + neue Tests

### Out of Scope
- Trip-Model und Trip-Store (M1d)
- CRUD Write-Operationen (POST/PUT/DELETE)
- Multi-User Support (M2)
- OpenAPI-Spec generieren
- Systemd-Unit

## Architecture

```
cmd/server/main.go          # Einstiegspunkt: Config laden, Router aufbauen, ListenAndServe
internal/config/config.go   # envconfig Struct mit GZ_ Prefix
internal/model/location.go  # Location Struct
internal/store/store.go     # JSON Store: LoadLocations(dataDir)
internal/handler/location.go # GET /api/locations Handler
internal/handler/proxy.go   # Bestehende Proxy-Handler (health, config, forecast)
```

```
Browser → Go (:8090) → GET /api/locations → JSON Store → data/users/default/locations/*.json
                     → GET /api/health    → Python-Ping (wie bisher)
                     → GET /api/config    → Proxy → Python :8000
                     → GET /api/forecast  → Proxy → Python :8000
```

## Source

- **Files:** `cmd/server/main.go`, `internal/config/config.go`, `internal/model/location.go`, `internal/store/store.go`, `internal/handler/location.go`, `internal/handler/proxy.go`
- **Identifier:** `main()`, `Config{}`, `Location{}`, `Store.LoadLocations()`, `LocationsHandler()`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| go-chi/chi/v5 | go module | HTTP Router (besteht) |
| kelseyhightower/envconfig | go module | Config aus Env-Vars (neu) |
| Python FastAPI | service | Backend auf localhost:8000 (Proxy) |
| data/users/default/locations/*.json | data files | Location-Daten (read-only) |

## File Structure

```
cmd/
├── gregor-api/          # ENTFERNEN (Code wandert nach cmd/server/)
│   ├── main.go
│   ├── main_test.go
│   ├── go.mod
│   └── go.sum
└── server/              # NEU
    ├── main.go          # ~40 LoC
    └── main_test.go     # Migrierte + neue Tests
internal/
├── config/
│   └── config.go        # ~50 LoC
├── model/
│   └── location.go      # ~25 LoC
├── store/
│   └── store.go         # ~60 LoC
└── handler/
    ├── proxy.go         # ~50 LoC (migriert aus cmd/gregor-api/main.go)
    └── location.go      # ~30 LoC
go.mod                   # Wandert ins Repo-Root
go.sum
```

## Implementation Details

### Config (internal/config/config.go)

```go
type Config struct {
    Port          string `envconfig:"PORT" default:"8090"`
    PythonCoreURL string `envconfig:"PYTHON_CORE_URL" default:"http://localhost:8000"`
    DataDir       string `envconfig:"DATA_DIR" default:"data"`
    UserID        string `envconfig:"USER_ID" default:"default"`
}

func Load() (*Config, error) {
    var cfg Config
    err := envconfig.Process("GZ", &cfg)
    return &cfg, err
}
```

Nur die Vars die M1c braucht. Weitere (SMTP, IMAP etc.) kommen in spaeteren Milestones.

### Location Model (internal/model/location.go)

```go
type Location struct {
    ID              string                  `json:"id"`
    Name            string                  `json:"name"`
    Lat             float64                 `json:"lat"`
    Lon             float64                 `json:"lon"`
    ElevationM      *int                    `json:"elevation_m,omitempty"`
    Region          *string                 `json:"region,omitempty"`
    BergfexSlug     *string                 `json:"bergfex_slug,omitempty"`
    ActivityProfile *string                 `json:"activity_profile,omitempty"`
    DisplayConfig   map[string]interface{}  `json:"display_config,omitempty"`
}
```

Optionale Felder als Pointer (nil = nicht vorhanden im JSON). `DisplayConfig` bleibt untypisiert (opaque map) bis M2.

### JSON Store (internal/store/store.go)

```go
type Store struct {
    DataDir string
    UserID  string
}

func New(dataDir, userID string) *Store {
    return &Store{DataDir: dataDir, UserID: userID}
}

func (s *Store) LoadLocations() ([]model.Location, error) {
    // 1. dir = DataDir/users/UserID/locations/
    // 2. os.ReadDir(dir) — alle .json Dateien
    // 3. Fuer jede: os.ReadFile + json.Unmarshal → Location
    // 4. Fehlerhafte Dateien ueberspringen (wie Python loader.py)
    // 5. Sortiert nach Name zurueckgeben
}

func (s *Store) LocationsDir() string {
    return filepath.Join(s.DataDir, "users", s.UserID, "locations")
}
```

### Proxy Handler (internal/handler/proxy.go)

Bestehender Code aus `cmd/gregor-api/main.go` extrahiert:
- `HealthHandler(pythonURL string) http.HandlerFunc`
- `ProxyHandler(pythonURL, path string) http.HandlerFunc`
- Closures statt Package-Level-Var (behebt Race Condition aus M1b)

### Location Handler (internal/handler/location.go)

```go
func LocationsHandler(store *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        locations, err := store.LoadLocations()
        if err != nil {
            http.Error(w, `{"error":"store_error"}`, 500)
            return
        }
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(locations)
    }
}
```

### Main (cmd/server/main.go)

```go
func main() {
    cfg, err := config.Load()
    // fatal on error

    s := store.New(cfg.DataDir, cfg.UserID)
    r := chi.NewRouter()
    r.Use(middleware.Logger)

    r.Get("/api/health", handler.HealthHandler(cfg.PythonCoreURL))
    r.Get("/api/config", handler.ProxyHandler(cfg.PythonCoreURL, "/config"))
    r.Get("/api/forecast", handler.ProxyHandler(cfg.PythonCoreURL, "/forecast"))
    r.Get("/api/locations", handler.LocationsHandler(s))

    log.Printf("Go API on :%s", cfg.Port)
    http.ListenAndServe(":"+cfg.Port, r)
}
```

### go.mod (Repo-Root)

```
module github.com/henemm/gregor-api

go 1.22

require (
    github.com/go-chi/chi/v5 v5.2.5
    github.com/kelseyhightower/envconfig v1.4.0
)
```

go.mod wandert von `cmd/gregor-api/` ins Repo-Root, damit `internal/` Packages aufloesbar sind.

## Expected Behavior

### GET /api/locations
- **Input:** `curl http://localhost:8090/api/locations`
- **Output:** JSON Array aller Locations aus `data/users/default/locations/`
- **Beispiel:**
```json
[
  {"id":"aberg","name":"Aberg","lat":47.366,"lon":13.116,"elevation_m":1150},
  {"id":"hochfügen","name":"Hochfügen","lat":47.067,"lon":11.667,"elevation_m":2300,"activity_profile":"wintersport"}
]
```

### Bestehende Proxy-Endpoints
- Verhalten identisch zu M1b (health, config, forecast)
- Einzige Aenderung: Closures statt Package-Level-Var

### Config
- `GZ_PORT=9090` → Server laeuft auf :9090
- `GZ_DATA_DIR=/other/data` → Store liest von dort
- Ohne Env-Vars: Defaults (Port 8090, data/, default)

### Error Cases
- `data/users/default/locations/` existiert nicht → leeres Array `[]`
- Kaputte JSON-Datei → wird uebersprungen, Rest wird geladen
- Kein einziger Location-File → leeres Array `[]`

## Testing

### TDD Tests (Go)

```bash
cd /home/hem/gregor_zwanzig && go test ./... -v
```

1. **Config:** Load() mit/ohne Env-Vars, Defaults pruefen
2. **Store:** LoadLocations() mit echten Dateien aus data/users/default/locations/
3. **Store Edge Cases:** Leeres Verzeichnis → [], fehlerhaftes JSON → ueberspringen
4. **Location Handler:** GET /api/locations gibt JSON Array zurueck
5. **Proxy (migriert):** Health, Config, Forecast wie bisher
6. **Integration:** Server-Setup mit Config → alle Endpoints erreichbar

## Known Limitations

- Nur Read-Only (kein POST/PUT/DELETE fuer Locations)
- Nur User "default" (kein Multi-User)
- DisplayConfig als untypisierte Map (wird erst in M2 typisiert)
- Kein Caching — jeder Request liest vom Filesystem
- cmd/gregor-api/ wird entfernt (alter Proxy-Code lebt in internal/handler/proxy.go weiter)

## Changelog

- 2026-04-12: Initial spec (M1c — Projektstruktur + Config + JSON Store)
