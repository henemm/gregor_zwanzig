---
entity_id: go_api_setup
type: module
created: 2026-04-12
updated: 2026-04-12
status: draft
version: "1.0"
tags: [migration, go, api, fastapi]
---

# M1: Go REST API Setup + Python-Core HTTP-Wrapper

## Approval

- [ ] Approved

## Purpose

Proof-of-Concept fuer die Hybrid-Migration: Go REST API als externe HTTP-Schicht, Python FastAPI als interner Wrapper um den bestehenden Core. Beweist, dass Go <-> Python Kommunikation funktioniert (Serialisierung, Enums, Datetimes, komplexe DTOs), bevor in M2-M4 alle Endpoints und das Frontend migriert werden.

## Scope

### In Scope (M1)
- Python FastAPI-Wrapper mit 3 Pilot-Endpoints
- Go HTTP-Server mit Chi Router als externer Proxy
- Health-Check, Config, Forecast als Proof-of-Concept
- Systemd-Service-Dateien (Go + Python API)

### Out of Scope (spaetere Meilensteine)
- SvelteKit Frontend (M2/M3)
- Auth / Multi-User (M2)
- Alle 26 CRUD-Endpoints (M2-M3)
- Scheduler-Migration (M4)
- NiceGUI-Entfernung (M4)

## Architecture

```
                    ┌──────────────────────┐
  Internet ──nginx──▶  Go API (:8080)      │
                    │  Chi Router           │
                    │  /api/health          │
                    │  /api/config          │
                    │  /api/forecast        │
                    └─────────┬────────────┘
                              │ HTTP (localhost)
                    ���─────────▼────────────┐
                    │  Python FastAPI       │
                    │  (:8000, localhost)   │
                    │  /health              │
                    │  /config              │
                    │  /forecast            │
                    └─────────┬────────────┘
                              │ direct import
                    ┌─────────▼────────────┐
                    │  Python Core          │
                    │  (unchanged)          │
                    │  services.forecast    │
                    │  app.config           │
                    │  app.models           │
                    └──────────────────────┘
```

NiceGUI laeuft waehrend M1 weiterhin parallel auf :8080. Go API bekommt erst nach M4 (Cutover) den externen Port. Fuer M1 laeuft Go auf einem separaten Port (z.B. :8090) zum Testen.

## Source

### Python FastAPI Wrapper (NEU)

- **File:** `api/main.py`
- **Identifier:** FastAPI app

```python
# api/main.py
from fastapi import FastAPI
from api.routers import health, config, forecast

app = FastAPI(title="Gregor Zwanzig Core API", version="0.1.0")
app.include_router(health.router)
app.include_router(config.router)
app.include_router(forecast.router)
```

### Go HTTP Server (NEU)

- **File:** `cmd/gregor-api/main.go`
- **Identifier:** main()

```go
// cmd/gregor-api/main.go
func main() {
    r := chi.NewRouter()
    r.Use(middleware.Logger)
    r.Get("/api/health", healthHandler)
    r.Get("/api/config", proxyToPython("/config"))
    r.Get("/api/forecast", proxyToPython("/forecast"))
    http.ListenAndServe(":8090", r)
}
```

## Endpoints

### 1. Health Check

| | Python (intern) | Go (extern) |
|--|----------------|-------------|
| **Route** | `GET /health` | `GET /api/health` |
| **Response** | `{"status": "ok", "version": "0.1.0"}` | Gleiches JSON, plus `"python_core": "ok"` |
| **Zweck** | Liveness des Python-Prozesses | Liveness beider Prozesse |

### 2. Config

| | Python (intern) | Go (extern) |
|--|----------------|-------------|
| **Route** | `GET /config` | `GET /api/config` |
| **Response** | Settings als JSON (ohne Secrets) | Pass-through |
| **Zweck** | Beweist Pydantic -> JSON -> Go Serialisierung |

**Secrets-Filter:** SMTP-Passwort, API-Keys, Signal-Credentials werden NICHT exponiert. Nur nicht-sensitive Felder (latitude, longitude, provider, report_type, forecast_hours).

Response-Schema:
```json
{
  "latitude": 47.2692,
  "longitude": 11.4041,
  "location_name": "Innsbruck",
  "provider": "geosphere",
  "report_type": "evening",
  "forecast_hours": 48,
  "channel": "console"
}
```

### 3. Forecast

| | Python (intern) | Go (extern) |
|--|----------------|-------------|
| **Route** | `GET /forecast?lat=&lon=&hours=` | `GET /api/forecast?lat=&lon=&hours=` |
| **Response** | NormalizedTimeseries als JSON | Pass-through |
| **Zweck** | Beweist komplexen DTO-Durchlauf (30+ Felder, Enums) |

Query-Parameter:
- `lat` (float, required): Breitengrad
- `lon` (float, required): Laengengrad
- `hours` (int, optional, default 48): Forecast-Stunden

