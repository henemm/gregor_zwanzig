---
entity_id: go_proxy_binary
type: module
created: 2026-04-12
updated: 2026-04-12
status: draft
version: "1.0"
tags: [migration, go, proxy, chi]
---

# M1b: Go Proxy Binary (Chi Router)

## Approval

- [ ] Approved

## Purpose

Go HTTP-Server als externer Proxy vor dem Python FastAPI Wrapper. Vervollstaendigt M1: beweist dass Go ↔ Python Kommunikation funktioniert (Request rein, durch Python-Core, JSON Response zurueck).

## Scope

### In Scope
- Go Binary mit Chi Router auf :8090
- Proxy zu Python FastAPI auf localhost:8000
- Health-Endpoint mit Python-Liveness-Check
- 503 Fallback wenn Python nicht erreichbar
- go.mod mit chi Dependency

### Out of Scope
- Auth / Multi-User (M2)
- Eigene Business-Logik in Go
- Nginx-Integration (M4)
- Systemd-Service (M4)

## Architecture

```
  curl/Browser → Go (:8090) → Python FastAPI (:8000) → Core
                  │
                  ├── /api/health    → eigene Response + Python-Ping
                  ├── /api/config    → Proxy → /config
                  └── /api/forecast  → Proxy → /forecast
```

## Source

- **File:** `cmd/gregor-api/main.go`
- **Identifier:** `main()`

## Endpoints

### GET /api/health

Eigener Health-Check plus Python-Core-Status:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "python_core": "ok"
}
```

Wenn Python nicht erreichbar:
```json
{
  "status": "degraded",
  "version": "0.1.0",
  "python_core": "unavailable"
}
```

Status-Code: immer 200 (Go selbst laeuft ja).

### GET /api/config

Pass-through Proxy zu `http://localhost:8000/config`.
- Erfolg: Python-Response 1:1 weiterleiten (Status + Body)
- Fehler: `503 {"error": "core_unavailable"}`

### GET /api/forecast?lat=&lon=&hours=

Pass-through Proxy zu `http://localhost:8000/forecast?lat=&lon=&hours=`.
- Erfolg: Python-Response 1:1 weiterleiten (Status + Body + Content-Type)
- Python gibt 422: 422 weiterleiten (Validierungsfehler)
- Python gibt 502: 502 weiterleiten (Provider-Fehler)
- Python nicht erreichbar: `503 {"error": "core_unavailable"}`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| go-chi/chi/v5 | go module | HTTP Router |
| Python FastAPI | service | Backend auf localhost:8000 |

## File Structure

```
cmd/
└── gregor-api/
    ├── go.mod        # module github.com/henemm/gregor-api, chi dependency
    ├── go.sum
    └── main.go       # HTTP Server + Proxy (~120 LoC)
```

## Implementation Details

### Proxy-Logik

```go
func proxyToPython(w http.ResponseWriter, r *http.Request, path string) {
    // 1. Build URL: http://localhost:8000 + path + query string
    // 2. Forward request via http.Get
    // 3. Copy status code, Content-Type header, body
    // 4. On error: 503 {"error": "core_unavailable"}
}
```

### Startup

```go
func main() {
    pythonURL := envOrDefault("PYTHON_CORE_URL", "http://localhost:8000")
    port := envOrDefault("PORT", "8090")

    r := chi.NewRouter()
    r.Use(middleware.Logger)
    r.Get("/api/health", healthHandler)
    r.Get("/api/config", configHandler)
    r.Get("/api/forecast", forecastHandler)

    log.Printf("Go API listening on :%s, proxying to %s", port, pythonURL)
    http.ListenAndServe(":"+port, r)
}
```

Konfigurierbar via Env-Vars:
- `PYTHON_CORE_URL` (default: `http://localhost:8000`)
- `PORT` (default: `8090`)

## Expected Behavior

- **Input:** `curl http://localhost:8090/api/forecast?lat=47.27&lon=11.40&hours=24`
- **Go:** Leitet weiter an `http://localhost:8000/forecast?lat=47.27&lon=11.40&hours=24`
- **Output:** Identisches JSON wie direkt von Python (Status, Headers, Body)

### Error Cases
- Python laeuft nicht → `503 {"error": "core_unavailable"}`
- Python gibt 4xx/5xx → Status + Body 1:1 weiterleiten

## Testing

### TDD Tests (Go)

```bash
cd cmd/gregor-api && go test -v
```

Tests mit echtem Python-Server (kein Mock):
1. Health-Endpoint gibt JSON mit python_core zurueck
2. Config-Proxy leitet Response korrekt weiter
3. Forecast-Proxy leitet Query-Params und Response weiter
4. Python nicht erreichbar → 503

### Integrationstest (manuell)

```bash
# Terminal 1: Python starten
cd /home/hem/gregor_zwanzig && uvicorn api.main:app --host 127.0.0.1 --port 8000

# Terminal 2: Go starten
cd /home/hem/gregor_zwanzig/cmd/gregor-api && go run main.go

# Terminal 3: Testen
curl http://localhost:8090/api/health
curl http://localhost:8090/api/config
curl "http://localhost:8090/api/forecast?lat=47.27&lon=11.40&hours=24"
```

## Known Limitations

- Go ist in M1 nur ein Proxy — keine eigene Logik
- Kein Connection Pooling (net/http Default Client reicht fuer PoC)
- Kein Timeout-Konfiguration (net/http Defaults)
- Kein Nginx davor (erst M4)

## Changelog

- 2026-04-12: Initial spec (M1b — Go Proxy Binary)