Response-Schema (gekuerzt):
```json
{
  "meta": {
    "provider": "OPENMETEO",
    "model": "best_match",
    "run": "2026-04-12T06:00:00+00:00",
    "grid_res_km": 11.0,
    "interp": "point_grid"
  },
  "data": [
    {
      "ts": "2026-04-12T12:00:00+00:00",
      "t2m_c": 18.5,
      "wind10m_kmh": 12.3,
      "gust_kmh": 25.1,
      "precip_1h_mm": 0.0,
      "cloud_total_pct": 45,
      "thunder_level": "NONE",
      "pop_pct": 10
    }
  ]
}
```

**Serialisierungs-Regeln:**
- Enums (ThunderLevel, PrecipType, Provider) → `.value` String
- Datetimes → ISO8601 mit Timezone (`+00:00`)
- Optional-Felder die None sind → weggelassen (`exclude_none=True`)
- Go-Structs nutzen `*float64` / `*int` fuer Optional + `omitempty`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/config.Settings` | class | Config-Daten fuer /config Endpoint |
| `src/services/forecast.ForecastService` | class | Forecast-Abfrage fuer /forecast Endpoint |
| `src/app/models.NormalizedTimeseries` | dataclass | Response-DTO fuer /forecast |
| `src/providers/openmeteo.OpenMeteoProvider` | class | Default-Provider fuer Forecast |
| FastAPI | pip | Python HTTP-Framework |
| chi | go module | Go HTTP-Router |

## File Structure

```
gregor_zwanzig/
├── api/                              # NEU: Python FastAPI Wrapper
│   ├── __init__.py
│   ├── main.py                       # FastAPI app (~40 LoC)
│   └── routers/
│       ├── __init__.py
│       ├── health.py                 # GET /health (~15 LoC)
│       ├── config.py                 # GET /config (~30 LoC)
│       └── forecast.py              # GET /forecast (~50 LoC)
│
├── cmd/                              # NEU: Go Binary
│   └── gregor-api/
│       ├── go.mod
│       ├── go.sum
│       └── main.go                   # HTTP Server + Proxy (~120 LoC)
│
├── src/                              # UNVERAENDERT
│   ├── app/
│   ├── services/
│   └── ...
```

## Expected Behavior

### Startup-Reihenfolge
1. Python FastAPI startet auf `localhost:8000`
2. Go startet auf `:8090`
3. Go prueft Python-Health (`GET http://localhost:8000/health`)
4. Bei Timeout (3 Retries, je 1s): Go startet trotzdem, gibt `503` fuer Proxy-Endpoints

### Request-Flow
- **Input:** HTTP Request an Go `:8090/api/forecast?lat=47.27&lon=11.40&hours=24`
- **Go:** Validiert Query-Params, leitet weiter an `http://localhost:8000/forecast?lat=47.27&lon=11.40&hours=24`
- **Python:** Ruft `ForecastService().get_forecast()` auf, serialisiert NormalizedTimeseries via Pydantic
- **Output:** JSON Response mit meta + data Array

### Error-Handling
- Python-Core nicht erreichbar → Go gibt `503 {"error": "core_unavailable"}` zurueck
- Ungueltige Koordinaten → Python gibt `422 {"detail": "lat must be between -90 and 90"}` zurueck
- Provider-Fehler → Python gibt `502 {"error": "provider_error", "detail": "..."}` zurueck

## Testing

### Integrationstest (manuell in M1)
```bash
# 1. Python starten
cd /home/hem/gregor_zwanzig
uvicorn api.main:app --host 127.0.0.1 --port 8000

# 2. Go starten
cd cmd/gregor-api
go run main.go

# 3. Testen
curl http://localhost:8090/api/health
curl http://localhost:8090/api/config
curl "http://localhost:8090/api/forecast?lat=47.27&lon=11.40&hours=24"
```

### Automatisierte Tests (TDD)
- `tests/tdd/test_go_api_setup.py` — Python FastAPI Endpoints mit TestClient
- Go-seitig: `main_test.go` mit httptest (wenn Go Proxy-Logik eigene Logik hat)

### Validierungskriterien
1. `/api/health` gibt 200 mit `python_core: ok` zurueck
2. `/api/config` gibt Settings-JSON ohne Secrets zurueck
3. `/api/forecast` gibt NormalizedTimeseries-JSON mit korrekten Enum-Strings und ISO-Datetimes zurueck
4. Forecast-Response hat mindestens 24 Datenpunkte (fuer hours=24)
5. Go gibt 503 wenn Python nicht laeuft

## Known Limitations

- M1 exponiert nur 3 von 26 Endpoints — kein CRUD, kein Auth
- Go ist in M1 nur ein Proxy, keine eigene Business-Logik
- NiceGUI laeuft parallel — kein Cutover in M1
- Kein Nginx-Setup in M1 (direkter Port-Zugriff zum Testen)

## Changelog

- 2026-04-12: Initial spec created (M1 Proof-of-Concept)
